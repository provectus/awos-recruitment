# data "aws_caller_identity" "current" {}
# data "aws_partition" "current" {}

data "aws_route53_zone" "this" {
  name = "awos.provectus.pro"
}
