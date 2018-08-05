from troposphere import GetAtt, Ref, Sub
from troposphere import Parameter, Template
from troposphere.cloudformation import Stack

import sierra.elb
import sierra.network
import sierra.pipeline

from .elb import ELB_NAME
from .utils import AttrDict


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
    extra_params, env_vars = [], {}

    for name, value in environment.items():
        if value is None:
            identifier = 'EnvironmentVariable' + str(len(extra_params))
            env_vars[name] = Ref(identifier)
            extra_params.append((identifier, name))
        elif isinstance(value, str):
            if '{ENDPOINT}' in value:
                value = Sub(value.format(ENDPOINT=f'${{{ELB_NAME}.DNSName}}'))
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

    return AttrDict(
        extra_params=extra_params,
        env_vars=env_vars,
        services=services,
    )


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

    template.add_metadata(build_interface(sierrafile.extra_params))

    parameters = AttrDict(

        # Network Parameters

        vpc_cidr=template.add_parameter(Parameter(
            'VpcCidr',
            Type='String',
            Default='192.172.0.0/16',
        )),
        subnet1_cidr=template.add_parameter(Parameter(
            'Subnet1Cidr',
            Type='String',
            Default='192.172.1.0/24',
        )),
        subnet2_cidr=template.add_parameter(Parameter(
            'Subnet2Cidr',
            Type='String',
            Default='192.172.2.0/24',
        )),

        # ECS Parameters

        cluster_size=template.add_parameter(Parameter(
            'ClusterSize',
            Type='Number',
            Default=1,
        )),
        instance_type=template.add_parameter(Parameter(
            'InstanceType',
            Type='String',
            Default='t2.small'
        )),
        key_name=template.add_parameter(Parameter(
            'KeyName',
            Type='AWS::EC2::KeyPair::KeyName',
        )),

        # Other Parameters

        github_token=template.add_parameter(Parameter(
            'GitHubToken',
            Type='String',
            NoEcho=True,
        )),

        bucket=template.add_parameter(Parameter(
            'TemplateBucket',
            Description='The S3 bucket containing all of the templates.',
            Type='String',
            Default='templates.sierra.goeppes',
        )),
    )

    # Environment Variable Parameters

    for env_var_param, env_var_name in sierrafile.extra_params:
        template.add_parameter(Parameter(
            env_var_param,
            Type='String',
            NoEcho=True,
        ))

    def template_url(name):
        return Sub(
            f'https://s3.amazonaws.com/'
            f'${{{parameters.bucket.title}}}/'
            f'templates/{name}'
        )

    # Resource Declarations

    network = sierra.network.inject(
        template,
        vpc_cidr=Ref(parameters.vpc_cidr),
        subnet1_cidr=Ref(parameters.subnet1_cidr),
        subnet2_cidr=Ref(parameters.subnet2_cidr),
    )

    elb = sierra.elb.inject(template, network)

    # Resources

    cluster = template.add_resource(Stack(
        'Cluster',
        TemplateURL=template_url('ecs-cluster.yml'),
        Parameters={
            'ClusterSize': Ref(parameters.cluster_size),
            'InstanceType': Ref(parameters.instance_type),
            'KeyName': Ref(parameters.key_name),
            'SourceSecurityGroup': elb.security_group,
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
                'ContainerImage': service.container.image,
                'ContainerPort': service.container.port,
                'ServiceName': name + '-service',
                'Cluster': GetAtt(cluster, 'Outputs.ClusterName'),
                'TargetGroup': elb.target_group,
            }
        ))

#        template.add_resource(Stack(
#            service['name'] + 'Pipeline',
#            TemplateURL=template_url('pipeline.yml'),
#            Parameters={
#                'GitUser': service.pipeline.user,
#                'GitRepo': service.pipeline.repo,
#                'GitBranch': service.pipeline.branch,
#                'GitToken': Ref(parameters.github_token),
#            }
#        ))

    return template
