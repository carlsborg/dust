import pprint
from boto import cloudformation
from troposphere import ec2, Ref, Template, GetAtt
import yaml
import boto
import copy
import os
import colorama
from dustcluster.EC2 import EC2Config

commands = ['cluster']

def usage(logger):
    logger.error("cluster [new] | [create clustername] | [status clustername] | [delete clustername] | list")


def cluster(cmdline, cluster, logger):
    '''
    cluster list|new|create|status|delete - list, create, delete or print cluster status

    Commands:

    cluster new
    cluster create clustername
    cluster status clustername
    cluster delete clustername
    cluster list

    Examples:

    cluster new                 # create a new cluster spec
    cluster create              # bring up a cluster using cloudformation 
    cluster status slurm
    cluster delete slurm
    cluster list                # see all cloudformation clusters
    '''

    args = cmdline.split()

    if not args:
        usage(logger)
        return

    subcommand = args[0]

    if subcommand == 'new':
        new_cluster(args, cluster, logger)
    elif subcommand == 'create':
        create_cluster(args, cluster, logger)
    elif subcommand == 'delete':
        delete_cluster(args, cluster, logger)
    elif subcommand == 'status':
        cluster_status(args, cluster, logger)
    elif subcommand == 'list':
        list_clusters(args, cluster, logger)
    else:
        usage(logger)
        return

def list_clusters(args, cluster, logger):
    cluster.show_clusters()

def get_closest_region(cluster, logger):

    user_data = cluster.config.get_userdata()
    region = user_data.get('closest_region')
    if region:
        return region

    creds = cluster.config.get_credentials()
    region = EC2Config.find_closest_region(logger, creds.get('aws_access_key_id'), creds.get('aws_secret_access_key'))
    user_data['closest_region'] = region
    cluster.config.write_userdata()

    return region

def configure_security_groups(vpc_subnet, vpc_id):

    node_sec_group = ec2.SecurityGroup('DustNodeSG')
    node_sec_group.GroupDescription = "Allow incoming ssh and icmp and all intracluster tcp"
    if vpc_subnet:
        node_sec_group.VpcId = vpc_id

    ssh_in_rule = ec2.SecurityGroupRule()
    ssh_in_rule.FromPort = 22
    ssh_in_rule.ToPort = 22
    ssh_in_rule.CidrIp = "0.0.0.0/0"
    ssh_in_rule.IpProtocol = 'tcp'

    icmp_in_rule = ec2.SecurityGroupRule()
    icmp_in_rule.FromPort = -1
    icmp_in_rule.ToPort = -1
    icmp_in_rule.CidrIp = "0.0.0.0/0"
    icmp_in_rule.IpProtocol = 'icmp'

    node_sec_group.SecurityGroupIngress = [ssh_in_rule, icmp_in_rule]

    intracluster_sec_group = ec2.SecurityGroupIngress('DustIntraClusterSG')
    if vpc_subnet:
        intracluster_sec_group.GroupId = Ref(node_sec_group)
    else:
        intracluster_sec_group.GroupName = Ref(node_sec_group)
    intracluster_sec_group.FromPort = 0 
    intracluster_sec_group.ToPort = 65535
    if vpc_subnet:
        intracluster_sec_group.SourceSecurityGroupId = Ref(node_sec_group)
    else:
        intracluster_sec_group.SourceSecurityGroupName = Ref(node_sec_group)
    intracluster_sec_group.IpProtocol = "-1"

    return node_sec_group, intracluster_sec_group 

