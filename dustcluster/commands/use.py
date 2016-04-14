# Copyright (c) Ran Dugal 2014
#
# This file is part of dust.
#
# Licensed under the GNU Affero General Public License v3, which is available at
# http://www.gnu.org/licenses/agpl-3.0.html
# 
# This program is distributed in the hope that it will be useful, but WITHOUT 
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU Affero GPL for more details.
#

''' dust command for getting and putting files from/to a set of nodes '''

import yaml
import os
from collections import OrderedDict

# export commands
commands = ['use', 'assign']

def use(cmdline, cluster, logger):
    '''
    use [region] | [cluster name] - select a set of nodes to work with

    Notes:
    Select all nodes in a region, or defined by a cluster config

    After the use command, commands like show and cluster wide commands like stop/start/@ for a target = * or None will
    apply to the set of nodes selected.

    Examples:
    use us-east-1       # work with all nodes in this region 
    use clusterA        # work with the nodes defined in cluster config saved as ./dustcluster/clusters/clusterA.yaml
    '''

    args = cmdline.split()

    usage = "use [region] | [cluster_name]"
    if not args:
        logger.error(usage)
        return

    try:
        if args[0] in cluster.clusters:
            use_cluster(args, cluster, logger)
        else:
            use_region(args, cluster, logger)

    except Exception, e:
        logger.exception(e)
        logger.error("Error using cluster or region : [%s]" % args[0])
        

def assign(cmdline, cluster, logger):
    '''
    assign filter_exp - assign the nodes from a filter expression to a new cluster

    Notes:
    Applies the filter to nodes in the current region, asks for login details, 
    and then save this in a cluster config file for future use.

    If any of the filtered nodes are already assigned to a cluster an error 
    is raised. Use the tag command and then filter on that tag.

    Examples:
    assign tags="aws:cloudformation:stack-name":ClusterA
    assign tags="*cloudformation*":ClusterA
    assign key=prodkey
    '''

    args = cmdline.split()

    usage = "assign filter-expression"
    if not args:
        logger.error(usage)
        return

    filter_exp = args[0]
    target_nodes = cluster.any_nodes_from_target(filter_exp)

    if not target_nodes:
        return

    target_cluster = ""
    if len(args) > 1:
        target_cluster = args[1]

    cluster.show(target_nodes)

    append_nodes = False
    if target_cluster in cluster.clusters:
        append_nodes(filter_exp, target_nodes, target_cluster, cluster, logger)
    else:
        write_new_cluster(filter_exp, target_nodes, target_cluster, cluster, logger)

def append_nodes(target, target_nodes, target_cluster, cluster, logger):
    print "TBD"
    pass

def write_new_cluster(filter_exp, target_nodes, target_cluster, cluster, logger):

    loginuser = raw_input("Ssh login user:")
    cloud = dict([
                ('provider' , 'ec2'),
                ('region' , cluster.cloud.region)
             ])

    if target_cluster:
        name = target_cluster
    else:
        name = raw_input("Name this cluster:")

    # write a new yaml template to ./dustcluster templates
    cluster_props = dict([
                    ('name', name),
                    ('filter' , filter_exp)
                    ])

    nodes = []
    for i, tnode in enumerate(target_nodes):
        node = dict()
        node['nodename'] = deduce_node_name(tnode, i)
        node['username'] = loginuser
        node['selector'] = deduce_selector(tnode, i)
        nodes.append(node)

    template = dict([   ('cloud', cloud),
                        ('cluster', cluster_props),
                        ('nodes', nodes)
                        ])

    str_yaml = yaml.dump(template, default_flow_style=False)

    logger.info("\n" + str_yaml)

    save_to_file = raw_input("Save as cluster %s [yes]:" % name) or "yes"

    if save_to_file.lower().startswith('y'):
            
        ret = cluster.save_cluster_config(name, str_yaml)
        if ret: 
            logger.info("Wrote cluster config to %s. Edit the file to rename nodes from defaults %s.. %s" 
                        % (ret,  nodes[0].get('nodename'), nodes[-1].get('nodename')))

            #cluster.switch_to_cluster(name)
            cluster.invalidate_cache()  # we want refresh to pick up the new names


def use_cluster(args, cluster, logger):

    cluster_name = args[0]
    cluster.switch_to_cluster(cluster_name)


def use_region(args, cluster, logger):

    new_region = args[0]

    if new_region == '*':
        new_region = cluster.cloud.region

    cluster.switch_to_region(new_region)

def deduce_node_name(node, i):

    for tag,val in node.get('tags').items():  
        if tag.lower() == 'name' and val.strip():
            return str(node.get('tags')[tag])

    return "node%d" % i

def deduce_selector(node, i):

    for tag,val in node.get('tags').items():
        if tag.lower() == 'name' and val.strip():
            return "tags=%s:%s" % ( "Name", str(node.get('tags')[tag]) )

    return 'id=%s' % str(node.get('id'))

