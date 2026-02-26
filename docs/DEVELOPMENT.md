# Development Guide

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| [Python](https://www.python.org/) | 3.12+ | Server runtime |
| [uv](https://docs.astral.sh/uv/) | latest | Python package and project manager |
| [Node.js](https://nodejs.org/) | 20+ | CLI runtime |
| [npm](https://www.npmjs.com/) | 10+ | CLI package manager |
| [just](https://github.com/casey/just) | latest | Command runner |
| [Docker](https://www.docker.com/) | latest | Container builds for deployment |
| [Terraform](https://www.terraform.io/) | 1.9+ | Infrastructure provisioning (AWS) |
| [AWS CLI](https://aws.amazon.com/cli/) | 2.x | AWS authentication and ECS deployments |

## Getting Started

```bash
# Install server dependencies
cd server && uv sync

# Install CLI dependencies
cd cli && npm install

# Copy environment config (optional — defaults work out of the box)
cp server/.env.example server/.env

# Verify everything works
just test -v
just validate-registry
```

## Common Commands

All commands run from the **repository root** via `just`:

| Command | Description |
|---------|-------------|
| `just serve` | Start the MCP server (default: `http://0.0.0.0:8000`) |
| `just test` | Run server tests |
| `just test -v` | Run tests with verbose output |
| `just test tests/test_validate.py` | Run a specific test file |
| `just validate-registry` | Validate all registry entries |
| `just validate-registry --format json` | Validate with JSON output (for CI) |
| `just build-cli` | Build the CLI (TypeScript → `cli/dist/`) |
| `just test-cli` | Run CLI tests |
| `just publish-cli` | Bump patch version and publish CLI to npm |
| `just publish-cli minor` | Bump minor version and publish |
| `just publish-cli major` | Bump major version and publish |
| `just deploy <account_id>` | Build, push to ECR, and redeploy to ECS (us-east-1 by default) |
| `just deploy <account_id> eu-west-1` | Deploy to a specific region |

## Server Configuration

Override defaults via environment variables or `server/.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `AWOS_HOST` | `0.0.0.0` | Server bind address |
| `AWOS_PORT` | `8000` | Server port |
| `AWOS_VERSION` | `0.1.0` | Server version |
| `AWOS_REGISTRY_PATH` | `../registry` | Path to the capability registry directory |
| `AWOS_EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Sentence-transformer model for embeddings |
| `AWOS_SEARCH_THRESHOLD` | `20` | Minimum relevance score (0–100) for search results |

## Project Structure

```
awos-recruitment/
├── server/              # Python FastMCP MCP server
│   ├── src/awos_recruitment_mcp/
│   │   ├── server.py        # FastMCP instance, lifespan handler, health check
│   │   ├── config.py        # Config from env vars
│   │   ├── registry.py      # Registry loader (scans and parses capabilities)
│   │   ├── search_index.py  # ChromaDB search index (build + query)
│   │   ├── models/          # Pydantic models (capabilities, skills, MCP defs, agents)
│   │   ├── tools/           # MCP tool implementations
│   │   └── validate/        # Registry validation CLI
│   ├── tests/               # pytest test suite
│   └── pyproject.toml       # Dependencies and project config
├── registry/            # Git-managed capability catalog
│   ├── skills/              # Claude Code skill definitions
│   ├── mcp/                 # MCP server definitions
│   └── agents/              # Claude Code agent definitions
├── cli/                 # TypeScript npx package for capability installation
│   ├── src/
│   │   ├── index.ts         # Entry point with error boundary
│   │   ├── cli.ts           # Argument parsing and subcommand routing
│   │   ├── commands/        # skill, mcp, and agent install commands
│   │   └── lib/             # download, json-merge, frontmatter, errors, types
│   ├── package.json
│   └── tsconfig.json
├── infra/               # Terraform infrastructure (AWS ECS, ALB, VPC)
│   ├── providers.tf         # AWS provider, backend config
│   ├── vpc.tf               # VPC, subnets, NAT gateway
│   ├── ecs.tf               # ECS cluster, service, task definition
│   ├── alb.tf               # Application Load Balancer, listeners
│   ├── acm.tf               # ACM certificate, DNS validation
│   ├── dns.tf               # Route 53 DNS record
│   ├── ecr.tf               # ECR repository
│   ├── ssm.tf               # SSM Parameter Store config
│   └── ...                  # security_groups.tf, logs.tf, variables.tf, outputs.tf
├── context/             # Product docs, specs, and roadmap
│   ├── product/             # Product definition, architecture, roadmap
│   └── spec/                # Feature specifications
├── justfile             # Command runner tasks
└── docs/                # Developer and contributor documentation
```

## Development Workflow with AWOS

This project uses [AWOS](https://github.com/provectus/awos) (AI Workflow Orchestration System) to manage feature development from spec to implementation. We recommend installing AWOS and using its structured pipeline for all feature work. See the AWOS repository for full documentation on available commands and workflow stages.
