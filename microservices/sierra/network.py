from troposphere import GetAZs, Join, Ref, Select, Sub, Tags
from troposphere.ec2 import (
    InternetGateway, Route, RouteTable,
    Subnet, SubnetRouteTableAssociation,
    VPC, VPCGatewayAttachment
)

from .utils import AttrDict


def inject(template, vpc_cidr, subnet1_cidr, subnet2_cidr):
    vpc = template.add_resource(VPC(
        'NetworkVpc',
        CidrBlock=vpc_cidr,
        Tags=Tags(Name=Ref('AWS::StackName')),
    ))

    internet_gateway = template.add_resource(InternetGateway(
        'NetworkInternetGateway',
        Tags=Tags(Name=Ref('AWS::StackName')),
    ))

    template.add_resource(VPCGatewayAttachment(
        'NetworkInternetGatewayAttachment',
        InternetGatewayId=Ref(internet_gateway),
        VpcId=Ref(vpc),
    ))

    route_table = template.add_resource(RouteTable(
        'NetworkRouteTable',
        VpcId=Ref(vpc),
        Tags=Tags(Name=Ref('AWS::StackName')),
    ))

    template.add_resource(Route(
        'NetworkDefaultRoute',
        RouteTableId=Ref(route_table),
        DestinationCidrBlock='0.0.0.0/0',
        GatewayId=Ref(internet_gateway),
    ))

    subnet1 = template.add_resource(Subnet(
        'NetworkSubnet1',
        VpcId=Ref(vpc),
        AvailabilityZone=Select(0, GetAZs()),
        MapPublicIpOnLaunch=True,
        CidrBlock=subnet1_cidr,
        Tags=Tags(Name=Sub('${AWS::StackName} (Public)')),
    ))

    subnet2 = template.add_resource(Subnet(
        'NetworkSubnet2',
        VpcId=Ref(vpc),
        AvailabilityZone=Select(1, GetAZs()),
        MapPublicIpOnLaunch=True,
        CidrBlock=subnet2_cidr,
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

    return AttrDict(
        vpc=Ref(vpc),
        subnets=Join(',', [Ref(subnet1), Ref(subnet2)]),
    )
