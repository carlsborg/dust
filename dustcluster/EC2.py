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
import boto3
from botocore.exceptions import ClientError
import socket
import datetime
import colorama
import time
import stat

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

        self._ec2client = None

        # cluster name
        self.name   = name
        self.key    = key
        self.region = region
        self.image  = image
        self.username = username
        self.keyfile = keyfile
        self.creds_map = creds_map

        self.ami_ids = {}

    def connect(self):  

        if not self.region:
            raise Exception('No region specified. Will not connect.')

        conn = boto3.resource('ec2', region_name = self.region, 
                              aws_access_key_id=self.creds_map['aws_access_key_id'], 
                              aws_secret_access_key=self.creds_map['aws_secret_access_key'])

        if not conn:
            raise Exception("Could not connect to region [%s]" % self.region)

        return conn

    def conn(self):

        if not self._connection:
            self._connection = self.connect()   

        return self._connection 

    def client(self):
        resource = self.conn()
        return resource.meta.client

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
        instances = self.conn().instances.all()
        return instances

    def create_absent_node(self, nodename, **kwargs):
        node = EC2Node(nodename=nodename, **kwargs)
        node.cloud = self
        return node

    def create_keypair(self, keyname, keydir):
        '''  create a keypair and save it keydir/keyname.pem '''

        if not os.path.exists(keydir):
            os.makedirs(keydir)

        keypath = os.path.join(keydir, "%s.pem" % keyname)
        if os.path.exists(keypath):
            logger.info('Found key pair locally, not doing anything. key=[%s] keypath=[%s]' % (keyname, keypath))
            return True, keyname, keypath

        # check is the keys exists in the cloud
        found = True
        try:
            ret = self.client().describe_key_pairs(KeyNames=[keyname])
        except ClientError as ex:
            if (ex.response['Error']['Code'] == 'InvalidKeyPair.NotFound'):
                found = False
            else:
                raise

        if found:
            return True, keyname, ""

        # create it
        keypair = self.conn().create_key_pair(KeyName=keyname)
        self.writekey(keypath, keypair.key_name, keypair.key_material, keypair.key_fingerprint)

        return False, keyname, keypath

    def writekey(self, keypath, keyname, keymaterial, fingerprint):

        # write creds
        logger.info("Writing new keypair [%s] to [%s] with mode (0600)" % (keyname, keypath))

        with open(keypath, 'wb') as fh:
            fh.write(keymaterial)

        os.chmod(keypath, stat.S_IRUSR | stat.S_IWUSR)

    def get_dust_ami_for_region(self, region):
        ''' latest public Amazon Linux AMI '''

        cached = self.ami_ids.get(region)
        if cached:
            return cached, 'ec2-user'

        ami_name = 'amzn-ami-hvm-2017.09.0.20170930-x86_64-gp2'

        filters = [
                        { 'Name': 'name' , 'Values' : [ami_name] } 
                ]

        try:
            images = list(self.conn().images.filter(ExecutableUsers=['all'], Owners=['137112412989'], Filters=filters))
        except boto.exception.ClientErro as ex:
            logger.error("Could not find ami %s in region %s" % (region, ami_name))

        for image in images:
            logger.info("Using default AMI: %s" % ami_name)
            self.ami_ids[region] = image.id 
            return image.id, 'ec2-user'

        return None



