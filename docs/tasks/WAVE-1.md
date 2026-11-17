# Task specs — Wave 1

Nine tasks. Each begins once its listed dependencies have merged.

`DAT-01`, `API-01` and `SIM-01` all unblock on `DAT-00` and are the three that
matter most — `API-01` especially, since the entire frontend lane hangs off it.

---

## API-01 — Publish the API contract

**Depends on:** `DAT-00`
**Branch:** `docs/API-01-api-contract`
**Files:** `docs/api.md`

### Context
**This is the project's pivot task.** Every `WEB` task depends on it and on
nothing else, which means the dashboard can be built in parallel with the
backend rather than after it. It requires no code and no deployed AWS resource.
It deliberately does **not** depend on `DAT-01`: the contract describes wire
shapes and must not leak physical table structure.

### Implementation
Document all five routes with complete request and response bodies:

| Method | Route |
|---|---|
| POST | `/readings` |
| GET | `/patients` |
| GET | `/patients/{patient_id}/readings` |
| GET | `/alerts` |
| PATCH | `/alerts/{alert_id}` |

For each route: method, path, auth requirement, query parameters with defaults
and caps, a full example request body, a full example success response body, and
every error code it can return.

Also specify:
- The error envelope (already pinned in `docs/architecture.md` §13) and the full list of `code`
  values the API can return.
- `limit` default and maximum for the history route.
- The `status` filter values for `GET /alerts`.
- The `connection_state` values (`connected` / `delayed` / `disconnected`) and
  the fact that it is derived at read time, not stored.
- Timestamp format, referencing `DAT-00` rather than restating field definitions.
- That `PATCH /alerts/{alert_id}` carries the action (`acknowledge` / `resolve`)
  and derives the actor from the JWT rather than the request body.

### Acceptance criteria
- [ ] All five routes documented with complete example request and response JSON
- [ ] Every error `code` value enumerated
- [ ] `limit` default and cap stated
- [ ] `status` filter values stated
- [ ] `connection_state` values stated, with derivation noted
- [ ] Reviewed by whoever will take `WEB-01` **and** whoever will take `API-03`
- [ ] Response examples use only `P001`–`P003` and synthetic values
- [ ] A reader can write a frontend fetch call against it with no other document

### Out of scope
Implementing any endpoint. Table design (`DAT-01`). Auth mechanics (`AUT-03`).

---

## DAT-01 — Table design document

**Depends on:** `DAT-00`
**Branch:** `docs/DAT-01-table-design`
**Files:** `docs/table-design.md`

### Context
Reviewed and merged before any table is created, so that the GSI requirements
are designed in rather than discovered during alert implementation.

### Implementation
- For each of the three tables: partition key, sort key, every attribute, and a
  complete example item using only fake IDs.
- Map every access pattern in `docs/architecture.md` §3 to a specific key or index.
  Any pattern that resolves to a `Scan` must be justified or redesigned.
- Specify both GSIs on `alerts` and state which query each serves:
  - GSI1 `patient_rule` / `status` → duplicate-active-alert suppression
  - GSI2 `status` / `created_at` → status-filtered listing for the dashboard
- Specify the `patient_rule` composite format (`P002#low_spo2`).
- Specify TTL: attribute `expires_at` on `readings`, epoch integer seconds,
  and the retention window chosen for the demo.
- State on-demand billing for all three tables and that no further index is permitted.

### Acceptance criteria
- [ ] All three tables fully specified with example items
- [ ] Every §3 access pattern mapped to a key or index
- [ ] Both GSIs specified with the query each serves
- [ ] `patient_rule` composite format defined
- [ ] TTL attribute, type and window defined
- [ ] Example items use fake IDs and synthetic values only
- [ ] Reviewed by whoever will take `ING-03` and whoever will take `ALR-04`

### Out of scope
Creating the tables (`DAT-02`–`04`).

---

## SIM-01 — Simulator core generator

**Depends on:** `DAT-00`
**Branch:** `feat/SIM-01-simulator-core`
**Files:** `simulator/simulator.py`, `simulator/requirements.txt`,
`tests/unit/test_simulator.py`

### Context
Runs with no AWS at all, printing batches to stdout, so that field shapes can be
verified before anything is deployed.

### Implementation
- Generate readings for `P001`, `P002`, `P003`, every field exactly as `DAT-00`
  defines it — names, types, units, ranges.
- `--iterations N` and an interval between batches; one batch per iteration
  containing all three patients.
