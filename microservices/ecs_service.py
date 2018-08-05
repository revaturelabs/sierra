#!/usr/bin/env python3

from troposphere import Parameter, Ref, Template
from troposphere.ecs import Cluster, Service, TaskDefinition, ContainerDefinition, NetworkConfiguration, AwsvpcConfiguration, PortMapping, LoadBalancer, Environment
from troposphere.iam import Role, Policy
from awacs.aws import Allow, Statement, Principal, Policy
from awacs.sts import AssumeRole



def ecs_service(template, env_var):
    ''' Pass in a template to which these resources should be added, and a dictionary of environment variables.
     If the value of a item in the dictionary is null the key will get added as a parameter to the template'''

    t = template

    #making a list of the environement variables to add to the container definition
    list_of_env_var = []
    for key, value in env_var.items():
        if value == None:
            t.add_parameter(Parameter(str(key), Type ='String'))
        else:
            list_of_env_var.append(Environment(Name=str(key), Value=str(value)))




    #t.add_version('2010-09-09')
    container_name = t.add_parameter(Parameter(
        'ContainerName',
        Type='String',
    ))

    container_image = t.add_parameter( Parameter(
        'ContainerImage',
        Type='String',
    ))

    container_port = t.add_parameter(Parameter(
        'ContainerPort',
        Type='Number',
    ))

    service_name= t.add_parameter(Parameter(
        'ServiceName',
        Type='String',
    ))

    cluster = t.add_parameter(Parameter(
        'Cluster',
        Type='String',
    ))


    target_group = t.add_parameter(Parameter(
        'TargetGroup',
        Type='String',
    ))



    task_role = Role(
        "TaskExecutionRole",
        AssumeRolePolicyDocument=Policy(
            Statement=[
                Statement(
                    Effect=Allow,
                    Action=[AssumeRole],
                    Principal=Principal("Service", ["ecs-tasks.amazonaws"])
                )
            ]
        ),
        ManagedPolicyArns = ['arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy']
    )
    t.add_resource(task_role)




    #cpu and memory might have to be integers
    task_definition = TaskDefinition(
        'TaskDefinition',
        RequiresCompatibilities=['EC2'],
        Cpu='128',
        Memory='256',
        NetworkMode='bridge',
        ExecutionRoleArn= Ref(task_role.title),
        ContainerDefinitions=[
            ContainerDefinition(
                Name= Ref(container_name.title),
                Image= Ref(container_image.title),
                Memory= '256',
                Essential=True,
                PortMappings=[PortMapping(ContainerPort=Ref(container_port), Protocol= 'tcp')],
                Environment = list_of_env_var
            )
        ]
    )

    t.add_resource(task_definition)


    service = Service(
        'Service',
        Cluster= Ref(cluster.title),
        ServiceName= Ref(service_name.title),
        DesiredCount=1,
        TaskDefinition=Ref(task_definition.title),
        LaunchType='EC2',
        LoadBalancers= [
            LoadBalancer(
                ContainerName= Ref(container_name.title),
                ContainerPort= Ref(container_port.title),
                TargetGroupArn= Ref(target_group.title)
            )
        ]

    )

    t.add_resource(service)

    return t.to_yaml()


temp = Template()
temp.add_version('2010-09-09')
env = {'jack': 4098, 'sape': 4139, 'null': None}

#print(type(env))
print(ecs_service(temp, env))

#print(temp.to_yaml())
