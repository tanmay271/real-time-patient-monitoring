# Infrastructure

This SAM template starts as a skeleton with no AWS resources; later tasks
(`DAT-02`-`04`, `ING-01`, `API-02`, `AUT-01`, `INF-05`, ...) add resources
using the naming convention documented in `template.yaml`. This file also
covers the IAM group and policy in `infra/iam-policy.json` (`INF-03`) — the
mechanism that lets six collaborators share one AWS account without being
able to touch each other's resources.

## Deploy

Deploy a contributor's isolated stack with:

```text
sam build && sam deploy --parameter-overrides Env=<your-name>
```

A one-off, task-scoped stack (used for a single task's deploy-and-verify
step, then torn down) is deployed the same way but with a task suffix on
both `Env` and the stack name, e.g. `Env=<your-name>-inf01`. See
"Scoping approach" below for why the IAM policy has to know about this
second naming shape too.

## Frontend hosting (`INF-05`)

After `sam deploy`, upload the built frontend with:

```text
aws s3 sync <build-dir> s3://patient-monitoring-<Env>-frontend
```

Serve it from the `FrontendDistributionDomainName` stack output. Building and
uploading the actual React app is a separate task (`WEB-09`) and is not done
here.

## Teardown

Remove a contributor's main stack with:

```text
sam delete --stack-name patient-monitoring-<your-name>
```

Remove a task-scoped stack the same way, with its own suffixed name:

```text
sam delete --stack-name patient-monitoring-<your-name>-<taskid>
```

## Scoping approach (`INF-03`)

The policy is attached to an IAM group (`patient-monitoring-developers`).
Every resource ARN in the policy uses the `${aws:username}` policy variable
in place of a literal name, so the one committed document scopes every group
member to their own prefix without per-user edits:

```
patient-monitoring-${aws:username}-*
```

This mirrors the `Env` parameter convention in `docs/architecture.md` §4.2 —
a collaborator deploys with `--parameter-overrides Env=<their-iam-username>`,
and every resource their stack creates is named `patient-monitoring-<their-
username>-<thing>`. Because the IAM policy substitutes the same username at
evaluation time, the resources a collaborator's own stack creates are exactly
the resources their policy lets them touch. Use the same IAM username as the
`Env` value every time — the two are tied together by this policy, not just
by convention.

**Two stack-name shapes, both covered.** A collaborator's main development
stack is named exactly `patient-monitoring-<username>` (no trailing
`-<thing>`). A task-scoped, deploy-and-delete-same-day stack (see "Deploy"
above) is named `patient-monitoring-<username>-<taskid>`, with an extra
suffix. `CloudFormationScoped` in `infra/iam-policy.json` grants both shapes
as two resource ARNs — `stack/patient-monitoring-${aws:username}/*` for the
main stack, `stack/patient-monitoring-${aws:username}-*/*` for any
task-scoped stack — so neither one needs a separate policy statement or a
per-task edit.

## What is fully scoped by resource name, and what isn't

| Service | Scoped to `patient-monitoring-${aws:username}-*`? | Notes |
|---|---|---|
| CloudFormation | Yes | `cloudformation:*` on both stack-name shapes above; `ListStacks`/`DescribeStacks`/`GetTemplateSummary` stay account-wide because they are read-only and SAM needs them before a stack name is known. |
| S3 | Yes | Scoped to the collaborator's own bucket prefix, plus the shared `aws-sam-cli-managed-default*` bucket SAM creates for deployment artifacts (that bucket is not per-prefix by design). |
| Lambda | Yes | `lambda:*` on the function-name ARN pattern. |
| DynamoDB | Yes | Data-plane actions (`GetItem`/`PutItem`/`UpdateItem`/`Query`/`Scan`) and the control-plane actions needed to let `sam deploy` create/update/delete the collaborator's own tables, all scoped to the table ARN and its `/index/*`. |
| IAM roles | Yes | `iam:CreateRole`/`PassRole` and the related role actions are scoped to a role-name pattern, not left account-wide. |
| CloudWatch Logs | Yes | Scoped to the `/aws/lambda/patient-monitoring-${aws:username}-*` log-group ARN. |
| API Gateway | No — `apigateway:*` on `arn:...::/apis*` | The HTTP API resource-ARN format does not support embedding `${aws:username}` in a way that isolates one collaborator's API from another's at the IAM layer. |
| Cognito | No — `cognito-idp:*` on `*` | Cognito user pool ARNs are assigned at creation time and aren't name-patternable the way DynamoDB table or Lambda function ARNs are. |
| CloudFront | No — `cloudfront:*` on `*` | Distribution ARNs are account/ID-based, not name-based, so there is no prefix to scope against. |

Per `docs/architecture.md:300`: ARN-pattern support for the `${aws:username}`
variable varies by service, and is not assumed uniform. The services above
that aren't scoped by resource name aren't an oversight — their ARN formats
don't expose a collaborator-name-shaped resource identifier to scope against.

## Data-plane least privilege, not end-to-end

Per `docs/architecture.md:302`: this policy claims *data-plane* least
privilege — a collaborator can read and write only their own DynamoDB tables,
invoke/update only their own Lambda functions, and operate only within their
own CloudFormation stack and log groups. It does not claim end-to-end least
privilege. `iam:CreateRole` and `iam:PassRole` are required for `sam deploy`
to create each stack's Lambda execution roles, and a permission set that
allows that self-service deployment is close to power-user in practice —
there is no tighter IAM-role scoping available that still lets a
collaborator deploy their own stack unassisted. This is stated here rather
than left implicit.

## Adding a new collaborator

1. Create an IAM user for them in the console (or via CLI), with a username
   that will double as their `Env` value.
2. Add that user to the `patient-monitoring-developers` group.

No policy edit is needed — the `${aws:username}` variable in
`infra/iam-policy.json` resolves per-user automatically, so the group policy
already covers the new collaborator's prefix the moment they're added.

## Cross-prefix denial verification

Verified against the account: a user scoped to the `tanmay` prefix was denied
both a cross-prefix table read and a cross-prefix stack change set, not given
a "not found" response.

`dynamodb:DescribeTable` on `patient-monitoring-otheruser-smoke`:

```
AccessDeniedException: User: arn:aws:iam::<ACCOUNT_ID>:user/tanmay is not
authorized to perform: dynamodb:DescribeTable on resource:
arn:aws:dynamodb:us-east-1:<ACCOUNT_ID>:table/patient-monitoring-otheruser-smoke
because no identity-based policy allows the dynamodb:DescribeTable action
```

`cloudformation:CreateChangeSet` on stack `patient-monitoring-otheruser`:

```
AccessDenied: User: arn:aws:iam::<ACCOUNT_ID>:user/tanmay is not authorized
to perform: cloudformation:CreateChangeSet on resource:
arn:aws:cloudformation:us-east-1:<ACCOUNT_ID>:stack/patient-monitoring-otheruser/*
because no identity-based policy allows the cloudformation:CreateChangeSet
action
```
