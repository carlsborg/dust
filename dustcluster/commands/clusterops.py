import pprint
from boto import cloudformation
from troposphere import ec2, Ref, Template, GetAtt
import yaml
import boto
import copy
import os
import colorama
from dustcluster.EC2 import EC2Config
from dustcluster.ec2amiprovider import EC2AMIProvider

commands = ['cluster']

def usage(logger):
    logger.error("cluster [create filename] | [status clustername] | [delete clustername] | list")


def cluster(cmdline, cluster, logger):
    '''
    cluster [create filename] | [status clustername] | [delete clustername] | list - create, delete or see cluster status

    Examples:
    cluster create slurm.yaml   # bring up a cluster and save it to ~/.dustcluster/clusters
    cluster status slurm
    cluster delete slurm
    cluster list                # see all clusters
    '''

    args = cmdline.split()

    if not args:
        usage(logger)
        return

    subcommand = args[0]

    if subcommand == 'create':
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

    user_data = cluster.get_user_data()
    region_data = user_data.get('closest_region')
    if region_data and region_data.get('region'):
        return region_data.get('region')

    region = EC2Config.find_closest_region(logger)
    region_data = { 'region' : region }
    cluster.update_user_data('closest_region', region_data)

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


def create_cluster(args, cluster, logger):
    '''
        parse a yaml spec for a cluster and create a cloud formation 
        template using troposphere. create this cluster as a cfn stack.
    '''

    try:

        specfile = args[1]

        str_yaml = ""
        with open(specfile, "r") as fh:
            str_yaml = fh.read()

        obj_yaml = yaml.load(str_yaml)

        cloud_spec = obj_yaml.get('cloud')
        target_region = cloud_spec.get('region')

        ami_provider = EC2AMIProvider()
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

        if cluster_name in cluster.clusters:
            obj_yaml = cluster.clusters[cluster_name]
            existing_region = obj_yaml.get('cloud').get('region').lower()
            raise Exception("A cluster named %s exists in region %s. Please use a different name" % 
                                    (cluster_name,existing_region))

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

            image_id = node.get('image')
            if image_id:
                instance.ImageId = image_id
            else: 
                default_ami, default_login_user = ami_provider.get_ami_for_region('amazonlinux', target_region)
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

        if not os.path.exists(cluster.clusters_dir):
            os.makedirs(cluster.clusters_dir)

        writecfnto = os.path.join(cluster.clusters_dir, "%s.%s.cfn" % (cluster_name, target_region))
        with open(writecfnto, "w") as fh:
            fh.write(cfn_json)

        logger.info("Wrote CloudFormation template to %s" % writecfnto)

        logger.info("Validating template ...")
        conn = get_cfn_connection(logger, cluster, target_region)

        valid = conn.validate_template(cfn_json)
        print valid.ValidateTemplateResult
        if valid.capabilities:
            print valid.capabilities, valid.capabilities_reason, valid.description

        try:
            if not have_nano: # boto dumps error with nano
                cost_url = conn.estimate_template_cost(cfn_json)
                logger.info("Estimated running cost of this cluster at:  %s" % cost_url)
        except Exception, ex:
            logger.info("Could not estimate template costs.")

        ret = raw_input("Create stack [y]:") or "y"

        if ret.lower()[0] != "y":
            return

        # create the stack

        conn.create_stack(stack_name=cluster_name,  template_body=cfn_json)

        cluster.invalidate_cache()

        save_cluster(cluster, obj_yaml, logger)

    except Exception, e:
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

        ret = raw_input("Please confirm: Delete stack[n]? ") or "n"

        if ret.lower()[0] != "y":
            return

        conn = get_cfn_connection(logger, cluster, region)

        # delete the stack
        conn.delete_stack(cluster_name)
        cluster.delete_cluster_config(cluster_name, region)
        cluster.read_all_clusters()

        cluster.invalidate_cache()

        if cluster.cur_cluster == cluster_name:
            cluster.cur_cluster = ""
        logger.info("Deleted cluster")

    except Exception, e:
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
    ''' write cluster config of the new cluster with filters '''

    cluster_props = obj_yaml.get('cluster')
    name = cluster_props.get('name')
    cluster_props['filter']= "tags=aws:cloudformation:stack-name:%s" % name

    nodes_props = obj_yaml.get('nodes')
    for node in nodes_props:
        node['selector'] = 'tags=Name:%s'  % node.get('nodename')

    str_yaml = yaml.dump(obj_yaml, default_flow_style=False)
    ret = cluster.save_cluster_config(name, str_yaml)

    if ret:
        logger.info("Wrote cluster to %s" % ret)
    return ret


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
                print stack
                events = stack.describe_events()
                for event in reversed(events):
                    print event
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
            print event.timestamp, event.resource_type, event.logical_resource_id,\
                event.resource_status, startColorCyan, event.resource_status_reason or "", endColor

    except Exception, e:
        logger.exception('Error: %s' % e)
        return

    logger.info('%sUse $refresh to update node state%s' % (colorama.Fore.GREEN, colorama.Style.RESET_ALL))

    logger.info('ok')

