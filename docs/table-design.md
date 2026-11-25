# DynamoDB Table Design

This document defines the DynamoDB table, key, and index design for the synthetic patient-monitoring application; it does not define endpoint implementation or other application behavior. Creating the tables is out of scope for this document and is handled by `DAT-02`–`DAT-04`. This project uses only synthetic data: patient IDs are invented and limited to `P001`, `P002`, and `P003`; it is an educational project, not a medical device; and thresholds and ranges are project settings, not clinical guidance.

## `patients`

This table stores one current-state item for each synthetic patient.

- Partition key: `patient_id` (`S`)
- Sort key: none

| Attribute | DynamoDB type | Meaning |
|---|---|---|
| `patient_id` | `S` | Identifier for one of the three fixed synthetic patients. |
| `device_id` | `S` | Simulated monitoring device that produced the latest reading. |
| `latest_reading_at` | `S` | ISO-8601 UTC timestamp with trailing `Z` for the latest reading used for current state. |
| `latest_reading_id` | `S` | Full identifier of the latest reading used for current state. |
| `heart_rate` | `N` | Latest heart rate in beats per minute. |
| `spo2` | `N` | Latest blood oxygen saturation percentage. |
| `temperature_c` | `N` | Latest temperature in degrees Celsius. |
| `systolic_bp` | `N` | Latest systolic blood pressure. |
| `diastolic_bp` | `N` | Latest diastolic blood pressure. |
| `status` | `S` | Current project status derived from the latest reading and alert evaluation. |
| `consecutive_abnormal` | `N` | Count of consecutive readings qualifying as abnormal for debounce tracking. |
| `consecutive_normal` | `N` | Count of consecutive readings qualifying as normal for debounce tracking. |

Example item:

```json
{
  "patient_id": "P002",
  "device_id": "DEV-P002-01",
  "latest_reading_at": "2026-11-17T14:22:03Z",
  "latest_reading_id": "r-8f3c1a2b9d4e4f1a8b6c2d9e0f1a2b3c",
  "heart_rate": 118,
  "spo2": 88,
  "temperature_c": 37.2,
  "systolic_bp": 142,
  "diastolic_bp": 91,
  "status": "critical",
  "consecutive_abnormal": 3,
  "consecutive_normal": 0
}
```

## `readings`

This table stores reading history.

- Partition key: `patient_id` (`S`)
- Sort key: `reading_time` (`S`)

The wire field `timestamp` maps to this table's `reading_time` sort key. They contain the same value, with different names at different layers. `reading_time` uses ISO-8601 UTC with a trailing `Z`, so lexical ordering is chronological ordering.

The sort key has only second resolution. Therefore, two distinct readings for the same patient in the same second would collide at the key. This limitation is inherited from `docs/architecture.md` §2.3, not a new design in this document. The simulator cadence mitigates it by emitting at most one reading per patient per batch/interval; this document assumes the simulator keeps per-patient reading intervals at one second or more. If that assumption changes, the key design here would need another look.

The `ConditionExpression attribute_not_exists(reading_id)` condition is evaluated only against the item at the specific `(patient_id, reading_time)` key. It therefore provides `reading_id` uniqueness at that key, not `reading_id` uniqueness across the table. This scope is inherited from the design in `docs/architecture.md` §2.5, rather than being a new decision here, and is sufficient for the exact retry case described there: the same reading, with the same `reading_id`, retried with the same `patient_id` and `reading_time`.

| Attribute | DynamoDB type | Meaning |
|---|---|---|
| `patient_id` | `S` | Identifier for the synthetic patient associated with the reading. |
| `reading_time` | `S` | Stored form of the wire `timestamp`, in ISO-8601 UTC with trailing `Z`; the sort key. |
| `reading_id` | `S` | Unique reading identifier: `r-` followed by 32 lowercase hexadecimal characters. |
| `device_id` | `S` | Simulated monitoring device that produced the reading. |
| `heart_rate` | `N` | Heart rate in beats per minute. |
| `spo2` | `N` | Blood oxygen saturation percentage. |
| `temperature_c` | `N` | Temperature in degrees Celsius. |
| `systolic_bp` | `N` | Systolic blood pressure. |
| `diastolic_bp` | `N` | Diastolic blood pressure. |
| `expires_at` | `N` | DynamoDB TTL value: Unix epoch integer seconds at which the retention window begins to expire. |

Example item:

```json
{
  "patient_id": "P002",
  "reading_time": "2026-11-17T14:22:03Z",
  "reading_id": "r-8f3c1a2b9d4e4f1a8b6c2d9e0f1a2b3c",
  "device_id": "DEV-P002-01",
  "heart_rate": 118,
  "spo2": 88,
  "temperature_c": 37.2,
  "systolic_bp": 142,
  "diastolic_bp": 91,
  "expires_at": 1795530123
}
```

## `alerts`

