# ProRAG CLI Reference

## Installation

ProRAG is distributed via AWS CodeArtifact (not PyPI):

```bash
# In a generated project directory:
task ca:login    # Authenticate to CodeArtifact, writes token to .env
task setup       # Create venv and install all dependencies
```

CodeArtifact details:
- Domain: `provrag`
- Account: `257394491982`
- Region: `us-east-2`
- AWS Profile: `provectus-demos`

## provrag CLI Commands

### provrag init

Scaffold a new ProRAG project from the Copier template.

```bash
# Interactive (prompts for all fields):
provrag init

# Non-interactive:
provrag init --name "Acme Legal RAG" --description "Legal document Q&A" \
  --index acme-legal-docs --dimension 1024 --author "Team Name" \
  --gitlab-group provectus-internals/MLP-COL/ai-accelerators/provrag-projects
```

Flags:
| Flag | Default | Description |
|------|---------|-------------|
| `--output-dir <dir>` | `.` | Parent directory for the new project |
| `--name <name>` | (prompted) | Project name (e.g., "acme-legal-rag") |
| `--description <desc>` | "RAG application built with ProRAG" | Short description |
| `--index <name>` | `{slug}-docs` | Default OpenSearch index name |
| `--dimension <int>` | `1024` | Embedding vector dimension |
| `--author <name>` | "Provectus" | Author name |
| `--gitlab-group <path>` | `provectus-internals/MLP-COL/ai-accelerators/provrag-projects` | GitLab group for repo creation |
| `--no-gitlab` | `false` | Skip GitLab repo creation |

After scaffolding:
1. `cd <project-name>`
2. `task ca:login` (authenticate to CodeArtifact)
3. `task setup` (install dependencies)
4. Configure `.env` for your environment

### provrag ingest

Run an ingestion pipeline to load, chunk, embed, and index documents.

```bash
provrag ingest --index my-docs --pipeline my_package.ingestion:ingest_pipeline
provrag ingest --index my-docs --prefix pdfs/ --pipeline my_package.ingestion:ingest_pipeline
```

Flags:
| Flag | Description |
|------|-------------|
| `--index <name>` | Override OpenSearch index name |
| `--prefix <s3-prefix>` | S3 key prefix to filter documents |
| `--pipeline <module:function>` | Pipeline path (auto-discovered if single pipeline) |

### provrag serve

Start the FastAPI server.

```bash
provrag serve --index my-docs --port 8000 --pipeline my_package.pipeline:rag_pipeline
```

Flags:
| Flag | Default | Description |
|------|---------|-------------|
| `--host <host>` | `0.0.0.0` | Bind host |
| `--port <int>` | `8000` | Bind port |
| `--index <name>` | (required) | OpenSearch index to query |
| `--pipeline <module:function>` | (auto-discovered) | Query pipeline path |

Test with:
```bash
curl http://localhost:8000/health
curl -X POST http://localhost:8000/query \
  -H 'Content-Type: application/json' \
  -d '{"query": "What is the refund policy?"}'
```

### provrag status

Show project lifecycle stage.

```bash
provrag status          # JSON output
provrag status --human  # Pretty-printed (for human users only, agents should use plain `provrag status`)
provrag status --stage-only  # Just the stage name
```

Stages (in order):
`unknown` -> `scaffolded` -> `configured` -> `repo_created` -> `infra_previewed` -> `infra_deployed` -> `app_built` -> `app_deployed` -> `live`

### provrag list

List all OpenSearch indices.

```bash
provrag list
```

### provrag clean

Delete an OpenSearch index permanently.

```bash
provrag clean --index my-docs        # Interactive confirmation
provrag clean --index my-docs --yes  # Skip confirmation
```

Flags:
| Flag | Description |
|------|-------------|
| `--index <name>` | Index to delete (required) |
| `--yes` / `-y` | Skip confirmation prompt |

## Taskfile Commands (in generated projects)

### Development

| Command | Description |
|---------|-------------|
| `task setup` | Create venv, install deps (requires `task ca:login` first) |
| `task ca:login` | Authenticate to AWS CodeArtifact (writes token to `.env`) |
| `task test` | Run unit tests (`uv run pytest tests/ -v`) |
| `task lint` | Ruff check (`uv run ruff check src/ tests/`) |
| `task format` | Ruff format (`uv run ruff format src/ tests/`) |
| `task typecheck` | mypy strict (`uv run mypy src/`) |
| `task check` | Run all checks: lint + typecheck + test |
| `task upgrade` | Upgrade ProRAG to latest version |

### Operations

| Command | Description |
|---------|-------------|
| `task serve` | Start API server (`provrag serve --index {index} --port 8000`) |
| `task ingest` | Run ingestion pipeline (`provrag ingest --index {index}`) |

### AWS Connectivity

| Command | Description |
|---------|-------------|
| `task connect` | Start SSM tunnels to AWS services via bastion host |
| `task disconnect` | Kill all active SSM tunnel sessions |

#### task connect

Establishes SSM port-forwarding tunnels through the ProRAG bastion host to VPC services:

| Local Port | Remote Service | Purpose |
|------------|---------------|---------|
| `localhost:9200` | OpenSearch VPC endpoint (port 443) | Vector search queries |
| `localhost:4200` | ALB -> Prefect Server | Workflow UI and API |
| `localhost:6006` | ALB -> Phoenix | Observability UI and traces |
| `localhost:8080` | ALB -> ECS Service (port 80) | Deployed API (at `/{project-slug}/`) |

Prerequisites:
- AWS SSO session active: `aws sso login --profile provectus-demos`
- Bastion host running (tag: `provrag-bastion-bastion`)
- `OPENSEARCH_ENDPOINT` set in `.env`

```bash
task connect      # Starts all tunnels in background, blocks until Ctrl+C
task disconnect   # Kills all aws ssm start-session processes
```

After connecting:
- Access OpenSearch via `localhost:9200` (with SSL, SigV4 signing via `signing_host`)
- Access Prefect UI at `http://localhost:4200`
- Access Phoenix UI at `http://localhost:6006`
- Access deployed API at `http://localhost:8080/{project-slug}/health`

## Bootstrap Script

Located at: `scripts/bootstrap.sh` in the ProRAG repository.

Run before first `provrag init`:
```bash
bash scripts/bootstrap.sh
```

Checks and optionally installs:
1. git
2. Homebrew (macOS)
3. Docker (+ daemon running)
4. mise (version manager)
5. Python 3.13 (via mise)
6. uv (Python package manager)
7. go-task (task runner)
8. AWS CLI
9. AWS SSO (`provectus-demos` profile + login)
10. Pulumi (infrastructure-as-code)
11. glab (GitLab CLI)
12. glab authentication to `gitlab.provectus.com`
13. ProRAG repository clone

AWS SSO details:
- Profile: `provectus-demos`
- Region: `us-east-2`
- SSO Start URL: `https://provectus.awsapps.com/start`
- GitLab host: `gitlab.provectus.com`
