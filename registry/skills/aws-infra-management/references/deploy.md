# AWS Infrastructure Deployment

## Profile Check
Skip if profile was already selected in this conversation. Otherwise, use `AskUserQuestion` to ask:
```
Before we start, are you:
1. Enthusiast - Keep it simple, I just want things running
2. DevOps - Show me the full picture (state, modules, pipelines)
```

## Workflow

1. **Requirements:** Identify AWS resources, lookup docs via `SearchAwsProviderDocs` or `SearchAwsccProviderDocs`, use `AskUserQuestion` for clarifying questions (region, instance type, etc.)
2. **Generate Config:** See structure below
3. **Security Scan:** `RunCheckovScan` (Enthusiast: only CRITICAL/HIGH; DevOps: full report)
4. **Cost Estimate:** (Enthusiast: "~$10/month"; DevOps: detailed breakdown + optimization tips)
5. **Deploy:** `ExecuteTerraformCommand` — init -> plan -> `AskUserQuestion` for approval -> apply
6. **Verify:** `aws` CLI checks, show summary

## Config Structure

| Profile    | Structure                                                           |
|------------|---------------------------------------------------------------------|
| Enthusiast | Single `main.tf`, local state, minimal variables                    |
| DevOps     | `environments/`, `modules/`, remote state (S3+DynamoDB), workspaces |

## DevOps Standards
- Remote state with locking (S3 + DynamoDB)
- Tagging: `Environment`, `ManagedBy`, `Project`, `CostCenter`
- Encryption + logging by default
- Least-privilege IAM per environment

## Enthusiast Quick-Starts
- Static Website: S3 + CloudFront (~$1/month)
- Web Server: Single EC2 (~$10/month)
- WordPress: EC2 + RDS (~$30/month)

## Safety Checklist
- [ ] Show plan before apply
- [ ] Get explicit confirmation
- [ ] Run `RunCheckovScan` security scan
- [ ] Show cost estimate
- [ ] Verify with `aws` CLI after deploy
