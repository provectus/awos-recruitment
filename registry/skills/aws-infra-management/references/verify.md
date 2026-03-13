# AWS Infrastructure Verification

Health checks, drift detection, and security validation for AWS resources.

## Workflow

1. **Discovery:** `Glob: **/*.tf`, `**/*.tfstate`
2. **Health Checks:** `aws` CLI to verify resource status
3. **Drift Detection:** `ExecuteTerraformCommand` (plan) — detect configuration drift
4. **Security Scan:** `RunCheckovScan` — AWS security and compliance checks

## Profile Output

**Enthusiast:** Simple status - "Everything is running" or "Found 1 issue: [description]"

**DevOps:** Full report with:
- Resource health table with AWS resource IDs
- Drift details and remediation steps
- Checkov results with check IDs (CKV_AWS_*)
- CIS AWS Benchmark compliance %
- State health and lock status (S3 + DynamoDB)

## Severity Actions

| Severity | Enthusiast            | DevOps SLA |
|----------|-----------------------|------------|
| CRITICAL | "Needs immediate fix" | Fix now    |
| HIGH     | "Should fix soon"     | 24 hours   |
| MEDIUM   | Hidden                | 1 week     |
| LOW      | Hidden                | 1 month    |
