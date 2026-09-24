---
name: terraform-conventions
description: Use when working with Terraform or OpenTofu - creating modules, writing tests (native test framework, Terratest), setting up CI/CD pipelines, reviewing configurations, choosing between testing approaches, debugging state issues, implementing security scanning (trivy, checkov), or making infrastructure-as-code architecture decisions. Enforces Provectus opinionated conventions (exact version pinning, etc.) on top of community best practices.
---

# Terraform Conventions

Terraform and OpenTofu guidance covering testing, modules, CI/CD, and production patterns. Based on terraform-best-practices.com and enterprise experience. Layered with Provectus opinionated conventions.

## Provectus Conventions

> ### Version Pinning
>
> Pin every Terraform, provider, and module version to an exact version.
>
> | Component | Constraint | Example |
> |-----------|-----------|---------|
> | **Terraform** | Exact version | `required_version = "= 1.14.8"` |
> | **Providers** | Exact version | `version = "= 6.41.0"` |
> | **Modules (prod)** | Exact version | `version = "5.1.2"` |
> | **Modules (dev)** | Exact version | `version = "5.1.2"` |
>
> No pessimistic (`~>`) or range constraints. Pin everything. This prevents drift between environments and ensures reproducible builds.

> ### Root Module Configuration
>
> **Use `locals.tf` instead of `terraform.tfvars` in root modules.** Define values directly in locals — no `.tfvars` files at the root level. This keeps all configuration in version-controlled HCL and avoids hidden variable overrides.
>
> ```hcl
> # locals.tf — root module
> locals {
>   environment = "prod"
>   project     = "my-project"
>   region      = "us-east-1"
> }
> ```

> ### Required Resource Tags
>
> Include these four tags on every taggable resource:
>
> | Tag | Description | Example |
> |-----|-------------|---------|
> | `Environment` | Deployment environment | `prod`, `staging`, `dev` |
> | `Project` | Project or service name | `my-project` |
> | `Owner` | Team or person responsible | `platform-team` |
> | `ManagedBy` | How the resource is managed | `terraform` |
>
> ```hcl
> locals {
>   required_tags = {
>     Environment = local.environment
>     Project     = local.project
>     Owner       = local.owner
>     ManagedBy   = "terraform"
>   }
> }
>
> resource "aws_s3_bucket" "this" {
>   bucket = "my-bucket"
>
>   tags = merge(local.required_tags, {
>     Name = "my-bucket"
>   })
> }
> ```

> ### Apply Workflow
>
> Use `plan -out` and get explicit approval before applying.
>
> ```bash
> terraform plan -out=plan.tfplan    # Step 1: Generate saved plan
> terraform show plan.tfplan         # Step 2: Review the plan
> # Step 3: Wait for explicit approval
> terraform apply plan.tfplan        # Step 4: Apply the saved plan
> ```
>
> Applying without a saved plan file applies whatever the config produces now, not what was reviewed.

## Core Principles

### 1. Code Structure Philosophy

**Module Hierarchy:**

| Type | When to Use | Scope |
|------|-------------|-------|
| **Resource Module** | Single logical group of connected resources | VPC + subnets, Security group + rules |
| **Infrastructure Module** | Collection of resource modules for a purpose | Multiple resource modules in one region/account |
| **Composition** | Complete infrastructure | Spans multiple regions/accounts |

**Hierarchy:** Resource → Resource Module → Infrastructure Module → Composition

**Directory Structure:**
```
environments/        # Environment-specific configurations
├── prod/
├── staging/
└── dev/

modules/            # Reusable modules
├── networking/
├── compute/
└── data/

examples/           # Module usage examples (also serve as tests)
├── complete/
└── minimal/
```

