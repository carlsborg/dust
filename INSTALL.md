
###Install 


Tested on: Debian 7, Python 2.7.3

#### 1. Install pip if you dont have it:

> sudo apt-get install python-pip

> sudo pip install -U pip


#### 2.  Install dependencies:

> sudo apt-get install python-dev

> sudo pip install boto

> sudo pip install paramiko


###Configure 


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

```
[Credentials]
aws_access_key_id = YOUR_ACCESS_KEY_ID
aws_secret_access_key = YourSecretAccessKey
```

Or create a named boto profile 

```
[profile Dust]
aws_access_key_id = YOUR_ACCESS_KEY_ID
aws_secret_access_key = YourSecretAccessKey
```

###Kick the tires

####1. Get dust

> $git clone https://github.com/carlsborg/dust.git

####2. Drop into a dust shell

> $python dust.py 

Examine the sample template, uncomment the boto_profile if you added one above.

> $vim samples/democloud.yaml

Load a sample template

> dust$ load samples/democloud.yaml

> loaded template samples/democloud.yaml with 1+3 nodes

> dust$ show 

this loads a template with a node called master and 3 nodes called worker0 to worker2.

> dust$ start worker* 

> dust$ show 

After the show command shows all instances running, check if ssh is working

Note: It could take a few minutes for the ssh port to open after ec2 shows the instance as running. During this time connect+login will appear to hang. Asynch connect is a work in progress.

> dust$ @worker* uname -a

List conf files on all running machines

> dust$ @ ls /etc/*.conf 

(Note that @ with no target means all running nodes.) 

Browse local file system, and upload a file to the cluster

> dust$ ls -l /etc/slurm-llnl   # commands not recognized by dust drop to system shell, e.g. vim, clear

> dust$ put worker* /etc/slurm-llnl/slurm.conf   # uploads to home dir

Check the home directories for the files

> dust$ @ pwd

> dust$ @ ls -l

Copy the files to the correct location

> dust$ @worker*  sudo cp slurm.conf /etc/slurm-llnl



#### Working with existing EC2 instances

Edit and load the template samples/cloud.cnf. It defines basic cloud config including region and key, but no nodes.
