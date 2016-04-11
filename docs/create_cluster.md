
### Creating a new cluster

The "cluster create" command uses troposphere to convert a cluster config of the form below to an AWS cloudformation template, 
and then uses the cloudformation apis to start the cluster.

Firewall/ec2 security groups are configured to:
- allow incoming tcp connections on all ports between nodes
- allow incoming ssh connections on port 22 and all ICMP from the outside
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

- image: ami-8fcee4e5
  instance_type: t2.nano
  nodename: worker
  username: ec2-user
  count: 2
```

Note: the second node has count = 2, so nodes will be called
worker1, worker2

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


Notes:

**Authentication**:

Only key based authentication is supported. DustCluster creates and uses a default key for all clusters you create.
Optionally, you can specify an existing key under each node.

Like so:

```
nodes:

- image: ami-8fcee4e5
  instance_type: t2.nano
  nodename: master
  username: ec2-user
  key: YourKeyName
```



**Placement groups**:

You can create a placement group and launch this cluster in it, with the flag *use_placement_group*

```
cloud:
  provider: ec2
  region: us-east-1

cluster:
  name: sample1
  use_placement_group: yes
```

This puts the nodes in a 10GBps network and closeby to each other for lower inter-node latency.

Notes: 
Only certain instances (xx.large) are allowed in placement groups.


**Launch in an existing VPC**:

You can launch the cluster in an existing VPC by providing the vpc id and subnet id in the cluster section:

```
cloud:
  provider: ec2
  region: us-east-1

cluster:
  name: VPCcluster
  subnet_id: subnet-33c11119
  vpc_id: vpc-29d8864d
```


**Launch in a new VPC**:

You can launch the cluster in a new VPC by providing the create_vpc flag:

```
cloud:
  provider: ec2
  region: us-east-1

cluster:
  name: VPCcluster
  create_vpc: yes
```

This creates an VPC, internet gateway, and public subnet and configures the routing tables.

**Why launch in a VPC?**

When used with the placement groups and the latest Amazon AMIs, this enables Enhanced Networking (using single root 
I/O virtualization). 

You can check if enhanced networking is enabled with:

> dust$ @ ethtool -i eth0 | grep driver     # "at all nodes" 

If Enhanced Networking is enabled the driver is ixgbevf instead of vif

```
[master] driver: ixgbevf
[master] 


[worker1] driver: ixgbevf
[worker1] 


[worker0] driver: ixgbevf
[worker0] 
```

