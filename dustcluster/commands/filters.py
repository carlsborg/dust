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
import colorama

''' dummy command to handle $help filters'''

help_str = '''
Most commands take a target. e.g. show -v [target]
Here, [target] is a comma separated list of filter expressions.

Filter expression is evaluated as (in order of precedence):

**A node index**
    dust$ stop 1,2,3
    dust$ @1,2,3 service restart nginx

**A cluster name**
    dust$ show -v pyspark1      # all nodes in cluster pyspark1
    dust$ stop slurm1           # all nodes in cluster slurm1

    Note: see $help assign for assigning nodes to clusters

**A node name**

    Name comes from Instance tags with Key=Name.e.g { name : mysql }

    dust$ stop worker\*
    dust$ start wo\*
    dust$ terminate worker[0-2]
    dust$ @worker\* vmstat

**attr=value EC2 attribute or tags**
    dust$ show state=stopped
    dust$ start state=stop*       # filters can have wildcards
    dust$ @ip=54.12.* uptime
    dust$ @tags=owner:devops uptime
    dust$ stop tags=env:*       # tags can have wildcards too
    dust$ show -v launch_time=2016-04-03*

Note: in addition, the show command takes a search term so  
        $show -v 192.168
      does a free text search for "192.168" in all attributes/tags.
'''

# export commands 
commands  = ['filters']

def filters(cmdline, cluster, logger):
    '''
    filters - see help on filter expressions
    '''

    print "%s%s%s" % (colorama.Fore.GREEN, help_str, colorama.Style.RESET_ALL)

