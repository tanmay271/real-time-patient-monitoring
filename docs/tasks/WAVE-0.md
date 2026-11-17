# Task specs — Wave 0

Seven tasks, no dependencies. All seven can start simultaneously.

Paste each spec into its GitHub Issue body. Branch, work, PR, tick the criteria.

---

## INF-01 — SAM template skeleton with `Env` parameter

**Depends on:** nothing
**Branch:** `infra/INF-01-sam-template-skeleton`
**Files:** `infra/template.yaml`, `infra/samconfig.toml`, `infra/README.md`

### Context
Every other AWS task deploys into the stack this template defines. The `Env`
parameter is what lets six contributors each run an isolated copy inside one
shared account, so it must be threaded through every resource name from the
start — retrofitting it later means touching every resource.

### Implementation
- `AWSTemplateFormatVersion` + `Transform: AWS::Serverless-2016-10-31`.
- One parameter: `Env`, type `String`, no default, with a description saying it
  is the contributor's IAM username or `demo`.
- Globals block: `Runtime: python3.13`, `Timeout: 10`, `MemorySize: 256`,
  `Tracing: Active` optional.
- No resources yet beyond whatever is needed for the template to validate — the
  tables arrive in `DAT-02`/`03`/`04`, the functions in `ING-01`.
- Every future resource name uses `!Sub "patient-monitoring-${Env}-<thing>"`.
  Add a comment in the template stating this rule.
- `infra/samconfig.toml` with `region = "us-east-1"` and
  `capabilities = "CAPABILITY_IAM"`.
- `infra/README.md` stub with the deploy and delete commands.

### Acceptance criteria
- [ ] `sam validate --lint --template infra/template.yaml` passes
- [ ] `Env` parameter present with no default
- [ ] Region `us-east-1` set in `samconfig.toml`
- [ ] No hardcoded resource name anywhere in the template
- [ ] No account ID, ARN literal or invoke URL in any committed file
- [ ] `infra/README.md` contains the deploy and teardown commands
- [ ] CI green

### Out of scope
Tables (`DAT-02`–`04`), Lambda functions (`ING-01`), API Gateway (`API-02`),
Cognito (`AUT-01`), S3/CloudFront (`INF-05`), IAM policies for humans (`INF-03`).

---

## INF-02 — Repository scaffold

**Depends on:** nothing
**Branch:** `infra/INF-02-repo-scaffold`
**Files:** `.gitignore`, `CONTRIBUTING.md`, `README.md`,
`.github/CODEOWNERS`, `.github/pull_request_template.md`,
`requirements-dev.txt`, directory placeholders

### Context
This lands before contributors are added, so that the first person to clone
finds the rules already in place rather than inferring them.

### Implementation
- Commit the scaffold files (provided).
- Replace `@REPLACE_WITH_GITHUB_USERNAME` in `CODEOWNERS` with the real handle.
- Create the directory tree from `docs/architecture.md` §5 with `.gitkeep` files
  in empty directories.
- `requirements-dev.txt`: `pytest`, `boto3`, plus whatever `TST-01` settles on
  for mocking (leave a comment pointing at `TST-01` rather than guessing).
- Configure branch protection on `main` in the GitHub UI: require a PR, require
  1 approval, dismiss stale approvals, require status checks, require
  conversation resolution, block direct and force pushes.

### Acceptance criteria
- [ ] All scaffold files committed
- [ ] `CODEOWNERS` names a real GitHub user and no placeholder remains
- [ ] Directory tree matches §5
- [ ] Branch protection active on `main` — verified by attempting a direct push
      and being rejected (paste the error in the PR)
- [ ] A fresh clone plus `pip install -r requirements-dev.txt` succeeds
- [ ] CI green

### Out of scope
CI workflow (`INF-04`). Adding collaborators — that happens after this merges.

---

## DAT-00 — Field contract / data dictionary

**Depends on:** nothing
**Branch:** `docs/DAT-00-data-dictionary`
**Files:** `docs/data-dictionary.md`

### Context
This is the first link in the project's critical path. The simulator generates
these fields (`SIM-01`), ingestion validates them (`ING-02`), the API serialises
them (`API-01`) and the dashboard renders them (`WEB-02`). Four tasks by
different people against one definition — so the definition comes first.

### Implementation
Document every field a reading contains. For each: name, JSON type, unit, valid
range, nullability, and a one-line meaning. At minimum:

| Field | Type | Unit | Range |
|---|---|---|---|
| `reading_id` | string | — | unique per reading |
| `patient_id` | string | — | `P001`–`P003` |
| `device_id` | string | — | `DEV-<patient_id>-NN` |
| `timestamp` | string | ISO-8601 UTC `Z` | — |
| `heart_rate` | integer | bpm | plausible physiological band |
| `spo2` | integer | percent | plausible physiological band |
| `temperature_c` | number | °C | plausible physiological band, one decimal |
| `systolic_bp` | integer | mmHg | plausible physiological band |
| `diastolic_bp` | integer | mmHg | plausible physiological band, < systolic |

Also specify: the batch envelope (`{"readings": [...]}`), the maximum batch size,
which fields are required versus optional, and the exact `reading_id` format.

Choose the numeric ranges deliberately — they become `ING-02`'s rejection
boundaries, so a range that is too tight will reject the simulator's own
emergency scenarios. Check each against the scenarios in §2.4 before settling.

