'''
commands to view cloudwatch logs easily
'''
import getopt
import time
import boto3
import colorama

commands = ['logs']

client_cache = {}

# if the arg matches a known log group/stream dont search for it
known_log_groups = set()
known_log_streams = set()

def get_client(cluster):
    client = client_cache.get(cluster.cloud.region)
    if not client:
        creds = cluster.config.get_credentials()
        client = boto3.client('logs', region_name=cluster.cloud.region, 
                                            aws_access_key_id=creds.get('aws_access_key_id'),
                                            aws_secret_access_key=creds.get('aws_secret_access_key'))

    return client

def logs(cmdline, cluster, logger):
    '''
    logs [-N M] [-t] [log_group] [log_stream]  - show M last cloudwatch log groups, log streams, or log events

    Notes:
    -N M  show last M entries
    -t    tail the most recent events from a log group

    Examples:
    logs                                show all log groups
    logs /aws/lam                       show log groups starting with /aws/lam
    logs /aws/lambda/test1              show log streams in this log group
    logs -t /aws/lambda/test1           show the most recent event streams events
    logs -t -N  50  /aws/lambda/f1      show the last 50 most recent events in this log group 
    logs -N 10 log_group log_stream     show last 10 events in log_stream
    '''
    opts,args = getopt.getopt(cmdline.split(), "tN:")

    limit = 5
    do_tail = False
    for opt, optval in opts:
        if opt == '-N':
            limit = int(optval)
        elif opt == '-t':
            do_tail = True

    loggroup_name = ""
    logstream_name = ""
    if len(args) > 0:
        loggroup_name = args[0]
    if len(args) > 1:
        logstream_name = args[1]

    resolved_log_group = ""

    client = get_client(cluster)

    print(colorama.Fore.GREEN, "limit=%s" % limit, colorama.Style.RESET_ALL)

    if loggroup_name in known_log_groups:
        logger.debug("known log group")
        resolved_log_group = loggroup_name
    else:
        logger.info("searching ...")
        # show log groups
        log_groups = None
        if loggroup_name:
            log_groups = client.describe_log_groups(logGroupNamePrefix=loggroup_name, limit=limit)
        else:
            log_groups = client.describe_log_groups(limit=limit)

        print(colorama.Fore.GREEN, "log groups:", colorama.Style.RESET_ALL)
        log_groups = log_groups.get('logGroups')
        log_groups = sorted(log_groups, key= lambda x: x.get('creationTime'))
        for log_group in log_groups:
            lg_name = log_group.get('logGroupName')
            ts = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(long(log_group['creationTime'])/1000.0))
            print(ts, colorama.Fore.CYAN, lg_name, colorama.Style.RESET_ALL)
            known_log_groups.add(lg_name)
            if len(log_groups) == 1 and lg_name == loggroup_name:
                resolved_log_group = loggroup_name

    if not resolved_log_group:
        logger.debug("could not resolve a unique log group. returning")
        return

    resolved_log_stream = ""
    if logstream_name in known_log_streams:
        logger.debug("known log stream")
        resolved_log_stream = logstream_name
        log_streams = []
    else:
        if logstream_name:
            log_streams = client.describe_log_streams(logGroupName=resolved_log_group, 
                    logStreamNamePrefix=logstream_name, limit=limit)
        else:
            log_streams = client.describe_log_streams(logGroupName=resolved_log_group, 
                    orderBy='LastEventTime', descending=True, limit=limit if not do_tail else 3)

        print(colorama.Fore.GREEN, "log streams:", colorama.Style.RESET_ALL)
        log_streams = log_streams.get('logStreams')

        print ("%-20s %-20s Messsage" % ('Creation', 'Last Event'))
        for log_stream in log_streams:
            ls_name = log_stream.get('logStreamName')
            ts1 = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(long(log_stream['creationTime'])/1000.0))
            ts2 = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(long(log_stream.get('lastEventTimestamp'))/1000.0))
            print(ts1, ts2, colorama.Fore.CYAN, ls_name, colorama.Style.RESET_ALL)

            known_log_streams.add(ls_name)
            if len(log_streams) == 1 and ls_name == logstream_name:
                resolved_log_stream = ls_name

        if do_tail:
            resolved_log_stream = log_streams[-1].get('logStreamName')

    if do_tail and logstream_name:
        for log_stream in log_streams:
                show_log_events(client, resolved_log_group, log_stream.get('logStreamName'), 3)
        return

    if not resolved_log_stream:
        logger.debug("could not resolve a unique log stream. returning")
    else:
        show_log_events(client, resolved_log_group, resolved_log_stream, limit)



def show_log_events(client, resolved_log_group, resolved_log_stream, limit):
    print(colorama.Fore.GREEN, "log events from %s:" % resolved_log_stream, colorama.Style.RESET_ALL)

    log_events = client.get_log_events(logGroupName = resolved_log_group,
                                        logStreamName = resolved_log_stream, limit=limit)

    for log_event in log_events.get('events'):
        ts = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(long(log_event['timestamp'])/1000.0))
        msg = log_event['message']
        if msg[-1] == '\n':
            msg = msg[:-1]
        if msg[0] in ['{', '[']:
            msg = format_as_json(msg)
        print(ts, colorama.Fore.CYAN, msg, colorama.Style.RESET_ALL)
    

def format_as_json(msg):
    ''' assume invalid json, pretty print dont decode '''
    ret = ""
    indent = -1
    for c in msg:
        ret += c
        if c == ',':
            ret += '\n'
            ret += '    ' * indent
        if c in ['{', '[']:
            indent += 1
            ret += '\n'
            ret += '    ' * indent
        if c in ['}', ']']:
            indent -= 1 
    return ret

