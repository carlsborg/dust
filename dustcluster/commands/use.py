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
from collections import OrderedDict

# export commands

commands = ['use']


#TODO: store key file- and loginuser- mappings in .dustcluster/mapping
def use(cmdline, cluster, logger):
    '''
    use region [region] | filter [filter] | template [file] - use a set of nodes. all nodes in a region, or defined by a filter, or by a template file.

    Notes:
    After the use command, commands like show and cluster wide commands like stop/start/@ for a target = * or None will
    apply to the set of nodes selected. 

    When used with the filter argument, applies the filter to nodes in the current region, asks for ssh details, 
    and then save this in a template file for future use.

    Examples:
    use region us-east-1        # work with all nodes in this region 
    use filter tags=env:dev     # work with nodes with this filter
    use template mycluster.yaml # work with the nodes defined in mycluster.yaml 
    '''

    args = cmdline.split()

    usage = "use region [region] | filter [filter] | template [file]"
    if not args:
        logger.error(usage)
        return

    if args[0] == "region":
        use_region(args, cluster, logger)
    elif args[0] == "filter":
        use_filter(args, cluster, logger)
    elif args[0] == "template":
        use_template(args, cluster, logger)
    else:
        logger.error(usage)

def use_filter(args, cluster, logger):

    # TODO: retain node names and loginusers if already there.
    #       prompt for save template

    if len(args) < 2:
        logger.error("use filter filter_expression. e.g. use filter state=running")
        return

    target = args[1]
    target_nodes = cluster.any_nodes_from_target(target)

    if not target_nodes:
        return

    cluster.show(target_nodes)

    loginuser = raw_input("Ssh login user:")
    cloud = dict([
                ('provider' , 'ec2'),
                ('region' , cluster.cloud.region)
             ])
    
    # write a new yaml template to ./dustcluster templates
    cluster_props = dict([
                    ('name', 'user_selected'),
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

    cluster.load_template_from_yaml(str_yaml)

    target_nodes = cluster.any_nodes_from_target(target)
    cluster.show(target_nodes)

    save_to_file = raw_input("Save template to file [no]:")

    if save_to_file.lower().startswith('y'):

        name = raw_input("Name this cluster:")
        template_file = "%s.yaml" % name

        with open(template_file, 'w') as yaml_file:
            yaml_file.write(str_yaml)

        logger.info("\n" + str_yaml)
        logger.info("Wrote template to %s. Edit the template to rename nodes from defaults %s.. %s" 
                    % (template_file,  nodes[0].get('nodename'), nodes[-1].get('nodename')))

    else:
        logger.info("Using cluster. Save template and edit it to rename nodes.")


def use_template(args, cluster, logger):

    if len(args) < 2:
        logger.error("use template template_file. e.g. use template mycluster.yaml")
        return

    template_file = args[1]

    cluster.load_template(template_file)
    cluster_nodes, num_absent_nodes = cluster.resolve_cluster_nodes()
    num_unnamed_nodes = len([node for node in cluster_nodes if not node.name])

    cluster.show(cluster_nodes)

    if num_absent_nodes:
        logger.info("Found %d nodes in the template that cannot be matched to any cloud reservations."
                        % num_absent_nodes)

    if num_unnamed_nodes:
        logger.info("Found %d nodes in the cloud for this cluster filter that are not in the template."
                        % num_unnamed_nodes)
        logger.info("Edit the template or use the '$use filter_expression' command to create a new one.")

def use_region(args, cluster, logger):

    if len(args) < 2:
        logger.info("Current region is %s" % cluster.region)
        return

    new_region = args[1]
    config_data = { 'provider': 'ec2', 'region' : new_region }

    if cluster.cloud:
        logger.info("Unloading current template")
        cluster.unload_template()

    cluster.load_template_from_config(config_data)

    logger.info("Connected to %s " % cluster.region)

def deduce_node_name(node, i):

    for tag in node.tags.keys():
        if tag.lower() == 'name':
            return node.tags[tag]

    return "node%d" % i

