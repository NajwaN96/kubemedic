# KubeMedic

The portfolio overview is the [repository README](../README.md). This file is the investigator reference.

KubeMedic watches Kubernetes workloads and writes a structured investigation when a reliability problem shows up. It explains the incident. A separate remediator can apply one of three Deployment actions, and only after a person approves that action. Remediation is off unless `KUBEMEDIC_REMEDIATION_ENABLED=true`.

Kubernetes keeps doing its own self-healing. TaskFlow is the sample workload. The watcher only observes, classifies, and recommends.

Detection and the first explanation are deterministic. `analysis_source` is `rules` unless an optional AI pass succeeds, in which case it becomes `rules+ai`. The rule text is kept either way. AI is off unless `KUBEMEDIC_AI_ENABLED=true`.

## What it detects

CrashLoopBackOff, ImagePullBackOff, ErrImagePull, OOMKilled, CreateContainerConfigError, CreateContainerError, FailedMount, FailedScheduling, readiness probe failure, liveness probe failure, repeated restarts, unavailable Deployment replicas, and database connectivity failures in application logs.

Repeated sightings of the same problem update the open investigation instead of creating a new one. The fingerprint is namespace, resource kind, resource name, issue, and container. `KUBEMEDIC_INCIDENT_COOLDOWN_SECONDS` (default 300) also reopens a recently resolved investigation of the same fingerprint.

An investigation is `open` while the failure is current, `recovering` once the resource looks healthy, and `resolved` after it stays healthy for `KUBEMEDIC_RECOVERY_STABILIZATION_SECONDS` (default 60). Events older than `KUBEMEDIC_EVENT_FRESHNESS_SECONDS` (default 300) remain stored and do not by themselves keep the investigation open.

If the Pod disappears, KubeMedic does not treat that as a repair. A healthy owning Deployment moves the investigation through the same stabilization window, with resolution reason `affected Pod was replaced and owning workload is healthy`. A Deployment that is still short of ready replicas keeps the investigation open. An unmanaged Pod, or a Pod whose Deployment is also gone, resolves as `affected resource no longer exists`. Evidence is kept.

## Severity

| Severity | When |
| --- | --- |
| critical | The workload wants replicas and none are ready |
| high | CrashLoopBackOff, OOMKilled, image pull failure, container config failure, liveness failure, database connectivity failure |
| medium | Readiness failure, scheduling failure, mount failure, degraded replicas, repeated restarts |
| low | Any other condition that still produced an investigation |

A high or medium issue is raised to critical when the related Deployment has zero ready replicas.

OOMKilled recommendations ask you to inspect memory behavior. Raising the limit is not the whole fix.

## Run it without a cluster

```bash
make kubemedic
./scripts/kubemedic-demo.sh crashloop
```

