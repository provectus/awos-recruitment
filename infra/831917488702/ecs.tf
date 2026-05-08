# ---------------------------------------------------------------------------
# ECS: cluster, task definition, service, and IAM roles
# ---------------------------------------------------------------------------

# ---- IAM policy documents -----------------------------------------------

data "aws_iam_policy_document" "ecs_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "ssm_read" {
  statement {
    actions   = ["ssm:GetParameters"]
    resources = ["arn:aws:ssm:${local.aws_region}:*:parameter/${local.project_name}/prod/*"]
  }

  statement {
    actions   = ["kms:Decrypt"]
    resources = ["*"]
  }
}

# ---- IAM Roles -----------------------------------------------------------

module "ecs_execution_role" {
  source = "../modules/iam_role"

  name               = "${local.project_name}-ecs-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume_role.json

  managed_policy_arns = [
    "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy",
  ]

  inline_policies = {
    "${local.project_name}-ssm-read" = data.aws_iam_policy_document.ssm_read.json
  }

  tags = local.default_tags
}

module "ecs_task_role" {
  source = "../modules/iam_role"

  name               = "${local.project_name}-ecs-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume_role.json

  tags = local.default_tags
}

# ---- ECS cluster + task definition + service ----------------------------

module "ecs" {
  source = "../modules/ecs"

  ecs_cluster_name = local.project_name
  aws_region       = local.aws_region
  private_subnets  = module.network.private_subnets

  task_family    = "${local.project_name}-mcp"
  service_name   = "${local.project_name}-mcp"
  container_name = "mcp-server"

  docker_image_task_definition = "${aws_ecr_repository.mcp.repository_url}:latest"
  ecs_task_cpu_limit           = 1024
  ecs_task_memory_limit        = 4096
  ecs_task_container_port      = 8000
  ecs_task_host_port           = 8000

  execution_role_arn = module.ecs_execution_role.role_arn
  task_role_arn      = module.ecs_task_role.role_arn

  ecs_security_group_id = [module.ecs_sg.security_group_id]

  secrets = [
    { name = "AWOS_HOST", valueFrom = aws_ssm_parameter.host.arn },
    { name = "AWOS_PORT", valueFrom = aws_ssm_parameter.port.arn },
    { name = "AWOS_VERSION", valueFrom = aws_ssm_parameter.version.arn },
    { name = "AWOS_EMBEDDING_MODEL", valueFrom = aws_ssm_parameter.embedding_model.arn },
    { name = "AWOS_SEARCH_THRESHOLD", valueFrom = aws_ssm_parameter.search_threshold.arn },
    { name = "AWOS_REGISTRY_PATH", valueFrom = aws_ssm_parameter.registry_path.arn },
    { name = "AWOS_POSTHOG_API_KEY", valueFrom = aws_ssm_parameter.posthog_api_key.arn },
  ]

  target_group_arn                   = aws_lb_target_group.mcp.arn
  health_check_grace_period_seconds  = 120
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200
  enable_deployment_circuit_breaker  = true

  ecs_service_enabled = true
  desired_count       = 2

  tags = local.default_tags

  depends_on = [aws_lb_listener.http]
}
