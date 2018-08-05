from troposphere import Ref, Sub
from troposphere.ec2 import SecurityGroup, SecurityGroupRule
from troposphere.elasticloadbalancingv2 import (
    Action, Listener, LoadBalancer, TargetGroup
)

from .utils import AttrDict


ELB_NAME = 'ElbLoadBalancer'


def inject(template, network):
    security_group = template.add_resource(SecurityGroup(
        'ElbSecurityGroup',
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
        'ElbDefaultTargetGroup',
        Name=Sub('${AWS::StackName}-default'),
        Port=80,
        Protocol='HTTP',
        TargetType='instance',
        VpcId=network.vpc,
    ))

    elb = template.add_resource(LoadBalancer(
        ELB_NAME,
        Name=Sub('${AWS::StackName}-elb'),
        Subnets=network.subnets,
        SecurityGroups=[Ref(security_group)],
    ))

    template.add_resource(Listener(
        'ElbLoadBalancerListener',
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

    return AttrDict(
        load_balancer=Ref(elb),
        security_group=Ref(security_group),
        target_group=Ref(target_group),
    )
