# AWS Stack Layout & Registry Modules

How to split AWS infrastructure into separately-stated stacks, how to pick between a public registry module and a raw `resource`, and how stacks read each other's outputs. Provectus conventions — they override the generic guidance in the other references where they differ.

## Table of Contents

1. [Registry Module Selection](#registry-module-selection)
2. [Stack Layers](#stack-layers)
3. [Security Baseline](#security-baseline)
4. [When to Write a Local Module](#when-to-write-a-local-module)
5. [Cross-Root Wiring by Lookup](#cross-root-wiring-by-lookup)
6. [Worked Example: ECS Fargate Service](#worked-example-ecs-fargate-service)
7. [Common Mistakes](#common-mistakes)

---

## Registry Module Selection

**Default: use a public registry module, pinned to an exact version.** Prefer the `terraform-aws-modules` namespace; otherwise a verified publisher with high downloads.

| Component | Registry module | Raw resource is fine when |
|-----------|-----------------|---------------------------|
| VPC, subnets, route tables, NAT, IGW | `terraform-aws-modules/vpc/aws` | never |
| VPC endpoints | `terraform-aws-modules/vpc/aws//modules/vpc-endpoints` | never |
| Security groups | `terraform-aws-modules/security-group/aws`, or the SG built into the alb/ecs modules | one rule attaching two existing SGs |
| Load balancer, listeners, target groups | `terraform-aws-modules/alb/aws` | never |
| ECS cluster, service, task definition, task/exec roles, log group | `terraform-aws-modules/ecs/aws` (+ `//modules/service`) | never |
| ACM certificate + DNS validation | `terraform-aws-modules/acm/aws` | never |
| Route53 zone | `terraform-aws-modules/route53/aws` | a single zone with no records |
| Route53 alias record for one host | — | always (one resource, a module adds nothing) |
| DynamoDB table | `terraform-aws-modules/dynamodb-table/aws` | never |
| S3 bucket | `terraform-aws-modules/s3-bucket/aws` | never |
| ECR repository + lifecycle policy | `terraform-aws-modules/ecr/aws` | never |
| RDS / Aurora | `terraform-aws-modules/rds/aws`, `…/rds-aurora/aws` | never |
| Lambda | `terraform-aws-modules/lambda/aws` | never |
| IAM roles / OIDC | `terraform-aws-modules/iam/aws` submodules | an inline policy on a role a module already created |
| Secrets Manager | raw `aws_secretsmanager_secret` is fine | the module adds little; keep write-only value arguments |

A raw `resource` is acceptable only when (a) no module covers it, (b) the module would wrap a single resource, or (c) the module lacks a feature you need. **Write the reason** in the design table.

### Registry lookup protocol (terraform MCP)

For every component, before writing code:

1. `search_modules` → pick the `terraform-aws-modules` (or verified) result.
2. `get_latest_module_version` → the number you will pin. **This is a lookup, not a constraint.**
3. `get_module_details` with `<namespace>/<name>/<provider>/<version>` → read inputs, outputs, submodules and the **Provider Dependencies** table.
4. Check the module's provider constraint (e.g. `aws >= 6.28`) accepts the provider version pinned in the root. If not, report the conflict — do not silently bump the provider.
5. **When the module replaces existing resources, compare its defaults — not just the arguments the old code set — against the live resource.** Old code that omitted an argument got the AWS default; the module may set a different one (e.g. the ECS container definition defaults `readonlyRootFilesystem = true`, the service `enable_ecs_managed_tags = true`, the ALB `enable_deletion_protection = true`). List every difference in the design. **A stricter security default stays:** adapt the workload instead (e.g. mount a writable volume for the paths the app writes, such as `~/.local`), and relax it only with a stated reason. A non-security default that would change behaviour is set explicitly to the live value.
6. Write `version = "X.Y.Z"` — exact. Never `~>`, `>=`, a range, an omitted `version`, or a floating git ref.

**Existing code:** keep every pinned version as-is and read docs at *that* version. A newer version is reported, never applied, unless the user asks for an upgrade.

**Registry MCP unreachable:** stop and tell the user. Never write versions or module inputs from memory.

**Scope:** every module in every root — including `bootstrap` and other helper roots. A version you did not resolve through the MCP in this session does not get written, not even with a "verify later" note.

---

## Stack Layers

**Directory layout: `<root>/<aws-account-id>/<env>/`.** `<root>` is `infra/` or `terraform/`; under it, one directory per AWS account (the 12-digit ID), and under each account one directory per environment — typically `dev`, `prod` and `shared`. The root name, the account IDs, which environments live in which account, and which account holds `shared` are **confirmed with the user in the Design phase** (or taken from the existing repo), never assumed.

**One root module (one state) per environment**, organised into layer files. Layers pass values through module outputs — no lookups, no remote state inside an environment. Resources used by several environments live in the `shared` root.

| Layer | Where | Contains | Changes |
|-------|-------|----------|---------|
| `bootstrap` | `<account>/bootstrap/`, local state | that account's state bucket (S3 native locking, `use_lockfile = true` — no DynamoDB lock table) | once per account |
| `shared` | `<account>/shared/` | Route53 zone, ECR repos, GitHub OIDC provider, CI roles | rarely |
| network | `<account>/<env>/network.tf` | VPC, subnets, endpoints | rarely |
| dns | `<account>/<env>/dns.tf` | ACM certificate + validation records | rarely |
| data | `<account>/<env>/data.tf` | DynamoDB / RDS / S3 with data, secrets | rarely, never destroyed |
| app | `<account>/<env>/app.tf` | ALB, ECS/Lambda, IAM task roles, log groups, app SGs, alias record | often |

```
infra/                       # or terraform/ — confirmed at design time
├── modules/
│   └── app/                 # only if justified — see next section
├── 111111111111/            # an AWS account (IDs are examples; the env → account mapping is a design question, not a default)
│   ├── bootstrap/
│   ├── shared/              # backend key: 111111111111/shared.tfstate
│   └── dev/                 # backend key: 111111111111/dev.tfstate
│       ├── network.tf
│       ├── dns.tf
│       ├── data.tf
│       ├── app.tf
│       ├── backend.tf  versions.tf  providers.tf  locals.tf  data-sources.tf  outputs.tf
└── 222222222222/            # another AWS account
    ├── bootstrap/
    └── prod/ …
```

Each root's provider sets `allowed_account_ids = ["<account-id>"]` from its directory, so a plan run with the wrong profile fails instead of touching another account.

**Protect the data layer inside the shared state:** `deletion_protection_enabled = true` on tables and databases (AWS refuses the delete even if a plan asks for it), `lifecycle { prevent_destroy = true }` on raw resources such as secrets, and read every plan for replacements in `data.tf` before applying.

**Split a layer into its own root only with a stated reason** — separate owning teams, plans that are too slow, or a blast radius the user explicitly wants isolated. Then the split-out root is wired by lookup (next sections). Never split by default.

**Refactoring inside one state:** use `moved {}` blocks (and `import {}` for objects the new modules manage separately), reviewed in a normal plan. No `terraform state mv` between backends.

---

## Security Baseline

**Least privilege by default.** Every row below is the default; a deviation is allowed only with a reason written in the design's security posture. Where a registry module already sets the value, keep it; where it does not, set it explicitly.

| Layer | Component | Required |
|-------|-----------|----------|
| network | subnets | ECS tasks, Lambdas in a VPC, databases and endpoints go in **private** subnets; only the ALB and NAT go in public ones |
| network | egress | NAT gateway, or VPC endpoints when there is no NAT: gateway endpoints for S3/DynamoDB, interface endpoints for ECR (`ecr.api`, `ecr.dkr`), `logs`, `secretsmanager` |
| network | VPC | flow logs on; the default security group has no rules |
| app | ALB SG | ingress 443 from `0.0.0.0/0` (and 80 only for the HTTPS redirect); egress only to the task SG on the container port |
| app | ALB | HTTPS listener with a TLS 1.2+ policy (e.g. `ELBSecurityPolicy-TLS13-1-2-2021-06`); port 80 redirects, never forwards; `drop_invalid_header_fields = true` |
| app | task SG | ingress only from the ALB SG (`referenced_security_group_id`) on the container port — never a CIDR |
| app | ECS task | `assign_public_ip = false`; `readonlyRootFilesystem = true` with a writable volume for the paths the app needs; non-root `user` when the image allows |
| app | IAM | separate task role and execution role; each statement lists exact actions and resource ARNs (the table ARN and its `/index/*`, the secret ARN) — no `Action = "*"`, no `Resource = "*"` except for actions that do not support resource-level permissions |
| app | secrets | injected through the container definition's `secrets` (the execution role gets `secretsmanager:GetSecretValue` on that ARN only), never through `environment` |
| app | logs | CloudWatch log group with explicit `retention_in_days` |
| data | DynamoDB / RDS | encryption at rest, point-in-time recovery / backups, deletion protection; RDS not publicly accessible |
| data | S3 | block public access (all four), encryption, versioning, TLS-only bucket policy |
| data | secrets | write-only value arguments; `prevent_destroy` |
| shared | ECR | scan on push; immutable tags |
| shared | CI role | GitHub OIDC trust scoped to the repo and branch/environment (`sub` condition); no long-lived keys |

**Static checks before every plan:** `trivy config .` and `checkov -d .`. HIGH/CRITICAL findings block. A suppression is an inline `#checkov:skip=<ID>:<reason>` / `#trivy:ignore:<ID>` with the reason from the design — never a blanket skip.

---

## When to Write a Local Module

A root calls registry modules **directly**. Do **not** create `modules/network` that only wraps `terraform-aws-modules/vpc` — a pass-through module adds a layer, an extra set of variables and outputs, and nothing else.

Write a local `modules/<name>` only when **both** hold:

- the stack composes **several** modules/resources with non-trivial wiring (e.g. ALB + ECS service + SG rules + IAM + alias record), **and**
- that wiring must be identical in more than one environment.

Local modules: provider constraints as `>=` minimums (the root's exact pin and `.terraform.lock.hcl` decide), registry module `version` still exact, no `provider` blocks.

---

## Cross-Root Wiring by Lookup

**Inside one root, pass module outputs directly.** Between roots — an environment reading `shared`, or a layer that was split out for a stated reason — **the consumer reads what the producer created through data sources**, by a name or tag the producer sets deterministically. No `terraform_remote_state`: consumers don't depend on another root's backend, and state read access isn't needed.

| Value | Producer sets | Consumer lookup |
|-------|---------------|-----------------|
| VPC | `Name = "<project>-<env>"` tag | `data "aws_vpc"` filtered by `tag:Name` |
| Subnets | `Tier = "public"` / `"private"` tags | `data "aws_subnets"` filtered by `vpc-id` + `tag:Tier` |
| Certificate | domain name | `data "aws_acm_certificate"` with `domain`, `statuses = ["ISSUED"]`, `most_recent = true` |
| Hosted zone | zone name | `data "aws_route53_zone"` with `name` |
| DynamoDB table | table name | `data "aws_dynamodb_table"` with `name` |
| Secret | secret name | `data "aws_secretsmanager_secret"` with `name` |
| ECR repo | repo name | `data "aws_ecr_repository"` with `name` |

When `shared` is in a different account than the consumer, the lookup uses an aliased provider that assumes a read-only role in that account; the producer's resource policy (e.g. the ECR repository policy) grants the consumer account access.

```hcl
# a split-out app root reading the network root
data "aws_vpc" "this" {
  filter {
    name   = "tag:Name"
    values = ["${local.project}-${local.environment}"]
  }
}

data "aws_subnets" "public" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.this.id]
  }

  tags = {
    Tier = "public"
  }
}

data "aws_acm_certificate" "this" {
  domain      = local.host_name
  statuses    = ["ISSUED"]
  most_recent = true
}
```

Put the lookup keys (names, tags) in `locals.tf` of both roots so the contract is visible. Use `terraform_remote_state` only when the producer is owned by another team and exposes a deliberate, versioned output contract.

---

## Worked Example: ECS Fargate Service

Request: containerised API on ECS Fargate behind HTTPS ALB at a custom domain, DynamoDB table, one secret, dev + prod, existing hosted zone.

| Component | Layer file | Source | Why |
|-----------|-------|--------|-----|
| VPC, public/private subnets | `network` | `terraform-aws-modules/vpc/aws` | registry |
| DynamoDB gateway + ECR/logs/Secrets Manager interface endpoints | `network` | `…/vpc/aws//modules/vpc-endpoints` | registry; private tasks egress without a NAT |
| Certificate + validation | `dns` | `terraform-aws-modules/acm/aws` | registry |
| Table | `data` | `terraform-aws-modules/dynamodb-table/aws` | registry |
| Secret | `data` | raw `aws_secretsmanager_secret` | module adds little; write-only value |
| ALB | `app` | `terraform-aws-modules/alb/aws` via `modules/app` | registry |
| ECS cluster + service + roles + logs | `app` | `terraform-aws-modules/ecs/aws` via `modules/app` | registry |
| Alias record | `app` | raw `aws_route53_record` | single resource |

Everything lives in one root per environment (`<account-id>/<env>`, one state). `modules/app` is justified only because the ALB + ECS + SG rules + alias wiring is identical in dev and prod; the other layers call registry modules directly.

```hcl
# 111111111111/dev/network.tf — registry module called directly, no local wrapper
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "X.Y.Z" # exact; resolved with get_latest_module_version at design time

  name = "${local.project}-${local.environment}"
  cidr = local.vpc_cidr
  azs  = local.azs

  public_subnets      = local.public_subnet_cidrs  # ALB only
  public_subnet_tags  = { Tier = "public" }
  private_subnets     = local.private_subnet_cidrs # ECS tasks
  private_subnet_tags = { Tier = "private" }

  enable_nat_gateway = false # egress via the endpoints below; a NAT is the alternative when tasks call the internet

  enable_flow_log                      = true
  create_flow_log_cloudwatch_log_group = true
  create_flow_log_cloudwatch_iam_role  = true
}

module "vpc_endpoints" {
  source  = "terraform-aws-modules/vpc/aws//modules/vpc-endpoints"
  version = "X.Y.Z" # same exact version as module.vpc

  vpc_id = module.vpc.vpc_id

  endpoints = {
    dynamodb = {
      service         = "dynamodb"
      service_type    = "Gateway"
      route_table_ids = module.vpc.private_route_table_ids
    }
    # plus Interface endpoints (private_dns_enabled = true, subnet_ids = module.vpc.private_subnets)
    # for ecr.api, ecr.dkr, logs and secretsmanager, with an SG allowing 443 from the task SG
  }
}

# 111111111111/dev/app.tf — same root, so outputs are passed directly (no lookups)
module "app" {
  source = "../../modules/app"

  vpc_id             = module.vpc.vpc_id
  alb_subnet_ids     = module.vpc.public_subnets
  service_subnet_ids = module.vpc.private_subnets # tasks never get a public IP
  certificate_arn    = module.acm.acm_certificate_arn
  table_arn          = module.table.dynamodb_table_arn
}
```

---

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Raw `aws_vpc` / `aws_subnet` / `aws_lb` / `aws_ecs_service` blocks | Use the registry module; raw only with a written reason |
| One module holding network + dns + data + app | Registry modules called from the env root, one file per layer |
| `modules/network` that only calls `terraform-aws-modules/vpc` | Call the registry module from the root |
| `version = "~> 6.0"`, `">= 6.0"`, or no `version` on a registry module | `version = "X.Y.Z"` |
| Replacing hand-written resources and trusting module defaults (a read-only root broke startup) | Diff module defaults against the live resource; set them explicitly |
| Bumping an existing module pin "while you're there" | Keep it; report the newer version instead |
| Version or inputs written from memory ("re-verify before apply") | Look them up via the terraform MCP; stop if it's unavailable |
| A separate root (state) per layer with no stated reason | One root per environment; split only for separate teams, slow plans, or an isolation the user asked for |
| `terraform state mv` between backends to refactor | `moved {}` blocks inside the one state, reviewed in a plan |
| Copying `required_version` from a skill example | Reuse the repo's pin; in a new repo resolve the latest release and confirm |
| DynamoDB table for state locking | `use_lockfile = true` in the S3 backend |
| `terraform_remote_state` between your own roots | Data-source lookup by name/tag |
| ACM certificate declared in `app.tf` | `dns.tf`; pass `module.acm.acm_certificate_arn` to the app |
| ECS tasks in public subnets with a public IP | Private subnets + NAT or VPC endpoints; public only as a written cost trade-off |
| Task SG ingress from a CIDR (`0.0.0.0/0`, the VPC CIDR) | Ingress only from the ALB SG on the container port |
| HTTP listener that forwards to the target group | Port 80 redirects to HTTPS |
| `Resource = "*"` or `dynamodb:*` on the task role | Exact actions on the table / index / secret ARNs |
| Secret value in the container `environment` | Container `secrets` referencing the Secrets Manager ARN |
| Relaxing a stricter module default to match legacy (`readonlyRootFilesystem = false`) | Keep the default, mount a writable volume; relax only with a written reason |
| trivy/checkov skipped, or findings silenced without a reason | Run both before the plan; inline skip with the ID and reason |
