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

import colorama

''' dust commands to start/stop/terminate nodes '''

# export commands
commands  = ['show', 'refresh', 'start', 'stop', 'terminate']


def show(cmdline, cluster, logger):
    '''
    show  [-vv] [filter | search_term]  - show all nodes or filtered nodes

    List node data from in memory cache. If filter does not match a node index,
    cluster name, node name, or EC2 attribute key=value expression then search
    all attributes and tags.

    Use $refresh to update cache.  
    Shows only nodes selected by the use command, if it was invoked earlier.

    -v  show more attributes
    -vv show all attributes

    Example:    
    show 1,3,4                   # filter_exp matches index numbers
    show worker[3-15]            # filter_exp matchs node names
    show launch_time=2017-10*    # filter_exp matches EC2 attribute 
    show 192.168.0.1             # no filter_exp match, use as search term 
    show state=running           # filter_exp matches 
    show running                 # search term matches

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

    if not cmdline.strip():
        cmdline = '*'

    _show(cmdline, cluster, logger, extended)

def _show(cmdline, cluster, logger, extended=0):
    try:

        target_nodes = []
        target_nodes = get_target_nodes(logger, cluster, cmdline, search=True)
        if not target_nodes:
            return

        cluster.show(target_nodes, extended=extended)

    except Exception as e:
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
    start filter   - start nodes or restart stopped nodes

    Arguments:
    none    --- Start all nodes defined in the cluster, idempotently
    filter  --- A node name or filter expression (see help filters) 
                Node names and filter values can be regular expressions.

    Example:
    start 3,4,5
    start devdb,dev1,dev2
    start state=stopped
    start worker[0-10]
    start cluster=spark1
    '''

    if not cmdline.strip():
        logger.error("start filter  - Restart stopped nodes")
        return

    try:

        target_nodes = get_target_nodes(logger, cluster, cmdline)

        if not target_nodes:
            logger.info('no target nodes to operate on')
            return

        for node in target_nodes:

            if not node.hydrated and not node.key:
                logger.info("No key name configured for this node in the template. Need a key name to launch a node.")
                keyname = input("Keyname [Enter to use dustcluster default]:")
                if keyname:
                    node.key = keyname
                else:
                    node.key, keyfile = cluster.get_default_key()
                    logger.info("Using default key [%s] in [%s]" % (node.key, keyfile)) 

            node.start()

    except Exception as e:
        logger.exception('Error: %s' % e)
        return

    logger.info( 'ok' )

    cluster.invalidate_cache()

def stop(cmdline, cluster, logger):
    '''
    stop  filter   - stop nodes

    Arguments:
    none    --- Stop all nodes defined in the cluster, idempotently
    filter  --- A node name or filter expression 

    Example:
    stop failover1
    stop state=running
    stop worker[0-20]
    stop worker*
    '''

    if not cmdline.strip():
        logger.error("stop filter   - Stop nodes")
        return
    
    operation(logger, cluster, 'stop', cmdline, confirm=True)
    cluster.invalidate_cache()

def terminate(cmdline, cluster, logger):
    '''
    terminate filter  - terminate nodes 

    Arguments:
    none    --- Terminate all nodes defined in the cluster, idempotently
    filter  --- A node name or filter expression (see help filters) 
                Node names and filter values can be regular expressions.

    Example:
    terminate failover1
    terminate state=running
    terminate worker[0-20]
    terminate worker*
    '''

    if not cmdline.strip():
        logger.error("terminate filter  - Terminate nodes")
        return

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
            cluster.show(target_nodes)
            logger.info( "%sInvoking %s on these nodes%s" % (colorama.Fore.RED, op, colorama.Style.RESET_ALL) )
            confirm_str = "Continue [Y/N]:"
            s = input(confirm_str) 
            while( s.lower() != 'y' and s.lower() != 'n' ):
                s = input(confirm_str) 

            if s.lower() == 'n':
                return

        for node in target_nodes:
            if node.state != "terminated":
                getattr(node, op)()

    except Exception as e:
        logger.exception('Error: %s' % e)
        return

    logger.info( 'ok' )


def get_target_nodes(logger, cluster, target_node_str=None, search=False):

    target_nodes = cluster.resolve_target_nodes(search=search, target_node_name=target_node_str)

    return target_nodes

