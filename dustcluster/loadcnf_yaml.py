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

def load_template(config_file, creds_map={}):
    '''
    load a cluster template and create provider-specific cluster and node objects
    TODO: validate all config options
    '''
    try:

        if not os.path.exists(config_file):
            raise Exception('Template file %s does not exist' % config_file)

        markup = open(config_file).read()

        return load_template_from_yaml(markup, creds_map)

    except Exception, ex:
        logger.error('Error loading template : %s' % ex)
        logger.exception(ex)


def load_template_from_yaml(markup, creds_map={}):
    '''
    load a cluster template and create provider-specific cluster and node objects
    TODO: validate all config options
    '''
    try:

        template_data = load(markup, Loader=Loader)

        cloud_data = template_data.get('cloud')

        if not cloud_data:
            raise Exception("No 'cloud:' section in template")

        provider = cloud_data.get('provider')

        if not provider:
            raise Exception("No 'provider:' section in cloud")

        cloud_provider = None
        cloudregion = cloud_data.get('region')
        if provider.lower() == 'ec2':
            cloud_provider = EC2Cloud(creds_map=creds_map, region=cloudregion)
        else:
            raise Exception("Unknown cloud provider [%s]." % provider)

        # TODO: validate all cluster properties and node properties against the provider

        #defaults = data.get('defaults') or {}
        #cloud_template = data.get('cloud') or {}
        #cloudname = cloud_template.get('name')
        #if cloud_template and not cloudname:
            #raise Exception("A cloud definition needs to have a 'cloudname' attribute")
        #cloud_template.update(copy.deepcopy(defaults))

        logger.debug('Loaded cluster config with %s nodes' % (len(template_data.get('nodes', [])) ))

    except Exception, ex:
        logger.error('Error loading template : %s' % ex)
        logger.exception(ex)
        cloud_provider = None
        template_data = None

    return (cloud_provider, template_data, cloudregion)

def load_template_from_map(config_data, creds_map={}):
    '''
    load a cluster template and create cloud and node objects
    TODO: validate all config options
    '''

    cloud = None
    cloudregion = None

    try:
        cloudregion = config_data["region"]
        cloud = EC2Cloud(creds_map=creds_map, region=cloudregion)
        logger.info('loaded template %s with region %s' % (config_data, cloudregion))

    except Exception, ex:
        logger.error('Error creating cloud cluster from config data.')
        raise

    return (cloud,"",cloudregion)


def show_template(config_file):
    '''
    load a cluster template and create cloud and node objects
    TODO: validate all config options
    '''
    try:

        if not os.path.exists(config_file):
            raise Exception('Template file %s does not exist' % config_file)

        markup = open(config_file).read()
        data = load(markup, Loader=Loader)
        print markup
        print data

        if config_file:
            logger.info('showing template %s with ' % (config_file) )
        else:
            logger.info('showing defaults from %s, no cloud defined' % (config_file))

    except Exception, ex:
        logger.error('Error showing template : %s' % ex)
        logger.exception(ex)     

    return data


def test():
    cloud = load_template('default.yaml')
    cloud.show_cloud()
    cloud.show_nodes()

if __name__ == '__main__':
    test()