def configure_vpc(cfn_template, cluster_name):

    vpc = ec2.VPC("DustVPC")
    vpc.CidrBlock = "10.0.0.0/16"
    vpc.Tags = [ec2.Tag("Name:", cluster_name)]
    cfn_template.add_resource(vpc)
    vpc_id = Ref(vpc)

    subnet = ec2.Subnet('dustSubnet')
    subnet.VpcId = vpc_id
    subnet.CidrBlock = "10.0.0.0/24"
    cfn_template.add_resource(subnet)
    vpc_subnet = Ref(subnet)

    net_gateway = ec2.InternetGateway('dustGateway')
    cfn_template.add_resource(net_gateway)

    attach_net_gateway = ec2.VPCGatewayAttachment('dustAttachGateway')
    attach_net_gateway.VpcId = vpc_id
    attach_net_gateway.InternetGatewayId = Ref(net_gateway)
    cfn_template.add_resource(attach_net_gateway)

    route_table = ec2.RouteTable('dustRoutetable')
    route_table.VpcId = vpc_id
    cfn_template.add_resource(route_table)

    route = ec2.Route('dustRoute')
    route.RouteTableId = Ref(route_table)
    route.DestinationCidrBlock = "0.0.0.0/0"
    route.GatewayId = Ref(net_gateway)
    route.DependsOn = "dustAttachGateway"
    cfn_template.add_resource(route)

    attach_route = ec2.SubnetRouteTableAssociation('dustAttachRouteTable')
    attach_route.SubnetId = vpc_subnet
    attach_route.RouteTableId = Ref(route_table)
    cfn_template.add_resource(attach_route)

    return vpc_id, vpc_subnet

def new_cluster(args, cluster, logger):

    name = input("Name this cluster: ")

    if (os.path.exists(cluster.config.get_clusters_dir() + "%s.cfn" % name)):
        clusters = cluster.config.get_clusters()
        logger.error("A cluster named %s already exists in region %s. Please use a different name" % 
                                    (name, clusters.get(name).get('cloud').get('region')))
        return

    numnodes = int(input("Number of nodes: "))
    nodetype = input("Node type [m4.large]: ") or "m4.large"

    use_placement_group = 'n'
    if "nano" not in nodetype and "small" not in nodetype and "micro" not in nodetype: 
        use_placement_group = input("use placement group?: [y]") or 'y'

    spec = {}
    spec['cloud']   = { 'provider' : 'ec2', 'region': cluster.cloud.region }
    spec['cluster'] = { 'name': name }

    if (use_placement_group == 'y' or use_placement_group == 'yes'):
        spec['cluster']['use_placement_group'] = 'yes'

    nodes = []
    def make_node(node_name):
        node = dict()
        node['instance_type'] = nodetype
        node['nodename'] = node_name
        return node

    node = make_node("master")
    nodes.append(node)

    if (numnodes > 1):
        node = make_node("worker")
        node['count'] = numnodes-1
        nodes.append(node)

    spec['nodes'] = nodes
    str_yaml = yaml.dump(spec, default_flow_style=False)
    ret = cluster.config.save_cluster_config(name, str_yaml)
    logger.info("Saved cluster spec to: %s" % ret)
    logger.info("Edit this file if needed and run %s$cluster create %s%s" % 
                    (colorama.Fore.GREEN, name, colorama.Style.RESET_ALL))
    cluster.config.read_all_clusters()
    cluster.clusters = cluster.config.get_clusters()

