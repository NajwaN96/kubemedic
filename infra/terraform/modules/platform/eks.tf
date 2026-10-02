data "aws_iam_policy_document" "eks_cluster_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["eks.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "eks_node_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "cluster" {
  name               = "${var.name}-eks-cluster"
  assume_role_policy = data.aws_iam_policy_document.eks_cluster_assume.json

  tags = {
    Name = "${var.name}-eks-cluster"
  }
}

resource "aws_iam_role_policy_attachment" "cluster" {
  role       = aws_iam_role.cluster.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
}

resource "aws_iam_role" "node" {
  name               = "${var.name}-eks-node"
  assume_role_policy = data.aws_iam_policy_document.eks_node_assume.json

  tags = {
    Name = "${var.name}-eks-node"
  }
}

resource "aws_iam_role_policy_attachment" "node" {
  role       = aws_iam_role.node.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
}

data "aws_iam_policy_document" "node_ecr_pull" {
  statement {
    sid       = "EcrAuth"
    effect    = "Allow"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid    = "EcrPull"
    effect = "Allow"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
    ]
    resources = [for repo in aws_ecr_repository.app : repo.arn]
  }
}

resource "aws_iam_role_policy" "node_ecr_pull" {
  name   = "${var.name}-node-ecr-pull"
  role   = aws_iam_role.node.id
  policy = data.aws_iam_policy_document.node_ecr_pull.json
}

resource "aws_eks_cluster" "this" {
  name     = var.name
  version  = var.cluster_version
  role_arn = aws_iam_role.cluster.arn

  vpc_config {
    subnet_ids              = aws_subnet.private[*].id
    endpoint_private_access = true
    endpoint_public_access  = false
    security_group_ids      = [aws_security_group.cluster.id]
  }

  access_config {
    authentication_mode                         = "API"
    bootstrap_cluster_creator_admin_permissions = false
  }

  upgrade_policy {
    support_type = "STANDARD"
  }

  # Empty on purpose. Control plane logs publish to CloudWatch and are billed.
  enabled_cluster_log_types = []

  depends_on = [aws_iam_role_policy_attachment.cluster]

  tags = {
    Name = var.name
  }
}

data "tls_certificate" "eks" {
  url = aws_eks_cluster.this.identity[0].oidc[0].issuer
}

resource "aws_iam_openid_connect_provider" "eks" {
  url             = aws_eks_cluster.this.identity[0].oidc[0].issuer
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.eks.certificates[0].sha1_fingerprint]
}

locals {
  eks_oidc_host = replace(aws_iam_openid_connect_provider.eks.url, "https://", "")
}

data "aws_iam_policy_document" "vpc_cni_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.eks.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.eks_oidc_host}:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.eks_oidc_host}:sub"
      values   = ["system:serviceaccount:kube-system:aws-node"]
    }
  }
}

data "aws_iam_policy_document" "ebs_csi_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.eks.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.eks_oidc_host}:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.eks_oidc_host}:sub"
      values   = ["system:serviceaccount:kube-system:ebs-csi-controller-sa"]
    }
  }
}

resource "aws_iam_role" "vpc_cni" {
  name               = "${var.name}-vpc-cni"
  assume_role_policy = data.aws_iam_policy_document.vpc_cni_assume.json

  tags = {
    Name = "${var.name}-vpc-cni"
  }
}

resource "aws_iam_role_policy_attachment" "vpc_cni" {
  role       = aws_iam_role.vpc_cni.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
}

resource "aws_iam_role" "ebs_csi" {
  name               = "${var.name}-ebs-csi"
  assume_role_policy = data.aws_iam_policy_document.ebs_csi_assume.json

  tags = {
    Name = "${var.name}-ebs-csi"
  }
}

resource "aws_iam_role_policy_attachment" "ebs_csi" {
  role       = aws_iam_role.ebs_csi.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy"
}

resource "aws_launch_template" "nodes" {
  name_prefix            = "${var.name}-node-"
  description            = "IMDSv2 and an encrypted root volume for the managed node group"
  update_default_version = true

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }

  monitoring {
    enabled = false
  }

  block_device_mappings {
    device_name = "/dev/xvda"

    ebs {
      volume_size           = 20
      volume_type           = "gp3"
      encrypted             = true
      delete_on_termination = true
    }
  }

  tag_specifications {
    resource_type = "instance"

    tags = {
      Name = "${var.name}-node"
    }
  }
}

resource "aws_eks_node_group" "this" {
  cluster_name    = aws_eks_cluster.this.name
  node_group_name = "${var.name}-nodes"
  node_role_arn   = aws_iam_role.node.arn
  subnet_ids      = aws_subnet.private[*].id
  ami_type        = "AL2023_x86_64_STANDARD"
  capacity_type   = "ON_DEMAND"
  instance_types  = ["t3.small"]

  scaling_config {
    desired_size = var.node_desired_size
    min_size     = var.node_min_size
    max_size     = var.node_max_size
  }

  update_config {
    max_unavailable_percentage = 50
  }

  launch_template {
    id      = aws_launch_template.nodes.id
    version = aws_launch_template.nodes.latest_version
  }

  labels = {
    workload = "taskflow"
  }

  depends_on = [
    aws_iam_role_policy_attachment.node,
    aws_iam_role_policy.node_ecr_pull,
  ]

  tags = {
    Name = "${var.name}-nodes"
  }
}

resource "aws_eks_addon" "vpc_cni" {
  cluster_name                = aws_eks_cluster.this.name
  addon_name                  = "vpc-cni"
  service_account_role_arn    = aws_iam_role.vpc_cni.arn
  resolve_conflicts_on_create = "NONE"
  resolve_conflicts_on_update = "NONE"

  depends_on = [aws_iam_role_policy_attachment.vpc_cni]
}

resource "aws_eks_addon" "coredns" {
  cluster_name                = aws_eks_cluster.this.name
  addon_name                  = "coredns"
  resolve_conflicts_on_create = "NONE"
  resolve_conflicts_on_update = "NONE"
}

resource "aws_eks_addon" "kube_proxy" {
  cluster_name                = aws_eks_cluster.this.name
  addon_name                  = "kube-proxy"
  resolve_conflicts_on_create = "NONE"
  resolve_conflicts_on_update = "NONE"
}

resource "aws_eks_addon" "ebs_csi" {
  cluster_name                = aws_eks_cluster.this.name
  addon_name                  = "aws-ebs-csi-driver"
  service_account_role_arn    = aws_iam_role.ebs_csi.arn
  resolve_conflicts_on_create = "NONE"
  resolve_conflicts_on_update = "NONE"

  depends_on = [aws_iam_role_policy_attachment.ebs_csi]
}

resource "aws_eks_access_entry" "break_glass" {
  count = var.break_glass_principal_arn == "" ? 0 : 1

  cluster_name  = aws_eks_cluster.this.name
  principal_arn = var.break_glass_principal_arn
  type          = "STANDARD"
}

resource "aws_eks_access_policy_association" "break_glass" {
  count = var.break_glass_principal_arn == "" ? 0 : 1

  cluster_name  = aws_eks_cluster.this.name
  principal_arn = var.break_glass_principal_arn
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSViewPolicy"

  access_scope {
    type       = "namespace"
    namespaces = ["taskflow", "kubemedic", "monitoring"]
  }

  depends_on = [aws_eks_access_entry.break_glass]
}
