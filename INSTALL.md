
###Install 


Tested on: Debian 7, Python 2.7.3

#### 1. Install pip if you dont have it:

> sudo apt-get install python-pip

> sudo pip install -U pip


#### 2.  Install dependencies:

> sudo apt-get install python-dev

> sudo pip install boto

> sudo pip install paramiko

> sudo pip install troposphere

###Configure 


####1. Get EC2 account credentials 

Log into AWS Management Console-> User name on top right-> Security Credentials. Then,

Create Access key -> Show Access key or Download access key 

(Optionally, fist create an IAM user and then create and use the access key for the new user, remember to do a "Attach user policy"->Administrator or similar for this user)  

AWS credentials look like this:

> Access Key ID: YOUR_ACCESS_KEY_ID

> Secret Access Key: YourSecretAccessKey


###Kick the tires

####1. Get dust

> $git clone https://github.com/carlsborg/dust.git

####2. Drop into a dust shell

> $./dust

> dust$ show 

should show running nodes in the region.

####3. Use existing nodes, no clusters configured

tbd

####4. Start a new cluster

tbd

####5. Work with existing clusters

