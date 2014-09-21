'''
Cloud cluster class   
'''

import re
import fnmatch

from dustcluster import loadcnf
from dustcluster.lineterm import LineTerm
from dustcluster.util import setup_logger
logger = setup_logger( __name__ )

class Cluster(object):
    ''' 
    Provides access to the cloud and node objects and methods for resolving a target node name to a list of nodes. 
    '''

    def __init__(self):
        self.cloud = None
        self.lineterm = LineTerm()

    def load_template(self, config_file):
        ''' load a cluster template ''' 
        self.cloud = loadcnf.load_template(config_file)

    def load_default_keys(self, default_keypath):
        ''' load default dust keys or create them '''
        self.cloud.load_default_keys(default_keypath)

    def _filter(self, nodes, filterkey, filterval):
        '''
        filter a list of nodes by attribute values
        e.g. filterkey=state,  filterval=running
        '''

        filtered = []

        if not filterkey:
            return nodes

        regex = fnmatch.translate(filterval)
        valid = re.compile(regex)

        for node in nodes:
            if filterkey:
                val =  getattr(node, filterkey, None)
                if not val:
                    continue
                logger.debug("trying filter %s on %s..." % (filterval, val))
                if not valid.match(val):
                    continue
            filtered.append(node)

        return filtered

    def resolve_target_nodes(self, op='operation', target_node_name=None):
        '''
            given a target string, create a list of target nodes to operate on
        '''
        if not self.cloud:
            logger.error('No cloud config loaded. See help load') 
            return

        # target string can be a filter expression
        filterkey = ""
        filterval = ""
        if target_node_name:
            if '=' in target_node_name:
                filterkey, filterval = target_node_name.split("=")
            else:
                filterkey, filterval = 'name', target_node_name

        # refresh state and identify template nodes
        member_nodes, nonmember_nodes = self.cloud.retrieve_node_state()

        if op:
            if filterkey:
                logger.info( "invoking %s on nodes where %s=%s" % (op, filterkey, filterval) )
            else:
                logger.info( "invoking %s on all nodes" % op )

        target_nodes  = self._filter(member_nodes, filterkey, filterval)
        target_nodes += self._filter(nonmember_nodes, filterkey, filterval)

        if not target_nodes:
            logger.info( 'no nodes found that match filter %s=%s' % (filterkey, filterval) )

        return target_nodes

    def show(self, target=None):
        ''' print summary of cloud nodes to stdout '''
        if not self.cloud:
            logger.error('No cloud config loaded. See help load') 
            return
        self.cloud.show(target)


    def running_nodes_from_target(self, target_str):
        '''
        params: same as a command
        returns: target_nodes : a list of running target nodes
        '''

        target_nodes = self.resolve_target_nodes(target_node_name=target_str)

        if not target_nodes:
            return None

        target_nodes = [node for node in target_nodes if node.state == 'running']

        if not target_nodes:
            logger.info( 'No target nodes are in the running state' )
            return None

        return target_nodes

    def logout(self):
        self.lineterm.shutdown()

