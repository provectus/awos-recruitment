#==========================================================
#  ECS
#==========================================================

module "ecs" {
  source  = "terraform-aws-modules/ecs/aws"
  version = "6.0.0"

  count = var.ecs_cluster_enabled ? 1 : 0

  cluster_name = var.ecs_cluster_name

  cluster_configuration = {
    execute_command_configuration = {
      logging = "OVERRIDE"
      log_configuration = {
        cloud_watch_log_group_name             = "/aws/ecs/${var.ecs_cluster_name}"
        cloudwatch_log_group_retention_in_days = 7
      }
    }
  }

  # Cluster capacity providers
  default_capacity_provider_strategy = {
    FARGATE = {
      weight = 50
      base   = 20
    }
  }

  # Capacity provider
  # fargate_capacity_providers = {
  #   FARGATE = {
  #     default_capacity_provider_strategy = {
  #       weight = 50
  #       base   = 20
  #     }
  #   }
  # }
}

resource "aws_cloudwatch_log_group" "task_definition" {
  name              = "/aws/ecs/task/${var.ecs_cluster_name}"
  retention_in_days = 30

  tags = var.tags
}

resource "aws_ecs_task_definition" "this" {
  container_definitions = jsonencode([{
    essential = true,
    image     = var.docker_image_task_definition,
    name      = var.container_name,
    command   = var.task_command,

    environment = var.ecs_task_env_variables
    secrets     = var.secrets

    portMappings = [
      {
        containerPort = var.ecs_task_container_port
        hostPort      = var.ecs_task_host_port
        protocol      = "tcp"
      }
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.task_definition.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "ecs"
      }
    }

  }])
  cpu                      = var.ecs_task_cpu_limit
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.task_role_arn
  family                   = local.task_family
  memory                   = var.ecs_task_memory_limit
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]

  tags = var.tags
}

resource "aws_ecs_service" "this" {
  count = var.ecs_service_enabled ? 1 : 0

  cluster         = module.ecs[0].cluster_id
  desired_count   = var.desired_count
  launch_type     = "FARGATE"
  name            = local.service_name
  task_definition = aws_ecs_task_definition.this.arn_without_revision

  health_check_grace_period_seconds  = var.target_group_arn != null ? var.health_check_grace_period_seconds : null
  deployment_minimum_healthy_percent = var.deployment_minimum_healthy_percent
  deployment_maximum_percent         = var.deployment_maximum_percent

  network_configuration {
    security_groups  = var.ecs_security_group_id
    subnets          = var.private_subnets
    assign_public_ip = false
  }

  dynamic "load_balancer" {
    for_each = var.target_group_arn != null ? [1] : []
    content {
      target_group_arn = var.target_group_arn
      container_name   = var.container_name
      container_port   = var.ecs_task_container_port
    }
  }

  dynamic "deployment_circuit_breaker" {
    for_each = var.enable_deployment_circuit_breaker ? [1] : []
    content {
      enable   = true
      rollback = true
    }
  }

  tags = var.tags

  lifecycle {
    ignore_changes = [desired_count, task_definition] # CI registers new task-def revisions; auto-scaling owns desired_count.
  }
}
