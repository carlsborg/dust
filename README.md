
dust
====

DustCluster v0.2.0 is an ssh cluster shell for EC2

Status:
* Tested/known to work on Linux and OSX only (Debian, Ubuntu, CentOS, OSX Yosemite)
* Developed/tested with Python 2.7
* Currently, this is alpha/work in progress

See setup.py for dependencies.

[![Build Status](https://travis-ci.org/carlsborg/dust.svg?branch=master)](https://travis-ci.org/carlsborg/dust) [![PyPI version](https://badge.fury.io/py/dustcluster.svg)](https://badge.fury.io/py/dustcluster)


### Overview

DustCluster lets you perform cluster-wide stateful ssh and node operations on AWS ec2 instances; and also bring up some pre-configured clusters on EC2.

This can be useful for developing, prototyping, and one-off configurations of (usually ephemeral) EC2 clusters. Such as when developing custom data engineering stacks and distributed systems.

### Quick Start

> sudo pip install dustcluster

At a bash prompt, drop into a dust shell:

> bash$ dust

> dust:2016-04-05 23:41:47,623 | Dust cluster shell, version 0.2.0. Type ? for help.

**Example AWS operations:**

Given 3 running instances tagged with Name = master, worker1, worker2, and 1 un-named node:

```
# list your instances

```
[eu-west-1]$ show

dust:23:45:11 | Nodes in region: eu-west-1

    @  Name         Type         State        ID                  IP              int_IP         


--vpc-dcb059b9:

unassigned:
       1               t2.nano      running      i-06f17739c9b4d2112 34.241.19.12    172.31.21.91   
       2  worker0      t2.nano      running      i-00adf7a4e1e8eb976 52.51.198.208   172.31.19.41   
       3  worker1      t2.nano      running      i-03b6a32edf6113c55 34.240.112.38   172.31.23.106  
       4  master       t2.nano      running      i-0011f74f23a745e7f 52.208.15.246   172.31.22.129  
```

dust$ node_operation  [filter expression]

```
dust$ show -v               # list details on workers0,1,2,3     
dust$ show -vv  worker[0-3] # list all filterable attributes
dust$ stop 1,2              # stop nodes 1,2
dust$ stop worker*          # stop nodes worker0, worker1

dust$ start state=stopped           # select nodes by attributes
dust$ show cluster=mysstack1        # select nodes by cluster
dust$ show launch_time=2016-04-08*  # select nodes by attributes + wildcards

dust$ tag 1,2 key=value
dust$ tag worker* key=value

```

**Example ssh operations:**

dust$ @[filter-expression] commmand  

```
dust$ @ free -m  	      # run the free -m command over ssh on all running nodes

      [worker0]              total       used       free     shared    buffers     cached
      [worker0] Mem:           489        147        342          0          8         90
      [worker0] -/+ buffers/cache:         48        440
      [worker0] Swap:            0          0          0
      [worker0] 


      [worker1]              total       used       free     shared    buffers     cached
      [worker1] Mem:           489        240        249          0         35        145
      [worker1] -/+ buffers/cache:         59        429
      [worker1] Swap:            0          0          0
      [worker1] 

      [master]              total       used       free     shared    buffers     cached
      [master] Mem:           489        238        251          0         33        144
      [master] -/+ buffers/cache:         60        429
      [master] Swap:            0          0          0
      [master]


dust$ @worker* service restart nginx
dust$ put data.dat worker* /opt/data

dust$ @1,2 cd /tmp      # stateful ssh commands
dust$ @1,2 ls           # show /tmp
```

There is a simple plugin model for adding stateful commands.
All commands you see in dust cluster are implemented as discoervable plugins.


#### Configure ssh logins

Before using ssh you need to configure logins. Use filter expressions to select nodes with the same login user and key:

i) by using the assign command

    This command writes login rules to ~/.dustcluster/login_rules.yaml.

    Example:

    $assign
    selector: tags=key:value 
    login-user: ec2-user
    keyfile : /path/to/kyfile
    member-of: webapp

    1] selector help:
    selector is a filter expression.`

    selector: *                    # selects all nodes
    selector: id=0-asd1212         # selects a single node
    selector: subnet=s-012sccas    # selects all nodes in a subnet

    2] member-of help:
    member-of adds nodes to a cluster, these nodes are grouped together in "show", 
    and can be made into a working set with the "use" command. cluster names can be
    used in filter expressions.

    3] login rules precedence:

    login rules are applied in order that they appear in the file. 
    So given a login_rules.yaml containing:

    - selector: tags=env:prod   
        ...
    - selector: tags=env:dev
        ...
    - selector: *
        ...

    a command like "@node5 service restart xyz" will search for a login rule by matching prod, dev, 
    and then default (*) in that order'''

ii) by manually editing the login rules file.
      See a sample login rules file here.

After assigning all nodes:


### More on Filter expressions 

Most commands take a target. e.g. show -v [target]

Here, [target] is a comma separated list of filter expressions.

Filter expression can be:

**A node index**

> dust$ show -v 1,2,3

> dust$ @1,2,3 service restart nginx

> dust$ @[1-5] cat /etc/resolv.conf


**By node name**

Name comes from Instance tage with Key=Name

> dust$ stop worker\*

> dust$ start wo\*

> dust$ terminate worker[0-2]

> dust$ @worker\* vmstat

**By EC2 attribute or tags**

> dust$ show state=stopped

> dust$ start state=stop*       # filters can have wildcards

> dust$ show ip=54.12.*

> dust$ show tags=owner:devops

> dust$ stop tags=env:*       # tags can have wildcards too

> dust$ show -v launch_time=2016-04-03*

> dust$ show -v launch_time=2016-04-03*

type show -vv [target] to see all the available properties you can filter on.
All filter expressions work for targeting ssh as well. e.g.@state=running free -m 

**By cluster name**

> dust$ show -v cluster=mystack1

> dust$ stop cluster=slurm1

### Switching regions

> dust$ use us-east-1

> dust$ use eu-west-1

etc

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


### More on cluster ssh

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


### Debugging 

See verbose AWS and ssh logging with

> dust$ loglevel debug

> dust$ loglevel info

