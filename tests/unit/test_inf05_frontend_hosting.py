"""Acceptance tests for INF-05: S3 bucket + CloudFront distribution for the
frontend.

Derived from docs/tasks/WAVE-1.md's `## INF-05` section (identical to issue
#5). Static checks against infra/template.yaml only; a direct-S3-denied
check, the stack-output check, the placeholder-page check and the 404
rewrite check are all runtime behaviour verified separately against a real
deployed scratch stack, not here. sam validate --lint is also run
separately.
"""
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_PATH = REPO_ROOT / "infra" / "template.yaml"


class _CfnTagLoader(yaml.SafeLoader):
    pass


def _construct_cfn_tag(loader, tag_suffix, node):
    if isinstance(node, yaml.ScalarNode):
        return {f"Fn::{tag_suffix}": loader.construct_scalar(node)}
    if isinstance(node, yaml.SequenceNode):
        return {f"Fn::{tag_suffix}": loader.construct_sequence(node)}
    return {f"Fn::{tag_suffix}": loader.construct_mapping(node)}


_CfnTagLoader.add_multi_constructor("!", _construct_cfn_tag)


def load_template():
    text = TEMPLATE_PATH.read_text(encoding="utf-8")
    return yaml.load(text, Loader=_CfnTagLoader)


def _resources_of_type(template, cfn_type):
    return {
        logical_id: resource
        for logical_id, resource in template["Resources"].items()
        if resource.get("Type") == cfn_type
    }


def _bucket_properties():
    template = load_template()
    buckets = _resources_of_type(template, "AWS::S3::Bucket")
    assert len(buckets) == 1, f"expected exactly one S3 bucket, found {list(buckets)}"
    logical_id = next(iter(buckets))
    return buckets[logical_id]["Properties"]


def _distribution_properties():
    template = load_template()
    distributions = _resources_of_type(template, "AWS::CloudFront::Distribution")
    assert len(distributions) == 1, (
        f"expected exactly one CloudFront distribution, found {list(distributions)}"
    )
    logical_id = next(iter(distributions))
    return distributions[logical_id]["Properties"]


def _oac_properties():
    template = load_template()
    oacs = _resources_of_type(template, "AWS::CloudFront::OriginAccessControl")
    assert len(oacs) == 1, f"expected exactly one OriginAccessControl, found {list(oacs)}"
    logical_id = next(iter(oacs))
    return oacs[logical_id]["Properties"]


def _bucket_policy_properties():
    template = load_template()
    policies = _resources_of_type(template, "AWS::S3::BucketPolicy")
    assert len(policies) == 1, f"expected exactly one bucket policy, found {list(policies)}"
    logical_id = next(iter(policies))
    return policies[logical_id]["Properties"]


def test_s3_bucket_exists():
    _bucket_properties()


def test_bucket_name_uses_fn_sub_with_env():
    properties = _bucket_properties()
    assert properties["BucketName"] == {
        "Fn::Sub": "patient-monitoring-${Env}-frontend"
    }


def test_bucket_blocks_all_public_access():
    properties = _bucket_properties()
    block = properties["PublicAccessBlockConfiguration"]
    assert block["BlockPublicAcls"] is True
    assert block["BlockPublicPolicy"] is True
    assert block["IgnorePublicAcls"] is True
    assert block["RestrictPublicBuckets"] is True


def test_bucket_has_no_public_acl():
    properties = _bucket_properties()
    assert "AccessControl" not in properties


def test_origin_access_control_exists_and_is_sigv4():
    properties = _oac_properties()
    config = properties["OriginAccessControlConfig"]
    assert config["SigningBehavior"] == "always"
    assert config["SigningProtocol"] == "sigv4"
    assert config["OriginAccessControlOriginType"] == "s3"


def test_origin_access_control_name_uses_fn_sub_with_env():
    properties = _oac_properties()
    config = properties["OriginAccessControlConfig"]
    assert config["Name"] == {"Fn::Sub": "patient-monitoring-${Env}-frontend-oac"}


def test_bucket_policy_grants_cloudfront_service_principal_only():
    properties = _bucket_policy_properties()
    statements = properties["PolicyDocument"]["Statement"]
    assert len(statements) == 1
    statement = statements[0]
    assert statement["Effect"] == "Allow"
    assert statement["Principal"] == {"Service": "cloudfront.amazonaws.com"}
    assert statement["Action"] == "s3:GetObject"


def test_bucket_policy_scopes_to_this_distribution_via_source_arn():
    properties = _bucket_policy_properties()
    statement = properties["PolicyDocument"]["Statement"][0]
    condition = statement["Condition"]
    assert "StringEquals" in condition
    source_arn = condition["StringEquals"]["AWS:SourceArn"]
    assert source_arn == {
        "Fn::Sub": (
            "arn:aws:cloudfront::${AWS::AccountId}:distribution/"
            "${FrontendDistribution}"
        )
    }


def test_distribution_exists():
    _distribution_properties()


def test_distribution_default_root_object_is_index_html():
    properties = _distribution_properties()
    assert properties["DistributionConfig"]["DefaultRootObject"] == "index.html"


def test_distribution_has_exactly_one_s3_origin_using_the_oac():
    properties = _distribution_properties()
    origins = properties["DistributionConfig"]["Origins"]
    assert len(origins) == 1
    origin = origins[0]
    assert "S3OriginConfig" in origin
    assert "OriginAccessControlId" in origin


def test_distribution_viewer_protocol_policy_redirects_to_https():
    properties = _distribution_properties()
    behavior = properties["DistributionConfig"]["DefaultCacheBehavior"]
    assert behavior["ViewerProtocolPolicy"] == "redirect-to-https"


def test_distribution_has_403_and_404_rewrite_to_index_html():
    properties = _distribution_properties()
    custom_errors = properties["DistributionConfig"]["CustomErrorResponses"]
    by_code = {entry["ErrorCode"]: entry for entry in custom_errors}
    assert set(by_code) == {403, 404}
    for entry in by_code.values():
        assert entry["ResponseCode"] == 200
        assert entry["ResponsePagePath"] == "/index.html"


def test_distribution_has_no_aliases_or_custom_domain():
    properties = _distribution_properties()
    assert "Aliases" not in properties["DistributionConfig"]


def test_distribution_is_enabled():
    properties = _distribution_properties()
    assert properties["DistributionConfig"]["Enabled"] is True


def test_distribution_domain_name_output_exists():
    template = load_template()
    outputs = template.get("Outputs", {})
    assert "FrontendDistributionDomainName" in outputs
    output = outputs["FrontendDistributionDomainName"]
    assert output["Value"] == {"Fn::GetAtt": "FrontendDistribution.DomainName"}
