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

'''
Dust command loop
'''

import sys
import socket
import os
import readline
import logging
import ConfigParser
import stat
import colorama

from collections import defaultdict
from cmd import Cmd
from EC2 import EC2Config

import paramiko
from dustcluster import commands, lineterm
from dustcluster import __version__
from dustcluster.cluster import ClusterCommandEngine
import atexit

from dustcluster import util
logger = util.setup_logger( __name__ )

class Console(Cmd):
    ''' command line tool to control a cloud cluster '''

    dustintro  = "Dust cluster shell, version %s. Type ? for help." % __version__
    default_keypath = os.path.join(os.getcwd(), 'keys')

    user_dir         = os.path.expanduser('~')
    dust_dir         = os.path.join(user_dir, '.dustcluster')
    history_file     = os.path.join(user_dir, '.dustcluster/cmd_history')
    dust_config_file = os.path.join(user_dir, '.dustcluster/config')
    aws_config_file  = os.path.join(user_dir, '.aws/config')

    def __init__(self):

        util.intro()

        logger.setLevel(logging.INFO)

        # read config/credentials 
        config_data = {}
        try:
            if os.path.exists(self.dust_config_file):
                logger.debug("Reading dust config from [%s]" % self.dust_config_file)
                config_data = self.read_config(self.dust_config_file)

            if not config_data.get('aws_access_key_id') and os.path.exists(self.aws_config_file):
                logger.debug("Reading aws credentials from [%s]" % self.aws_config_file)
                config_data.update(self.read_config(self.aws_config_file))

            if not config_data.get('aws_access_key_id'):
                logger.info("%sWelcome to dustcluster, creating config file:%s"  % (colorama.Fore.GREEN, colorama.Style.RESET_ALL))
                config_data = self.ask_and_write_credentials(self.dust_config_file)

        except Exception, e:
            logger.error("Error getting config/credentials. Cannot continue.")
            raise

        # load history
        try:
            if os.path.exists(self.history_file):
                readline.read_history_file(self.history_file)
            else:
                if not os.path.exists(self.dust_dir):
                    os.makedirs(self.dust_dir)

        except IOError:
            logger.warning("Error reading history file. No command history available.")

        atexit.register(readline.write_history_file, self.history_file)

        Cmd.__init__(self)

        self.commands = {}  # { cmd : (helpstr, module) }
        # startup
        self.cluster = ClusterCommandEngine(config_data)
        self.cluster.load_commands()
 
        self.exit_flag = False
        self.cluster.lineterm.set_refresh_callback(self.redisplay)

        self.cluster.handle_command('loglevel',  config_data.get('loglevel') or 'info')
        logger.info(self.dustintro)
        if self.cluster.clusters:
            print "\nAvailable clusters:"
            self.cluster.show_clusters()

    @property
    def prompt(self):
        if self.cluster.cloud and self.cluster.cloud.region:
            return "[%s]$ " % self.cluster.cloud.region
        else:
            return "[dust]$ "

    def read_config(self, config_file):

        parser = ConfigParser.ConfigParser()
        parser.read(config_file)

        config_data = parser.defaults()
        
        if not config_data:
            config_data = dict(parser.items("default"))

        return config_data

    def ask_and_write_credentials(self, config_file):

        config_data = EC2Config.configure(logger)

        parser = ConfigParser.ConfigParser(config_data)

        logger.info("Writing credentials to [%s] with mode (0600)" % config_file)

        if not os.path.exists(self.dust_dir):
            os.makedirs(self.dust_dir)

        with open(config_file, 'wb') as fh:
            parser.write(fh)

        os.chmod(config_file, stat.S_IRUSR | stat.S_IWUSR)

        return parser.defaults()

    def redisplay(self):
        ''' refresh the prompt '''
        sys.stdout.write('\n\r' + self.prompt)
        sys.stdout.write(readline.get_line_buffer())
        sys.stdout.flush()


    def emptyline(self):
        pass

    def do_help(self, args):
        '''
        help [cmd] - Show help on command cmd. 
        Modified from base class.
        '''

        commands = self.cluster.get_commands()

        if args:
            if args in commands:
                docstr, _ = commands.get(args)
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
        for cmd, (docstr, mod) in commands.items():
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
                pos = helpstr.rfind('-')
                cmd, doc = helpstr[:pos].strip(), helpstr[pos+1:].strip()
            else:
                doc = ""
            print "%-40s%s" % (cmd.strip(), doc.strip())
        else:
            print "%-40s" % cmd.strip()


    def default(self, line):

        # handle a cluster command
        cmd, arg, line = self.parseline(line)
        if not self.cluster.handle_command(cmd, arg):
            # not handled? try system shell
            logger.info( 'dustcluster: [%s] unrecognized, trying system shell...\n' % line )
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


    def do_exit(self, _):
        '''
        exit - exit dust shell
        '''     
        logger.info( 'Exiting dust console. Find updates, file bugs at http://github.com/carlsborg/dust.')
        logger.info( '%sThis is an early beta release. Consider updating with $pip install dustcluster --upgrade"%s.' %
                     (colorama.Fore.GREEN, colorama.Style.RESET_ALL))

        self.cluster.logout()
        self.exit_flag = True
        return True

    def do_EOF(self, line):
        '''
        EOF/Ctrl D - exit dust shell
        '''
        return self.do_exit(line)

