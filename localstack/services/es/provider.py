import logging
from typing import Optional, cast

from localstack.aws.api import RequestContext
from localstack.aws.api.es import (
    ARN,
    AdvancedOptions,
    AdvancedSecurityOptionsInput,
    AutoTuneOptionsInput,
    CognitoOptions,
    CompatibleElasticsearchVersionsList,
    CompatibleVersionsMap,
    CreateElasticsearchDomainResponse,
    DeleteElasticsearchDomainResponse,
    DescribeElasticsearchDomainConfigResponse,
    DescribeElasticsearchDomainResponse,
    DescribeElasticsearchDomainsResponse,
    DomainEndpointOptions,
    DomainInfoList,
    DomainName,
    DomainNameList,
    EBSOptions,
    ElasticsearchClusterConfig,
    ElasticsearchDomainConfig,
    ElasticsearchDomainStatus,
    ElasticsearchVersionString,
    EncryptionAtRestOptions,
    EngineType,
    EsApi,
    GetCompatibleElasticsearchVersionsResponse,
    ListDomainNamesResponse,
    ListElasticsearchVersionsResponse,
    ListTagsResponse,
    LogPublishingOptions,
    MaxResults,
    NextToken,
    NodeToNodeEncryptionOptions,
    PolicyDocument,
    SnapshotOptions,
    StringList,
    TagList,
    VPCOptions,
)
from localstack.aws.api.opensearch import (
    ClusterConfig,
    CompatibleVersionsList,
    DomainConfig,
    DomainStatus,
    VersionString,
)
from localstack.utils.analytics import event_publisher
from localstack.utils.aws import aws_stack

LOG = logging.getLogger(__name__)


def _version_to_opensearch(
    version: Optional[ElasticsearchVersionString],
) -> Optional[VersionString]:
    if version is not None:
        if version.startswith("OpenSearch_"):
            return version
        else:
            return f"Elasticsearch_{version}"


def _version_from_opensearch(
    version: Optional[VersionString],
) -> Optional[ElasticsearchVersionString]:
    if version is not None:
        if version.startswith("Elasticsearch_"):
            return version.split("_")[1]
        else:
            return version


def _instancetype_to_opensearch(instance_type: Optional[str]) -> Optional[str]:
    if instance_type is not None:
        return instance_type.replace("elasticsearch", "search")


def _instancetype_from_opensearch(instance_type: Optional[str]) -> Optional[str]:
    if instance_type is not None:
        return instance_type.replace("search", "elasticsearch")


def _clusterconfig_from_opensearch(
    cluster_config: Optional[ClusterConfig],
) -> Optional[ElasticsearchClusterConfig]:
    if cluster_config is not None:
        # Just take the whole typed dict and typecast it to our target type
        result = cast(ElasticsearchClusterConfig, cluster_config)

        # Adjust the instance type names
        result["InstanceType"] = _instancetype_from_opensearch(cluster_config.get("InstanceType"))
        result["DedicatedMasterType"] = _instancetype_from_opensearch(
            cluster_config.get("DedicatedMasterType")
        )
        result["WarmType"] = _instancetype_from_opensearch(cluster_config.get("WarmType"))
        return result


def _domainstatus_from_opensearch(
    domain_status: Optional[DomainStatus],
) -> Optional[ElasticsearchDomainStatus]:
    if domain_status is not None:
        # Just take the whole typed dict and typecast it to our target type
        result = cast(ElasticsearchDomainStatus, domain_status)
        # Only specifically handle keys which are named differently or their values differ (version and clusterconfig)
        result["ElasticsearchVersion"] = _version_from_opensearch(
            domain_status.get("EngineVersion")
        )
        result["ElasticsearchClusterConfig"] = _clusterconfig_from_opensearch(
            domain_status.get("ClusterConfig")
        )
        result.pop("EngineVersion", None)
        result.pop("ClusterConfig", None)
        return result


def _clusterconfig_to_opensearch(
    elasticsearch_cluster_config: Optional[ElasticsearchClusterConfig],
) -> Optional[ClusterConfig]:
    if elasticsearch_cluster_config is not None:
        result = cast(ClusterConfig, elasticsearch_cluster_config)
        result["InstanceType"] = _instancetype_to_opensearch(result.get("InstanceType"))
        result["DedicatedMasterType"] = _instancetype_to_opensearch(
            result.get("DedicatedMasterType")
        )
        result["WarmType"] = _instancetype_to_opensearch(result.get("WarmType"))
        return result


