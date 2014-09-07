'''
dust command for invoking ssh operations on a set of nodes, or entering a raw ssh shell to a single node 
'''

import dustcluster.lineterm as lineterm 
from dustcluster.util import running_nodes_from_target

# @target cmd - line bufferred and raw mode ssh 

def atssh(cmdline, cluster, logger):
    '''
    ssh commands
    '''

    target = cmdline.split()[0]

    target_nodes = running_nodes_from_target(target, cluster, logger)
    if not target_nodes:
        return

    sshcmd = cmdline[len(target):].strip()

    if sshcmd:
        logger.info( 'running [%s] over ssh on nodes: %s' % (sshcmd,  str([node.name for node in target_nodes])) )
        for node in target_nodes:
            lineterm.command(cluster.keyfile, node, sshcmd)
    else:
        if len(target_nodes) > 1: 
            logger.info( 'Raw shell support is for single host targets only. See help atssh' )
            return

        lineterm.shell(cluster.keyfile, target_nodes[0])

    logger.info('ok')

# export commands
commands  = { 
'atssh':    '''
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
}

# set docstrings
atssh.__doc__ = commands['atssh']

