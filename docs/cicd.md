# CI/CD and supply chain

Workflows live in `.github/workflows/`. They check the repository. They do not deploy, and they do not push images.

A GitHub-hosted run was not observed from this environment. The commands below were run locally. Treat hosted status as unknown until you see a run on GitHub.

## Workflows

| File | Trigger | Blocks the workflow when |
| --- | --- | --- |
| `ci.yml` | Pull request, push to `main`, or `workflow_call` | Backend tests, KubeMedic tests, `npm run build`, kubeconform, `terraform fmt`, `terraform validate`, or the Trivy Terraform config gate fail |
| `security.yml` | Pull request or push to `main` | gitleaks finds a secret, or Trivy finds a fixed HIGH or CRITICAL CVE in pinned Python or npm dependencies |
| `build-images.yml` | Push to `main`, `workflow_dispatch`, or `workflow_call` | The image build, kubeconform, or archive step fails. Image CVEs are reported and do not fail the job |
| `release.yml` | Tag `vX.Y.Z` | Any called gate fails. On success it creates a GitHub Release with the reports and image archives |

`ci.yml` permissions are `contents: read`. The Terraform job does not request `id-token: write`. `release.yml` uses `contents: write` only on the job that publishes the release.

## What does not happen

- No `kubectl apply` against a live cluster in CI. GitHub-hosted runners have no cluster. `scripts/validate-k8s.sh` uses kubeconform, and uses `kubectl apply --dry-run=client` only when a cluster is already reachable.
- No `terraform plan`, `terraform apply`, or `terraform destroy`.
- No push to GHCR or ECR.
- No deploy of the kind manifests from a workflow.
- Image tag `latest` is rejected by `scripts/build-images.sh`.

## Supply chain

| Control | What it does here |
| --- | --- |
| Immutable tags | `sha-` plus the first 12 characters of the commit. A release adds `vX.Y.Z` |
| gitleaks 8.24.2 | Fails the security workflow. Tests, fixtures, `secret.example.yaml`, and `.env.example` are allowlisted because they hold placeholders |
| Trivy 0.74.0 filesystem | Fails on fixed HIGH or CRITICAL issues in pinned dependency files. Unfixed findings do not fail that job |
| Trivy image | Writes a JSON report and a CycloneDX SBOM. Does not fail the build |
| kubeconform 0.6.7 | Strict schemas for Kubernetes 1.32. Grafana dashboard JSON is not a Kubernetes object, so it is not passed in. The ConfigMaps that mount those files are checked |
| Release artifacts | Scan JSON, SBOMs, digests, and gzipped `docker save` archives. Workflow artifacts are kept 14 days |

An SBOM is a CycloneDX inventory of components in the image. This repository does not sign images. Do not describe the pipeline as signed or attested.

Image scans of the current kind tags, run locally during the DevSecOps work: `taskflow-api:local` and `kubemedic:local` had no CRITICAL findings; `kubemedic:local` had 14 fixed HIGH findings; `taskflow-frontend:local` had fixed CRITICAL `CVE-2026-31789` from `nginxinc/nginx-unprivileged`. Failing the build on those base packages would block every change until the upstream images move. The report is the artifact.

`scripts/validate-k8s.sh` also fails if the Git ConfigMap sets `KUBEMEDIC_REMEDIATION_ENABLED` to anything other than `false`.

## Terraform in CI

`scripts/terraform-check.sh` refuses the arguments `apply`, `destroy`, `plan`, `import`, and `refresh`. It fails if a workflow file contains `terraform apply`, `terraform destroy`, or `terraform plan`. It also fails if a forbidden billable resource type is declared. Then it formats, initializes with `-backend=false`, validates, and scans.

Known config findings are documented in [aws-architecture.md](aws-architecture.md). `AWS-0039` is ignored. `AWS-0038` and `AWS-0178` are MEDIUM and do not fail the HIGH gate. They are not implemented controls.
