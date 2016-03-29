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
Cloud cluster class   
'''

import time
import re
import fnmatch
import os
import yaml

from copy import deepcopy

from dustcluster import loadcnf_yaml
from dustcluster.lineterm import LineTerm
from pkgutil import walk_packages
from dustcluster import commands

from dustcluster.util import setup_logger
logger = setup_logger( __name__ )

import glob


class CommandState(object):
    '''
    Commands can store arbitrary state here.  
    '''

    def __init__(self):
        self.global_state   = {}    # { command_name.var : value, where command_name can also be 'global_state' }

    def get(self, state_var):
        return self.global_state.get(state_var)

    def put(self, state_var, value):
        self.global_state[state_var] = value


class Cluster(object):
    ''' 
    Provides access to the cloud and node objects and methods for resolving a target node name to a list of nodes.
    Loads commands and invokes them. Maintains command state. 
    This object is accessible from all commands. 
    '''

    def __init__(self, config_data):

        self.cloud = None
        self.nodecache = None # invalidated on load template/start/stop/terminate/etc
        self.template = None
        self.region = None

        self.config_data = config_data
        self.user_data = None
        self.load_template_from_config(config_data)
        self.validate_config()

        self._commands = {}
        self.command_state = CommandState()
        self.lineterm = LineTerm()

        self.user_dir = os.path.expanduser('~')
        self.dust_dir = os.path.join(self.user_dir, '.dustcluster')
        self.clusters_dir = os.path.join(self.dust_dir, 'clusters')
        self.user_data_file = os.path.join(self.dust_dir, 'user_data')
        self.default_keys_dir = os.path.join(self.dust_dir, 'keys')

        self.clusters = {}
        self.read_all_clusters()

    def validate_config(self):

        required = ["aws_access_key_id", "aws_secret_access_key", "region"]
        for s in required:
            if s not in self.config_data.keys():
                logger.error("Config data [%s] is missing [%s] key" % (str(self.config_data.keys()), s))
                raise Exception("Bad config.")

    def invalidate_cache(self):
        if self.nodecache:
            self.nodecache = None

    def load_commands(self):
        '''
        discover commands under dustcluster.commands relative to this module, and dynamically import command modules
        look for more paths inside ~/.dustcluster/user_commands
        '''

        start_time = time.time()

        cmds = walk_packages( commands.__path__, commands.__name__ + '.')
        cmdmods  = [cmd[1] for cmd in cmds]
        logger.debug( '... loading commands from %s modules' % len(cmdmods))
        logger.debug(list(cmdmods))

        # import commands and add them to the commands map
        for cmdmod in cmdmods:
            newmod = __import__(cmdmod, fromlist=['commands'])

            for cmdname in newmod.commands:
                cmdfunc =  getattr(newmod, cmdname, 'None')
                if not cmdfunc:
                    logger.error('exported command %s not found in %s' % (cmdname, newmod))
                    continue
                self._commands[cmdname] = (cmdfunc.__doc__, newmod)

        end_time = time.time()

        if self._commands:
            logger.debug('... loaded %s commands from %s in %.3f sec:' % \
                            (len(self._commands), commands.__name__, (end_time-start_time))  )

        for cmd, (shelp, cmdmod) in self._commands.items():
            logger.debug( '%s %s' % (cmdmod.__name__, shelp.split('\n')[1]))

    def  get_commands(self):
        return self._commands

    def handle_command(self, cmd, arg):
        cmddata = self._commands.get(cmd)
        if cmddata:
            _ , cmdmod = cmddata
            func = getattr(cmdmod,  cmd)
            func(arg, self, logger)
            return True

        return False

    def read_all_clusters(self):
        wildcardpath = os.path.join(self.clusters_dir, "*.yaml")
        cluster_files = glob.glob(wildcardpath)
        logger.debug("found [%d] clusters in %s" % (len(cluster_files), wildcardpath))
        clusters = {}
        for cluster_file in cluster_files:
            
            if os.path.isfile(cluster_file):
                with open(cluster_file, "r") as fh:
                    cluster = yaml.load(fh.read())
                    cluster_props = cluster.get('cluster')
                    cluster_name = cluster_props.get('name')
                    clusters[cluster_name] = cluster

        self.clusters = clusters

    def load_template(self, config_file):

        self.cloud, self.template, self.region = loadcnf_yaml.load_template(config_file, creds_map=self.config_data)
        self.invalidate_cache()

    def load_template_from_yaml(self, str_yaml):

        self.cloud, self.template, self.region = loadcnf_yaml.load_template_from_yaml(str_yaml, creds_map=self.config_data)
        self.invalidate_cache()
        logger.info("To unload this cluster do $use %s" % self.cloud.region)

    def load_template_from_config(self,config_data):

        cluster_config = {}

        # create cluster objects with defaults
        cluster_config["region"] = config_data.get("region")

        logger.info("Setting region to %s" % cluster_config["region"])

        self.cloud , self.template, self.region = loadcnf_yaml.load_template_from_map(
                                               cluster_config, creds_map=self.config_data)
        self.invalidate_cache()

    def unload_template(self):
        ''' unload a cluster template ''' 
        self.cloud = None
        self.template = None
        self.region = None
        self.invalidate_cache()


    def get_default_key(self):
        ''' get the default key for this region and provider '''

        try:

            keymap = self.get_user_data('ec2-key-mapping') or {}

            keyname = "%s_dustcluster" % (self.cloud.region)
            keyname = keyname.translate(None, "-")

            region_key = "%s#%s" % (self.cloud.region, keyname)
            keyfile = keymap.get(region_key)
            if keyfile:
                return keyname, keyfile

            keyname, keypath = self.cloud.create_keypair(keyname, self.default_keys_dir)

            keymap[region_key] = keypath
            self.update_user_data('ec2-key-mapping', keymap)
            logger.info("Updating new key mappings to userdata [%s]" % self.user_data_file)
            return keyname, keypath

        except Exception, ex:
            logger.error('Error getting default keys: %s' % ex)


    def set_template(self, cloud):
        ''' set a cluster template ''' 
        self.cloud = cloud
        self.invalidate_cache()


    def get_user_data(self, section):

        if not self.user_data:

            if os.path.exists(self.user_data_file):
                with open(self.user_data_file, 'r') as fh:
                    self.user_data = yaml.load(fh) or {}
            else:
                self.user_data = {}

        return self.user_data.get(section)


    def update_user_data(self, section, data):

        self.user_data[section] = data
        str_yaml = yaml.dump(self.user_data, default_flow_style=False)

        if not os.path.exists(self.dust_dir):
            os.makedirs( self.dust_dir )

        with open(self.user_data_file, 'w') as yaml_file:
            yaml_file.write(str_yaml)


    def show(self, nodes, extended=False):
        ''' print summary of cloud nodes to stdout '''

        if not self.cloud:
            logger.error('Internal error. No cloud config or template loaded.')
            return

        if self.template:
            cluster_props = self.template.get('cluster')
            name = cluster_props.get('name')
            if not name:
                cluster_filter = cluster_props.get('filter')
            logger.info( "Showing nodes for cluster [%s] in region [%s]" % (name or cluster_filter, self.cloud.region))
        else:
            logger.info( "All nodes in current region: %s" % self.cloud.region)

        # get node data
        if not nodes:
            logger.debug("No nodes to show")
            return []

        header_data, header_fmt = nodes[0].disp_headers()

        node_data = [node.disp_data() for node in nodes]

        node_extended_data = []
        if extended:
            node_extended_data = [node.extended_data() for node in nodes]

        # render node data
        startColorGreen = "\033[0;32;40m"
        startColorBlue  = "\033[0;34;40m"
        startColorCyan  = "\033[0;36;40m"
        endColor        = "\033[0m"

        try:

            print startColorGreen
            print " ".join(header_fmt) % tuple(header_data)
            print endColor

            print startColorCyan
            for i, datum in enumerate(node_data):
                print " ".join(header_fmt) % tuple(datum)
                if node_extended_data:
                    #ext_data = ",".join("%s:%s" % (k,v) for k,v in extended_node_data[i].items())
                    #print (header_fmt[0] % " "), startColorBlue, ext_data, startColorCyan
                    for k,v in node_extended_data[i].items():
                        print startColorBlue,header_fmt[0] % "", k, ":", v
                    print startColorCyan

            print endColor

        finally:
            print endColor


    def _filter_tags(self, tags, fkey, fval):

        keyregex = fnmatch.translate(fkey)
        keymatch = re.compile(keyregex)

        valregex = fnmatch.translate(fval)
        valmatch = re.compile(valregex)

        # match tag keys, then vals
        for tagkey, tagval in tags.items():
            if keymatch.match(tagkey) and valmatch.match(tagval):
                return True

        return False


    def _filter(self, nodes, filterkey, filterval):
        '''
        filter a list of nodes by attribute values
        e.g. filterkey=state,  filterval=running
        '''

        filtered = []

        if not filterkey:
            return nodes

        if filterkey == "tags":

            fkey = ""
            fval = ""

            pos = filterval.rfind(':')
            if pos:
                fval = filterval[pos+1:]
                fkey = filterval[:pos]

                if fkey[0] == '"' and fkey[-1] == '"':
                    fkey = fkey[1:-1]

            if not fkey and not fval:
                logger.error("Bad filter. Use tags=key:value, wildcards allowed on key, value.")
                return []

            for node in nodes:
                if self._filter_tags(node.tags, fkey, fval):
                    filtered.append(node)

        else:

            regex = fnmatch.translate(filterval)
            valid = re.compile(regex)

            for node in nodes:
                val =  getattr(node, filterkey, None)
                if not val:
                    continue
                logger.debug("trying filter %s on %s..." % (filterval, val))
                if not valid.match(val):
                    continue
                filtered.append(node)

        return filtered

    def resolve_cluster_nodes(self):
        ''' return a list of cloud nodes that match the cluster filter'''

        startColorGreen = "\033[0;32;40m"
        endColor        = "\033[0m"


        # refresh nodes state from cloud
        if self.nodecache:
            logger.info("Retrieved [%d] nodes %sfrom cache%s" % (len(self.nodecache), startColorGreen, endColor))
            nodes = self.nodecache
        else:
            nodes = self.cloud.refresh()
            logger.info("Retrieved [%d] nodes %sfrom cloud provider%s" % (len(nodes), startColorGreen, endColor))
            self.nodecache = nodes

        # filter by cluster filter
        filterkey, filterval = "", ""
        if self.template and self.template.get('cluster'):
            cluster_props = self.template.get('cluster')
            cluster_filter = cluster_props.get('filter')
            if not cluster_filter:
                name = cluster_props.get('name')
                if name:
                    filterkey, filterval = 'tags', ("cluster:%s" % name)
            elif '=' in cluster_filter:
                filterkey, filterval = cluster_filter.split("=")
            else:
                raise Exception("Cluster template must have a name or a filter of the form key=val. Got [%s]" % cluster_filter)

        if filterkey and filterval:
            logger.debug("Filtering to cluster with %s=%s" % (filterkey, filterval)) 
            cluster_nodes = self._filter(nodes, filterkey, filterval)
        else:
            cluster_nodes = nodes

        # name the nodes from the cluster template
        cluster_nodes, num_absent_nodes = self.match_nodes_to_template(cluster_nodes)

        return cluster_nodes, num_absent_nodes


    def resolve_target_nodes(self, op='operation', target_node_name=None):
        '''
            given a target string, filter nodes from cloud provider and create a list of target nodes to operate on
            if a cluster is being used, filter by cluster selector first
        '''
        if not self.cloud:
            logger.error('Internal error: No cloud provider loaded.')
            return

        cluster_nodes, num_absent_nodes = self.resolve_cluster_nodes()

        # filter by target string 
        # target string can be a name wildcard or filter expression with wildcards
        filterkey, filterval = "", ""
        if target_node_name:
            if '=' in target_node_name:
                filterkey, filterval = target_node_name.split("=")
            else:
                filterkey, filterval = 'name', target_node_name

        if filterkey and filterval:
            target_nodes  = self._filter(cluster_nodes, filterkey, filterval)
        else:
            target_nodes = cluster_nodes

        if op:
            if filterkey:
                logger.debug( "invoking %s on nodes where %s=%s" % (op, filterkey, filterval) )
            else:
                logger.debug( "invoking %s on all cluster nodes" % op )

        if not target_nodes:
            logger.info( 'no nodes found that match filter %s=%s' % (filterkey, filterval) )

        return target_nodes


    def match_nodes_to_template(self, cluster_nodes):
        '''
        do an outer join of the template nodes and cloud nodes using the 
        node filter expression as the key.

        assumes the list of nodes is already filtered by cluster filter
        '''

        if not self.template:
            return cluster_nodes, 0

        template_nodes = self.template.get('nodes')
        if not template_nodes:
            return cluster_nodes, len(cluster_nodes)

        absent_nodes = []

        for i, template_node in enumerate(template_nodes):

            filter_value = template_node.get('selector')
            nodename = template_node.get('nodename')

            if filter_value:
                filterkey, filterval = filter_value.split("=")
            else:
                filterkey, filterval = "tags", "name:%s" % nodename

            logger.debug("matching template node filters [%s=%s]to cluster nodes" % (filterkey, filterval))
            matching_nodes = self._filter(cluster_nodes, filterkey, filterval)
        
            logger.debug("Found %s matching nodes out of %d for this filter" % (len(matching_nodes), len(cluster_nodes)) )

            cluster_props = self.template.get('cluster')

            if not matching_nodes:
                abs_node = self.cloud.create_absent_node(**template_node)
                abs_node.clustername = cluster_props.get('name')
                absent_nodes.append(abs_node)

            for matching_node in matching_nodes:
                matching_node.name = nodename
                username = template_node.get('username')
                if username:
                    matching_node.username = username
                keyfile = template_node.get('keyfile')
                if keyfile:
                    matching_node.keyfile = keyfile

                matching_node.clustername = cluster_props.get('name')

        return cluster_nodes + absent_nodes, len(absent_nodes)


    def running_nodes_from_target(self, target_str):
        '''
        params: same as a command
        returns: target_nodes : a list of running target nodes
        '''

        target_nodes = self.any_nodes_from_target(target_str)
        if not target_nodes:
            return None

        target_nodes = [node for node in target_nodes if node.state == 'running']
        if not target_nodes:
            logger.info( 'No target nodes are in the running state' )
            return None

        return target_nodes


    def any_nodes_from_target(self, target_str):
        '''
        params: same as a command
        returns: target_nodes : a list of stopped or running target nodes
        '''

        target_nodes = self.resolve_target_nodes(target_node_name=target_str)
        if not target_nodes:
            logger.info( 'No target nodes found that match filter [%s]' % target_str)

        return target_nodes


    def logout(self):
        self.lineterm.shutdown()
