locals {
  aws_region   = "us-east-1"
  environment  = "prod"
  project_name = "awos-recruitment"

  main_domain_name = "awos.provectus.pro"
  sub_domain_name  = "recruitment.awos.provectus.pro"

  acm_certificates = {
    "tls-public-sub" = {
      domain_name               = local.main_domain_name
      subject_alternative_names = ["*.${local.main_domain_name}"]
      private_zone              = false
    }
  }

  vpc_name = "${local.project_name}-vpc"
  vpc_cidr = "10.1.0.0/16"

  default_tags = {
    "Managed"     = "by-terraform"
    "Environment" = "prod"
    "Project"     = "awos-recruitment"
    "Owner"       = "Managed DevOps Team"
  }

  github_repository = "provectus/awos-recruitment"

  # Ref pattern allowed to assume the deploy role. Examples:
  #   "ref:refs/heads/main"  - only workflows running on main
  #   "ref:refs/tags/v*"     - only version tags
  #   "environment:prod"     - only workflows targeting the "prod" GitHub environment
  #   "*"                    - any workflow in the repo (least restrictive)
  # TEMPORARY: opened to all workflow contexts (2026-04-27) for OIDC trust
  # testing. Revert to "ref:refs/heads/main" once verification is complete.
  github_deploy_ref = "*"
}
