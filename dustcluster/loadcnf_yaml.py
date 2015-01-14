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
import copy
from yaml import load, dump, Loader, Dumper

from dustcluster.EC2 import EC2Cloud, EC2Node
from dustcluster.util import setup_logger
logger = setup_logger( __name__ )

def load_template(config_file):
    '''
    load a cluster template and create cloud and node objects
    TODO: validate all config options
    '''
    try:

        if not os.path.exists(config_file):
            raise Exception('Template file %s does not exist' % config_file)

        markup = open(config_file).read()
        data = load(markup, Loader=Loader)

        defaults = data.get('defaults') or {}
        cloud_template = data.get('cloud') or {}

        cloudname = cloud_template.get('name')
        if cloud_template and not cloudname:
            raise Exceptio("A cloud definition needs to have a 'cloudname' attribute")

        cloud_template.update(copy.deepcopy(defaults))
        provider = cloud_template.pop('provider', '')
        if provider != 'ec2': 
            raise Exception('load_template: missing or unknown cloud.provider specified - %s' %  provider)

        cloud = EC2Cloud(**cloud_template)

        if cloud_template:
            logger.info('loaded template %s with %s nodes' % (config_file, len(cloud_template.get('nodes', [])) ))
        else:
            logger.info('loaded defaults from %s, no cloud defined' % (config_file))

    except Exception, ex:
        logger.error('Error loading template : %s' % ex)
        logger.exception(ex)
        cloud = None

    return cloud

def test():
    cloud = load_template('default.yaml')
    cloud.show_cloud()
    cloud.show_nodes()

if __name__ == '__main__':
    test()