- `--scenario normal` only at this stage; the argument exists so `SIM-02` adds
  values without changing the interface.
- Baseline values per patient with small random drift, so output looks like a
  monitored patient rather than noise.
- `reading_id` unique per reading in the format `DAT-00` specifies.
- `timestamp` generated as ISO-8601 UTC with a trailing `Z`, from an aware
  datetime. Never `datetime.now()` without a timezone.
- Print each batch as the `{"readings": [...]}` envelope.
- Keep it standard-library only if possible; if not, add the dependency to
  `simulator/requirements.txt`.

### Acceptance criteria
- [ ] `python simulator/simulator.py --scenario normal --iterations 2` emits two
      batches of three patients each
- [ ] Every field from `DAT-00` present, correctly typed, within its stated range
- [ ] `diastolic_bp < systolic_bp` in every generated reading
- [ ] `reading_id` unique across a 100-iteration run
- [ ] Timestamps are timezone-aware UTC ending in `Z`
- [ ] Unit test asserts the envelope shape and one range check per numeric field
- [ ] No AWS SDK import and no network call
- [ ] CI green

### Out of scope
Scenarios beyond `normal` (`SIM-02`). Sending to AWS (`SIM-03`). Device pause
(`SIM-04`). README (`SIM-05`).

---

## INF-03 — IAM group and prefix-scoped policy

**Depends on:** `INF-01`
**Branch:** `infra/INF-03-iam-collaborator-policy`
**Files:** `infra/iam-policy.json`, `infra/README.md`

### Context
This is what makes one shared account safe for six people: each contributor can
deploy and operate their own stack and cannot touch anyone else's tables.

### Implementation
- Create an IAM group for contributors.
- Write a policy using the `${aws:username}` variable in resource ARNs so one
  document scopes every user to their own prefix. Cover DynamoDB data actions on
  `patient-monitoring-${aws:username}-*` and its `/index/*`.
- **Verify the ARN pattern works per service** rather than assuming it —
  variable support in resource ARNs varies. Test by attempting a cross-prefix
  read and confirming denial.
- Grant the CloudFormation, Lambda, API Gateway, Cognito, logs and
  `iam:CreateRole`/`iam:PassRole` permissions needed for self-service deploys.
  Constrain the role path or name pattern where possible.
- Document in `infra/README.md` what the policy does and does not constrain —
  specifically that data-plane isolation is enforced while deploy permissions
  are necessarily broad.

### Acceptance criteria
- [ ] Group created, policy attached, policy JSON committed
- [ ] A test user can deploy their own stack successfully
- [ ] A test user is **denied** reading another prefix's table — paste the
      `AccessDenied` error in the PR
- [ ] `${aws:username}` substitution confirmed working for every service it is used on
- [ ] `infra/README.md` states the data-plane versus deploy-permission distinction
- [ ] No account ID in the committed policy file (use a placeholder)

### Out of scope
Creating the five real IAM users — that happens when contributors are added.

---

## INF-04 — CI workflow

**Depends on:** `INF-02`
**Branch:** `infra/INF-04-ci-workflow`
**Files:** `.github/workflows/ci.yml`

### Context
Catches a broken template before five people pull it.

### Implementation
- Commit the provided workflow.
- Confirm each job runs: template validation, Python unit tests, the committed-
  identifier guard. The frontend job stays conditional until `frontend/` exists.
- Make the jobs required status checks in branch protection.
- Verify the identifier guard actually fires by pushing a branch containing a
  fake 12-digit number, confirming the red, then removing it.

### Acceptance criteria
- [ ] Workflow runs on PRs to `main`
- [ ] `sam validate --lint` job passes on the current template
- [ ] Unit test job passes
- [ ] Identifier guard demonstrated failing on a deliberate test commit, then passing
- [ ] Jobs marked as required status checks
- [ ] No AWS credentials used anywhere in CI

### Out of scope
Deployment from CI — deploys stay manual and per-contributor.

---

## INF-05 — S3 bucket and CloudFront distribution

**Depends on:** `INF-01`
**Branch:** `infra/INF-05-frontend-hosting`
**Files:** `infra/template.yaml`

### Context
The distribution domain is an input to two later tasks: the CORS origin
(`API-07`) and the Cognito callback URL (`AUT-02`). Creating it early means
neither of those is blocked, and means the fallback-to-localhost decision can be
made on evidence rather than panic.

