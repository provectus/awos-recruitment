---
name: documentation-engineering
description: >-
  Repository documentation and Confluence publishing. Use when asked to analyze
  a repository's structure, generate documentation (README, architecture, API
  reference, onboarding guide, runbook), publish to Confluence, sync docs, or
  audit documentation quality and coverage.
version: 0.1.0
---

# Documentation Engineering

Full-lifecycle documentation skill: analyze repositories, generate docs, publish to Confluence, sync changes, and audit quality.

## Repository Analysis

Before generating documentation, scan the repo systematically:

1. **Clone** with `git clone --depth 1`
2. **Scan structure** — directories, entry points, config files
3. **Detect tech stack** from `package.json`, `requirements.txt`, `go.mod`, `Cargo.toml`
4. **Extract API endpoints** from route definitions, controllers, OpenAPI specs
5. **Catalog dependencies** with versions
6. **Parse CI/CD** from `.github/workflows/`, `.gitlab-ci.yml`
7. **Inventory existing docs** — README, CHANGELOG, CONTRIBUTING, `docs/`

### Key Artifacts

| Artifact | Source Files | Purpose |
|----------|-------------|---------|
| Tech Stack | `package.json`, `requirements.txt`, `go.mod` | Languages, frameworks |
| Entry Points | `main.*`, `app.*`, `index.*`, `cmd/` | Application startup |
| API Endpoints | `routes/`, `controllers/`, OpenAPI specs | Public interfaces |
| Database Schema | `migrations/`, `models/`, `schema.*` | Data layer |
| CI/CD Pipeline | `.github/workflows/`, `.gitlab-ci.yml` | Build/deploy process |
| Configuration | `.env.example`, `config/`, `settings.*` | Environment setup |

### Output Format

Produce structured JSON for downstream operations:

```json
{
  "project_name": "example-service",
  "tech_stack": { "language": "TypeScript", "framework": "NestJS", "database": "PostgreSQL" },
  "structure": { "source_dir": "src/", "test_dir": "test/", "entry_point": "src/main.ts" },
  "api_endpoints": [],
  "dependencies": {},
  "ci_cd": {}
}
```

## Document Generation

### README

Include: project title + badges, prerequisites, installation, configuration (from `.env.example`), usage, API summary, testing, deployment, contributing guidelines.

### Architecture Doc

```markdown
# Architecture: <Project Name>
## Overview — high-level purpose
## System Diagram — Mermaid or PlantUML
## Components — purpose, technology, key files per component
## Data Flow — request lifecycle
## Infrastructure — hosting, databases, external services
```

### API Reference

Extract from OpenAPI specs, route definitions, or controller decorators:

```markdown
### GET /api/v1/users
**Auth**: Bearer token required
**Query**: `page`, `limit`, `search`
**Response**: `200 OK` — Array of User objects
```

### Onboarding Guide

Day 1: environment setup. Day 2: codebase tour (modules, data models). Day 3: first contribution (branch, commit, PR workflow).

### Runbook

Service overview, health check endpoints, common issues with symptoms/diagnosis/resolution.

## Confluence Publishing

### Markdown to Storage Format

| Markdown | Confluence Storage Format |
|----------|--------------------------|
| `# Heading` | `<h1>Heading</h1>` |
| `**bold**` | `<strong>bold</strong>` |
| `` `code` `` | `<code>code</code>` |
| Code blocks | `<ac:structured-macro ac:name="code">` |
| Tables | `<table><tr><th>...</th></tr></table>` |
| Info boxes | `<ac:structured-macro ac:name="info">` |

### Page Workflow

1. Identify target space and parent page
2. Search by title to avoid duplicates
3. Convert Markdown to Storage Format
4. Create or update page via REST API
5. Add labels: `auto-generated`, `repo:<name>`, `type:<doctype>`
6. Verify formatting by fetching page back

### Sync Strategy

- Detect changes with `git log --since="<last-sync>" --name-only`
- Update only changed sections — preserve manual edits
- Increment version number, add "Auto-updated from <repo> on <date>"

## Documentation Quality

Score on five dimensions: completeness, accuracy, readability, freshness, formatting. Flag broken links, outdated code examples, missing sections. Track coverage across repos.

## Deep Dives

| Topic | Reference |
|---|---|
| Repository analysis workflow | `references/repo-analysis.md` |
| Document templates and generation | `references/doc-generation.md` |
| Confluence publishing patterns | `references/confluence-publishing.md` |
| Documentation sync and quality | `references/doc-sync.md` |
