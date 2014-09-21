#!/usr/bin/python
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

def run_console():
    '''
    Invoke the command loop. Or execute a single command if passed as command line args.
    '''

    if os.name != 'posix':
        logging.error('Sorry this version of dust has been tested on posix operating systems only.') 
        return

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

