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

''' dust command for getting and putting files from/to a set of nodes '''

import glob

def put(cmdline, cluster, logger):
    ''' upload a file to a set of nodes ''' 

    target = cmdline.split()[0]

    target_nodes = cluster.running_nodes_from_target(target)
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
            cluster.lineterm.put(cluster.cloud.keyfile, node, fname, destfile)


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
        cluster.lineterm.get(cluster.cloud.keyfile, node, remotefile, localdir)

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

