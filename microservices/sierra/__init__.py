import awacs.codebuild
import awacs.ecs
import awacs.iam
import awacs.logs
import awacs.s3
import awacs.ssm
import awacs.sts
import troposphere.ecs

from awacs.aws import Allow, PolicyDocument, Statement, Principal
from troposphere import Base64, GetAZs, GetAtt, Ref, Select, Sub, Tags
from troposphere import Parameter, Template
from troposphere.autoscaling import AutoScalingGroup, LaunchConfiguration
from troposphere.codebuild import Artifacts, Environment, Project, Source
from troposphere.codepipeline import (
    Actions, ActionTypeId, ArtifactStore, InputArtifacts,
    OutputArtifacts, Pipeline, Stages)
from troposphere.ec2 import (
    InternetGateway, Route, RouteTable, SecurityGroup, SecurityGroupRule,
    Subnet, SubnetRouteTableAssociation, VPC, VPCGatewayAttachment)
from troposphere.ecs import (
    Cluster, ContainerDefinition, Service, TaskDefinition, PortMapping)
from troposphere.elasticloadbalancingv2 import (
    Action, Listener, LoadBalancer, TargetGroup)
from troposphere.policies import (
    CreationPolicy, UpdatePolicy, ResourceSignal, AutoScalingRollingUpdate)
from troposphere.iam import InstanceProfile, Policy, Role
from troposphere.s3 import Bucket

from .utils import AttrDict
from .webhook import AuthenticationConfiguration, FilterRule, Webhook


ELB_NAME = 'ElbLoadBalancer'
DEFAULTS = AttrDict({
    'container': AttrDict({
        'count': 1,
        'cpu': 128,
        'memory': 256,
    }),
    'pipeline': AttrDict({
        'enable': False,
    }),
})


