module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "6.0.0"

  name = var.vpc_name

  cidr = var.vpc_cidr
  azs  = slice(data.aws_availability_zones.available.names, 0, 3)

  public_subnets = [
    cidrsubnet(var.vpc_cidr, 8, 1),
    cidrsubnet(var.vpc_cidr, 8, 2),
    cidrsubnet(var.vpc_cidr, 8, 3)
  ]
  public_subnet_tags = {
    Role = "public"
  }

  private_subnets = [
    cidrsubnet(var.vpc_cidr, local.private_subnet_newbits, 11),
    cidrsubnet(var.vpc_cidr, local.private_subnet_newbits, 12),
    cidrsubnet(var.vpc_cidr, local.private_subnet_newbits, 13)
  ]
  private_subnet_tags = {
    Role = "private"
  }

  intra_subnets = var.create_intra_subnets == false ? [] : [
    cidrsubnet(var.vpc_cidr, 8, 15),
    cidrsubnet(var.vpc_cidr, 8, 16),
    cidrsubnet(var.vpc_cidr, 8, 17)
  ]

  database_subnets = var.create_database_subnets == false ? [] : [
    cidrsubnet(var.vpc_cidr, 8, 21),
    cidrsubnet(var.vpc_cidr, 8, 22),
    cidrsubnet(var.vpc_cidr, 8, 23)
  ]

  enable_nat_gateway = var.enable_nat_gateway
  single_nat_gateway = true

  enable_dns_hostnames = true
  enable_dns_support   = true

  create_database_subnet_group  = false
  manage_default_security_group = false

  tags = var.tags

}

resource "aws_security_group" "this" {
  name        = "${var.project_name}-general"
  description = "Security groups for aws services"
  vpc_id      = module.vpc.vpc_id

  dynamic "ingress" {
    for_each = var.ports
    content {
      from_port   = ingress.value
      to_port     = ingress.value
      protocol    = "tcp"
      cidr_blocks = ["0.0.0.0/0"] # Open to all IPs; adjust as needed
    }
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1" # All protocols
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = var.tags
}
