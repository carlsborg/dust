'''
Dust command loop
'''

import time
import sys
import socket
import os
import readline
import logging

from collections import defaultdict
from pkgutil import walk_packages
from cmd import Cmd

from dustcluster import commands
from dustcluster.cluster import Cluster


from dustcluster import util
logger = util.setup_logger( __name__ )

__version__ = '0.01 head/unstable'

class Console(Cmd):
    ''' command line tool to control a cloud cluster '''

    prompt = "dust:%s$ " % socket.gethostname()
    dustintro  = "Dust cluster shell, version %s. Type ? for help." % __version__ 
    default_keypath = os.path.join(os.getcwd(), 'keys')

    def __init__(self):
        Cmd.__init__(self)
        self.cluster = Cluster()
        self.commands = {}  # { cmd : (helpstr, module) }

        util.intro()
        logger.info(self.dustintro)

        # startup
        self.load_commands()

        default_config = 'default.cnf'
        if os.path.exists(default_config):
            logger.info('Found %s, loading template' % default_config)
            self.cluster.load_template(default_config)
            self.cluster.load_default_keys(self.default_keypath)

        self.exit_flag = False
        self.cluster.lineterm.set_refresh_callback(self.redisplay)

    def redisplay(self):
        ''' refresh the prompt '''
        sys.stdout.write('\n\r' + self.prompt)
        sys.stdout.write(readline.get_line_buffer())
        sys.stdout.flush()

    def load_commands(self):
        '''
        dynamically import modules from under dustcluster.commands, and discover commands 
        '''

        start_time = time.time()

        cmds = walk_packages( commands.__path__, commands.__name__ + '.')
        cmdmods  = [cmd[1] for cmd in cmds]
        logger.debug( '... loading commands from %s modules' % len(cmdmods))
        logger.debug(list(cmdmods))

        # import commands and add them to the commands map
        for cmdmod in cmdmods:
            newmod = __import__(cmdmod, fromlist=['commands'])
            for cmdname, cmdhelp in newmod.commands.items():
                self.commands[cmdname] = (cmdhelp, newmod)

        end_time = time.time()

        if self.commands:
            logger.debug('... loaded %s commands from %s in %.3f sec:' % \
                            (len(self.commands), commands.__name__, (end_time-start_time))  )

        for cmd, (shelp, cmdmod) in self.commands.items():
            logger.debug( '%s %s' % (cmdmod.__name__, shelp.split('\n')[1]))

    def emptyline(self):
        pass

    def do_help(self, args):
        '''
        help [cmd] - Show help on command cmd. 
        Modified from base class.
        '''

        if args:
            if args in self.commands:
                docstr, _ = self.commands.get(args)
                print docstr
                return
            return Cmd.do_help(self, args)

        print self.dustintro
        print "\nAvailable commands:\n"

        # generate help summary from docstrings

        names = dir(self.__class__)
        prevname = ""
        for name in names:
            if name[:3] == 'do_':
                if name == prevname:
                    continue
                cmd = name[3:]
                docstr = ""
                if getattr(self, name):
                    docstr = getattr(self, name).__doc__
                self._print_cmd_help(docstr, cmd)

        # show help from drop-in commands
        modcommands = defaultdict(list)
        for cmd, (docstr, mod) in self.commands.items():
            modcommands[mod].append( (cmd, docstr) )

        for mod, cmds in modcommands.iteritems():
            print "\n== From %s:" % mod.__name__
            for (cmd, docstr) in cmds: 
                self._print_cmd_help(docstr, cmd)

        print '\nType help [command] for detailed help on a command'

        print '\nFor most commands, [target] can be a node name, regular expression, or filter expression'
        print 'A node "name" in these commands is the Name tag in the cloud node metadata or in the cluster definition.'
        print '\n'


    def _print_cmd_help(self, docstr, cmd):
        ''' format and print the cmd help string '''
        if docstr and '\n' in docstr:
            helpstr = docstr.split('\n')[1]
            if '-' in helpstr:
                cmd, doc = helpstr.split('-')
            else:
                doc = ""
            print "%-40s%s" % (cmd.strip(), doc.strip())
        else:
            print "%-40s" % cmd.strip()


    def default(self, line):

        # handle unrecognized command
        cmd, arg, line = self.parseline(line)
        cmddata = self.commands.get(cmd)
        if cmddata:
            _ , cmdmod = cmddata
            func = getattr(cmdmod,  cmd)
            func(arg, self.cluster, logger)
        else:

            # not handled? try system shell
            logger.info( 'dustcluster: [%s] trying system shell...\n' % line )
            os.system(line)
        return

    def parseline(self, line):

        # expand @target cmd to atssh target cmd
        if line and line[0] == '@':
            tokens = line.split()
            if len(tokens[0]) == 1:
                line = 'atssh * ' + line[1:]
            else:
                target  = tokens[0][1:]
                line = 'atssh %s %s ' % (target, line[len(tokens[0]):] )

        ret = Cmd.parseline(self, line)
        return ret

    def do_load(self, configfile):
        '''
        load file - load a cluster template definition file

        Arguments:
        file        --- path to the template definition file

        Note: 
        If a template file called default.cnf exists in the current working directory, it gets loaded on startup.
        If key, keyfile are not specified, a default key in ./keys/default.key is created or re-used.

        Example:
        load samples/ec2sample.cnf
        '''

        self.cluster.load_template(configfile)
        self.cluster.load_default_keys(self.default_keypath)

    def do_exit(self, _):
        '''
        exit - exit dust shell
        '''     
        logger.info( 'exiting dustcluster console. please file bugs at http://github.com/carlsborg/dust.')
        self.cluster.logout()
        self.exit_flag = True
        return True

    def do_EOF(self, line):
        '''
        EOF/Ctrl D - exit dust shell
        '''
        return self.do_exit(line)

    def do_loglevel(self, line):
        '''
        loglevel [info|debug] - turn up/down the logging to debug/info
        '''

        if line.lower() == 'info':
            logging.getLogger().setLevel( logging.INFO )
            logger.info('switched log level to INFO') 
        if line.lower() == 'debug':
            logging.getLogger().setLevel( logging.DEBUG )
            logger.info('switched log level to DEBUG')
        else:
            logger.info('undefined log level %s' % line)

