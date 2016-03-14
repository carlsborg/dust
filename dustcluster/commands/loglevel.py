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

''' dust commands to set log levels on all module loggers ''' 


# export commands 
commands  = ['loglevel']

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

    logging.getLogger("paramiko").setLevel(level)

    plogger = paramiko.util.logging.getLogger()
    plogger.setLevel(level)

    for mname, mlogger in logging.Logger.manager.loggerDict.iteritems():
        if getattr(mlogger, 'setLevel', None):
            logger.debug('setting loglevel on %s' % mname)
            mlogger.setLevel(level)

