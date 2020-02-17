
###Install 

$pip3 install dustcluster --user

###Configure

####1. Get EC2 account credentials 

Log into AWS Management Console-> User name on top right-> Security Credentials. Then,

Create Access key -> Show Access key or Download access key 

(Optionally, fist create an IAM user and then create and use the access key for the new user, remember to do a "Attach user policy"->Administrator or similar for this user)  

AWS credentials look like this:

> Access Key ID: AKIAIEABCDABCDABCD

> Secret Access Key: P123oiwndoindfpKDDDKANSDFIDd00fdKA8saase

Create a file ~/.aws/credentials:

[default]
aws_access_key_id = YourAccessKeyID
aws_secret_access_key = YourSecretAccessKey


###Kick the tires


####2. Drop into a dust shell

> dust

> dust$ show 

should show running nodes in the region.

####3. Use existing nodes, no clusters configured

tbd

####4. Start a new cluster

tbd

####5. Work with existing clusters

