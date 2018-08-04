from collections import namedtuple
from troposphere import GetAZs, Join, Ref, Select, Sub, Tags
from troposphere.ec2 import (
    InternetGateway, Route, RouteTable,
    Subnet, SubnetRouteTableAssociation,
    VPC, VPCGatewayAttachment
)


Network = namedtuple('Network', ['vpc', 'subnets'])


def inject(template, prefix, vpc_cidr, subnet1_cidr, subnet2_cidr):
    vpc = template.add_resource(VPC(
        'VPC',
        CidrBlock=Ref(vpc_cidr),
        Tags=Tags(Name=Ref(prefix)),
    ))

    internet_gateway = template.add_resource(InternetGateway(
        'InternetGateway',
        Tags=Tags(Name=Ref(prefix)),
    ))

    template.add_resource(VPCGatewayAttachment(
        'InternetGatewayAttachment',
        InternetGatewayId=Ref(internet_gateway),
        VpcId=Ref(vpc),
    ))

    route_table = template.add_resource(RouteTable(
        'RouteTable',
        VpcId=Ref(vpc),
        Tags=Tags(Name=Ref(prefix)),
    ))

    template.add_resource(Route(
        'DefaultRoute',
        RouteTableId=Ref(route_table),
        DestinationCidrBlock='0.0.0.0/0',
        GatewayId=Ref(internet_gateway),
    ))

    subnet1 = template.add_resource(Subnet(
        'Subnet1',
        VpcId=Ref(vpc),
        AvailabilityZone=Select(0, GetAZs()),
        MapPublicIpOnLaunch=True,
        CidrBlock=Ref(subnet1_cidr),
        Tags=Tags(Name=Sub(f'${{{prefix}}} (Public)')),
    ))

    subnet2 = template.add_resource(Subnet(
        'Subnet2',
        VpcId=Ref(vpc),
        AvailabilityZone=Select(1, GetAZs()),
        MapPublicIpOnLaunch=True,
        CidrBlock=Ref(subnet2_cidr),
        Tags=Tags(Name=Sub(f'${{{prefix}}} (Public)')),
    ))

    template.add_resource(SubnetRouteTableAssociation(
        'Subnet1RouteTableAssociation',
        RouteTableId=Ref(route_table),
        SubnetId=Ref(subnet1),
    ))

    template.add_resource(SubnetRouteTableAssociation(
        'Subnet2RouteTableAssociation',
        RouteTableId=Ref(route_table),
        SubnetId=Ref(subnet2),
    ))

    return Network(
        vpc=Ref(vpc),
        subnets=Join(',', [Ref(subnet1), Ref(subnet2)]),
    )
