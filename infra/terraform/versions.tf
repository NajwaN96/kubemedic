terraform {
  required_version = ">= 1.9.0, < 2.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.70"
    }
  }

  # Local state only. A remote backend would be another AWS resource.
  backend "local" {
    path = "terraform.tfstate"
  }
}

provider "aws" {
  region = var.aws_region

  # Static checks must not need credentials or the instance metadata service.
  skip_credentials_validation = true
  skip_requesting_account_id  = true
  skip_metadata_api_check     = true
  skip_region_validation      = true

  default_tags {
    tags = {
      Project     = "taskflow"
      Environment = "reference-not-provisioned"
      CostCenter  = "portfolio-zero"
      ManagedBy   = "terraform"
    }
  }
}
