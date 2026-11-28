"""Acceptance tests for AUT-01 Cognito infrastructure."""

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_PATH = REPO_ROOT / "infra" / "template.yaml"


class _CfnTagLoader(yaml.SafeLoader):
    """Load CloudFormation intrinsic tags as ordinary dictionaries."""


def _construct_cfn_tag(loader, tag_suffix, node):
    if isinstance(node, yaml.ScalarNode):
        value = loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        value = loader.construct_sequence(node)
    else:
        value = loader.construct_mapping(node)

    return {f"Fn::{tag_suffix}": value}


_CfnTagLoader.add_multi_constructor("!", _construct_cfn_tag)


def load_template():
    text = TEMPLATE_PATH.read_text(encoding="utf-8")
    return yaml.load(text, Loader=_CfnTagLoader)


def test_user_pool_uses_email_and_disables_self_signup():
    resources = load_template()["Resources"]
    user_pool = resources["UserPool"]

    assert user_pool["Type"] == "AWS::Cognito::UserPool"

    properties = user_pool["Properties"]
    assert properties["UserPoolName"] == {
        "Fn::Sub": "patient-monitoring-${Env}-users"
    }
    assert properties["UsernameAttributes"] == ["email"]
    assert properties["AdminCreateUserConfig"]["AllowAdminCreateUserOnly"] is True


def test_user_pool_has_strong_password_policy():
    properties = load_template()["Resources"]["UserPool"]["Properties"]
    policy = properties["Policies"]["PasswordPolicy"]

    assert policy["MinimumLength"] >= 12
    assert policy["RequireLowercase"] is True
    assert policy["RequireUppercase"] is True
    assert policy["RequireNumbers"] is True
    assert policy["RequireSymbols"] is True


def test_app_client_has_no_secret():
    resources = load_template()["Resources"]
    client = resources["UserPoolClient"]

    assert client["Type"] == "AWS::Cognito::UserPoolClient"

    properties = client["Properties"]
    assert properties["UserPoolId"] == {"Fn::Ref": "UserPool"}
    assert properties["GenerateSecret"] is False


def test_cognito_stack_outputs_are_present():
    outputs = load_template()["Outputs"]

    assert outputs["CognitoUserPoolId"]["Value"] == {
        "Fn::Ref": "UserPool"
    }
    assert outputs["CognitoUserPoolClientId"]["Value"] == {
        "Fn::Ref": "UserPoolClient"
    }
    assert outputs["CognitoIssuerUrl"]["Value"] == {
        "Fn::Sub": (
            "https://cognito-idp.${AWS::Region}."
            "${AWS::URLSuffix}/${UserPool}"
        )
    }