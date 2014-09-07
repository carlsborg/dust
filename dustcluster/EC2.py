''' EC2 cloud and node objects '''
import sys
import boto, boto.ec2

from dustcluster.util import setup_logger
logger = setup_logger( __name__ )


class EC2Session(object):
    '''global cloud session - used by cloud, node and orphaned node objects'''

    _connection     = None

    def __init__(self):
        raise Exception("static invocation only")

    @staticmethod
    def connect(region, verbose):
        if verbose:
            boto.set_stream_logger('boto')
        EC2Session._connection = boto.ec2.connect_to_region(region)
        logger.debug( 'boto version: %s' % EC2Session._connection.APIVersion )

    @staticmethod
    def conn():
        return EC2Session._connection

class EC2Cloud(object):
    '''
    describe and control EC2 clouds
    '''

    def __init__(self, name, key, region="", image="", username="", keyfile=""):

        if not region:
            region = 'eu-west-1'

        EC2Session.connect(region, verbose=False)

        if not key:
            raise Exception("Cannot create a cloud without a key")

        self.name   = name
        self.key    = key
        self.region = region
        self.image  = image
        self.username = username
        self.keyfile = keyfile

        self.template_nodes = {}

    def conn(self):
        return EC2Session.conn()

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
                tmpnode = EC2Node(vm=vm, username=self.username)
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

        headers = nodes[0].disp_headers() if nodes else nonmember_nodes[0].disp_headers()
        headerfmt =  "%12s " * len(headers)
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
        reservations = EC2Session.conn().get_all_reservations(instance_ids=iids)
        for r in reservations:
            for i in r.instances:
                ret.append(i)
        return ret

    def show(self, nodes=None):
        self.show_cloud()
        self.show_nodes(nodes)

    def get_template_nodes(self):
        return self.template_nodes

class EC2Node(object):
    '''
    describe and control EC2 nodes within an EC2 cloud
    '''

    def __init__(self, name="", instance_type="", image="",  username='', vm=None):

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

        self._username = username
        self.is_template_node = False
        self.cloud = None
        self.context = {}

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
    
    def assign_vm(self, vm):
        self._vm  = vm

    def add_handler(self, event, handler):
        pass

    def start(self):

        vm = self._vm
        if vm:
            if vm.state == 'running' or vm.state == 'pending':
                logger.info( "Nothing to do for node {%s}" % self._name )
                return

            if vm.state == 'stopped':
                logger.info( 'restarting node %s : %s' % (self._name, self) )
                EC2Session.conn().start_instances(instance_ids=[vm.id])
                return

        logger.info( 'starting node %s-%s' % (self._name, self) )
        res = EC2Session.conn().run_instances(self._image, key_name=self.cloud.key, instance_type=self._instance_type)
        for inst in res.instances:
            inst.add_tag('name', self._name)

    def stop(self):

        vm = self._vm
        if vm:
            if vm.state == 'stopped':
                return 
            else:
                logger.info('stopping %s' % self._name)
                EC2Session.conn().stop_instances(instance_ids = [vm.id])
        else:
            logger.error('no vm that matches node defination for %s' %  self._name)

    def terminate(self):

        tags = self._vm.tags
        newname = ''
        if tags and tags.get('name'):
            newname = tags['name'] + '_terminated'
            self._vm.add_tag('name', newname)

        instance_ids = [self._vm.id]

        EC2Session.conn().stop_instances( instance_ids = instance_ids )
        EC2Session.conn().terminate_instances( instance_ids = instance_ids )

    def disp_headers(self):
        headers = ["Name", "Instance", "Image", "State", "ID", "IP", "DNS", "tags"]
        return headers

    def disp_data(self):

        vals = [self._name, self._instance_type, self._image]

        if self._vm:
            vm = self._vm
            vmdata = [vm.state, vm.id, vm.ip_address, vm.public_dns_name, vm.tags]
            vals += vmdata
        else:
            vals += ['not_started', '', '', '', '']

        return vals

