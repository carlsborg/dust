# Copyright (c) Ran Dugal 2014
#
# This file is part of dust cluster
#
# Licensed under the GNU Affero General Public License v3, which is available at
# http://www.gnu.org/licenses/agpl-3.0.html
# 
# This program is distributed in the hope that it will be useful, but WITHOUT 
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU Affero GPL for more details.
#

import logging
import paramiko
import boto
from dustcluster import util

''' dust commands to set log levels on all module loggers ''' 


# export commands 
commands  = ['loglevel']

boto.set_stream_logger('boto', logging.DEBUG)

def loglevel(cmdline, cluster, logger):
    '''
    loglevel [info|debug] - turn up/down the logging to debug/info
    '''

    level = cmdline.strip().lower()

    if level.lower() == 'info':
        set_loglevel(logger, logging.INFO)
        logger.info('switched log level to INFO')
    elif level.lower() == 'debug':
        set_loglevel(logger, logging.DEBUG)
        logger.info('switched log level to DEBUG')
    else:
        logger.info('undefined log level %s' % level)

def set_loglevel(logger, level):

    logging.getLogger().setLevel(level)
    logger.setLevel(level)

    for mname, mlogger in logging.Logger.manager.loggerDict.iteritems():
        if getattr(mlogger, 'setLevel', None):
            logger.debug('setting loglevel on %s' % mname)
            mlogger.setLevel(level)

    # handle paramiko separately, its logs at INFO way too liberally

    paramiko_logger = logging.getLogger("paramiko")
    if len(paramiko_logger.handlers) == 0:
        util.setup_logger("paramiko")

    if (level == logging.INFO):
        paramiko_logger.setLevel(logging.ERROR)
        logging.getLogger("paramiko.transport").setLevel(logging.ERROR)
    elif (level == logging.DEBUG):
        paramiko_logger.setLevel(logging.DEBUG)
        logging.getLogger("paramiko.transport").setLevel(logging.DEBUG)

