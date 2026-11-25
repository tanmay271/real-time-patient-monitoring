"""Acceptance tests for ING-01: handler skeleton, table env vars, execution role.

Derived from docs/architecture.md section 8 (ING-01 row), sections 2.3, 4.2
and 5, docs/api.md (error envelope, POST /readings) and docs/table-design.md
(access patterns). Static template checks and direct handler calls only; no AWS
calls. sam validate --lint and a real deploy are run separately.
"""
import ast
import importlib
import json
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_PATH = REPO_ROOT / "infra" / "template.yaml"
SRC_PATH = REPO_ROOT / "src"
HANDLER_PATH = SRC_PATH / "ingest" / "handler.py"

BASIC_EXECUTION_POLICY = {
    "Fn::Sub": (
        "arn:${AWS::Partition}:iam::aws:policy/service-role/"
        "AWSLambdaBasicExecutionRole"
    )
}


class _CfnTagLoader(yaml.SafeLoader):
    pass


def _construct_cfn_tag(loader, tag_suffix, node):
    key = "Ref" if tag_suffix == "Ref" else f"Fn::{tag_suffix}"
    if isinstance(node, yaml.ScalarNode):
        return {key: loader.construct_scalar(node)}
    if isinstance(node, yaml.SequenceNode):
        return {key: loader.construct_sequence(node, deep=True)}
    return {key: loader.construct_mapping(node, deep=True)}


_CfnTagLoader.add_multi_constructor("!", _construct_cfn_tag)


def load_template():
    text = TEMPLATE_PATH.read_text(encoding="utf-8")
    return yaml.load(text, Loader=_CfnTagLoader)


def _resource(logical_id):
    resources = load_template()["Resources"]
    assert logical_id in resources, f"{logical_id} resource is missing"
    return resources[logical_id]


def _function_properties():
    return _resource("IngestFunction")["Properties"]


def _role_properties():
    return _resource("IngestRole")["Properties"]


def _as_list(value):
    return value if isinstance(value, list) else [value]


@pytest.fixture
def handler(monkeypatch):
    monkeypatch.syspath_prepend(str(SRC_PATH))
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    for name in ("ingest.handler", "ingest"):
        sys.modules.pop(name, None)
    yield importlib.import_module("ingest.handler")
    for name in ("ingest.handler", "ingest"):
        sys.modules.pop(name, None)


@pytest.fixture
def table_env(monkeypatch):
    monkeypatch.setenv("PATIENTS_TABLE", "example-patients")
    monkeypatch.setenv("READINGS_TABLE", "example-readings")


# Handler skeleton


def test_handler_file_exists():
    assert HANDLER_PATH.is_file()


def test_handler_exposes_lambda_entry_point(handler):
    assert callable(handler.lambda_handler)


def _assert_not_implemented_response(response):
    assert response["statusCode"] == 500
    assert response["headers"]["Content-Type"] == "application/json"
    assert json.loads(response["body"]) == {
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "ingestion is not implemented yet",
        }
    }


def test_skeleton_returns_error_envelope(handler, table_env):
    event = {"body": json.dumps({"readings": []})}
    _assert_not_implemented_response(handler.lambda_handler(event, None))


@pytest.mark.parametrize("missing", ["PATIENTS_TABLE", "READINGS_TABLE"])
def test_skeleton_returns_error_envelope_when_a_table_variable_is_missing(
    handler, table_env, monkeypatch, missing
):
    monkeypatch.delenv(missing)
    _assert_not_implemented_response(handler.lambda_handler({}, None))


def test_table_names_come_from_environment(handler, table_env, monkeypatch):
    names = handler.table_names()
    assert names == {
        "patients": "example-patients",
        "readings": "example-readings",
    }
    monkeypatch.setenv("READINGS_TABLE", "other-readings")
    assert handler.table_names()["readings"] == "other-readings"


