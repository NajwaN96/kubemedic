# Reference AWS Architecture — Not Provisioned

WARNING:

This Terraform configuration defines AWS resources that may incur charges.

Do not run `terraform apply` unless AWS costs have been explicitly reviewed and approved.

For the portfolio environment this configuration is intentionally plan/design only.

The live runtime is the existing kind cluster. Nothing in this directory is provisioned, and the project workflow does not apply it.

## Two pictures

Reference design, not created:

```text
GitHub
↓
GitHub Actions
↓
OIDC
↓
AWS IAM
↓
ECR
↓
EKS
├── TaskFlow
├── KubeMedic
├── PostgreSQL
└── Prometheus/Grafana
```

What actually runs:

```text
Developer
↓
Docker
↓
kind Kubernetes
├── TaskFlow
├── KubeMedic
├── PostgreSQL
└── Prometheus/Grafana
```

PostgreSQL stays an in-cluster StatefulSet. Prometheus and Grafana stay in-cluster. This design does not define RDS, Amazon Managed Prometheus, or Amazon Managed Grafana.

## What `terraform apply` does today

The platform module is created only when both of these are true:

- `allow_paid_apply = true`
- `cost_review_acknowledgement` equals `I reviewed the AWS cost and approve creating billable resources`

Both default the other way. A default apply has an empty resource set. `enable_nat_gateway` is `false`, and validation rejects `true`, so a NAT Gateway cannot be turned on by a variable. Node `desired_size` and `min_size` are validated at `0`.

Do not flip those gates for this portfolio. Even an approved apply of the module would start billing, because an EKS control plane is charged per hour with zero nodes.

## Checks that are allowed

From the repository root:

```bash
make terraform-check
```

That command runs:

- `terraform fmt -check`
- `terraform init -backend=false`
- `terraform validate`
- Trivy configuration scanning

It refuses `apply`, `destroy`, and `plan`. `plan` calls AWS. CI uses the same script. No workflow applies infrastructure, and no workflow requests `id-token: write`.

Trivy scans `infra/terraform` and `infra/terraform/modules/platform`. The second path matters because the platform module is not instantiated, so a scan of the root alone does not see its resources. The gate fails on HIGH and CRITICAL findings.

`AWS-0039` (EKS secret encryption) is the one ignored HIGH finding. Envelope encryption of Kubernetes secrets requires a customer-managed KMS key, and that key is a monthly charge, so the resource is not defined. The exception is in `.trivyignore`. A full scan still reports two MEDIUM findings that the gate does not fail: `AWS-0038` (control plane logging) and `AWS-0178` (VPC flow logs). Both publish to CloudWatch and are omitted on purpose. Public endpoints, public addresses, and open ingress are not ignored.

State is local (`terraform.tfstate`). `*.tfstate`, `*.tfstate.*`, and `.terraform/` are gitignored. There is no remote state bucket.

## Networking

| Piece | Reference choice |
| --- | --- |
| VPC | `10.40.0.0/16`, DNS hostnames on |
| Availability Zones | `us-east-1a` and `us-east-1b`, written in the configuration so a plan does not need an Availability Zone lookup |
| Public subnets | `10.40.0.0/24`, `10.40.1.0/24`, default route to an internet gateway, `map_public_ip_on_launch = false` |
| Private subnets | `10.40.10.0/24`, `10.40.11.0/24`, route table with no default route |
| Cluster and nodes | Private subnets only |
| Security groups | Node-to-node, control plane to kubelet, nodes to the API on 443. No `0.0.0.0/0` ingress. Egress is HTTPS to the VPC CIDR |
| Load balancer tags | `kubernetes.io/role/elb` and `kubernetes.io/role/internal-elb` are labels only. The AWS Load Balancer Controller is not installed, so the tags do not create a load balancer |

An internet gateway has no hourly charge. A public subnet without a public address and without a workload does not expose a node. Production worker nodes belong in the private subnets, which is where this design places them.

### NAT Gateway cost

A NAT Gateway is how private nodes usually reach the internet, including ECR, without a public address on each node. In the published US East (Ohio) example on the Amazon VPC pricing page, a NAT Gateway is **$0.045 per hour** and **$0.045 per GB** processed. A public NAT Gateway also uses a public IPv4 address, billed at **$0.005 per hour**. One gateway per Availability Zone doubles the hourly charge. This configuration does not define a NAT Gateway or an Elastic IP.

Private nodes with no NAT Gateway and no VPC interface endpoint cannot pull from ECR. That is acceptable here because images are loaded into kind, and the node group desired size is 0. A later approved design has to choose one paid egress path before any node is scaled above zero. Interface VPC endpoints are hourly. They are not defined. Gateway endpoints for S3 are free, and they do not serve ECR.

## EKS

The cluster resource is inside the uninstantiated module.

