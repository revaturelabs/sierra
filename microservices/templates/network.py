from troposphere import GetAZs, Ref, Select, Sub
from troposphere import Parameter, Tags
from troposphere.ec2 import (
    InternetGateway, Route, RouteTable,
    Subnet, SubnetRouteTableAssociation,
    VPC, VPCGatewayAttachment
)


def add_to(template):
    prefix = template.add_parameter(Parameter(
        'Prefix',
        Type='String',
    ))
    vpc_cidr = template.add_parameter(Parameter(
        'VpcCidr',
        Type='String',
        Default='192.172.0.0/16',
    ))
    subnet1_cidr = template.add_parameter(Parameter(
        'Subnet1Cidr',
        Type='String',
        Default='192.172.1.0/24',
    ))
    subnet2_cidr = template.add_parameter(Parameter(
        'Subnet2Cidr',
        Type='String',
        Default='192.172.2.0/24',
    ))

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
        Tags=Tags(Name=Sub(f'${{{prefix.title}}} (Public)')),
    ))

    subnet2 = template.add_resource(Subnet(
        'Subnet2',
        VpcId=Ref(vpc),
        AvailabilityZone=Select(1, GetAZs()),
        MapPublicIpOnLaunch=True,
        CidrBlock=Ref(subnet2_cidr),
        Tags=Tags(Name=Sub(f'${{{prefix.title}}} (Public)')),
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
