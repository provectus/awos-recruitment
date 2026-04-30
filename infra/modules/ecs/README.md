# ecs

<!-- BEGIN_TF_DOCS -->
## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) | = 1.14.8 |
| <a name="requirement_aws"></a> [aws](#requirement\_aws) | = 6.41.0 |

## Providers

| Name | Version |
|------|---------|
| <a name="provider_aws"></a> [aws](#provider\_aws) | = 6.41.0 |

## Modules

| Name | Source | Version |
|------|--------|---------|
| <a name="module_ecs"></a> [ecs](#module\_ecs) | terraform-aws-modules/ecs/aws | 6.0.0 |

## Resources

| Name | Type |
|------|------|
| [aws_cloudwatch_log_group.task_definition](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/cloudwatch_log_group) | resource |
| [aws_ecs_service.this](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/ecs_service) | resource |
| [aws_ecs_task_definition.this](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/ecs_task_definition) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_aws_region"></a> [aws\_region](#input\_aws\_region) | AWS region for ECS deployment | `string` | n/a | yes |
| <a name="input_container_name"></a> [container\_name](#input\_container\_name) | Name of the container in the ECS task definition | `string` | n/a | yes |
| <a name="input_deployment_maximum_percent"></a> [deployment\_maximum\_percent](#input\_deployment\_maximum\_percent) | Upper limit (% of desired\_count) of running tasks during a deployment | `number` | `200` | no |
| <a name="input_deployment_minimum_healthy_percent"></a> [deployment\_minimum\_healthy\_percent](#input\_deployment\_minimum\_healthy\_percent) | Lower limit (% of desired\_count) of running tasks during a deployment | `number` | `100` | no |
| <a name="input_desired_count"></a> [desired\_count](#input\_desired\_count) | Desired number of ECS task instances | `number` | `1` | no |
| <a name="input_docker_image_task_definition"></a> [docker\_image\_task\_definition](#input\_docker\_image\_task\_definition) | Docker image for the ECS task definition | `string` | n/a | yes |
| <a name="input_ecs_cluster_enabled"></a> [ecs\_cluster\_enabled](#input\_ecs\_cluster\_enabled) | Enable creation of the ECS cluster | `bool` | `true` | no |
| <a name="input_ecs_cluster_name"></a> [ecs\_cluster\_name](#input\_ecs\_cluster\_name) | Name of the ECS cluster | `string` | n/a | yes |
| <a name="input_ecs_security_group_id"></a> [ecs\_security\_group\_id](#input\_ecs\_security\_group\_id) | List of security group IDs for ECS tasks | `list(string)` | `[]` | no |
| <a name="input_ecs_service_enabled"></a> [ecs\_service\_enabled](#input\_ecs\_service\_enabled) | Enable the ECS service for the task | `bool` | `false` | no |
| <a name="input_ecs_task_container_port"></a> [ecs\_task\_container\_port](#input\_ecs\_task\_container\_port) | Container port exposed by the ECS task | `number` | `80` | no |
| <a name="input_ecs_task_cpu_limit"></a> [ecs\_task\_cpu\_limit](#input\_ecs\_task\_cpu\_limit) | Maximum CPU units allocated for the ECS task | `number` | `512` | no |
| <a name="input_ecs_task_env_variables"></a> [ecs\_task\_env\_variables](#input\_ecs\_task\_env\_variables) | A list of environment variables to pass to the ECS task | `list(any)` | `[]` | no |
| <a name="input_ecs_task_host_port"></a> [ecs\_task\_host\_port](#input\_ecs\_task\_host\_port) | Host port mapped to the container port | `number` | `80` | no |
| <a name="input_ecs_task_memory_limit"></a> [ecs\_task\_memory\_limit](#input\_ecs\_task\_memory\_limit) | Maximum memory (in MiB) allocated for the ECS task | `number` | `1024` | no |
| <a name="input_enable_deployment_circuit_breaker"></a> [enable\_deployment\_circuit\_breaker](#input\_enable\_deployment\_circuit\_breaker) | Enable ECS deployment circuit breaker with rollback | `bool` | `false` | no |
| <a name="input_execution_role_arn"></a> [execution\_role\_arn](#input\_execution\_role\_arn) | ARN of the ECS task execution IAM role | `string` | n/a | yes |
| <a name="input_health_check_grace_period_seconds"></a> [health\_check\_grace\_period\_seconds](#input\_health\_check\_grace\_period\_seconds) | Seconds to ignore failing load balancer health checks on newly launched tasks | `number` | `0` | no |
| <a name="input_private_subnets"></a> [private\_subnets](#input\_private\_subnets) | List of private subnet IDs for ECS tasks | `list(string)` | `[]` | no |
| <a name="input_secrets"></a> [secrets](#input\_secrets) | List of container secrets pulled from SSM Parameter Store or Secrets Manager | <pre>list(object({<br/>    name      = string<br/>    valueFrom = string<br/>  }))</pre> | `[]` | no |
| <a name="input_service_name"></a> [service\_name](#input\_service\_name) | Override for the ECS service name. Defaults to <cluster>-service if null. | `string` | `null` | no |
| <a name="input_tags"></a> [tags](#input\_tags) | A map of key-value pairs to assign metadata to resources | `map(string)` | n/a | yes |
| <a name="input_target_group_arn"></a> [target\_group\_arn](#input\_target\_group\_arn) | ALB target group ARN to attach the ECS service to. If null, no load balancer is configured. | `string` | `null` | no |
| <a name="input_task_command"></a> [task\_command](#input\_task\_command) | Command to run the application in the container | `list(string)` | `null` | no |
| <a name="input_task_family"></a> [task\_family](#input\_task\_family) | Override for the ECS task definition family. Defaults to <cluster>-tasks if null. | `string` | `null` | no |
| <a name="input_task_role_arn"></a> [task\_role\_arn](#input\_task\_role\_arn) | ARN of the IAM role for ECS task permissions | `string` | n/a | yes |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_ecs_cluster_arn"></a> [ecs\_cluster\_arn](#output\_ecs\_cluster\_arn) | n/a |
| <a name="output_ecs_cluster_name"></a> [ecs\_cluster\_name](#output\_ecs\_cluster\_name) | The name of the ECS cluster. |
| <a name="output_ecs_container_name"></a> [ecs\_container\_name](#output\_ecs\_container\_name) | n/a |
| <a name="output_ecs_task_log_group_name"></a> [ecs\_task\_log\_group\_name](#output\_ecs\_task\_log\_group\_name) | n/a |
| <a name="output_service_name"></a> [service\_name](#output\_service\_name) | n/a |
| <a name="output_task_definition_arn"></a> [task\_definition\_arn](#output\_task\_definition\_arn) | n/a |
| <a name="output_task_definition_revision"></a> [task\_definition\_revision](#output\_task\_definition\_revision) | n/a |
<!-- END_TF_DOCS -->
