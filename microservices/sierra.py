#!/usr/bin/env python3

import argparse
import json
import sys
import troposphere.cloudformation as cf
from troposphere import Parameter, Ref, Template


def meta_git_repo(url):
    """Creates a list of services from a meta git repository."""
    print('Currently unsupported')
    sys.exit(0)
    

def services_file(path):
    """Creates a list of services from a configuration file."""
    return []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('location', type=str)

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        '--meta-git-repo',
        action='store_const', const=meta_git_repo, dest='func',
        help='Indicates location is a URL of a valid meta Git repository.',
    )
    group.add_argument(
        '--services-file',
        action='store_const', const=services_file, dest='func',
        help='Indicates location is a local file path of a Sierra config file.',
    )

    args = parser.parse_args()

    services = args.func(args.location)

    # start of template generation

    template = Template()

    bucket = template.add_parameter(Parameter(
        'TemplateBucket',
        Description='The S3 bucket containing all of the templates.',
        Type='String',
    ))

    cluster = template.add_resource(cf.Stack(
        'Cluster',
        TemplateURL='https://s3.amazonaws.com/${TemplateBucket}/templates/ecs-cluster.yaml',
        Parameters={
            'InstanceType': '',
        }
    ))

    print(template.to_json())


if __name__ == '__main__':
    main()
