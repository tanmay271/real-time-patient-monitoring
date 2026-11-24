# Test plan and evidence register

These rules apply to every row added to this register:

- Each test is assigned to someone who did not write the feature under test.
- Only synthetic data (`P001`, `P002`, `P003`) is used in any test. Alerts are reset between runs where a stale alert would invalidate the result.
- Row IDs use `<SECTION>-<NN>`, with a zero-padded two-digit number and the prefixes `UNIT`, `API`, `INT`, `REL`, `SEC`, `PERF`, and `DEMO`. IDs are strictly increasing within each section. `PERF-SC1` through `PERF-SC4` are reserved for the `TST-07` through `TST-10` success-criteria measurements.
- Dates use `YYYY-MM-DD` in UTC.
- Evidence links point to a path under `docs/evidence/` or to a merged PR/commit URL on this GitHub repository. They are never local absolute paths or live AWS console URLs.
- Multiline output or output containing `|` is saved under `docs/evidence/` as its own file and linked from the Evidence link column; it is not pasted into a table cell.
- For future rows, use Unit for unit-level code tested directly, API for one call through the deployed HTTP API, and Integration for a multi-step flow through the live stack.

### DynamoDB test mocking approach

The DynamoDB test mocking approach is **moto**. It makes no real AWS calls and needs no AWS account, so tests are consistent across all six contributors' laptops and CI. It matches the `AGENTS.md` rules for `Decimal`, `ConditionExpression`, and `Query` rather than `Scan` because it emulates real DynamoDB behavior instead of relying on hand-rolled stubs. It also has no Docker or Java dependency, unlike `dynamodb-local`.

`requirements-dev.txt` does not exist yet; it is owned by `INF-02` and has not merged. Whoever lands `INF-02` should add `moto` to that file alongside `pytest` and `boto3`.

## Unit

Unit tests exercise individual functions or modules directly without requiring a deployed stack.

`UNIT-01` below is the worked example that fixes the row format; it is run
by whichever contributor is checking the infra scaffold at the time, which
should be someone other than whoever wrote the file under test.

| ID | Prerequisites | Command/Action | Expected | Actual | Date | Tester | Evidence link |
|---|---|---|---|---|---|---|---|
| UNIT-01 | `infra/template.yaml` exists on the branch. | `pytest tests/unit/test_infra_template.py` and, separately, `sam validate --lint --template infra/template.yaml` | All 11 pytest assertions pass; `sam validate --lint` exits 0. | `pytest`: 11 passed in 0.06s. `sam validate --lint`: "infra/template.yaml is a valid SAM Template". | 2026-11-24 | Tanmay | `docs/evidence/UNIT-01-infra-template-checks.txt` |

## API

API tests exercise one request through the deployed HTTP API and verify its response.

| ID | Prerequisites | Command/Action | Expected | Actual | Date | Tester | Evidence link |
|---|---|---|---|---|---|---|---|

## Integration

Integration tests exercise multi-step flows through the live stack.

| ID | Prerequisites | Command/Action | Expected | Actual | Date | Tester | Evidence link |
|---|---|---|---|---|---|---|---|

## Reliability

Reliability tests exercise behavior under retries, failures, recovery, and other operational conditions.

| ID | Prerequisites | Command/Action | Expected | Actual | Date | Tester | Evidence link |
|---|---|---|---|---|---|---|---|

## Security

Security tests exercise authentication, authorization, input handling, and protection of sensitive data.

| ID | Prerequisites | Command/Action | Expected | Actual | Date | Tester | Evidence link |
|---|---|---|---|---|---|---|---|

## Performance

Performance tests record latency, throughput, capacity, and other measured system behavior.

| ID | Prerequisites | Command/Action | Expected | Actual | Date | Tester | Evidence link |
|---|---|---|---|---|---|---|---|

## Demo

Demo checks verify the end-to-end scenarios prepared for presentation.

| ID | Prerequisites | Command/Action | Expected | Actual | Date | Tester | Evidence link |
|---|---|---|---|---|---|---|---|
