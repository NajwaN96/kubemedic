variable "aws_region" {
  type        = string
  default     = "us-east-1"
  description = "Region used by the reference design. No data source calls AWS to discover it."

  validation {
    condition     = can(regex("^[a-z]{2}-[a-z]+-[0-9]$", var.aws_region))
    error_message = "aws_region must be a region name such as us-east-1."
  }
}

variable "allow_paid_apply" {
  type        = bool
  default     = false
  description = "Leave false. The platform module is created only when this is true and cost_review_acknowledgement matches exactly."

  validation {
    condition = (
      var.allow_paid_apply == false && var.cost_review_acknowledgement == ""
      ) || (
      var.allow_paid_apply == true && var.cost_review_acknowledgement == "I reviewed the AWS cost and approve creating billable resources"
    )
    error_message = "Keep allow_paid_apply false and the acknowledgement empty. Both must change together, and the acknowledgement must match exactly, before the platform module can be created."
  }
}

variable "cost_review_acknowledgement" {
  type        = string
  default     = ""
  description = "Leave empty. Applying the platform requires the exact acknowledgement string documented in the README."
}

variable "enable_nat_gateway" {
  type        = bool
  default     = false
  description = "Must stay false. A NAT Gateway is billed per hour, per gigabyte, and per public IPv4 address."

  validation {
    condition     = var.enable_nat_gateway == false
    error_message = "NAT Gateway must stay disabled. Enabling it would allocate a public IPv4 address and incur hourly charges."
  }
}

variable "name" {
  type        = string
  default     = "taskflow"
  description = "Short name prefixed onto reference resource names."

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,20}$", var.name))
    error_message = "name must be a short lowercase DNS label."
  }
}

variable "vpc_cidr" {
  type        = string
  default     = "10.40.0.0/16"
  description = "CIDR for the reference VPC."
}

variable "cluster_version" {
  type        = string
  default     = "1.36"
  description = "EKS Kubernetes version in standard support. The kind cluster is a separate version and is not changed by this variable."

  validation {
    condition     = contains(["1.34", "1.35", "1.36"], var.cluster_version)
    error_message = "cluster_version must be an EKS version in standard support (1.34, 1.35, or 1.36). Extended support is a higher hourly charge and is not selectable here."
  }
}

variable "node_desired_size" {
  type        = number
  default     = 0
  description = "Managed node group desired size. Must stay 0 so an apply cannot launch EC2 or EBS."

  validation {
    condition     = var.node_desired_size == 0
    error_message = "node_desired_size must stay 0. A larger value launches EC2 instances and EBS volumes."
  }
}

variable "node_min_size" {
  type        = number
  default     = 0
  description = "Managed node group minimum size. Must stay 0."

  validation {
    condition     = var.node_min_size == 0
    error_message = "node_min_size must stay 0."
  }
}

variable "node_max_size" {
  type        = number
  default     = 2
  description = "Ceiling recorded on the node group. No instances are launched while desired and min stay 0."

  validation {
    condition     = var.node_max_size >= 1 && var.node_max_size <= 2
    error_message = "node_max_size must be 1 or 2 for this reference design."
  }
}

variable "github_repository" {
  type        = string
  default     = "example-org/taskflow-kubemedic"
  description = "GitHub repository allowed to assume the CI role, as ORG/REPO. No wildcards."

  validation {
    condition     = can(regex("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", var.github_repository))
    error_message = "github_repository must be ORG/REPO with no wildcard."
  }
}

variable "ecr_repository_names" {
  type        = list(string)
  default     = ["taskflow-api", "taskflow-frontend", "kubemedic"]
  description = "Image repositories the CI role may push. The remediator uses the kubemedic image."

  validation {
    condition = length(var.ecr_repository_names) > 0 && alltrue([
      for name in var.ecr_repository_names : can(regex("^[a-z0-9]+([._-][a-z0-9]+)*$", name))
    ])
    error_message = "ecr_repository_names must be lowercase ECR names with no wildcard."
  }
}

variable "break_glass_principal_arn" {
  type        = string
  default     = ""
  description = "Optional IAM principal for a read-only EKS access entry. Empty creates no access entry."

  validation {
    condition     = var.break_glass_principal_arn == "" || can(regex("^arn:aws:iam::[0-9]{12}:(role|user)/[A-Za-z0-9+=,_.@/-]+$", var.break_glass_principal_arn))
    error_message = "break_glass_principal_arn must be empty or one IAM role or user ARN."
  }
}
