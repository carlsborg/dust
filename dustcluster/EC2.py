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

''' EC2 cluster and node objects '''
import logging
import os, sys
from copy import deepcopy, copy
import boto, boto.ec2

from dustcluster.util import setup_logger
logger = setup_logger( __name__ )


class EC2Cloud(object):
    '''
    provides a connection to EC2 and generates a list of Node objects 
    '''

    def __init__(self, name='', key='', region="", image="", username="", keyfile="", creds_map={}):

        if not region:
            region = 'eu-west-1'

        self._connection = None
        # cluster name
        self.name   = name
        self.key    = key
        self.region = region
        self.image  = image
        self.username = username
        self.keyfile = keyfile
        self.creds_map = creds_map


    def connect(self):

        if not self.region:
            raise Exception('No region specified. Will not connect.')
  
        conn = boto.ec2.connect_to_region(self.region,
                                            aws_access_key_id=self.creds_map['aws_access_key_id'], 
                                            aws_secret_access_key=self.creds_map['aws_secret_access_key'], 
                                            )

        logger.debug('Connected, boto version: %s' % conn.APIVersion)
        return conn

    def conn(self):

        if not self._connection:
            self._connection=self.connect()

        return self._connection

    def get_cluster_description(self):

        if self.name: 
            return "cluster '%s' in %s, using key: %s" % (self.name, self.region, self.key)
        else:
            return "no cluster defined. using defaults region %s and key %s" % (self.region, self.key)

    def refresh(self):
        ''' get nodes/reservations from cloud '''

        logger.debug('hydrating from all cloud nodes')

        vms = self._get_instances()

        all_nodes = []
        for vm in vms:
            node = EC2Node(username=self.username, cloud=self)
            node.hydrate(vm)
            all_nodes.append(node)
        return all_nodes

    def _get_instances(self, iids=None):
        ret = []
        reservations = self.conn().get_all_reservations(instance_ids=iids)
        for r in reservations:
            for i in r.instances:
                ret.append(i)
        return ret

    def create_absent_node(self, nodename, **kwargs):
        node = EC2Node(nodename=nodename, **kwargs)
        node.cloud = self
        return node

    def create_keypair(self, keyname, keydir):
        '''  create a keypair and save it keydir/keyname.pem '''

        os.makedirs(keydir)

        keypath = os.path.join(keydir, "%s.pem" % keyname)
        if os.path.exists(keypath):
            logger.info('Found key pair locally, not doing anything. key=[%s] keypath=[%s]' % (keyname, keypath))
            return keyname, keypath 

        # check is the keys exists in the cloud
        keypairs = self.conn().get_all_key_pairs()
        for keypair in keypairs:
            if keypair.name == keyname:
                errstr = "They key %s has exists on this account already." % keyname
                logger.info('Cloud keys : %s' % str(keypairs)) 
                raise Exception(errstr)

        # create it
        key = self.conn().create_key_pair(keyname)
        if key:
            key.save(keydir)
        else:
            raise Exception('Error creating key')

        return keyname, keypath


class EC2Node(object):
    '''
    describe and control EC2 nodes within an EC2 cloud
    '''

    def __init__(self, key="", keyfile="", nodename="", instance_type="", image="",  username='', vm=None, cloud=None):

        self._hydrated = False

        self._name      = nodename
        self._image     = image
        self._instance_type = instance_type
        self._vm        = None
        self._keyfile    = keyfile

        # for starting new nodes
        self._clustername = None
        self._key = key

        self._username = username
        self.is_template_node = False
        self.cloud = cloud or None
        self.context = {}
        self._secgroups = []

    def __repr__(self):
        data = self.disp_data()
        return ",".join(str(datum) for datum in data)

    def hydrate(self, vm):
        ''' populate template node state from the cloud reservation ''' 
        self._name      = ""
        self._image     = vm.image_id
        self._instance_type     = vm.instance_type
        self._vm = vm
        self._hydrated = True

    def unhydrate(self, vm):
        ''' populate template node state from the cloud reservation ''' 
        self._vm = None
        self._hydrated = False

    @property
    def hydrated(self):
        return self._hydrated

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
    def clustername(self):
        if self.hydrated:
            return self._vm.tags.get('cluster')
        else:
            return self._clustername

    @clustername.setter
    def clustername(self, value):
        self._clustername = value

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
    def tags(self):
        return self._vm.tags if self._vm else {}

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
    def key(self):
        if self._vm:
            return self._vm.key_name
        else:
            return self._key

    @key.setter
    def key(self, value):
        self._key = value

    @property
    def keyfile(self):
        return self._keyfile
        
    @keyfile.setter
    def keyfile(self, value):
        self._keyfile = value

    def assign_vm(self, vm):
        self._vm  = vm

    def add_handler(self, event, handler):
        pass

    def start(self):

        #if not self.cluster.get_keyfile_for_key(self.key):
        #    raise Exception("No key specified, not starting nodes.")

        vm = self._vm
        if vm:
            if vm.state == 'running' or vm.state == 'pending':
                logger.info( "Nothing to do for node [%s]" % self._name )
                return

            if vm.state == 'stopped':
                logger.info( 'restarting node %s : %s' % (self._name, self) )
                self.cloud.conn().start_instances(instance_ids=[vm.id])
                return

        logger.info( 'launching new node name=[%s] image=[%s] instance=[%s]'
                        % (self._name, self._image, self._instance_type) )

        res = self.cloud.conn().run_instances(self._image, key_name=self._key, instance_type=self._instance_type)
        for inst in res.instances:
            inst.add_tag('name', self._name)
            inst.add_tag('cluster', self._clustername)

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

            logger.info('terminating %s id=[%s]' % (self._name, self._vm.id))

            self.cloud.conn().stop_instances( instance_ids = instance_ids )
            self.cloud.conn().terminate_instances( instance_ids = instance_ids )

    def disp_headers(self):
        headers = ["Name", "Instance", "State", "ID",  "ext_IP", "int_IP"]
        fmt =     ["%-12s",  "%-12s",  "%-12s",  "%-10s", "%-15s", "%-15s"]
        return headers, fmt

    def disp_data(self):

        vals = [self._name, self._instance_type]

        if self._vm:
            vm = self._vm
            vmdata = [vm.state, vm.id, vm.ip_address, vm.private_ip_address]
            vals += vmdata
        else:
            vals += ['not_started', '', '', '']

        return vals

    def extended_data(self):
        # updated here for showex command error
        ret = {}

        if self.hostname:
            ret['hostname'] = self.hostname

        if self.image:
            ret['image'] = self.image

        if self.vm:

            if self._vm.public_dns_name:
                ret['DNS'] = self._vm.public_dns_name

            if self._vm.tags:
                ret['tags'] = ",".join( '%s=%s' % (k,v) for k,v in self._vm.tags.items())

            if self._vm.key_name:
                ret['key'] = self._vm.key_name

        return ret

