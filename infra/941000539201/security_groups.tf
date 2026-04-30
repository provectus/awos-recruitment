# ---------------------------------------------------------------------------
# Security Groups: ALB and ECS
# ---------------------------------------------------------------------------

# ---- ALB Security Group ---------------------------------------------------

resource "aws_security_group" "alb" {
  name        = "${local.project_name}-alb-sg"
  description = "Allow HTTP/HTTPS inbound traffic to the ALB"
  vpc_id      = aws_vpc.main.id

  tags = {
    Name = "${local.project_name}-alb-sg"
  }
}

resource "aws_vpc_security_group_ingress_rule" "alb_https" {
  security_group_id = aws_security_group.alb.id
  description       = "HTTPS from anywhere"
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_ingress_rule" "alb_http" {
  security_group_id = aws_security_group.alb.id
  description       = "HTTP from anywhere (redirects to HTTPS)"
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 80
  to_port           = 80
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "alb_to_ecs" {
  security_group_id            = aws_security_group.alb.id
  description                  = "Allow traffic to ECS tasks on port 8000"
  referenced_security_group_id = aws_security_group.ecs.id
  from_port                    = 8000
  to_port                      = 8000
  ip_protocol                  = "tcp"
}

# ---- ECS Security Group ---------------------------------------------------

resource "aws_security_group" "ecs" {
  name        = "${local.project_name}-ecs-sg"
  description = "Allow inbound from ALB and outbound HTTPS for ECR/SSM"
  vpc_id      = aws_vpc.main.id

  tags = {
    Name = "${local.project_name}-ecs-sg"
  }
}

resource "aws_vpc_security_group_ingress_rule" "ecs_from_alb" {
  security_group_id            = aws_security_group.ecs.id
  description                  = "Allow traffic from ALB on port 8000"
  referenced_security_group_id = aws_security_group.alb.id
  from_port                    = 8000
  to_port                      = 8000
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "ecs_https_out" {
  security_group_id = aws_security_group.ecs.id
  description       = "Allow outbound HTTPS for ECR pulls and SSM"
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
}
