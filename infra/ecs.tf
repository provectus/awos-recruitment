# ---------------------------------------------------------------------------
# ECS Cluster, Task Definition, Service, and IAM Roles
# ---------------------------------------------------------------------------

# ---- ECS Cluster ---------------------------------------------------------

resource "aws_ecs_cluster" "main" {
  name = var.project_name

  tags = {
    Name = "${var.project_name}-cluster"
  }
}

# ---- Task Execution IAM Role --------------------------------------------

data "aws_iam_policy_document" "ecs_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ecs_execution" {
  name               = "${var.project_name}-ecs-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume_role.json

  tags = {
    Name = "${var.project_name}-ecs-execution"
  }
}

resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

data "aws_iam_policy_document" "ssm_read" {
  statement {
    actions   = ["ssm:GetParameters"]
    resources = ["arn:aws:ssm:${var.aws_region}:*:parameter/${var.project_name}/prod/*"]
  }
}

resource "aws_iam_role_policy" "ecs_execution_ssm" {
  name   = "${var.project_name}-ssm-read"
  role   = aws_iam_role.ecs_execution.id
  policy = data.aws_iam_policy_document.ssm_read.json
}

# ---- Task IAM Role -------------------------------------------------------

resource "aws_iam_role" "ecs_task" {
  name               = "${var.project_name}-ecs-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume_role.json

  tags = {
    Name = "${var.project_name}-ecs-task"
  }
}

# ---- Task Definition -----------------------------------------------------

resource "aws_ecs_task_definition" "mcp" {
  family                   = "${var.project_name}-mcp"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 1024
  memory                   = 4096
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name      = "mcp-server"
      image     = "${aws_ecr_repository.mcp.repository_url}:latest"
      essential = true

      portMappings = [
        {
          containerPort = 8000
          protocol      = "tcp"
        }
      ]

      secrets = [
        {
          name      = "AWOS_HOST"
          valueFrom = aws_ssm_parameter.host.arn
        },
        {
          name      = "AWOS_PORT"
          valueFrom = aws_ssm_parameter.port.arn
        },
        {
          name      = "AWOS_VERSION"
          valueFrom = aws_ssm_parameter.version.arn
        },
        {
          name      = "AWOS_EMBEDDING_MODEL"
          valueFrom = aws_ssm_parameter.embedding_model.arn
        },
        {
          name      = "AWOS_SEARCH_THRESHOLD"
          valueFrom = aws_ssm_parameter.search_threshold.arn
        },
        {
          name      = "AWOS_REGISTRY_PATH"
          valueFrom = aws_ssm_parameter.registry_path.arn
        },
        {
          name      = "AWOS_POSTHOG_API_KEY"
          valueFrom = aws_ssm_parameter.posthog_api_key.arn
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.mcp.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "mcp"
        }
      }
    }
  ])

  tags = {
    Name = "${var.project_name}-mcp-task"
  }
}

# ---- ECS Service ---------------------------------------------------------

resource "aws_ecs_service" "mcp" {
  name            = "${var.project_name}-mcp"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.mcp.arn
  desired_count   = 2
  launch_type     = "FARGATE"

  health_check_grace_period_seconds = 120

  network_configuration {
    subnets          = [aws_subnet.private_a.id, aws_subnet.private_b.id]
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.mcp.arn
    container_name   = "mcp-server"
    container_port   = 8000
  }

  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  depends_on = [aws_lb_listener.https]

  tags = {
    Name = "${var.project_name}-mcp-service"
  }
}
