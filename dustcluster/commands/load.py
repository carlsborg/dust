import pprint
from boto import cloudformation
from troposphere import ec2, Ref, Template
import yaml
import boto
import copy

commands = ['load', 'status']


def load(cmdline, cluster, logger):
    '''
    load [spec]  - bring up a cluster from a spec, and save it in the clusters

    Examples:
    tag worker* env=dev    # add tag env=dev to nodes named worker* 

    Multiple tags works.
    tag worker* tag1=val1,tag2=val2,tag3=val3 - add tags tag1,tag2,tag3 on target nodes    
    '''

    try:

        args = cmdline.split()

        if not args:
            logger.error("usage: load specfile")
            return

        specfile = args[0]

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

        for node in nodes:
            nodename = node.get('nodename')
            instance = ec2.Instance(nodename, 
                                    Tags = [ec2.Tag("name", nodename)])

            keyname = node.get('key')
            if keyname:
                instance.KeyName = keyname
            instance.ImageId = node.get('image')
            instance.InstanceType = node.get('instance_type')
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

        conn = cluster.command_state.get(cfn_id)
        if not conn:
            conn = boto.cloudformation.connect_to_region(cluster.cloud.region,
                                            aws_access_key_id=cluster.cloud.creds_map['aws_access_key_id'], 
                                            aws_secret_access_key=cluster.cloud.creds_map['aws_secret_access_key'])


        # create the stack
        conn.validate_template(cfn_json)

        conn.create_stack(stack_name=cluster_name,  template_body=cfn_json)

        cluster.invalidate_cache()

        save_cluster(cluster, obj_yaml, logger)

    except Exception, e:
        logger.exception('Error: %s' % e)
        return

    logger.info( 'Cluster creation kicked off. see status with $status %s.' %  cluster_name)
    logger.info( 'Once the nodes are up, do $use cluster %s' %  cluster_name)


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


def status(cmdline, cluster, logger):
    '''
    status [clustername]  - print notifications from the cloud for this cluster

    Examples:
    status mycluster
    
    Note:
    With no args, describe all stacks
    '''

    try:

        cfn_id = 'cloudformation-connection-%s' % cluster.cloud.region
        conn = cluster.command_state.get(cfn_id)
        if not conn:
            logger.info("Connecting to cloud formation endpoint in %s" % cluster.cloud.region) 
            conn = boto.cloudformation.connect_to_region(cluster.cloud.region,
                                            aws_access_key_id=cluster.cloud.creds_map['aws_access_key_id'], 
                                            aws_secret_access_key=cluster.cloud.creds_map['aws_secret_access_key'])


        cluster_name = cmdline.strip()
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

