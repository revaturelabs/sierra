import awacs.codebuild
import awacs.ecs
import awacs.iam
import awacs.logs
import awacs.s3
import awacs.ssm
import awacs.sts
from awacs.aws import Allow, PolicyDocument, Principal, Statement

from troposphere import GetAtt, Ref, Sub
from troposphere.codebuild import Artifacts, Environment, Project, Source
from troposphere.codepipeline import (
    Actions, ActionTypeId, ArtifactStore, InputArtifacts,
    OutputArtifacts, Pipeline, Stages)
from troposphere.iam import Policy, Role
from troposphere.s3 import Bucket

from .webhook import AuthenticationConfiguration, FilterRule, Webhook


def inject(template, name, settings, github_token, cluster, service):
    artifact_bucket = template.add_resource(Bucket(
        f'{name}ArtifactBucket',
        DeletionPolicy='Retain'
    ))

    codebuild_role = template.add_resource(Role(
        f'{name}CodeBuildServiceRole',
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
        f'{name}CodePipelineServiceRole',
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
                        Resource=[
                            Sub(f'${{{artifact_bucket.title}.Arn}}/*')
                        ],
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
        f'{name}CodeBuildProject',
        Name=f'{name}Build',
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
        f'{name}Pipeline',
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
                        'Owner': settings.user,
                        'Repo': settings.repo,
                        'Branch': settings.branch,
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
        f'{name}CodePipelineWebhook',
        Name=f'{name}-webhook',
        Authentication='GITHUB_HMAC',
        AuthenticationConfiguration=AuthenticationConfiguration(
            SecretToken=Ref(github_token),
        ),
        Filters=[FilterRule(
            JsonPath='$.ref',
            MatchEquals=Sub(f'refs/heads/${{{settings.branch}}}')
        )],
        TargetAction='Source',
        TargetPipeline=Ref(pipeline),
        TargetPipelineVersion=1,
        RegisterWithThirdParty=True,
    ))
