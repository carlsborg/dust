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
Cluster command engine
'''

import time
import re
import fnmatch
import os
import yaml
import colorama

from copy import deepcopy

from dustcluster.lineterm import LineTerm
from pkgutil import walk_packages
from dustcluster import commands

from dustcluster.util import setup_logger
logger = setup_logger( __name__ )

import glob

from dustcluster.EC2 import EC2Cloud


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


class ClusterCommandEngine(object):
    '''
    Provides access to the cloud and node objects and methods for resolving a target node name to a list of nodes.
    Loads commands and invokes them. Maintains command state. 
    This object is accessible from all commands. 
    '''

    def __init__(self, config_data):

        self.cloud = None
        self.nodecache = dict() # invalidated on load template/start/stop/terminate/etc
        self.region = None

        self.dust_config_data = config_data
        self.user_data = None
        self.cur_cluster = ""
        self.provider_cache = {}

        self.validate_config()
        self.init_default_provider(config_data)

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

        self.write_user_data()


    def validate_config(self):

        required = ["aws_access_key_id", "aws_secret_access_key", "region"]
        for s in required:
            if s not in self.dust_config_data.keys():
                logger.error("Config data [%s] is missing [%s] key" % (str(self.dust_config_data.keys()), s))
                raise Exception("Bad config.")

    def write_user_data(self):

        closest_region = self.dust_config_data.get("closest_region")
        if closest_region:
            self.update_user_data("closest_region", { "region" : closest_region } )

    def invalidate_cache(self):

        if self.nodecache.get(self.cloud.region):
            del self.nodecache[self.cloud.region]

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

    def get_commands(self):
        return self._commands

    def handle_command(self, cmd, arg):

        try:
            cmddata = self._commands.get(cmd)
            if cmddata:
                _ , cmdmod = cmddata
                func = getattr(cmdmod,  cmd)
                func(arg, self, logger)
                return True
        except Exception, ex:
            logger.exception(ex)
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


    def save_cluster_config(self, name, str_yaml):
        ''' return path if saved ''' 

        template_file = "%s.yaml" % name
        template_file = os.path.join(self.clusters_dir, template_file)

        if os.path.exists(template_file):
            yesno = raw_input("%s exists. Overwrite?[y]:" % template_file) or "yes"
            if not yesno.lower().startswith("y"):
                return None

        if not os.path.exists(self.clusters_dir):
            os.makedirs(self.clusters_dir)

        with open(template_file, 'w') as yaml_file:
            yaml_file.write(str_yaml)

        self.read_all_clusters()

        return template_file

    def delete_cluster_config(self, name, region):
        template_file = "%s.yaml" % name
        template_file = os.path.join(self.clusters_dir, template_file)
        os.remove(template_file)

        template_file = "%s.%s.cfn" % (region,name)
        template_file = os.path.join(self.clusters_dir, template_file)
        if os.path.exists(template_file):
            os.remove(template_file)

        logger.info("Deleted cluster config: %s" % template_file)


    def init_default_provider(self, dust_config_data):

        default_region = dust_config_data.get("region")
        if not default_region:
            raise Exception("Dust cluster config file or aws config file does not have a default region.")

        cloud_data = { 'provider': 'ec2', 'region' :  default_region}

        self.init_cloud_provider(cloud_data)

    def switch_to_region(self, new_region):

        cloud_data = { 'provider': 'ec2', 'region' : new_region }

        self.unload_cur_cluster()

        if new_region != self.cloud.region:
            self.invalidate_cache()

        self.init_cloud_provider(cloud_data)

        logger.info("Connected to %s " % self.region)


    def switch_to_cluster(self, cluster_name):

        if cluster_name not in self.clusters:
            logger.error("%s is not a recognized cluster." % cluster_name)
            self.show_clusters()
            return

        self.cur_cluster = cluster_name

        cluster_config_data = self.clusters[cluster_name]

        cloud_data = cluster_config_data.get('cloud')

        if not cloud_data:
            raise Exception("No 'cloud:' section in template")

        self.init_cloud_provider(cloud_data)

        cluster_nodes = self.get_current_nodes()

        logger.debug(cluster_nodes)

        num_unnamed_nodes = len([node for node in cluster_nodes if not node.name])
        num_absent_nodes = len([node for node in cluster_nodes if not node.hydrated])

        self.show(cluster_nodes)

        if num_absent_nodes:
            logger.info("Found %d nodes in the cluster config that cannot be matched to any cloud reservations."
                            % num_absent_nodes)

        if num_unnamed_nodes:
            logger.info("Found %d nodes in the cloud for this cluster filter that are not in the cluster config."
                            % num_unnamed_nodes)
            logger.info("Edit the template or use the '$assign filter_expression' command to create a new one.")

        logger.debug('Switched to cluster config %s with %s nodes' % (cluster_name, len(cluster_config_data.get('nodes', [])) ))


    def init_cloud_provider(self, cloud_data):

        self.cloud, self.region = self.get_cloud_provider(cloud_data)


    def get_cloud_provider(self, cloud_data):

        provider = cloud_data.get('provider')

        if not provider:
            raise Exception("No 'provider:' section in cloud")

        cloud_provider = None
        cloudregion = cloud_data.get('region')
        if provider.lower() == 'ec2':
            cloud_provider = self.get_cloud_provider_by_region(provider, cloudregion)
        else:
            raise Exception("Unknown cloud provider [%s]." % provider)

        return cloud_provider, cloudregion


    def get_cloud_provider_by_region(self, provider, cloudregion):

        key = (provider,cloudregion)
        cloud_provider = self.provider_cache.get(key) 

        if not cloud_provider:
            cloud_provider = EC2Cloud(creds_map=self.dust_config_data, region=cloudregion)
            cloud_provider.connect()
            self.provider_cache[key] = cloud_provider

        return cloud_provider


    def show_clusters(self):

        clusters = {}

        for cluster_name, obj_yaml in self.clusters.iteritems():

            region = obj_yaml.get('cloud').get('region')

            if region not in clusters:
                clusters[region] = []

            clusters[region].append(obj_yaml)

        for region in clusters:
            print "Region: %s" % region

            for obj_yaml in clusters[region]:
                print " ", obj_yaml.get('cluster').get('name')


    def unload_cur_cluster(self):
        ''' unload a cluster template ''' 
        self.cur_cluster = ""


    def get_default_key(self, region=""):
        ''' get the default key for current or specified region

            first we go to user_data and get the default key name for this install
            if its not there, create the name
                              creaet the defauly key name entry
                              create the key
                                 -- if it already exists, show a warning
                              create the mapping in user_data

            query user data for the keys location
        '''

        try:

            if not region:
                region = self.cloud.region

            user_data = self.get_user_data()
            default_keynames = user_data.get('default-keynames') or {}

            namekey = 'ec2-default-keyname-' + region 
            default_keyname = ""
            if default_keynames:
                default_keyname = default_keynames.get(namekey) or {}

            if not default_keynames or not default_keyname:
                timestamp = time.strftime("%Y%m%d%H%M%S", time.gmtime())
                default_keyname = "dust_%s_%s" % (region, timestamp)
                default_keyname = default_keyname.replace("-", "")
                default_keynames[namekey] = default_keyname

                exists, keyname, keypath = self.cloud.create_keypair(default_keyname, self.default_keys_dir)
                self.update_user_data('default-keynames', default_keynames)

                region_key = "%s#%s" % (region, default_keyname)

                if exists and not keypath:
                    errstr = "WARNING: The default key %s exists in the cloud but wasnt created with the local dustcluster install. " % keyname
                    errstr += "You will be asked for the key file while attempting ssh operations into this cluster. "
                    errstr += "If you do not have access to this key, specify another key in the cluster config. "
                    logger.warn("%s%s%s" % (colorama.Fore.RED, errstr, colorama.Style.RESET_ALL))

                if keypath:
                    keymap = user_data.get('ec2-key-mapping') or {}
                    keymap[region_key] = keypath
                    self.update_user_data('ec2-key-mapping', keymap)
                    logger.info("Updating new key mappings to userdata [%s]" % self.user_data_file)

                return default_keyname, keypath

            keymap = self.get_user_data().get('ec2-key-mapping') or {}
            region_key = "%s#%s" % (region, default_keyname)
            keyfile = keymap.get(region_key)
            if not keyfile:
                errstr = "default key %s exists in user_data mapping but the file cannot be found" % default_keyname
                logger.error("%s%s%s" % (colorama.Fore.RED, errstr, colorama.Style.RESET_ALL))

            return default_keyname, keyfile

        except Exception, ex:
            logger.exception(ex)
            logger.error('Error getting default keys: %s' % ex)

    def get_user_data(self):

        if not self.user_data:

            if os.path.exists(self.user_data_file):
                with open(self.user_data_file, 'r') as fh:
                    self.user_data = yaml.load(fh) or {}
            else:
                self.user_data = {}

        return self.user_data


    def update_user_data(self, section, data):

        user_data = self.get_user_data()

        user_data[section] = data
        str_yaml = yaml.dump(user_data, default_flow_style=False)

        if not os.path.exists(self.dust_dir):
            os.makedirs(self.dust_dir)

        with open(self.user_data_file, 'w') as yaml_file:
            yaml_file.write(str_yaml)

        self.user_data = user_data


    def show(self, nodes, extended=False):
        ''' print summary of cloud nodes to stdout '''

        if not self.cloud:
            logger.error('Internal error. No cloud provider set.')
            return

        # get node data
        if not nodes:
            logger.debug("No nodes to show")
            return []

        logger.info("Nodes in region: %s" % self.cloud.region)

        try:
            header_data, header_fmt = nodes[0].disp_headers()

            print colorama.Fore.GREEN
            print "   ", " ".join(header_fmt) % tuple(header_data)
            print colorama.Style.RESET_ALL

            prev_cluster_name = "_"
            prev_vpc = "_"
            for node in nodes:

                node_vpc = node.get('vpc')
                if node_vpc and node_vpc != prev_vpc:
                    print ""
                    print "%s--%s:%s" % (colorama.Fore.GREEN, node_vpc, colorama.Style.RESET_ALL)
                    prev_vpc = node_vpc

                if node.cluster != prev_cluster_name:
                    if node.cluster:
                        cluster_config = self.clusters[node.cluster]
                        cluster_props = cluster_config.get('cluster')
                        name = cluster_props.get('name')
                        cluster_filter = cluster_props.get('filter')
                        if extended:
                            print( "%sCluster [%s] (%s)" % (colorama.Style.RESET_ALL, name, cluster_filter))
                        else:
                            print( "%s%s" % (colorama.Style.RESET_ALL, name))
                        prev_cluster_name = name or cluster_filter
                    else:
                        print colorama.Style.RESET_ALL
                        print( "Unassigned:" )
                        name = "Unassigned"
                        prev_cluster_name = None

                print colorama.Fore.CYAN, "    ", " ".join(header_fmt) % tuple(node.disp_data())
                ext_data = []
                if extended == 1:
                    ext_data = node.extended_data().items()
                elif extended == 2:
                    ext_data = node.all_data().items()

                if ext_data:
                    for k,v in ext_data:
                        print colorama.Style.RESET_ALL, colorama.Style.DIM, header_fmt[0] % "", k, ":", v
                    print colorama.Style.RESET_ALL

        finally:
            print colorama.Style.RESET_ALL


    def _filter_tags(self, tags, fkey, fval):

        keyregex = fnmatch.translate(fkey)
        keymatch = re.compile(keyregex)

        valregex = fnmatch.translate(fval)
        valmatch = re.compile(valregex)

        # match tag keys, then vals
        for tagkey, tagval in tags.items():
            if keymatch.match(tagkey.lower()) and valmatch.match(tagval.lower()):
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

        filterkey = filterkey.lower()
        filterval = filterval.lower()

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
                if self._filter_tags(node.get('tags'), fkey, fval):
                    filtered.append(node)

        else:

            regex = fnmatch.translate(filterval)
            valid = re.compile(regex)

            for node in nodes:
                val =  node.get(filterkey)
                if not val:
                    continue
                logger.debug("trying filter %s on %s..." % (filterval, val))
                if not valid.match(val):
                    continue
                filtered.append(node)

        return filtered


    def _find_matching_node(self, node_props, cluster_nodes):
        ''' using node_props.selector, find the matching node in cluster_nodes ''' 

        # filter by node filter
        filter_value = node_props.get('selector')
        nodename = node_props.get('nodename')

        if filter_value:
            filterkey, filterval = filter_value.split("=")
        else:
            filterkey, filterval = "tags", "name:%s" % nodename

        #logger.debug("matching template node filters [%s=%s]to cluster nodes" % (filterkey, filterval))
        matching_nodes = self._filter(cluster_nodes, filterkey, filterval)

        return matching_nodes

    def get_current_nodes(self):
        ''' same as get_current_nodes_by_cluster but flattens the map ''' 

        cur_nodes = self.get_current_nodes_by_cluster()

        # flatten
        ret_nodes = []
        for cluster_name, nodelist in cur_nodes.iteritems():
            ret_nodes.extend(nodelist)

        ret_nodes = sorted(ret_nodes, key =lambda x: (x.get('vpc'), x.cluster))

        return ret_nodes


    def get_current_nodes_by_cluster(self):
        ''' 
            return nodes matched to all clusters in this region
            if nodes are in the cluster config but not in the cloud, it creates nodes in state "absent"
            returns { clustername : (nodes, absentnodes) }
        '''

        nodecache_nodes = self.nodecache.get(self.cloud.region)
        if nodecache_nodes:
            logger.info("Retrieved [%d] nodes %s%sfrom cache%s" % (len(nodecache_nodes),
                                                                    colorama.Fore.GREEN, colorama.Style.BRIGHT, colorama.Style.RESET_ALL))
            nodes = nodecache_nodes
        else:
            nodes = self.cloud.refresh()
            logger.info("Retrieved [%d] nodes %s%sfrom cloud provider%s" % (len(nodes), 
                                                                    colorama.Fore.GREEN, colorama.Style.BRIGHT, colorama.Style.RESET_ALL))
            self.nodecache[self.cloud.region] = nodes

        clusters = []
        if self.cur_cluster:
            clusters = [self.cur_cluster]
        else:
            clusters = [cluster_name for cluster_name, cluster in self.clusters.items() if cluster.get('cloud').get('region') == self.cloud.region]

        ret_nodes = dict()
        ret_nodes['Unassigned'] =  list()
        for cluster_name in self.clusters:
            ret_nodes[cluster_name] = list()

        # iterate through configured clusters
        for cluster_name in clusters:

            cluster_nodes = self.get_cluster_nodes(nodes, cluster_name)

            for node in cluster_nodes:
                node.cluster = cluster_name

            cluster = self.clusters[cluster_name]
            cluster_props = cluster.get('cluster')
            cluster_node_props = cluster.get('nodes')

            for node_props in cluster_node_props:
                matched_nodes = self._find_matching_node(node_props, cluster_nodes)

                logger.debug("Found %s matching nodes for %s:%s", len(matched_nodes), 
                                        cluster_name, node_props.get('selector'))

                if matched_nodes:
                    for node in matched_nodes:

                        node.name = node_props.get('nodename')
                        username = node_props.get('username')
                        if username:
                            node.username = username
                        keyfile = node_props.get('keyfile')
                        if keyfile:
                            node.keyfile = keyfile

                        #if node.cluster:
                        #    logger.warning("node [%s] is configured in more than one cluster ([%s], [%s])" % 
                        #                        (node.name, node.cluster,cluster_props.get('name')))

                        node.cluster = cluster_props.get('name')
                        ret_nodes[cluster_name].append(node)
                else:
                    logger.debug("Creating absent node for %s" % node_props.get('selector'))
                    node_args = deepcopy(node_props)
                    if node_args.get('selector'):
                        node_args.pop('selector')
                    abs_node = self.cloud.create_absent_node(**node_args)
                    abs_node.cluster = cluster_props.get('name')
                    ret_nodes[cluster_name].append(abs_node)

            # sweep for non configered cluster nodes
            for node in cluster_nodes:
                if not node.name:
                    ret_nodes[cluster_name].append(node)

        # sweep for unassigned nodes
        if not self.cur_cluster:
            for node in nodes:
                if not node.cluster:
                    ret_nodes['Unassigned'].append(node)

        return ret_nodes


    def get_cluster_nodes(self, nodes, cluster_name):
        ''' filter nodes by cluster filter '''

        cur_cluster_config = self.clusters.get(cluster_name)

        # filter by cluster filter
        filterkey, filterval = "", ""

        if cur_cluster_config.get('cluster'):
            cluster_props = cur_cluster_config.get('cluster')
            cluster_filter = cluster_props.get('filter')
            if not cluster_filter:
                name = cluster_props.get('name')
                if name:
                    filterkey, filterval = 'tags', ("cluster:%s" % name)
                else:
                    raise Exception("No cluster filter or name configured in cluster %s" % cluster_name)
            elif '=' in cluster_filter:
                filterkey, filterval = cluster_filter.split("=")
            else:
                raise Exception("Cluster template must have a name or a filter of the form key=val. Got [%s]" % cluster_filter)

        logger.debug("Filtering to cluster with %s=%s" % (filterkey, filterval)) 
        cluster_nodes = self._filter(nodes, filterkey, filterval)

        return cluster_nodes


    def resolve_target_nodes(self, op='operation', target_node_name=None):
        '''
            given a target string, filter nodes from cloud provider and create a list of target nodes to operate on
            filter by all clusters
        '''
        if not self.cloud:
            raise Exception('Internal error: No cloud provider loaded.')

        cluster_nodes = self.get_current_nodes()

        if not cluster_nodes:
            return []

        # filter by target string 
        # target string can be a name wildcard or filter expression with wildcards

        if target_node_name == '*':
            return cluster_nodes

        filterkey, filterval = "", ""
        if target_node_name:
            if '=' in target_node_name:
                parts = target_node_name.split("=")
                if len(parts) != 2:
                    str_err = "Filter format error. Should be key=value for node properties or tags=key:value for tags. Use quotes if needed."
                    raise Exception("%s%s%s" %(colorama.Fore.RED, str_err, colorama.Style.RESET_ALL))
                filterkey, filterval  = parts
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


    def running_nodes_from_target(self, target_str):
        '''
        params: same as a command
        returns: target_nodes : a list of running target nodes
        '''

        target_nodes = self.any_nodes_from_target(target_str)
        if not target_nodes:
            return None

        target_nodes = [node for node in target_nodes if node.get('state') == 'running']
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

