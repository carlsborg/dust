#!/usr/bin/env python
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

'''Dust is an ssh cluster shell for EC2 cloud nodes'''

import os
import sys
import logging

from dustcluster.console import Console

if sys.version <= '2.6' or sys.version >= '3.0':
  print 'Dust has only been tested with Python 2.7. Your version is %s. Exiting' % sys.version.split()[0]
  sys.exit(1)

if 'posix' not in os.name:
  print 'Dust has only been tested with on Linux. Exiting'
  sys.exit(1)

def run_console():
    '''
    Invoke the command loop. Or execute a single command if passed as command line args.
    '''
    
    console = Console()

    try:
        if len(sys.argv) > 1:
            console.onecmd(' '.join(sys.argv[1:]))
            return

        while not console.exit_flag:
            try:
                console.cmdloop()
            except KeyboardInterrupt:
                sys.stdout.flush()
                sys.stdout.write('\n\r')
                continue
    except:
        logging.exception('\n\nA fatal error ocurred. Please file bugs at github.com/carlsborg/dust\n\n')

if __name__ == '__main__':
    run_console()

