---
name: aws-infra-management
description: "Manage AWS infrastructure with Terraform/Terragrunt via MCP tools. Auto-activates when user mentions deploying resources, infrastructure costs, destroying environments, Terraform files, AWS services, or infrastructure health checks. Provides profile-aware interactions (Enthusiast vs DevOps). AWS-focused with S3, EC2, RDS, Lambda, VPC, IAM, and other AWS services."
---

# AWS Infrastructure Management Skill

## Activation Triggers

Activate when user mentions: deploy, create, provision, destroy, delete, clean up, verify, health check, status, explain infrastructure, cost estimate, pricing, budget, Terraform, Terragrunt, `.tf` files, or AWS services (EC2, S3, RDS, Lambda, VPC, IAM, CloudFront, ECS, EKS, etc.).

## Profile Detection (Ask Once)

On first infrastructure operation, ask the user's experience level and remember it for the session. **If a profile has already been selected in this conversation, skip this step — never ask again.**

Use `AskUserQuestion` to choose one of these options
```
Before we start, are you:
1. Enthusiast - Keep it simple, I just want things running
2. DevOps - Show me the full picture (state, modules, pipelines)
```

| Profile    | Style                                                                                                                                                                                                  |
|------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Enthusiast | Simple language, explain AWS names (e.g., "S3 = cloud storage", "EC2 = virtual server"), single-file configs, hide complexity, focus on "it works", relatable costs ("about $5/month - like a coffee") |
| DevOps     | Full HCL with modules, remote state configuration, CI/CD integration notes, drift detection, security scanning details, cost optimization recommendations, production hardening                        |

## Operations

| Operation | File                                | Triggers                          |
|-----------|-------------------------------------|-----------------------------------|
| Deploy    | [deploy.md](references/deploy.md)   | deploy, create, provision, set up |
| Destroy   | [destroy.md](references/destroy.md) | destroy, delete, remove, clean up |
| Verify    | [verify.md](references/verify.md)   | verify, check, health, validate   |
| Status    | [status.md](references/status.md)   | status, what's running, list      |
| Explain   | [explain.md](references/explain.md) | explain, describe, how does       |
| Cost      | [cost.md](references/cost.md)       | cost, estimate, pricing, budget   |

## Core Tools

| Tool              | Purpose                                                                |
|-------------------|------------------------------------------------------------------------|
| `AskUserQuestion` | Ask the user for input — profile selection, confirmations, choices, missing parameters |

## MCP Tools

Two MCP servers provide Terraform tooling. Use MCP tools instead of direct CLI calls wherever possible.

### `aws-tf` (AWS Labs Terraform MCP Server) — Primary execution server

| Tool                         | Purpose                                                        |
|------------------------------|----------------------------------------------------------------|
| `ExecuteTerraformCommand`    | Run terraform init/validate/plan/apply/destroy                 |
| `ExecuteTerragruntCommand`   | Run terragrunt init/validate/plan/apply/destroy/output/run-all |
| `RunCheckovScan`             | Security and compliance scanning                               |
| `SearchUserProvidedModule`   | Analyze Terraform Registry modules by URL/identifier           |
| `SearchAwsProviderDocs`      | Look up AWS provider resource documentation                    |
| `SearchAwsccProviderDocs`    | Look up AWSCC provider resource documentation                  |
| `SearchSpecificAwsIaModules` | Search AWS-IA GenAI modules (Bedrock, SageMaker, etc.)         |

### `mcp_tf` (HashiCorp Terraform MCP Server) — Registry & workspace management

| Tool                        | Purpose                                      |
|-----------------------------|----------------------------------------------|
| `search_modules`            | Search Terraform Registry modules            |
| `get_module_details`        | Get module details (inputs, outputs, README) |
| `search_providers`          | Search Terraform Registry providers          |
| `get_provider_details`      | Get provider resource/data-source details    |
| `get_provider_capabilities` | Get provider capabilities and schema         |
| `search_policies`           | Search Terraform Registry policies           |

### AWS CLI (verification only)

Use `aws` CLI **only for post-operation verification** when MCP tools don't cover it (e.g., checking resource status, confirming deletions).

## Environment

- AWS credentials configured (AWS_PROFILE, AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY, or IAM role)
- MCP servers `mcp_tf` and `aws-tf` must be enabled
- Docker required for `mcp_tf` (HashiCorp server)
- `uvx` required for `aws-tf` (AWS Labs server)

## Critical Safety Rules

1. **Never delete local files before cloud resources are destroyed**
2. **Always verify with AWS CLI** after Terraform operations
3. **Get explicit confirmation** for destructive operations
4. **Run security scans** before applying infrastructure
5. **Show cost estimates** before deployment approval

## Profile-Specific Behaviors

### Enthusiast Profile
- Generate simple, single-file Terraform configs
- Use local state (no remote backend complexity)
- Provide one-click deployment commands
- Explain costs in everyday terms
- Hide security scan details unless critical
- Suggest starter resources: single EC2 instance, S3 bucket, static website with CloudFront

### DevOps Profile
- Generate modular, production-ready configs
- Configure remote state with locking (S3 + DynamoDB)
- Include workspace management for multi-env
- Show full Checkov scan results
- Recommend CI/CD pipeline integration (GitHub Actions, GitLab CI)
- Discuss state locking, drift detection, blast radius
- Suggest tagging strategies and cost allocation

## Question Framework

See [questions.md](references/questions.md) for clarifying questions and confirmation patterns.
