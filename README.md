# KubeMedic

KubeMedic is a Kubernetes reliability engineering lab that detects workload failures, collects operational evidence, tracks incidents through recovery, and supports human-approved remediation.

It uses [TaskFlow](#taskflow) as a real application workload. The lab shows Kubernetes operations, observability, incident response, safe remediation, DevSecOps, and an infrastructure-as-code design that is not provisioned.

Kubernetes can restart a container or replace a Pod. That does not, by itself, say what failed, which evidence supports the diagnosis, whether the application recovered, or whether a change is safe to make. KubeMedic is that investigation and recovery record. It is not a replacement for Prometheus, and it is not an autonomous SRE.

The operator console and TaskFlow are available in English and Arabic. Arabic uses a right-to-left layout. Technical identifiers such as `INV-000019`, Pod names, and Kubernetes reasons stay unchanged.

## Contents

- [Why KubeMedic](#why-kubemedic)
- [What is running](#what-is-running)
- [Architecture](#architecture)
- [How it works](#how-it-works)
- [Features](#features)
- [Failure matrix](#failure-matrix)
- [Incident story](#incident-story)
- [Observability](#observability)
- [AI-assisted investigation](#ai-assisted-investigation)
- [Human-approved remediation](#human-approved-remediation)
- [Security](#security)
- [DevSecOps](#devsecops)
- [AWS reference architecture](#aws-reference-architecture)
- [Screenshots](#screenshots)
- [Quick start](#quick-start)
- [Testing](#testing)
- [Repository structure](#repository-structure)
- [Limitations](#limitations)
- [Documentation](#documentation)

## Why KubeMedic

A restarted Pod is not an explanation.

| Kubernetes already does this | KubeMedic adds this |
| --- | --- |
| Restarts containers and replaces Pods | Names the failure and stores the evidence |
| Keeps the desired replica count | Tracks open, recovering, and resolved |
| Does not remember why the last rollout was bad | Proposes one typed action and waits for a person |
| Exposes metrics | Keeps an audit of what changed, then checks that the workload recovered |

Rules make the diagnosis. An optional AI pass can explain the same evidence later. It cannot execute Kubernetes operations. Remediation is disabled unless the lab flag is turned on, and even then a person must approve the action.

## What is running

| Environment | Status |
| --- | --- |
| Docker Compose | Implemented |
| kind Kubernetes | Implemented and live-verified on cluster `taskflow` |
| Prometheus and Grafana | Implemented and live-verified |
| KubeMedic | Implemented and live-verified |
| Human-approved remediation | Implemented and live-verified. Disabled again after the controlled test |
| Optional AI | Implemented. Disabled without an API key |
| GitHub Actions | Implemented and checked locally. A GitHub-hosted run was not observed from this environment |
| AWS, EKS, and ECR | Reference Terraform design only |

The live path is Developer, Docker, then kind. TaskFlow, KubeMedic, PostgreSQL, Prometheus, and Grafana run in that cluster.

## Architecture

```mermaid
flowchart TB
  User[User] --> TaskFlow[TaskFlow]
  TaskFlow --> Kind[Kubernetes / kind]
  Kind --> Workloads[Workloads]
  Kind --> KM[KubeMedic]
  KM --> Watcher[Watcher]
  KM --> Evidence[Evidence]
  KM --> Rules[Rules]
  Evidence --> Investigation[Investigation]
  Rules --> Investigation
  Investigation --> AI[Optional AI]
  Investigation --> Proposal[Remediation proposal]
  Proposal --> Human[Human approval]
  Human --> Api[Kubernetes API]
  Api --> Verify[Verification]
```

### Investigation

```mermaid
flowchart TB
  State[Kubernetes state] --> Detect[Detection]
  Detect --> Collect[Evidence collector]
  Collect --> Rules[Deterministic rules]
  Rules --> Inv[Investigation]
  Inv --> Open[OPEN]
  Open --> Recovering[RECOVERING]
  Recovering --> Resolved[RESOLVED]
  Inv -.-> AI[Optional AI enrichment]
```

Rules remain the record if AI is disabled or the provider fails.

### Observability

```mermaid
flowchart TB
  App[TaskFlow metrics] --> Prom[Prometheus]
  KM[KubeMedic metrics] --> Prom
  Ksm[kube-state-metrics] --> Prom
  Cadv[cAdvisor via the node proxy] --> Prom
  Prom --> Graf[Grafana]
```

Prometheus scrapes the TaskFlow API, KubeMedic, kube-state-metrics, and a narrow cAdvisor query. Grafana has two dashboards: TaskFlow service health and KubeMedic reliability.

### Remediation

```mermaid
flowchart TB
  Inv[Investigation] --> Proposal[Remediation proposal]
  Proposal --> Human[Human approval]
  Human --> Policy[Policy validation]
  Policy --> Exec[Typed executor]
  Exec --> Api[Kubernetes API]
  Api --> Verify[Verification]
  Verify --> Audit[Audit trail]
```

There is no automatic remediation.

### DevSecOps

```mermaid
flowchart TB
  Dev[Developer] --> PR[Pull request]
  PR --> CI[GitHub Actions]
  CI --> Tests[Tests]
  CI --> Front[Frontend build]
  CI --> Kube[kubeconform]
  CI --> Leaks[gitleaks]
  CI --> Trivy[Trivy]
  CI --> Image[Image build]
  CI --> Sbom[SBOM]
  CI --> Main[Main or a version tag]
```

CI does not deploy to the cluster and does not push to a registry.

### Reference AWS Architecture — Not Provisioned

```mermaid
flowchart TB
  GH[GitHub] --> Actions[GitHub Actions]
  Actions --> OIDC[OIDC]
  OIDC --> IAM[AWS IAM]
  IAM --> ECR[ECR]
  ECR --> EKS[EKS]
  EKS --> TF[TaskFlow]
  EKS --> KM[KubeMedic]
  EKS --> PG[PostgreSQL]
  EKS --> Mon[Monitoring]
```

Designed in Terraform. Not provisioned. AWS infrastructure cost from this project: **$0**.

## How it works

1. The watcher reads Pods, events, and Deployments in namespace `taskflow`. It does not read Secret data.
2. The collector stores a bounded evidence record: status, restarts, probes, events, and redacted logs.
3. Local rules classify the issue and severity.
4. The same fingerprint updates one investigation instead of opening a duplicate.
5. When the workload looks healthy, the incident moves to recovering, then to resolved after a stabilization window. One poll cannot resolve it.
6. Some findings become a typed proposal: restart, rollback, or scale. Others stay informational.
7. A person approves with a name, a reason, and an explicit confirmation. The remediator then calls the Kubernetes API.
8. Verification requires the Deployment generation to advance and the updated replicas to become ready. Execution and recovery are separate.
9. The audit stores images, replica counts, revision, and generation. It does not store environment variables or Secret values.

## TaskFlow

TaskFlow is a small task manager: a React and TypeScript UI, a FastAPI API, and PostgreSQL. It is the workload KubeMedic watches. It has health and readiness endpoints, Prometheus metrics, and ordinary create, list, complete, and delete operations.

Compose publishes the UI on `127.0.0.1:41821`, the API on `127.0.0.1:41822`, and PostgreSQL on `127.0.0.1:41823`. On kind, the UI is reached with a port-forward to `127.0.0.1:41831`.

## Features

| Capability | In this repository |
| --- | --- |
| Real Kubernetes failure detection | Watcher on the kind cluster |
| Evidence collection | Events, status, probes, redacted logs |
| Deterministic diagnosis | Local rules. `analysis_source` stays `rules` unless AI succeeds |
| Incident lifecycle | Open, recovering, resolved |
| Stale event handling | Old events stay stored and do not keep an incident open |
| Orphan reconciliation | A disappeared Pod is not treated as a silent success |
| Prometheus metrics | TaskFlow and KubeMedic |
| Grafana dashboards | Service health and reliability overview |
| Optional AI | Off by default. Sanitized payload. No cluster credentials |
| Human-approved remediation | Restart, rollback, or scale from 1 to 5 |
| Operator console | Arabic and English, RTL and LTR, responsive incident flow |
| Audit trail | Before and after workload facts |
| RBAC separation | Read-only watcher and a narrow remediator |
| DevSecOps | Tests, kubeconform, gitleaks, Trivy, SBOM, immutable tags |
| Terraform AWS design | Reference only. Nothing is applied |

## Failure matrix

These classes are implemented in the rules. The running cluster has stored investigations for each of them except repeated restarts and a standalone Pod-deletion type. Pod replacement is handled by orphan reconciliation.

| Failure | Typical severity | Kubernetes | KubeMedic | Remediation |
| --- | --- | --- | --- | --- |
| CrashLoopBackOff | High, or critical if nothing is ready | Restarts the container | Stores exit status, logs, and events | Rollback when the Deployment revision is 2 or newer. Otherwise restart |
| ImagePullBackOff / ErrImagePull | High | Keeps retrying the pull | Keeps the image and event text | None. The image reference has to change |
| OOMKilled | High | Restarts the container | Records the kill and memory context | None. Raising the limit is not treated as the fix |
| CreateContainerConfigError | High | Pod stays waiting | Points at the missing configuration | None. Often a missing Secret or ConfigMap |
| FailedScheduling | Medium | Pod stays pending | Stores the scheduler message | None |
| Readiness probe failed | Medium | Stops sending traffic | Stores probe evidence | None |
| Liveness probe failed | High | Restarts the container | Stores probe evidence | None |
| Database connectivity | High | Application may restart or stay unready | Classifies from redacted application logs | None. Fix PostgreSQL or the configuration |
| Unavailable replicas | Medium, or critical if zero are ready | Keeps reconciling | Tracks desired against ready | Restart, or scale to 1 when desired is 0 |
| Pod deletion | Not a separate issue type | Replaces a managed Pod | Resolves only after the owning workload is healthy through the stabilization window | None for a delete by itself |

Severity rises to critical when the Deployment wants replicas and none are ready.

## Incident story

The primary lab incident is **INV-000019**.

A bad TaskFlow API rollout entered CrashLoopBackOff. KubeMedic opened the investigation from rules, with `analysis_source` `rules`. Remediation was disabled, so an approval attempt returned **409**. The flag was enabled only for the controlled test. **REM-000003** was a `rollback_deployment`, approved by the operator. The Deployment generation advanced, the command override was gone, and both API Pods were ready. The remediation reached **verified**. The investigation reached **resolved** with reason `affected Pod was replaced and owning workload is healthy`, and `recovery_duration_seconds` was 75. The flag was set back to false.

**REM-000001** and **REM-000002** are kept in the database on purpose. They were marked verified while the Deployment generation did not change. That bug, and the fix, are written up in [docs/lessons-learned.md](docs/lessons-learned.md).

## Observability

Grafana is anonymous and read-only in this lab. After `make deploy-monitoring`:

```bash
kubectl -n monitoring port-forward svc/grafana 41833:3000
kubectl -n monitoring port-forward svc/prometheus 41834:9090
```

Dashboards: `taskflow-health` and `kubemedic-reliability`.

## AI-assisted investigation

AI is optional. The cluster ConfigMap sets `KUBEMEDIC_AI_ENABLED` to `false`. No API key is committed.

When enabled, the provider receives a sanitized subset of the stored investigation. Secret-like values are redacted first. If the provider errors, the rule investigation remains. The dashboard labels this block **AI-assisted analysis**, under the deterministic section. AI output is never a remediation command.

## Human-approved remediation

Supported actions are `restart_deployment`, `rollback_deployment`, and `scale_deployment`. Scale accepts an integer from 1 through `KUBEMEDIC_REMEDIATION_MAX_REPLICAS` (5).

The watcher ServiceAccount `kubemedic` is read-only in namespace `taskflow`. The remediator ServiceAccount may get, list, and watch Deployments and ReplicaSets, and may patch or update Deployments. It cannot read Secrets, exec into Pods, delete objects, or use a ClusterRole.

`KUBEMEDIC_REMEDIATION_ENABLED` is `false` in Git. Approval still requires `confirm: true`, a short approver name, and a stored reason. The executor uses an explicit patch content type. Rollback replaces the Pod template inside the executor. It does not accept a caller-supplied patch.

## Security

- Database passwords and API keys are not committed. `taskflow/.env` is gitignored. The cluster Secret `taskflow-db` is created by `make deploy`.
- `k8s/taskflow/backend/secret.example.yaml` is an example. The deploy script does not apply it.
- Images run as non-root. Containers set `allowPrivilegeEscalation: false`.
- Debug fault routes stay unmounted unless `FAULT_INJECTION_ENABLED=true`.
- Compose ports bind to `127.0.0.1`.
- See [SECURITY.md](SECURITY.md) and [docs/threat-model.md](docs/threat-model.md).

## DevSecOps

| Workflow | When | What it checks |
| --- | --- | --- |
| `ci.yml` | Pull request and push to `main` | Backend tests, KubeMedic tests, frontend production build, kubeconform, Terraform fmt, validate, and config scan |
| `security.yml` | Pull request and push to `main` | gitleaks, Trivy on pinned dependencies |
| `build-images.yml` | Push to `main` | Image build, image CVE report, CycloneDX SBOM, manifest validation, saved image archives |
| `release.yml` | Tag `vX.Y.Z` | The gates above, then a GitHub Release |

Image tags are `sha-` plus twelve characters of the commit. A release also tags `vX.Y.Z`. The workflows refuse `latest`. Kind manifests stay on `:local`. Nothing is pushed to GHCR or ECR, and nothing is deployed.

Image scans record HIGH and CRITICAL findings, including unfixed ones, and do not fail the build. A local image scan during the DevSecOps work found no CRITICAL findings in `taskflow-api:local` or `kubemedic:local`, 14 fixed HIGH findings in `kubemedic:local`, and one fixed CRITICAL finding in `taskflow-frontend:local` (`CVE-2026-31789` in the nginx base image). This pass rebuilt `kubemedic:local` from the same base image for the dashboard and did not repeat that image scan. Dependency scans fail on a fixed HIGH or CRITICAL CVE in pinned Python or npm dependencies. Details are in [docs/cicd.md](docs/cicd.md).

Workflows are implemented and the same commands were run locally. A GitHub-hosted Actions run was not observed from this environment.

## AWS reference architecture

`infra/terraform/` describes a VPC, private and public subnets, ECR, EKS, a managed node group at desired size 0, IAM, and GitHub OIDC. The platform module is omitted unless two cost-review settings are changed. `enable_nat_gateway` cannot be set true. CI does not run `terraform plan` or `terraform apply`.

Trivy config ignores one HIGH finding, `AWS-0039`, because EKS secret encryption would require a customer-managed KMS key. `AWS-0038` and `AWS-0178` remain visible on a full scan as MEDIUM findings for control-plane logs and VPC flow logs. Those controls are not implemented. They are omitted so the reference design does not imply paid CloudWatch logging.

No AWS resources were created. `terraform apply` was not run. AWS infrastructure cost from this project is **$0**.

## Screenshots

Taken from the running kind lab. The operator console is in English and Arabic. Arabic uses RTL layout. Task titles stay in the language the user wrote.

![KubeMedic overview in English](docs/images/kubemedic/dashboard-en.png)

![KubeMedic overview in Arabic](docs/images/kubemedic/dashboard-ar.png)

![INV-000019 in English](docs/images/kubemedic/investigation-en.png)

![INV-000019 in Arabic](docs/images/kubemedic/investigation-ar.png)

![REM-000003 approval record in English](docs/images/remediation/approval-en.png)

![REM-000003 approval record in Arabic](docs/images/remediation/approval-ar.png)

![TaskFlow in English](docs/images/taskflow/taskflow-en.png)

![TaskFlow in Arabic](docs/images/taskflow/taskflow-ar.png)

Earlier captures from the same lab:

![KubeMedic overview](docs/images/kubemedic/overview.png)

![INV-000019 CrashLoopBackOff](docs/images/incidents/inv-000019.png)

![Human-approved remediation record](docs/images/remediation/rem-000003.png)

![TaskFlow](docs/images/taskflow/healthy.png)

![Grafana TaskFlow dashboard](docs/images/observability/grafana-taskflow.png)

![Grafana KubeMedic dashboard](docs/images/observability/grafana-kubemedic.png)

More images are under `docs/images/`. There is no CI screenshot, because a GitHub-hosted run was not observed.

## Quick start

Requirements: Python 3.11+, Docker, and Docker Compose v2. The kind path also needs kind and kubectl.

Compose:

```bash
make setup
make test
make local
make status
```

- UI: http://127.0.0.1:41821
- API: http://127.0.0.1:41822
- PostgreSQL: `127.0.0.1:41823`

Kind:

```bash
make kind-up
make deploy
make deploy-kubemedic
make deploy-monitoring
kubectl -n taskflow port-forward svc/taskflow-frontend 41831:8080
kubectl -n kubemedic port-forward svc/kubemedic 41832:80
```

`make reset` reapplies the healthy TaskFlow manifests. `make clean` removes Compose. `make clean-k8s` deletes only the `taskflow` namespace.

Fixture replay, without using the cluster watcher:

```bash
make kubemedic
./scripts/kubemedic-demo.sh crashloop
```

`make help` lists the targets.

## Testing

```bash
make test
make kubemedic-test
make validate-k8s
make terraform-check
```

`make test` is the TaskFlow backend suite. `make kubemedic-test` is the investigator, AI, and remediation suite. `make validate-k8s` runs kubeconform and, when a cluster is reachable, `kubectl apply --dry-run=client`. It refuses a Git ConfigMap that enables remediation. `make terraform-check` does not plan or apply.

The frontend production build is `npm ci` and `npm run build` in `taskflow/frontend`.

## Repository structure

| Path | What it is |
| --- | --- |
| `taskflow/` | React UI, FastAPI API, Compose file |
| `kubemedic/` | Watcher, rules, API, dashboard, remediator, tests |
| `k8s/` | Manifests for TaskFlow, KubeMedic, and monitoring |
| `infra/terraform/` | Unapplied AWS reference design |
| `scripts/` | Setup, kind, deploy, scans, and Terraform checks |
| `.github/workflows/` | CI, security, image build, and release |
| `docs/` | Demo, design notes, interview material, and screenshots |

## Design decisions

The short version: TaskFlow exists so the investigator has a real workload. kind is the cluster. SQLite is the lab store. Rules are authoritative. AI is optional. Remediation is a second identity and a human gate. Prometheus answers "is it hurting?" and KubeMedic answers "what happened?". Terraform describes AWS without creating it.

The longer version is [docs/design-decisions.md](docs/design-decisions.md).

## Limitations

- One cluster, one namespace, one SQLite file on a ReadWriteOnce volume.
- The remediator only changes Deployments, and only the three allowlisted actions.
- AI does nothing until a key is provided. This lab has not run a live OpenAI call.
- GitHub-hosted Actions were not observed from this environment.
- AWS is a design. There is no EKS cluster.
- Image CVE gates report upstream base-image findings instead of failing the build.
- There is no license file yet. Add one before a public release if you want others to reuse the code.

## Documentation

- [Demo script](docs/demo.md)
- [Local kind guide](docs/local-kind.md)
- [Failure scenarios](docs/failure-scenarios.md)
- [Runbook](docs/runbook.md)
- [CI/CD and supply chain](docs/cicd.md)
- [AWS reference architecture](docs/aws-architecture.md)
- [AWS cost notes](docs/aws-cost-analysis.md)
- [Threat model](docs/threat-model.md)
- [Interview story](docs/interview-story.md)
- [Resume language](docs/resume-description.md)
- [LinkedIn drafts](docs/linkedin-post.md)
- [Portfolio page copy](docs/portfolio-description.md)
