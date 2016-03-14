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

'''load a cloud config '''
import os
import re
import ConfigParser
from dustcluster.EC2 import EC2Cluster, EC2Node

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
        text_conf = config.read(config_file)

        if not os.path.exists(config_file) or not config:
            raise Exception('Could not load config file %s' % config_file)

        if not config.has_section('cloud'):
            raise Exception('load_template: cannot find @cloud section in template.')

        cloudopts = dict( config.items('cloud') )

        provider = cloudopts.pop('provider', '')
        if provider != 'ec2': 
            raise Exception('load_template: missing or unknown cloud.provider specified - %s' %  provider)

        # create cloud
        cloud = EC2Cluster(**cloudopts)

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
        logger.error('Error loading template : %s' % ex)
        logger.exception(ex)
        cloud = None

    return cloud





def test():
    cloud = load_template('sample.ec2.cnf')
    cloud.show()

if __name__ == '__main__':
    test()
