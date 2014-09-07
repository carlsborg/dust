#!/usr/bin/python

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

