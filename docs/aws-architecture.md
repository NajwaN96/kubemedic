# Reference AWS Architecture — Not Provisioned

Designed in Terraform under `infra/terraform/`. Not provisioned. No AWS resources were created. `terraform apply` was not run. `terraform plan` was not run. AWS infrastructure cost from this project is **$0**.

The live system remains kind. See the repository README for that picture. This document is only the reference.

## Shape

```text
GitHub
→ GitHub Actions
→ OIDC
→ AWS IAM
→ ECR
→ EKS
   ├── TaskFlow
   ├── KubeMedic
   ├── PostgreSQL
   └── Monitoring
```

PostgreSQL is a StatefulSet in the design, not RDS. Prometheus and Grafana stay in the cluster, not Amazon Managed Prometheus or Grafana.

## Safety gates

| Gate | Default |
| --- | --- |
| `allow_paid_apply` | `false` |
| `cost_review_acknowledgement` | empty. The module is created only when this equals the exact sentence in `infra/terraform/README.md` |
| `enable_nat_gateway` | `false`, and validation rejects `true` |
| `node_desired_size` and `node_min_size` | `0` |
| CI | `fmt`, `init -backend=false`, `validate`, Trivy config. The script exits if asked to plan or apply |
| State | Local `terraform.tfstate`. `*.tfstate`, `*.tfstate.*`, and `.terraform/` are gitignored. There is no remote backend |

Do not flip the gates to "see what would happen" on an account you care about. An applied EKS control plane is billed per hour at zero nodes.

## What the module would create if those gates were changed

That is a description, not a request to create it.

- VPC `10.40.0.0/16` in `us-east-1a` and `us-east-1b`
- Public subnets with an internet gateway and `map_public_ip_on_launch = false`
- Private subnets with no default route
- Security groups with no `0.0.0.0/0` ingress
- Three immutable ECR repositories and basic scan on push
- EKS 1.36, standard support, private API, API authentication, no cluster-creator admin
- Managed node group, Amazon Linux 2023, desired 0, on private subnets
- GitHub OIDC role trusted only for `repo:ORG/REPO:ref:refs/heads/main`
- IRSA for the VPC CNI and the EBS CSI driver

The CI role can push those three repositories and describe the cluster. It cannot call `eks:AccessKubernetesApi` or create the cluster. KubeMedic RBAC would still be the YAML in `k8s/kubemedic/`.

Private nodes at desired 0 do not need a pull path. Before any future change scaled nodes above zero, someone would have to choose a paid egress path. NAT is not that choice in this repository. Interface VPC endpoints are not defined either.

## Terraform findings that are not fixed on purpose

| ID | Severity | Why it is still here |
| --- | --- | --- |
| AWS-0039 | HIGH, ignored in `.trivyignore` | EKS secret encryption requires a customer-managed KMS key. That key is a monthly charge. It is not defined |
| AWS-0038 | MEDIUM, not ignored | Control plane logs go to CloudWatch. `enabled_cluster_log_types` is empty |
| AWS-0178 | MEDIUM, not ignored | VPC flow logs go to CloudWatch. No flow log resource exists |

A full `trivy config` scan shows the two MEDIUM findings. The CI gate is HIGH and CRITICAL, with AWS-0039 ignored. Public endpoints, public addresses, and open ingress are not on the ignore list.

## Prices used when writing the design

Checked against AWS pages on 2026-10-01. Region rates differ.

- EKS standard support: $0.10 per cluster per hour
- EKS extended support: $0.60 per cluster per hour. The module hardcodes `STANDARD`
- NAT Gateway, US East (Ohio) example: $0.045 per hour and $0.045 per GB, plus $0.005 per hour for the public IPv4 address

More of the billing notes are in [aws-cost-analysis.md](aws-cost-analysis.md) and `infra/terraform/README.md`.
