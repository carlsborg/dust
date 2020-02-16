
dustcluster
===========

DustCluster v0.2.0 is an AWS command line interface in an REPL shell with cluster-aware ssh and EC2 node operations, with plugin commands to bring up some pre-configured clusters on EC2.

Status:
* Linux and OSX only
* Python 3.x

[![Build Status](https://travis-ci.org/carlsborg/dust.svg?branch=master)](https://travis-ci.org/carlsborg/dust) [![PyPI version](https://badge.fury.io/py/dustcluster.svg)](https://badge.fury.io/py/dustcluster)


**Quickstart:**

bash$ pip install dustcluster

bash$ dust

[eu-west-1] show

![dustcluster](https://i.imgur.com/zOIloLD.png)

* [Rationale](#rationale)
* [Summary of Features](#summary-of-features)
    * [As an EC2 web console replacement](#as-an-ec2-web-console-replacement)
    * [Parallel ssh operations](#parallel-ssh-operations)
    * [Cluster-aware ssh and node operations](#cluster-aware-ssh-and-node-operations)
    * [Spin up a new compute cluster](#spin-up-a-new-compute-cluster)
    * [Regions](#regions)
    * [Run commands on localhost](#run-commands-on-localhost)
    * [Command History](#command-history)
* [More on Filter expressions](#more-on-filter-expressions)
* [Configure ssh Logins](#configure-ssh-logins)
* [Writing plugin commands](#writing-plugin-commands)
* [Install](#install)


### Rationale

This can be useful for developing, prototyping, and one-off configurations of (usually ephemeral) EC2 clusters. Such as when developing/testing custom data engineering stacks and distributed systems.


### Summary of Features

##### As an EC2 web console replacement

![dustcluster ec2 operations](https://i.imgur.com/A7VIWeR.gif)
   
 
* start/stop/terminate
  ``` 
  stop [filter-expression]  
  stop *           		# stop all nodes
  stop 1,3,4       		# by index
  stop worker*     		# by name
  stop state=running 	# by EC2 attribute
  ```
 
* list nodes
  ```
  show [-v] [-vv] [filter-expression | search term]
  show      # list all nodes
  show -v   # list with extended attributes
  show -vv  # list with all attributes

  show -v  1,3,4  # using filter expresison
  show -v  worker*
  ```
  
* search
  ``` 
  $show searches all ec2 attributes and tags

  show mongo          # matches tag app=mongodb
  show running        # matches state=running attribute
  show 192.168.0.15   # matches public_ip_address, private_ip_address etc
  show 0.15           # same as above, partial matches work
  show run
  ```

* tag/untag nodes
  ```	
  tag [filter-expression] tags
  tag worker* env=dev
  tag 3,4 stack=spark1
  ```

* refresh cache 
  ```
  refresh
  ```

* view cloudwatch logs 
  ```
  logs                            # shows log groups
  logs /aws/lambda/hello_world    # show log streams in this group
  logs -t /aws/lambda/hello_world # show the most recent log events in this group
  logs -N 50 -t  /aws/lambda/xyz  # increase output limit to 50
  ```

> **Note:** Filter expressions can contain index numbers, node names, or all EC2 instance attributes from show -vv .e.g. image=ami-123145. More on [filter expressions](#more-on-filter-expressions) below.

##### Parallel ssh operations

You need to [configure logins](#configure-ssh-logins) first.

* run non-interactive commands 
  ``` 
  @[filter-expression] command

  e.g. Run  "uptime" on ..

  @ uptime                    # all running nodes
  @1,3,4 uptime               # nodes with indexes 1,3 and 4 
  @worker* uptime             # node names matching worker*
  @image=ami-1234 uptime      # EC2 attribute
  @tags=key:value uptime      # by tags
  ```

* run interactive commands
  ```
  Same as above. This is **stateful** ssh - the connection is kept open.

  @1,2,3 sudo apt-get install nginx

    .
    .
    [worker3] After this operation, 5,342 kB of additional disk space will be used.
    [worker3] Do you want to continue? [Y/n]

        
  @1,2,3 y

  // sends a Y to all the nodes named work\* and the apt-get script continues.
  ```        

* run ncurses/full screen commands
  ```
  @[filter_exp]  -  drops to a shell

  [eu-west-1]$ @9
  dust:11:48:43 | *** Entering raw shell, press ctrl-c thrice to return to cluster shell. Press Enter to continue.***

  [ec2-user@ip-172-31-44-125 ~]$ 
  [ec2-user@ip-172-31-44-125 ~]$ vim /etc/resolv.conf
  ```

* secure copy files
  ```
  put [filter_exp] localfile* remote_dir
  get [filter_exp] remotefile local_dir

  put 1,3 /home/alice/data*.csv /home/ec2-user
  get 1,3 /home/ec2-user/data3.csv .
  ```

##### Cluster-aware ssh and node operations

When you are working with a 3 node cluster but you have 25 ec2 nodes... 

* use a working set
  ```
  use [clustername | *]

  use spark1
  show              # shows cluster nodes only
  @ uptime          # incvoke command over ssh to cluster nodes only
  tag * cool=yes    # tags cluster nodes only
  ```

You specify cluster membership in the [login configuration](#configure-ssh-logins).

* remove working set restriction
  ```
  use *
  ```


##### Spin up a new compute cluster

* Create a N node compute cluster with 10 GBps interconnect with in a placement group in the default VPC, with keys downloaded and security groups configured. More details here.
```
  cluster new           - asks for node count and creates a cluster spec   

  cluster create base1  - converts the spec to a CloudFormation template and instantiates it

  cluster status base1  - shows the Cloudformation status

  cluster delete base1  - terminates the cluster nodes  
```


##### Regions
  ```
  use us-east-1     # switch to region
  ```

##### Run commands on localhost

If dustcluster doesn't recognize a command, it drops it to the calling shell.

  ```
  [eu-west-1]$ ls -plart /var/log
  dust:12:06:08 | dustcluster: [ls -plart /var/log] unrecognized, trying system shell...

  total 25828
  drwx------.  2 root    root               4096 Feb  5  2016 ppp/
  drwx------.  3 root    root               4096 Nov 14  2016 libvirt/
  drwxr-xr-x.  2 chrony  chrony             4096 Nov 21  2016 chrony/
  .
  .

  [eu-west-1]$ vim /home/alice/topsecret.txt    # runs vim locally

  ```

##### Command History

* Reverse search (ctrl-R) to retrieve old commands
  ```
  (reverse-i-search)`':@1,3,5,7 grep -c ERROR /var/logs/applogs/app.log

  up/down arrow to navigate 
  ``` 

### More on Filter expressions 

Most commands take a target. e.g. show -v [target]

Here, [target] is a comma separated list of filter expressions.

Filter expression can be:

**A node index**

> dust$ stop 1,2,3

> dust$ @1,2,3 service restart nginx

**By node name**

Name comes from Instance tags with Key=Name

> dust$ stop worker\*

> dust$ start wo\*

> dust$ terminate worker[0-2]

> dust$ @worker\* vmstat

**By EC2 attribute or tags**

> dust$ show state=stopped

> dust$ start state=stop*       # filters can have wildcards

> dust$ @ip=54.12.* uptime

> dust$ @tags=owner:devops uptime

> dust$ stop tags=env:*       # tags can have wildcards too

> dust$ show -v launch_time=2016-04-03*

"show" takes a search term as well so this is equivalent:

> dust$ show -v 2016-04-03

**By cluster name**

> dust$ show -v cluster=mystack1

> dust$ stop cluster=slurm1

### Configure ssh Logins

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

### Writing plugin commands

Write commands to an interface and drop them into dustcluster...

i) Write a plugin command that list all your instances in all regions.

TBD

ii) Write a plugin command that runs a set of ssh commands on a cluster 

TBD


### Installation Troubleshooting

If pip install fails on the cryptography libs (needed for ssh), then manually install these deps:

**Ubuntu:**
```
# pip
sudo apt-get update
sudo apt-get install python-pip
sudo pip install pip --upgrade

# deps
sudo apt-get install build-essential python-dev libffi-dev libssl-dev
sudo pip install enum34 cffi bcrypt cryptography

# dust
sudo pip install dustcluster
```

**AmazonLinux/CentOS:**
```
#deps
yum install gcc gcc-c++ make openssl-devel python-devel libffi-devel libssl-devel        
sudo  pip install enum34 cffi bcrypt cryptography

# dust
sudo pip install dustcluster
```

On a python 3 default system, use sudo pip2.7 instead of pip above.
