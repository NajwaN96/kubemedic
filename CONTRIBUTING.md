# Contributing

The lab should stay runnable on kind, with remediation off and no AWS resources created.

## Setup

```bash
make setup
make test
make kubemedic-test
```

Kind and the scanners are described in the [README](README.md) and [docs/local-kind.md](docs/local-kind.md).

## Pull requests

- Run the test you touched. `make validate-k8s` if you change manifests. `make terraform-check` if you change `infra/terraform/`.
- Do not enable `KUBEMEDIC_REMEDIATION_ENABLED` or `KUBEMEDIC_AI_ENABLED` in Git.
- Do not add `terraform apply` or `terraform plan` to a workflow.
- Do not commit `.env`, kubeconfig, Terraform state, or a real API key.
- Keep new remediation actions out unless they are typed, allowlisted, and covered by tests. Do not accept a caller-supplied patch.

## Security

See [SECURITY.md](SECURITY.md). Report vulnerabilities without pasting live credentials.
