"""Acceptance tests for INF-01: SAM template skeleton with Env parameter.

Static checks against infra/template.yaml, infra/samconfig.toml and
infra/README.md. No AWS calls and no dependency on the sam CLI binary;
sam validate --lint is run separately in CI and in local verification.
"""
import re
import tomllib
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_PATH = REPO_ROOT / "infra" / "template.yaml"
SAMCONFIG_PATH = REPO_ROOT / "infra" / "samconfig.toml"
README_PATH = REPO_ROOT / "infra" / "README.md"

# The test file itself is excluded: its source necessarily contains the
# "arn:aws:" and 12-digit literals below as detection patterns, which would
# otherwise flag itself as a false positive.
COMMITTED_FILES = [
    TEMPLATE_PATH,
    SAMCONFIG_PATH,
    README_PATH,
]

ACCOUNT_ID_PATTERN = re.compile(r"\d{12}")
ARN_PATTERN = re.compile(r"arn:aws:")


class _CfnTagLoader(yaml.SafeLoader):
    """A yaml.SafeLoader that tolerates CloudFormation short-form intrinsic
    function tags (!Sub, !Ref, !GetAtt, ...) by parsing their payload as a
    plain value instead of raising a ConstructorError."""


def _construct_cfn_tag(loader, tag_suffix, node):
    if isinstance(node, yaml.ScalarNode):
        return {f"Fn::{tag_suffix}": loader.construct_scalar(node)}
    if isinstance(node, yaml.SequenceNode):
        return {f"Fn::{tag_suffix}": loader.construct_sequence(node)}
    return {f"Fn::{tag_suffix}": loader.construct_mapping(node)}


_CfnTagLoader.add_multi_constructor("!", _construct_cfn_tag)


def load_template():
    text = TEMPLATE_PATH.read_text(encoding="utf-8")
    return text, yaml.load(text, Loader=_CfnTagLoader)


def test_template_file_exists():
    assert TEMPLATE_PATH.is_file()


def test_template_format_version_and_transform():
    _, template = load_template()
    assert template["AWSTemplateFormatVersion"] == "2010-09-09"
    assert template["Transform"] == "AWS::Serverless-2016-10-31"


def test_env_parameter_present_with_no_default():
    _, template = load_template()
    parameters = template["Parameters"]
    assert "Env" in parameters
    env_param = parameters["Env"]
    assert env_param["Type"] == "String"
    assert "Description" in env_param
    assert "Default" not in env_param


def test_globals_block_matches_spec():
    _, template = load_template()
    function_globals = template["Globals"]["Function"]
    assert function_globals["Runtime"] == "python3.13"
    assert function_globals["Timeout"] == 10
    assert function_globals["MemorySize"] == 256


def test_resources_key_present():
    # INF-01's skeleton required Resources == {}. Later tasks (starting with
    # DAT-02) add real resources, so this now only checks the key survives
    # as a mapping, not that it stays empty.
    _, template = load_template()
    assert isinstance(template["Resources"], dict)


def test_naming_convention_comment_present():
    text, _ = load_template()
    assert "patient-monitoring-{Env}-" in text
    assert "Fn::Sub" in text


def test_no_hardcoded_patient_monitoring_resource_name():
    # Every resource name must be built with Fn::Sub against the Env
    # parameter, never a literal "patient-monitoring-<concrete-env>-..."
    # string baked into a resource property.
    _, template = load_template()
    literal_pattern = re.compile(r"patient-monitoring-(?!\{Env\}|\$\{Env\})[a-z0-9]+-")
    for resource in template["Resources"].values():
        properties = resource.get("Properties", {})
        assert not literal_pattern.search(str(properties)), (
            f"literal resource name found in {resource}"
        )


def test_samconfig_region_is_us_east_1():
    with SAMCONFIG_PATH.open("rb") as f:
        config = tomllib.load(f)
    assert config["default"]["deploy"]["parameters"]["region"] == "us-east-1"


def test_samconfig_capability_iam():
    with SAMCONFIG_PATH.open("rb") as f:
        config = tomllib.load(f)
    capabilities = config["default"]["deploy"]["parameters"]["capabilities"]
    assert "CAPABILITY_IAM" in capabilities


def test_readme_has_deploy_and_teardown_commands():
    text = README_PATH.read_text(encoding="utf-8")
    assert "sam deploy" in text
    assert "sam delete" in text


def test_no_account_id_or_arn_in_committed_files():
    # No real AWS account ID (a 12-digit literal) is ever allowed, in any
    # file. A bare "arn:aws:" substring, however, is allowed in README.md:
    # INF-03 documents real IAM AccessDenied output there with an
    # "<ACCOUNT_ID>" placeholder (not a digit literal), which is itself an
    # ARN-shaped string. template.yaml and samconfig.toml are fully
    # parameterized and should never contain an ARN at all.
    for path in COMMITTED_FILES:
        text = path.read_text(encoding="utf-8")
        assert not ACCOUNT_ID_PATTERN.search(text), (
            f"possible account ID literal in {path}"
        )
        if path != README_PATH:
            assert not ARN_PATTERN.search(text), f"ARN literal found in {path}"
