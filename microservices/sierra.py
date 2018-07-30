#!/usr/bin/env python3

"""Generate a CloudFormation template for microservices.

"""

import argparse
import sys
import troposphere.cloudformation as cf
from troposphere import Sub
from troposphere import Parameter, Template


S3_DOMAIN = 's3.amazonaws.com'


def meta_git_repo(url):
    """Creates a list of services from a meta git repository."""
    print('Currently unsupported')
    sys.exit(0)


def services_file(path):
    """Creates a list of services from a configuration file."""
    return []


def build_template(services):
    template = Template()

    bucket = template.add_parameter(Parameter(
        'TemplateBucket',
        Description='The S3 bucket containing all of the templates.',
        Type='String',
    ))

    def template_url(name):
        return Sub(f'https://{S3_DOMAIN}/${{{bucket.title}}}/templates/{name}')

    template.add_resource(cf.Stack(
        'Network',
        TemplateURL=template_url('network.yml'),
    ))

    template.add_resource(cf.Stack(
        'Cluster',
        TemplateURL=template_url('ecs-cluster.yml'),
        Parameters={
            'InstanceType': 't2.micro',
        }
    ))

    template.add_resource(cf.Stack(
        'LoadBalancer',
        TemplateURL=template_url('load-balancer.yml'),
    ))

    return template


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('location', type=str)
    parser.add_argument('--format', default='json', choices=['json', 'yaml'])

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