The dashboard is [http://127.0.0.1:41832](http://127.0.0.1:41832).

Scenarios: `crashloop`, `bad-image`, `oom`, `missing-secret`, `failed-scheduling`, `readiness`, `database`.

`make kubemedic` sets `KUBEMEDIC_DEMO_MODE=true` and `KUBEMEDIC_WATCH_ENABLED=false`. Both the server and the script use `data/kubemedic.db`. Cluster status stays **Disconnected** until a kubeconfig or an in-cluster ServiceAccount is available. The API and dashboard keep working.

Fixtures in `fixtures/` are sanitized Kubernetes API documents. Replay uses the same collector, rule analyzer, investigation service, and SQLite repository as a live watch.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Process is up |
| GET | `/ready` | SQLite is readable. Kubernetes being down does not fail this |
| GET | `/api/v1/cluster/status` | `connected` or `disconnected`, plus the namespace |
| GET | `/api/v1/investigations` | List. Filters: `status`, `severity`, `issue` |
| GET | `/api/v1/investigations/{id}` | Full investigation |
| POST | `/api/v1/investigations/{id}/resolve` | Mark resolved in SQLite only |
| GET | `/api/v1/remediation/status` | `enabled` and `approval_required`. Approval stays required |
| GET | `/api/v1/remediations` | Stored proposals |
| GET | `/api/v1/investigations/{id}/remediations` | Proposals for one investigation |
| POST | `/api/v1/remediations/{id}/approve` | Approve one typed action. Requires `confirm: true`. 409 when remediation is disabled |
| POST | `/api/v1/investigations/{id}/remediation/approve` | Approve the latest proposed action for that investigation |
| POST | `/api/v1/remediations/{id}/cancel` | Cancel a proposal that has not started |
| GET | `/api/v1/ai/status` | `enabled`, `provider`, `model`, `status`. No credential |
| POST | `/api/v1/investigations/{id}/ai/analyze` | One optional AI pass over stored evidence. Refused with 409 when AI is off. Does not change Kubernetes |
| POST | `/api/v1/demo/{scenario}` | Replay a fixture. Only when `KUBEMEDIC_DEMO_MODE=true` |

## Kubernetes connection

If `KUBERNETES_SERVICE_HOST` is set, KubeMedic loads the in-cluster ServiceAccount. Otherwise it loads kubeconfig. If that fails, status is `disconnected` and the process stays up.

The default namespace is `taskflow`, from `KUBEMEDIC_NAMESPACE`.

The watcher lists Pods, Events, Deployments, and ReplicaSets, and reads Pod logs. It does not create, update, patch, or delete objects, and it does not read Secret data.

On the kind cluster `taskflow`, the in-cluster process reported `connected` and the watcher stored investigations from real Pods. Unit tests cover snapshot classification, a fake list/log client, and serialization of Kubernetes client objects into the API shape the collector expects. `make kubemedic` still runs with the watcher off for fixture replay.

## RBAC

Manifests are in `k8s/kubemedic/`. Both processes run in namespace `kubemedic`. Their Roles are in namespace `taskflow` and are bound to different ServiceAccounts.

The watcher ServiceAccount `kubemedic` uses Role `kubemedic-observer`:

| Resource | Verbs |
| --- | --- |
| pods, events, persistentvolumeclaims | get, list, watch |
| pods/log | get |
| apps/deployments, apps/replicasets | get, list, watch |

The remediator ServiceAccount `kubemedic-remediator` uses Role `kubemedic-remediator`:

| Resource | Verbs |
| --- | --- |
| apps/deployments | get, list, watch, patch, update |
| apps/replicasets | get, list, watch |

Observation stays read-only. The remediator is not given Secret access, ConfigMap access, Pod exec, delete, a ClusterRole, or a wildcard. Both pods mount PersistentVolumeClaim `kubemedic-data`. That claim is ReadWriteOnce, which is enough on the one-node kind cluster.

## Human-approved remediation

```text
Investigation
   ↓
Typed proposal
   ↓
Human approval
   ↓
Policy check
   ↓
Typed executor
   ↓
Verification
   ↓
Audit trail
```

`KUBEMEDIC_REMEDIATION_ENABLED` defaults to false. Proposals can still be recorded so the gate is visible. Approval returns 409 while the flag is false, and the executor is not called. Turning the flag on does not start automatic repair. `approval_required` stays true. There is no automatic-remediation switch.

The allowlist is `restart_deployment`, `rollback_deployment`, and `scale_deployment` for a Deployment in the watched namespace. Scale is an integer from 1 to `KUBEMEDIC_REMEDIATION_MAX_REPLICAS` (default 5). A CrashLoopBackOff on revision 2 or later proposes a rollback. A CrashLoopBackOff without a previous revision proposes a restart. A Deployment that wants zero replicas proposes a scale to 1. Image pull, scheduling, missing configuration, probe failures, database connectivity, and OOMKilled stay informational.

AI text is not an action. The executor builds the patch itself: a restart annotation, a replace of `spec.template` from the previous ReplicaSet, or `spec.replicas`. Replacing the template drops fields the previous revision does not have, including a command added by a bad rollout. Callers cannot supply shell, kubectl, YAML, or a patch document. Verification requires the Deployment generation to change and the updated ready replicas to match the desired count. The audit record stores images, replica counts, revision, and generation. It does not store environment values or Secret contents.

Statuses are `proposed`, `approved`, `executing`, `succeeded`, `failed`, `cancelled`, and `verified`. `succeeded` means the API accepted the patch. `verified` means the Deployment later reported enough ready replicas. A verification timeout stays `failed`.

The remediator process is `python -m app.remediation.runner`. It reads the same SQLite file as the API. A ConfigMap change is picked up when that pod restarts.

## AI-assisted investigation

```text
Kubernetes
   ↓
Evidence
   ↓
Rules
   ↓
Investigation
   ↓
Sanitizer
   ↓
Optional AI
   ↓
Enhanced explanation
```

Rules always run first. The AI provider sees a small sanitized payload: issue, severity, namespace, resource kind, container state, exit code, restart count, memory limit, a few events, bounded logs, and the rule analysis. It does not receive the Kubernetes object, the resource name, Secret data, or the API key. A successful result is stored beside the rule result as `ai_analysis`. `analysis_source` becomes `rules+ai`. A failure leaves the rule investigation intact and sets `ai_status` to a non-secret reason such as `quota_exhausted`, `authentication_error`, `timeout`, or `unavailable`.

The watcher calls the provider once per evidence signature. Another poll that only increments `occurrence_count` does not call again. `POST /api/v1/investigations/{id}/ai/analyze` is the explicit retry and is the way to analyze an investigation that already exists. Historical investigations are not sent automatically.

`KUBEMEDIC_AI_ENABLED` defaults to false. `KUBEMEDIC_AI_PROVIDER` defaults to `openai`. `OPENAI_API_KEY` and `OPENAI_MODEL` come from the environment. The model default in code is `gpt-4o-mini` when `OPENAI_MODEL` is unset. The key is not written to Git, to the dashboard, or to `/api/v1/ai/status`.

## Privacy and security

KubeMedic does not request Kubernetes Secret objects. Neither the observer Role nor the remediator Role includes `secrets`. The observer Role has no write verbs.

Before a payload can leave the process, assignments of password, passwd, token, api_key, authorization, secret, client_secret, and access_key are replaced with `[REDACTED]`. The same pass covers bearer tokens, OpenAI-style `sk-` keys, AWS access key ids, database and HTTP URLs that contain a username and password, private-key blocks, and JWT-shaped tokens. A log line such as `secret "taskflow-db" not found` is kept, because that is an error string, not a Secret value.

This redaction is not a guarantee that every secret shape will be recognized. The controls that do not depend on pattern matching are: Secret objects are not read, the AI payload is a projection rather than a full object dump, and AI is off unless it is explicitly enabled.

## Redaction

Logs and event messages are passed through `app/redact.py` before they are stored. URL userinfo, bearer tokens, AWS access-key assignments, and `password` / `token` / `authorization` / `api_key` / `secret` assignments are replaced. A message such as `secret "taskflow-db" not found` is kept, because the Secret value was never read. This is not a complete secret scanner. The primary control is that KubeMedic does not request Secret objects.

## Tests

```bash
make kubemedic-test
```

## Layout

`app/kubernetes/` connects and watches. `app/investigation/collector.py` turns one API-shaped snapshot into evidence. `app/investigation/analyzer.py` applies the rules. `app/investigation/service.py` deduplicates and stores the investigation. Demo fixtures call that same service.
