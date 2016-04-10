import pprint
from boto import cloudformation
from troposphere import ec2, Ref, Template, GetAtt
import yaml
import boto
import copy
import os

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

    clusters = {}

    for cluster_name, obj_yaml in cluster.clusters.iteritems():

        region = obj_yaml.get('cloud').get('region')

        if region not in clusters:
            clusters[region] = []

        clusters[region].append(obj_yaml)

    for region in clusters:
        print "Region: %s" % region

        for obj_yaml in clusters[region]:
            print " ", obj_yaml.get('cluster').get('name')

def create_cluster(args, cluster, logger):
    '''
        parse a yaml spec for a cluster and create a cloud formation 
        template using troposphere. create this cluster as a cfn stack.
    '''

    try:

        specfile = args[1]

        cfn_id = 'cloudformation-connection-%s' % cluster.cloud.region

        str_yaml = ""
        with open(specfile, "r") as fh:
            str_yaml = fh.read()

        obj_yaml = yaml.load(str_yaml)

        # use troposphere to write out a cloud formation template
        cfn_template = Template()
        nodes = obj_yaml.get('nodes')
        nodes = expand_clones(nodes)
        obj_yaml['nodes'] = nodes

        # placement group
        cluster_spec = obj_yaml.get('cluster')

        print cluster_spec
        if not cluster_spec:
            raise Exception("No cluster section in template %s" % specfile)

        cluster_name = cluster_spec.get('name')
        if not cluster_name:
            raise Exception("No cluster name in template %s" % specfile)


        # placement group
        enable_placement = cluster_spec.get('use_placement_group')

        placement_group = None
        if enable_placement:
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

        if str(cluster_spec.get('create_vpc')).lower() == 'yes':
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

        elif cluster_spec.get('vpc_id'):
            vpc_id     = cluster_spec.get('vpc_id')
            vpc_subnet = cluster_spec.get('subnet_id')

        if vpc_id and not vpc_subnet:
            logger.error("Need to specify subnet_id and vpc_id if you want to launch nodes into a vpc")
            return

        # create a security group
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


        cfn_template.add_resource(node_sec_group)

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
        cfn_template.add_resource(intracluster_sec_group)

        # create instances 

        for node in nodes:
            nodename = node.get('nodename')
            instance = ec2.Instance(nodename, 
                                    Tags = [ec2.Tag("Name", nodename)])

            keyname = node.get('key')
            if keyname:
                instance.KeyName = keyname
            else:
                logger.error("No keyname provided for node %s" % nodename)
                return
            instance.ImageId = node.get('image')
            instance.InstanceType = node.get('instance_type')

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

        logger.info(cfn_json)

        writecfnto = os.path.join(cluster.clusters_dir, "%s.cfn" % cluster_name)
        with open(writecfnto, "w") as fh:
            fh.write(cfn_json)

        logger.info("Wrote CloudFormation template to %s" % writecfnto)


        logger.info("Validating template ...")
        conn = get_cfn_connection(logger, cluster)

        valid = conn.validate_template(cfn_json)
        print valid.ValidateTemplateResult
        if valid.capabilities:
            print valid.capabilities, valid.capabilities_reason, valid.description

        try:
            cost_url = conn.estimate_template_cost(cfn_json)
            logger.info("Estimated running cost of this cluster at:  %s" % cost_url)
        except Exception, ex:
            logger.info("Error calling estimate template costs.")

        ret = raw_input("Create stack [y]:") or "y"

        if ret.lower()[0] != "y":
            return

        # create the stack

        conn.create_stack(stack_name=cluster_name,  template_body=cfn_json)

        cluster.invalidate_cache()

        save_cluster(cluster, obj_yaml, logger)

    except Exception, e:
        logger.exception('Error: %s' % e)
        return

    logger.info( 'Cluster creation kicked off. see status with $cluster status %s.' %  cluster_name)
 

def delete_cluster(args, cluster, logger):

    try:

        cluster_name = args[1]

        if cluster_name not in cluster.clusters:
            logger.error("%s is not a cluster" % cluster_name)
            return

        cfn_id = 'cloudformation-connection-%s' % cluster.cloud.region

        ret = raw_input("Please confirm: Delete stack[n]? ") or "n"

        if ret.lower()[0] != "y":
            return

        conn = get_cfn_connection(logger, cluster)

        # delete the stack
        conn.delete_stack(cluster_name)
        cluster.delete_cluster_config(cluster_name)
        cluster.read_all_clusters()

        cluster.invalidate_cache()
        logger.info("Deleted cluster")

    except Exception, e:
        logger.exception('Error: %s' % e)
        return


def expand_clones(nodes):

    ret_nodes = []

    for node in nodes:

        counter = 0
        clones = int(node.get('count') or 1)

        if clones == 1:
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


def get_cfn_connection(logger, cluster):

    cfn_id = 'cloudformation-connection-%s' % cluster.cloud.region

    conn = cluster.command_state.get(cfn_id)

    if not conn:
        logger.info("Connecting to cloud formation endpoint in %s" % cluster.cloud.region)
        conn = boto.cloudformation.connect_to_region(cluster.cloud.region,
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
    With no args, describe all stacks
    '''

    try:

        conn = get_cfn_connection(logger, cluster)

        cluster_name = args[1]

        if not cluster_name:
            stacks = conn.describe_stacks()
            for stack in stacks:
                print stack
                events = stack.describe_events()
                for event in reversed(events):
                    print event
            return

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

    logger.info('ok')

