'''load a cloud config '''
import os
import re
import ConfigParser
from dustcluster.EC2 import EC2Cloud, EC2Node

from dustcluster.util import setup_logger
logger = setup_logger( __name__ )

class DustConfigParser(ConfigParser.ConfigParser):
    ''' override the section RE  '''
    def __init__(self, *arg, **kwargs):
        ConfigParser.ConfigParser.SECTCRE = re.compile( r'@(?P<header>\w+)' )
        ConfigParser.ConfigParser.__init__(self, *arg, **kwargs)

def load_template(config_file):
    '''
    load a cluster template and create cloud and node objects
    TODO: validate all config options
    '''
    try:
        config = DustConfigParser()
        config.read(config_file)

        if not os.path.exists(config_file) or not config:
            raise Exception('Could not load config file %s' % config_file)

        if not config.has_section('cloud'):
            raise Exception('load_template: cannot find @cloud section in template.')

        cloudopts = dict( config.items('cloud') )

        provider = cloudopts.pop('provider', '')
        if provider != 'ec2': 
            raise Exception('load_template: missing or unknown cloud.provider specified - %s' %  provider)

        # create cloud
        cloud = EC2Cloud(**cloudopts)

        sections  = config.sections()
        for section in sections:
            if section.lower() == 'cloud':
                continue

            nodeopts = dict( config.items(section) )

            # create node
            worker = EC2Node(name=section, **nodeopts)
            cloud.add_node(worker)

        logger.info('loaded template %s with %s nodes' % (config_file, (len(sections)-1)))
    except Exception, ex:
        logger.error('Error loding template : %s' % ex)
        cloud = None

    return cloud

def test():
    cloud = load_template('sample.ec2.cnf')
    cloud.show()

if __name__ == '__main__':
    test()
