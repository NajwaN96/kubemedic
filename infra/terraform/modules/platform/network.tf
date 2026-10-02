locals {
  availability_zones = ["${var.aws_region}a", "${var.aws_region}b"]
  public_cidrs       = ["10.40.0.0/24", "10.40.1.0/24"]
  private_cidrs      = ["10.40.10.0/24", "10.40.11.0/24"]
  # No NAT Gateway and no Elastic IP are defined. This count is an output, not a resource.
  nat_gateway_count = 0
}

resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = "${var.name}-vpc"
  }
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id

  tags = {
    Name = "${var.name}-igw"
  }
}

resource "aws_subnet" "public" {
  count = length(local.availability_zones)

  vpc_id                  = aws_vpc.this.id
  cidr_block              = local.public_cidrs[count.index]
  availability_zone       = local.availability_zones[count.index]
  map_public_ip_on_launch = false

  tags = {
    Name                     = "${var.name}-public-${local.availability_zones[count.index]}"
    Tier                     = "public"
    "kubernetes.io/role/elb" = "1"
  }
}

resource "aws_subnet" "private" {
  count = length(local.availability_zones)

  vpc_id                  = aws_vpc.this.id
  cidr_block              = local.private_cidrs[count.index]
  availability_zone       = local.availability_zones[count.index]
  map_public_ip_on_launch = false

  tags = {
    Name                              = "${var.name}-private-${local.availability_zones[count.index]}"
    Tier                              = "private"
    "kubernetes.io/role/internal-elb" = "1"
  }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.this.id
  }

  tags = {
    Name = "${var.name}-public"
  }
}

resource "aws_route_table" "private" {
  count = length(local.availability_zones)

  vpc_id = aws_vpc.this.id

  tags = {
    Name = "${var.name}-private-${local.availability_zones[count.index]}"
  }
}

resource "aws_route_table_association" "public" {
  count = length(local.availability_zones)

  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "private" {
  count = length(local.availability_zones)

  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[count.index].id
}

resource "aws_security_group" "cluster" {
  name        = "${var.name}-eks-cluster"
  description = "Additional security group for the EKS API"
  vpc_id      = aws_vpc.this.id

  tags = {
    Name = "${var.name}-eks-cluster"
  }
}

resource "aws_security_group" "nodes" {
  name        = "${var.name}-eks-nodes"
  description = "Worker nodes in the private subnets"
  vpc_id      = aws_vpc.this.id

  tags = {
    Name = "${var.name}-eks-nodes"
  }
}

resource "aws_security_group_rule" "nodes_within_group" {
  type              = "ingress"
  description       = "Node to node inside the node security group"
  security_group_id = aws_security_group.nodes.id
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  self              = true
}

resource "aws_security_group_rule" "nodes_from_cluster" {
  type                     = "ingress"
  description              = "Control plane to node kubelet"
  security_group_id        = aws_security_group.nodes.id
  from_port                = 1025
  to_port                  = 65535
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.cluster.id
}

resource "aws_security_group_rule" "nodes_https_from_cluster" {
  type                     = "ingress"
  description              = "Control plane to node HTTPS"
  security_group_id        = aws_security_group.nodes.id
  from_port                = 443
  to_port                  = 443
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.cluster.id
}

resource "aws_security_group_rule" "cluster_from_nodes" {
  type                     = "ingress"
  description              = "Nodes to the Kubernetes API"
  security_group_id        = aws_security_group.cluster.id
  from_port                = 443
  to_port                  = 443
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.nodes.id
}

resource "aws_security_group_rule" "nodes_https_to_vpc" {
  type              = "egress"
  description       = "HTTPS to addresses inside the VPC CIDR"
  security_group_id = aws_security_group.nodes.id
  from_port         = 443
  to_port           = 443
  protocol          = "tcp"
  cidr_blocks       = [var.vpc_cidr]
}

resource "aws_security_group_rule" "cluster_https_to_vpc" {
  type              = "egress"
  description       = "HTTPS from the API security group into the VPC CIDR"
  security_group_id = aws_security_group.cluster.id
  from_port         = 443
  to_port           = 443
  protocol          = "tcp"
  cidr_blocks       = [var.vpc_cidr]
}
