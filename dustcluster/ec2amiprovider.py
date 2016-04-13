
AMAZON_LINUX_AMIS = {
            'us-east-1' : 'ami-2df5df47',
            'us-west-1' : 'ami-f7f58397',
            'us-west-2' : 'ami-42b15122',
            'eu-west-1' : 'ami-3c38884f',
            'eu-central-1' : 'ami-d8203bb4',
            'ap-northeast-1': 'ami-eeabaf80',
            'ap-northeast-2' : 'ami-431fd12d',
            'ap-southeast-1' : 'ami-8504cae6',
            'ap-southeast-2' :  'ami-a30126c0',
            'sa-east-1'     : 'ami-e2f4778e'
            }

class EC2AMIProvider(object):
    ''' 
        responsible for obtaining most recent AMI's
        these are hardcoded for now, future versions will use DustCluster published AMIs
    '''

    def get_ami_for_region(self, os, region):

        if os == 'amazonlinux':
            return (AMAZON_LINUX_AMIS.get(region), 'ec2-user')

        return None

