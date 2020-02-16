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
import sys

from copy import deepcopy

from dustcluster.lineterm import LineTerm
from pkgutil import walk_packages
from dustcluster import commands
from dustcluster.config import DustConfig

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

    def __init__(self):

        self.cloud = None
        self.nodecache = dict() # invalidated on load template/start/stop/terminate/etc
        self.region = None

        self.config = DustConfig()

        self.cur_cluster = ""
        self.provider_cache = {}

        self.init_default_provider()

        self.clusters = self.config.get_clusters()

        self._commands = {}
        self.command_state = CommandState()
        self.lineterm = LineTerm()

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
            newmod=None 
            try:
                newmod = __import__(cmdmod, fromlist=['dustcluster.commands'])
            except Exception as e:
                logger.error("Error importing command from module [%s] %s" % (cmdmod, e))

            if not newmod:
                logger.warn("Could not import module %s from dustcluster.commands" % str(cmdmod))

            #sys.stdout.write("\rloading .. %-20s          " % cmdmod)
            #sys.stdout.flush()

            for cmdname in newmod.commands:
                cmdfunc =  getattr(newmod, cmdname, 'None')
                if not cmdfunc:
                    logger.error('exported command %s not found in %s' % (cmdname, newmod))
                    continue
                self._commands[cmdname] = (cmdfunc.__doc__, newmod)

        end_time = time.time()

        if self._commands:
            logger.debug('loaded %s commands from %s in %.3f sec\n' % \
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
        except Exception as ex:
            logger.exception(ex)
            return True

        return False

    def init_default_provider(self):

        default_region = self.config.get_userdata().get("region")

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

        if cluster_name.strip() == '*':
            self.cur_cluster = ""
        else:    
            login_rules = self.config.get_login_rules()
            clusters = set([ rule.get('member-of') for rule in login_rules ])

            if cluster_name not in clusters:
                logger.error("%s is not a recognized cluster." % cluster_name)
                self.show_clusters()
                return

            self.cur_cluster = cluster_name

        cluster_nodes = self.resolve_target_nodes()
        self.show(cluster_nodes)

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
            cloud_provider = EC2Cloud(creds_map=self.config.get_credentials(), region=cloudregion)
            cloud_provider.connect()
            self.provider_cache[key] = cloud_provider

        return cloud_provider

    def show_clusters(self):
        login_rules = self.config.get_login_rules()
        clusters = set([ rule.get('member-of') for rule in login_rules ])
        logger.info("%sConfigured clusters with logins:%s" % (colorama.Fore.GREEN, colorama.Style.RESET_ALL))
        for cluster in clusters:
            print(cluster)

    def unload_cur_cluster(self):
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

            user_data = self.config.get_userdata()
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

                exists, keyname, keypath = self.cloud.create_keypair(default_keyname, self.config.get_default_keys_dir())

                self.config.get_userdata().update( { 'default-keynames' :  default_keynames } )
                self.config.write_user_data()

                region_key = "%s#%s" % (region, default_keyname)

                if exists and not keypath:
                    errstr = "WARNING: The default key %s exists in the cloud but wasnt created with the local dustcluster install. " % keyname
                    errstr += "You will be asked for the key file while attempting ssh operations into this cluster. "
                    errstr += "If you do not have access to this key, specify another key in the cluster config. "
                    logger.warn("%s%s%s" % (colorama.Fore.RED, errstr, colorama.Style.RESET_ALL))

                if keypath:
                    keymap = user_data.get('ec2-key-mapping') or {}
                    keymap[region_key] = keypath
                    userdata = self.config.get_userdata()
                    userdata.update( { 'ec2-key-mapping':  keymap } )
                    logger.info("Updating new key mappings to userdata [%s]" % self.config.userdata_file)
                    self.config.write_user_data()

                return default_keyname, keypath

            keymap = self.config.get_userdata().get('ec2-key-mapping') or {}
            region_key = "%s#%s" % (region, default_keyname)
            keyfile = keymap.get(region_key)
            if not keyfile:
                errstr = "default key %s exists in user_data mapping but the file cannot be found" % default_keyname
                logger.error("%s%s%s" % (colorama.Fore.RED, errstr, colorama.Style.RESET_ALL))

            return default_keyname, keyfile

        except Exception as ex:
            logger.exception(ex)
            logger.error('Error getting default keys: %s' % ex)


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

            print(colorama.Fore.GREEN)
            print("   ", " ".join(header_fmt) % tuple(header_data))
            print(colorama.Style.RESET_ALL)

            prev_cluster_name = "_"
            prev_vpc = "_"
            for node in nodes:
                
                node_vpc = node.get('vpc')
                if node_vpc and node_vpc != prev_vpc:
                    print("")
                    print("%s--%s:%s" % (colorama.Fore.GREEN, node_vpc, colorama.Style.RESET_ALL))
                    prev_vpc = node_vpc

                if node.cluster != prev_cluster_name:
                    if node.cluster:
                        if True:
                            print( "%scluster [%s]" % (colorama.Style.RESET_ALL, node.cluster))
                        else:
                            print( "%s%s" % (colorama.Style.RESET_ALL, node.cluster))
                        prev_cluster_name = node.cluster or cluster_filter
                    else:
                        print (colorama.Style.RESET_ALL)
                        print( "unassigned:" )
                        prev_cluster_name = None

                print(
                    colorama.Style.NORMAL,
                     colorama.Fore.CYAN, 
                     " ", 
                     " ".join(header_fmt) % tuple(node.disp_data()))
                ext_data = []
                if extended == 1:
                    ext_data = node.extended_data().items()
                elif extended == 2:
                    ext_data = node.all_data().items()

                if ext_data:
                    for (k,v) in sorted(ext_data, key=lambda x:x[0]):
                        print(colorama.Style.RESET_ALL, colorama.Style.DIM, header_fmt[1] % "", k, ":", v)
                    print(colorama.Style.RESET_ALL)

        finally:
            print(colorama.Style.RESET_ALL)


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

            regex = fnmatch.translate(filterval.lower())
            valid = re.compile(regex)

            for node in nodes:
                val =  node.get(filterkey)
                if not val:
                    continue
                logger.debug("trying filter %s on %s..." % (filterval, val))
                if not valid.match(str(val).lower()):
                    continue
                filtered.append(node)

        return filtered

    def _search(self, nodes, search_term):
        '''
        filter a list of nodes by search term
        e.g. "running"
        '''

        results = set()
        search_term = search_term.lower()

        for node in nodes:
            for val in node.get('tags').values():
                if search_term in val.lower():
                    results.add(node)
                    break

            for key in node.extended_fields + node.all_fields:
                if search_term in str(node.get(key)).lower():
                    results.add(node)
                    break

        return list(results)

    def _find_matching_nodes(self, selector, cluster_nodes):
        ''' using node_props.selector, find the matching node in cluster_nodes ''' 

        if selector == '*':
            return cluster_nodes

        if '=' not in selector:
            logger.error("Invalid login selector %s" % selector)
            return []

        filterkey, filterval = selector.split("=")

        #logger.debug("matching template node filters [%s=%s]to cluster nodes" % (filterkey, filterval))
        matching_nodes = self._filter(cluster_nodes, filterkey, filterval)

        return matching_nodes

    def _get_nodes_with_login_data(self):
        ''' get all nodes matched to login rules '''

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

        self._match_nodes_to_login_rules(nodes)
        ret_nodes = sorted(nodes, key =lambda x: (x.cluster or '', x.get('vpc') or ''))
        for i in range( len(ret_nodes) ):
            ret_nodes[i].index = str(i + 1)
        return ret_nodes

    def _match_nodes_to_login_rules(self, nodes):

        for rule in self.config.get_login_rules():
            selector = rule.get('selector')
            matched_nodes = self._find_matching_nodes(selector, nodes)
            for node in matched_nodes:
                if not node.login_rule:         # to maintain rule precedence, dont rematch
                    node.login_rule = rule
                    node.cluster = rule.get('member-of')

    def resolve_target_nodes(self, search=False, target_node_name=""):
        '''
            given a target string, filter nodes from cloud provider and create a list of target nodes to operate on
            filter by all clusters
        '''
        if not self.cloud:
            raise Exception('Internal error: No cloud provider loaded.')

        cluster_nodes = self._get_nodes_with_login_data()

        # working set
        if self.cur_cluster:
            cluster_nodes = list(filter(lambda x: (x.login_rule.get('member-of') == self.cur_cluster), cluster_nodes))

        if not cluster_nodes:
            return []

        # filter by target string
        # target string can be a comma separated list of filter expressions

        if target_node_name == '*' or not target_node_name:
            return cluster_nodes

        filtered_nodes = set()
        for filter_exp in target_node_name.split(","):
            if '=' in filter_exp:
                parts = filter_exp.split("=")
                if len(parts) != 2:
                    str_err = "Filter format error. Should be key=value for node properties or tags=key:value for tags. Use quotes if needed."
                    raise Exception("%s%s%s" %(colorama.Fore.RED, str_err, colorama.Style.RESET_ALL))
                filterkey, filterval  = parts
            elif filter_exp in self.clusters:
                filterkey, filterval = 'cluster', filter_exp    
            else:
                filterkey, filterval = 'name', filter_exp
                if self.is_numeric(filter_exp):
                    filterkey = 'index'

            if filterkey and filterval:
                target_nodes  = list(self._filter(cluster_nodes, filterkey, filterval))
                filtered_nodes.update(target_nodes)

        if search and not filtered_nodes:
            for search_term in target_node_name.split(","):
                filtered_nodes.update( self._search(cluster_nodes, search_term))

        if not filtered_nodes:
            logger.info( "no nodes found that match filter %s" % (target_node_name) )
        else:
            logger.debug( "resolved target string [%s] to %s nodes" % (target_node_name, len(filtered_nodes)) )

        return sorted( list(filtered_nodes), key=lambda x: x.index )


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

    def is_numeric(self, s):
        try:
            int(s)
            return True
        except ValueError:
            return False
