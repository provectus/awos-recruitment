module "network" {
  source             = "../modules/vpc"
  project_name       = local.project_name
  env                = local.environment
  vpc_name           = local.vpc_name
  vpc_cidr           = local.vpc_cidr
  enable_nat_gateway = true
  tags               = local.default_tags
  ports              = [443]
}

module "alb_sg" {
  source = "../modules/security_groups"

  name        = "${local.project_name}-alb-sg"
  description = "Allow HTTP/HTTPS inbound traffic to the ALB"
  vpc_id      = module.network.vpc_id

  ingress_rules = [
    { from_port = 80, to_port = 80, protocol = "tcp", cidr_blocks = ["0.0.0.0/0"] },
    { from_port = 443, to_port = 443, protocol = "tcp", cidr_blocks = ["0.0.0.0/0"] },
  ]

  egress_rules = [
    { from_port = 8000, to_port = 8000, protocol = "tcp", cidr_blocks = [local.vpc_cidr] },
  ]

  tags = local.default_tags
}

module "ecs_sg" {
  source = "../modules/security_groups"

  name        = "${local.project_name}-ecs-sg"
  description = "Allow inbound from ALB and outbound HTTPS for ECR/SSM"
  vpc_id      = module.network.vpc_id

  ingress_rules = [
    { from_port = 8000, to_port = 8000, protocol = "tcp", security_groups = [module.alb_sg.security_group_id] },
  ]

  egress_rules = [
    { from_port = 443, to_port = 443, protocol = "tcp", cidr_blocks = ["0.0.0.0/0"] },
  ]

  tags = local.default_tags
}
