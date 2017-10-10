
import yaml
import dustcluster
from dustcluster.console import Console
from dustcluster.cluster import ClusterCommandEngine

import unittest
import mock
import boto

'''
functional tests - mock cloud provider data and invoke commands
'''

## mocks

class MockCommandEngine(ClusterCommandEngine):
    ''' mock command engine, null out some methods '''

    def read_all_clusters(*args, **kwargs):
        pass

    def update_user_data(*args, **kwargs):
        pass

class MockInstance():

    def __init__(self):
        self.stop_count = 0
        self.terminate_count = 0 

    def stop():
        self.stop_count += 1

    def terminate():
        self.terminate_count +=1


class MockBotoEC2Connection():
    ''' mocks data returned from the cloud provider '''

    def __init__(self):
        self.APIVersion = "test"
        self.stop_count = 0

    def stop_instances(self, *args, **kwargs):
        self.stop_count += 1

    def get_all_reservations(*args, **kwargs):

        ret = []

        class Instance:
            def __init__(self):
                self.instance_type = 't2.nano'
                self.state = 'running'
                self.id = 'id-1234'
                self.ip_address = "1.2.3.4"
                self.private_ip_address = "172.100.2.3"
                self.image_id = 'ami-test'
                self.vpc_id = 'vpc-id-1'
                self.tags = { 'Name':'worker1', 'aws:cloudformation:stack-name':'nano1' }

        class Reservation:
            def __init__(self):
                self.instances = []

        names = ['master', 'worker0', 'worker1']
        for i in range(3):
            reservation = Reservation()
            inst = Instance()
            inst.tags['Name'] = names[i]
            reservation.instances.append(inst)
            ret.append(reservation)

        for i in range(3):
            reservation = Reservation()
            inst = Instance()
            inst.tags['Name'] = 'node%s' % i
            inst.tags['aws:cloudformation:stack-name'] = 'nano2'
            inst.state='stopped'
            inst.ip_address = ''
            reservation.instances.append(inst)
            ret.append(reservation)

        return ret

g_test_cluster_config = '''
    cloud:
      provider: ec2
      region: eu-central-1
    cluster:
      filter: tags=aws:cloudformation:stack-name:nano1
      name: nano1
    nodes:
    - image: ami-d8203bb4
      instance_type: t2.nano
      nodename: master
      selector: tags=Name:master
      username: ec2-user
    - image: ami-d8203bb4
      instance_type: t2.nano
      nodename: worker0
      selector: tags=Name:worker0
      username: ec2-user
    - image: ami-d8203bb4
      instance_type: t2.nano
      nodename: worker1
      selector: tags=Name:worker1
      username: ec2-user
'''

## test cases

@mock.patch('dustcluster.cluster.ClusterCommandEngine', autospec=MockCommandEngine)
@mock.patch('boto.ec2.connect_to_region', return_value=MockBotoEC2Connection())
class TestCommandEngine(unittest.TestCase):

    def setUp(self):
        self.engine = ClusterCommandEngine()
        self.engine.load_commands()

        self.engine.clusters =  {'nano1'  : yaml.load(g_test_cluster_config) }
        self.engine.handle_command('loglevel', 'debug')
        self.engine.handle_command('cluster', 'list')

    def test_match_nodes_to_cluster_config(self, mock_ec2_conn, mock_engine):

        target_nodes = self.engine.resolve_target_nodes(op='show', target_node_name="")
        self.assertEqual( len(target_nodes), 6 )

    def test_filter_by_name(self, mock_ec2_conn, mock_engine):

        target_nodes = self.engine.resolve_target_nodes(op='show', target_node_name="worker*")
        self.assertEqual( len(target_nodes), 2 )

    def test_filter_by_property(self, mock_ec2_conn, mock_engine):

        target_nodes = self.engine.resolve_target_nodes(op='show', target_node_name="ip=1.2.*")
        self.assertEqual( len(target_nodes), 3)


    def test_filter_by_property(self, mock_ec2_conn, mock_engine):

        target_nodes = self.engine.resolve_target_nodes(op='show', target_node_name="tags=*stack-name:nano1")
        self.assertEqual( len(target_nodes), 3)

    def test_node_op_stop(self, mock_ec2_conn, mock_engine):

        self.engine.handle_command('stop', 'worker*')
        self.assertEqual(self.engine.cloud.conn().stop_count, 2)

if __name__ == "__main__":
    unittest.main()