def parse_sierrafile(raw_sierrafile):
    """Creates a list of services from a configuration file."""

    def update(old, new):
        for k, v in new.items():
            if isinstance(v, dict):
                old[k] = update(old.get(k, AttrDict()), v)
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
        if 'pipeline' in service:
            service.pipeline.enable = True

        update(service, defaults)
        update(service, DEFAULTS)

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
                    'ImageId',
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

    template.add_version('2010-09-09')

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
            Default=2,
        )),
        instance_type=template.add_parameter(Parameter(
            'InstanceType',
            Type='String',
            Default='t2.medium'
        )),
        key_name=template.add_parameter(Parameter(
            'KeyName',
            Type='AWS::EC2::KeyPair::KeyName',
        )),
        image_id=template.add_parameter(Parameter(
            'ImageId',
            Type='AWS::SSM::Parameter::Value<AWS::EC2::Image::Id>',
            Default=(
                '/aws/service/ecs/optimized-ami'
                '/amazon-linux/recommended/image_id'
            ),
            Description=(
              'An SSM parameter that resolves to a valid AMI ID.'
              ' This is the AMI that will be used to create ECS hosts.'
              ' The default is the current recommended ECS-optimized AMI.'
            )
        )),

        # Other Parameters

        github_token=template.add_parameter(Parameter(
            'GitHubToken',
            Type='String',
            NoEcho=True,
        )),
    )

    # Environment Variable Parameters

    for env_var_param, env_var_name in sierrafile.extra_params:
        template.add_parameter(Parameter(
            env_var_param,
            Type='String',
            NoEcho=True,
        ))

    # Resource Declarations

    # # Network

    network_vpc = template.add_resource(VPC(
        'NetworkVpc',
        CidrBlock=Ref(parameters.vpc_cidr),
        Tags=Tags(Name=Ref('AWS::StackName')),
    ))

    network_ig = template.add_resource(InternetGateway(
        'NetworkInternetGateway',
        Tags=Tags(Name=Ref('AWS::StackName')),
    ))

    template.add_resource(VPCGatewayAttachment(
        'NetworkInternetGatewayAttachment',
        InternetGatewayId=Ref(network_ig),
        VpcId=Ref(network_vpc),
    ))

    route_table = template.add_resource(RouteTable(
        'NetworkRouteTable',
        VpcId=Ref(network_vpc),
        Tags=Tags(Name=Ref('AWS::StackName')),
    ))

    template.add_resource(Route(
        'NetworkDefaultRoute',
        RouteTableId=Ref(route_table),
        DestinationCidrBlock='0.0.0.0/0',
        GatewayId=Ref(network_ig),
    ))

    subnet1 = template.add_resource(Subnet(
        'NetworkSubnet1',
        VpcId=Ref(network_vpc),
        AvailabilityZone=Select(0, GetAZs()),
        MapPublicIpOnLaunch=True,
        CidrBlock=Ref(parameters.subnet1_cidr),
        Tags=Tags(Name=Sub('${AWS::StackName} (Public)')),
    ))

    subnet2 = template.add_resource(Subnet(
        'NetworkSubnet2',
        VpcId=Ref(network_vpc),
        AvailabilityZone=Select(1, GetAZs()),
        MapPublicIpOnLaunch=True,
        CidrBlock=Ref(parameters.subnet2_cidr),
        Tags=Tags(Name=Sub('${AWS::StackName} (Public)')),
    ))

    template.add_resource(SubnetRouteTableAssociation(
        'NetworkSubnet1RouteTableAssociation',
        RouteTableId=Ref(route_table),
        SubnetId=Ref(subnet1),
    ))

    template.add_resource(SubnetRouteTableAssociation(
        'NetworkSubnet2RouteTableAssociation',
        RouteTableId=Ref(route_table),
        SubnetId=Ref(subnet2),
    ))

    elb = template.add_resource(LoadBalancer(
        ELB_NAME,
        Name=Sub('${AWS::StackName}-elb'),
        Type='network',
        Subnets=[Ref(subnet1), Ref(subnet2)],
    ))

    # # Cluster

    ecs_host_role = template.add_resource(Role(
        'EcsHostRole',
        AssumeRolePolicyDocument=PolicyDocument(
            Statement=[Statement(
                Effect=Allow,
                Principal=Principal('Service', 'ec2.amazonaws.com'),
                Action=[awacs.sts.AssumeRole]
            )],
        ),
        ManagedPolicyArns=[
            'arn:aws:iam::aws:policy/'
            'service-role/AmazonEC2ContainerServiceforEC2Role'
        ]
    ))

    ecs_host_profile = template.add_resource(InstanceProfile(
        'EcsHostInstanceProfile',
        Roles=[Ref(ecs_host_role)]
    ))

    ecs_host_sg = template.add_resource(SecurityGroup(
        'EcsHostSecurityGroup',
        GroupDescription=Sub('${AWS::StackName}-hosts'),
        VpcId=Ref(network_vpc),
        SecurityGroupIngress=[SecurityGroupRule(
            CidrIp='0.0.0.0/0',
            IpProtocol='-1'
        )]
    ))

    cluster = template.add_resource(Cluster(
        'EcsCluster',
        ClusterName=Ref('AWS::StackName')
    ))

    autoscaling_name = 'EcsHostAutoScalingGroup'
    launch_conf_name = 'EcsHostLaunchConfiguration'

    launch_conf = template.add_resource(LaunchConfiguration(
        launch_conf_name,
        ImageId=Ref(parameters.image_id),
        InstanceType=Ref(parameters.instance_type),
        IamInstanceProfile=Ref(ecs_host_profile),
        KeyName=Ref(parameters.key_name),
        SecurityGroups=[Ref(ecs_host_sg)],
        UserData=Base64(Sub(
            '#!/bin/bash\n'
            'yum install -y aws-cfn-bootstrap\n'
            '/opt/aws/bin/cfn-init -v'
            ' --region ${AWS::Region}'
            ' --stack ${AWS::StackName}'
            f' --resource {launch_conf_name}\n'
            '/opt/aws/bin/cfn-signal -e $?'
            ' --region ${AWS::Region}'
            ' --stack ${AWS::StackName}'
            f' --resource {autoscaling_name}\n'
        )),
        Metadata={
            'AWS::CloudFormation::Init': {
                'config': {
                    'commands': {
                        '01_add_instance_to_cluster': {
                            'command': Sub(
                                f'echo ECS_CLUSTER=${{{cluster.title}}}'
                                f' > /etc/ecs/ecs.config'
                            ),
                        }
                    },
                    'files': {
                        '/etc/cfn/cfn-hup.conf': {
                            'mode': 0o400,
                            'owner': 'root',
                            'group': 'root',
                            'content': Sub(
                                '[main]\n'
                                'stack=${AWS::StackId}\n'
                                'region=${AWS::Region}\n'
                            ),
                        },
                        '/etc/cfn/hooks.d/cfn-auto-reloader.conf': {
                            'content': Sub(
                                '[cfn-auto-reloader-hook]\n'
                                'triggers=post.update\n'
                                'path=Resources.ContainerInstances.Metadata'
                                '.AWS::CloudFormation::Init\n'
                                'action=/opt/aws/bin/cfn-init -v'
                                ' --region ${AWS::Region}'
                                ' --stack ${AWS::StackName}'
                                f' --resource {launch_conf_name}\n'
                            ),
                        },
                    },
                    'services': {
                        'sysvinit': {
                            'cfn-hup': {
                                'enabled': True,
                                'ensureRunning': True,
                                'files': [
                                    '/etc/cfn/cfn-hup.conf',
                                    '/etc/cfn/hooks.d/cfn-auto-reloader.conf'
                                ]
                            }
                        }
                    }
                }
            }
        }
    ))

    autoscaling_group = template.add_resource(AutoScalingGroup(
        autoscaling_name,
        VPCZoneIdentifier=[Ref(subnet1), Ref(subnet2)],
        LaunchConfigurationName=Ref(launch_conf),
        DesiredCapacity=Ref(parameters.cluster_size),
        MinSize=Ref(parameters.cluster_size),
        MaxSize=Ref(parameters.cluster_size),
        Tags=[{
            'Key': 'Name',
            'Value': Sub('${AWS::StackName} - ECS Host'),
            'PropagateAtLaunch': True,
        }],
        CreationPolicy=CreationPolicy(
            ResourceSignal=ResourceSignal(Timeout='PT15M'),
        ),
        UpdatePolicy=UpdatePolicy(
            AutoScalingRollingUpdate=AutoScalingRollingUpdate(
                MinInstancesInService=1,
                MaxBatchSize=1,
                PauseTime='PT5M',
                WaitOnResourceSignals=True,
            ),
        ),
    ))

    # # Services

    task_role = template.add_resource(Role(
        'TaskExecutionRole',
        AssumeRolePolicyDocument=PolicyDocument(
            Statement=[Statement(
                Effect=Allow,
                Principal=Principal('Service', 'ecs-tasks.amazonaws.com'),
                Action=[awacs.sts.AssumeRole],
            )],
        ),
        ManagedPolicyArns=[
            'arn:aws:iam::aws:policy/'
            'service-role/AmazonECSTaskExecutionRolePolicy'
        ],
    ))

    artifact_bucket = template.add_resource(Bucket(
        'ArtifactBucket',
        DeletionPolicy='Retain'
    ))

    codebuild_role = template.add_resource(Role(
        'CodeBuildServiceRole',
        Path='/',
        AssumeRolePolicyDocument=PolicyDocument(
            Version='2012-10-17',
            Statement=[
                Statement(
                    Effect=Allow,
                    Principal=Principal(
                        'Service', 'codebuild.amazonaws.com'
                    ),
                    Action=[
                        awacs.sts.AssumeRole,
                    ],
                ),
            ],
        ),
        Policies=[Policy(
            PolicyName='root',
            PolicyDocument=PolicyDocument(
                Version='2012-10-17',
                Statement=[
                    Statement(
                        Resource=['*'],
                        Effect=Allow,
                        Action=[
                            awacs.ssm.GetParameters,
                        ],
                    ),
                    Statement(
                        Resource=['*'],
                        Effect=Allow,
                        Action=[
                            awacs.s3.GetObject,
                            awacs.s3.PutObject,
                            awacs.s3.GetObjectVersion,
                        ],
                    ),
                    Statement(
                        Resource=['*'],
                        Effect=Allow,
                        Action=[
                            awacs.logs.CreateLogGroup,
                            awacs.logs.CreateLogStream,
                            awacs.logs.PutLogEvents,
                        ],
                    ),
                ],
            ),
        )],
    ))

    codepipeline_role = template.add_resource(Role(
        'CodePipelineServiceRole',
        Path='/',
        AssumeRolePolicyDocument=PolicyDocument(
            Version='2012-10-17',
            Statement=[
                Statement(
                    Effect=Allow,
                    Principal=Principal(
                        'Service', 'codepipeline.amazonaws.com'
                    ),
                    Action=[
                        awacs.sts.AssumeRole,
                    ],
                ),
            ],
        ),
        Policies=[Policy(
            PolicyName='root',
            PolicyDocument=PolicyDocument(
                Version='2012-10-17',
                Statement=[
                    Statement(
                        Resource=[
                            Sub(f'${{{artifact_bucket.title}.Arn}}/*')
                        ],
                        Effect=Allow,
                        Action=[
                            awacs.s3.GetBucketVersioning,
                            awacs.s3.GetObject,
                            awacs.s3.GetObjectVersion,
                            awacs.s3.PutObject,
                        ],
                    ),
                    Statement(
                        Resource=['*'],
                        Effect=Allow,
                        Action=[
                            awacs.ecs.DescribeServices,
                            awacs.ecs.DescribeTaskDefinition,
                            awacs.ecs.DescribeTasks,
                            awacs.ecs.ListTasks,
                            awacs.ecs.RegisterTaskDefinition,
                            awacs.ecs.UpdateService,
                            awacs.codebuild.StartBuild,
                            awacs.codebuild.BatchGetBuilds,
                            awacs.iam.PassRole,
                        ],
                    ),
                ],
            ),
        )],
    ))

    for name, settings in sierrafile.services.items():
        task_definition = template.add_resource(TaskDefinition(
            f'{name}TaskDefinition',
            RequiresCompatibilities=['EC2'],
            Cpu=str(settings.container.cpu),
            Memory=str(settings.container.memory),
            NetworkMode='bridge',
            ExecutionRoleArn=Ref(task_role.title),
            ContainerDefinitions=[
                ContainerDefinition(
                    Name=f'{name}',
                    Image=settings.container.image,
                    Memory=str(settings.container.memory),
                    Essential=True,
                    PortMappings=[
                        PortMapping(
                            ContainerPort=settings.container.port,
                            Protocol='tcp',
                        ),
                    ],
                    Environment=[
                        troposphere.ecs.Environment(Name=k, Value=v)
                        for k, v in sierrafile.env_vars.items()
                        if k in settings.get('environment', [])
                    ],
                ),
            ],
        ))

        target_group = template.add_resource(TargetGroup(
            f'{name}TargetGroup',
            Name=f'tg-{name}'[:32],
            Port=settings.container.port,
            Protocol='TCP',
            VpcId=Ref(network_vpc),
        ))

        listener = template.add_resource(Listener(
            f'{name}ElbListener',
            LoadBalancerArn=Ref(elb),
            Port=settings.container.port,
            Protocol='TCP',
            DefaultActions=[
                Action(TargetGroupArn=Ref(target_group), Type='forward')
            ],
        ))

        service = template.add_resource(Service(
            f'{name}Service',
            Cluster=Ref(cluster),
            ServiceName=f'{name}-service',
            DependsOn=[autoscaling_group.title, listener.title],
            DesiredCount=settings.container.count,
            TaskDefinition=Ref(task_definition),
            LaunchType='EC2',
            LoadBalancers=[
                troposphere.ecs.LoadBalancer(
                    ContainerName=f'{name}',
                    ContainerPort=settings.container.port,
                    TargetGroupArn=Ref(target_group),
                ),
            ],
        ))

        if settings.pipeline.enable:
            project = template.add_resource(Project(
                f'{name}CodeBuildProject',
                Name=f'{name}Build',
                ServiceRole=Ref(codebuild_role),
                Artifacts=Artifacts(Type='CODEPIPELINE'),
                Source=Source(Type='CODEPIPELINE'),
                Environment=Environment(
                    ComputeType='BUILD_GENERAL1_SMALL',
                    Image='aws/codebuild/docker:17.09.0',
                    Type='LINUX_CONTAINER',
                ),
            ))

            pipeline = template.add_resource(Pipeline(
                f'{name}Pipeline',
                RoleArn=GetAtt(codepipeline_role, 'Arn'),
                ArtifactStore=ArtifactStore(
                    Type='S3',
                    Location=Ref(artifact_bucket),
                ),
                Stages=[
                    Stages(
                        Name='Source',
                        Actions=[Actions(
                            Name='Source',
                            ActionTypeId=ActionTypeId(
                                Category='Source',
                                Owner='ThirdParty',
                                Version='1',
                                Provider='GitHub',
                            ),
                            OutputArtifacts=[
                                OutputArtifacts(Name=f'{name}Source'),
                            ],
                            RunOrder='1',
                            Configuration={
                                'Owner': settings.pipeline.user,
                                'Repo': settings.pipeline.repo,
                                'Branch': settings.pipeline.branch,
                                'OAuthToken': Ref(parameters.github_token),
                            },
                        )],
                    ),
                    Stages(
                        Name='Build',
                        Actions=[Actions(
                            Name='Build',
                            ActionTypeId=ActionTypeId(
                                Category='Build',
                                Owner='AWS',
                                Version='1',
                                Provider='CodeBuild',
                            ),
                            InputArtifacts=[
                                InputArtifacts(Name=f'{name}Source'),
                            ],
                            OutputArtifacts=[
                                OutputArtifacts(Name=f'{name}Build'),
                            ],
                            RunOrder='1',
                            Configuration={
                                'ProjectName': Ref(project),
                            },
                        )],
                    ),
                    Stages(
                        Name='Deploy',
                        Actions=[Actions(
                            Name='Deploy',
                            ActionTypeId=ActionTypeId(
                                Category='Deploy',
                                Owner='AWS',
                                Version='1',
                                Provider='ECS',
                            ),
                            InputArtifacts=[
                                InputArtifacts(Name=f'{name}Build')
                            ],
                            RunOrder='1',
                            Configuration={
                                'ClusterName': Ref(cluster),
                                'ServiceName': Ref(service),
                                'FileName': 'image.json',
                            },
                        )],
                    ),
                ],
            ))

            template.add_resource(Webhook(
                f'{name}CodePipelineWebhook',
                Name=f'{name}-webhook',
                Authentication='GITHUB_HMAC',
                AuthenticationConfiguration=AuthenticationConfiguration(
                    SecretToken=Ref(parameters.github_token),
                ),
                Filters=[FilterRule(
                    JsonPath='$.ref',
                    MatchEquals=f'refs/heads/{settings.pipeline.branch}'
                )],
                TargetAction='Source',
                TargetPipeline=Ref(pipeline),
                TargetPipelineVersion=1,
                RegisterWithThirdParty=True,
            ))

    return template
