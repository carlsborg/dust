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
import colorama

# export commands
commands = ['use', 'assign']

def use(cmdline, cluster, logger):
    '''
    use * | [region] | [cluster name] - select a set of nodes to work with

    Notes:
    Select all nodes in a region, or defined by a cluster config

    After the use command, commands like show and cluster wide commands like stop/start/@ for a target = * or None will
    apply to the set of nodes selected.

    Examples:
    use us-east-1       # work with all nodes in this region 
    use clusterA        # restrict nodes to a working set defined by member-of in login_rules.yaml
    use *               # lose working set
    '''

    args = cmdline.split()

    login_rules = cluster.config.get_login_rules()
    clusters = set([ rule.get('member-of') for rule in login_rules ])

    usage = "use [region] | [cluster_name] | *"
    if not args:
        logger.error(usage)
        logger.info("Available clusters: " + ",".join(clusters))
        return

    try:
        if args[0] in clusters or args[0] == '*':
            use_cluster(args, cluster, logger)
        else:
            use_region(args, cluster, logger)

    except Exception as e:
        logger.exception(e)
        logger.error("Error using cluster or region : [%s]" % args[0])
        

def assign(cmdline, cluster, logger):
    '''
    assign filter_exp  - specify login rules and cluster membership for nodes

    Notes:
    This command writes login rules to ~/.dustcluster/login_rules.yaml.
    You can manually edit this file and setup login rules there.

    Example:
    $assign Name=sim*
    $assign tags=stack:web*

    $assign tags=key:value
    login-user: ec2-user
    keyfile : /path/to/kyfile
    member-of: webapp

    1] member-of help:
    member-of adds nodes to a cluster, these nodes are grouped together in "show", 
    and can be made into a working set with the "use" command

    2] login rules precedence:

    login rules are applied in order that they appear in the file. 
    So given a login_rules.yaml containing:

    - selector: tags=env:prod   
        ...
    - selector: tags=env:dev
        ...
    - selector: *
        ...

    a command like "@1 service restart xyz" will search for a login rule by matching prod, dev, 
    and then default (*) in that order'''

    args = cmdline.split()

    usage = "assign [filter-exp]"
    if not args:
        logger.error(usage)
        return

    filter_exp  = args[0]
    target_nodes = cluster.any_nodes_from_target(filter_exp)

    precedence = ""
    if len(args) >= 4:
        login_user = args[1]
        keyfile    = args[2]
        member_of  = args[3]
        precedence = args[4]
    else:
        if len(target_nodes) == 0:
            logger.info("%sLogin rule [%s] matched with %s nodes%s." % 
                    (colorama.Fore.RED, filter_exp, len(target_nodes), colorama.Style.RESET_ALL))
            return

        logger.info("%sLogin rule [%s] matched with %s nodes%s." % 
                    (colorama.Fore.GREEN, filter_exp, len(target_nodes), colorama.Style.RESET_ALL))

        login_user = input("login-user: ")
        keyfile    = input("keyfile: ")

        while not os.path.exists(keyfile):
            logger.info("cannot read keyfile/does not exist")   
            keyfile    = input("keyfile: ")

        member_of  = input("member-of: ")

        ret = ""
        while ret not in ['h','l','c']:
            ret = input("Write this rule with [h]ighest or [l]owest precedence or [c]ancel: ").lower().strip()
        if ret == "c":
            return
        precedence = ret

    login_rule =  { "selector" : filter_exp, 
                    "login-user" : login_user, 
                    "keyfile" : keyfile, 
                    "member-of" : member_of }

    login_rules = cluster.config.get_login_rules()
    if precedence == "l":
        login_rules.append(login_rule)
    else:
        login_rules.insert(0, login_rule)

    cluster.config.write_login_rules()

    logger.info("Wrote login rules to %s" % cluster.config.login_rules_file)

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

