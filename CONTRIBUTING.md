# Contributing

Six contributors share one AWS account and one `main` branch. These rules exist
so that nobody's work lands on top of anybody else's.

## Before you start

1. Read `docs/architecture.md` §13 (conventions) and §8 (the task list).
2. Pick a task from the current wave in §9. **Do not start a task whose
   dependencies have not merged** — check §8 for its `depends on` list.
3. Claim it: comment on its GitHub Issue and assign yourself. If no issue
   exists, create one using the task ID as the title prefix.

## One task, one branch, one PR

```bash
git checkout main && git pull
git checkout -b feat/ING-04-idempotent-writes
```

Branch naming: `<type>/<TASK-ID>-<short-description>`

| Type | Use for |
|---|---|
| `feat` | New functionality |
| `fix` | Correcting merged behaviour |
| `docs` | Documentation only |
| `test` | Tests only |
| `infra` | Template, CI, IAM |

A task is sized to finish in one sitting (2–4 hours). If yours is sprawling past
that, it is two tasks — say so on the issue and split it rather than opening a
branch that lives for two weeks.

**Stay in scope.** Do not fix something belonging to another task ID, even if it
is one line and obviously broken. Open an issue for it. Cross-task changes make
review impossible and break the contribution record.

## Before opening the PR

```bash
git fetch origin && git rebase origin/main
pytest tests/unit
sam validate --lint --template infra/template.yaml
```

Then open the PR, fill in the template, and attach evidence. Evidence is
required for anything touching AWS resources or measured behaviour: test output,
a CloudWatch log line, a DynamoDB item, a screenshot.

## Review

- One approval from **anyone other than the author**. Review duty rotates across
  all six of us; nobody is the designated approver.
- `infra/` and the contract documents additionally require the
  template maintainer's review (`CODEOWNERS` requests this automatically).
- CI must be green.
- Reviewers check the acceptance criteria in the task spec, not just that the
  code looks reasonable.

## Your own AWS stack

Each contributor deploys their own copy of the whole system inside the shared
account, so your testing cannot contaminate anyone else's:

```bash
cd infra
sam deploy --stack-name patient-monitoring-<yourname> \
           --parameter-overrides Env=<yourname> \
           --capabilities CAPABILITY_IAM
```

Use the same `<yourname>` every time; it is your IAM username, which is what the
access policy is scoped to. You can read and write only your own tables.

**Never deploy to `patient-monitoring-demo`.** That stack is the graded
environment, deployed from a tagged commit by one designated member, and frozen
before the presentation.

Shut your simulator down when you stop working. The cost risk in this project is
not the services, it is a forgotten loop.

## Things that will get a PR sent back

- A `Scan` on the `readings` table (use `Query` on the partition key)
- A `float` written to DynamoDB (use `decimal.Decimal`)
- A hardcoded resource name, Region, invoke URL, pool ID or account ID
- A local or naive timestamp
- A new error response shape (there is one envelope; see §13)
- Patient values in a log line
- An endpoint change without the matching `docs/api.md` update in the same PR
- A new DynamoDB index without a template review
