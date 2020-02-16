import time
import datetime
import boto3

commands = ['rules']
client_cache = {}

def get_client(cluster):
    client = client_cache.get(cluster.cloud.region)
    if not client:
        creds = cluster.config.get_credentials()
        client = boto3.client('config', region_name=cluster.cloud.region, 
                                            aws_access_key_id=creds.get('aws_access_key_id'),
                                            aws_secret_access_key=creds.get('aws_secret_access_key'))
    return client


def run_rule(rulename, cluster, logger):

    client = get_client(cluster)
    client.start_config_rules_evaluation(ConfigRuleNames=[rulename])

    for i in range(12):
        time.sleep(1)
        print(".")
    print

    # get custom lambda name
    ret = client.describe_config_rules(ConfigRuleNames=[rulename])
    source = ret['ConfigRules'][0].get('Source')
    lambda_name = ""
    if source.get('Owner') == 'CUSTOM_LAMBDA':
        lambda_name = source.get('SourceIdentifier').split(":")[-1]
    
    if lambda_name:
        log_group = '/aws/lambda/' + lambda_name
        logger.info("logs -t " + log_group)
        cluster.handle_command("logs", "-t " + log_group)
    else:
        logger.info("No custom lambda found. %s" % source)


def get_max_date(lastgood, lastfailed):
    if lastgood and lastfailed:
        last_invoked = max(lastgood, lastfailed)
    else:
        last_invoked = lastgood or lastfailed

    return last_invoked


def rules_status(rulename, cluster, logger):

    client = get_client(cluster)

    if rulename:
        resp = client.describe_config_rule_evaluation_status(ConfigRuleNames=[rulename], 
                        Limit=50)
    else:
        resp = client.describe_config_rule_evaluation_status(Limit=50)

    fmt = "%-25s %-30s %-30s %-10s %-10s"
    print (fmt % ("Rule name", "Last Invoked", "Last Eval", "Last Error", "Last Err Msg"))

    status_list = resp.get('ConfigRulesEvaluationStatus')
    status_list = filter(
                         lambda x :  get_max_date(x.get('LastSuccessfulInvocationTime'),x.get('LastFailedInvocationTime')),
                         status_list
                         )

    status_list = sorted(status_list, 
                        key= lambda x : get_max_date(x.get('LastSuccessfulInvocationTime'),
                        x.get('LastFailedInvocationTime')))

    for status in status_list:
        last_invoked = get_max_date(status.get('LastSuccessfulInvocationTime'),
                                    status.get('LastFailedInvocationTime'))

        last_eval = get_max_date(status.get('LastSuccessfulEvaluationTime'), 
                                 status.get('LastFailedEvaluationTime'))

        print (fmt % (status['ConfigRuleName'], last_invoked, last_eval,
                                             status.get('LastErrorCode'), status.get('LastErrorMessage')))

def rules(cmdline, cluster, logger):
    '''
    rules [run rulename | status rulename]    - run config rule rule_name, and print logs

    Examples:
    rules run hello_world
    rules status hello_world
    '''

    args = cmdline.split()
    if len(args) < 1:
        print ("usage: rules [run | status] rule name")
        return

    cmd = args[0]
    rulename = ""
    if len(args) > 1:
        rulename = args[1]

    if (cmd == "run"):
        if not rulename:
            print("no rulename")
            return
        logger.info("running rule %s" % rulename)
        run_rule(rulename, cluster, logger)
    elif (cmd == "status"):
        rules_status(rulename, cluster, logger)

