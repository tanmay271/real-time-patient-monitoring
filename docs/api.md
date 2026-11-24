# API Contract

This API uses only synthetic data. Patient IDs are invented and limited to `P001`–`P003`; this is an educational project, not a medical device, and its thresholds and ranges are project settings, not medical guidance. This document is the authoritative wire contract; `docs/architecture.md` §3 is only an outline. Any PR changing an endpoint must update this file in the same PR.

## Conventions

- Base URL: `https://{api-id}.execute-api.us-east-1.amazonaws.com`
- All timestamps use ISO-8601 UTC with a trailing `Z`, for example `2026-11-17T14:22:03Z`, as specified in `docs/data-dictionary.md`.
- Every non-2xx response from every route uses exactly this envelope, with no extra fields:

  ```json
  { "error": { "code": "INVALID_READING", "message": "spo2 must be between 50 and 100" } }
  ```

  `code` is stable SCREAMING_SNAKE. `message` is safe to display and never contains a stack trace, table name, ARN, or account ID.
- Status codes used anywhere in this API: `400` invalid input, `401` missing or invalid credentials, `403` valid credentials with insufficient permission, `404` missing record, and `500` unexpected failure. No other status code is used.
- Cognito JWT routes use `Authorization: Bearer <token>`.
- `POST /readings` uses AWS SigV4 request signing (IAM), not a Cognito JWT. It does not accept a Cognito JWT because the simulator is not an interactive browser client. API keys are not used because this project uses an HTTP API and API keys require a REST API.

## Error codes

| code | HTTP status / location | route(s) | meaning |
|---|---|---|---|
| `INVALID_BATCH` | 400 envelope | `POST /readings` | request body is not valid JSON, `readings` is missing or not an array, or array length is outside 1–50 |
| `INVALID_READING` | 200 body, per-item in `errors[]` (not an envelope code) | `POST /readings` | one reading in an otherwise-valid batch fails a field type, range, format, or enum check, including violating the invariant `diastolic_bp < systolic_bp` (i.e. `diastolic_bp >= systolic_bp`) |
| `INVALID_QUERY_PARAM` | 400 envelope | `GET /patients/{patient_id}/readings`, `GET /alerts` | bad `limit`, bad `start`/`end`, or unrecognized `status` value |
| `INVALID_ACTION` | 400 envelope | `PATCH /alerts/{alert_id}` | `action` is missing or is not `acknowledge`/`resolve` |
| `INVALID_ALERT_TRANSITION` | 400 envelope | `PATCH /alerts/{alert_id}` | `acknowledge` is used on a non-`active` alert, or `resolve` is used on a non-`acknowledged` alert |
| `UNAUTHENTICATED` | 401 envelope | all protected routes | missing or invalid credentials |
| `FORBIDDEN` | 403 envelope | all protected routes | valid credentials, insufficient permission |
| `NOT_FOUND` | 404 envelope | `GET /patients/{patient_id}/readings`, `PATCH /alerts/{alert_id}` | unknown `patient_id` or `alert_id` |
| `INTERNAL_ERROR` | 500 envelope | any route | unexpected failure |

`INVALID_READING` is the one code in this list that never appears in the `{error:{...}}` envelope. It appears inside a 200 success response, once per failed reading.

## `connection_state`

`connection_state` has three values: `connected`, `delayed`, and `disconnected`. Based on `latest_reading_at`, the thresholds are `< 15s` for `connected`, `15–30s` for `delayed`, and `> 30s` for `disconnected`. It is derived at read time in the API Lambda from `latest_reading_at` and is never stored, per `docs/architecture.md` §2.5.

## `POST /readings`

**Method and path:** `POST /readings`

**Auth:** AWS SigV4 request signing (IAM). This route does not accept a Cognito JWT.

**Query parameters:** None.

**Path parameters:** None.

