''' dust command for performing ec2 specific operations on nodes ''' 

from collections import namedtuple
from dustcluster.EC2 import EC2Cloud, EC2Node

AuthRule = namedtuple('AuthRule', 'protocol portstart portend cidrip')

# Add custom rules to the default security group

# See here for details
# http://docs.aws.amazon.com/AWSEC2/latest/CommandLineReference/ApiReference-cmd-AuthorizeSecurityGroupIngress.html
# http://boto.readthedocs.org/en/latest/security_groups.html

authrules = [
AuthRule('tcp', 80, 80, '0.0.0.0/0'),   # http 
AuthRule('icmp', -1, -1, '0.0.0.0/0')   # all icmp messages
]

def ec2sec(cmdline, cluster, logger):
    '''
    configure security group
    '''

    args = cmdline

    # get a boto connection object
    conn = cluster.cloud.conn()
    
    sec_groups = conn.get_all_security_groups()

    if args == 'show':

        for sg in sec_groups:
            logger.info('group %s:' % sg.name)
            for rule in sg.rules:
                logger.info(rule)
    
    elif args == 'add': 

        for sg in sec_groups:
            if sg.name == r'default': 
                for rule in authrules:
                    sg.authorize(rule.protocol, rule.portstart, rule.portend, rule.cidrip)

    else: 
        logger.error('unknown args %s' % args)

    logger.info('ok')


def define_template(cmdline, cluster, logger):
    '''
    define_template - custom command, programatically create a cluster template and load it
    '''

    # set cloud and node defaults
    cloud = EC2Cloud(name='democloud', key='test2', region='eu-west-1', image='ami-896c96fe')

    # master node
    master = EC2Node(name='master', instance_type='m3.medium')
    cloud.add_node(master)

    # worker nodes
    for i in range(3):
        worker = EC2Node(name='worker%d'%i, instance_type='t2.small', image='ami-3eb46b49')
        cloud.add_node(worker)

    cluster.set_template(cloud)

# export commands
commands  = {
'ec2sec':   '''
            ec2sec [show] [add] - configure the default security group
            ''',
'define_template':   '''
                define_template - custom command, programatically create a cluster template and load it
                '''
}

# set docstrings
ec2sec.__doc__ = commands['ec2sec']
define_template.__doc__ = commands['define_template']

