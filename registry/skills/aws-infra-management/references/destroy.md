# AWS Infrastructure Destruction

## Critical Rule
```
DESTRUCTION ORDER (NEVER VIOLATE)
1. Destroy cloud resources with ExecuteTerraformCommand (destroy)
2. Verify resources deleted with aws CLI
3. Only then delete local files
```

**Enthusiast:** Delete cloud stuff first, then local files - otherwise you lose track and keep paying.
**DevOps:** State integrity is critical. Backup state before destruction.

## Workflow

1. **Discovery:** `Glob: **/*.tf`, `**/*.tfstate`
2. **Show Plan:** `ExecuteTerraformCommand` (plan -destroy) — resources to delete, data loss warnings, cost savings
3. **Get Confirmation:** Use `AskUserQuestion` — require explicit "yes"
4. **Execute:** `ExecuteTerraformCommand` (destroy)
5. **Verify:** `aws` CLI checks (wait for long-running deletions: NAT 5-10min, RDS 5-15min)
6. **Cleanup:** Delete `.terraform/`, `*.tfstate`, use `AskUserQuestion` to confirm deletion of `*.tf` files

## Profile Differences

| Aspect       | Enthusiast                       | DevOps                                      |
|--------------|----------------------------------|---------------------------------------------|
| Plan view    | "1 web server, 1 storage bucket" | Full resource IDs, state location           |
| Warnings     | "Files will be deleted forever"  | Data loss risk level, dependent resources   |
| Confirmation | Simple yes/no                    | Environment, resource count, estimated time |

## Safety Checklist

**Both:** Confirm environment, verify deletion via `aws` CLI, cleanup only after verification

**DevOps only:** Check production tags, backup state, notify team, check CI/CD won't recreate
