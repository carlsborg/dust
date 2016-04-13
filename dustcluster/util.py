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

''' utility functions '''

import logging

def setup_logger(sname):

    logger = logging.getLogger(sname)

    console = logging.StreamHandler()

    formatter = logging.Formatter('\rdust:%(asctime)s | %(message)s', '%H:%M:%S')
    console.setFormatter(formatter)

    logger.addHandler(console)
    
    logger.propagate = False

    return logger


def intro():
    s_intro = r'''
        .___              __  
      __| _/_ __  _______/  |_
     / __ |  |  \/  ___/\   __\
    / /_/ |  |  /\___ \  |  | 
    \____ |____//____  > |__| 
         \/          \/      
       
     [..Dust Cluster Shell..] 

'''

    print s_intro

