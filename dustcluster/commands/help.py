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
from collections import defaultdict
import dustcluster

''' render help from plugin command docstrings ''' 

# export commands 
commands  = ['help']

def help(cmdline, cluster, logger):
    '''
    help [cmd] - Show help on command cmd. 
    '''

    commands = cluster.get_commands()
    args = cmdline.split()

    if len(args) > 0:
        if args[0] in commands:
            docstr, _ = commands.get(args[0])
            print(colorama.Fore.GREEN, docstr, colorama.Style.RESET_ALL)

            if "filter" in docstr:
                print("    Type filters for help with filter expressions.\n")

            return

    print("Dust cluster shell, version %s" % (dustcluster.__version__))
    print("\nAvailable commands:\n")

    # generate help summary from docstrings

    # show help from drop-in commands
    modcommands = defaultdict(list)
    for cmd, (docstr, mod) in commands.items():
        modcommands[mod].append( (cmd, docstr) )

    for mod, cmds in modcommands.items():
        print("\n%s== From %s:%s" % (colorama.Style.DIM, mod.__name__, colorama.Style.RESET_ALL))
        for (cmd, docstr) in cmds: 
            _print_cmd_help(docstr, cmd)

    print('\nType help [command] for detailed help on a command')
    print('\n')


def _print_cmd_help(docstr, cmd):
    ''' format and print the cmd help string '''
    if docstr and '\n' in docstr:
        helpstr = docstr.split('\n')[1]
        if '-' in helpstr:
            pos = helpstr.rfind('-')
            cmd, doc = helpstr[:pos].strip(), helpstr[pos+1:].strip()
        else:
            doc = ""
        parts = cmd.strip().split()
        cmdname= "%s %s%s%s" % (parts[0], colorama.Style.DIM, " ".join(parts[1:]), colorama.Style.RESET_ALL)
        print("%-50s%s%s%s" % (cmdname, colorama.Fore.GREEN, doc.strip(), colorama.Style.RESET_ALL))
    else:
        print("%-50s" % cmd.strip())

