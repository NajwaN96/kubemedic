# AWS cost analysis

**Reference only. Not provisioned. No AWS resources were created. `terraform apply` was not run. AWS infrastructure cost from this project is $0.**

The kind cluster, local Docker images, and GitHub Actions minutes are outside this note. This note is about AWS infrastructure the Terraform module describes and does not create.

## This portfolio

| Item | Cost |
| --- | --- |
| VPC, subnets, route tables, security groups, IAM, internet gateway | Not created |
| NAT Gateway and public IPv4 | Not created. The variable cannot be set true |
| EKS control plane | Not created. Would be $0.10 per cluster per hour on standard support, including at zero nodes |
| EC2 workers and their EBS root volumes | Not created. Desired size is fixed at 0 |
| Load balancers, RDS, Route 53 | Not in the configuration |
| CloudWatch logs and VPC flow logs | Not configured |
| Customer-managed KMS | Not configured |
| ECR storage | Not created. CI does not push images |
| Enhanced ECR scanning | Not configured. Basic scan on push is the setting inside the unapplied module |

## If someone later removed the gates

These are list prices so a reviewer can see why the gates exist. They are not an invoice.

| Resource | Published charge used in the design notes |
| --- | --- |
| EKS standard support | $0.10 per cluster per hour |
| EKS extended support | $0.60 per cluster per hour. Not selectable in this module |
| NAT Gateway | $0.045 per hour and $0.045 per GB in the US East (Ohio) example, plus $0.005 per hour for its public IPv4 address. One per Availability Zone multiplies the hourly charge |
| In-use public IPv4 | $0.005 per hour |
| EBS volumes | Billed when a node launches or a PersistentVolumeClaim binds. No `aws_ebs_volume` resource is defined |
| CloudWatch | Billed for ingestion and storage if control plane logs or flow logs were enabled |

A default `terraform apply` does not reach those resources, because the platform module count is 0. Applying after both acknowledgement gates are changed would start the control-plane charge immediately. That is why the README in `infra/terraform/` says not to apply unless cost has been reviewed, and why CI will not apply for you.
