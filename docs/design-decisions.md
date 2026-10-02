# Design decisions

## Why TaskFlow exists

KubeMedic needs a workload with a real process, a database, probes, and metrics. TaskFlow is that application: tasks in PostgreSQL, a small UI, and health endpoints. It is not the product being demonstrated.

## Why kind

The lab has to run on one machine without a cloud bill. kind provides a Kubernetes API, a kubelet, and a Service network. The cluster name is `taskflow`. The native snapshotter avoids an overlay-on-overlay failure in this environment. kube-proxy uses nftables because this kernel rejects the iptables statistic match.

## Why Kubernetes

The failures KubeMedic explains are Kubernetes failures: crash loops, image pull, scheduling, probes, missing configuration, and replica drift. A Compose-only demo cannot show those objects, RBAC, or a second ServiceAccount.

## Why FastAPI

The API is small, typed, and easy to test. TaskFlow and KubeMedic both use it. Metrics are plain Prometheus text on `/metrics`.

## Why SQLite

One investigator and one remediator share a file on a ReadWriteOnce volume. WAL mode lets both processes use it on the single kind node. There is no database server to operate. A production store would be a replicated database with more than one writer node. That is intentionally out of scope.

## Why deterministic rules

The same Pod status should produce the same issue, severity, and proposal every time. Rules are testable without a network. `analysis_source` stays `rules` unless an optional AI pass succeeds, and even then the rule text is kept.

## Why optional AI

An extra explanation can help a reader who was not watching the cluster. It is not the source of truth. The provider sees a sanitized copy of stored evidence, not the API server. If the call fails, the investigation is unchanged. The default is off, and no key is stored in Git.

## Why stale event freshness

Kubernetes events outlive the condition that created them. `KUBEMEDIC_EVENT_FRESHNESS_SECONDS` (default 300) keeps those events in the record and stops them from holding an incident open after the Pod has recovered. Freshness is applied only when the caller passes the current time.

## Why a stabilization window

One healthy observation is not recovery. A Pod can become ready and crash again inside the same minute. `KUBEMEDIC_RECOVERY_STABILIZATION_SECONDS` (default 60) is why status moves open, then recovering, then resolved. One poll never resolves.

## Why orphan reconciliation

Deleting a Pod, or losing the object between polls, is not proof that the failure is gone. If the owning Deployment is healthy, the incident still waits out the stabilization window and then resolves with a reason that says the Pod was replaced. If the Deployment is still short of replicas, the incident stays open. Evidence is not deleted.

## Why a separate remediator

The watcher should keep working if remediation is disabled or the remediator is scaled to zero. Its ServiceAccount cannot patch Deployments. The remediator process is a second Deployment, `python -m app.remediation.runner`, with its own ServiceAccount.

## Why human approval

A restart, rollback, or scale changes a live workload. The lab requires `confirm: true`, an approver name, and a reason that is stored and not executed as a command. The feature flag defaults to false. Disabled approval returns 409.

## Why no automatic remediation

Several real failures are fixed by a human changing an image, a Secret, a probe, or cluster capacity. An automatic restart would hide that. The allowlist is only three Deployment actions. AI text is ignored when proposals are created.

## Why Prometheus and Grafana

Prometheus is the metrics store already used for request rate, errors, restarts, and investigation counts. Grafana is the view. KubeMedic does not try to graph time series itself. kube-state-metrics and a narrow cAdvisor scrape add cluster facts. They are not a second investigation engine.

## Why GitHub Actions

The gates match the stack: pytest, a frontend production build, kubeconform, gitleaks, Trivy, and an image archive with a CycloneDX SBOM. Hosted runners have no cluster, so CI does not deploy.

## Why an SBOM

The image report should say what was packaged, not only which CVEs Trivy saw that day. CycloneDX is attached to the workflow artifacts. Images are not signed.

## Why Terraform

The AWS shape is specific enough to review: network, ECR, EKS, IAM, and GitHub OIDC. Terraform makes that reviewable and gives CI a validate step. The module count stays zero so a default apply creates nothing.

## Why AWS is reference-only

An EKS control plane is billed per hour even with zero nodes. NAT Gateways, public IPv4 addresses, load balancers, and CloudWatch logs add more. The portfolio question is whether the design is coherent and least-privilege, not whether a cluster is sitting idle. Nothing was applied. Cost from AWS infrastructure in this project is $0.
