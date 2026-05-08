# infra

<!-- BEGIN_TF_DOCS -->
## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) | = 1.14.8 |
| <a name="requirement_aws"></a> [aws](#requirement\_aws) | = 6.41.0 |

## Providers

| Name | Version |
|------|---------|
| <a name="provider_aws"></a> [aws](#provider\_aws) | 6.41.0 |

## Modules

| Name | Source | Version |
|------|--------|---------|
| <a name="module_acm_certificates"></a> [acm\_certificates](#module\_acm\_certificates) | ../modules/acm_certificate | n/a |
| <a name="module_alb_sg"></a> [alb\_sg](#module\_alb\_sg) | ../modules/security_groups | n/a |
| <a name="module_ecs"></a> [ecs](#module\_ecs) | ../modules/ecs | n/a |
| <a name="module_ecs_execution_role"></a> [ecs\_execution\_role](#module\_ecs\_execution\_role) | ../modules/iam_role | n/a |
| <a name="module_ecs_sg"></a> [ecs\_sg](#module\_ecs\_sg) | ../modules/security_groups | n/a |
| <a name="module_ecs_task_role"></a> [ecs\_task\_role](#module\_ecs\_task\_role) | ../modules/iam_role | n/a |
| <a name="module_network"></a> [network](#module\_network) | ../modules/vpc | n/a |

## Resources

| Name | Type |
|------|------|
| [aws_ecr_lifecycle_policy.mcp](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/ecr_lifecycle_policy) | resource |
| [aws_ecr_repository.mcp](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/ecr_repository) | resource |
| [aws_iam_role.github_deploy](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/iam_role) | resource |
| [aws_iam_role_policy.github_deploy](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/iam_role_policy) | resource |
| [aws_lb.main](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/lb) | resource |
| [aws_lb_listener.http](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/lb_listener) | resource |
| [aws_lb_listener.https](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/lb_listener) | resource |
| [aws_lb_target_group.mcp](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/lb_target_group) | resource |
| [aws_route53_record.app](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/route53_record) | resource |
| [aws_route53_zone.subdomain](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/route53_zone) | resource |
| [aws_ssm_parameter.embedding_model](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/ssm_parameter) | resource |
| [aws_ssm_parameter.host](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/ssm_parameter) | resource |
| [aws_ssm_parameter.port](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/ssm_parameter) | resource |
| [aws_ssm_parameter.posthog_api_key](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/ssm_parameter) | resource |
| [aws_ssm_parameter.registry_path](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/ssm_parameter) | resource |
| [aws_ssm_parameter.search_threshold](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/ssm_parameter) | resource |
| [aws_ssm_parameter.version](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/ssm_parameter) | resource |
| [aws_caller_identity.current](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/data-sources/caller_identity) | data source |
| [aws_iam_openid_connect_provider.github](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/data-sources/iam_openid_connect_provider) | data source |
| [aws_iam_policy_document.ecs_assume_role](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/data-sources/iam_policy_document) | data source |
| [aws_iam_policy_document.github_deploy](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/data-sources/iam_policy_document) | data source |
| [aws_iam_policy_document.github_deploy_assume](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/data-sources/iam_policy_document) | data source |
| [aws_iam_policy_document.ssm_read](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/data-sources/iam_policy_document) | data source |
| [aws_partition.current](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/data-sources/partition) | data source |

## Inputs

No inputs.

## Outputs

No outputs.
<!-- END_TF_DOCS -->
