# Security

KubeMedic is a local lab. It is not a hosted service. There is no private contact address in this repository. If you find a vulnerability in the code, open a GitHub issue or a private report through the host you forked it to. Please do not include live credentials in the report.

## Credentials

Real database passwords, cloud keys, kubeconfigs, and API tokens do not belong in Git. `taskflow/.env` is gitignored. `make deploy` creates Secret `taskflow-db` on the cluster and does not write that password into the repo. `k8s/taskflow/backend/secret.example.yaml` and `taskflow/.env.example` are placeholders. gitleaks allowlists those paths and the test fixtures because they contain fake values used to prove redaction. Do not put a real secret in an allowlisted path.

Terraform state and `.terraform/` are gitignored. Do not commit them.

## Runtime boundaries

- The watcher cannot read Secret objects.
- Logs and events are redacted before they are stored, and again before an optional AI request.
- AI is disabled in the cluster ConfigMap. No provider key is committed. AI output is not executed.
- Remediation is disabled in Git. The remediator cannot exec, delete, or accept a caller-supplied patch.
- Containers that this repo builds run as non-root with `allowPrivilegeEscalation: false`.
- Compose publishes ports on `127.0.0.1` only. The kind Services are reached with port-forward in the lab notes.

## Lab scope

The KubeMedic HTTP API has no authentication. Do not publish it on a network you do not control. Prometheus is allowed to read node metrics. That ClusterRole is not a write role and it is not cluster-admin.

`terraform apply` can create billable AWS resources if the cost gates in `infra/terraform/` are edited. This project does not apply that configuration. See [docs/threat-model.md](docs/threat-model.md).
