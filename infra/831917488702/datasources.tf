data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

data "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"
}

# data "aws_route53_zone" "this" {
#   name = "awos.provectus.pro"
# }
