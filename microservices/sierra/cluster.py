import awacs.sts
from awacs.aws import Allow, PolicyDocument, Statement, Principal

from troposphere import Ref, Sub, Base64, Template
from troposphere.ec2 import SecurityGroup, SecurityGroupRule
from troposphere.autoscaling import AutoScalingGroup, LaunchConfiguration
from troposphere.ecs import Cluster
from troposphere.policies import CreationPolicy, UpdatePolicy, ResourceSignal, AutoScalingRollingUpdate
from troposphere.iam import InstanceProfile, Role


def inject(template, vpc, subnets, imageId, instanceType, keyName, clusterSize):
    
    ecsHostRole = template.add_resource(Role(
        'ECSHostRole',
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

    ecsHostInstanceProfile = template.add_resource(InstanceProfile(
        'EcsHostInstanceProfile',
        Roles=[Ref(ecsHostRole)]
    ))

    ecsHostSecurityGroup = template.add_resource(SecurityGroup(
        'EcsHostSecurityGroup',
        GroupDescription=Sub('${AWS::StackName}-hosts'),
        VpcId=Ref(vpc),
        SecurityGroupIngress=[SecurityGroupRule(
            CidrIp='0.0.0.0/0',
            IpProtocol='-1'
        )]
    ))

    cluster = template.add_resource(Cluster(
        'Cluster',
        ClusterName=Ref('AWS::StackName')
    ))

    launchConfiguration = template.add_resource(LaunchConfiguration(
        'LaunchConfiguration',
        ImageId=Ref(imageId),
        InstanceType=Ref(instanceType),
        IamInstanceProfile=Ref(ecsHostInstanceProfile),
        KeyName=Ref(keyName),
        SecurityGroups=[Ref(ecsHostSecurityGroup)],
        UserData=Base64(Sub(
            '''|
            #!/bin/bash
            yum install -y aws-cfn-bootstrap
            /opt/aws/bin/cfn-init -v --region ${AWS::Region} --stack ${AWS::StackName} --resource LaunchConfiguration
            /opt/aws/bin/cfn-signal -e $? --region ${AWS::Region} --stack ${AWS::StackName} --resource AutoScalingGroup
            '''
        )),
        Metadata={
            "config": {
                "commands": {
                    "01_add_instance_to_cluster": {
                    "command": "echo ECS_CLUSTER=${Cluster} > /etc/ecs/ecs.config"
                    }
                },
                "files": {
                    "/etc/cfn/cfn-hup.conf": {
                        "mode": 256,
                        "owner": "root",
                        "group": "root",
                        "content": "[main]\nstack=${AWS::StackId}\nregion=${AWS::Region}\n"
                    },
                    "/etc/cfn/hooks.d/cfn-auto-reloader.conf": {
                        "content": "[cfn-auto-reloader-hook]\ntriggers=post.update\npath=Resources.ContainerInstances.Metadata.AWS::CloudFormation::Init\naction=/opt/aws/bin/cfn-init -v --region ${AWS::Region} --stack ${AWS::StackName} --resource LaunchConfiguration\n"
                    }
                },
                "services": {
                    "sysvinit": {
                        "cfn-hup": {
                            "enabled": True,
                            "ensureRunning": True,
                            "files": [
                            "/etc/cfn/cfn-hup.conf",
                            "/etc/cfn/hooks.d/cfn-auto-reloader.conf"
                            ]
                        }
                    }
                }
            }
        }
    ))

    autoScalingGroup = template.add_resource(AutoScalingGroup(
        'AutoScalingGroup',
        VPCZoneIdentifier=Ref(subnets),
        LaunchConfigurationName=Ref(launchConfiguration),
        DesiredCapacity=Ref(clusterSize),
        MinSize=Ref(clusterSize),
        MaxSize=Ref(clusterSize),
        Tags=[
            {
                'Key': 'name',
                'Value': Sub('${AWS::StackName} - ECS Host'),
                'PropogateAtLaunch': True
            }
        ],
        CreationPolicy=CreationPolicy(
            ResourceSignal=ResourceSignal(Timeout='PT15M')
        ),
        UpdatePolicy=UpdatePolicy(
            AutoScalingRollingUpdate=AutoScalingRollingUpdate(
                MinInstancesInService=1,
                MaxBatchSize=1,
                PauseTime='PT5M',
                WaitOnResourceSignals=True
            )
        )
    ))
