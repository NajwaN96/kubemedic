# LinkedIn

Two drafts. Both are accurate only if AWS stays undescribed as "deployed" and AI stays optional.

## Full

I built KubeMedic, a Kubernetes reliability lab, and used a small task app called TaskFlow as the workload.

Kubernetes will restart a container or replace a Pod. That does not tell you what failed, which logs and events support the diagnosis, or whether the application actually recovered. KubeMedic watches the TaskFlow namespace, classifies the failure with local rules, and keeps one investigation from open, to recovering, to resolved.

Prometheus and Grafana show the service symptoms: ready replicas, error rate, open investigations. The investigation page keeps the evidence after the incident is closed.

AI can add an explanation of a sanitized copy of that evidence. It is off unless a key is configured. It does not see the API server, and it cannot run a remediation.

The write path is separate. A read-only ServiceAccount watches. A second ServiceAccount can restart, roll back, or scale a Deployment, only after a person confirms the action, and only when the lab flag is on. The flag is off by default. The first rollback attempts taught me not to trust ready replicas alone: the Deployment generation had not moved, because the patch content type was wrong. The fixed path requires the generation to advance and the new Pods to become ready. On the incident I use in the write-up, that rollback returned the API to 2/2.

GitHub Actions runs the tests, kubeconform, gitleaks, Trivy, and a CycloneDX SBOM. It does not deploy the cluster. I also wrote a Terraform design for GitHub OIDC, ECR, and EKS. It is not provisioned. The AWS infrastructure cost from the project is $0. The system that actually runs is kind on my machine.

The lesson I would keep: a successful-looking health check is not the same thing as a change that landed.

## Short

I built KubeMedic, a lab that investigates Kubernetes failures instead of only restarting them.

It watches a real TaskFlow app on kind, stores the evidence, and tracks each incident until the workload has stayed healthy. A Deployment change is possible only after a person approves a typed action. Prometheus and Grafana cover the metrics. GitHub Actions runs tests, kubeconform, and image SBOMs, and does not deploy. The EKS and ECR design is Terraform, and it was not applied.

The bug I cared about: a rollback looked verified while the Deployment generation never changed. Ready Pods from the old revision were still up. Verification now requires the generation to move.
