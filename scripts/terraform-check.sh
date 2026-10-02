#!/usr/bin/env bash
# Format, validate, and scan the Terraform design.
# This script does not plan or apply, and it does not talk to the AWS API.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

for arg in "$@"; do
  case "$arg" in
    apply | destroy | plan | import | refresh)
      echo "terraform-check refuses '${arg}'. The reference design is not applied from this workflow." >&2
      exit 1
      ;;
  esac
done

if grep -RInE 'terraform[[:space:]]+(apply|destroy|plan)' .github/workflows; then
  echo "A GitHub Actions workflow invokes Terraform apply, destroy, or plan." >&2
  exit 1
fi

forbidden='aws_nat_gateway|aws_eip|aws_lb|aws_alb|aws_db_instance|aws_ebs_volume|aws_route53_zone|aws_route53_record|aws_cloudwatch_log_group|aws_flow_log|aws_kms_key|aws_instance|aws_ecr_registry_scanning_configuration'
if grep -RInE "^resource \"(${forbidden})\"" infra/terraform; then
  echo "A forbidden billable resource type is defined under infra/terraform." >&2
  exit 1
fi

if ! command -v terraform >/dev/null 2>&1; then
  echo "terraform is not on PATH." >&2
  exit 1
fi

export TF_IN_AUTOMATION=1
export TF_INPUT=0
export AWS_EC2_METADATA_DISABLED=true

cd "$ROOT/infra/terraform"
terraform fmt -check -recursive
terraform init -backend=false -input=false
terraform validate

cd "$ROOT"
# The root module count is 0, so Trivy does not descend into the platform module.
# Scan that directory on its own. .terraform is a provider cache, not project code.
scan_config() {
  trivy config \
    --quiet \
    --severity HIGH,CRITICAL \
    --exit-code 1 \
    --skip-dirs "$ROOT/infra/terraform/.terraform" \
    --ignorefile "$ROOT/infra/terraform/.trivyignore" \
    "$1"
}
scan_config "$ROOT/infra/terraform"
scan_config "$ROOT/infra/terraform/modules/platform"