@pytest.mark.parametrize("missing", ["PATIENTS_TABLE", "READINGS_TABLE"])
def test_table_names_fails_loudly_without_a_variable(
    handler, table_env, monkeypatch, missing
):
    monkeypatch.delenv(missing)
    with pytest.raises(KeyError):
        handler.table_names()


def test_no_table_name_literal_in_source():
    sources = list(SRC_PATH.rglob("*.py"))
    assert sources, "no Python source under src/"
    for path in sources:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert "patient-monitoring-" not in node.value, str(path)


# Function resource


def test_function_is_a_serverless_function():
    assert _resource("IngestFunction")["Type"] == "AWS::Serverless::Function"


def test_function_name_uses_fn_sub_with_env():
    assert _function_properties()["FunctionName"] == {
        "Fn::Sub": "patient-monitoring-${Env}-ingest"
    }


def test_function_code_root_and_handler():
    properties = _function_properties()
    assert properties["CodeUri"] == "../src/"
    assert properties["Handler"] == "ingest.handler.lambda_handler"


def test_function_inherits_runtime_timeout_and_memory_from_globals():
    properties = _function_properties()
    for key in ("Runtime", "Timeout", "MemorySize"):
        assert key not in properties


def test_function_environment_references_both_tables():
    assert _function_properties()["Environment"]["Variables"] == {
        "PATIENTS_TABLE": {"Ref": "PatientsTable"},
        "READINGS_TABLE": {"Ref": "ReadingsTable"},
    }


def test_function_has_no_event_sources():
    assert "Events" not in _function_properties()


# Execution role


def test_function_uses_the_dedicated_role():
    properties = _function_properties()
    assert properties["Role"] == {"Fn::GetAtt": "IngestRole.Arn"}
    assert "Policies" not in properties


def test_role_is_an_iam_role_without_explicit_name():
    assert _resource("IngestRole")["Type"] == "AWS::IAM::Role"
    assert "RoleName" not in _role_properties()


def test_role_is_assumable_only_by_lambda():
    statements = _role_properties()["AssumeRolePolicyDocument"]["Statement"]
    assert len(statements) == 1
    statement = statements[0]
    assert statement["Effect"] == "Allow"
    assert statement["Principal"] == {"Service": "lambda.amazonaws.com"}
    assert _as_list(statement["Action"]) == ["sts:AssumeRole"]


def test_role_attaches_only_basic_execution_managed_policy():
    assert _role_properties()["ManagedPolicyArns"] == [BASIC_EXECUTION_POLICY]


def test_role_inline_policy_name_uses_env():
    policies = _role_properties()["Policies"]
    assert len(policies) == 1
    assert policies[0]["PolicyName"] == {
        "Fn::Sub": "patient-monitoring-${Env}-ingest-tables"
    }


def test_role_inline_policy_grants_exactly_the_ingest_table_actions():
    statements = _role_properties()["Policies"][0]["PolicyDocument"]["Statement"]
    grants = []
    for statement in statements:
        assert statement["Effect"] == "Allow"
        assert "NotAction" not in statement
        assert "NotResource" not in statement
        for action in _as_list(statement["Action"]):
            for resource in _as_list(statement["Resource"]):
                grants.append((action, json.dumps(resource, sort_keys=True)))
    assert sorted(grants) == sorted(
        [
            (
                "dynamodb:PutItem",
                json.dumps({"Fn::GetAtt": "ReadingsTable.Arn"}),
            ),
            (
                "dynamodb:UpdateItem",
                json.dumps({"Fn::GetAtt": "PatientsTable.Arn"}),
            ),
        ]
    )


# Scope


def test_no_resources_belonging_to_other_tasks():
    types = {r["Type"] for r in load_template()["Resources"].values()}
    for forbidden in (
        "AWS::Serverless::HttpApi",
        "AWS::Serverless::Api",
        "AWS::ApiGatewayV2::Api",
        "AWS::Logs::LogGroup",
    ):
        assert forbidden not in types
