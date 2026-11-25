import argparse
import json
import random
import time
import uuid
from datetime import datetime, timezone


PATIENT_IDS = ["P001", "P002", "P003"]

BASELINES = {
    "P001": {
        "heart_rate": 72,
        "spo2": 98,
        "temperature_c": 36.7,
        "systolic_bp": 120,
        "diastolic_bp": 80,
    },
    "P002": {
        "heart_rate": 78,
        "spo2": 97,
        "temperature_c": 36.5,
        "systolic_bp": 125,
        "diastolic_bp": 82,
    },
    "P003": {
        "heart_rate": 68,
        "spo2": 99,
        "temperature_c": 36.9,
        "systolic_bp": 115,
        "diastolic_bp": 75,
    },
}


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now_utc().strftime("%Y-%m-%dT%H:%M:%SZ")


def _clamp(value: int | float, lower: int | float, upper: int | float) -> int | float:
    return max(lower, min(upper, value))


def generate_reading(patient_id: str) -> dict:
    baseline = BASELINES[patient_id]
    heart_rate = int(_clamp(baseline["heart_rate"] + random.randint(-4, 4), 30, 220))
    spo2 = int(_clamp(baseline["spo2"] + random.randint(-1, 1), 50, 100))
    systolic_bp = int(
        _clamp(baseline["systolic_bp"] + random.randint(-4, 4), 70, 200)
    )
    diastolic_bp = int(
        _clamp(baseline["diastolic_bp"] + random.randint(-3, 3), 40, 120)
    )
    diastolic_bp = min(diastolic_bp, systolic_bp - 1)

    temperature_c = baseline["temperature_c"] + random.uniform(-0.2, 0.2)
    temperature_c = round(float(_clamp(temperature_c, 34.0, 41.0)), 1)

    return {
        "reading_id": "r-" + uuid.uuid4().hex,
        "patient_id": patient_id,
        "device_id": f"DEV-{patient_id}-01",
        "timestamp": _now_iso(),
        "heart_rate": heart_rate,
        "spo2": spo2,
        "temperature_c": temperature_c,
        "systolic_bp": systolic_bp,
        "diastolic_bp": diastolic_bp,
    }


def generate_batch() -> dict:
    return {"readings": [generate_reading(patient_id) for patient_id in PATIENT_IDS]}


def main(argv=None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=["normal"], default="normal")
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument("--interval", type=float, default=5.0)
    args = parser.parse_args(argv)

    for iteration in range(args.iterations):
        print(json.dumps(generate_batch()))
        if iteration < args.iterations - 1:
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