**Key principle from terraform-best-practices.com:**
- Separate **environments** (prod, staging) from **modules** (reusable components)
- Use **examples/** as both documentation and integration test fixtures
- Keep modules small and focused (single responsibility)

**For detailed module architecture, see:** [Code Patterns: Module Types & Hierarchy](references/code-patterns.md)

### 2. Naming Conventions

**Resources:**
```hcl
# Good: Descriptive, contextual
resource "aws_instance" "web_server" { }
resource "aws_s3_bucket" "application_logs" { }

# Good: "this" for singleton resources (only one of that type)
resource "aws_vpc" "this" { }
resource "aws_security_group" "this" { }

# Avoid: Generic names for non-singletons
resource "aws_instance" "main" { }
resource "aws_s3_bucket" "bucket" { }
```

**Singleton Resources:**

Use `"this"` when your module creates only one resource of that type:

DO:
```hcl
resource "aws_vpc" "this" {}           # Module creates one VPC
resource "aws_security_group" "this" {}  # Module creates one SG
```

DON'T use "this" for multiple resources:
```hcl
resource "aws_subnet" "this" {}  # If creating multiple subnets
```

Use descriptive names when creating multiple resources of the same type.

**Variables:**
```hcl
# Prefix with context when needed
var.vpc_cidr_block          # Not just "cidr"
var.database_instance_class # Not just "instance_class"
```

**Files:**
- `main.tf` - Primary resources
- `variables.tf` - Input variables
- `outputs.tf` - Output values
- `versions.tf` - Provider versions
- `data.tf` - Data sources (optional)

## Testing Strategy Framework

### Decision Matrix: Which Testing Approach?

| Your Situation | Recommended Approach | Tools | Cost |
|----------------|---------------------|-------|------|
| **Quick syntax check** | Static analysis | `terraform validate`, `fmt` | Free |
| **Pre-commit validation** | Static + lint | `validate`, `tflint`, `trivy`, `checkov` | Free |
| **Terraform 1.6+, simple logic** | Native test framework | Built-in `terraform test` | Free-Low |
| **Pre-1.6, or Go expertise** | Integration testing | Terratest | Low-Med |
| **Security/compliance focus** | Policy as code | OPA, Sentinel | Free |
| **Cost-sensitive workflow** | Mock providers (1.7+) | Native tests + mocking | Free |
| **Multi-cloud, complex** | Full integration | Terratest + real infra | Med-High |

### Testing Pyramid for Infrastructure

```
        /\
       /  \          End-to-End Tests (Expensive)
      /____\         - Full environment deployment
     /      \        - Production-like setup
    /________\
   /          \      Integration Tests (Moderate)
  /____________\     - Module testing in isolation
 /              \    - Real resources in test account
/________________\   Static Analysis (Cheap)
                     - validate, fmt, lint
                     - Security scanning
```

### Native Test Best Practices (1.6+)

**Before generating test code:**

1. **Confirm the resource schema** — which nested blocks are sets and which are
   lists. With the `terraform-mcp-server` MCP server, call
   `terraform-mcp-server:search_providers` then
   `terraform-mcp-server:get_provider_details`; without it, read the provider's
   registry docs page for the pinned version.

2. **Choose correct command mode:**
   - `command = plan` - Fast, for input validation
   - `command = apply` - Required for computed values and set-type blocks

3. **Handle set-type blocks correctly:**
   - Cannot index with `[0]`
   - Use `for` expressions to iterate
   - Or use `command = apply` to materialize

**Common patterns:**
- S3 encryption rules: **set** (use for expressions)
- Lifecycle transitions: **set** (use for expressions)
- IAM policy statements: **set** (use for expressions)

**For detailed testing guides, see:**
- **[Testing Frameworks Guide](references/testing-frameworks.md)** - Deep dive into static analysis, native tests, and Terratest
- **[Quick Reference](references/quick-reference.md#testing-approach-selection)** - Decision flowchart and command cheat sheet

## Code Structure Standards

### Resource Block Ordering

Order arguments consistently so diffs stay readable:

1. `count` or `for_each` first (blank line after)
2. Other arguments
3. `tags` as last real argument
4. `depends_on` after tags (if needed)
5. `lifecycle` at the very end (if needed)

```hcl
# GOOD - Correct ordering
resource "aws_nat_gateway" "this" {
  count = var.create_nat_gateway ? 1 : 0

  allocation_id = aws_eip.this[0].id
  subnet_id     = aws_subnet.public[0].id

  tags = merge(local.required_tags, {
    Name = "${var.name}-nat"
  })

  depends_on = [aws_internet_gateway.this]

  lifecycle {
    create_before_destroy = true
  }
}
```

### Variable Block Ordering

1. `description` (always required)
2. `type`
3. `default`
4. `sensitive` (when setting to true)
5. `nullable` (when setting to false)
6. `validation`

```hcl
variable "environment" {
  description = "Environment name for resource tagging"
  type        = string
  default     = "dev"
  nullable    = false

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod."
  }
}
```

**For complete structure guidelines, see:** [Code Patterns: Block Ordering & Structure](references/code-patterns.md#block-ordering--structure)

## Count vs For_Each: When to Use Each

### Quick Decision Guide

| Scenario | Use | Why |
|----------|-----|-----|
| Boolean condition (create or don't) | `count = condition ? 1 : 0` | Simple on/off toggle |
| Simple numeric replication | `count = 3` | Fixed number of identical resources |
| Items may be reordered/removed | `for_each = toset(list)` | Stable resource addresses |
| Reference by key | `for_each = map` | Named access to resources |
| Multiple named resources | `for_each` | Better maintainability |

### Common Patterns

**Boolean conditions:**
```hcl
# GOOD - Boolean condition
resource "aws_nat_gateway" "this" {
  count = var.create_nat_gateway ? 1 : 0
  # ...
}
```

**Stable addressing with for_each:**
```hcl
# GOOD - Removing "us-east-1b" only affects that subnet
resource "aws_subnet" "private" {
  for_each = toset(var.availability_zones)

  availability_zone = each.key
  # ...
}

# BAD - Removing middle AZ recreates all subsequent subnets
resource "aws_subnet" "private" {
  count = length(var.availability_zones)

  availability_zone = var.availability_zones[count.index]
  # ...
}
```

**For migration guides and detailed examples, see:** [Code Patterns: Count vs For_Each](references/code-patterns.md#count-vs-for_each-deep-dive)

## Locals for Dependency Management

Where destroy order matters — VPCs with secondary CIDR blocks are the usual
case — route the reference through a `local` built with `try()` instead of
pointing at the resource directly. That creates the implicit dependency which
makes Terraform delete subnets before the CIDR association.

**For the worked example, see:** [Code Patterns: Locals for Dependency Management](references/code-patterns.md#locals-for-dependency-management)

## Module Development

### Standard Module Structure

```
my-module/
├── README.md           # Usage documentation
├── main.tf             # Primary resources
├── variables.tf        # Input variables with descriptions
├── outputs.tf          # Output values
├── versions.tf         # Provider version constraints
├── examples/
│   ├── minimal/        # Minimal working example
│   └── complete/       # Full-featured example
└── tests/              # Test files
    └── module_test.tftest.hcl  # Or .go
```

### Best Practices Summary

**Variables:**
- Always include `description`
- Use explicit `type` constraints
- Provide sensible `default` values where appropriate
- Add `validation` blocks for complex constraints
- Use `sensitive = true` for secrets

**Outputs:**
- Always include `description`
- Mark sensitive outputs with `sensitive = true`
- Consider returning objects for related values
- Document what consumers should do with each output

**For detailed module patterns, see:**
- **[Module Patterns Guide](references/module-patterns.md)** - Variable best practices, output design, DO vs DON'T patterns
- **[Quick Reference](references/quick-reference.md#common-patterns)** - Resource naming, variable naming, file organization

## CI/CD Integration

### Recommended Workflow Stages

1. **Validate** - Format check + syntax validation + linting
2. **Test** - Run automated tests (native or Terratest)
3. **Plan** - Generate and review execution plan
4. **Apply** - Execute changes (with approvals for production)

### Cost Optimization Strategy

1. **Use mocking for PR validation** (free)
2. **Run integration tests only on main branch** (controlled cost)
3. **Implement auto-cleanup** (prevent orphaned resources)
4. **Tag all test resources** (track spending)

**For complete CI/CD templates, see:**
- **[CI/CD Workflows Guide](references/ci-cd-workflows.md)** - GitHub Actions, GitLab CI, Atlantis integration, cost optimization
- **[Quick Reference](references/quick-reference.md#troubleshooting-guide)** - Common CI/CD issues and solutions

## Security & Compliance

### Essential Security Checks

```bash
# Static security scanning
trivy config .
checkov -d .
```

### Common Issues to Avoid

**Don't:**
- Store secrets in variables
- Use default VPC
- Skip encryption
- Open security groups to 0.0.0.0/0

**Do:**
- Use AWS Secrets Manager / Parameter Store
- Create dedicated VPCs
- Enable encryption at rest
- Use least-privilege security groups

**For detailed security guidance, see:**
- **[Security & Compliance Guide](references/security-compliance.md)** - Trivy/Checkov integration, secrets management, state file security, compliance testing

## Version Management

> **Provectus Convention: All versions must be pinned to exact versions. No pessimistic (`~>`) or range constraints.**

### Version Constraint Syntax

```hcl
version = "= 6.41.0"    # Exact (required by Provectus convention)
version = "5.1.2"        # Exact (alternative syntax for modules)
```

### Strategy by Component

| Component | Strategy | Example |
|-----------|----------|---------|
| **Terraform** | Pin exact version | `required_version = "= 1.14.8"` |
| **Providers** | Pin exact version | `version = "= 6.41.0"` |
| **Modules (prod)** | Pin exact version | `version = "5.1.2"` |
| **Modules (dev)** | Pin exact version | `version = "5.1.2"` |

### Update Workflow

```bash
# Step 1: Lock versions initially
terraform init              # Creates .terraform.lock.hcl — commit this file

# Step 2: To update, change the exact version in versions.tf first,
#         then re-resolve the lock file
terraform init -upgrade

# Step 3: Review and test
terraform plan
```

**For detailed version management, see:** [Code Patterns: Version Management](references/code-patterns.md#version-management)

## Modern Terraform Features (1.0+)

### Feature Availability by Version

| Feature | Version | Use Case |
|---------|---------|----------|
| `try()` function | 0.13+ | Safe fallbacks, replaces `element(concat())` |
| `nullable = false` | 1.1+ | Prevent null values in variables |
| `moved` blocks | 1.1+ | Refactor without destroy/recreate |
| `optional()` with defaults | 1.3+ | Optional object attributes |
| Native testing | 1.6+ | Built-in test framework |
| Mock providers | 1.7+ | Cost-free unit testing |
| Provider functions | 1.8+ | Provider-specific data transformation |
| Cross-variable validation | 1.9+ | Validate relationships between variables |
| Write-only arguments | 1.11+ | Secrets never stored in state |

Check the pinned `required_version` before using a feature from this table — a
pin below the listed version rejects it at parse time.

**For worked examples of each, see:** [Code Patterns: Modern Terraform Features](references/code-patterns.md#modern-terraform-features-10)

## Version-Specific Guidance

Which testing approach each version supports, and the Terraform/OpenTofu
comparison (licensing, governance, feature parity), are in
[Quick Reference: Version-Specific Guidance](references/quick-reference.md#version-specific-guidance).

## References

- [`references/code-patterns.md`](references/code-patterns.md) — block ordering, count vs for_each, modern features, version management, refactoring
- [`references/module-patterns.md`](references/module-patterns.md) — module hierarchy, structure, variables, outputs, anti-patterns
- [`references/testing-frameworks.md`](references/testing-frameworks.md) — static analysis, native tests, Terratest
- [`references/ci-cd-workflows.md`](references/ci-cd-workflows.md) — GitHub Actions, GitLab CI, Atlantis, cost control
- [`references/security-compliance.md`](references/security-compliance.md) — trivy/checkov, secrets management, state security
- [`references/quick-reference.md`](references/quick-reference.md) — command cheat sheets, pre-commit checklist, troubleshooting

## License

This skill is based on [terraform-skill](https://github.com/antonbabenko/terraform-skill) by Anton Babenko, licensed under the **Apache License 2.0**.