**Request body:** `readings` is an array of 1–50 reading objects. Each object has exactly the nine required data-dictionary fields: `reading_id`, `patient_id`, `device_id`, `timestamp`, `heart_rate`, `spo2`, `temperature_c`, `systolic_bp`, and `diastolic_bp`.

```json
{
  "readings": [
    {
      "reading_id": "r-8f3c1a2b9d4e4f1a8b6c2d9e0f1a2b3c",
      "patient_id": "P001",
      "device_id": "DEV-P001-01",
      "timestamp": "2026-11-17T14:22:03Z",
      "heart_rate": 72,
      "spo2": 98,
      "temperature_c": 36.7,
      "systolic_bp": 118,
      "diastolic_bp": 76
    },
    {
      "reading_id": "r-1a2b3c4d5e6f7890a1b2c3d4e5f67890",
      "patient_id": "P002",
      "device_id": "DEV-P002-01",
      "timestamp": "2026-11-17T14:22:04Z",
      "heart_rate": 118,
      "spo2": 92,
      "temperature_c": 37.2,
      "systolic_bp": 142,
      "diastolic_bp": 91
    },
    {
      "reading_id": "r-abcdef0123456789abcdef0123456789",
      "patient_id": "P003",
      "device_id": "DEV-P003-01",
      "timestamp": "2026-11-17T14:22:05Z",
      "heart_rate": 84,
      "spo2": 97,
      "temperature_c": 38.0,
      "systolic_bp": 130,
      "diastolic_bp": 82
    }
  ]
}
```

**Success: `200 OK`** for every structurally valid batch:

```json
{
  "accepted": 2,
  "rejected": 1,
  "duplicate": 0,
  "errors": [
    { "index": 2, "code": "INVALID_READING", "message": "readings[2].spo2 must be between 50 and 100" }
  ]
}
```

`accepted` + `rejected` + `duplicate` always equals the number of submitted readings. `errors` is empty when `rejected` is `0`. `index` is the zero-based position in the submitted `readings` array. A duplicate `reading_id` from an idempotent re-send counts toward `duplicate`, not `rejected`, and is not invalid.

All-new, all-valid example:

```json
{
  "accepted": 3,
  "rejected": 0,
  "duplicate": 0,
  "errors": []
}
```

**Errors:**

- `400 INVALID_BATCH` when the body is not valid JSON, `readings` is missing or not an array, or the array is empty or has 51 items. Example:

  ```json
  { "error": { "code": "INVALID_BATCH", "message": "readings must contain between 1 and 50 items" } }
  ```

Malformed or missing SigV4 signing produces `401 UNAUTHENTICATED` using the standard envelope, as for any other protected route. `403 FORBIDDEN` and `500 INTERNAL_ERROR` also use the standard envelope.

## `GET /patients`

**Method and path:** `GET /patients`

**Auth:** Cognito JWT: `Authorization: Bearer <token>`.

**Query parameters:** None.

**Path parameters:** None.

**Request body:** None.

**Success: `200 OK`:** An array of exactly three objects, one per patient.

```json
[
  {
    "patient_id": "P001",
    "device_id": "DEV-P001-01",
    "latest_reading_at": "2026-11-17T14:22:03Z",
    "heart_rate": 72,
    "spo2": 98,
    "temperature_c": 36.7,
    "systolic_bp": 118,
    "diastolic_bp": 76,
    "status": "normal",
    "connection_state": "connected"
  },
  {
    "patient_id": "P002",
    "device_id": "DEV-P002-01",
    "latest_reading_at": "2026-11-17T14:21:48Z",
    "heart_rate": 118,
    "spo2": 92,
    "temperature_c": 37.2,
    "systolic_bp": 142,
    "diastolic_bp": 91,
    "status": "warning",
    "connection_state": "delayed"
  },
  {
    "patient_id": "P003",
    "device_id": "DEV-P003-01",
    "latest_reading_at": "2026-11-17T14:21:20Z",
    "heart_rate": 84,
    "spo2": 97,
    "temperature_c": 38.0,
    "systolic_bp": 130,
    "diastolic_bp": 82,
    "status": "critical",
    "connection_state": "disconnected"
  }
]
```

