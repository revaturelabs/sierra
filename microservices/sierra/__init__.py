from troposphere import GetAtt, Ref, Sub
from troposphere import Parameter, Template
from troposphere.cloudformation import Stack
from troposphere.ec2 import SecurityGroup, SecurityGroupRule
from troposphere.elasticloadbalancingv2 import (
    Action, Listener, LoadBalancer, TargetGroup)

import sierra.network


S3_DOMAIN = 's3.amazonaws.com'


def parse_sierrafile(raw_sierrafile):
    """Creates a list of services from a configuration file."""

    def update(old, new):
        for k, v in new.items():
            if isinstance(v, dict):
                old[k] = update(old.get(k, {}), v)
            else:
                old.setdefault(k, v)
        return old

    environment = raw_sierrafile.get('environment', {})
    params, env_vars = [], {}

    for name, value in environment.items():
        if value is None:
            identifier = 'EnvironmentVariable' + str(len(params))
            params.append((identifier, name))
            env_vars[name] = Ref(identifier)
        elif isinstance(value, str):
            if '{ENDPOINT}' in value:
                value = Sub(value.format(ENDPOINT='${LoadBalancer.DNSName}'))
            env_vars[name] = value
        else:
            raise TypeError()

    defaults = raw_sierrafile.get('default', {})
    services = raw_sierrafile['services']

    for name, service in services.items():
        update(service, defaults)
        for env_var in service.get('environment', []):
            if env_var not in environment:
                raise ValueError()

    return {
        'env_vars': env_vars,
        'params': params,
        'services': services,
    }


def build_interface(env_vars):

    def clean(d):
        return {k: v for k, v in d.items() if v}

    def parameter_groups(groups):
        return [
            {'Label': {'default': name}, 'Parameters': params}
            for name, params in groups.items()
        ]

    return {
        'AWS::CloudFormation::Interface': clean({
            'ParameterGroups': parameter_groups(clean({
                'Network Configuration': [
                    'VpcCidr',
                    'Subnet1Cidr',
                    'Subnet2Cidr',
                ],
                'ECS Configuration': [
                    'InstanceType',
                    'ClusterSize',
                    'KeyName',
                ],
                'Environment Variables': [
                    k for k, v in env_vars
                ],
            })),
            'ParameterLabels': {
                k: {'default': v}
                for k, v in env_vars
            },
        }),
    }


def build_template(sierrafile):
    template = Template()

    template.add_metadata(build_interface(sierrafile['params']))

    # Network Parameters

    vpc_cidr = template.add_parameter(Parameter(
        'VpcCidr',
        Type='String',
        Default='192.172.0.0/16',
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

    # ECS Parameters

    cluster_size = template.add_parameter(Parameter(
        'ClusterSize',
        Type='Number',
        Default=1
    ))

    instance_type = template.add_parameter(Parameter(
        'InstanceType',
        Type='String',
        Default='t2.small'
    ))

    key_name = template.add_parameter(Parameter(
        'KeyName',
        Type='AWS::EC2::KeyPair::KeyName',
    ))

    # Environment Variable Parameters

    for env_var_param, env_var_name in sierrafile['params']:
        template.add_parameter(Parameter(
            env_var_param,
            Type='String',
            NoEcho=True,
        ))

    # Other Parameters

    bucket = template.add_parameter(Parameter(
        'TemplateBucket',
        Description='The S3 bucket containing all of the templates.',
        Type='String',
        Default='templates.sierra.goeppes',
    ))

    def template_url(name):
        return Sub(f'https://{S3_DOMAIN}/${{{bucket.title}}}/templates/{name}')

    network = sierra.network.inject(
        template,
        prefix='AWS::StackName',
        vpc_cidr=vpc_cidr,
        subnet1_cidr=subnet1_cidr,
        subnet2_cidr=subnet2_cidr,
    )

    # Elastic Load Balancer

    security_group = template.add_resource(SecurityGroup(
        'SecurityGroup',
        GroupName=Sub('${AWS::StackName}-elb-sg'),
        GroupDescription=Sub('${AWS::StackName}-elb-sg'),
        VpcId=network.vpc,
        SecurityGroupIngress=[
            SecurityGroupRule(
                CidrIp='0.0.0.0/0',
                IpProtocol='tcp',
                FromPort=80,
                ToPort=80,
            ),
        ],
    ))

    target_group = template.add_resource(TargetGroup(
        'DefaultTargetGroup',
        Name=Sub('${AWS::StackName}-default'),
        Port=80,
        Protocol='HTTP',
        TargetType='instance',
        VpcId=network.vpc,
    ))

    elb = template.add_resource(LoadBalancer(
        'LoadBalancer',
        Name=Sub('${AWS::StackName}-elb'),
        Subnets=network.subnets,
        SecurityGroups=[Ref(security_group)],
    ))

    template.add_resource(Listener(
        'LoadBalancerListener',
        LoadBalancerArn=Ref(elb),
        Port=80,
        Protocol='HTTP',
        DefaultActions=[
            Action(
                TargetGroupArn=Ref(target_group),
                Type='forward',
            )
        ],
    ))

    # Resources

    cluster = template.add_resource(Stack(
        'Cluster',
        TemplateURL=template_url('ecs-cluster.yml'),
        Parameters={
            'ClusterSize': Ref(cluster_size),
            'InstanceType': Ref(instance_type),
            'KeyName': Ref(key_name),
            'SourceSecurityGroup': Ref(security_group),
            'Subnets': network.subnets,
            'VPC': network.vpc,
        }
    ))

    for name, service in sierrafile['services'].items():
        template.add_resource(Stack(
            name + 'Service',
            TemplateURL=template_url('ecs-service.yml'),
            Parameters={
                'ContainerName': name + '-container',
                'ContainerImage': service['docker']['image'],
                'ContainerPort': service['docker']['port'],
                'ServiceName': name + '-service',
                'Cluster': GetAtt(cluster, 'Outputs.ClusterName'),
                'TargetGroup': Ref(target_group),
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
