import awacs.sts
from awacs.aws import Allow, PolicyDocument, Statement, Principal

from troposphere import Ref
from troposphere.ecs import (
    ContainerDefinition, Service, TaskDefinition,
    PortMapping, LoadBalancer, Environment)
from troposphere.elasticloadbalancingv2 import Action, Listener, TargetGroup
from troposphere.iam import Role

from .utils import AttrDict


def inject(template, name, container_settings,
           cluster, elb, vpc, env_vars):
    """Pass in a template to which these resources should be added, and a
    dictionary of environment variables.
    """
    task_role = template.add_resource(Role(
        f'{name}TaskExecutionRole',
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

    task_definition = template.add_resource(TaskDefinition(
        f'{name}TaskDefinition',
        RequiresCompatibilities=['EC2'],
        Cpu=str(container_settings.cpu),
        Memory=str(container_settings.memory),
        NetworkMode='bridge',
        ExecutionRoleArn=Ref(task_role.title),
        ContainerDefinitions=[
            ContainerDefinition(
                Name=f'{name}-container',
                Image=container_settings.image,
                Memory=str(container_settings.memory),
                Essential=True,
                PortMappings=[
                    PortMapping(
                        ContainerPort=container_settings.port,
                        Protocol='tcp',
                    ),
                ],
                Environment=[
                    Environment(Name=k, Value=v)
                    for k, v in env_vars.items()
                ],
            ),
        ],
    ))

    target_group = template.add_resource(TargetGroup(
        f'{name}TargetGroup',
        Name=f'tg-{name}'[:32],
        Port=container_settings.port,
        Protocol='TCP',
        VpcId=Ref(vpc),
    ))

    listener = template.add_resource(Listener(
        f'{name}ElbListener',
        LoadBalancerArn=Ref(elb),
        Port=container_settings.port,
        Protocol='TCP',
        DefaultActions=[
            Action(TargetGroupArn=Ref(target_group), Type='forward')
        ],
    ))

    service = template.add_resource(Service(
        f'{name}Service',
        Cluster=cluster,
        ServiceName=f'{name}-service',
        DependsOn=[listener.title],
        DesiredCount=container_settings.count,
        TaskDefinition=Ref(task_definition),
        LaunchType='EC2',
        LoadBalancers=[
            LoadBalancer(
                ContainerName=f'{name}-container',
                ContainerPort=container_settings.port,
                TargetGroupArn=Ref(target_group),
            ),
        ],
    ))

    return AttrDict(
        service=service,
    )
