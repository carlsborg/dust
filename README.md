dust
====

DustCluster is an ssh cluster shell for EC2

Status:
* Tested/known to work on Linux only (Debian, Ubuntu, CentOS)
* Developed/tested with Python 2.7
* Currently, this is alpha/work in progress

[Installation and quick start](INSTALL.md)

## Rationale

DustCluster is an ssh cluster shell primarily useful for development, prototyping, one-off configuration of (usually ephemeral) EC2 clusters.
Can be useful when developing custom data engineering stacks.

Features:
* Parallel stateful bash shells over ssh.
* Node selection with wildcards in name, property, or tag -- for ssh or node operations.
* Commands to bring up a new cluster using cloudformation from a minimal spec via troposphere.
* Easily extensible -- add new stateful commands.

Example:
Given a cluster with nodes named master, worker1 .. 5, you can do:

```
dust$ @ pwd  	# run the pwd command on all running nodes 

dust$ @worker* cd /opt/data    # issue stateful shell commands to nodes named worker*
dust$ put data.dat worker* /opt/data
dust$ @w* ls

dust$ @state=running cd /etc    # select nodes by property for ssh 
dust$ showex key=MyKey          # select nodes by property for show details

dust$ stop worker*         # stop all nodes with a local name worker*
dust$ terminate worker[4-5] # terminate nodes named worker4, worker5 
```

## Usage

### Working with existing nodes

Drop into a dust shell, and show all the nodes in the current region 

> dust$ show

```
Name         Instance     State        ID         ext_IP          int_IP         

             t2.nano      running      i-c8cbad4b 52.90.67.41     172.31.60.216  
             t2.nano      running      i-e6d4b265 52.90.136.102   172.31.61.174  
             t2.nano      running      i-1bd4b298 54.209.17.39    172.31.52.216  
             t2.nano      running      i-72caacf1 52.91.104.162   172.31.58.249  
             t2.nano      running      i-07d5b384 52.91.240.38    172.31.59.61
```

Or show with details:

> dust$ showex

```
Name         Instance     State        ID         ext_IP          int_IP         

             t2.nano      running      i-c8cbad4b 52.90.67.41     172.31.60.216  
              image : ami-8fcee4e5
              hostname : ec2-52-90-67-41.compute-1.amazonaws.com
              key : useast1_dustcluster
              DNS : ec2-52-90-67-41.compute-1.amazonaws.com
              tags : cluster=nano,name=node0

            .. etc..                   
```

Use filters to show/start/stop nodes:

> dust$ show state=running

> dust$ stop id=i-e6d4b265

Filter by tag:

> dust$ showex tags=name:node\*

Some setup - assign nodes to a cluster and name them, using the 'assign' command.

> dust$ assign tags=\*cloudformation\*stack-name:kafka1   

This selects nodes for tags where key is \*cloudformation\*stack-name and value is kafka1, and saves them to a
 cluster config so that you can name nodes and address them by a friendly name (as you would in sshconfig).

Edit the cluster config file for nodenames if needed and then use the cluster with:

> dust$ use cluster NewClusterName

Now you can perform cluster operations targeting nodes with the local names and wildcards.


### Start a new cluster

Optionally there is support to sync a very minimal cluster spec to the cloud. The load command uses troposphere 
to convert a cluster config of the form below to an AWS cloudformation template, and then uses the cloudformation apis
to start the cluster.

sample1.yaml

```
cloud:
  provider: ec2
  region: us-east-1

cluster:
  name: sample1

nodes:

- image: ami-8fcee4e5
  instance_type: t2.nano
  nodename: master
  username: ec2-user
  key: YourKeyName

- image: ami-8fcee4e5
  instance_type: t2.nano
  nodename: worker
  username: ec2-user
  key: YourKeyName
  count: 2
```

Note the second node has count = 2.

> dust$ load sample1.yaml

This dumps the cloudformation template for review, validates it from the cloud, and creates a stack.
See the creation status of this cluster with $status stackname

> dust$ status sample1

Shows events from the cloudformation create:

```
dust:dragonex$ status sample1
dust:2016-03-30 13:52:01,121 | Connecting to cloud formation endpoint in us-east-1
StackEvent AWS::CloudFormation::Stack sample1 CREATE_IN_PROGRESS
StackEvent AWS::EC2::Instance master CREATE_IN_PROGRESS
StackEvent AWS::EC2::Instance worker1 CREATE_IN_PROGRESS
StackEvent AWS::EC2::Instance master CREATE_IN_PROGRESS
StackEvent AWS::EC2::Instance worker1 CREATE_IN_PROGRESS
dust:2016-03-30 13:52:01,636 | ok
```

Once the new nodes are up, use them with:

> dust$ use cluster sample1

