from troposphere import Ref, Sub
from troposphere.elasticloadbalancingv2 import LoadBalancer

from .utils import AttrDict


ELB_NAME = 'ElbLoadBalancer'


def inject(template, network, ports):
    elb = template.add_resource(LoadBalancer(
        ELB_NAME,
        Name=Sub('${AWS::StackName}-elb'),
        Type='network',
        Subnets=network.subnets,
    ))

    return AttrDict(
        load_balancer=Ref(elb),
    )
