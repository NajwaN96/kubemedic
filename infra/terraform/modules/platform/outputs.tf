output "cluster_name" {
  value = aws_eks_cluster.this.name
}

output "ecr_repository_urls" {
  value = { for name, repo in aws_ecr_repository.app : name => repo.repository_url }
}

output "github_actions_role_arn" {
  value = aws_iam_role.github_actions.arn
}

output "nat_gateway_count" {
  value = local.nat_gateway_count
}

output "node_desired_size" {
  value = aws_eks_node_group.this.scaling_config[0].desired_size
}
