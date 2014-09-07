''' dust command for getting and putting files from/to a set of nodes '''

# programatically create a cluster template and load it

import dustcluster.lineterm as lineterm
from dustcluster.util import running_nodes_from_target
import glob


def put(cmdline, cluster, logger):
    ''' upload a file to a set of nodes ''' 

    target = cmdline.split()[0]

    target_nodes = running_nodes_from_target(target, cluster, logger)
    if not target_nodes:
        return

    args = cmdline[len(target):].strip()

    arrargs = args.split()
    
    srcfile = None
    destfile = None

    if len(arrargs) > 0:
        srcfile = arrargs[0]

    if len(arrargs) > 1:
        destfile = arrargs[1]

    for node in target_nodes:
        for fname in glob.iglob(srcfile): 
            lineterm.put(cluster.keyfile, node, fname, destfile)


def get(cmdline, cluster, logger):
    ''' download a file from a set of nodes ''' 

    target = cmdline.split()[0]

    target_nodes = running_nodes_from_target(target, cluster, logger)
    if not target_nodes:
        return

    args = cmdline[len(target):].strip()

    arrargs = args.split()

    remotefile = None
    localdir = None

    remotefile = arrargs[0]

    if len(arrargs) > 1:
        localdir = arrargs[1]

    for node in target_nodes:
        lineterm.get(cluster.keyfile, node, remotefile, localdir)

commands = {
'put':  '''
        put tgt src [dest] - upload src file to a set of target nodes
        ''',
'get':  '''
        get tgt remotefile [localdir] - download remotefile from a set of nodes to [localdir] or cwd as remotefile.nodename
        '''
}

# set docstrings
put.__doc__ = commands['put']
get.__doc__ = commands['get']

