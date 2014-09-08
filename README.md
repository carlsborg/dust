dust
====

Dust is an ssh cluster shell for EC2 clusters.

(Currently, this is unstable/head work in progress, and bugs abound)

## Rationale

While developing/prototyping/running tests on EC2, one often needs to bring up a set of nodes, poke around using ssh, stop some nodes, terminate others, and bring the whole cluster back up later on. 

Dust is a potentially useful swiss army knife for these kinds of system admin tasks and development activities. Suitable for for small clusters upto 10 nodes or so.

Possibly also helpful for getting to repeatable custom playbooks/recipes in third party configration tools.

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

> dust$ start

> dust$ show


### Use filter expressions and wildcards for operations on node subsets


\# target is nodes named worker*
> dust$ stop worker\*             

\# target is nodes where state=stopped
> dust$ start state=stopped     

\# target is nodes named worker0, worker1
> dust$ terminate worker[0-1]


### Send line-buffered shell commands over ssh to a set of nodes 

Use '@[target] cmd' to execute cmd on nodes defined by [target]

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

Equivalent ways to address the same node set:

> dust$ @worker[0-1]  ls /var/log

> dust$ @w\*  ls /var/log

Using filter expressions:

> dust$ stop master

> dust$ @state=running  ls /var/log

> dust$ @state=run\*  ls /var/log/auth.log

```
[worker0] -rw-r----- 1 syslog adm 398707 Sep  7 23:42 /var/log/auth.log
[worker0] 


[worker1] -rw-r----- 1 syslog adm 642 Sep  7 23:42 /var/log/auth.log
[worker1] 


[worker2] -rw-r----- 1 syslog adm 14470 Sep  7 23:46 /var/log/auth.log
[worker2] 
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

the interactive command continues on all nodes where the response was sent.

### Enter into fully  responses to interactive raw shell on a single node 

> dust$ @worker2

This enters the a regular interactive shell session reusing the same session as the one above, but in char buffered mode -- for running full screen console apps such as vim or top. When done, exit the shell completely ($exit) or keep it going in 
the background (Ctrl-C x3) for future line buffered commands or raw shell mode.


### Extensible drop in commands 

To add functionality, drop in a python file implementing new commands into dustcluster/commands. 

Out of the box commands: get (cluster download), put (cluster upload), setting up security groups, etc.

Type help or ? inside the dust shell for more

Unrecognized commands drop to the system shell, so you can edit files, run configuration management tools locally from the same prompt.
