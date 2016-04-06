import pprint

commands = ['tag', 'untag']


def tag(cmdline, cluster, logger):
    '''
    tag tgt tagkey=tagvalue   - add tag to target node

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

        conn = cluster.cloud.conn()
        r_ids = [node.get('id') for node in target_nodes]

        tagsdict = {}

        for tag in taglist:

            if "=" in tag:
                tagkey, tagval = tag.split("=")
            else:
                tagkey = tag
                tagval = ""

            if tagkey.startswith("aws"):
                logger.error("Error: tagname cannot start with [aws].")
                return

            tagsdict[tagkey] = tagval

        conn.create_tags(r_ids, tagsdict)

        # refresh from cloud next operation
        cluster.invalidate_cache()

    except Exception, e:
        logger.exception('Error: %s' % e)
        return

    logger.info( 'ok' )




def untag(cmdline, cluster, logger):
    '''
    untag tgt tagkey   - remove a tag from a target node

    Notes:
    untag an ec2 node with tag key

    Examples:
    untag worker* env    # remove tag env from nodes named worker*
    untag state=running env=prod
    '''

    try:

        args = cmdline.split()

        if len(args) < 2:
            logger.error("usage: untag target tag")
            return

        target = args[0]
        tags   = args[1]

        taglist = tags.split(",")

        target_nodes = cluster.any_nodes_from_target(target)
        if not target_nodes:
            logger.info('No running nodes found.')
            return

        conn = cluster.cloud.conn()
        r_ids = [node.get('id') for node in target_nodes]

        tagsdict = {}

        for tag in taglist:

            if "=" in tag:
                tagkey, tagval = tag.split("=")
            else:
                tagkey = tag
                tagval = None

            if tagkey.startswith("aws"):
                logger.error("Error: tagname cannot start with [aws].")
                return

            tagsdict[tagkey] = tagval

        conn.delete_tags(r_ids, tagsdict)

        # refresh from cloud next operation
        cluster.invalidate_cache()

    except Exception, e:
        logger.exception('Error: %s' % e)
        return

    logger.info( 'ok' )

