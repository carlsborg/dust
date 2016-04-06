

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

> dust$ show -v

```
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

> dust$ show -v tags=name:node\*

Filter by tag to show the cloud formation stack slurm1:

> dust$ show -v tags=aws:cloudformation:stack-name:slurm1
or

> dust$ show -v tags=\*stack-name:slurm1



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

We still have some unassigned nodes. Use $show -v to examine tags and properties for 
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
