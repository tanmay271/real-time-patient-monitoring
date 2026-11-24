# Infrastructure

This SAM template is currently a skeleton with no AWS resources. Later tasks
will add resources using the naming convention documented in `template.yaml`.

Deploy a contributor's isolated stack with:

```text
sam build && sam deploy --parameter-overrides Env=<your-name>
```

Remove that stack with:

```text
sam delete --stack-name patient-monitoring-<your-name>
```
