# Technical Specification: Capability Installation

- **Functional Specification:** `context/spec/004-capability-installation/functional-spec.md`
- **Status:** Completed
- **Author(s):** Engineering

---

## 1. High-Level Technical Approach

This feature adds two components:

1. **Server-side (`POST /bundle/skills` and `POST /bundle/mcp` endpoints):** Two new HTTP routes on the existing FastMCP server. Each accepts a JSON list of capability names and returns a `.tar.gz` archive containing the matching registry files. Built with Python's `tarfile` module and the existing registry path infrastructure.

2. **Client-side (npx CLI package):** A new TypeScript CLI in `cli/` with `skill` and `mcp` subcommands. Each subcommand calls its corresponding bundle endpoint, extracts the archive, and writes capabilities to their local destinations (`.claude/skills/` for skills, `.mcp.json` for MCP tools). Uses best-effort semantics: each item installs independently, with a summary at the end.

---

## 2. Proposed Solution & Implementation Plan (The "How")

### Architecture Changes

No changes to the overall architecture. The server gains two new HTTP routes. A new `cli/` TypeScript package is added to the monorepo.

### API Contracts

#### `POST /bundle/skills`

| Aspect | Detail |
|---|---|
| Method | `POST` |
| Content-Type (request) | `application/json` |
| Content-Type (response) | `application/gzip` |
| Auth | None |

**Request body:**

| Field | Type | Rules |
|---|---|---|
| `names` | `string[]` | 1-20 items. Each must match `^[a-z0-9-]{1,64}$`. |

**Response:**
- `200 OK`: tar.gz archive. Each found skill is included as its full directory: `<name>/SKILL.md`, `<name>/references/*.md`. Not-found names are silently omitted.
- `400 Bad Request`: Invalid request body. JSON error response.

**Archive layout:**
```
modern-python-development/SKILL.md
modern-python-development/references/modern-syntax.md
modern-python-development/references/patterns.md
...
```

#### `POST /bundle/mcp`

| Aspect | Detail |
|---|---|
| Method | `POST` |
| Content-Type (request) | `application/json` |
| Content-Type (response) | `application/gzip` |
| Auth | None |

**Request body:**

| Field | Type | Rules |
|---|---|---|
| `names` | `string[]` | 1-20 items. Each must match `^[a-z0-9-]{1,64}$`. |

**Response:**
- `200 OK`: tar.gz archive. Each found MCP definition is included as `<name>.yaml`. Not-found names are silently omitted.
- `400 Bad Request`: Invalid request body. JSON error response.

**Archive layout:**
```
context7.yaml
playwright.yaml
```

### Server-Side Changes (Python)

| File | Change |
|---|---|
| `models/bundle.py` | New `BundleRequest` Pydantic model with `names: list[str]` field (1-20 items, kebab-case pattern). |
| `models/__init__.py` | Re-export `BundleRequest`. |
| `registry.py` | New `resolve_skill_paths(names, registry_path)` and `resolve_mcp_paths(names, registry_path)` functions. Map names to file paths by checking `skills/<name>/` dirs and `mcp/<name>.yaml` files respectively. Return found paths and not-found names. |
| `server.py` | Two new `@mcp.custom_route` handlers: `/bundle/skills` and `/bundle/mcp`. Each parses the request with `BundleRequest`, calls the corresponding resolve function, builds a tar.gz in memory with `tarfile`, and returns it as `Response(content=..., media_type="application/gzip")`. |

### CLI Package (TypeScript)

**Location:** `cli/`

**Dependencies:**

| Dependency | Type | Purpose |
|---|---|---|
| `tar` (v7+) | runtime | tar.gz extraction |
| `yaml` (v2+) | runtime | YAML parsing for MCP definitions |
| `typescript` (v5.7+) | dev | Compilation |
| `@types/node` (v22+) | dev | Node.js type definitions |
| `vitest` (v3+) | dev | Testing |

**Configuration:**
- `AWOS_SERVER_URL` env var, defaults to `http://localhost:8000`
- `package.json` with `"type": "module"`, `bin` entry pointing to `dist/index.js`
- `tsconfig.json`: `target: ES2022`, `module: Node16`, `strict: true`

