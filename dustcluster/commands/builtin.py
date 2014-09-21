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
# built in node commands

def show(cmdline, cluster, logger):
    ''' write cluster node summary to stdout '''
    target_nodes = cluster.resolve_target_nodes(op='', target_node_name=cmdline)
    if not target_nodes:
        return
    cluster.show(target_nodes)

def start(cmdline, cluster, logger):
    ''' start/restart nodes '''
    operation(logger, cluster, 'start', cmdline)

def stop(cmdline, cluster, logger):
    ''' stop nodes '''
    operation(logger, cluster, 'stop', cmdline)

def terminate(cmdline, cluster, logger):
    ''' terminate nodes ''' 
    operation(logger, cluster, 'terminate', cmdline, confirm=True)

def operation(logger, cluster, op, target_node_str=None, confirm=False):
    ''' invoke attribute op on a set of nodes ''' 

    try:

        target_nodes = cluster.resolve_target_nodes(op, target_node_str)

        if not target_nodes:
            return

        target_nodes = [node for node in target_nodes if node.state != 'terminated']

        if not target_nodes:
            logger.info('not invoking operations on terminated nodes')
            return

        if confirm:
            logger.info( "Invoking %s on these nodes" % op )
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

# export commands and help strings
commands  = {
'show': '''
        show - Show all nodes

        Retrieves state from the cloud provider.
        If a cluster template is loaded, show cluster member and non-member nodes separately.
        ''', 
'start' : '''   
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
        ''',
'stop' : '''
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
        ''',
'terminate' :   '''
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
}

# set docstrings
show.__doc__  = commands['show']
start.__doc__ = commands['start']
stop.__doc__ = commands['stop']
terminate.__doc__ = commands['terminate']

