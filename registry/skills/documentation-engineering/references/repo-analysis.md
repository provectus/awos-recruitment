# Repository Analysis Reference

## Workflow

1. **Clone the repo** using `git clone --depth 1` with token auth
2. **Scan directory structure** using `find`, `ls`, file reading
3. **Detect tech stack** from config files (package.json, requirements.txt, go.mod, etc.)
4. **Extract entry points** — find main.*, app.*, index.*, cmd/ patterns
5. **Map API endpoints** — scan route definitions, controllers, OpenAPI specs
6. **Catalog dependencies** — list direct and dev dependencies with versions
7. **Analyze CI/CD** — parse .github/workflows/, .gitlab-ci.yml, Jenkinsfile
8. **Identify existing docs** — check for README, CHANGELOG, CONTRIBUTING, docs/ directory
9. **Produce analysis JSON** — structured output for downstream operations

## Key Artifacts to Extract

| Artifact | Source Files | Purpose |
|----------|-------------|---------|
| Tech Stack | `package.json`, `requirements.txt`, `go.mod`, `Cargo.toml` | Identify languages, frameworks, dependencies |
| Entry Points | `main.*`, `app.*`, `index.*`, `cmd/` | Understand application startup |
| API Endpoints | `routes/`, `controllers/`, `api/`, OpenAPI specs | Document public interfaces |
| Database Schema | `migrations/`, `models/`, `schema.*` | Document data layer |
| CI/CD Pipeline | `.github/workflows/`, `.gitlab-ci.yml`, `Jenkinsfile` | Document build/deploy process |
| Configuration | `.env.example`, `config/`, `settings.*` | Document environment setup |
| Tests | `test/`, `tests/`, `__tests__/`, `*_test.*` | Understand test coverage |

## Analysis Output Format

```json
{
  "project_name": "example-service",
  "description": "Extracted from README or package.json",
  "tech_stack": {
    "language": "TypeScript",
    "framework": "NestJS",
    "database": "PostgreSQL",
    "cache": "Redis"
  },
  "structure": {
    "source_dir": "src/",
    "test_dir": "test/",
    "docs_dir": "docs/",
    "entry_point": "src/main.ts"
  },
  "api_endpoints": [],
  "dependencies": {},
  "ci_cd": {}
}
```