This table stores alert lifecycle records. The base-table primary key is `alert_id` alone, with no sort key. This supports the point lookup required by `PATCH /alerts/{alert_id}`; the two alert-list and suppression queries are served by the GSIs instead, so the base table does not need a range-query sort key.

- Partition key: `alert_id` (`S`)
- Sort key: none

| Attribute | DynamoDB type | Meaning |
|---|---|---|
| `alert_id` | `S` | Unique identifier for this alert lifecycle record. |
| `patient_id` | `S` | Synthetic patient associated with the alert. |
| `rule` | `S` | Alert rule identifier, such as `low_spo2` or `fever`. |
| `severity` | `S` | Project alert severity, such as `warning` or `critical`. |
| `status` | `S` | Lifecycle state: `active`, `acknowledged`, or `resolved`. |
| `patient_rule` | `S` | Composite value used by GSI1: `<patient_id>#<rule>`. |
| `created_at` | `S` | ISO-8601 UTC creation timestamp with trailing `Z`. |
| `acknowledged_by` | `S` or `NULL` | Signed-in user identifier when acknowledged; null while not acknowledged. |
| `acknowledged_at` | `S` or `NULL` | ISO-8601 UTC acknowledgement timestamp with trailing `Z`; null while not acknowledged. |
| `resolved_at` | `S` or `NULL` | ISO-8601 UTC resolution timestamp with trailing `Z`; null while not resolved. |

Example item:

```json
{
  "alert_id": "a-5d21e9",
  "patient_id": "P002",
  "rule": "low_spo2",
  "severity": "critical",
  "status": "active",
  "patient_rule": "P002#low_spo2",
  "created_at": "2026-11-17T14:22:05Z",
  "acknowledged_by": null,
  "acknowledged_at": null,
  "resolved_at": null
}
```

## GSIs on `alerts`

Only these two global secondary indexes exist on `alerts`.

### GSI1

- Partition key: `patient_rule` (`S`)
- Sort key: `status` (`S`)
- Query served: duplicate-active-alert suppression. Before creating an alert, query GSI1 with `patient_rule = <patient_id>#<rule>` and `status = active` to find an existing active alert for the same patient and rule.

### GSI2

- Partition key: `status` (`S`)
- Sort key: `created_at` (`S`)
- Query served: `GET /alerts?status=active` and the equivalent status-filtered dashboard listing. Query GSI2 with the requested `status`, ordered by `created_at`.

### `patient_rule` composite format

`patient_rule` is formatted as `<patient_id>#<rule>`. For example, `P002#low_spo2` identifies the low-oxygen rule for synthetic patient `P002`. The five valid `rule` values are:

- `low_spo2`
- `high_heart_rate`
- `fever`
- `abnormal_bp`
- `combination`

## TTL on `readings`

The TTL attribute is `readings.expires_at`, DynamoDB type `N`, containing Unix epoch integer seconds. The retention window is 7 days, so the writer sets `expires_at` to the reading timestamp plus `604800` seconds. Seven days matches `OPS-02`'s 7-day CloudWatch retention and is long enough for multi-day trend charts without allowing history to grow unbounded across the semester. DynamoDB TTL deletion is asynchronous; an item is not guaranteed to disappear exactly at the 7-day mark.

The `readings` example above uses `reading_time` `2026-11-17T14:22:03Z`, which is epoch `1794925323`; adding 604800 seconds produces the shown `expires_at` value `1795530123`.

## Access patterns

| Access pattern | Table or index | DynamoDB operation | Key or condition used |
|---|---|---|---|
| `POST /readings` — store each accepted reading | `readings` | `PutItem` | `patient_id` + `reading_time`, with `ConditionExpression attribute_not_exists(reading_id)` for idempotency. |
| `POST /readings` — update current state | `patients` | `UpdateItem` | `patient_id`, conditionally update only when the incoming `timestamp` is later than `latest_reading_at`. |
| Duplicate-active-alert suppression inside `POST /readings` | `alerts` GSI1 | `Query` | `patient_rule = <patient_id>#<rule>` and `status = active`. |
| `GET /patients` | `patients` | `Scan` | Read the bounded collection of at most three patient items. |
| `GET /patients/{patient_id}/readings` | `readings` | `Query` | Partition by `patient_id`; use the `reading_time` sort-key range for optional `start`/`end` bounds and the request limit. |
| `GET /alerts?status=` | `alerts` GSI2 | `Query` | Partition by requested `status`, ordered by `created_at`. |
| `PATCH /alerts/{alert_id}` | `alerts` base table | `GetItem` / `UpdateItem` | Point lookup and lifecycle update by `alert_id`. |

The `Scan` is acceptable only for `GET /patients` because the table is bounded at no more than three synthetic patient items. Reading history must use `Query` on `patient_id`; a `Scan` on `readings` is a defect.

## Billing and index rule

All three tables—`patients`, `readings`, and `alerts`—use DynamoDB on-demand billing. No further index may be added to any table without a template review; the only permitted secondary indexes in this design are GSI1 and GSI2 on `alerts`.
