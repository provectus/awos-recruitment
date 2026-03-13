# AWS Infrastructure Explanation

Generate architecture documentation for deployed AWS infrastructure.

## Workflow

1. **Discovery:** `Glob: **/*.tf`, `**/*.tfstate`
2. **Analysis:** Parse state, map dependencies, lookup docs via `SearchAwsProviderDocs` or `get_provider_details`
3. **Verify:** `aws` CLI checks
4. **Generate:** Profile-appropriate explanation

## Profile Output

### Enthusiast
- Simple diagram: `[Internet] --> [CloudFront] --> [S3 Bucket]`
- Plain English descriptions ("S3 = cloud storage", "EC2 = virtual server")
- Cost in relatable terms ("~$35/month, like a streaming subscription")
- Hide technical IDs and ARNs

### DevOps
- Environment, AWS region, state backend location (S3 + DynamoDB)
- Resource inventory table with IDs and file:line references
- ASCII network topology with CIDR blocks and VPC layout
- Security config: Security Groups, IAM roles, encryption status, KMS keys
- State & modules: versions, workspace
- Actionable recommendations
