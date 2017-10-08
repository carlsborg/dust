
import os
import colorama
import ConfigParser
from EC2 import EC2Config
import stat
import yaml

from dustcluster.util import setup_logger
logger = setup_logger( __name__ )

class DustConfig(object):
    ''' loads, saves, owns credentials config file and user_data config file '''

    _instance = None

    def __new__(cls):
        if not DustConfig._instance:
             DustConfig._instance = object.__new__(cls)
        return DustConfig._instance

    user_dir         = os.path.expanduser('~')
    dust_dir         = os.path.join(user_dir, '.dustcluster')

    def __init__(self):

        self.credentials = {}
        self.user_data = {}

        self.history_file     = os.path.join(self.dust_dir, 'cmd_history')
        self.credentials_file = os.path.join(self.dust_dir, 'credentials')
        self.userdata_file    = os.path.join(self.dust_dir, 'user_data')
        self.aws_credentials_file  = os.path.join(self.user_dir, '.aws/credentials')

        # first time setup
        if not os.path.exists(self.credentials_file) or not os.path.exists(self.userdata_file):
            logger.info("%sWelcome to dustcluster, creating config file:%s"  % (colorama.Fore.GREEN, colorama.Style.RESET_ALL))

            aws_creds = {}
            if os.path.exists(self.aws_credentials_file):
                confirm = raw_input("Found default awscli credentials in [%s]. Use these? [Y]:" % self.aws_credentials_file) or "y"
                if confirm[0].lower() == "y":
                    aws_creds = self.read_credentials(self.aws_credentials_file)

            ec2creds, ec2data =  EC2Config.setup_credentials(aws_creds)
            self.credentials.update(ec2creds)
            self.user_data.update(ec2data)
            self.write_credentials()
            self.write_user_data()
        else:
            # read in credentials and user data
            logger.debug("Reading credentials from [%s]" % self.credentials_file)
            self.credentials = self.read_credentials(self.credentials_file)

            logger.debug("Reading user data from [%s]" % self.userdata_file)
            self.user_data = self.read_user_data()

            EC2Config.validate(self.credentials, self.user_data)

    @staticmethod
    def get():
        return DustConfig._instance

    def get_credentials(self):
        return self.credentials

    def get_userdata(self):
        return self.user_data

    def get_history_file_path(self):
        return self.history_file

    def read_user_data(self):
        if os.path.exists(self.userdata_file):
            with open(self.userdata_file, 'r') as fh:
                user_data = yaml.load(fh) or {}
        else:
            user_data = {}

        return user_data

    def read_credentials(self, file_path):
        ''' read dustcluster or aws credentials '''

        parser = ConfigParser.ConfigParser()
        parser.read(file_path)

        config_data = parser.defaults()

        if not config_data:
            config_data = dict(parser.items("default"))

        return config_data

    def write_user_data(self):

        logger.debug("Writing user data to %s" % self.userdata_file)

        str_yaml = yaml.dump(self.user_data, default_flow_style=False)

        if not os.path.exists(self.dust_dir):
            os.makedirs(self.dust_dir)

        with open(self.userdata_file, 'w') as yaml_file:
            yaml_file.write(str_yaml)

    def write_credentials(self):

        # write creds
        logger.info("Writing credentials to [%s] with mode (0600)" % self.credentials_file)
        parser = ConfigParser.ConfigParser(self.credentials)
        if not os.path.exists(self.dust_dir):
            os.makedirs(self.dust_dir)

        with open(self.credentials_file, 'wb') as fh:
            parser.write(fh) 
        os.chmod(self.credentials_file, stat.S_IRUSR | stat.S_IWUSR)

    def xxwrite_user_data(self):

        closest_region = self.dust_config_data.get("closest_region")
        if closest_region:
            self.update_user_data("closest_region", { "region" : closest_region } )

