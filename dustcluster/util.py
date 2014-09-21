''' utility functions '''

import logging

def setup_logger(sname):

    logger = logging.getLogger(sname)
    logger.setLevel(logging.INFO)

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)

    formatter = logging.Formatter('\rdust:%(asctime)s | %(message)s')
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

