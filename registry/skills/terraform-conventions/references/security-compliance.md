# Security & Compliance

> **Part of:** [terraform-skill](../SKILL.md)
> **Purpose:** Security best practices and compliance patterns for Terraform/OpenTofu

This document provides security hardening guidance and compliance automation strategies for infrastructure-as-code.

---

## Table of Contents

1. [Security Scanning Tools](#security-scanning-tools)
2. [Common Security Issues](#common-security-issues)
3. [Compliance Testing](#compliance-testing)
4. [Secrets Management](#secrets-management)
5. [State File Security](#state-file-security)

---

## Security Scanning Tools

### Essential Security Checks

```bash
# Static security scanning
trivy config .
checkov -d .

# Compliance testing
terraform-compliance -f compliance/ -p tfplan.json
```

### Trivy Integration

**Install:**

```bash
# macOS
brew install trivy

# Linux
curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin

# In CI
- uses: aquasecurity/trivy-action@master
  with:
    scan-type: 'config'
    scan-ref: '.'
```

**Note:** Trivy is the successor to tfsec, maintained by Aqua Security.

**Example Output:**

```
Result #1 HIGH Security group rule allows egress to multiple public internet addresses
────────────────────────────────────────────────────────────────────────────────
  security.tf:15-20

   12 | resource "aws_security_group_rule" "egress" {
   13 |   type              = "egress"
   14 |   from_port         = 0
   15 |   to_port           = 0
   16 |   protocol          = "-1"
   17 |   cidr_blocks       = ["0.0.0.0/0"]
   18 |   security_group_id = aws_security_group.this.id
   19 | }
```

### Checkov Integration

```bash
# Run Checkov
checkov -d . --framework terraform

# Skip specific checks
checkov -d . --skip-check CKV_AWS_23

# Generate JSON report
checkov -d . -o json > checkov-report.json
```

---

## Common Security Issues

### ❌ DON'T: Store Secrets in Variables

```hcl
# BAD: Secret in plaintext
variable "database_password" {
  type    = string
  default = "SuperSecret123!"  # ❌ Never do this
}
```

### ✅ DO: Read a Pre-existing Secret Into a Write-only Argument

```hcl
# Good: Reference a secret created outside Terraform, pass it write-only
data "aws_secretsmanager_secret" "db_password" {
  name = "prod/database/password"
}

data "aws_secretsmanager_secret_version" "db_password" {
  secret_id = data.aws_secretsmanager_secret.db_password.id
}

resource "aws_db_instance" "this" {
  engine         = "mysql"
  instance_class = "db.t3.micro"
  username       = "admin"

  # password_wo is sent to AWS and never written to state.
  # password_wo_version is required whenever password_wo is set - bump it to
  # make Terraform push a rotated secret.
  password_wo         = data.aws_secretsmanager_secret_version.db_password.secret_string
  password_wo_version = 1
}
```

Plain `password = ...` is what puts the secret in state, so it stays a DON'T
even when the value comes from Secrets Manager. See
[Secrets Management](#secrets-management) for the version requirements and the
fallback for older pins.

### ❌ DON'T: Use Default VPC

```hcl
# BAD: Default VPC has public subnets
resource "aws_instance" "app" {
  ami           = "ami-12345"
  subnet_id     = "subnet-default"  # ❌ Avoid default resources
}
```

### ✅ DO: Create Dedicated VPCs

```hcl
# Good: Custom VPC with private subnets
resource "aws_vpc" "this" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
}

resource "aws_subnet" "private" {
  vpc_id            = aws_vpc.this.id
  cidr_block        = "10.0.1.0/24"
  availability_zone = "us-east-1a"
}
```

### ❌ DON'T: Skip Encryption

```hcl
# BAD: Unencrypted S3 bucket
resource "aws_s3_bucket" "data" {
  bucket = "my-data-bucket"
  # ❌ No encryption configured
}
```

### ✅ DO: Enable Encryption at Rest

```hcl
# Good: Enable encryption
resource "aws_s3_bucket" "data" {
  bucket = "my-data-bucket"
}

resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  bucket = aws_s3_bucket.data.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}
```

### ❌ DON'T: Open Security Groups to Internet

```hcl
# BAD: Security group open to internet
resource "aws_security_group_rule" "allow_all" {
  type              = "ingress"
  from_port         = 0
  to_port           = 65535
  protocol          = "tcp"
  cidr_blocks       = ["0.0.0.0/0"]  # ❌ Never do this
  security_group_id = aws_security_group.this.id
}
```

### ✅ DO: Use Least-Privilege Security Groups

```hcl
# Good: Restrict to specific ports and sources
resource "aws_security_group_rule" "app_https" {
  type              = "ingress"
  from_port         = 443
  to_port           = 443
  protocol          = "tcp"
  cidr_blocks       = ["10.0.0.0/16"]  # ✅ Internal only
  security_group_id = aws_security_group.this.id
}
```

---

## Compliance Testing

### terraform-compliance

**Install:**

```bash
pip install terraform-compliance
```

**Example Compliance Test:**

```gherkin
# compliance/aws-encryption.feature
Feature: AWS Resources must be encrypted

  Scenario: S3 buckets must have encryption
    Given I have aws_s3_bucket defined
    When it has aws_s3_bucket_server_side_encryption_configuration
    Then it must contain rule
    And it must contain apply_server_side_encryption_by_default

  Scenario: RDS instances must be encrypted
    Given I have aws_db_instance defined
    Then it must contain storage_encrypted
    And its value must be true
```

**Run Tests:**

```bash
# Generate plan in JSON
terraform plan -out=tfplan
terraform show -json tfplan > tfplan.json

# Run compliance tests
terraform-compliance -f compliance/ -p tfplan.json
```

### Open Policy Agent (OPA)

```rego
# policy/s3_encryption.rego
package terraform.s3

deny[msg] {
  resource := input.resource_changes[_]
  resource.type == "aws_s3_bucket"
  not resource.change.after.server_side_encryption_configuration

  msg := sprintf("S3 bucket '%s' must have encryption enabled", [resource.address])
}
```

---

## Secrets Management

The rule behind every pattern here: a secret Terraform can read is a secret
Terraform writes to state, and state is readable by anyone with the backend
bucket. So the secret value should never pass through a regular argument.

### Default: Pre-existing Secret + Write-only Argument

Create the secret outside Terraform (console, CLI, or a separate
bootstrap process), then read it and pass it as a write-only argument:

```hcl
data "aws_secretsmanager_secret" "db_password" {
  name = "prod/database/password"
}

data "aws_secretsmanager_secret_version" "db_password" {
  secret_id = data.aws_secretsmanager_secret.db_password.id
}

resource "aws_db_instance" "this" {
  engine         = "mysql"
  instance_class = "db.t3.micro"
  username       = "admin"

  password_wo         = data.aws_secretsmanager_secret_version.db_password.secret_string
  password_wo_version = 1
}
```

**Requirements:** write-only arguments need Terraform 1.11+, and each resource
needs a provider version that implements them — `aws_db_instance.password_wo`
landed in AWS provider 5.88.0. Check the pins in `versions.tf` before
generating this pattern; under older pins Terraform rejects the argument with
"An argument named `password_wo` is not expected here."
`password_wo_version` is required whenever `password_wo` is set; increment it
to push a rotated value.

**Escape hatch for older pins:** let RDS own the password instead of
Terraform — the value is generated by AWS, stored in Secrets Manager, and
never reaches state:

```hcl
resource "aws_db_instance" "this" {
  engine         = "mysql"
  instance_class = "db.t3.micro"
  username       = "admin"

  manage_master_user_password = true  # Cannot be combined with password/password_wo
}
```

### Legacy Pattern: `random_password` Into Secrets Manager

```hcl
# LEGACY - both the generated value and the secret version land in state
resource "random_password" "db_password" {
  length  = 32
  special = true
}

resource "aws_secretsmanager_secret_version" "db_password" {
  secret_id     = aws_secretsmanager_secret.db_password.id
  secret_string = random_password.db_password.result
}
```

You will meet this in existing codebases. It is not the pattern to generate:
`random_password.result` and `secret_string` are both stored in plaintext in
the state file, so the Secrets Manager entry adds a second copy rather than
protecting the first. For moving an existing configuration off it, see
Secrets Remediation in `references/code-patterns.md`.

### Environment Variables

```bash
# Never commit these
export TF_VAR_database_password="secret123"
export AWS_ACCESS_KEY_ID="AKIAIOSFODNN7EXAMPLE"
export AWS_SECRET_ACCESS_KEY="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
```

**In .gitignore:**

```
*.tfvars
.env
secrets/
```

---

## State File Security

### Encrypt State at Rest

```hcl
# backend.tf
terraform {
  backend "s3" {
    bucket         = "my-terraform-state"
    key            = "prod/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "terraform-locks"
    encrypt        = true  # ✅ Always enable encryption
  }
}
```

### Secure State Bucket

```hcl
resource "aws_s3_bucket" "terraform_state" {
  bucket = "my-terraform-state"
}

# Enable versioning (protect against accidental deletion)
resource "aws_s3_bucket_versioning" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  versioning_configuration {
    status = "Enabled"
  }
}

# Enable encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Block public access
resource "aws_s3_bucket_public_access_block" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
```

### Restrict State Access

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::123456789012:role/TerraformRole"
      },
      "Action": [
        "s3:ListBucket",
        "s3:GetObject",
        "s3:PutObject"
      ],
      "Resource": [
        "arn:aws:s3:::my-terraform-state",
        "arn:aws:s3:::my-terraform-state/*"
      ]
    }
  ]
}
```

---

## IAM Best Practices

### ✅ DO: Use Least Privilege

```hcl
# Good: Specific permissions only
resource "aws_iam_policy" "app_policy" {
  name = "app-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject"
        ]
        Resource = "arn:aws:s3:::my-app-bucket/*"
      }
    ]
  })
}
```

### ❌ DON'T: Use Wildcard Permissions

```hcl
# BAD: Overly broad permissions
resource "aws_iam_policy" "bad_policy" {
  policy = jsonencode({
    Statement = [
      {
        Effect   = "Allow"
        Action   = "*"  # ❌ Never use wildcard
        Resource = "*"
      }
    ]
  })
}
```

---

## Compliance Checklists

### SOC 2 Compliance

- [ ] Encryption at rest for all data stores
- [ ] Encryption in transit (TLS/SSL)
- [ ] IAM policies follow least privilege
- [ ] Logging enabled for all resources
- [ ] MFA required for privileged access
- [ ] Regular security scanning in CI/CD

### HIPAA Compliance

- [ ] PHI encrypted at rest and in transit
- [ ] Access logs enabled
- [ ] Dedicated VPC with private subnets
- [ ] Regular backup and retention policies
- [ ] Audit trail for all infrastructure changes

### PCI-DSS Compliance

- [ ] Network segmentation (separate VPCs)
- [ ] No default passwords
- [ ] Strong encryption algorithms
- [ ] Regular security scanning
- [ ] Access control and monitoring

---

## Resources

- [Trivy Documentation](https://aquasecurity.github.io/trivy/)
- [Checkov Documentation](https://www.checkov.io/)
- [terraform-compliance](https://terraform-compliance.com/)
- [Open Policy Agent](https://www.openpolicyagent.org/)
- [AWS Security Best Practices](https://aws.amazon.com/security/best-practices/)

---

**Back to:** [Main Skill File](../SKILL.md)
