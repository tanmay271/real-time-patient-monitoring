"""Acceptance tests for SIM-01: core generator, 3 patients, JSON batch to stdout.

Static/behavioral checks against simulator/simulator.py. Imports the module
directly off disk (no package, matches the test_infra_template.py /
test_repo_scaffold.py convention) and runs one subprocess invocation for the
CLI-shape criterion. No AWS calls, no real network access.
"""
import ast
import importlib.util
import json
import re
import subprocess
import sys
from datetime import timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SIMULATOR_PATH = REPO_ROOT / "simulator" / "simulator.py"

TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

FIELD_NAMES = {
    "reading_id",
    "patient_id",
    "device_id",
    "timestamp",
    "heart_rate",
    "spo2",
    "temperature_c",
    "systolic_bp",
    "diastolic_bp",
}

PATIENT_IDS = {"P001", "P002", "P003"}

ALLOWED_IMPORT_MODULES = {
    "argparse",
    "json",
    "random",
    "uuid",
    "time",
    "datetime",
    "sys",
}


def _load_simulator_module():
    spec = importlib.util.spec_from_file_location("simulator", SIMULATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


simulator = _load_simulator_module()


def test_generate_batch_envelope_shape():
    batch = simulator.generate_batch()
    assert set(batch.keys()) == {"readings"}
    assert isinstance(batch["readings"], list)
    assert len(batch["readings"]) == 3
    assert {r["patient_id"] for r in batch["readings"]} == PATIENT_IDS


def test_reading_has_exactly_the_nine_dat00_fields():
    batch = simulator.generate_batch()
    for reading in batch["readings"]:
        assert set(reading.keys()) == FIELD_NAMES


def test_reading_field_types_and_ranges():
    readings = []
    for _ in range(50):
        readings.extend(simulator.generate_batch()["readings"])

    for reading in readings:
        assert isinstance(reading["reading_id"], str)
        assert isinstance(reading["patient_id"], str)
        assert isinstance(reading["device_id"], str)
        assert isinstance(reading["timestamp"], str)

        assert isinstance(reading["heart_rate"], int)
        assert 30 <= reading["heart_rate"] <= 220

        assert isinstance(reading["spo2"], int)
        assert 50 <= reading["spo2"] <= 100

        assert isinstance(reading["temperature_c"], float)
        assert 34.0 <= reading["temperature_c"] <= 41.0

        assert isinstance(reading["systolic_bp"], int)
        assert 70 <= reading["systolic_bp"] <= 200

        assert isinstance(reading["diastolic_bp"], int)
        assert 40 <= reading["diastolic_bp"] <= 120


def test_temperature_has_exactly_one_decimal_place():
    readings = []
    for _ in range(50):
        readings.extend(simulator.generate_batch()["readings"])

    for reading in readings:
        value = reading["temperature_c"]
        assert round(value, 1) == value


def test_reading_id_format():
    batch = simulator.generate_batch()
    for reading in batch["readings"]:
        assert re.fullmatch(r"r-[0-9a-f]{32}", reading["reading_id"])


def test_device_id_format():
    batch = simulator.generate_batch()
    for reading in batch["readings"]:
        assert re.fullmatch(
            rf"DEV-{reading['patient_id']}-\d{{2}}", reading["device_id"]
        )


def test_diastolic_less_than_systolic_in_every_reading():
    for _ in range(50):
        for reading in simulator.generate_batch()["readings"]:
            assert reading["diastolic_bp"] < reading["systolic_bp"]


def test_reading_id_unique_across_100_iteration_run():
    reading_ids = set()
    for _ in range(100):
        for reading in simulator.generate_batch()["readings"]:
            reading_ids.add(reading["reading_id"])
    assert len(reading_ids) == 300


def test_timestamp_format_ends_in_z():
    batch = simulator.generate_batch()
    for reading in batch["readings"]:
        assert TIMESTAMP_RE.match(reading["timestamp"])


def test_timestamp_source_is_timezone_aware_utc():
    now = simulator._now_utc()
    assert now.tzinfo is timezone.utc


def test_cli_emits_two_batches_of_three_patients():
    result = subprocess.run(
        [
            sys.executable,
            str(SIMULATOR_PATH),
            "--scenario",
            "normal",
            "--iterations",
            "2",
            "--interval",
            "0",
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert len(lines) == 2
    for line in lines:
        batch = json.loads(line)
        assert set(batch.keys()) == {"readings"}
        assert len(batch["readings"]) == 3
        assert {r["patient_id"] for r in batch["readings"]} == PATIENT_IDS


def test_cli_rejects_unknown_scenario():
    result = subprocess.run(
        [
            sys.executable,
            str(SIMULATOR_PATH),
            "--scenario",
            "falling_oxygen",
            "--iterations",
            "1",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode != 0


def test_no_aws_sdk_or_network_imports():
    source = SIMULATOR_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top_level = alias.name.split(".")[0]
                assert top_level in ALLOWED_IMPORT_MODULES, (
                    f"unexpected import: {alias.name}"
                )
        elif isinstance(node, ast.ImportFrom):
            if node.module is not None:
                top_level = node.module.split(".")[0]
                assert top_level in ALLOWED_IMPORT_MODULES, (
                    f"unexpected import: {node.module}"
                )
