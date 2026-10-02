locals {
  # Both gates must pass. The default apply therefore contains zero AWS resources.
  platform_enabled = var.allow_paid_apply && var.cost_review_acknowledgement == "I reviewed the AWS cost and approve creating billable resources"
}

module "platform" {
  source = "./modules/platform"
  count  = local.platform_enabled ? 1 : 0

  name                      = var.name
  aws_region                = var.aws_region
  vpc_cidr                  = var.vpc_cidr
  enable_nat_gateway        = var.enable_nat_gateway
  cluster_version           = var.cluster_version
  node_desired_size         = var.node_desired_size
  node_min_size             = var.node_min_size
  node_max_size             = var.node_max_size
  github_repository         = var.github_repository
  ecr_repository_names      = var.ecr_repository_names
  break_glass_principal_arn = var.break_glass_principal_arn
}