class EC2Node(object):
    '''
    describe and control EC2 nodes within an EC2 cloud
    '''

    def __init__(self, key="", keyfile="", nodename="", instance_type="", image="",  username='', vm=None, cloud=None):

        self._key = key
        self._keyfile    = keyfile
        self._name      = nodename
        self._instance_type = instance_type
        self._image     = image
        self._username = username
        self._vm        = None
        self.cloud      = cloud

        self._hydrated = False

        self.login_rule = {}
        self.index = None

        # for starting new nodes
        self._clustername = None

        self.friendly_names = { 
                                'image'    : 'image_id', 
                                'dns_name' : 'public_dns_name', 
                                'type'     : 'instance_type',
                                'key'      : 'key_name',
                                'vpc'      : 'vpc_id',
                                'ip'       : 'ip_address'
                               }

        self.extended_fields = [ 'dns_name', 'image', 'tags', 'key', 'launch_time', 
                                'username', 'groups', 'state', 'login']

        self.all_fields = ['ami_launch_index', 'architecture', 'block_device_mappings', 'classic_address',
                     'client_token', 'console_output', 'ebs_optimized', 'elastic_gpu_associations', 
                     'ena_support', 'hypervisor', 'iam_instance_profile', 'id', 'image', 'image_id',
                      'instance_id', 'instance_lifecycle', 'instance_type', 'kernel_id', 'launch_time', 
                      'monitoring', 'network_interfaces', 'placement', 'placement_group', 'platform', 
                      'private_dns_name', 'private_ip_address', 'product_codes', 'public_dns_name', 'public_ip_address', 
                      'ramdisk_id', 'root_device_name', 'security_groups', 'sriov_net_support', 'state', 'state_reason',
                       'state_transition_reason', 'subnet', 'subnet_id', 'tags', 'virtualization_type', 'volumes', 
                       'vpc', 'vpc_addresses', 'vpc_id']

        self.non_instance_fields = ['name', 'username', 'cluster', 'keyfile', 'key', 'tags', 'groups', 'state', 'index', 'login']

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
    def name(self):
        return self.tags.get('Name') or self.tags.get('name') or ""


    @property
    def cluster(self):
        return self._clustername

    @cluster.setter
    def cluster(self, value):
        self._clustername = value

    @property
    def username(self):
        return self._username

    @username.setter
    def username(self, value):
        self._username = value

    @property
    def keyfile(self):
        return self._keyfile
        
    @keyfile.setter
    def keyfile(self, value):
        self._keyfile = value

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
    def tags(self):
        if self._vm and self._vm.tags:
            ret = {}
            for tagitem in self._vm.tags:
                ret[ tagitem.get('Key') ] = tagitem.get('Value')
            return ret
        else:
            return {}

    @property
    def state(self):
        if self._vm:
            return self._vm.state.get('Name')
        else:
            return '-'

    @property
    def groups(self):
        if self._vm:
            return [ "(name=%s id=%s) " % ( grp.get('GroupName'),grp.get('GroupId') ) for grp in self._vm.security_groups ] 
        return []

    @property
    def login(self):
        if self.login_rule:
            return "%s %s" % ( self.login_rule.get('login-user'), self.login_rule.get('keyfile') )
        return "(not configured)"

    def start(self):

        #if not self.cluster.get_keyfile_for_key(self.key):
        #    raise Exception("No key specified, not starting nodes.")

        vm = self._vm
        if vm:
            if self.state == 'running' or self.state == 'pending':
                logger.info( "Nothing to do for node [%s]" % self._name )
                return

            if self.state == 'stopped':
                logger.info( 'restarting node %s : %s' % (self._name, self) )
                self.vm.start()
                return

        logger.info( 'creating instance name=[%s] image=[%s] instance=[%s]'
                        % (self._name, self._image, self._instance_type) )

        res = self.cloud.conn().run_instances(self._image, key_name=self._key, instance_type=self._instance_type)

    def stop(self):

        vm = self._vm
        if vm:
            if self.state == 'stopped':
                return 
            else:
                logger.info('stopping %s' % self._name)
                vm.stop()
        else:
            logger.error('no vm that matches node defination for %s' %  self._name)

    def terminate(self):

        if self._vm:
            tags = self.tags
            newname = ''
            if tags and tags.get('Name'):
                newname = tags['Name'] + '_terminated'
                self._vm.create_tags( Tags= [ { 'Key': 'Name', 'Value' : newname } ] )

            instance_ids = [self._vm.id]

            logger.info('terminating %s id=[%s]' % (self._name, self._vm.id))

            self._vm.stop()
            self._vm.terminate()

    def disp_headers(self):
        headers = ["@",    "Name", "Type", "State", "ID",  "IP", "int_IP"]
        fmt =     ["%-3s"  "%-15s",  "%-12s",  "%-12s",  "%-19s", "%-15s", "%-15s"]
        return headers, fmt


    def disp_data(self):

        name = self.name
        if len(name) > 14:
            name = name[:6] + ".." + name[-6:]

        vals = [self.index, name, self._instance_type]

        if self._vm:
            vm = self._vm
            vmdata = [self.state, vm.id, vm.public_ip_address, vm.private_ip_address]
            vals += vmdata
        else:
            startColorRed = "\033[0;31;40m"
            endColor      = "\033[0m"
            vals += ['%sabsent%s' % (startColorRed, endColor), '', '', '']

        return vals


    def get(self, prop_name):
        ''' return property from the underlying instance '''

        if prop_name in self.non_instance_fields:
            val = getattr(self, prop_name)
            return val

        if prop_name in self.friendly_names:
            prop_name = self.friendly_names[prop_name]

        if not self._vm:
            return ""

        return getattr(self._vm, prop_name)

    def extended_data(self):
        # updated here for showex command error
        ret = {}

        for field in self.extended_fields:
            val = self.get(field)

            if field == 'tags' and self._vm:
                sep = " , "
                val = sep.join( '%s%s%s=%s' % (colorama.Style.RESET_ALL, k, colorama.Style.DIM, v) \
                                    for k,v in self.tags.items())

            if val:
                ret[field] = val

        return ret


    def all_data(self):
        # updated here for showex command error
        ret = {}

        for field in self.all_fields:

            if field.startswith("_"):
                continue

            val = self.get(field)

            if val:
                ret[field] = val

        ret.update ( self.extended_data() )

        return ret


