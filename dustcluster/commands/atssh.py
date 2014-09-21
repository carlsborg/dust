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
                cluster.lineterm.command(cluster.cloud.keyfile, node, sshcmd)
        else:
            if len(target_nodes) > 1: 
                logger.info( 'Raw shell support is for single host targets only. See help atssh' )
                return

            cluster.lineterm.shell(cluster.cloud.keyfile, target_nodes[0])

    except Exception, ex:
        logger.exception( ex )
        is_error = True

    if not is_error:
        logger.info('ok')


