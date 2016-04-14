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

import yaml
import os
import colorama

'''
dust command for invoking ssh operations on a set of nodes, or entering a raw ssh shell to a single node 
'''

# export commands
commands  = ['atssh']

# @target cmd - line bufferred and raw mode ssh

def atssh(cmdline, cluster, logger):
    '''
    @[target] [cmd]     - ssh command or ssh shell.  see help atssh.

    @[target] [cmd]     - execute shell command cmd on [target]
    @ [cmd]             - execute shell command cmd on all nodes
    @nodename           - enter raw shell mode on a single node 

    Arguments:
    shell cmd   --- Shell command to invoke on the nodes via ssh 
    target      --- A node name or filter expression (see help filters) 
                    Node names and filter values can be wildcards
    nodename    --  A single node name

    
    @[target] [cmd] and @[nodename] use the same interactive shell.

    Example:
    @worker* restart service xyz
    @master sudo apt-get install xyz
    @ tail /etc/resolve.conf
    '''
    is_error = False

    try:
        target = cmdline.split()[0]

        target_nodes = cluster.running_nodes_from_target(target)
        if not target_nodes:
            return

        sshcmd = cmdline[len(target):].strip()

        if sshcmd:
            logger.info( 'running [%s] over ssh on nodes: %s' % (sshcmd,  str([node.name for node in target_nodes])) )
            for node in target_nodes:
                keyfile = _get_key_file(node, cluster, logger)
                if keyfile:
                    cluster.lineterm.command(keyfile, node, sshcmd)
        else:
            if len(target_nodes) > 1: 
                logger.info( 'Raw shell support is for single host targets only. See help atssh' )
                return

            keyfile = _get_key_file(target_nodes[0], cluster, logger)
            if keyfile:
                cluster.lineterm.shell(keyfile, target_nodes[0])

    except Exception, ex:
        logger.exception( ex )
        is_error = True

    if not is_error:
        logger.info('ok')


def _get_key_file(node, cluster, logger):
    '''
    if node has a keyfile property return it, else find a mapped key 
    '''

    if node.keyfile: 
        return node.keyfile

    if not node.key:
        logger.error("No keyfile and no key configured for this node.")
        return ""

    keyfile = _get_key_location(node.key, cluster, logger)
    if not keyfile:
        str_err = "No keyfile mapping found for key [%s]. This mapping should be in ~./dustcluster/userdata." % node.key
        str_err += "Or as 'keyfile' in the cluster config"
        logger.error("%s%s%s" %(colorama.Fore.RED, str_err, colorama.Style.RESET_ALL))
        return ""

    return keyfile


def _get_key_location(key, cluster, logger):
    ''' lookup the commandstate keymapping cache for key to file mapping
        if it isn't there, create an entry for this key in ~./dustcluster/userdata
        and update the cache'''

    ret = {}

    state_key = 'atssh-keymap'

    user_data = cluster.get_user_data()
    keymap = user_data.get('ec2-key-mapping') or {}

    dirty = False
    keyfile = keymap.get("%s#%s" % (cluster.cloud.region,key))
    if keyfile:
        ret[key] = keyfile
    else:
        keypath = raw_input("Path to key %s for region %s:" % (key, cluster.cloud.region))
        if not keypath or not os.path.exists(keypath):
            logger.error("No key file at that location")
            return ""

        keymap[str(cluster.cloud.region + '#' + key)] = keypath
        dirty = True
        ret[key] = keypath

    if dirty:
        cluster.update_user_data('ec2-key-mapping', keymap)
        logger.info("Updating new key mappings to userdata [%s]" % cluster.user_data_file)

    return ret[key]