### helpers

class EC2Config(object):

    @staticmethod
    def http_ping(endpoint):

        req = '''GET / HTTP/1.1\nUser-Agent: DustCluster\nHost: %s\nAccept: */*\n\n'''

        try:
            t1 = time.time() * 1000
            sendsock = socket.create_connection((endpoint, 80))
            smsg = req % endpoint
            sendsock.settimeout(2)
            sendsock.sendall(smsg)
            rbuf = " "
            while rbuf[-1] != '\n':
                rbuf = sendsock.recv(256)
            sendsock.close()
            t2 = time.time() * 1000
        except socket.timeout:
            return -1

        except Exception as ex:
            print("%s" % (endpoint, ex))
            return -1

        return int(t2 - t1)

    @staticmethod
    def find_closest_region(logger, aws_access_key_id, aws_secret_access_key):

        client = boto3.client('ec2', region_name='us-east-1', aws_access_key_id=aws_access_key_id,
                                                aws_secret_access_key=aws_secret_access_key)

        regions = client.describe_regions()

        connect_times = []
        for regioninfo in regions.get('Regions'):
            ms = EC2Config.http_ping(regioninfo.get('Endpoint'))
            sms = "[timeout/erorr]" if ms == -1 else str(ms)
            logger.info("http ping time to %s (%s) : %s ms" % (regioninfo['Endpoint'], regioninfo['RegionName'], sms))
            connect_times.append((regioninfo['RegionName'], ms))

        connect_times = sorted(connect_times, key=lambda x: x[1])

        logger.info("%sClosest AWS endpoints to you appears to be [%s] with connect time %sms %s" % ( colorama.Fore.GREEN, 
                            connect_times[0][0], connect_times[0][1], colorama.Style.RESET_ALL ))

        return connect_times[0][0]

    @staticmethod
    def check_credentials(region, aws_access_key_id, aws_secret_access_key, logger):

        try:
            client = boto3.client('ec2', region_name=region, aws_access_key_id=aws_access_key_id,
                                                aws_secret_access_key=aws_secret_access_key)

            if not client:
                return None
            
            client.describe_regions()
        except Exception as e:
            logger.exception(e)
            return None

        return client

    @staticmethod
    def setup_credentials(override_creds):

        user_data = {}
        credentials   = {}

        good_creds = False

        while not good_creds:

            if override_creds:
                acc_key_id = override_creds.get('aws_access_key_id')
                acc_key = override_creds.get('aws_secret_access_key')
                override_creds = None   # for retry
            else:
                acc_key_id  = input("Enter aws_access_key_id:").strip()
                acc_key     = input("Enter aws_secret_access_key:").strip()

            confirmed = False
            while not confirmed:
                region      = input("Enter default region [Enter to find closest region]:")
                if region.strip():
                    break
                else:
                    logger.info("Finding nearest AWS region endpoint...")
                    region = EC2Config.find_closest_region(logger, acc_key_id, acc_key)
                    confirm = input("Accept %s?[y]" % region) or "y"
                    if confirm[0].lower() == "y":
                        user_data['closest_region'] = region
                        break

            # test creds
            ret = EC2Config.check_credentials(region, acc_key_id, acc_key, logger)

            if ret:
                good_creds = True
                logger.info("%sCredentials verified.%s" % 
                                (colorama.Fore.GREEN, colorama.Style.RESET_ALL))
            else:
                logger.error("%sCould not connect to region [%s] with these credentials, please try again%s" % 
                                (colorama.Fore.RED, region, colorama.Style.RESET_ALL))

        credentials["aws_access_key_id"] = acc_key_id
        credentials["aws_secret_access_key"] = acc_key

        user_data["region"] = region
        user_data["closest_region"] = region

        return credentials, user_data

    @staticmethod
    def validate(credentials, user_data):

        required = ["aws_access_key_id", "aws_secret_access_key"]
        for s in required:
            if s not in credentials.keys():
                logger.error("Credentials data [%s] is missing [%s] key" % (str(credentials.keys()), s))
                raise Exception("Bad config.")

        required = ["region"]
        for s in required:
            if s not in user_data.keys():
                logger.error("User data [%s] is missing [%s] key" % (str(user_data.keys()), s))
                raise Exception("Bad config.")
