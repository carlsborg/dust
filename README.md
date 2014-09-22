dust
====

Dust is an ssh cluster shell for EC2

Status:
* Tested/known to work on Linux only (Debian, Ubuntu, CentOS)
* Developed/tested with Python 2.7
* Currently, this is unstable/head work in progress

[Installation and quick start](INSTALL.md)

## Rationale

While developing/prototyping on EC2 clusters, one often needs to bring up a set of nodes, invoke exploratory ssh commands on the cluster, stop some nodes, resize them, terminate others, and bring the whole cluster back up later on. 

Dust is an ssh cluster shell primarily useful for development, prototyping, custom configuration of EC2 clusters.

The underlying philosophy is that it should be simple to setup a cluster via config, and manage it from the command line; any cloud configuration tasks that would require complex command line options are better done via drop-in python dust commands; and any repeatable OS configuration tasks are better done by invoking a configuration management tool, possibly via a python dust command.

## Usage
Running dust.py drops to a shell that allows you to: 

### Define a cluster of named nodes and idempotently sync it to EC2

sample.cnf

```
@cloud
provider=ec2
name=democloud
region=eu-west-1
username=ubuntu
key=mykey
keyfile=/path/to/mykey.pem

@master
instance_type=m3.medium
image=ami-896c96fe

@worker0
instance_type=t2.small 
image=ami-3eb46b49

@worker1
instance_type=t2.small 
image=ami-3eb46b49
```

> dust$ load sample.cnf

> dust$ show

```
dust:dragonex$ show
dust:2014-09-14 08:29:22,234 | cluster 'democloud' in eu-west-1, using key: ec2dust
        Name     Instance        Image        State           ID           IP          DNS         tags 
Template Nodes:
     worker1     t2.small ami-892fe1fe  not_started                                                     
     worker0     t2.small ami-892fe1fe  not_started                                                     
     worker2     t2.small ami-892fe1fe  not_started                                                     
      master    m3.medium ami-892fe1fe  not_started                                                     
```


> dust$ start

> dust$ show

The nodes should be in the pending state, and the ID, IP and DNS fields populated.

**Note on authentication**:

Only key based authentication is supported. If key and keyfile are not specified in the config above, a new key pair is created in ./keys/clustername.pem and used for starting nodes.


### Use filter expressions and wildcards for operations on node subsets

The generalized usage of commands in dust is:

> $somecmd [target] args

e.g. target is nodes named worker*
> dust$ stop worker\*             

e.g. target is nodes named worker0, worker1, worker2
> dust$ terminate worker[0-2]

e.g. target is nodes where state=stopped
> dust$ start state=stopped     

> dust$ start state=stop*    # filters can have wildcards 


### Send line-buffered commands over ssh to a set of nodes

Use

> @[target] cmd

to execute cmd over ssh on nodes defined by [target]

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

Equivalent ways to address the same node set, using wildcards:

> dust$ @worker[0-2]  ls /var/log

> dust$ @w\*  ls /var/log

Using filter expressions:

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


Note that we are demultiplexing full interactive ssh shells here:

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

### Send line-buffered responses to interactive shell commands on a set of nodes

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

### Enter a fully interactive raw shell on a single node 

> dust$ @worker2

This enters the a regular interactive ssh shell on worker2 -- for running full screen console apps such as vim 
or top. Reusing the same ssh session as the one above, but in char buffered mode. 

When done, log out of the ssh shell ($exit) or keep it going in the background (Ctrl-C x3) for future line 
buffered commands or raw shell mode.


### Extensible drop in commands 

To add functionality, drop in a python file implementing new commands into dustcluster/commands. 

Out of the box commands: get (cluster download), put (cluster upload), setting up security groups, etc.

Type help or ? inside the dust shell for more

Unrecognized commands drop to the system shell, so you can edit files, run configuration management tools locally 
from the same prompt.


