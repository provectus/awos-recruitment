locals {
  aws_region = "us-east-1"

  default_tags = {
    "Managed"     = "by-terraform"
    "Environment" = "prod"
    "Project"     = "awos-recruitment"
    "Owner"       = "Managed DevOps Team"
  }

  state_bucket = "awos-recruitment-tf-states"
}