```
dust:2016-03-30 13:53:01,772 | Showing nodes for cluster [sample1] in region [us-east-1]

Name         Instance     State        ID         ext_IP          int_IP         


worker0      t2.nano      running      i-3b2c29b8 52.87.190.56    172.31.59.157  
master       t2.nano      running      i-362c29b5 54.173.43.74    172.31.55.88   
worker1      t2.nano      running      i-632f2ae0 52.207.216.220  172.31.50.102  
```


**Note on authentication**:

Only key based authentication is supported. You can specify the key or keyfile in the cluster config under each node.

### Target a set of nodes with wildcards and filter expressions

Once you have loaded a cluster config with "$use cluster clustername", nodes now have 
friendly names and you can use nodename wildcards as a target:

The basic node operations are start/stop/terminate 

with wildcards:

> dust$ stop worker\*

> dust$ start wo\*

> dust$ terminate worker[0-2]

with filter expressions:

> dust$ start state=stopped

> dust$ start state=stop*       # filters can have wildcards 

> dust$ stop tags=env:dev

The general form for node opertions is

> start/stop/terminate [target]

No target implies all nodes.


### Cluster ssh to a set of nodes

Send commands to parallel bash shells with the @[target] operator 

Execute 'uptime' over ssh on a set of nodes named worker\* with:

> dust$ @worker\* uptime

Execute 'uptime' over ssh on all nodes with tag env=dev

> dust$ @tags=env:dev uptime

The general form for ssh is:

> dust$ @[target] command


e.g.

> dust$ @worker\* tail -2 /etc/resolv.conf

```
[worker0] nameserver 172.31.0.2
[worker0] search eu-west-1.compute.internal
[worker0] 


[worker1] nameserver 172.31.0.2
[worker1] search eu-west-1.compute.internal
[worker1] 


[worker2] nameserver 172.31.0.2
[worker2] search eu-west-1.compute.internal
[worker2] 
```

Again, [target] can have wildcards:

> dust$ @worker[0-2]  ls /var/log

> dust$ @w\*  ls /var/log

Or filter expressions:

> dust$ stop master

> dust$ @state=running  ls /var/log

> dust$ @id=i-c123*  ls /var/log

> dust$ @state=run\*  ls -l /var/log/auth.log

```
[worker0] -rw-r----- 1 syslog adm 398707 Sep  7 23:42 /var/log/auth.log
[worker0] 


[worker1] -rw-r----- 1 syslog adm 642 Sep  7 23:42 /var/log/auth.log
[worker1] 


[worker2] -rw-r----- 1 syslog adm 14470 Sep  7 23:46 /var/log/auth.log
[worker2] 
```

### These are demultiplexed fully interactive ssh shells !

So this works:

> dust$ @worker* cd /tmp

> dust$ @worker* pwd

```
[worker0] /tmp
[worker0] 

[worker1] /tmp
[worker1] 
```

And so does this:

> dust$ @worker0 sleep 10 && echo '10 second sleep done!' & 


> dust$ @worker0 ls -l /var/log/boot.log

```
[worker0] -rw------- 1 root root 0 Sep 19 13:18 /var/log/boot.log
[worker0] 

# 10 seconds later

[worker0] 10 second sleep done!
[worker0] 
```

And this:

> dust$ @worker\* sudo apt-get install nginx

```
.
.
[worker0] After this operation, 5,342 kB of additional disk space will be used.
[worker0] Do you want to continue? [Y/n] 

.
.
[worker1] After this operation, 5,342 kB of additional disk space will be used.
[worker1] Do you want to continue? [Y/n] 

.
.
[worker2] After this operation, 5,342 kB of additional disk space will be used.
[worker2] Do you want to continue? [Y/n] 
```

> dust$ @work\* Y

sends a Y to all the nodes named work\* and the apt-get script continues.

(There are commands to drive Ansible playbooks coming soon)

### Run vim or top on a single node, with the same ssh session.

> dust$ @worker2

The ssh '@' operator with a target and no commands enters a regular interactive ssh shell on a single node -- for running full screen console apps such as vim or top. 

This re-uses the same ssh session as the one above, but in char buffered mode:

> dust$ @worker* cd /tmp

> dust$ @worker0

> rawshell:worker0:/tmp$ pwd

```
/tmp
```


When done, log out of the ssh shell ($exit) or keep it going in the background (Ctrl-C x3) for future line 
buffered commands or raw shell mode.


### Add custom functionality with stateful drop-in python commands 

To add functionality, drop in a python file implementing new commands into dustcluster/commands. 

Out of the box commands: get (cluster download), put (cluster upload), setting up security groups, etc.

Type help or ? inside the dust shell for more

Unrecognized commands drop to the system shell, so you can edit files, run configuration management tools locally 
from the same prompt.

