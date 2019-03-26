"""CodePipeline Webhook made using Troposphere API.

Troposphere does not appear to support this resource at the moment, so we
have to make it ourself. If at some point they do add support, use that
instead and get rid of this file.
"""

from troposphere import AWSObject, AWSProperty
from troposphere.validators import boolean, integer


basestring = (str, bytes)


class AuthenticationConfiguration(AWSProperty):
    props = {
        'AllowedIPRange': (basestring, False),
        'SecretToken': (basestring, False),
    }


class FilterRule(AWSProperty):
    props = {
        'JsonPath': (basestring, True),
        'MatchEquals': (basestring, False),
    }


class Webhook(AWSObject):
    resource_type = 'AWS::CodePipeline::Webhook'

    props = {
        'Name': (basestring, False),
        'Authentication': (basestring, True),
        'AuthenticationConfiguration': (AuthenticationConfiguration, True),
        'Filters': ([FilterRule], True),
        'RegisterWithThirdParty': (boolean, False),
        'TargetPipeline': (basestring, True),
        'TargetAction': (basestring, True),
        'TargetPipelineVersion': (integer, True),
    }
