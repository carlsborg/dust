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

''' EC2 cloud and node objects '''
import os, sys
from copy import deepcopy, copy
import boto, boto.ec2

from dustcluster.util import setup_logger
logger = setup_logger( __name__ )


class EC2Cloud(object):
    '''
    describe and control EC2 clouds
    '''

    def __init__(self, name, key='', region="", image="", username="", keyfile="", profile=None):

        if not region:
            region = 'eu-west-1'

        self._connection = None
        self.name   = name
        self.key    = key
        self.region = region
        self.image  = image
        self.username = username
        self.keyfile = keyfile
        self.profile = profile

        self.template_nodes = {}

    def connect(self):

        if not self.region:
            raise Exception('No region specified. Will not connect.')

        conn = boto.ec2.connect_to_region(self.region, profile_name=self.profile)

        logger.debug('Connected, boto version: %s' % conn.APIVersion)
        return conn

    def conn(self):

        if not self._connection:
            self._connection=self.connect()

        return self._connection

    def set_verbosity(self,level):
        if level == 'debug':
            boto.set_stream_logger('boto')
        else:
            boto.set_stream_logger(None)

    def add_node(self, node):

        if node.name in self.get_template_nodes():
            raise Exception("node with name %s already exists" % node.name)

        if not node.image:
             node.image = self.image
            
        if not node.username:
            node.username = self.username

        node.cloud = self
        node.is_template_node = True

        self.template_nodes[node.name] = node

    def show_cloud(self):
        logger.info( "cluster '%s' in %s, using key: %s" % (self.name, self.region, self.key))

    def _node_for_vm(self, vm, nodes):

        if not vm.tags:
            return None

        vmname = vm.tags.get(u'name')
        if not vmname:
            return None

        matches = []
        for name, node in nodes.iteritems():
            if name == vmname and vm.instance_type == node.instance_type and vm.image_id == node.image:
                return node

        return None

    def retrieve_node_state(self, verbose=False):
        ''' populate template nodes with state from the cloud reservations '''

        nonmember_nodes = []

        vms = self._get_instances()
        nodes = self.get_template_nodes()

        # reset state
        for node in nodes.values():
            node.vm = None

        if verbose:
            logger.debug( '%d cloud vms,  %s template nodes' % (len(vms), len(nodes)) )

        for vm in vms:
            node = self._node_for_vm(vm, nodes)
            if not node or node.vm:
                tmpnode = EC2Node(vm=vm, username=self.username, cloud=self)
                tmpnode.is_template_node = False
                nonmember_nodes.append(tmpnode)
                continue

            if node.vm:
                logger.error('ERROR: multiple cloud reservations found for template node %s.' % node.name)
                continue

            # update state
            node.vm = vm

        return nodes.values(), nonmember_nodes

    def show_nodes(self, input_nodes=None):

        if input_nodes:
            nodes = [node for node in input_nodes if node.is_template_node == True]
            nonmember_nodes = [node for node in input_nodes if node.is_template_node == False]
        else:
            nodes, nonmember_nodes = self.retrieve_node_state(verbose=True)

        if not nodes and not nonmember_nodes:
            logger.info( 'no template nodes defined, and no cloud nodes found' )
            return

        headers, headerfmt = nodes[0].disp_headers() if nodes else nonmember_nodes[0].disp_headers()
        print headerfmt % tuple(headers)

        if nodes:
            print "Template Nodes:"
            for node in nodes:
                print headerfmt % tuple(node.disp_data())

        if nonmember_nodes:
            print "Non-template nodes:"
            for vm in nonmember_nodes:
                print headerfmt % tuple(vm.disp_data())


    def get_known_vms(self, machines):

        knownvms   = {}
        for vm in machines:
            unknownvms = []
            known = False
            nodename = ""
            if vm.tags:
                nodename   = vm.tags.get(u'name')
                nodeconfig = self.nodes.get(nodename)
                if nodename and nodeconfig and \
                    vm.instance_type == nodeconfig.instance and \
                    vm.image_id == nodeconfig.image:
                    known = True

            if known:
                knownvms[nodename] = vm
            else:                   
                unknownvms.append(vm)
                continue

        return knownvms, unknownvms

    def _get_instances(self, iids=None):
        ret = []
        reservations = self.conn().get_all_reservations(instance_ids=iids)
        for r in reservations:
            for i in r.instances:
                ret.append(i)
        return ret

    def show(self, nodes=None):
        self.show_cloud()
        self.show_nodes(nodes)

    def get_template_nodes(self):
        return self.template_nodes

    def load_default_keys(self, keypath):
        ''' load the default keypair if it exists
            else create a default keypair and save it to keypath '''

        default_keypair = 'ec2dust'

        # try keys/dust.key
        default_keyfile = os.path.join(keypath, '%s.pem' % default_keypair)
        if os.path.exists(default_keyfile):
            logger.info('Found default key pair locally, key=%s keypath=%s' % (default_keypair,default_keyfile))
            self.key = default_keypair
            self.keyfile = default_keyfile
            return

        # check existing keys in the cloud 
        keypairs = self.conn().get_all_key_pairs()
        if default_keypair in keypairs:
            logger.info('Found default key pair in cloud, downloading \
                            key=%s keypath=%s' % (default_keypair,default_keyfile))
            kp = keypairs[0]
            ret = key.save(keypath)
        else:
            # create it
            logger.info('Creating default key pair key=%s keypath=%s' % (default_keypair,default_keyfile))
            key = self.conn().create_key_pair(default_keypair)
            if key:
                key.save(keypath)
            else:
                raise Exception('Error creating key')

        self.key = default_keypair
        self.keyfile = default_keyfile

