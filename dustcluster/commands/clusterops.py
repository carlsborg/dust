import pprint
from boto import cloudformation
from troposphere import ec2, Ref, Template
import yaml
import boto
import copy

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

        # create a security group
        node_sec_group = ec2.SecurityGroup('DustNodeSG')
        node_sec_group.GroupDescription = "Allow cluster nodes to access each other"
        cfn_template.add_resource(node_sec_group)

        intracluster_sec_group = ec2.SecurityGroupIngress('DustIntraClusterSG')
        intracluster_sec_group.GroupName = Ref(node_sec_group)
        intracluster_sec_group.FromPort = 0 
        intracluster_sec_group.ToPort = 65535
        intracluster_sec_group.SourceSecurityGroupName = Ref(node_sec_group)
        intracluster_sec_group.IpProtocol = 'tcp'
        cfn_template.add_resource(intracluster_sec_group)

        ssh_sec_group = ec2.SecurityGroupIngress('DustSshSG')
        ssh_sec_group.GroupName = Ref(node_sec_group)
        ssh_sec_group.FromPort = 22
        ssh_sec_group.ToPort = 22
        ssh_sec_group.CidrIp = "0.0.0.0/0"
        ssh_sec_group.IpProtocol = 'tcp'
        cfn_template.add_resource(ssh_sec_group)

        for node in nodes:
            nodename = node.get('nodename')
            instance = ec2.Instance(nodename, 
                                    Tags = [ec2.Tag("name", nodename)])

            keyname = node.get('key')
            if keyname:
                instance.KeyName = keyname
            else:
                logger.error("No keyname provided for node %s" % nodename)
                return
            instance.ImageId = node.get('image')
            instance.InstanceType = node.get('instance_type')
            instance.SecurityGroups = [ Ref(node_sec_group) ]
            cfn_template.add_resource(instance)

        # save it to ./dustcluster/clusters/name_region.cfn
        cfn_json = cfn_template.to_json()

        cluster_spec = obj_yaml.get('cluster')
        if not cluster_spec:
            raise Exception("No cluster section in template %s" % specfile)

        cluster_name = cluster_spec.get('name')
        if not cluster_name:
            raise Exception("No cluster name in template %s" % specfile)

        logger.info(cfn_json)

        ret = raw_input("Create stack[y]:") or "y"

        if ret.lower()[0] != "y":
            return

        conn = get_cfn_connection(logger, cluster)

        # create the stack
        conn.validate_template(cfn_json)

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
        node['selector'] = 'tags=name:%s'  % node.get('nodename')

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

        for event in reversed(events):
            print event

    except Exception, e:
        logger.exception('Error: %s' % e)
        return

    logger.info('ok')

