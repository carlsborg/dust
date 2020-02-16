
import os
import colorama
import configparser
from dustcluster.EC2 import EC2Config
import stat
import yaml
import glob

from dustcluster.util import setup_logger
logger = setup_logger( __name__ )

class DustConfig(object):
    ''' loads, saves, owns credentials config file and user_data config file '''

    _instance = None
    _inited   = False

    def __new__(cls):
        if not DustConfig._instance:
             DustConfig._instance = object.__new__(cls)
        return DustConfig._instance

    user_dir         = os.path.expanduser('~')
    dust_dir         = os.path.join(user_dir, '.dustcluster')

    def __init__(self):

        if DustConfig._inited:
            return

        DustConfig._inited = True

        self.credentials = {}
        self.user_data   = {}
        self.login_rules = []
        self.clusters    = {}

        self.history_file     = os.path.join(self.dust_dir, 'cmd_history')
        self.credentials_file = os.path.join(self.dust_dir, 'credentials')
        self.userdata_file    = os.path.join(self.dust_dir, 'user_data')
        self.aws_credentials_file  = os.path.join(self.user_dir, '.aws/credentials')
        self.login_rules_file = os.path.join(self.dust_dir, 'login_rules.yaml')
        self.default_keys_dir = os.path.join(self.dust_dir, 'keys')
        self.clusters_dir     = os.path.join(self.dust_dir, 'clusters')

        if not os.path.exists(self.dust_dir):
            os.makedirs(self.dust_dir)

        # first time setup
        if not os.path.exists(self.credentials_file) or not os.path.exists(self.userdata_file):
            logger.info("%sWelcome to dustcluster, creating config file:%s"  % (colorama.Fore.GREEN, colorama.Style.RESET_ALL))

            aws_creds = {}
            if os.path.exists(self.aws_credentials_file):
                confirm = input("Found default awscli credentials in [%s]. Use these? [Y]:" % self.aws_credentials_file) or "y"
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

            self.read_all_clusters()
            self.read_login_rules()

    @staticmethod
    def get():
        return DustConfig._instance

    def get_credentials(self):
        return self.credentials

    def get_default_keys_dir(self):
        return self.default_keys_dir

    def get_userdata(self):
        return self.user_data

    def get_login_rules(self):
        return self.login_rules

    def get_clusters(self):
        return self.clusters

    def get_history_file_path(self):
        return self.history_file

    def get_clusters_dir(self):

        if not os.path.exists(self.clusters_dir):
            os.makedirs(self.clusters_dir)

        return self.clusters_dir

    def read_login_rules(self):
        if os.path.exists(self.login_rules_file):
            with open(self.login_rules_file, "r") as fh:
                rules = yaml.load(fh.read(), Loader=yaml.SafeLoader)
                login_rules = rules
        else:
            login_rules = {}

        self.login_rules =  login_rules.get('login_rules') or []

    def write_login_rules(self):
        str_yaml = yaml.dump({ "login_rules" : self.login_rules}, default_flow_style=False)
        with open(self.login_rules_file, 'w') as fh:
            fh.write(str_yaml)

    def read_user_data(self):
        if os.path.exists(self.userdata_file):
            with open(self.userdata_file, 'r') as fh:
                user_data = yaml.load(fh, Loader=yaml.SafeLoader) or {}
        else:
            user_data = {}

        return user_data

    def write_user_data(self):

        logger.debug("Writing user data to %s" % self.userdata_file)

        str_yaml = yaml.dump(self.user_data, default_flow_style=False)

        if not os.path.exists(self.dust_dir):
            os.makedirs(self.dust_dir)

        with open(self.userdata_file, 'w') as yaml_file:
            yaml_file.write(str_yaml)

    def read_credentials(self, file_path):
        ''' read dustcluster or aws credentials '''

        parser = configparser.ConfigParser()
        parser.read(file_path)

        config_data = parser.defaults()

        if not config_data:
            config_data = dict(parser.items("default"))

        return config_data

    def write_credentials(self):

        # write creds
        logger.info("Writing credentials to [%s] with mode (0600)" % self.credentials_file)
        parser = ConfigParser.ConfigParser(self.credentials)
        if not os.path.exists(self.dust_dir):
            os.makedirs(self.dust_dir)

        with open(self.credentials_file, 'wb') as fh:
            parser.write(fh) 
        os.chmod(self.credentials_file, stat.S_IRUSR | stat.S_IWUSR)

    def save_cluster_config(self, name, str_yaml):
        ''' return path if saved ''' 

        template_file = "%s.yaml" % name
        template_file = os.path.join(self.clusters_dir, template_file)

        if os.path.exists(template_file):
            yesno = input("%s exists. Overwrite?[y]:" % template_file) or "yes"
            if not yesno.lower().startswith("y"):
                return None

        if not os.path.exists(self.clusters_dir):
            os.makedirs(self.clusters_dir)

        str_comment = "#This picks up the latest Amazon Linux AMI with user ec2-user.\n" + \
                      "#For a custom AMI, add props under cluster: \n" + \
                      "#   image: amixyz\n" + \
                      "#   username: login user\n\n"
        with open(template_file, 'w') as yaml_file:
            yaml_file.write(str_comment)
            yaml_file.write(str_yaml)

        return template_file

    def delete_cluster_config(self, name, region):
        template_file = "%s.yaml" % name
        template_file = os.path.join(self.clusters_dir, template_file)
        os.remove(template_file)

        template_file = "%s.%s.cfn" % (region,name)
        template_file = os.path.join(self.clusters_dir, template_file)
        if os.path.exists(template_file):
            os.remove(template_file)

        logger.info("Deleted cluster config: %s" % template_file)

    def read_all_clusters(self):
        wildcardpath = os.path.join(self.clusters_dir, "*.yaml")
        cluster_files = glob.glob(wildcardpath)
        logger.debug("found [%d] clusters in %s" % (len(cluster_files), wildcardpath))
        clusters = {}
        for cluster_file in cluster_files:
            
            if os.path.isfile(cluster_file):
                with open(cluster_file, "r") as fh:
                    cluster = yaml.load(fh.read(), Loader=yaml.SafeLoader)
                    cluster_props = cluster.get('cluster')
                    cluster_name = cluster_props.get('name')
                    clusters[cluster_name] = cluster

        self.clusters = clusters

