locals {
  aws_region        = "us-east-1"
  project_name      = "awos-recruitment"
  domain_name       = "recruitment.awos.provectus.pro"
  vpc_cidr          = "10.0.0.0/16"
  github_repository = "provectus/awos-recruitment"

  # Ref pattern allowed to assume the deploy role. Examples:
  #   "ref:refs/heads/main"  - only workflows running on main
  #   "ref:refs/tags/v*"     - only version tags
  #   "environment:prod"     - only workflows targeting the "prod" GitHub environment
  #   "*"                    - any workflow in the repo (least restrictive)
  github_deploy_ref = "ref:refs/heads/main"
}
