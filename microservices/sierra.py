#!/usr/bin/env python3

"""Generate a CloudFormation template for microservices.

"""

import argparse
import json
import sys

from troposphere import GetAtt, Join, Ref, Sub
from troposphere import Parameter, Template
from troposphere.cloudformation import Stack


S3_DOMAIN = 's3.amazonaws.com'


def meta_git_repo(url):
    """Creates a list of services from a meta git repository."""
    print('Currently unsupported')
    sys.exit(0)


def services_file(path):
    """Creates a list of services from a configuration file."""

    def update(old, new):
        for k, v in new.items():
            if isinstance(v, dict):
                old[k] = update(old.get(k, {}), v)
            else:
                old.setdefault(k, v)
        return old

    with open(path) as f:
        config = json.load(f)

    default = config['default']
    del config['default']

    for service in config['services']:
        update(service, default)

    return config['services']


def build_template(services):
    template = Template()

    bucket = template.add_parameter(Parameter(
        'TemplateBucket',
        Description='The S3 bucket containing all of the templates.',
        Type='String',
        Default='templates.sierra.goeppes',
    ))

    instance_type = template.add_parameter(Parameter(
        'InstanceType',
        Type='String',
        Default='t2.micro'
    ))

    cluster_size = template.add_parameter(Parameter(
        'ClusterSize',
        Type='Number',
        Default=1
    ))

    key_name = template.add_parameter(Parameter(
        'KeyName',
        Type='AWS::EC2::KeyPair::KeyName',
    ))

    subnets = template.add_parameter(Parameter(
        'Subnets',
        Type='List<AWS::EC2::Subnet::Id>',
    ))

    vpc = template.add_parameter(Parameter(
        'VPC',
        Type='AWS::EC2::VPC::Id',
    ))

    def template_url(name):
        return Sub(f'https://{S3_DOMAIN}/${{{bucket.title}}}/templates/{name}')

#    template.add_resource(Stack(
#        'Network',
#        TemplateURL=template_url('network.yml'),
#    ))

    elb = template.add_resource(Stack(
        'ELB',
        TemplateURL=template_url('load-balancer.yml'),
        Parameters={
            'Prefix': Ref('AWS::StackName'),
            'Subnets': Join(',', Ref(subnets)),
            'VPC': Ref(vpc),
        }
    ))

    cluster = template.add_resource(Stack(
        'Cluster',
        TemplateURL=template_url('ecs-cluster.yml'),
        Parameters={
            'ClusterSize': Ref(cluster_size),
            'InstanceType': Ref(instance_type),
            'KeyName': Ref(key_name),
            'SourceSecurityGroup': GetAtt(elb, 'Outputs.SecurityGroup'),
            'Subnets': Join(',', Ref(subnets)),
            'VPC': Ref(vpc),
        }
    ))

    for service in services:
        template.add_resource(Stack(
            service['name'] + 'Service',
            TemplateURL=template_url('ecs-service.yml'),
            Parameters={
                'ContainerName': service['name'] + '-container',
                'ContainerImage': service['docker']['image'],
                'ContainerPort': service['docker']['port'],
                'ServiceName': service['name'] + '-service',
                'Cluster': GetAtt(cluster, 'Outputs.ClusterName'),
                'TargetGroup': GetAtt(elb, 'Outputs.TargetGroup'),
            }
        ))

#        template.add_resource(Stack(
#            service['name'] + 'Pipeline',
#            TemplateURL=template_url('pipeline.yml'),
#            Parameters={
#                'GitRepo': service['git']['github-repo'],
#                'GitBranch': service['git']['github-branch'],
#                'GitUser': service['git']['github-user'],
#                'GitToken': service['git']['github-token'],
#            }
#        ))

    return template


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('location', type=str)
    parser.add_argument('--format', default='yaml', choices=['yaml', 'json'])

    group = parser.add_mutually_exclusive_group(required=True)

    group.add_argument(
        '--meta-git-repo',
        action='store_const', const=meta_git_repo, dest='func',
        help='indicates location is a url of a meta git repo',
    )

    group.add_argument(
        '--services-file',
        action='store_const', const=services_file, dest='func',
        help='indicates location is a path of a sierra config file',
    )

    if not sys.argv[1:]:
        parser.print_help()
        parser.exit()

    args = parser.parse_args()

    services = args.func(args.location)
    template = build_template(services)

    if args.format == 'json':
        result = template.to_json()
    else:
        result = template.to_yaml()

    print(result)


if __name__ == '__main__':
    main()
