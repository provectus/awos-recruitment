# Security Best Practices

## IAM Least Privilege

### Execution role design

Every Lambda function has an **execution role** -- the IAM role it assumes when running. This role determines what AWS services and resources the function can access.

### Principles

| Principle | Implementation |
|---|---|
| Specific actions | `dynamodb:GetItem`, `dynamodb:PutItem` -- not `dynamodb:*` |
| Specific resources | `arn:aws:dynamodb:us-east-1:123456789:table/MyTable` -- not `*` |
| One role per function | Functions with different responsibilities get different roles |
| Condition keys | Use `aws:RequestedRegion`, `aws:SourceArn` to narrow further |
| Regular audits | Use IAM Access Analyzer to find unused permissions |

### Resource-based policies

Control who can **invoke** your function (separate from what the function can do):

- Allow specific AWS services (API Gateway, S3, SNS) to invoke the function
- Restrict invocation to specific accounts or source ARNs
- Deny cross-account invocation unless explicitly required

### Common anti-patterns

| Anti-pattern | Risk | Fix |
|---|---|---|
| `"Action": "*"` on execution role | Full AWS access if function is compromised | List specific actions |
| `"Resource": "*"` | Access to all resources of that type | Specify resource ARNs |
| Shared execution role across many functions | Blast radius of compromised function expands | Separate roles per function |
| Managed policies like `AmazonS3FullAccess` | Grants access to all buckets in the account | Custom policy with specific bucket ARN |
| Never rotating credentials | Long-lived credentials are a risk | Lambda execution role credentials are short-lived by default -- don't override this |

## Code Signing

Code signing ensures that only trusted code runs in your Lambda function.

### How it works

1. You configure a **signing profile** in AWS Signer
2. You sign your deployment package with the profile
3. You attach a **code signing configuration** to your Lambda function
4. Lambda verifies the signature on every deploy and rejects unsigned or tampered code

### When to use

| Scenario | Code signing? |
|---|---|
| Production functions handling sensitive data | Yes |
| Functions in regulated industries (finance, healthcare) | Yes |
| Internal dev/test functions | Optional |
| Functions deployed via trusted CI/CD only | Recommended as defense in depth |

### Configuration options

| Setting | Options |
|---|---|
| `UntrustedArtifactOnDeployment` | `Warn` (log but deploy) or `Enforce` (reject) |
| Signing profile platform | `AWSLambda-SHA384-ECDSA` |
| Signature validity | Configurable expiry period |

## VPC Configuration

### When to place Lambda in a VPC

| Need | VPC required? |
|---|---|
| Access private RDS/ElastiCache/Redshift | Yes |
| Access resources in a private subnet | Yes |
| Call public AWS APIs (DynamoDB, S3, SQS) | No -- use VPC endpoints or stay outside VPC |
| Internet access from Lambda | NAT Gateway required if in VPC |
| Compliance requirement for network isolation | Yes |

### VPC trade-offs

| Benefit | Cost |
|---|---|
| Network isolation for private resources | Additional cold start latency (ENI attachment) |
| Security group and NACL controls | Requires VPC endpoint or NAT for public services |
| Private connectivity to on-premises | ENI quota consumption |
| Compliance with network segmentation policies | More complex networking configuration |

### VPC best practices

- Place Lambda in **private subnets** -- never public subnets (Lambda doesn't use public IPs even in public subnets)
- Use **VPC endpoints** for AWS services (S3, DynamoDB, SQS, etc.) to avoid NAT Gateway costs and latency
- Use **at least 2 subnets** across different AZs for availability
- Size subnets for ENI consumption: each concurrent execution may use an ENI (Lambda optimizes sharing)
- Monitor ENI quota -- shared with other services in the same VPC

## Secrets Management

### Where to store secrets

| Method | Security | Rotation | Cost |
|---|---|---|---|
| Hardcoded in code | Terrible -- exposed in source control | Manual | Free |
| Environment variables (plaintext) | Low -- visible in Lambda console | Manual redeploy | Free |
| Environment variables (encrypted with CMK) | Medium -- encrypted at rest | Manual redeploy | KMS charges |
| Secrets Manager | High -- encrypted, audited, versioned | Automatic rotation supported | Per-secret charge |
| Parameter Store (SecureString) | High -- encrypted with KMS | Manual or custom rotation | Free (standard) / small charge (advanced) |

### Recommended pattern

1. Store secrets in **Secrets Manager** or **Parameter Store SecureString**
2. Reference the secret ARN in a Lambda environment variable
3. Retrieve and cache the secret at module level (execution environment reuse)
4. Grant the execution role `secretsmanager:GetSecretValue` on the specific secret ARN
5. Enable automatic rotation for database credentials

### Lambda environment variable encryption

- All environment variables are encrypted at rest by default using an AWS-managed KMS key
- For sensitive values, use a **customer-managed CMK** for additional control and audit trail
- Enable **encryption helpers** in the console to encrypt values in transit with a different key

## Security Monitoring

### AWS Security Hub

Security Hub evaluates Lambda configurations against security controls:

| Control | What it checks |
|---|---|
| Lambda functions should use supported runtimes | Flags end-of-life runtimes |
| Lambda functions should have a dead-letter queue configured | Ensures failed events aren't silently lost |
| Lambda functions should restrict public access | Flags functions with overly permissive resource policies |
| Lambda function policies should prohibit public access | Checks for `"Principal": "*"` in resource policies |

### Amazon GuardDuty Lambda Protection

GuardDuty monitors network activity when Lambda functions are invoked:

- Detects communication with known malicious IPs
- Identifies cryptocurrency mining activity
- Flags DNS queries to malicious domains
- Monitors for credential exfiltration attempts

### CloudTrail

All Lambda API calls are logged in CloudTrail:

- `CreateFunction`, `UpdateFunctionCode`, `UpdateFunctionConfiguration`
- `Invoke` (data events -- must be explicitly enabled)
- `AddPermission`, `RemovePermission` (resource policy changes)

Enable CloudTrail data events for Lambda to audit who invoked which functions.

## Data Protection

### Encryption

| Data state | Protection |
|---|---|
| In transit | All Lambda APIs require TLS 1.2+ |
| At rest (code) | Encrypted in S3 with service-managed keys |
| At rest (environment variables) | Encrypted with KMS (AWS-managed or customer-managed key) |
| In transit (environment variables) | Decrypted only in the execution environment |
| `/tmp` storage | Ephemeral, isolated per execution environment, destroyed on environment shutdown |

### Network security

| Control | Purpose |
|---|---|
| Security groups | Control inbound/outbound traffic for VPC-attached functions |
| NACLs | Subnet-level network filtering |
| VPC endpoints | Private connectivity to AWS services without internet |
| PrivateLink | Private connectivity to third-party services |

## Governance

### Governance strategies for Lambda

| Strategy | Implementation |
|---|---|
| Approved runtimes | Use AWS Config rules to flag functions with unsupported runtimes |
| Maximum timeout limits | Organization SCPs or Config rules to enforce timeout caps |
| Required tags | SCPs requiring cost-center, team, environment tags |
| Code signing enforcement | Organization-wide code signing configurations |
| VPC requirement | SCPs requiring VPC configuration for functions accessing sensitive data |
| Layer governance | Approve and publish shared layers centrally; restrict layer sources |

### Service Control Policies (SCPs)

Use SCPs to enforce organization-wide Lambda policies:

- Prevent creation of functions without VPC configuration
- Restrict allowed runtimes
- Require encryption with customer-managed keys
- Prevent public resource policies
