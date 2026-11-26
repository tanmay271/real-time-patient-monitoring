"""Acceptance tests for DAT-03: `readings` table with TTL on `expires_at`.

Derived from docs/architecture.md section 8 (DAT-03 row), sections 2.3 and
13, and docs/table-design.md (`readings`, TTL and billing sections). Static
checks against infra/template.yaml only; sam validate --lint and a real
deploy are run separately.
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


def _readings_table():
    resources = load_template()["Resources"]
    assert "ReadingsTable" in resources, "ReadingsTable resource is missing"
    return resources["ReadingsTable"]


def _readings_properties():
    return _readings_table()["Properties"]


def test_readings_table_is_a_dynamodb_table():
    assert _readings_table()["Type"] == "AWS::DynamoDB::Table"


def test_exactly_one_table_is_named_readings():
    resources = load_template()["Resources"]
    matches = [
        logical_id
        for logical_id, resource in resources.items()
        if resource.get("Type") == "AWS::DynamoDB::Table"
        and resource["Properties"].get("TableName")
        == {"Fn::Sub": "patient-monitoring-${Env}-readings"}
    ]
    assert matches == ["ReadingsTable"]


def test_readings_table_is_on_demand_with_no_provisioned_capacity():
    properties = _readings_properties()
    assert properties["BillingMode"] == "PAY_PER_REQUEST"
    assert "ProvisionedThroughput" not in properties


def test_readings_table_key_schema_is_patient_id_then_reading_time():
    assert _readings_properties()["KeySchema"] == [
        {"AttributeName": "patient_id", "KeyType": "HASH"},
        {"AttributeName": "reading_time", "KeyType": "RANGE"},
    ]


def test_readings_table_declares_only_the_two_key_attributes_as_strings():
    definitions = _readings_properties()["AttributeDefinitions"]
    assert sorted(definitions, key=lambda item: item["AttributeName"]) == [
        {"AttributeName": "patient_id", "AttributeType": "S"},
        {"AttributeName": "reading_time", "AttributeType": "S"},
    ]


def test_readings_table_ttl_is_enabled_on_expires_at():
    assert _readings_properties()["TimeToLiveSpecification"] == {
        "AttributeName": "expires_at",
        "Enabled": True,
    }


def test_readings_table_has_no_secondary_indexes():
    properties = _readings_properties()
    assert "GlobalSecondaryIndexes" not in properties
    assert "LocalSecondaryIndexes" not in properties
