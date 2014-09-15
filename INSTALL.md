
###Install 


Tested on: Debian 7, Python 2.7.3

#### 1. Install pip if you dont have it:

> sudo apt-get install python-pip

> sudo pip install -U pip


#### 2.  Install dependencies:

> sudo apt-get install python-dev

> sudo pip install boto

> sudo pip install paramiko

###Quick Start


####1. Get EC2 account credentials 

Log into AWS Management Console-> User name on top right-> Security Credentials. Then,

Create Access key -> Show Access key or Download access key. 
Or
Create an IAM user and then create an access key for the user. 

AWS credentials look like this:

> Access Key ID: YOUR_ACCESS_KEY_ID

> Secret Access Key: YourSecretAccessKey


####2. Configure boto:

Paste the credentials in a boto config 

> vim  ~/.boto

[Credentials]
aws_access_key_id = YOUR_ACCESS_KEY_ID
aws_secret_access_key = YourSecretAccessKey

####3. Get dust

> $git clone https://github.com/carlsborg/dust.git

####4. Drop into a dust shell and issue some commands

> $python dust.py 

Load a sample template

> dust$ load samples/ec2sample.cnf

> loaded template samples/ec2sample.cnf with 5 nodes

this loads a template with a node called master and 4 nodes called worker0 to worker3.

Start workers

> start worker* 

Check if ssh is working

> @worker* uname -a

Browse local file system, and upload a file to the cluster

> $ls /etc/slurm-llnl   # commands not recognized by dust drop to system shell

> $put worker* /etc/slurm-llnl/slurm.conf   # uploads to home dir

Copy the files to the correct location

> @worker*  cp slurm.conf /etc/slurm-llnl

#### Working with existing EC2 instances

Edit and load the template samples/cloud.cnf. It defines basic cloud config including region and key. 
