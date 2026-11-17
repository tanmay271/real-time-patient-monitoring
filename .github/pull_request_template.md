## Task

Closes #<issue number>
Task ID: `<e.g. ING-04>`

## What changed

<One or two sentences. What a reviewer needs to know before reading the diff.>

## Acceptance criteria

Copy the checklist from the task spec in `docs/tasks/` and tick what this PR satisfies.

- [ ]
- [ ]

## Evidence

<Test output, screenshot, CloudWatch log line, or DynamoDB item. Required for
anything touching AWS resources or measured behaviour.>

## Checks

- [ ] Branch named `<type>/<TASK-ID>-<desc>`
- [ ] Rebased on current `main`
- [ ] CI green (`sam validate` + pytest)
- [ ] No account ID, invoke URL, pool ID or key added to any committed file
- [ ] `docs/api.md` updated in this PR if any endpoint changed
- [ ] Synthetic data only
- [ ] Scope limited to this task ID
