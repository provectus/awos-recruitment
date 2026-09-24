# terraform-conventions — maintainer notes

Local documentation for people editing this skill. It is not part of the
install bundle (`/bundle/skills` ships `SKILL.md` plus the flat files under
`references/`), so nothing here costs runtime tokens.

## Evaluations

Three prompts that exercise the conventions the skill exists to enforce. Run
each against a session with the skill loaded and check the expected
behaviours; run them again without the skill to see what the skill is buying.

They are chosen to catch drift between `SKILL.md` and the references, which is
how the 2026-09 audit findings arose — a README template that emitted `>=`
constraints, a `.gitignore` that deleted the lock file, secrets guidance that
labelled the same pattern DO in one file and BAD in another. Each of those
would have failed one of these evals.

### Eval 1 — Generate a module

> Create a Terraform module for an S3 bucket with versioning and server-side
> encryption for our prod account. Include the usual module files.

Expected behaviour:

- `versions.tf` pins `required_version` and every provider with exact `=`
  constraints — no `~>` and no `>=` anywhere in the output
- the README requirements table shows those same exact versions, not ranges
- every taggable resource merges `local.required_tags`, with
  `ManagedBy = "terraform"` (lower-case `t`)
- the generated `.gitignore` does **not** list `.terraform.lock.hcl`
- variables are ordered description → type → default → sensitive → nullable →
  validation
- it does not stop to ask "Terraform or OpenTofu?" — it detects or defaults to
  Terraform and proceeds

### Eval 2 — Handle a database secret

> Add an RDS MySQL instance to this module. The master password already lives
> in Secrets Manager under `prod/database/password`.

Expected behaviour:

- reads the existing secret with an `ephemeral`
  `aws_secretsmanager_secret_version` lookup rather than creating one, and not
  with a `data` source, whose result Terraform writes to state
- passes it as `password_wo` **with** `password_wo_version`
- does **not** offer `manage_master_user_password = true` as a substitute here:
  that makes RDS generate its own password in its own secret and never reads
  `prod/database/password`, so every consumer of the existing secret would
  start failing to authenticate
- does not introduce `random_password`
- does not assign the secret to the plain `password` argument
- says why: a value assigned to `password` is stored in plaintext in state

### Eval 3 — Review an existing configuration

Give it a configuration that contains, deliberately:

```hcl
terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}

resource "aws_instance" "app" {
  for_each      = var.environments
  count         = 2
  instance_type = "t3.micro"

  tags = { Name = "app" }
}

resource "aws_db_instance" "this" {
  password = var.db_password
}
```

> Review this Terraform for us.

Expected behaviour:

- flags `count` + `for_each` on one resource as invalid, not merely
  discouraged — Terraform rejects it
- flags `>= 1.5` and `~> 5.0` against the exact-pinning convention
- flags the missing required tags (`Environment`, `Project`, `Owner`,
  `ManagedBy`)
- flags `password = var.db_password` as a secret written to state
- does not offer to run `terraform apply`; proposes
  `terraform plan -out=plan.tfplan` and review first

## Checking HCL in this skill

Every HCL snippet should survive `terraform validate`. The quickest harness:

```bash
mkdir tfcheck && cd tfcheck
# add a versions.tf pinning the versions the skill's examples use,
# paste the snippet under test into main.tf, then:
terraform init
terraform fmt -check -diff
terraform validate
```

Snippets that reference `local.required_tags` or module variables need those
stubbed in the harness; that is expected, and is not a reason to drop the
convention from the example.

## Layout constraints

The registry validator (`server/src/awos_recruitment_mcp/validate/`) accepts
only `SKILL.md` and `README.md` as files, and only `references/` and
`scripts/` as directories, with flat files inside them. An `evals/` directory
would fail validation, which is why these prompts live here.
