# AWS Infrastructure Status

Quick, lightweight overview (< 5 seconds).

## Workflow

1. **Discovery:** `Glob: **/*.tfstate`, `**/*.tf`
2. **Parse State:** Resource counts, identifiers, last modified
3. **Quick Check:** Optional `aws` CLI verification
4. **Output:** Profile-appropriate summary

## Profile Output

### Enthusiast
```
Everything is running!
- 1 web server (online)
- 1 storage bucket
Monthly cost: ~$35
```

### DevOps
```
State: s3://company-tfstate/prod/terraform.tfstate
Last Modified: 2024-01-15 14:32 UTC

| Type | Count | Status |
|------|-------|--------|
| aws_instance | 2 | running |
| aws_s3_bucket | 1 | available |

Drift Status: Unknown (run verify)
```

## No Infrastructure Found

- **Enthusiast:** Offer simple AWS deployment options with costs (S3 static site, EC2 server)
- **DevOps:** Report missing files, suggest initialization with `ExecuteTerraformCommand` (init)

For detailed analysis, use EXPLAIN.md or VERIFY.md.
