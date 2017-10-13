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

# export commands

commands = ['put', 'get']

def put(cmdline, cluster, logger):
    '''
    put localfiles target [target dir] - upload local files

    Notes:
    localfiles can have wildcards

    Examples:
    put /opt/data/data1.txt worker* # uploads data.txt to cwd
    put /opt/data/data*.txt 1,2     # wildcards work
    put /opt/data/data2.txt worker* /opt/data
    '''
    if not cmdline or len(cmdline) < 2:
        logger.error("usage: put target src [dest]")
        return

    arr  = cmdline.split()
    srcfile = arr[0]
    target = arr[1]

    destdir = None
    if len(arr) > 2:
        destdir = arr[2]

    globbed = glob.iglob(srcfile)
    if not list(globbed):
        logger.error('local files not found : %s' % srcfile)
        return

    target_nodes = cluster.running_nodes_from_target(target)
    if not target_nodes:
        return

    for node in target_nodes:
        globbed = glob.iglob(srcfile)
        for fname in globbed: 
            cluster.lineterm.put(node.login_rule.get('keyfile'), node, fname, destdir)


def get(cmdline, cluster, logger):
    '''
    get tgt remotefile [localdir] - download remotefile from a set of nodes to [localdir] or cwd as remotefile.nodename

    Notes:
    remotefile cannot be a wildcard

    Example:
    get worker* /opt/output/data1.txt    # download to cwd
    get worker* /opt/output/data1.txt /tmp   # download to /tmp
    '''

    if not cmdline or len(cmdline) < 2:
        logger.error("usage: get target remotefile [localdir]")
        return

    target = cmdline.split()[0]

    target_nodes = cluster.running_nodes_from_target(target)
    if not target_nodes:
        logger.info('no running nodes match %s' % target)
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


