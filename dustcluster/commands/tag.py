import pprint

commands = ['tag', 'untag', 'openport']

def tag(cmdline, cluster, logger):
    '''
    tag filter key=value   - add tag to target nodes

    Notes:
    tag an ec2 node with key=value

    Examples:
    tag worker* env=dev    # add tag env=dev to nodes named worker* 

    Multiple tags works.
    tag worker* tag1=val1,tag2=val2,tag3=val3 - add tags tag1,tag2,tag3 on target nodes
    '''

    try:

        args = cmdline.split()

        if len(args) < 2:
            logger.error("usage: tag target tag=value")
            return

        target = args[0]
        tags   = args[1]

        taglist = tags.split(",")

        target_nodes = cluster.any_nodes_from_target(target)
        if not target_nodes:
            logger.info('No running nodes found.')
            return

        client = cluster.cloud.client()
        r_ids = [node.get('id') for node in target_nodes]

        tagparam = get_tag_param(taglist)

        client.create_tags(Resources=r_ids, Tags=tagparam)

        # refresh from cloud next operation
        cluster.invalidate_cache()

    except Exception as e:
        logger.exception('Error: %s' % e)
        return

    logger.info( 'ok' )




def untag(cmdline, cluster, logger):
    '''
    untag filter key=value   - remove a tag from a target node

    Notes:
    untag an ec2 node with tag key and value 

    Examples:
    untag worker* env=dev           # remove tag env from nodes named worker*
    untag state=running env=prod
    '''

    try:

        args = cmdline.split()

        if len(args) < 2:
            logger.error("usage: untag filter-exp tag=value")
            return

        target = args[0]
        tags   = args[1]

        taglist = tags.split(",")

        target_nodes = cluster.any_nodes_from_target(target)
        if not target_nodes:
            logger.info('No running nodes found.')
            return

        client = cluster.cloud.client()
        r_ids = [node.get('id') for node in target_nodes]

        tagparam = get_tag_param(taglist)

        client.delete_tags(Resources=r_ids, Tags=tagparam)

        # refresh from cloud next operation
        cluster.invalidate_cache()

    except Exception as e:
        logger.exception('Error: %s' % e)
        return

    logger.info( 'ok' )

def get_tag_param(taglist):

        tagparam = []

        for tag in taglist:

            if "=" in tag:
                tagkey, tagval = tag.split("=")
            else:
                tagkey = tag
                tagval = ""

            if tagkey.startswith("aws"):
                logger.error("Error: tagname cannot start with [aws].")
                return

            tagparam.append( {'Key': tagkey, 'Value': tagval } )

        return tagparam


def openport(cmdline, cluster, logger):
    '''
    openport secgroup_id [port  cidr_range]   - list or open TCP ingress port

    secgroup_ip: security group id. (see show -vv under security_groups)
    port: ingress port to open
    cidr_range: cidr range or 0.0.0.0/0 (all) if not given

    Examples:                   
    openport sg-e12345                         # list ingress rules        
    openport sg-e12345 8080                    # open ingress tcp port 8080 from all ips
    openport sg-e12345 8080 192.168.3.0/24     # open ingress tcp port 8080 from cidr range 
    '''

    try:

        args = cmdline.split()

        if len(args) < 1:
            logger.error("openport sec_grp [port] [cidr range]")
            return

        grp_id  = args[0].strip()
        res = cluster.cloud.conn()
        grp = res.SecurityGroup(grp_id)

        if len(args) < 2:
            show_ingress_rules(grp)
            return

        port    = args[1].strip()
        range   = args[2].strip() if len(args) > 2 else "0.0.0.0/0"

        grp.authorize_ingress(CidrIp=range, FromPort=int(port), ToPort=int(port), IpProtocol='tcp')

    except Exception as e:
        logger.exception('Error: %s' % e)
        return

    logger.info( 'ok' )

def show_ingress_rules(grp):
        grp.reload()
        for perm in grp.ip_permissions:
            pprint.pprint(perm)