`status` values are `normal`, `warning`, and `critical`, set by `ALR-01`'s thresholds. `consecutive_abnormal`, `consecutive_normal`, and `latest_reading_id` are internal alert-debounce bookkeeping and are not part of this response.

**Errors:** `401 UNAUTHENTICATED`, `403 FORBIDDEN`, and `500 INTERNAL_ERROR`, each using the standard envelope. For example:

```json
{ "error": { "code": "UNAUTHENTICATED", "message": "authentication is required" } }
```

## `GET /patients/{patient_id}/readings`

**Method and path:** `GET /patients/{patient_id}/readings`

**Auth:** Cognito JWT: `Authorization: Bearer <token>`.

**Query parameters:**

| name | type | default | cap / constraint |
|---|---|---|---|
| `limit` | integer | `100` | `1`–`500` inclusive; values over `500` are invalid |
| `start` | ISO-8601 UTC string | none | optional, inclusive; must end in `Z` |
| `end` | ISO-8601 UTC string | none | optional, inclusive; must end in `Z` |

`start` and `end` may be given together, either alone, or neither.

**Path parameters:** `patient_id`, one of `P001`, `P002`, or `P003`.

**Request body:** None.

**Success: `200 OK`:** An array of full reading objects, with only the nine data-dictionary fields, ordered newest first.

```json
[
  {
    "reading_id": "r-00112233445566778899aabbccddeeff",
    "patient_id": "P001",
    "device_id": "DEV-P001-01",
    "timestamp": "2026-11-17T14:22:05Z",
    "heart_rate": 84,
    "spo2": 97,
    "temperature_c": 38.0,
    "systolic_bp": 130,
    "diastolic_bp": 82
  },
  {
    "reading_id": "r-8f3c1a2b9d4e4f1a8b6c2d9e0f1a2b3c",
    "patient_id": "P001",
    "device_id": "DEV-P001-01",
    "timestamp": "2026-11-17T14:22:03Z",
    "heart_rate": 72,
    "spo2": 98,
    "temperature_c": 36.7,
    "systolic_bp": 118,
    "diastolic_bp": 76
  }
]
```

**Errors:**

- `400 INVALID_QUERY_PARAM` for a bad `limit`, `limit` ≤ 0 or > 500, or an invalid `start`/`end` format. Example: `{ "error": { "code": "INVALID_QUERY_PARAM", "message": "limit must be between 1 and 500" } }`.
- `401 UNAUTHENTICATED`: `{ "error": { "code": "UNAUTHENTICATED", "message": "authentication is required" } }`.
- `403 FORBIDDEN`: `{ "error": { "code": "FORBIDDEN", "message": "permission denied" } }`.
- `404 NOT_FOUND` for an unknown `patient_id`: `{ "error": { "code": "NOT_FOUND", "message": "patient not found" } }`.
- `500 INTERNAL_ERROR`: `{ "error": { "code": "INTERNAL_ERROR", "message": "unexpected failure" } }`.

## `GET /alerts`

**Method and path:** `GET /alerts`

**Auth:** Cognito JWT: `Authorization: Bearer <token>`.

**Query parameters:**

| name | type | default | cap / constraint |
|---|---|---|---|
| `status` | string | all three statuses | optional; one of `active`, `acknowledged`, or `resolved` |
| `limit` | integer | `100` | `1`–`500` inclusive |

**Path parameters:** None.

**Request body:** None.

**Success: `200 OK`:** Alert objects are ordered by `created_at` descending. `patient_rule` (the GSI1 key) is not part of the response. Severity-first ordering for an active-alert panel is a client-side concern and is not guaranteed by this route.

