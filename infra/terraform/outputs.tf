output "architecture" {
  value       = "Reference AWS Architecture — Not Provisioned"
  description = "Label for this design. The live runtime is the local kind cluster."
}

output "platform_instantiated" {
  value       = local.platform_enabled
  description = "False unless both paid-apply gates are set. A default apply creates no AWS resources."
}

output "nat_gateway_enabled" {
  value       = var.enable_nat_gateway
  description = "Always false. The configuration rejects a true value."
}

output "cluster_name" {
  value       = one(module.platform[*].cluster_name)
  description = "Null while the platform module is omitted."
}

output "ecr_repository_urls" {
  value       = one(module.platform[*].ecr_repository_urls)
  description = "Null while the platform module is omitted."
}

output "github_actions_role_arn" {
  value       = one(module.platform[*].github_actions_role_arn)
  description = "Null while the platform module is omitted."
}
