#!/usr/bin/env python3

"""Generate a CloudFormation template for microservices.

By default it uses the Sierrafile in the current working directory.

"""

import argparse
import json
import sys

from troposphere import GetAtt, Ref, Sub
from troposphere import Parameter, Template
from troposphere.cloudformation import Stack


S3_DOMAIN = 's3.amazonaws.com'


def parse_services(parser, filename):
    """Creates a list of services from a configuration file."""

    def update(old, new):
        for k, v in new.items():
            if isinstance(v, dict):
                old[k] = update(old.get(k, {}), v)
            else:
                old.setdefault(k, v)

    try:
        with open(filename) as f:
            config = json.load(f)
    except FileNotFoundError:
        parser.print_help()
        parser.exit()

    default = config['default']
    del config['default']

    for service in config['services']:
        update(service, default)

    return config['services']


def build_template(services):
    template = Template()

    template.add_metadata({
        'AWS::CloudFormation::Interface': {
            'ParameterGroups': [
                {
                    'Label': {'default': 'Network Configuration'},
                    'Parameters': [
                        'VpcCidr',
                        'Subnet1Cidr',
                        'Subnet2Cidr',
                    ],
                },
                {
                    'Label': {'default': 'ECS Configuration'},
                    'Parameters': [
                        'InstanceType',
                        'ClusterSize',
                        'KeyName',
                    ],
                },
            ],
        }
    })

    cluster_size = template.add_parameter(Parameter(
        'ClusterSize',
        Type='Number',
        Default=1
    ))

    instance_type = template.add_parameter(Parameter(
        'InstanceType',
        Type='String',
        Default='t2.micro'
    ))

    key_name = template.add_parameter(Parameter(
        'KeyName',
        Type='AWS::EC2::KeyPair::KeyName',
    ))

    subnet1_cidr = template.add_parameter(Parameter(
        'Subnet1Cidr',
        Type='String',
        Default='192.172.1.0/24',
    ))

    subnet2_cidr = template.add_parameter(Parameter(
        'Subnet2Cidr',
        Type='String',
        Default='192.172.2.0/24',
    ))

    bucket = template.add_parameter(Parameter(
        'TemplateBucket',
        Description='The S3 bucket containing all of the templates.',
        Type='String',
        Default='templates.sierra.goeppes',
    ))

    vpc_cidr = template.add_parameter(Parameter(
        'VpcCidr',
        Type='String',
        Default='192.172.0.0/16',
    ))

    def template_url(name):
        return Sub(f'https://{S3_DOMAIN}/${{{bucket.title}}}/templates/{name}')

    network = template.add_resource(Stack(
        'Network',
        TemplateURL=template_url('network.yml'),
        Parameters={
            'Prefix': Ref('AWS::StackName'),
            'VpcCidr': Ref(vpc_cidr),
            'Subnet1Cidr': Ref(subnet1_cidr),
            'Subnet2Cidr': Ref(subnet2_cidr),
        }
    ))

    elb = template.add_resource(Stack(
        'ELB',
        TemplateURL=template_url('load-balancer.yml'),
        Parameters={
            'Prefix': Ref('AWS::StackName'),
            'Subnets': GetAtt(network, 'Outputs.Subnets'),
            'VPC': GetAtt(network, 'Outputs.VpcId'),
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
            'Subnets': GetAtt(network, 'Outputs.Subnets'),
            'VPC': GetAtt(network, 'Outputs.VpcId'),
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
    parser.add_argument('-f', '--file', type=str,
                        default='Sierrafile')
    parser.add_argument('-o', '--out', type=argparse.FileType('w'),
                        default=sys.stdout)
    parser.add_argument('--format', choices=['yaml', 'json'],
                        default='yaml')

    args = parser.parse_args()

    services = parse_services(parser, args.file)
    template = build_template(services)

    if args.format == 'json':
        result = template.to_json()
    else:
        result = template.to_yaml()

    print(result, file=args.out)


if __name__ == '__main__':
    main()
