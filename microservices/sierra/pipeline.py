import awacs.codebuild
import awacs.ecs
import awacs.iam
import awacs.s3
import awacs.ssm
import awacs.sts
import awacs.logs

from awacs.aws import Allow, PolicyDocument, Principal, Statement

from troposphere import AWSObject, AWSProperty
from troposphere import GetAtt, Ref, Sub
from troposphere.codebuild import Artifacts, Environment, Project, Source
from troposphere.codepipeline import (
    Actions, ActionTypeId, ArtifactStore, InputArtifacts,
    OutputArtifacts, Pipeline, Stages
)
from troposphere.iam import Policy, Role
from troposphere.s3 import Bucket
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


def inject(template, github, github_token, cluster, service):
    artifact_bucket = template.add_resource(Bucket(
        'ArtifactBucket',
        DeletionPolicy='Retain'
    ))

    artifact_bucket_arn = awacs.s3.ARN(f'${{{artifact_bucket.title}}}/*')

    codebuild_role = template.add_resource(Role(
        'CodeBuildServiceRole',
        Path='/',
        AssumeRolePolicyDocument=PolicyDocument(
            Version='2012-10-17',
            Statement=[
                Statement(
                    Effect=Allow,
                    Principal=Principal(
                        'Service', 'codebuild.amazonaws.com'
                    ),
                    Action=[
                        awacs.sts.AssumeRole,
                    ],
                ),
            ],
        ),
        Policies=[Policy(
            PolicyName='root',
            PolicyDocument=PolicyDocument(
                Version='2012-10-17',
                Statement=[
                    Statement(
                        Resource=['*'],
                        Effect=Allow,
                        Action=[
                            awacs.ssm.GetParameters,
                        ],
                    ),
                    Statement(
                        Resource=['*'],
                        Effect=Allow,
                        Action=[
                            awacs.s3.GetObject,
                            awacs.s3.PutObject,
                            awacs.s3.GetObjectVersion,
                        ],
                    ),
                    Statement(
                        Resource=['*'],
                        Effect=Allow,
                        Action=[
                            awacs.logs.CreateLogGroup,
                            awacs.logs.CreateLogStream,
                            awacs.logs.PutLogEvents,
                        ],
                    ),
                ],
            ),
        )],
    ))

    codepipeline_role = template.add_resource(Role(
        'CodePipelineServiceRole',
        Path='/',
        AssumeRolePolicyDocument=PolicyDocument(
            Version='2012-10-17',
            Statement=[
                Statement(
                    Effect=Allow,
                    Principal=Principal(
                        'Service', 'codepipeline.amazonaws.com'
                    ),
                    Action=[
                        awacs.sts.AssumeRole,
                    ],
                ),
            ],
        ),
        Policies=[Policy(
            PolicyName='root',
            PolicyDocument=PolicyDocument(
                Version='2012-10-17',
                Statement=[
                    Statement(
                        Resource=[Sub(artifact_bucket_arn)],
                        Effect=Allow,
                        Action=[
                            awacs.s3.GetBucketVersioning,
                            awacs.s3.GetObject,
                            awacs.s3.GetObjectVersion,
                            awacs.s3.PutObject,
                        ],
                    ),
                    Statement(
                        Resource=['*'],
                        Effect=Allow,
                        Action=[
                            awacs.ecs.DescribeServices,
                            awacs.ecs.DescribeTaskDefinition,
                            awacs.ecs.DescribeTasks,
                            awacs.ecs.ListTasks,
                            awacs.ecs.RegisterTaskDefinition,
                            awacs.ecs.UpdateService,
                            awacs.codebuild.StartBuild,
                            awacs.codebuild.BatchGetBuilds,
                            awacs.iam.PassRole,
                        ],
                    ),
                ],
            ),
        )],
    ))

    project = template.add_resource(Project(
        f'{service.title}CodeBuildProject',
        Name=f'{service.title}',
        ServiceRole=Ref(codebuild_role),
        Artifacts=Artifacts(Type='CODEPIPELINE'),
        Source=Source(Type='CODEPIPELINE'),
        Environment=Environment(
            ComputeType='BUILD_GENERAL1_SMALL',
            Image='aws/codebuild/docker:17.09.0',
            Type='LINUX_CONTAINER',
        ),
    ))

    pipeline = template.add_resource(Pipeline(
        f'{service.title}Pipeline',
        RoleArn=GetAtt(codepipeline_role, 'Arn'),
        ArtifactStore=ArtifactStore(
            Type='S3',
            Location=Ref(artifact_bucket),
        ),
        Stages=[
            Stages(
                Name='Source',
                Actions=[Actions(
                    Name='Source',
                    ActionTypeId=ActionTypeId(
                        Category='Source',
                        Owner='ThirdParty',
                        Version='1',
                        Provider='GitHub',
                    ),
                    OutputArtifacts=[OutputArtifacts(Name='Source')],
                    RunOrder='1',
                    Configuration={
                        'Owner': github['user'],
                        'Repo': github['repo'],
                        'Branch': github['branch'],
                        'OAuthToken': Ref(github_token),
                    },
                )],
            ),
            Stages(
                Name='Build',
                Actions=[Actions(
                    Name='Build',
                    ActionTypeId=ActionTypeId(
                        Category='Build',
                        Owner='AWS',
                        Version='1',
                        Provider='CodeBuild',
                    ),
                    InputArtifacts=[InputArtifacts(Name='Source')],
                    OutputArtifacts=[OutputArtifacts(Name='Build')],
                    RunOrder='1',
                    Configuration={
                        'ProjectName': Ref(project),
                    },
                )],
            ),
            Stages(
                Name='Deploy',
                Actions=[Actions(
                    Name='Deploy',
                    ActionTypeId=ActionTypeId(
                        Category='Deploy',
                        Owner='AWS',
                        Version='1',
                        Provider='ECS',
                    ),
                    InputArtifacts=[InputArtifacts(Name='Build')],
                    RunOrder='1',
                    Configuration={
                        'ClusterName': Ref(cluster),
                        'ServiceName': Ref(service),
                        'FileName': 'image.json',
                    },
                )],
            ),
        ],
    ))

    template.add_resource(Webhook(
        f'{service.title}CodePipelineWebhook',
        Name=f'{service.title}-webhook',
        Authentication='GITHUB_HMAC',
        AuthenticationConfiguration=AuthenticationConfiguration(
            SecretToken=Ref(github_token),
        ),
        Filters=[FilterRule(
            JsonPath='$.ref',
            MatchEquals=Sub('refs/heads/${{{}}}'.format(github['branch']))
        )],
        TargetAction='Source',
        TargetPipeline=Ref(pipeline),
        TargetPipelineVersion=1,
        RegisterWithThirdParty=True,
    ))

    return {
        'PipelineUrl': 'blah',
    }
