variable "name" {
  type = string
}

variable "aws_region" {
  type = string
}

variable "vpc_cidr" {
  type = string
}

variable "enable_nat_gateway" {
  type = bool

  validation {
    condition     = var.enable_nat_gateway == false
    error_message = "NAT Gateway must stay disabled in the platform module."
  }
}

variable "cluster_version" {
  type = string

  validation {
    condition     = contains(["1.34", "1.35", "1.36"], var.cluster_version)
    error_message = "cluster_version must stay inside the EKS standard-support set."
  }
}

variable "node_desired_size" {
  type = number

  validation {
    condition     = var.node_desired_size == 0
    error_message = "node_desired_size must stay 0."
  }
}

variable "node_min_size" {
  type = number

  validation {
    condition     = var.node_min_size == 0
    error_message = "node_min_size must stay 0."
  }
}

variable "node_max_size" {
  type = number
}

variable "github_repository" {
  type = string

  validation {
    condition     = can(regex("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", var.github_repository))
    error_message = "github_repository must be ORG/REPO with no wildcard."
  }
}

variable "ecr_repository_names" {
  type = list(string)
}

variable "break_glass_principal_arn" {
  type = string
}