class EC2Node(object):
    '''
    describe and control EC2 nodes within an EC2 cloud
    '''

    def __init__(self, name="", instance_type="", image="",  username='', vm=None, cloud=None, security_groups=''):

        if vm:
            self._name      = vm.tags.get('name') or ""
            self._image     = vm.image_id
            self._instance_type     = vm.instance_type
            self._vm = vm
        else:
            self._name      = name
            self._image     = image
            self._instance_type = instance_type
            self._vm        = None

        self.security_groups = [sg.strip() for sg in security_groups.split(',')]
        self._username = username
        self.is_template_node = False
        self.cloud = cloud or None
        self.context = {}
        self._secgroups = []

    def __repr__(self):
        data = self.disp_data()
        return ",".join(str(datum) for datum in data)

    @property
    def vm(self):
        return self._vm

    @vm.setter
    def vm(self, value):
        self._vm = value

    @property
    def image(self):
        return self._image

    @image.setter
    def image(self, value):
        self._image = value

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value

    @property
    def instance_type(self):
        return self._instance_type

    @instance_type.setter
    def instance_type(self, value):
        self._instance_type = value

    @property
    def state(self):
        return self._vm.state if self._vm else ""

    @property
    def id(self):
        return self._vm.id if self._vm else ""
    
    @property
    def hostname(self):
        if self._vm:
            return self._vm.public_dns_name 
        return '-' 

    @property
    def username(self):
        return self._username

    @username.setter
    def username(self, value):
        self._username = value

    @property
    def security_groups(self):
        return self._secgroups

    @security_groups.setter
    def security_groups(self, value):
        self._secgroups = value

    def assign_vm(self, vm):
        self._vm  = vm

    def add_handler(self, event, handler):
        pass

    def start(self):

        if not self.cloud.key:
            raise Exception("No key specified, not starting nodes.")

        vm = self._vm
        if vm:
            if vm.state == 'running' or vm.state == 'pending':
                logger.info( "Nothing to do for node {%s}" % self._name )
                return

            if vm.state == 'stopped':
                logger.info( 'restarting node %s : %s' % (self._name, self) )
                self.cloud.conn().start_instances(instance_ids=[vm.id])
                return

        logger.info( 'starting node %s-%s' % (self._name, self) )

        logger.debug( 'image=%s keypair=%s instance=%s' % (self._image, self.cloud.key, self._instance_type) )

        res = self.cloud.conn().run_instances(self._image, key_name=self.cloud.key, instance_type=self._instance_type)
        for inst in res.instances:
            inst.add_tag('name', self._name)

    def stop(self):

        vm = self._vm
        if vm:
            if vm.state == 'stopped':
                return 
            else:
                logger.info('stopping %s' % self._name)
                self.cloud.conn().stop_instances(instance_ids = [vm.id])
        else:
            logger.error('no vm that matches node defination for %s' %  self._name)

    def terminate(self):

        if self._vm:
            tags = self._vm.tags
            newname = ''
            if tags and tags.get('name'):
                newname = tags['name'] + '_terminated'
                self._vm.add_tag('name', newname)

            instance_ids = [self._vm.id]

            self.cloud.conn().stop_instances( instance_ids = instance_ids )
            self.cloud.conn().terminate_instances( instance_ids = instance_ids )

    def disp_headers(self):
        headers = ["Name", "Instance", "State", "ID",  "ext_IP", "int_IP", "DNS"]
        fmt =     "%-12s %-12s %-12s %-10s %-15s %-15s %s"
        return headers, fmt

    def disp_data(self):

        vals = [self._name, self._instance_type]

        if self._vm:
            vm = self._vm
            vmdata = [vm.state, vm.id, vm.ip_address, vm.private_ip_address, vm.public_dns_name]
            vals += vmdata
        else:
            vals += ['not_started', '', '', '', '']

        return vals

