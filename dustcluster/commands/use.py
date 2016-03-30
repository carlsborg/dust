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
    use region [region] | cluster [name] - select a set of nodes to work with

    Notes:
    Select all nodes in a region, or defined by a filter, or by a cluster config file.

    After the use command, commands like show and cluster wide commands like stop/start/@ for a target = * or None will
    apply to the set of nodes selected.

    Examples:
    use region us-east-1        # work with all nodes in this region 
    use cluster clusterA        # work with the nodes defined in cluster config clusterA.yaml
    '''

    args = cmdline.split()

    usage = "use region [region] | cluster [cluster_name]"
    if not args:
        logger.error(usage)
        return

    if args[0] == "region":
        use_region(args, cluster, logger)
    elif args[0] == "cluster":
        use_cluster(args, cluster, logger)
    else:
        logger.error(usage)


def assign(cmdline, cluster, logger):
    '''
    assign [filter] - assign the nodes from [filter] to a new cluster

    Notes:
    Applies the filter to nodes in the current region, asks for ssh details, 
    and then save this in a cluster config file for future use.

    If any of the filtered nodes are already assigned to a cluster an error 
    is raised. Use the tag command and then filter on that tag.

    Examples:
    assign tags="aws:cloudformation:stack-name":ClusterA
    assign tags="*cloudformation*":ClusterA
    '''

    args = cmdline.split()

    usage = "assign filter-expression"
    if not args:
        logger.error(usage)
        return

    target = args[0]
    target_nodes = cluster.any_nodes_from_target(target)

    if not target_nodes:
        return

    cluster.show(target_nodes)

    loginuser = raw_input("Ssh login user:")
    cloud = dict([
                ('provider' , 'ec2'),
                ('region' , cluster.cloud.region)
             ])


    name = raw_input("Name this cluster:")
 
    # write a new yaml template to ./dustcluster templates
    cluster_props = dict([
                    ('name', name),
                    ('filter' , target)
                    ])

    nodes = []
    for i, tnode in enumerate(target_nodes):
        node = dict()
        node['nodename'] = deduce_node_name(tnode, i)
        node['instance_type'] = str(tnode.instance_type)
        node['image'] = str(tnode.image)
        node['username'] = loginuser
        node['selector'] = 'id=%s' % str(tnode.id)
        nodes.append(node)

    template = dict([   ('cloud', cloud),
                        ('cluster', cluster_props),
                        ('nodes', nodes)
                        ])

    str_yaml = yaml.dump(template, default_flow_style=False)

    logger.info("\n" + str_yaml)

    save_to_file = raw_input("Save as cluster %s [yes]:" % name) or "yes"

    if save_to_file.lower().startswith('y'):
        template_file = "%s.yaml" % name
        template_file = os.path.join(cluster.clusters_dir, template_file)

        if os.path.exists(template_file):
            yesno = raw_input("%s exists. Overwrite?[y]:" % template_file) or "yes"
            if not yesno.lower().startswith("y"):
                return

        if not os.path.exists(cluster.clusters_dir):
            os.makedirs(cluster.clusters_dir)

        with open(template_file, 'w') as yaml_file:
            yaml_file.write(str_yaml)

        logger.info("Wrote cluster config to %s. Edit the file to rename nodes from defaults %s.. %s" 
                    % (template_file,  nodes[0].get('nodename'), nodes[-1].get('nodename')))

        cluster.read_all_clusters()

        cluster.switch_to_cluster(name)


def use_cluster(args, cluster, logger):

    if len(args) < 2:
        logger.error("use cluster [clustername]. e.g. use cluster clusterA.yaml")
        return

    cluster_name = args[1]

    cluster.switch_to_cluster(cluster_name)


def use_region(args, cluster, logger):

    if len(args) < 2:
        logger.info("Current region is %s" % cluster.region)
        return

    new_region = args[1]
    cloud_data = { 'provider': 'ec2', 'region' : new_region }

    cluster.unload_cur_cluster()
    cluster.init_cloud_provider(cloud_data)

    logger.info("Connected to %s " % cluster.region)

def deduce_node_name(node, i):

    for tag in node.tags.keys():
        if tag.lower() == 'name':
            return str(node.tags[tag])

    return "node%d" % i

