"""Acceptance tests for INF-02: repository scaffold completion.

Static filesystem checks only. No network access, no AWS calls, no pip
invocation — a real `pip install -r requirements-dev.txt` is run by hand as
separate verification evidence, not asserted here (package-index
resolvability is not deterministic in a unit test).
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

EXISTING_SCAFFOLD_FILES = [
    REPO_ROOT / ".gitignore",
    REPO_ROOT / "CONTRIBUTING.md",
    REPO_ROOT / "README.md",
    REPO_ROOT / ".github" / "CODEOWNERS",
    REPO_ROOT / ".github" / "pull_request_template.md",
]

# Directory tree from docs/architecture.md §5 that is this task's gap.
# Each is an empty placeholder: a single ".gitkeep" file, no content, since
# the content belongs to a later task (ING-01, API-02, SIM-01, AUT-06/
# WEB-05/INF-05 per docs/architecture.md §8).
PLACEHOLDER_DIRS = [
    REPO_ROOT / "src" / "ingest",
    REPO_ROOT / "src" / "api",
    REPO_ROOT / "src" / "common",
    REPO_ROOT / "simulator",
    REPO_ROOT / "frontend" / "src" / "pages",
    REPO_ROOT / "frontend" / "src" / "components",
    REPO_ROOT / "frontend" / "src" / "auth",
    REPO_ROOT / "frontend" / "src" / "api",
]

REQUIREMENTS_DEV_PATH = REPO_ROOT / "requirements-dev.txt"
CODEOWNERS_PATH = REPO_ROOT / ".github" / "CODEOWNERS"


def test_existing_scaffold_files_present():
    for path in EXISTING_SCAFFOLD_FILES:
        assert path.is_file(), f"missing scaffold file: {path}"


def test_codeowners_has_no_placeholder():
    text = CODEOWNERS_PATH.read_text(encoding="utf-8")
    assert "REPLACE_WITH_GITHUB_USERNAME" not in text
    assert "@" in text


def test_placeholder_directories_exist_with_gitkeep():
    for directory in PLACEHOLDER_DIRS:
        gitkeep = directory / ".gitkeep"
        assert directory.is_dir(), f"missing directory: {directory}"
        assert gitkeep.is_file(), f"missing .gitkeep in: {directory}"


def test_requirements_dev_file_exists():
    assert REQUIREMENTS_DEV_PATH.is_file()


def test_requirements_dev_lists_exactly_the_decided_packages():
    lines = [
        line.strip()
        for line in REQUIREMENTS_DEV_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert lines == ["pytest", "boto3", "moto"]


def test_requirements_dev_cites_tst_01_for_the_mocking_decision():
    text = REQUIREMENTS_DEV_PATH.read_text(encoding="utf-8")
    assert "TST-01" in text
