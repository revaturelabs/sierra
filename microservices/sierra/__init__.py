from troposphere import GetAtt, Ref, Sub
from troposphere import Parameter, Template
from troposphere.cloudformation import Stack

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
    params, env_vars, endpoints = [], {}, {}

    for name, value in environment.items():
        if value is None:
            params.append(name)
        elif isinstance(value, str):
            if '{ENDPOINT}' in value:
                endpoints[name] = value
            else:
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
        'endpoints': endpoints,
        'env_vars': env_vars,
        'params': params,
        'services': services,
    }


def parameter_groups(groups):
    return [
        {'Label': {'default': name}, 'Parameters': params}
        for name, params in groups.items()
    ]


def build_template(sierrafile):
    template = Template()

    template.add_metadata({
        'AWS::CloudFormation::Interface': {
            'ParameterGroups': parameter_groups({
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
            }),
        }
    })

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

    elb = template.add_resource(Stack(
        'ELB',
        TemplateURL=template_url('load-balancer.yml'),
        Parameters={
            'Prefix': Ref('AWS::StackName'),
            'Subnets': network.subnets,
            'VPC': network.vpc,
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
