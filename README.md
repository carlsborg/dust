
dust
====

DustCluster is an ssh cluster shell for EC2

Status:
* Tested/known to work on Linux only (Debian, Ubuntu, CentOS)
* Developed/tested with Python 2.7
* Currently, this is alpha/work in progress

[Installation and quick start](INSTALL.md)


Table of Contents
=================

  * [Rationale](#rationale)
  * [Usage](#usage)
    * [Working with existing nodes](#working-with-existing-nodes)
      * [One time setup](#one-time-setup)
    * [Start a new cluster](#start-a-new-cluster)
    * [Target nodes with wildcards and filter expressions](#target-nodes-with-wildcards-and-filter-expressions)
    * [Cluster ssh to a set of nodes](#cluster-ssh-to-a-set-of-nodes)
      * [These are demultiplexed fully interactive ssh shells !](#these-are-demultiplexed-fully-interactive-ssh-shells-)
      * [Run vim or top on a single node, with the same ssh session.](#run-vim-or-top-on-a-single-node-with-the-same-ssh-session)
    * [Add stateful drop-in python commands](#add-stateful-drop-in-python-commands)



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
dust:2016-04-01 22:55:32,904 | Retrieved [5] nodes from cloud provider
dust:2016-04-01 22:55:32,904 | Nodes in region: us-east-1

    Name         Instance     State        ID         ext_IP          int_IP         


Unassigned:
                   t2.micro     running      i-a65f5f3c 52.91.213.83    172.31.56.107  
                   t2.micro     running      i-a55f5f3f 54.173.124.145  172.31.56.108  
                   t2.nano      running      i-b4b1b02e 52.205.250.99   172.31.60.117  
                   t2.nano      running      i-92aeaf08 54.174.251.139  172.31.58.157  
                   t2.nano      running      i-b3b1b029 52.87.183.163   172.31.57.33  
```

Or show with details:

> dust$ showex

```
dust:dragonex$ showex
dust:2016-04-01 22:56:27,527 | Retrieved [1] nodes from cache
dust:2016-04-01 22:56:27,528 | Nodes in region: us-east-1

    Name         Instance     State        ID         ext_IP          int_IP         


Unassigned:
              t2.nano      running      i-b4b1b02e 52.205.250.99   172.31.60.117  
              tags : aws:cloudformation:stack-name=slurm1,aws:cloudformation:stack-id=arn:aws:cloudformation:us-east-1:065319647096:stack/slurm1/018af690-f84e-11e5-94ee-500c20fefad2,aws:cloudformation:logical-id=master
              image : ami-8fcee4e5
              hostname : ec2-52-205-250-99.compute-1.amazonaws.com
              launch_time : 2016-04-01T21:09:27.000Z
              key : useast1_dustcluster
              vpc:subnet : vpc-2ce97948:subnet-193d2c32

              ... etc
```

As of now these nodes show as "Unassigned" to any cluster. In this state you can perform basic node state operations on them:

Use filters to show/start/stop nodes:

> dust$ show state=running

> dust$ stop id=i-e6d4b265

Filter by tag:

> dust$ showex tags=name:node\*

Filter by tag to show the cloud formation stack slurm1:

> dust$ showex tags=aws:cloudformation:stack-name:slurm1
or

> dust$ showex tags=\*stack-name:slurm1



#### One time setup

To enable cluster ssh, we assign nodes to a cluster:

> dust$ assign tags=\*cloudformation\*stack-name:slurm1

This selects nodes where tags have key = \*cloudformation\*stack-name and value=slurm1, and saves down a cluster config
so that you can name nodes and address them by friendly names (as you would in sshconfig).

Name this cluster slurm1

> Wrote cluster config to /home/booda/.dustcluster/clusters/slurm1.yaml.

Edit the cluster config file for nodenames if needed.

Now you can perform cluster ssh operations.

> show

```
dust:2016-04-01 23:08:31,777 | Nodes in region: us-east-1

    Name         Instance     State        ID         ext_IP          int_IP         


Unassigned:
                   t2.micro     running      i-a65f5f3c 52.91.213.83    172.31.56.107  
                   t2.micro     running      i-a55f5f3f 54.173.124.145  172.31.56.108  

slurm1
      node0        t2.nano      running      i-b4b1b02e 52.205.250.99   172.31.60.117  
      node1        t2.nano      running      i-92aeaf08 54.174.251.139  172.31.58.157  
      node2        t2.nano      running      i-b3b1b029 52.87.183.163   172.31.57.33  
```

We still have some unassigned nodes. Use $showex to examine tags and properties for 
the unassigned nodes and assign them to a cluster. If there are no usable tags, you can tag the nodes with:

> dust$ tag id=i-a65f5f3c cluster-name=webtest

> dust$ tag id=i-a55f5f3f cluster-name=webtest

> dust$ assign tags=cluster-name:webtest

> Name this cluster: webtest

```
dust:2016-04-01 23:12:17,530 | Wrote cluster config to /home/booda/.dustcluster/clusters/web.yaml.
```

Optionally edit this file if needed - change names, specify an
alternate ssh key, etc and reload the clusters with $refresh

> dust$ show

```
dust:2016-04-01 23:21:01,749 | Nodes in region: us-east-1

    Name         Instance     State        ID         ext_IP          int_IP         


slurm1
      node0        t2.nano      running      i-b4b1b02e 52.205.250.99   172.31.60.117  
      node1        t2.nano      running      i-92aeaf08 54.174.251.139  172.31.58.157  
      node2        t2.nano      running      i-b3b1b029 52.87.183.163   172.31.57.33   

webtest
      web1        t2.micro     running      i-a65f5f3c 52.91.213.83    172.31.56.107 
      web2        t2.micro     running      i-a55f5f3f 54.173.124.145  172.31.56.108 
```

These cluster configs are in  ~/.dustcluster/clusters

### Start a new cluster

Optionally there is support to sync a very minimal cluster spec to the cloud. 

The $load command uses troposphere to convert a cluster config of the form below to an AWS cloudformation template, 
and then uses the cloudformation apis to start the cluster.

Firewall/ec2 security groups are configured to:
- allow incoming tcp connections on all ports between nodes
- allow incoming ssh connections on port 22 from the outside
- allow all outgoing connections

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

Note: the second node has count = 2, so nodes will be called
worker1, worker2

Note: replace YourKeyName with an existing key name

> dust$ cluster create sample1.yaml

This dumps the cloudformation template for review, validates it from the cloud, and creates a stack.
See the creation status of this cluster with $cluster status stackname

> dust$ cluster status sample1

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

You can see the new cluster with $show/ex:

```
dust:2016-04-01 23:48:57,732 | Nodes in region: us-east-1

    Name         Instance     State        ID         ext_IP          int_IP         


sample2
      master       t2.nano      running      i-8b131311 52.90.188.52    172.31.51.183  
      worker0      t2.nano      running      i-d115154b 54.152.211.101  172.31.57.213  
      worker1      t2.nano      running      i-411313db 52.207.253.73   172.31.58.141  

slurm1
      node0        t2.nano      running      i-b4b1b02e 52.205.250.99   172.31.60.117  
      node1        t2.nano      running      i-92aeaf08 54.174.251.139  172.31.58.157  
      node2        t2.nano      running      i-b3b1b029 52.87.183.163   172.31.57.33   

web
      node0        t2.micro     running      i-a65f5f3c 52.91.213.83    172.31.56.107  
      node1        t2.micro     running      i-a55f5f3f 54.173.124.145  172.31.56.108  

```

Life is good.

You can list all clusters, and delete a cluster with:

> dust$ cluster delete slurm1

> dust$ cluster list # show clusters by region


**Note on authentication**:

Only key based authentication is supported. You can specify the key or keyfile in the cluster config under each node.

### Target a set of nodes

*By node name*

Once you have assigned nodes to a cluster, nodes now have friendly names and you can use 
nodename wildcards as a target for node operations or ssh operations.

> dust$ stop worker\*

> dust$ start wo\*

> dust$ terminate worker[0-2]

> dust$ stop                    # no target or * means all nodes


*By filter expression*

> dust$ show state=stopped

> dust$ showex key=*Prod*

> dust$ start state=stop*       # filters can have wildcards

> dust$ show tags=owner:devops

> dust$ stop tags=env:*       # tags can have wildcards too


*By cluster name*

> dust$ showex cluster=sample1

> dust$ stop cluster=slurm1


### Using a working set 

*Restrict the working set of nodes to the cluster slurm1*

> dust$ use slurm1

> dust$ show

```
dust:2016-04-01 23:36:47,009 | Nodes in region: us-east-1

    Name         Instance     State        ID         ext_IP          int_IP         


slurm1
      node0        t2.nano      running      i-b4b1b02e 52.205.250.99   172.31.60.117  
      node1        t2.nano      running      i-92aeaf08 54.174.251.139  172.31.58.157  
      node2        t2.nano      running      i-b3b1b029 52.87.183.163   172.31.57.33   
```

Now all global operations (without a filter or with filter=\*)
will apply to only these nodes:

> dust$ stop # stops all nodes in cluster slurm1

> dust$ stop *  # same

> dust$ start # starts all nodes in cluster slurm1

> dust$ @ sudo tail /var/log/audit  # invoke sudo tail on all nodes


*Revert to everything in region us-east-1*

> dust$ use us-east-1


### Cluster ssh to a set of nodes

Send commands to parallel bash shells with the "at target" @[target] operator. 
No target means all nodes in the working set.

Execute 'dmesg | tail' over ssh on all $used nodes:

> dust$ @ dmesg | tail

Execute 'uptime' over ssh on a set of nodes named worker\* with:

> dust$ @worker\* uptime

Execute 'uptime' over ssh on all nodes with tag env=dev

> dust$ @tags=env:dev uptime

Execute 'uptime' over ssh on all nodes in cluster named slurm:

> dust$ @cluster=slurm1 ls /opt

or

> dust$ use slurm1

> dust$ @ ls /opt


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

#### These are demultiplexed fully interactive ssh shells !

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

#### Run vim or top on a single node, with the same ssh session.

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


### Add stateful drop-in python commands

To add functionality, drop in a python file implementing new commands into dustcluster/commands.

Out of the box commands: get (cluster download), put (cluster upload), setting up security groups, etc.

Type help or ? inside the dust shell for more

Unrecognized commands drop to the system shell, so you can edit files, run configuration management tools locally
from the same prompt.
