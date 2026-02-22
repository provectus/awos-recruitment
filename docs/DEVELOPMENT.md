# Development Guide

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| [Python](https://www.python.org/) | 3.12+ | Server runtime |
| [uv](https://docs.astral.sh/uv/) | latest | Python package and project manager |
| [just](https://github.com/casey/just) | latest | Command runner |

## Getting Started

```bash
# Install server dependencies
cd server && uv sync

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
│   │   ├── models/          # Pydantic models (capabilities, skills, MCP defs)
│   │   ├── tools/           # MCP tool implementations
│   │   └── validate/        # Registry validation CLI
│   ├── tests/               # pytest test suite
│   └── pyproject.toml       # Dependencies and project config
├── registry/            # Git-managed capability catalog
│   ├── skills/              # Claude Code skill definitions
│   └── mcp/                 # MCP server definitions
├── cli/                 # TypeScript npx package (planned)
├── context/             # Product docs, specs, and roadmap
│   ├── product/             # Product definition, architecture, roadmap
│   └── spec/                # Feature specifications
├── justfile             # Command runner tasks
└── docs/                # Developer and contributor documentation
```

## Development Workflow with AWOS

This project uses **AWOS** (AI Workflow Orchestration System) to manage feature development from spec to implementation. All feature work follows a structured pipeline driven by slash commands.

### The AWOS Pipeline

Each feature progresses through these stages:

| Stage | Command | What it does |
|-------|---------|--------------|
| 1. Spec | `/awos:spec` | Creates a functional specification — the "what" and "why" |
| 2. Tech | `/awos:tech` | Creates a technical specification — the "how" |
| 3. Tasks | `/awos:tasks` | Breaks the tech spec into vertical slices with sub-tasks |
| 4. Implement | `/awos:implement` | Delegates tasks to specialized coding agents |
| 5. Verify | `/awos:verify` | Checks acceptance criteria, marks spec as complete |

### Supporting Commands

| Command | What it does |
|---------|--------------|
| `/awos:product` | Define or update the product definition |
| `/awos:architecture` | Define or update the system architecture |
| `/awos:roadmap` | Build or update the product roadmap |

### How to Start a New Feature

1. Check the roadmap at `context/product/roadmap.md` for the next incomplete item.
2. Run `/awos:spec` to create the functional specification (or pass a topic directly: `/awos:spec My Feature Name`).
3. Run `/awos:tech` to create the technical plan.
4. Run `/awos:tasks` to break it into implementable slices.
5. Run `/awos:implement` to start coding — it delegates to specialized agents and tracks progress.
6. Run `/awos:verify` when all tasks are done to validate acceptance criteria.

### Where Specs Live

All specifications are stored under `context/spec/` in numbered directories:

```
context/spec/
├── 001-mcp-server-protocol-integration/   # Completed
│   ├── functional-spec.md
│   ├── technical-considerations.md
│   └── tasks.md
├── 002-capability-registry-indexing/       # Completed
│   ├── functional-spec.md
│   ├── technical-considerations.md
│   └── tasks.md
└── 003-semantic-search/                   # Completed
    ├── functional-spec.md
    ├── technical-considerations.md
    └── tasks.md
```

Each directory contains the full paper trail for a feature: what was decided, how it was built, and what was verified.
