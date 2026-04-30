# ---------------------------------------------------------------------------
# Application Load Balancer, Target Group, and HTTP Listener
# HTTPS listener intentionally omitted until ACM certificate is in place.
# ---------------------------------------------------------------------------

# ---- ALB -----------------------------------------------------------------

resource "aws_lb" "main" {
  name               = "${local.project_name}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [module.alb_sg.security_group_id]
  subnets            = module.network.public_subnets

  tags = local.default_tags
}

# ---- Target Group --------------------------------------------------------

resource "aws_lb_target_group" "mcp" {
  name                 = "${local.project_name}-tg"
  port                 = 8000
  protocol             = "HTTP"
  target_type          = "ip"
  vpc_id               = module.network.vpc_id
  deregistration_delay = 30

  health_check {
    path                = "/health"
    interval            = 30
    timeout             = 10
    healthy_threshold   = 2
    unhealthy_threshold = 3
    matcher             = "200"
  }

  tags = local.default_tags
}

# ---- HTTP Listener (redirect to HTTPS) -----------------------------------

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"

    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

# ---- HTTPS Listener ------------------------------------------------------

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = module.acm_certificates["tls-public-sub"].certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.mcp.arn
  }
}
