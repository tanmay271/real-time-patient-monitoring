"""Acceptance tests for INF-04: CI workflow (sam validate + pytest on PR).

Static checks against .github/workflows/ci.yml. These tests cannot trigger
or observe a real GitHub Actions run; "the job passes" is verified
separately by running sam validate --lint and pytest locally, and by
watching the actual CI run on this task's PR. Branch-protection required
status checks are a GitHub setting, not something this file can check.
"""
import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"

# The no-secrets job's own regex, duplicated here (a GitHub Actions step
# isn't importable Python). Keep in sync with ci.yml's PATTERN variable.
GUARD_PATTERN = re.compile(
    r"[0-9]{12}|execute-api\.[a-z0-9-]+\.amazonaws\.com|us-east-1_[A-Za-z0-9]{9}"
)

# Fragment-built fixtures: no line below holds 12 consecutive digits or an
# unbroken execute-api/Cognito-pool substring, so this file won't trip the
# no-secrets job that greps the whole repo (ci.yml's no-secrets job).
_FAKE_ACCOUNT_ID = "1234" + "5678" + "9012"
_FAKE_INVOKE_URL = "abc123." + "execute-api." + "us-east-1" + ".amazonaws.com"
_FAKE_POOL_ID = "us-east-1_" + "AbCdEfGhI"


def load_workflow():
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    return text, yaml.safe_load(text)


def _triggers(workflow):
    # PyYAML's YAML-1.1 resolver parses the unquoted `on:` key as the
    # boolean True, not the string "on".
    return workflow.get("on", workflow.get(True))


def test_workflow_file_exists():
    assert WORKFLOW_PATH.is_file()


def test_triggers_on_pull_request_to_main():
    _, workflow = load_workflow()
    triggers = _triggers(workflow)
    assert triggers["pull_request"]["branches"] == ["main"]


def test_triggers_on_push_to_main():
    _, workflow = load_workflow()
    triggers = _triggers(workflow)
    assert triggers["push"]["branches"] == ["main"]


def test_no_job_level_hashfiles_if():
    # Regression guard: a job-level `if: hashFiles(...)` is rejected by
    # GitHub ("Unrecognized function: hashFiles"), which is why no job in
    # this workflow ever ran before INF-04.
    _, workflow = load_workflow()
    for job_name, job in workflow["jobs"].items():
        job_if = job.get("if") or ""
        assert "hashFiles(" not in job_if, (
            f"job {job_name!r} has hashFiles() in a job-level if:, which "
            "GitHub rejects"
        )


def test_validate_template_job_runs_sam_validate():
    _, workflow = load_workflow()
    job = workflow["jobs"]["validate-template"]
    assert job["runs-on"] == "ubuntu-latest"
    run_steps = " ".join(s.get("run", "") for s in job["steps"])
    assert "sam validate --lint" in run_steps
    assert "infra/template.yaml" in run_steps


def test_test_python_job_runs_pytest():
    _, workflow = load_workflow()
    job = workflow["jobs"]["test-python"]
    assert job["runs-on"] == "ubuntu-latest"
    run_steps = " ".join(s.get("run", "") for s in job["steps"])
    assert "requirements-dev.txt" in run_steps
    assert "pytest tests/unit" in run_steps


def test_no_secrets_job_runs_guard_script():
    _, workflow = load_workflow()
    job = workflow["jobs"]["no-secrets"]
    assert job["runs-on"] == "ubuntu-latest"
    run_steps = " ".join(s.get("run", "") for s in job["steps"])
    assert "grep" in run_steps
    assert "PATTERN" in run_steps


def test_build_frontend_job_is_step_level_conditional():
    # Regression guard for the fix: the frontend-exists check must live on
    # the steps, not the job (see test_no_job_level_hashfiles_if), while
    # frontend/ still has no package.json.
    _, workflow = load_workflow()
    job = workflow["jobs"]["build-frontend"]
    assert "if" not in job
    conditional_steps = [s for s in job["steps"] if "if" in s]
    assert conditional_steps, "expected at least one step-level if: in build-frontend"


def test_no_aws_credentials_referenced():
    text, _ = load_workflow()
    forbidden = [
        "aws-actions/configure-aws-credentials",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "secrets.AWS_",
    ]
    for token in forbidden:
        assert token not in text, f"found forbidden AWS credential reference: {token}"


def test_guard_pattern_matches_fake_identifiers():
    assert GUARD_PATTERN.search(_FAKE_ACCOUNT_ID)
    assert GUARD_PATTERN.search(_FAKE_INVOKE_URL)
    assert GUARD_PATTERN.search(_FAKE_POOL_ID)


def test_guard_pattern_ignores_benign_text():
    assert not GUARD_PATTERN.search("just some ordinary prose, no secrets here")
    assert not GUARD_PATTERN.search("12345678901")  # 11 digits, one short