### Acceptance criteria
- [ ] Every field has name, type, unit, range, nullability and meaning
- [ ] Batch envelope and maximum batch size specified
- [ ] Required versus optional stated per field
- [ ] Ranges verified wide enough to admit all four scenarios' values
- [ ] `diastolic_bp < systolic_bp` invariant stated
- [ ] Reviewed by whoever will take `SIM-01` and whoever will take `ING-02`
- [ ] Explicitly labelled: synthetic data, educational project settings

### Out of scope
Alert thresholds (`ALR-01`) — those are decision boundaries, not validity
ranges. A reading can be valid and critical at the same time; keep the two
concepts separate.

---

## OPS-03 — AWS Budgets alert

**Depends on:** nothing
**Branch:** `infra/OPS-03-budget-alert`
**Files:** `docs/cost-log.md`

### Context
Seven stacks in one account on a credit-based Free Plan. The cost risk is not
the architecture, it is a simulator left looping.

### Implementation
- Create an AWS Budget in the account with a monthly threshold appropriate to
  the course (a low figure — this project should cost cents).
- Set alerts at 50%, 80% and 100% of threshold.
- Confirm the notification email actually arrives — a configured-but-unconfirmed
  subscription is worthless.
- Determine whether this account has a hard spend limit available (depends on
  sign-up vintage) or only budget notifications. Record the answer.
- Create `docs/cost-log.md` with a table: date, amount, note.

### Acceptance criteria
- [ ] Budget created with three alert thresholds
- [ ] A test notification received at the configured address (confirm, don't assume)
- [ ] `docs/cost-log.md` exists with the first dated entry
- [ ] Documented whether a hard spend limit exists on this account
- [ ] No account ID in the committed file

### Out of scope
Weekly logging discipline (`OPS-04`). CloudWatch retention (`OPS-02`).

---

## TST-01 — Test plan structure

**Depends on:** nothing
**Branch:** `test/TST-01-test-plan-structure`
**Files:** `tests/test-plan.md`, `tests/unit/.gitkeep`,
`tests/integration/.gitkeep`, `tests/load/.gitkeep`

### Context
Every later `TST` task appends to this file. Deciding the evidence format once
means the Week 10 status update and the final presentation can read measurements
straight out of it.

### Implementation
- Sections: unit, API, integration, reliability, security, performance, demo.
- A row format per test: ID, prerequisites, command or action, expected result,
  actual result, date, tester, evidence link.
- State the rule that a test is assigned to someone who did not write the feature.
- State the rule that only synthetic data is used and that alerts are reset
  between runs where it matters.
- **Decide the DynamoDB mocking approach** for unit tests (this is one of the
  open conventions in §13) and record the decision plus reasoning. Add the chosen
  library to `requirements-dev.txt`.

### Acceptance criteria
- [ ] All seven sections present with the row format defined
- [ ] Mocking approach decided, justified and added to `requirements-dev.txt`
- [ ] Non-author assignment rule written down
- [ ] One worked example row filled in so the format is unambiguous
- [ ] `docs/architecture.md` §13 "Still undecided" table updated to remove the mocking entry
- [ ] CI green

### Out of scope
Writing actual tests — those belong to `TST-02` onward.

---

## DOC-03 — Synthetic data and prototype disclaimer

**Depends on:** nothing
**Branch:** `docs/DOC-03-disclaimers`
**Files:** `docs/disclaimers.md`, plus the statement added to `README.md`

### Context
The course requires that no real patient information is used. Stating the
boundary once, in a referenceable place, means every later document and slide
can point at it instead of re-wording it.

### Implementation
- Write the synthetic-data statement: what the simulator generates, that no real
  or de-identified patient data is used, and that patient IDs are invented.
- Write the prototype statement: educational project, not a medical device, not
  validated, thresholds are project settings not clinical guidance.
- Add a condensed version to `README.md` as a blockquote near the top.
- Note where else it must appear: the dashboard UI footer (`WEB-01`), the final
  slides (`DOC-06`), and the repository description.

### Acceptance criteria
- [ ] Both statements written
- [ ] Condensed version in `README.md`
- [ ] List of other places the statement must appear, with task IDs
- [ ] No clinical claim anywhere in the wording

### Out of scope
Implementing the UI footer (`WEB-01`).

---

## DOC-04 — References and AI-tool citation

**Depends on:** nothing
**Branch:** `docs/DOC-04-references`
**Files:** `docs/references.md`

### Context
The course permits any resource and any AI tool, on condition that each is
credited and cited in the final presentation. Recording citations as they are
incurred is far easier than reconstructing them in week fifteen.

### Implementation
- Create `docs/references.md` with sections: AWS documentation, libraries and
  frameworks, public datasets, AI tools, other sources.
- Seed the AI-tools section with what has been used so far, including for
  planning and architecture, not only for code.
- State the rule in `CONTRIBUTING.md`: if a PR used an AI tool or an outside
  source materially, add the citation in the same PR.

### Acceptance criteria
- [ ] `docs/references.md` created with all five sections
- [ ] AI tools used to date recorded, with what each was used for
- [ ] Citation-in-the-same-PR rule added to `CONTRIBUTING.md`
- [ ] Format consistent enough to drop into a slide unedited

### Out of scope
The presentation itself (`DOC-06`).
