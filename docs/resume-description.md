# Resume description

Do not say the project is in production, that AWS is deployed, or that AI remediates incidents. The running environment is a local kind cluster.

## One line

Built KubeMedic, a Kubernetes reliability lab that investigates TaskFlow failures on kind, tracks incidents through recovery, and applies a Deployment change only after human approval.

## Two bullets

- Built a Kubernetes reliability lab that detects workload failures, stores evidence, and tracks incidents from open through stabilized recovery on a local kind cluster.
- Implemented least-privilege remediation for restart, rollback, and scale, with a separate ServiceAccount, human approval, and checks that the Deployment generation actually changed. CI runs tests, kubeconform, secret scanning, and image SBOMs. The EKS design is Terraform only and was not provisioned.

## Three technical bullets

- Implemented Kubernetes failure detection and an incident lifecycle for a real TaskFlow workload, including stale-event handling and reconciliation when a Pod disappears.
- Separated a read-only observer from an allowlisted remediator, and fixed rollback verification so readiness alone cannot mark a no-op patch as verified.
- Added Prometheus and Grafana dashboards, GitHub Actions gates with immutable image tags and CycloneDX SBOMs, and a zero-cost Terraform reference design for OIDC, ECR, and EKS that is not applied.

## Facts you can defend

- Failure classes include CrashLoopBackOff, image pull errors, OOMKilled, container config errors, scheduling, probe failures, unavailable replicas, and database connectivity.
- Remediation actions: three. Scale bounds: 1 to 5. Default: disabled.
- Live incident used in the write-up: INV-000019, remediation REM-000003, recovery 75 seconds, analysis source `rules`.
- AWS infrastructure cost from this project: $0.
