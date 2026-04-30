# ---------------------------------------------------------------------------
# GitHub Actions OIDC provider + deploy role
#
# Lets workflows in the configured GitHub repo assume an AWS role via OIDC
# (no long-lived access keys). The role is scoped to pushing images to ECR
# and rolling the MCP ECS service.
# ---------------------------------------------------------------------------


# ---- OIDC provider -------------------------------------------------------
#
# Account-scoped: if another project in this AWS account already created
# this provider, import it instead of applying:
#   terraform import aws_iam_openid_connect_provider.github \
#     arn:aws:iam::<account-id>:oidc-provider/token.actions.githubusercontent.com
#
# thumbprint_list is intentionally omitted: AWS validates the GitHub JWKS
# endpoint against its own trusted CA library and ignores configured
# thumbprints for well-known IdPs (GitHub, GitLab, Google, Auth0).

# resource "aws_iam_openid_connect_provider" "github" {
#   url            = "https://token.actions.githubusercontent.com"
#   client_id_list = ["sts.amazonaws.com"]

#   tags = local.default_tags
# }

# ---- Deploy role ---------------------------------------------------------

data "aws_iam_policy_document" "github_deploy_assume" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [data.aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${local.github_repository}:${local.github_deploy_ref}"]
    }
  }
}

resource "aws_iam_role" "github_deploy" {
  name               = "${local.project_name}-github-deploy"
  assume_role_policy = data.aws_iam_policy_document.github_deploy_assume.json

  tags = local.default_tags
}

# ---- Deploy permissions --------------------------------------------------

data "aws_iam_policy_document" "github_deploy" {
  # ECR auth token endpoint does not support resource-level permissions.
  statement {
    sid       = "EcrAuth"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  # Push/pull scoped to the MCP repository only.
  statement {
    sid = "EcrPushPull"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
      "ecr:InitiateLayerUpload",
      "ecr:UploadLayerPart",
      "ecr:CompleteLayerUpload",
      "ecr:PutImage",
    ]
    resources = [aws_ecr_repository.mcp.arn]
  }

  # RegisterTaskDefinition / DescribeTaskDefinition do not support
  # resource-level permissions.
  statement {
    sid = "EcsTaskDefinition"
    actions = [
      "ecs:RegisterTaskDefinition",
      "ecs:DescribeTaskDefinition",
    ]
    resources = ["*"]
  }

  # Scoped to the MCP service on our cluster only.
  statement {
    sid = "EcsService"
    actions = [
      "ecs:UpdateService",
      "ecs:DescribeServices",
    ]
    resources = [
      "arn:${data.aws_partition.current.partition}:ecs:${local.aws_region}:${data.aws_caller_identity.current.account_id}:service/${module.ecs.ecs_cluster_name}/${module.ecs.service_name}",
    ]
  }

  # Required when registering a new task definition revision that
  # references these roles.
  statement {
    sid     = "PassTaskRoles"
    actions = ["iam:PassRole"]
    resources = [
      module.ecs_task_role.role_arn,
      module.ecs_execution_role.role_arn
    ]
    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy" "github_deploy" {
  name   = "${local.project_name}-github-deploy"
  role   = aws_iam_role.github_deploy.id
  policy = data.aws_iam_policy_document.github_deploy.json
}