```json
[
  {
    "alert_id": "a-5d21e9ab34cd56ef7890ab12cd34ef56",
    "patient_id": "P002",
    "rule": "low_spo2",
    "severity": "critical",
    "status": "active",
    "created_at": "2026-11-17T14:22:10Z",
    "acknowledged_by": null,
    "acknowledged_at": null,
    "resolved_at": null
  },
  {
    "alert_id": "a-1234567890abcdef1234567890abcdef",
    "patient_id": "P003",
    "rule": "fever",
    "severity": "warning",
    "status": "resolved",
    "created_at": "2026-11-17T14:20:00Z",
    "acknowledged_by": "operator@example.test",
    "acknowledged_at": "2026-11-17T14:20:30Z",
    "resolved_at": "2026-11-17T14:22:00Z"
  }
]
```

**Errors:**

- `400 INVALID_QUERY_PARAM` for an unrecognized `status` or bad `limit`. Example: `{ "error": { "code": "INVALID_QUERY_PARAM", "message": "status must be active, acknowledged, or resolved" } }`.
- `401 UNAUTHENTICATED`: `{ "error": { "code": "UNAUTHENTICATED", "message": "authentication is required" } }`.
- `403 FORBIDDEN`: `{ "error": { "code": "FORBIDDEN", "message": "permission denied" } }`.
- `500 INTERNAL_ERROR`: `{ "error": { "code": "INTERNAL_ERROR", "message": "unexpected failure" } }`.

## `PATCH /alerts/{alert_id}`

**Method and path:** `PATCH /alerts/{alert_id}`

**Auth:** Cognito JWT: `Authorization: Bearer <token>`.

**Query parameters:** None.

**Path parameters:** `alert_id`, a literal `a-` followed by 32 lowercase hexadecimal characters.

**Request body:** Exactly `{ "action": "acknowledge" }` or `{ "action": "resolve" }`. There is no actor field; the actor is derived from the Cognito JWT on the server side.

```json
{ "action": "acknowledge" }
```

**Success: `200 OK` — acknowledge:**

```json
{
  "alert_id": "a-5d21e9ab34cd56ef7890ab12cd34ef56",
  "patient_id": "P002",
  "rule": "low_spo2",
  "severity": "critical",
  "status": "acknowledged",
  "created_at": "2026-11-17T14:22:10Z",
  "acknowledged_by": "operator@example.test",
  "acknowledged_at": "2026-11-17T14:23:00Z",
  "resolved_at": null
}
```

**Request body for resolve:**

```json
{ "action": "resolve" }
```

**Success: `200 OK` — resolve:**

```json
{
  "alert_id": "a-5d21e9ab34cd56ef7890ab12cd34ef56",
  "patient_id": "P002",
  "rule": "low_spo2",
  "severity": "critical",
  "status": "resolved",
  "created_at": "2026-11-17T14:22:10Z",
  "acknowledged_by": "operator@example.test",
  "acknowledged_at": "2026-11-17T14:23:00Z",
  "resolved_at": "2026-11-17T14:25:00Z"
}
```

**Errors:**

- `400 INVALID_ACTION` for a missing or invalid action: `{ "error": { "code": "INVALID_ACTION", "message": "action must be acknowledge or resolve" } }`.
- `400 INVALID_ALERT_TRANSITION` when `acknowledge` is used on an already-acknowledged or resolved alert, or `resolve` is used on an active alert: `{ "error": { "code": "INVALID_ALERT_TRANSITION", "message": "resolve requires an acknowledged alert" } }`.
- `401 UNAUTHENTICATED`: `{ "error": { "code": "UNAUTHENTICATED", "message": "authentication is required" } }`.
- `403 FORBIDDEN`: `{ "error": { "code": "FORBIDDEN", "message": "permission denied" } }`.
- `404 NOT_FOUND` for an unknown `alert_id`: `{ "error": { "code": "NOT_FOUND", "message": "alert not found" } }`.
- `500 INTERNAL_ERROR`: `{ "error": { "code": "INTERNAL_ERROR", "message": "unexpected failure" } }`.
