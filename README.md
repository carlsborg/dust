
dust
====

DustCluster is an ssh cluster shell for EC2

Status:
* Tested/known to work on Linux and OSX only (Debian, Ubuntu, CentOS, OSX Yosemite)
* Developed/tested with Python 2.7
* Currently, this is alpha/work in progress

See setup.py for dependencies.


Table of Contents
=================

  * [Rationale](#rationale)
  * [Getting started](#getting-started)
  * [Target a set of nodes](#target-a-set-of-nodes)
  * [Use a working set](#use-a-working-set)
  * [Cluster ssh to a set of nodes](#cluster-ssh-to-a-set-of-nodes)
    * [These are demultiplexed fully interactive ssh shells !](#these-are-demultiplexed-fully-interactive-ssh-shells-)
    * [Run vim or top on a single node, with the same ssh session.](#run-vim-or-top-on-a-single-node-with-the-same-ssh-session)
  * [Add stateful drop-in python commands](#add-stateful-drop-in-python-commands)



### Rationale

DustCluster lets you perform cluster-wide parallel ssh and node operations on AWS ec2 instances, using
wildcard and filter expressions to target nodes.

It also lets you easily bring up a new cluster from a minimal spec, with security groups, placement groups,
and spot pricing configured, on top of which you can use the cluster ssh feature to configure them.

This can be useful for developing, prototyping, and one-off configurations of (usually ephemeral) EC2 clusters.
Such as when developing custom data engineering stacks.

Example:
Given a cluster with nodes named master, worker1 .. 5, you can do:

```
dust$ @ pwd  	# run the pwd command over ssh on all running nodes

dust$ @worker* cd /opt/data    # issue stateful shell commands to nodes named worker*
dust$ put data.dat worker* /opt/data
dust$ @w* ls

dust$ @state=running cd /etc        # select nodes by property for ssh commands
dust$ show -v key=MyKey             # select nodes by property for show details
dust$ show launch_time=2016-04-08*  # select nodes by property + wildcards for show 

dust$ stop worker*          # stop all nodes with a local name worker*
dust$ terminate worker[4-5] # terminate nodes named worker4, worker5
```

There is a simple plugin model for adding stateful commands.
All commands you see in dust cluster are implemented as plugins.


### Getting started

At a bash prompt, drop into a dust shell:

> bash$ dust

> dust:2016-04-05 23:41:47,623 | Dust cluster shell, version 0.01. Type ? for help.

You can then either:

1) [Assign existing instances to clusters](docs/assign_to.md)

See [Using DustCluster to bring up high performance cluster infrastructure on AWS EC2](https://zvzzt.wordpress.com/2016/04/11/using-dustcluster-to-bring-up-high-performance-cluster-infrastructure-on-aws-ec2/)


and/or

2) [Bring up a new cluster from a minimal spec](docs/create_cluster.md) with a single command

Both ways, cluster configs are saved to ~/.dustcluster/clusters. and you will henceforth see clusters with named nodes. e.g.


> dust$ show

```
dust:2016-04-01 23:21:01,749 | Nodes in region: us-east-1

    Name         Instance     State        ID         ext_IP          int_IP         


slurm1
      master       t2.small     running      i-b4b1b02e 52.205.250.99   172.31.60.117  
      worker1      t2.nano      running      i-92aeaf08 54.174.251.139  172.31.58.157  
      worker2      t2.nano      running      i-b3b1b029 52.87.183.163   172.31.57.33   

webtest
      web1        t2.micro     running      i-a65f5f3c 52.91.213.83    172.31.56.107
      web2        t2.micro     running      i-a55f5f3f 54.173.124.145  172.31.56.108
```

This shows two clusters called slurm1 and webtest.

Use show -v and show -vv to see *some* node details and *all* node details respectively.

### Target a set of nodes

Most commands take a [target]. e.g. show -v [target]

**By node name**

Once you have assigned nodes to a cluster, nodes now have friendly names and you can use
nodename wildcards as a target for node operations or ssh operations.

> dust$ stop worker\*

> dust$ start wo\*

> dust$ terminate worker[0-2]

> dust$ stop                    # no target or * means all nodes


**By filter expression**

> dust$ show state=stopped

> dust$ start state=stop*       # filters can have wildcards

> dust$ show ip=54.12.*

> dust$ show tags=owner:devops

> dust$ stop tags=env:*       # tags can have wildcards too

> dust$ show -v launch_time=2016-04-03*


type show -vv [target] to see all the available properties you can filter on.


**By cluster name**

> dust$ show -v cluster=sample1

> dust$ stop cluster=slurm1



### Use a working set

**Restrict the working set of nodes to the cluster slurm1**

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


**Revert to everything in the current region**

> dust$ use *

**Switch to everything in a new region**

> dust$ use us-west-1



### Cluster ssh to a set of nodes

Invoke commands over parallel bash shells with the "at target" @[target] operator.
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

The plugin model is simple -- it gives you a list of targeted node objects that the command can perform
operations on, and a cluster state object which holds boto connections etc.

TBD: plugin model

Out of the box commands: get (cluster download), put (cluster upload), setting up security groups, etc.
Type help or ? inside the dust shell for more

Unrecognized commands drop to the system shell, so you can edit files, run configuration management tools locally
from the same prompt.
