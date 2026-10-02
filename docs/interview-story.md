# Interview story

## 30 seconds

I built KubeMedic, a Kubernetes reliability lab. It watches a real application called TaskFlow on a local kind cluster, opens an investigation when something like CrashLoopBackOff happens, and keeps the evidence through recovery. If a fix is a Deployment restart, rollback, or scale, a person has to approve it. Prometheus and Grafana show the symptoms. GitHub Actions runs the tests and security scans. I also wrote a Terraform design for EKS and ECR, and I did not provision it, so the AWS cost is zero.

## 2 minutes

TaskFlow is a small task manager, React and FastAPI in front of PostgreSQL, so KubeMedic has something real to watch. The watcher is read-only. It classifies Pod and Deployment failures with local rules, deduplicates them, and moves each incident from open to recovering to resolved only after the workload stays healthy. Stale Kubernetes events stay in the record but do not keep the incident open. If the Pod disappears, that is not treated as a fix.

Remediation is a second ServiceAccount. It can patch Deployments and nothing else. The flag is off in Git. The interesting bug was a rollback that looked verified because old Pods were still ready, while the Deployment generation never changed. The client had sent a strategic merge with the wrong content type. The fix checks the content type, replaces the Pod template, and refuses to verify unless generation advances.

AI can explain a sanitized copy of the evidence. It is off, it is not the source of truth, and it cannot call Kubernetes. CI builds immutable image tags, an SBOM, and scan reports, and it does not deploy. The AWS module is real Terraform with the platform count set to zero.

## 5 minutes

Start from the gap. Kubernetes will restart a container and replace a Pod. After a bad rollout I still need to know which revision broke, what the logs said, whether the new Pods became ready, and who changed the Deployment back. Metrics answer the first half. The investigation record answers the second.

Detection is a watcher on namespace `taskflow`. The fingerprint is namespace, kind, name, issue, and container, so a crash loop updates one row. Severity is critical when the Deployment wants replicas and none are ready. Otherwise crash loops, OOM, image pull, config errors, liveness, and database failures are high. Scheduling, mounts, readiness, and partial replica loss are medium.

Recovery is two steps. Healthy right now means recovering. Healthy for the stabilization window means resolved. One poll cannot skip the window. Orphan reconciliation covers a deleted Pod: the owner has to be healthy, and the reason text says the Pod was replaced.

The remediation path is intentionally narrow. Rules propose rollback when CrashLoopBackOff starts on revision 2 or later, restart for the other restartable cases, and scale to 1 only when desired is 0. Image pull, scheduling, probes, OOM, and database failures stay informational. Approval is a name, a reason, and `confirm: true`. The executor does not accept a patch document from the client.

On INV-000019 the first two rollback records were false verifies. REM-000003 is the one that moved generation from 3 to 4 and returned the API to 2/2. I left the bad rows in the database because they are the lesson. Remediation is disabled again.

For a production version I would replace SQLite, add authentication on the approval API, and decide an egress path before any private node could pull from ECR. I would not turn on automatic remediation just because the happy path worked once.

## Questions

**What problem does KubeMedic solve?**
It records what failed, the evidence, and whether the workload actually recovered. Kubernetes self-healing does not write that down.

**Why did you build TaskFlow too?**
The investigator needs a workload with probes, a database, and metrics. TaskFlow is that stand-in. It is ordinary CRUD, which keeps the demo about operations rather than about the sample app.

**Why Kubernetes?**
The failures are Kubernetes objects and events. Compose can run TaskFlow. It cannot show CrashLoopBackOff, ReplicaSets, or a second ServiceAccount.

**Doesn't Kubernetes already self-heal?**
It restarts and replaces. It does not explain the rollout, decide that a rollback is safe, or wait to see that the new generation became ready. KubeMedic is that layer.

**How is KubeMedic different from Prometheus?**
Prometheus stores time series. KubeMedic stores an incident with logs, events, a lifecycle, and an approval audit. The Grafana boards read Prometheus. They do not replace the investigation.

**Why Prometheus?**
The applications already expose `/metrics`. Prometheus is the usual scraper, and Grafana already speaks it. I did not need a second metrics database.

**Why Grafana?**
It is the view for request rate, ready replicas, and investigation counts. Anonymous view-only access is enough for the lab.

**How are incidents detected?**
The watcher lists and watches Pods, events, and Deployments. Rules map status, waiting reasons, probe failures, and log hints onto issue types.

**How do you avoid duplicate incidents?**
The fingerprint is namespace, resource kind, resource name, issue, and container. Repeats increment the occurrence count. A recently resolved fingerprint can reopen inside a cooldown instead of looking like a brand new incident.

