"""Acceptance tests for DAT-02: `patients` table in template.

Derived from docs/architecture.md section 8 (DAT-02 row) and section 2.3,
plus docs/table-design.md's `## patients` section (DAT-01, merged) — no
standalone docs/tasks/WAVE-2.md exists yet for this task. Static checks
against infra/template.yaml only; sam validate --lint and a real deploy are
run separately.
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


def _dynamodb_table_resources(template):
    return {
        logical_id: resource
        for logical_id, resource in template["Resources"].items()
        if resource.get("Type") == "AWS::DynamoDB::Table"
    }


def test_exactly_one_dynamodb_table_exists():
    # True as of DAT-02; DAT-03/DAT-04 add the next tables and update this
    # count the same way DAT-02 updates INF-01's "zero resources" check.
    template = load_template()
    tables = _dynamodb_table_resources(template)
    assert len(tables) == 1, f"expected exactly one DynamoDB table, found {list(tables)}"


def test_patients_table_logical_id_and_type():
    template = load_template()
    tables = _dynamodb_table_resources(template)
    assert "PatientsTable" in tables


def _patients_table_properties():
    template = load_template()
    return template["Resources"]["PatientsTable"]["Properties"]


def test_patients_table_billing_mode_is_on_demand():
    properties = _patients_table_properties()
    assert properties["BillingMode"] == "PAY_PER_REQUEST"


def test_patients_table_key_schema_is_patient_id_only():
    properties = _patients_table_properties()
    key_schema = properties["KeySchema"]
    assert len(key_schema) == 1
    assert key_schema[0] == {"AttributeName": "patient_id", "KeyType": "HASH"}


def test_patients_table_attribute_definitions_declare_only_patient_id():
    properties = _patients_table_properties()
    attribute_definitions = properties["AttributeDefinitions"]
    assert len(attribute_definitions) == 1
    assert attribute_definitions[0] == {"AttributeName": "patient_id", "AttributeType": "S"}


def test_patients_table_name_uses_fn_sub_with_env():
    properties = _patients_table_properties()
    table_name = properties["TableName"]
    assert table_name == {"Fn::Sub": "patient-monitoring-${Env}-patients"}


def test_patients_table_has_no_global_secondary_indexes():
    properties = _patients_table_properties()
    assert "GlobalSecondaryIndexes" not in properties
