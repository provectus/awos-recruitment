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

No modules.

## Resources

| Name | Type |
|------|------|
| [aws_acm_certificate.main](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/acm_certificate) | resource |
| [aws_acm_certificate_validation.main](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/acm_certificate_validation) | resource |
| [aws_cloudwatch_log_group.mcp](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/cloudwatch_log_group) | resource |
| [aws_ecr_lifecycle_policy.mcp](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/ecr_lifecycle_policy) | resource |
| [aws_ecr_repository.mcp](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/ecr_repository) | resource |
| [aws_ecs_cluster.main](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/ecs_cluster) | resource |
| [aws_ecs_service.mcp](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/ecs_service) | resource |
| [aws_ecs_task_definition.mcp](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/ecs_task_definition) | resource |
| [aws_eip.nat](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/eip) | resource |
| [aws_iam_role.ecs_execution](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/iam_role) | resource |
| [aws_iam_role.ecs_task](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/iam_role) | resource |
| [aws_iam_role_policy.ecs_execution_ssm](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/iam_role_policy) | resource |
| [aws_iam_role_policy_attachment.ecs_execution](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/iam_role_policy_attachment) | resource |
| [aws_internet_gateway.main](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/internet_gateway) | resource |
| [aws_lb.main](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/lb) | resource |
| [aws_lb_listener.http](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/lb_listener) | resource |
| [aws_lb_listener.https](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/lb_listener) | resource |
| [aws_lb_target_group.mcp](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/lb_target_group) | resource |
| [aws_nat_gateway.main](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/nat_gateway) | resource |
| [aws_route53_record.cert_validation](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/route53_record) | resource |
| [aws_route_table.private](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/route_table) | resource |
| [aws_route_table.public](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/route_table) | resource |
| [aws_route_table_association.private_a](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/route_table_association) | resource |
| [aws_route_table_association.private_b](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/route_table_association) | resource |
| [aws_route_table_association.public_a](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/route_table_association) | resource |
| [aws_route_table_association.public_b](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/route_table_association) | resource |
| [aws_security_group.alb](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/security_group) | resource |
| [aws_security_group.ecs](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/security_group) | resource |
| [aws_ssm_parameter.embedding_model](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/ssm_parameter) | resource |
| [aws_ssm_parameter.host](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/ssm_parameter) | resource |
| [aws_ssm_parameter.port](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/ssm_parameter) | resource |
| [aws_ssm_parameter.posthog_api_key](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/ssm_parameter) | resource |
| [aws_ssm_parameter.registry_path](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/ssm_parameter) | resource |
| [aws_ssm_parameter.search_threshold](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/ssm_parameter) | resource |
| [aws_ssm_parameter.version](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/ssm_parameter) | resource |
| [aws_subnet.private_a](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/subnet) | resource |
| [aws_subnet.private_b](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/subnet) | resource |
| [aws_subnet.public_a](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/subnet) | resource |
| [aws_subnet.public_b](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/subnet) | resource |
| [aws_vpc.main](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/vpc) | resource |
| [aws_vpc_security_group_egress_rule.alb_to_ecs](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/vpc_security_group_egress_rule) | resource |
| [aws_vpc_security_group_egress_rule.ecs_https_out](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/vpc_security_group_egress_rule) | resource |
| [aws_vpc_security_group_ingress_rule.alb_http](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/vpc_security_group_ingress_rule) | resource |
| [aws_vpc_security_group_ingress_rule.alb_https](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/vpc_security_group_ingress_rule) | resource |
| [aws_vpc_security_group_ingress_rule.ecs_from_alb](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/vpc_security_group_ingress_rule) | resource |
| [aws_availability_zones.available](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/data-sources/availability_zones) | data source |
| [aws_iam_policy_document.ecs_assume_role](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/data-sources/iam_policy_document) | data source |
| [aws_iam_policy_document.ssm_read](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/data-sources/iam_policy_document) | data source |
| [aws_route53_zone.this](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/data-sources/route53_zone) | data source |

## Inputs

No inputs.

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_alb_dns_name"></a> [alb\_dns\_name](#output\_alb\_dns\_name) | DNS name of the Application Load Balancer |
| <a name="output_ecr_repository_url"></a> [ecr\_repository\_url](#output\_ecr\_repository\_url) | URL of the ECR repository for the MCP server image |
| <a name="output_ecs_cluster_name"></a> [ecs\_cluster\_name](#output\_ecs\_cluster\_name) | Name of the ECS cluster |
| <a name="output_ecs_service_name"></a> [ecs\_service\_name](#output\_ecs\_service\_name) | Name of the ECS service |
<!-- END_TF_DOCS -->
