"""Acceptance tests for DAT-04: `alerts` table with GSI1 and GSI2.

Derived from docs/architecture.md section 8 (DAT-04 definition of done),
sections 2.3 and 2.4, docs/table-design.md (`alerts`, GSIs, access patterns,
billing) and docs/api.md (`GET /alerts`). Template checks are static; the two
query checks build a moto table from the template's own properties. sam
validate --lint and a real deploy are run separately. All data is synthetic.
"""
from pathlib import Path

import boto3
import pytest
import yaml
from boto3.dynamodb.conditions import Key
from moto import mock_aws

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_PATH = REPO_ROOT / "infra" / "template.yaml"
ALERTS_NAME = {"Fn::Sub": "patient-monitoring-${Env}-alerts"}


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


def _tables():
    return {
        logical_id: resource
        for logical_id, resource in load_template()["Resources"].items()
        if resource.get("Type") == "AWS::DynamoDB::Table"
    }


def _alerts_properties():
    tables = _tables()
    assert "AlertsTable" in tables, "AlertsTable resource is missing"
    return tables["AlertsTable"]["Properties"]


def _indexes():
    return {
        index["IndexName"]: index
        for index in _alerts_properties()["GlobalSecondaryIndexes"]
    }


def test_exactly_one_table_is_named_alerts():
    matches = [
        logical_id
        for logical_id, resource in _tables().items()
        if resource["Properties"].get("TableName") == ALERTS_NAME
    ]
    assert matches == ["AlertsTable"]


def test_alerts_table_is_on_demand_with_no_provisioned_capacity():
    properties = _alerts_properties()
    assert properties["BillingMode"] == "PAY_PER_REQUEST"
    assert "ProvisionedThroughput" not in properties
    for index in properties["GlobalSecondaryIndexes"]:
        assert "ProvisionedThroughput" not in index


def test_alerts_table_key_is_alert_id_only():
    assert _alerts_properties()["KeySchema"] == [
        {"AttributeName": "alert_id", "KeyType": "HASH"}
    ]


def test_alerts_table_declares_exactly_the_key_attributes_as_strings():
    definitions = _alerts_properties()["AttributeDefinitions"]
    assert sorted(definitions, key=lambda item: item["AttributeName"]) == [
        {"AttributeName": name, "AttributeType": "S"}
        for name in ("alert_id", "created_at", "patient_rule", "status")
    ]


def test_gsi1_is_patient_rule_then_status():
    assert _indexes()["GSI1"]["KeySchema"] == [
        {"AttributeName": "patient_rule", "KeyType": "HASH"},
        {"AttributeName": "status", "KeyType": "RANGE"},
    ]


def test_gsi2_is_status_then_created_at():
    assert _indexes()["GSI2"]["KeySchema"] == [
        {"AttributeName": "status", "KeyType": "HASH"},
        {"AttributeName": "created_at", "KeyType": "RANGE"},
    ]


@pytest.mark.parametrize("index_name", ["GSI1", "GSI2"])
def test_index_projects_the_whole_alert(index_name):
    assert _indexes()[index_name]["Projection"] == {"ProjectionType": "ALL"}


def test_only_the_two_alerts_indexes_exist_in_the_template():
    found = []
    for logical_id, resource in _tables().items():
        properties = resource["Properties"]
        assert "LocalSecondaryIndexes" not in properties, logical_id
        for index in properties.get("GlobalSecondaryIndexes", []):
            found.append((logical_id, index["IndexName"]))
    assert sorted(found) == [("AlertsTable", "GSI1"), ("AlertsTable", "GSI2")]


def test_alert_history_is_never_expired():
    assert "TimeToLiveSpecification" not in _alerts_properties()


def _alert(suffix, patient_id, rule, status, created_at):
    return {
        "alert_id": "a-" + suffix * 32,
        "patient_id": patient_id,
        "rule": rule,
        "severity": "warning",
        "status": status,
        "patient_rule": f"{patient_id}#{rule}",
        "created_at": created_at,
        "acknowledged_by": None,
        "acknowledged_at": None,
        "resolved_at": None,
    }


# Inserted out of time order so that ordering comes from the index.
ACTIVE_LATER = _alert("1", "P002", "low_spo2", "active", "2026-11-17T14:22:05Z")
RESOLVED_SAME_KEY = _alert(
    "2", "P002", "low_spo2", "resolved", "2026-11-17T14:10:00Z"
)
ACTIVE_EARLIER = _alert("3", "P003", "fever", "active", "2026-11-17T14:20:00Z")
ACKNOWLEDGED = _alert(
    "4", "P001", "high_heart_rate", "acknowledged", "2026-11-17T14:21:00Z"
)


@pytest.fixture
def alerts_table(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    properties = _alerts_properties()
    with mock_aws():
        resource = boto3.resource("dynamodb", region_name="us-east-1")
        table = resource.create_table(
            TableName="patient-monitoring-unit-alerts",
            BillingMode=properties["BillingMode"],
            KeySchema=properties["KeySchema"],
            AttributeDefinitions=properties["AttributeDefinitions"],
            GlobalSecondaryIndexes=properties["GlobalSecondaryIndexes"],
        )
        for item in (ACTIVE_LATER, RESOLVED_SAME_KEY, ACTIVE_EARLIER, ACKNOWLEDGED):
            table.put_item(Item=item)
        yield table


def _suppression_query(table, patient_rule):
    return table.query(
        IndexName="GSI1",
        KeyConditionExpression=Key("patient_rule").eq(patient_rule)
        & Key("status").eq("active"),
    )["Items"]


def test_suppression_query_finds_only_the_active_alert(alerts_table):
    assert _suppression_query(alerts_table, "P002#low_spo2") == [ACTIVE_LATER]


def test_suppression_query_is_empty_without_an_active_alert(alerts_table):
    assert _suppression_query(alerts_table, "P002#fever") == []
    assert _suppression_query(alerts_table, "P001#high_heart_rate") == []


@pytest.mark.parametrize(
    "status, expected",
    [
        ("active", [ACTIVE_LATER, ACTIVE_EARLIER]),
        ("acknowledged", [ACKNOWLEDGED]),
        ("resolved", [RESOLVED_SAME_KEY]),
    ],
)
def test_status_listing_is_filtered_and_newest_first(alerts_table, status, expected):
    items = alerts_table.query(
        IndexName="GSI2",
        KeyConditionExpression=Key("status").eq(status),
        ScanIndexForward=False,
    )["Items"]
    assert items == expected
