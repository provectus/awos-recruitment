# ---------------------------------------------------------------------------
# SSM Parameter Store: Configuration for the MCP server
# ---------------------------------------------------------------------------

resource "aws_ssm_parameter" "host" {
  name  = "/${local.project_name}/prod/host"
  type  = "String"
  value = "0.0.0.0"

  tags = {
    Name = "${local.project_name}-ssm-host"
  }
}

resource "aws_ssm_parameter" "port" {
  name  = "/${local.project_name}/prod/port"
  type  = "String"
  value = "8000"

  tags = {
    Name = "${local.project_name}-ssm-port"
  }
}

resource "aws_ssm_parameter" "version" {
  name  = "/${local.project_name}/prod/version"
  type  = "String"
  value = "0.1.0"

  tags = {
    Name = "${local.project_name}-ssm-version"
  }
}

resource "aws_ssm_parameter" "embedding_model" {
  name  = "/${local.project_name}/prod/embedding-model"
  type  = "String"
  value = "all-MiniLM-L6-v2"

  tags = {
    Name = "${local.project_name}-ssm-embedding-model"
  }
}

resource "aws_ssm_parameter" "search_threshold" {
  name  = "/${local.project_name}/prod/search-threshold"
  type  = "String"
  value = "20"

  tags = {
    Name = "${local.project_name}-ssm-search-threshold"
  }
}

resource "aws_ssm_parameter" "registry_path" {
  name  = "/${local.project_name}/prod/registry-path"
  type  = "String"
  value = "/app/registry"

  tags = {
    Name = "${local.project_name}-ssm-registry-path"
  }
}

resource "aws_ssm_parameter" "posthog_api_key" {
  name  = "/${local.project_name}/prod/posthog-api-key"
  type  = "SecureString"
  value = "placeholder"

  tags = {
    Name = "${local.project_name}-ssm-posthog-api-key"
  }

  lifecycle {
    ignore_changes = [value]
  }
}
