# Patient Vital-Sign Reading Data Dictionary

> **Synthetic and educational project disclaimer:** This project uses only synthetic data. Patient IDs are invented and limited to `P001`, `P002`, and `P003`. This is an educational project, not a medical device; the thresholds and ranges in this document are project settings, not clinical guidance.

## Batch envelope

Each ingestion payload is a JSON object with one key, `readings`, whose value
is an array of reading objects:

```json
{ "readings": [ ... ] }
```

The `readings` array must contain **1 to 50 readings inclusive**. An empty or
missing `readings` array is rejected at ingestion. Normal traffic is three
readings per batch, one for each patient; the limit of 50 provides bounded
headroom for a device catching up after a pause.

## Reading fields

All nine fields are required and non-nullable on every reading object. There
are no optional fields in this version of the contract.

| Name | JSON type | Unit | Valid range / format | Nullable | Required | Meaning |
|---|---|---|---|---|---|---|
| `reading_id` | string | — | Literal prefix `r-` followed by a 32-character lowercase hexadecimal string (a UUID4 with dashes removed); unique per reading. Example: `r-8f3c1a2b9d4e4f1a8b6c2d9e0f1a2b3c`. | false | true | Unique identifier for this single reading, used for idempotent writes. |
| `patient_id` | string | — | Enum: `P001` \| `P002` \| `P003` | false | true | Identifies which of the three fixed synthetic patients this reading belongs to. |
| `device_id` | string | — | `DEV-<patient_id>-NN`, where `NN` is a zero-padded two-digit device number; for example, `DEV-P002-01`. | false | true | Identifies the simulated monitoring device that produced the reading. |
| `timestamp` | string | ISO-8601 UTC | ISO-8601 UTC with a trailing `Z`; for example, `2026-11-17T14:22:03Z`. | false | true | Identifies when the reading was taken by the device clock, not when it was received by the server. |
| `heart_rate` | integer | bpm | 30–220 inclusive | false | true | Heart rate in beats per minute. |
| `spo2` | integer | percent | 50–100 inclusive | false | true | Blood oxygen saturation percentage. |
| `temperature_c` | number | degrees Celsius | 34.0–41.0 inclusive; exactly one decimal place | false | true | Body temperature in Celsius. |
| `systolic_bp` | integer | mmHg | 70–200 inclusive | false | true | Systolic blood pressure. |
| `diastolic_bp` | integer | mmHg | 40–120 inclusive, and strictly less than `systolic_bp` on the same reading | false | true | Diastolic blood pressure. |

### Field notes

- The shorter example `r-8f3c1a` in `docs/architecture.md` is an abbreviated
  illustration only, not the literal format. The full 32-hex-character format
  in this dictionary is authoritative for implementation. Idempotent writes
  use the `reading_id` uniqueness condition (`attribute_not_exists(reading_id)`).
- `timestamp` is the wire/API field name. `docs/architecture.md` separately
  names the DynamoDB sort-key attribute for the readings table `reading_time`
  (see its section 13, "Timestamps"). `reading_time` is an internal storage
  attribute name decided under task DAT-01, not a different field, and is out of
  scope for this dictionary.
- The `heart_rate` range admits the `high_heart_rate` scenario's critical alert
  threshold of ≥130 bpm with headroom.
- The `spo2` range admits the `falling_oxygen` scenario's critical alert
  threshold of ≤89% with headroom and matches the range used in the project's
  invalid-reading example.
- The `temperature_c` range admits the `fever` scenario's critical alert
  threshold of ≥39.0°C with headroom while staying physiologically plausible.
- Unlike the other three vital fields, neither BP field is specifically driven
  by the four simulator scenarios (`normal`, `falling_oxygen`,
  `high_heart_rate`, and `fever`). Their ranges are set from physiological
  plausibility plus the `abnormal_bp` alert thresholds alone, not from a named
  scenario.

### Blood-pressure invariant

`diastolic_bp` must always be **strictly less than** `systolic_bp` on the same
reading. A reading where `diastolic_bp >= systolic_bp` is invalid, even when
both values are individually within their listed ranges.

## Required versus optional fields

All 9 fields listed above are required on every reading object, and all 9 are
non-nullable. There are no optional fields in this version of the contract.

## Scenario and alert-rule coverage

The ranges below are validity ranges, not alert decision boundaries. Every
numeric alert threshold is strictly inside the corresponding validity range,
so the simulator can produce valid readings that are warning or critical.

| Scenario or alert rule | Relevant threshold or expected coverage | Dictionary range check |
|---|---|---|
| `normal` scenario | Generates ordinary in-range values for all nine fields. | All numeric fields have room for ordinary values strictly inside their ranges; BP readings also observe `diastolic_bp < systolic_bp`. |
| `falling_oxygen` scenario | Drives `spo2` down to the critical `low_spo2` threshold of ≤89%. | `89` is strictly inside `50–100`. The warning threshold `92` is also strictly inside `50–100`. |
| `high_heart_rate` scenario | Drives `heart_rate` up to the critical threshold of ≥130 bpm. | `130` is strictly inside `30–220`. The warning threshold `110` is also strictly inside `30–220`. |
| `fever` scenario | Drives `temperature_c` up to the critical threshold of ≥39.0°C. | `39.0` is strictly inside `34.0–41.0`. The warning threshold `38.0` is also strictly inside `34.0–41.0`. |
| `low_spo2` alert rule | Warning ≤92%; critical ≤89%. | Both thresholds are strictly inside `spo2` range `50–100`. |
| `high_heart_rate` alert rule | Warning ≥110 bpm; critical ≥130 bpm. | Both thresholds are strictly inside `heart_rate` range `30–220`. |
| `fever` alert rule | Warning ≥38.0°C; critical ≥39.0°C. | Both thresholds are strictly inside `temperature_c` range `34.0–41.0`. |
| `abnormal_bp` alert rule | Warning: systolic ≥140 or diastolic ≥90; critical: systolic ≥160 or diastolic ≥100. | Systolic thresholds `140` and `160` are strictly inside `70–200`; diastolic thresholds `90` and `100` are strictly inside `40–120`. |
| `combination` alert rule | Fires when two or more warning rules are present concurrently. | It combines the warning thresholds above; each contributing threshold is strictly inside its field's stated range. |
