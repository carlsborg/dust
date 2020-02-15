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
import stat
import colorama
import threading

from collections import defaultdict
from cmd import Cmd
from dustcluster.EC2 import EC2Config

import paramiko
from dustcluster import commands, lineterm
from dustcluster import __version__
from dustcluster.cluster import ClusterCommandEngine
from dustcluster.config import DustConfig

import atexit
import shlex

from dustcluster import util
logger = util.setup_logger(__name__)

if os.environ.get('COLORTERM') or 'color' in os.environ.get('TERM'):
    colorama.Fore.CYAN = '\x1b[38;5;75m'
    colorama.Fore.GREEN = '\x1b[38;5;76m'


class Console(Cmd):
    ''' command line tool to control a cloud cluster '''

    dustintro = "Dust cluster shell, version %s. Type %s?%s for help." % (
        __version__, colorama.Fore.GREEN, colorama.Style.RESET_ALL)

    def __init__(self):

        util.intro()

        logger.setLevel(logging.DEBUG)

        # read/create config
        try:
            self.config = DustConfig()
        except Exception as e:
            logger.error("Error getting config/credentials. Cannot continue.")
            raise

        # load history
        try:
            if os.path.exists(self.config.get_history_file_path()):
                readline.read_history_file(self.config.get_history_file_path())

        except IOError:
            logger.warning(
                "Error reading history file. No command history available.")

        atexit.register(self.on_exit, None)

        Cmd.__init__(self)

        self.commands = {}  # { cmd : (helpstr, module) }
        # startup
        self.cluster = ClusterCommandEngine()

        self.exit_flag = False
        self.cluster.lineterm.set_refresh_callback(self.redisplay)

        threading.Thread(target=self.cluster.load_commands).start()
        logger.info(self.dustintro)

    @property
    def prompt(self):
        if self.cluster.cloud and self.cluster.cloud.region:
            return "[%s]$ " % self.cluster.cloud.region
        else:
            return "[dust]$ "

    def redisplay(self):
        ''' refresh the prompt '''
        sys.stdout.write('\n\r' + self.prompt)
        sys.stdout.write(readline.get_line_buffer())
        sys.stdout.flush()

    def on_exit(self, _):
        readline.write_history_file(self.config.get_history_file_path())

        confregion = self.config.user_data['region']
        cloud_region = ""
        if self.cluster and self.cluster.cloud:
            cloud_region = self.cluster.cloud.region

        if confregion != cloud_region:
            self.config.user_data['region'] = cloud_region
            self.config.write_user_data()

        print

    def emptyline(self):
        pass

    def do_help(self, args):
        '''
        Modified from base class.
        '''
        self.default("help " + args)

    def onecmd(self, line):
        """ 
        The builtin version of this calls .default() in the exception handler.
        This makes exceptions printed in the commands ugly. So we fix it in the override.
        """
        cmd, arg, line = self.parseline(line)
        if not line:
            return self.emptyline()
        if cmd is None:
            return self.default(line)
        self.lastcmd = line
        if line == 'EOF':
            self.lastcmd = ''
        if cmd == '':
            return self.default(line)
        else:
            useDefault = False
            try:
                func = getattr(self, 'do_' + cmd)
            except AttributeError:
                useDefault = True

            if useDefault:
                return self.default(line)

            return func(arg)

    def default(self, line):
        try:
            cmd, arg, line = self.parseline(line)
            ret = self.cluster.handle_command(cmd, arg)
            if not ret:
                # not handled? try system shell
                logger.info(
                    'dustcluster: [%s] unrecognized, trying system shell...\n' % line)
                os.system(line)
        except Exception as ex:
            logger.exception("Error executing command [%s]" % line)

        return

    def parseline(self, line):

        # expand @target cmd to atssh target cmd
        if line and line[0] == '@':
            tokens = line.split()
            if len(tokens[0]) == 1:
                line = 'atssh * ' + line[1:]
            else:
                target = tokens[0][1:]
                line = 'atssh %s %s ' % (target, line[len(tokens[0]):])

        ret = Cmd.parseline(self, line)
        return ret

    def do_exit(self, _):
        '''
        exit - exit dust shell
        '''
        logger.info(
            'Exiting dust console. Find updates, file bugs at http://github.com/carlsborg/dust.')
        logger.info('%sThis is an early beta release. Consider updating with $pip install dustcluster --upgrade"%s.' %
                    (colorama.Fore.GREEN, colorama.Style.RESET_ALL))

        self.cluster.logout()
        self.exit_flag = True
        return True

    def do_EOF(self, line):
        '''
        EOF/Ctrl D - exit dust shell
        '''
        return self.do_exit(line)
