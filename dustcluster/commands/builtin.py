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

''' dust commands to start/stop/terminate nodes '''

# export commands
commands  = ['show', 'refresh', 'start', 'stop', 'terminate']


def show(cmdline, cluster, logger):
    '''
    show  [-vv] [filter]  - Show all nodes or filtered nodes

    Show node data from in memory cache. 
    Use $refresh to update cache.  
    Shows only nodes selected by the use command, if any.

    Example:
    show -v launch_time=*2016-04*
    show -vv ip=52.51* 
    '''

    args = cmdline.split()
    extended = 0
    if args and args[0].startswith("-"):
        if args[0] == "-v":
            extended = 1
        elif args[0] == "-vv":
            extended = 2
        else:
            logger.error("Unknown switch %s" % args[0])
            return
 
        cmdline = " ".join(args[1:])

    _show(cmdline, cluster, logger, extended)

def _show(cmdline, cluster, logger, extended=0):
    try:

        target_nodes = []
        target_nodes = get_target_nodes(logger, cluster, cmdline)
        if not target_nodes:
            return

        cluster.show(target_nodes, extended=extended)

    except Exception, e:
        logger.exception('Error: %s' % e)
        return

def refresh(cmdline, cluster, logger):
    '''
    refresh [filter]  - refresh from cloud and call show with filter

    Note that some operations (start/stop/etc) cause a refresh to occur on the next show.
    '''


    cluster.invalidate_cache()
    _show(cmdline, cluster, logger, False)

def start(cmdline, cluster, logger):
    '''   
    start [target]   - Start nodes or restart stopped nodes

    Arguments:
    none    --- Start all nodes defined in the cluster, idempotently
    target  --- A node name or filter expression (see help filters) 
                Node names and filter values can be regular expressions.

    Example:
    start worker1
    start state=stopped
    start worker[0-10]
    stop worker*
    '''    

    try:

        target_nodes = get_target_nodes(logger, cluster, cmdline)

        if not target_nodes:
            logger.info('no target nodes to operate on')
            return

        for node in target_nodes:

            if not node.hydrated and not node.key:
                logger.info("No key name configured for this node in the template. Need a key name to launch a node.")
                keyname = raw_input("Keyname [Enter to use dustcluster default]:")
                if keyname:
                    node.key = keyname
                else:
                    node.key, keyfile = cluster.get_default_key()
                    logger.info("Using default key [%s] in [%s]" % (node.key, keyfile)) 

            node.start()

    except Exception, e:
        logger.exception('Error: %s' % e)
        return

    logger.info( 'ok' )

    cluster.invalidate_cache()

def stop(cmdline, cluster, logger):
    '''
    stop [target]   - Stop nodes

    Arguments:
    none    --- Stop all nodes defined in the cluster, idempotently
    target  --- A node name or filter expression (see help filters) 
                Node names and filter values can be regular expressions.

    Example:
    stop failover1
    stop state=running
    stop worker[0-20]
    stop worker*
    '''
    operation(logger, cluster, 'stop', cmdline)
    cluster.invalidate_cache()

def terminate(cmdline, cluster, logger):
    '''
    terminate [target]  - Terminate nodes 

    Arguments:
    none    --- Terminate all nodes defined in the cluster, idempotently
    target  --- A node name or filter expression (see help filters) 
                Node names and filter values can be regular expressions.

    Example:
    terminate failover1
    terminate state=running
    terminate worker[0-20]
    terminate worker*
    '''
    operation(logger, cluster, 'terminate', cmdline, confirm=True)
    cluster.invalidate_cache()

def operation(logger, cluster, op, target_node_str=None, confirm=False):
    ''' invoke attribute op on a set of nodes ''' 

    try:

        target_nodes = get_target_nodes(logger, cluster, target_node_str)

        if not target_nodes:
            logger.info('no target nodes to operate on')
            return

        if confirm:
            logger.debug( "Invoking %s on these nodes" % op )
            cluster.show(target_nodes)

            confirm_str = "Continue [Y/N]:"
            s = raw_input(confirm_str) 
            while( s.lower() != 'y' and s.lower() != 'n' ):
                s = raw_input(confirm_str) 

            if s.lower() == 'n':
                return

        for node in target_nodes:
            getattr(node, op)()

    except Exception, e:
        logger.exception('Error: %s' % e)
        return

    logger.info( 'ok' )


def get_target_nodes(logger, cluster, target_node_str=None):

    target_nodes = cluster.resolve_target_nodes(op='show', target_node_name=target_node_str)

    return target_nodes