def _domainconfig_from_opensearch(
    domain_config: Optional[DomainConfig],
) -> Optional[ElasticsearchDomainConfig]:
    if domain_config is not None:
        result = cast(ElasticsearchDomainConfig, domain_config)
        result["ElasticsearchVersion"] = _version_from_opensearch(
            domain_config.get("EngineVersion")
        )
        result["ElasticsearchClusterConfig"] = _clusterconfig_from_opensearch(
            domain_config.get("ClusterConfig")
        )
        result.pop("EngineVersion", None)
        result.pop("ClusterConfig", None)
        return result


def _compatible_version_list_from_opensearch(
    compatible_version_list: Optional[CompatibleVersionsList],
) -> Optional[CompatibleElasticsearchVersionsList]:
    if compatible_version_list is not None:
        return [
            CompatibleVersionsMap(
                SourceVersion=_version_from_opensearch(version_map["SourceVersion"]),
                TargetVersions=[
                    _version_from_opensearch(target_version)
                    for target_version in version_map["TargetVersions"]
                ],
            )
            for version_map in compatible_version_list
        ]


class EsProvider(EsApi):
    # TODO implement error handling
    # TODO describe-domain-config doesn't work yet (it broke with recent changes to the operation determination / regex)

    def create_elasticsearch_domain(
        self,
        context: RequestContext,
        domain_name: DomainName,
        elasticsearch_version: ElasticsearchVersionString = None,
        elasticsearch_cluster_config: ElasticsearchClusterConfig = None,
        ebs_options: EBSOptions = None,
        access_policies: PolicyDocument = None,
        snapshot_options: SnapshotOptions = None,
        vpc_options: VPCOptions = None,
        cognito_options: CognitoOptions = None,
        encryption_at_rest_options: EncryptionAtRestOptions = None,
        node_to_node_encryption_options: NodeToNodeEncryptionOptions = None,
        advanced_options: AdvancedOptions = None,
        log_publishing_options: LogPublishingOptions = None,
        domain_endpoint_options: DomainEndpointOptions = None,
        advanced_security_options: AdvancedSecurityOptionsInput = None,
        auto_tune_options: AutoTuneOptionsInput = None,
        tag_list: TagList = None,
    ) -> CreateElasticsearchDomainResponse:
        opensearch_client = aws_stack.connect_to_service("opensearch", region_name=context.region)

        kwargs = {
            "DomainName": domain_name,
            "EngineVersion": _version_to_opensearch(elasticsearch_version),
            "ClusterConfig": _clusterconfig_to_opensearch(elasticsearch_cluster_config),
            "EBSOptions": ebs_options,
            "AccessPolicies": access_policies,
            "SnapshotOptions": snapshot_options,
            "VPCOptions": vpc_options,
            "CognitoOptions": cognito_options,
            "EncryptionAtRestOptions": encryption_at_rest_options,
            "NodeToNodeEncryptionOptions": node_to_node_encryption_options,
            "AdvancedOptions": advanced_options,
            "LogPublishingOptions": log_publishing_options,
            "DomainEndpointOptions": domain_endpoint_options,
            "AdvancedSecurityOptions": advanced_security_options,
            "AutoTuneOptions": auto_tune_options,
            "TagList": tag_list,
        }

        # Filter the kwargs to not set None values at all (boto doesn't like that)
        kwargs = {key: value for key, value in kwargs.items() if value is not None}

        domain_status = opensearch_client.create_domain(**kwargs)["DomainStatus"]

        # record event
        event_publisher.fire_event(
            event_publisher.EVENT_ES_CREATE_DOMAIN,
            payload={"n": event_publisher.get_hash(domain_name)},
        )

        status = _domainstatus_from_opensearch(domain_status)
        return CreateElasticsearchDomainResponse(DomainStatus=status)

    def delete_elasticsearch_domain(
        self, context: RequestContext, domain_name: DomainName
    ) -> DeleteElasticsearchDomainResponse:
        opensearch_client = aws_stack.connect_to_service("opensearch", region_name=context.region)

        domain_status = opensearch_client.delete_domain(
            DomainName=domain_name,
        )["DomainStatus"]

        # record event
        event_publisher.fire_event(
            event_publisher.EVENT_ES_DELETE_DOMAIN,
            payload={"n": event_publisher.get_hash(domain_name)},
        )

        status = _domainstatus_from_opensearch(domain_status)
        return DeleteElasticsearchDomainResponse(DomainStatus=status)

    def describe_elasticsearch_domain(
        self, context: RequestContext, domain_name: DomainName
    ) -> DescribeElasticsearchDomainResponse:
        opensearch_client = aws_stack.connect_to_service("opensearch", region_name=context.region)

        opensearch_status = opensearch_client.describe_domain(
            DomainName=domain_name,
        )["DomainStatus"]

        status = _domainstatus_from_opensearch(opensearch_status)
        return DescribeElasticsearchDomainResponse(DomainStatus=status)

    def describe_elasticsearch_domains(
        self, context: RequestContext, domain_names: DomainNameList
    ) -> DescribeElasticsearchDomainsResponse:
        opensearch_client = aws_stack.connect_to_service("opensearch", region_name=context.region)

        opensearch_status_list = opensearch_client.describe_domains(DomainNames=domain_names)[
            "DomainStatusList"
        ]

        status_list = [_domainstatus_from_opensearch(s) for s in opensearch_status_list]
        return DescribeElasticsearchDomainsResponse(DomainStatusList=status_list)

    def list_domain_names(
        self, context: RequestContext, engine_type: EngineType = None
    ) -> ListDomainNamesResponse:
        opensearch_client = aws_stack.connect_to_service("opensearch", region_name=context.region)
        # Only hand the EngineType param to boto if it's set
        kwargs = {}
        if engine_type:
            kwargs["EngineType"] = engine_type
        domain_names = opensearch_client.list_domain_names(**kwargs)["DomainNames"]
        return ListDomainNamesResponse(DomainNames=cast(Optional[DomainInfoList], domain_names))

    def list_elasticsearch_versions(
        self,
        context: RequestContext,
        max_results: MaxResults = None,
        next_token: NextToken = None,
    ) -> ListElasticsearchVersionsResponse:
        opensearch_client = aws_stack.connect_to_service("opensearch", region_name=context.region)
        # Construct the arguments as kwargs to not set None values at all (boto doesn't like that)
        kwargs = {
            key: value
            for key, value in {"MaxResults": max_results, "NextToken": next_token}.items()
            if value is not None
        }
        versions = opensearch_client.list_versions(**kwargs)
        return ListElasticsearchVersionsResponse(
            ElasticsearchVersions=[
                _version_from_opensearch(version) for version in versions["Versions"]
            ],
            NextToken=versions.get(next_token),
        )

    def get_compatible_elasticsearch_versions(
        self, context: RequestContext, domain_name: DomainName = None
    ) -> GetCompatibleElasticsearchVersionsResponse:
        opensearch_client = aws_stack.connect_to_service("opensearch", region_name=context.region)
        # Only hand the DomainName param to boto if it's set
        kwargs = {}
        if domain_name:
            kwargs["DomainName"] = domain_name
        compatible_versions_response = opensearch_client.get_compatible_versions(**kwargs)
        compatible_versions = compatible_versions_response.get("CompatibleVersions")
        return GetCompatibleElasticsearchVersionsResponse(
            CompatibleElasticsearchVersions=_compatible_version_list_from_opensearch(
                compatible_versions
            )
        )

    def describe_elasticsearch_domain_config(
        self, context: RequestContext, domain_name: DomainName
    ) -> DescribeElasticsearchDomainConfigResponse:
        opensearch_client = aws_stack.connect_to_service("opensearch", region_name=context.region)
        domain_config = opensearch_client.describe_domain_config(DomainName=domain_name).get(
            "DomainConfig"
        )
        return DescribeElasticsearchDomainConfigResponse(
            DomainConfig=_domainconfig_from_opensearch(domain_config)
        )

    def add_tags(self, context: RequestContext, arn: ARN, tag_list: TagList) -> None:
        opensearch_client = aws_stack.connect_to_service("opensearch", region_name=context.region)
        opensearch_client.add_tags(ARN=arn, TagList=tag_list)

    def list_tags(self, context: RequestContext, arn: ARN) -> ListTagsResponse:
        opensearch_client = aws_stack.connect_to_service("opensearch", region_name=context.region)
        response = opensearch_client.list_tags(ARN=arn)
        return ListTagsResponse(TagList=response.get("TagList"))

    def remove_tags(self, context: RequestContext, arn: ARN, tag_keys: StringList) -> None:
        opensearch_client = aws_stack.connect_to_service("opensearch", region_name=context.region)
        opensearch_client.remove_tags(ARN=arn, TagKeys=tag_keys)