def create_cluster(args, cluster, logger):
    '''
        parse a yaml spec for a cluster and create a cloud formation 
        template using troposphere. create this cluster as a cfn stack.
    '''

    try:
        cluster.config.read_all_clusters()

        cluster_name = args[1]
        clusters = cluster.config.get_clusters()

        obj_yaml = clusters.get(cluster_name)

        if not obj_yaml:
            logger.error("no such cluster spec in %s" % cluster.config.get_clusters_dir())
            return
        
        cloud_spec = obj_yaml.get('cloud')
        target_region = cloud_spec.get('region')

        if target_region == 'closest' or not target_region:
            target_region = get_closest_region(cluster, logger)
            cloud_spec['region'] = target_region

        # for default keys, etc
        if cluster.region != target_region:
            cluster.switch_to_region(target_region)

        # use troposphere to write out a cloud formation template
        cfn_template = Template()
        nodes = obj_yaml.get('nodes')
        nodes = expand_clones(nodes)
        obj_yaml['nodes'] = nodes

        cluster_spec = obj_yaml.get('cluster')
        if not cluster_spec:
            raise Exception("No cluster section in template %s" % specfile)

        cluster_name = cluster_spec.get('name')
        if not cluster_name:
            raise Exception("No cluster name in template %s" % specfile)

        # placement group
        enable_placement = str(cluster_spec.get('use_placement_group')).lower()

        placement_group = None
        if enable_placement == 'yes' or enable_placement == 'true':
            placement_group = ec2.PlacementGroup('DustPlacementGroup')
            placement_group.Strategy='cluster'
            cfn_template.add_resource(placement_group)

            for node in nodes:
                inst_type = node.get('instance_type')
                if "large" not in inst_type:
                    logger.error("Only large instance types can be launched into placement groups.")
                    logger.error("http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/placement-groups.html")
                    return

        # subnet for VPC
        create_vpc = None
        vpc_id     = None
        vpc_subnet = None

        vpc_flag = str(cluster_spec.get('create_vpc')).lower()
        if vpc_flag == 'yes' or vpc_flag == 'true':
            vpc_id, vpc_subnet = configure_vpc(cfn_template, cluster_name)

        elif cluster_spec.get('vpc_id'):
            vpc_id     = cluster_spec.get('vpc_id')
            vpc_subnet = cluster_spec.get('subnet_id')

        if vpc_id and not vpc_subnet:
            logger.error("Need to specify subnet_id and vpc_id if you want to launch nodes into a vpc")
            return

        # create security groups
        node_sec_group, intracluster_sec_group= configure_security_groups(vpc_subnet, vpc_id)
        cfn_template.add_resource(node_sec_group)
        cfn_template.add_resource(intracluster_sec_group)

        # create instances
        have_nano = False 
        for node in nodes:
            nodename = node.get('nodename')
            instance = ec2.Instance(nodename, 
                                    Tags = [ec2.Tag("Name", nodename)])

            keyname = node.get('key')
            if keyname:
                instance.KeyName = keyname
            else:
               # default keys
                default_key = cluster_spec.get('key')
                if not default_key:
                    default_key, keypath = cluster.get_default_key(target_region)
                instance.KeyName = default_key

            image_id = cluster_spec.get('image')
            if image_id:
                instance.ImageId = image_id
                login_user = cluster_spec.get('username')
                if not login_user:
                    logger.error("Need to specify a login user with a custom AMI")
                node['username'] = login_user
            else:
                default_ami, default_login_user = cluster.cloud.get_dust_ami_for_region(target_region)
                instance.ImageId = default_ami
                node['image'] = default_ami
                node['username'] = default_login_user

            instance.InstanceType = node.get('instance_type')

            if 'nano' in instance.InstanceType:
                have_nano = True

            if create_vpc:
                instance.DependsOn = "dustAttachGateway"

            # vpc public ip
            if vpc_subnet:
                network_interface = ec2.NetworkInterfaceProperty("DustNIC" + nodename)
                network_interface.AssociatePublicIpAddress = True
                network_interface.DeleteOnTermination = True
                network_interface.DeviceIndex = 0 
                network_interface.SubnetId = vpc_subnet
                network_interface.GroupSet =  [Ref(node_sec_group)]
                instance.NetworkInterfaces = [network_interface]

            if not vpc_subnet:
                instance.SecurityGroups = [ Ref(node_sec_group) ]

            if placement_group:
                instance.PlacementGroupName = Ref(placement_group)

            cfn_template.add_resource(instance)

        # save it to ./dustcluster/clusters/name_region.cfn
        cfn_json = cfn_template.to_json()

        writecfnto = os.path.join(cluster.config.get_clusters_dir(), "%s.%s.cfn" % (cluster_name, target_region))
        with open(writecfnto, "w") as fh:
            fh.write(cfn_json)

        logger.info("Wrote CloudFormation template to %s" % writecfnto)

        logger.info("Validating template ...")
        conn = get_cfn_connection(logger, cluster, target_region)

        valid = conn.validate_template(cfn_json)
        #print valid.ValidateTemplateResult
        if valid.capabilities:
            print(valid.capabilities, valid.capabilities_reason, valid.description)

        try:
            if not have_nano: # boto dumps error with nano
                cost_url = conn.estimate_template_cost(cfn_json)
                logger.info("Estimated running cost of this cluster at:  %s" % cost_url)
        except Exception as ex:
            logger.info("Could not estimate template costs.")

        ret = input("Create stack [y]:") or "y"

        if ret.lower()[0] != "y":
            return

        # create the stack

        conn.create_stack(stack_name=cluster_name,  template_body=cfn_json)

        cluster.invalidate_cache()

        save_cluster(cluster, obj_yaml, logger)

    except Exception as e:
        logger.exception('Error: %s' % e)
        logger.error('%sCluster create threw. Please check for new instances with refresh.%s' % (colorama.Fore.RED, colorama.Style.RESET_ALL))
        return

    logger.info( '%sCluster creation kicked off. see status with $cluster status %s.%s' %  
                        (colorama.Fore.GREEN,cluster_name,colorama.Style.RESET_ALL))

    logger.info( 'Refresh node state with the $refresh command.')