### Implementation
- Private S3 bucket for the built frontend; no public bucket ACL.
- CloudFront distribution with Origin Access Control reading from the bucket.
- Default root object `index.html`; a 403/404 → `/index.html` 200 rewrite so
  client-side routing works.
- Output the distribution domain name as a CloudFormation output named clearly
  enough for `AUT-02` and `API-07` to consume.
- Keep it inside the always-free CloudFront allowance: no extra behaviours, no
  custom domain, no WAF.

### Acceptance criteria
- [ ] Bucket and distribution created by `sam deploy`
- [ ] Bucket is not publicly readable — verify a direct S3 URL is denied
- [ ] Distribution domain appears in stack outputs
- [ ] A placeholder `index.html` uploaded and served over the CloudFront URL
- [ ] 404 rewrite to `/index.html` verified
- [ ] Resource names carry the `${Env}` prefix
- [ ] Distribution domain **not** committed anywhere

### Out of scope
Building or deploying the real frontend (`WEB-09`). CORS (`API-07`).

---

## AUT-01 — Cognito user pool and app client

**Depends on:** `INF-01`
**Branch:** `infra/AUT-01-cognito-user-pool`
**Files:** `infra/template.yaml`

### Context
Deliberately early. The original checklist put identity in its final phase,
which forces auth to be retrofitted into a finished dashboard during the worst
week of the project. The pool has no dependencies beyond the template, so it
exists from Wave 1 and `WEB` can wire login as it builds rather than afterwards.

### Implementation
- User pool with a strong password policy.
- App client **without** a client secret — required for a browser SPA.
- Disable self-service sign-up; demo users are created administratively.
- No unnecessary attributes; email as the username is sufficient.
- Output the user pool ID, app client ID and the pool's issuer URL as stack
  outputs for `AUT-03` and `AUT-06`.
- `${Env}` prefix on resource names like everything else.

### Acceptance criteria
- [ ] Pool and app client created by `sam deploy`
- [ ] App client has no secret — confirm in the console or via CLI
- [ ] Self-service sign-up disabled
- [ ] Pool ID, client ID and issuer URL present in stack outputs
- [ ] One demo user created manually and able to obtain a token
- [ ] No pool ID or client ID committed to any file

### Out of scope
JWT authorizer on routes (`AUT-03`). React login (`AUT-06`). Callback URLs
(`AUT-02`, needs `INF-05`). Documented user-reset procedure (`AUT-05`).

---

## OPS-02 — CloudWatch log retention

**Depends on:** `INF-01`
**Branch:** `infra/OPS-02-log-retention`
**Files:** `infra/template.yaml`

### Context
Lambda log groups default to never expiring. Seven stacks logging indefinitely
is a slow storage leak and the single easiest cost control in the project.

### Implementation
- Set `RetentionInDays: 7` for every Lambda log group the stack creates.
- Prefer explicit `AWS::Logs::LogGroup` resources with the
  `/aws/lambda/patient-monitoring-${Env}-*` naming so retention is declared in
  code rather than set by hand after the fact.
- Add a note in `infra/README.md` that log groups are stack-managed, so
  `sam delete` removes them.

### Acceptance criteria
- [ ] Retention is 7 days on every log group the stack creates
- [ ] Retention visible in the console after a deploy, not just in the template
- [ ] Log groups are deleted by `sam delete` — verify on a scratch stack
- [ ] Noted in `infra/README.md`

### Out of scope
Structured log content (`OPS-01`).

---

## OPS-04 — Cost log discipline

**Depends on:** `OPS-03`
**Branch:** `docs/OPS-04-cost-log`
**Files:** `docs/cost-log.md`, `CONTRIBUTING.md`

### Context
The Week 10 status update has to report actual AWS cost to date. A weekly habit
makes that a copy-paste; reconstructing it from the billing console at the last
minute does not work, because the console's granularity degrades over time.

### Implementation
- Establish the weekly entry format: date, month-to-date spend, credits
  remaining, note on anything unusual.
- Add the first two entries.
- Add a line to `CONTRIBUTING.md` naming the weekday the check happens and who
  does it if the usual person is unavailable.
- Record the current credit balance so burn rate is visible rather than inferred.

### Acceptance criteria
- [ ] Format defined, first entries present
- [ ] Credit balance recorded
- [ ] Weekly cadence and fallback owner written into `CONTRIBUTING.md`
- [ ] No account ID in the file

### Out of scope
Budget creation (`OPS-03`).
