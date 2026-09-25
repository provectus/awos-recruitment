# Version Management

> **Part of:** [terraform-skill](../SKILL.md)
> **Purpose:** Version pinning, modern Terraform features, and version-specific guidance

## Contents

- Version Pinning: constraint syntax, strategy by component, update workflow
- Modern Terraform Features (1.0+): feature availability by version, quick examples
- Version-Specific Guidance: Terraform 1.0-1.5, 1.6+, 1.7+

---

## Version Pinning

> **Provectus Convention: All versions must be pinned to exact versions. No pessimistic (`~>`) or range constraints.**

### Version Constraint Syntax

```hcl
version = "= 5.82.2"    # Exact (required by Provectus convention)
version = "5.1.2"        # Exact (alternative syntax for modules)
```

### Strategy by Component

| Component | Strategy | Example |
|-----------|----------|---------|
| **Terraform** | Pin exact version | `required_version = "= 1.9.8"` |
| **Providers** | Pin exact version | `version = "= 5.82.2"` |
| **Modules (prod)** | Pin exact version | `version = "5.1.2"` |
| **Modules (dev)** | Pin exact version | `version = "5.1.2"` |

### Update Workflow

```bash
# Lock versions initially
terraform init              # Creates .terraform.lock.hcl

# Update to latest within constraints
terraform init -upgrade     # Updates providers

# Review and test
terraform plan
```


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

### Quick Examples

```hcl
# try() - Safe fallbacks (0.13+)
output "sg_id" {
  value = try(aws_security_group.this[0].id, "")
}

# optional() - Optional attributes with defaults (1.3+)
variable "config" {
  type = object({
    name    = string
    timeout = optional(number, 300)  # Default: 300
  })
}

# Cross-variable validation (1.9+)
variable "environment" { type = string }
variable "backup_days" {
  type = number
  validation {
    condition     = var.environment == "prod" ? var.backup_days >= 7 : true
    error_message = "Production requires backup_days >= 7"
  }
}
```


## Version-Specific Guidance

### Terraform 1.0-1.5
- Use Terratest for testing
- No native testing framework available
- Focus on static analysis and plan validation

### Terraform 1.6+ / OpenTofu 1.6+
- **New:** Native `terraform test` / `tofu test` command
- Consider migrating from external frameworks for simple tests
- Keep Terratest only for complex integration tests

### Terraform 1.7+ / OpenTofu 1.7+
- **New:** Mock providers for unit testing
- Reduce cost by mocking external dependencies
- Use real integration tests for final validation

### Terraform vs OpenTofu

