# ---------------------------------------------------------------------------
# CloudWatch Log Group for ECS tasks
# ---------------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "mcp" {
  name              = "/ecs/${local.project_name}-mcp"
  retention_in_days = 30

  tags = {
    Name = "${local.project_name}-mcp-logs"
  }
}