def delete_cluster(args, cluster, logger):

    try:

        cluster_name = args[1]

        if cluster_name not in cluster.clusters:
            logger.error("%s is not a cluster" % cluster_name)
            return

        obj_yaml = cluster.clusters[cluster_name]
    
        region = obj_yaml.get('cloud').get('region')

        ret = input("Please confirm: Delete stack[n]? ") or "n"

        if ret.lower()[0] != "y":
            return

        conn = get_cfn_connection(logger, cluster, region)

        # delete the stack
        conn.delete_stack(cluster_name)
        cluster.config.delete_cluster_config(cluster_name, region)
        cluster.config.read_all_clusters()

        cluster.invalidate_cache()

        if cluster.cur_cluster == cluster_name:
            cluster.cur_cluster = ""
        logger.info("Deleted cluster")

    except Exception as e:
        logger.exception('Error: %s' % e)
        return


def expand_clones(nodes):

    ret_nodes = []

    for node in nodes:

        counter = 0
        clones = int(node.get('count') or 1)

        if not node.get('count'):
            ret_nodes.append(node)
        else:
            for i in range(clones):
                newnode = copy.deepcopy(node)
                newnode.pop('count')
                nodename = node.get('nodename')
                nodename_c = "%s%s" % (nodename, i)
                newnode['nodename'] = nodename_c
                ret_nodes.append(newnode)

    return ret_nodes


def save_cluster(cluster, obj_yaml, logger):
    ''' write login rules with new cluster with filters '''

    cluster_props = obj_yaml.get('cluster')
    name = cluster_props.get('name')
    filter_exp = "tags=aws:cloudformation:stack-name:%s" % name

    login_user = cluster_props.get('username') or 'ec2-user'
    region = obj_yaml.get('cloud').get('region')
    args = " %s %s %s h" % (login_user, cluster.get_default_key(region)[1] , name)
    print("ARGs", args)
    cluster.handle_command("assign", filter_exp + args)

    cluster.config.read_all_clusters()

def get_cfn_connection(logger, cluster, region):

    cfn_id = 'cloudformation-connection-%s' % region

    conn = cluster.command_state.get(cfn_id)

    if not conn:
        logger.info("Connecting to cloud formation endpoint in %s" % region)
        conn = boto.cloudformation.connect_to_region(region,
                                        aws_access_key_id=cluster.cloud.creds_map['aws_access_key_id'], 
                                        aws_secret_access_key=cluster.cloud.creds_map['aws_secret_access_key'])
        cluster.command_state.put(cfn_id, conn)

    return conn



def cluster_status(args, cluster, logger):
    '''
    cluster status [clustername]  - print notifications from the cloud for this cluster

    Examples:
    cluster status mycluster
    
    Note:
    With no args, describe all stacks _in the current region_
    '''

    try:
        
        cluster_name = None if len(args)<2 else args[1] 

        if not cluster_name:
            conn = get_cfn_connection(logger, cluster, cluster.cloud.region)

            stacks = conn.describe_stacks()
            for stack in stacks:
                print(stack)
                events = stack.describe_events()
                for event in reversed(events):
                    print(event)
            return

        obj_yaml = cluster.clusters.get(cluster_name)
        if not obj_yaml:
            logger.error("No such cluster %s" % cluster_name)

        if obj_yaml:
            region = obj_yaml.get('cloud').get('region')
        else:
            region = cluster.cloud.region

        conn = get_cfn_connection(logger, cluster, region)

        # get stack events
        events = conn.describe_stack_events(cluster_name)

        startColorCyan  = "\033[0;36;40m"
        endColor       = "\033[0m"

        for event in reversed(events):
            print(event.timestamp, event.resource_type, event.logical_resource_id,\
                event.resource_status, startColorCyan, event.resource_status_reason or "", endColor)

    except Exception as e:
        logger.exception('Error: %s' % e)
        return

    logger.info('%sUse $refresh to update node state%s' % (colorama.Fore.GREEN, colorama.Style.RESET_ALL))

    logger.info('ok')
