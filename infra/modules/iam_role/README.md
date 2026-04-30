# iam_role

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

No modules.

## Resources

| Name | Type |
|------|------|
| [aws_iam_role.this](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/iam_role) | resource |
| [aws_iam_role_policy.inline](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/iam_role_policy) | resource |
| [aws_iam_role_policy_attachment.managed](https://registry.terraform.io/providers/hashicorp/aws/6.41.0/docs/resources/iam_role_policy_attachment) | resource |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_assume_role_policy"></a> [assume\_role\_policy](#input\_assume\_role\_policy) | Trust policy JSON document granting the role to be assumed | `string` | n/a | yes |
| <a name="input_inline_policies"></a> [inline\_policies](#input\_inline\_policies) | Map of inline policy name to policy JSON document | `map(string)` | `{}` | no |
| <a name="input_managed_policy_arns"></a> [managed\_policy\_arns](#input\_managed\_policy\_arns) | List of AWS- or customer-managed policy ARNs to attach to the role | `list(string)` | `[]` | no |
| <a name="input_name"></a> [name](#input\_name) | The name of the IAM role | `string` | n/a | yes |
| <a name="input_tags"></a> [tags](#input\_tags) | Map of tags to apply to the role | `map(string)` | `{}` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_role_arn"></a> [role\_arn](#output\_role\_arn) | ARN of the IAM role |
| <a name="output_role_id"></a> [role\_id](#output\_role\_id) | ID of the IAM role |
| <a name="output_role_name"></a> [role\_name](#output\_role\_name) | Name of the IAM role |
<!-- END_TF_DOCS -->