**How do stale Kubernetes events work?**
Events older than the freshness window, 300 seconds by default, remain stored. They do not by themselves keep the investigation open.

**What happens when a Pod disappears?**
Absence is not success. If the owning Deployment is healthy, the incident still goes through recovering and then resolved, with a reason that the Pod was replaced. If the Deployment is still short, the incident stays open. If the owner is gone, it resolves as a missing resource. Evidence stays.

**How does incident recovery work?**
Healthy observation moves it to recovering. It resolves only after the stabilization window, default 60 seconds.

**Why a stabilization window?**
A single ready status can flap. The window forces the next poll to agree.

**Why deterministic rules before AI?**
The classification has to be stable and testable when the network is down. AI is an optional comment on the same evidence.

**What happens if OpenAI is unavailable?**
Nothing in the record changes. `analysis_source` stays `rules`. The dashboard says the deterministic investigation is still available.

**How do you protect Secrets from AI?**
The watcher cannot read Secrets. Stored text is redacted. The AI payload is a bounded, sanitized subset. The default is off, and no key is in Git.

**Why is remediation human-approved?**
A write to a Deployment is an operation, not a conclusion. The person supplies a name and a reason, and must confirm.

**Why not automatic remediation?**
Many of the failures are fixed by changing an image, a Secret, or capacity. An automatic restart would hide that, and a bad automatic rollback is worse than a late one.

**How is remediation restricted?**
Three action names, namespace `taskflow`, scale integers 1 through 5, no shell, no caller-supplied patch, no Secret or ConfigMap writes.

**How did you separate RBAC?**
ServiceAccount `kubemedic` is bound to a read-only Role. ServiceAccount `kubemedic-remediator` is bound to a Role that can patch Deployments and read ReplicaSets. Neither is a ClusterRole.

**How does rollback work?**
The executor sends a JSON patch that replaces `/spec/template` with the previous template. The content type is set explicitly. The client does not get to choose the patch.

**How do you verify remediation?**
The runner fails the attempt if generation does not increase. Verified means updated ready replicas cover the desired count and the observed generation has caught up. Succeeded and verified are different.

**What bug did you find in rollback verification?**
The Kubernetes client defaulted to JSON Patch while the body was a strategic merge, so the API server ignored it. Old ready Pods made readiness look fine. REM-000001 and REM-000002 show that. REM-000003 is the corrected rollback.

**Why SQLite?**
One node, two processes, one file on a PVC. It keeps the lab free of another database. It will not be the store for several clusters.

**What would replace SQLite in production?**
A replicated database with backups, and a single writer or a real locking story. I would not pretend the PVC is highly available.

**How would you scale this to multiple clusters?**
One watcher identity per cluster, a store that is not on that cluster's disk, and a queue for proposals. I would not start by giving one remediator a ClusterRole across all of them.

**Why GitHub Actions?**
The checks are the ones this repo needs: tests, a frontend build, kubeconform, secret scanning, dependency and image scans, and an SBOM. Hosted runners have no cluster, so deploy stays a local command.

**What security gates exist?**
gitleaks, Trivy on pinned dependencies, kubeconform, a Terraform validate and config scan, and a check that remediation stays false in Git. Image CVEs are reported. They do not fail the build, because the base images carry findings.

**What is an SBOM?**
A CycloneDX bill of materials for the built image. It is uploaded with the scan report. The images are not signed.

**Why immutable tags?**
`sha-<12>` and `vX.Y.Z` name one build. `latest` is rejected. The kind manifests stay on `:local` because that is the image loaded into the node, not a registry tag.

**Why Terraform?**
The AWS design is specific: subnets, private API, OIDC subject, ECR repositories, desired size 0. HCL is easier to review than a diagram alone, and `terraform validate` runs in CI.

**Why isn't AWS actually deployed?**
An EKS control plane costs money with zero nodes. NAT, public IPv4, and log delivery cost more. The design is there to review. The running system is kind. Cost from AWS infrastructure is $0.

**How would you deploy it to EKS?**
I would not, on this portfolio account. If a team accepted the bill, they would still have to pick egress for private nodes, add an access entry that is not cluster-admin, keep the same RBAC YAML, and push immutable tags to ECR with the OIDC role. None of that is wired to CI today.

**Why GitHub OIDC?**
The reference role trusts `token.actions.githubusercontent.com` and one `repo:ORG/REPO:ref:refs/heads/main` subject. There is no long-lived access key in the workflow. This repository's workflows do not request `id-token: write`, because they never assume that role.

**What would you change for production?**
Authentication on the approval API, a real datastore, backups, a supported Kubernetes version policy separate from kind, image signing if the registry required it, and an explicit decision about which failures are allowed to become proposals. I would keep the human gate.