**Key files and responsibilities:**

| File | Responsibility |
|---|---|
| `src/index.ts` | Shebang entry point (`#!/usr/bin/env node`), top-level error boundary. |
| `src/cli.ts` | Parses `process.argv`, routes to `skill` or `mcp` subcommand. Validates at least one name is provided. |
| `src/commands/skill.ts` | Downloads from `/bundle/skills`. For each skill in the extracted archive: check `.claude/skills/<name>/` doesn't exist (conflict check), copy directory to destination. Print per-item results. |
| `src/commands/mcp.ts` | Downloads from `/bundle/mcp`. For each YAML in the extracted archive: parse it, check server key not in `.mcp.json` (conflict check), merge into `.mcp.json` (create if needed). Print per-item results. |
| `src/lib/download.ts` | `fetch()` a bundle endpoint, pipe response through `zlib.createGunzip()` and `tar.extract()` to a temp directory. |
| `src/lib/json-merge.ts` | Read/create `.mcp.json`, merge new `mcpServers` entries, write back. |
| `src/lib/errors.ts` | `CliError` hierarchy with exit codes: `NetworkError`, `ConflictError`, `NotFoundError`. |
| `src/lib/types.ts` | Shared interfaces for MCP YAML shape, install results. |

**Install flow (skill subcommand):**
1. Parse args, collect skill names.
2. POST names to `{AWOS_SERVER_URL}/bundle/skills`, extract tar.gz to temp directory.
3. Diff requested names against extracted directories to identify not-found names.
4. For each found skill: check `.claude/skills/<name>/` doesn't exist, then copy directory. Record result.
5. Print summary. Exit 0 if all succeeded, non-zero if any failed.

**Install flow (mcp subcommand):**
1. Parse args, collect MCP tool names.
2. POST names to `{AWOS_SERVER_URL}/bundle/mcp`, extract tar.gz to temp directory.
3. Diff requested names against extracted YAML files to identify not-found names.
4. For each found MCP YAML: parse it, check server key not in `.mcp.json`, merge config entry into `.mcp.json` (create file if needed). Record result.
5. Print summary. Exit 0 if all succeeded, non-zero if any failed.

---

## 3. Impact and Risk Analysis

**System Dependencies:**
- The bundle endpoints depend on the registry path (already configured via `AWOS_REGISTRY_PATH`).
- The CLI depends on the server being reachable. No other system dependencies.

**Risks and Mitigations:**

| Risk | Mitigation |
|---|---|
| Large archives | Cap `names` list at 20. Individual capabilities are small (a few KB of markdown/YAML). |
| Partial write on crash | Extract to temp directory first, then copy to final destinations. Clean up temp dir in `finally`. |
| Path traversal in archive | `tar` npm package strips absolute paths by default. Validate extracted paths stay within expected directories. |
| `.mcp.json` corruption | Parse and merge in memory before writing. Fail cleanly if existing file is malformed JSON. |
| Server unavailable | CLI prints clear error with the URL it tried. Non-zero exit code. |

---

## 4. Testing Strategy

**Server tests** (`tests/test_bundle.py`):
- Use `httpx.ASGITransport` pattern (same as `test_health.py`).
- Create a mini registry via `tmp_path` fixture.
- Test cases per endpoint: valid request, partial matches, empty names (400), all not-found (200 with empty archive), names exceeding limit (400).
- Verify response is valid tar.gz, extract with `tarfile`, assert correct file contents and structure.

**CLI unit tests** (Vitest):
- `json-merge.test.ts`: Create new `.mcp.json`, merge into existing, conflict detection, preserve unknown keys, handle malformed JSON.
- `download.test.ts`: Mock `fetch`, test network error handling, corrupt response handling.
- `commands/skill.test.ts` and `commands/mcp.test.ts`: Use temp directories, mock HTTP, verify files written correctly and conflicts detected.

**CLI integration tests:**
- Spawn built binary as child process.
- Verify exit codes, stdout messages for success/error.
