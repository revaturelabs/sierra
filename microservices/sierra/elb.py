from troposphere import Ref, Sub
from troposphere import Parameter
from troposphere.ec2 import SecurityGroup, SecurityGroupRule
from troposphere.elasticloadbalancingv2 import (
    Action, Listener, LoadBalancer, TargetGroup
)


def add_to(template):
    prefix = template.add_parameter(Parameter(
        'Prefix',
        Type='String',
    ))
    subnet_ids = template.add_parameter(Parameter(
        'Subnets',
        Type='List<AWS::EC2::Subnet::Id>',
    ))
    vpc_id = template.add_parameter(Parameter(
        'VPC',
        Type='AWS::EC2::VPC::Id',
    ))

    security_group = template.add_resource(SecurityGroup(
        'SecurityGroup',
        GroupName=Sub(f'${{{prefix.title}}}-elb-sg'),
        GroupDescription=Sub(f'${{{prefix.title}}}-elb-sg'),
        VpcId=Ref(vpc_id),
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
        Name=Sub(f'${{{prefix.title}}}-default'),
        Port=80,
        Protocol='HTTP',
        TargetType='instance',
        VpcId=Ref(vpc_id),
    ))

    elb = template.add_resource(LoadBalancer(
        'LoadBalancer',
        Name=Sub(f'${{{prefix.title}}}-elb'),
        Subnets=Ref(subnet_ids),
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