| Topic | Choice |
| --- | --- |
| Version | `1.36` by default. `1.34` and `1.35` are the other standard-support versions as of 2026-10-01. Standard support is **$0.10 per cluster per hour**. Extended support is **$0.60 per cluster per hour**. `upgrade_policy.support_type` is hardcoded to `STANDARD` |
| kind | The live cluster is kind on Kubernetes 1.37. This variable does not change it |
| Managed node group | Amazon Linux 2023, `ON_DEMAND`, `t3.small`, private subnets, desired 0, min 0, max 2 |
| Root volume | Launch template requests a 20 GiB encrypted gp3 volume. The volume is created only if a node launches. There is no standalone EBS volume resource |
| API endpoint | Private only. Public access is hardcoded off |
| Authentication | `API` mode. The cluster creator does not receive admin permissions |
| Access entry | None, unless `break_glass_principal_arn` is one IAM role or user ARN. That optional entry is `AmazonEKSViewPolicy` on namespaces `taskflow`, `kubemedic`, and `monitoring`. It is not cluster-admin |
| Add-ons | `vpc-cni`, `coredns`, `kube-proxy`, `aws-ebs-csi-driver` |
| Logs | `enabled_cluster_log_types` is empty. Control plane logs go to CloudWatch and are billed. VPC flow logs are omitted for the same reason |
| KMS | ECR uses AES256. EBS uses the AWS-managed encryption key. A customer-managed KMS key has a monthly charge and is not defined |

Scaling the node group above zero launches EC2 and the root EBS volume. The control plane is billed even at zero nodes, which is why the module stays omitted.

If this module were applied as written, Kubernetes API calls would fail until a reviewed access entry was added. That lockout is deliberate: the GitHub role is not given `eks:AccessKubernetesApi`, and nobody is granted cluster-admin.

## ECR

Three immutable repositories: `taskflow/taskflow-api`, `taskflow/taskflow-frontend`, and `taskflow/kubemedic`. The remediator uses the KubeMedic image. Scan on push uses basic scanning. Enhanced scanning uses Amazon Inspector and is not configured. CI builds images and stores them as workflow artifacts. It does not push to ECR.

## IAM and GitHub OIDC

The GitHub OIDC provider trusts `token.actions.githubusercontent.com`. The role trust allows only `repo:ORG/REPO:ref:refs/heads/main` for `github_repository` (default `example-org/taskflow-kubemedic`). The audience must be `sts.amazonaws.com`.

The inline policy allows:

- `ecr:GetAuthorizationToken` on `*`, which AWS requires for a token
- layer upload and `PutImage` on the three repository ARNs
- `eks:DescribeCluster` on this cluster ARN
- `eks:ListClusters` on `*`, which the list API requires

It does not allow `eks:CreateCluster`, `eks:AccessKubernetesApi`, `ec2:*`, `iam:*`, or `AdministratorAccess`. Pull requests cannot assume the role. The workflow in this repository does not request an OIDC token.

IRSA roles exist for `kube-system/aws-node` (`AmazonEKS_CNI_Policy`) and `kube-system/ebs-csi-controller-sa` (`AmazonEBSCSIDriverPolicy`). The node role gets `AmazonEKSWorkerNodePolicy` plus a pull policy scoped to the three repositories. The node role does not get the account-wide ECR read policy or the CNI policy.

## Kubernetes, RBAC, and KubeMedic

Workload YAML stays in `k8s/`. Terraform does not copy it. On the reference cluster a person would apply that YAML after the cluster existed. The kind deploy scripts remain the path that actually runs.

KubeMedic's split is unchanged:

- Service account `kubemedic` is bound to Role `kubemedic-observer` in namespace `taskflow`: get, list, and watch pods, events, PVCs, pod logs, deployments, and replica sets. No secrets and no writes.
- Service account `kubemedic-remediator` is bound to Role `kubemedic-remediator`: deployments get, list, watch, patch, and update; replica sets get, list, and watch. No secrets, exec, delete, ClusterRole, or wildcard.
- `KUBEMEDIC_REMEDIATION_ENABLED` stays `false` in Git. Approval is still required when that flag is on. The allowlist is `restart_deployment`, `rollback_deployment`, and `scale_deployment`.

The EBS CSI add-on would create volumes when a PersistentVolumeClaim binds. Those volumes are billed. PostgreSQL on EKS would use that path. It is not RDS, and no volume is defined in Terraform.

Subnet tags do not install a load balancer. There is no Ingress controller in this design.

## What would cost money if the module were applied

Published list prices, checked on 2026-10-01. Region rates differ. The NAT figures are the US East (Ohio) example on the Amazon VPC pricing page.

| If created | Charge |
| --- | --- |
| Nothing, which is this portfolio | **$0**. No account resources are created |
| EKS control plane on standard support | $0.10 per cluster per hour, including at zero nodes |
| EKS extended support | $0.60 per cluster per hour. Not selectable here |
| Managed nodes above desired 0 | EC2 hours plus the 20 GiB gp3 root volume per node |
| NAT Gateway | $0.045 per hour and $0.045 per GB, plus $0.005 per hour for its public IPv4. Not defined |
| Public IPv4 on a node or load balancer | $0.005 per hour. None are allocated |
| CloudWatch logs or VPC flow logs | Ingestion and storage. Both are omitted |
| Customer-managed KMS key | Monthly key charge. Not defined |
| ECR enhanced scanning | Inspector pricing. Basic scan on push is the setting used here |
| EBS volumes from PVCs | Billed when a claim binds. No volume resource is defined |
| ECR storage | Billed when images are stored. This repo does not push |

VPC, subnets, route tables, security groups, IAM, and an internet gateway have no hourly resource charge. They still are not created, because the module count is zero.

## Files

```text
infra/terraform/
├── versions.tf
├── variables.tf
├── main.tf
├── outputs.tf
├── .trivyignore
├── .terraform.lock.hcl
└── modules/platform/
    ├── versions.tf
    ├── variables.tf
    ├── network.tf
    ├── ecr.tf
    ├── iam.tf
    ├── eks.tf
    └── outputs.tf
```
