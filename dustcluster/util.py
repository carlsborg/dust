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


def running_nodes_from_target(target_str, cluster, logger):
    '''
    params: same as a command
    returns: target_nodes : a list of running target nodes
    '''

    target_nodes = cluster.resolve_target_nodes(target_node_name=target_str)

    if not target_nodes:
        return None

    target_nodes = [node for node in target_nodes if node.state == 'running']

    if not target_nodes:
        logger.info( 'No target nodes are in the running state' )
        return None

    return target_nodes

