# Technical Specification: Capability Registry & Indexing

- **Functional Specification:** `context/spec/002-capability-registry-indexing/functional-spec.md`
- **Status:** Completed
- **Author(s):** AWOS

---

## 1. High-Level Technical Approach

Establish the Git-managed registry as a directory structure at the repo root (`registry/`) containing two types of capabilities: Claude Code skills (directory-per-skill with `SKILL.md`) and MCP server definitions (flat YAML files). Seed it with real examples copied from the project.

Add Pydantic validation models inside the existing server package (`awos_recruitment_mcp`) to define the schemas for both capability types. Build a CLI validation module (`awos_recruitment_mcp.validate`) that scans the registry, validates all entries against these models, and reports errors in human-readable or JSON format.

A `justfile` at the repo root wraps the validation command for convenience and CI integration.

---

## 2. Proposed Solution & Implementation Plan (The "How")

### 2.1 Registry Directory Structure

```
registry/
├── skills/
│   ├── python/
│   │   ├── SKILL.md
│   │   └── references/
│   │       ├── modern-syntax.md
│   │       ├── type-hints.md
│   │       ├── patterns.md
│   │       └── project-structure.md
│   └── typescript/
│       ├── SKILL.md
│       └── references/
│           ├── type-system.md
│           ├── patterns.md
│           └── project-structure.md
└── mcp/
    ├── context7.yaml
    └── playwright.yaml
```

Skills are copied as-is from `.claude/skills/python/` and `.claude/skills/typescript/` with their full directory structure. The existing `registry/CLAUDE.md` will be removed or replaced.

### 2.2 New Dependencies

Added to `server/pyproject.toml`:

| Package | Type | Purpose |
|---|---|---|
| `python-frontmatter` | Runtime | Parse YAML front matter from SKILL.md files |
| `pyyaml` | Runtime | YAML parsing for MCP definition files (also a dependency of python-frontmatter) |

### 2.3 Data Models

New Pydantic models in `server/src/awos_recruitment_mcp/models/`:

**`skill_metadata.py` — SkillMetadata**

Validates the YAML front matter of a SKILL.md file.

| Field | Type | Required | Constraints |
|---|---|---|---|
| `name` | `str` | Yes | Lowercase letters, numbers, hyphens only. Max 64 chars. Pattern: `^[a-z0-9-]{1,64}$` |
| `description` | `str` | Yes | Non-empty string |
| `version` | `str` | No | Semver string (existing skills use this field) |
| `argument-hint` | `str` | No | — |
| `disable-model-invocation` | `bool` | No | Default: false |
| `user-invocable` | `bool` | No | Default: true |
| `allowed-tools` | `str` | No | Comma-separated tool names |
| `model` | `str` | No | — |
| `context` | `str` | No | Must be `"fork"` if present |
| `agent` | `str` | No | — |
| `hooks` | `dict` | No | — |

The model uses `model_config = ConfigDict(extra="forbid")` to reject unknown fields. Field names with hyphens use Pydantic aliases (e.g., `argument_hint: str | None = Field(None, alias="argument-hint")`).

**`mcp_definition.py` — McpDefinition**

Validates a complete MCP YAML file.

| Field | Type | Required | Constraints |
|---|---|---|---|
| `name` | `str` | Yes | Non-empty string |
| `description` | `str` | Yes | Non-empty string |
| `config` | `dict[str, McpServerConfig]` | Yes | Exactly one key (the server identifier) |

**`McpServerConfig` (nested model):**

| Field | Type | Required | Constraints |
|---|---|---|---|
| `type` | `str` | Yes | One of: `"stdio"`, `"sse"`, `"http"`, `"websocket"` |
| `command` | `str` | No | — |
| `args` | `list[str]` | No | — |
| `env` | `dict[str, str]` | No | — |
| `url` | `str` | No | — |

Uses `model_config = ConfigDict(extra="allow")` since MCP server configs may have additional transport-specific fields.

### 2.4 Validation CLI Module

New module at `server/src/awos_recruitment_mcp/validate/`:

```
validate/
├── __init__.py       # Core validation logic (scan, parse, validate, report)
└── __main__.py       # CLI entry point (argparse, format flag, exit codes)
```

**Invocation:** `uv run python -m awos_recruitment_mcp.validate [--format human|json] [--registry-path PATH]`

- `--format`: Output format. `human` (default) or `json`.
- `--registry-path`: Path to the registry directory. Defaults to `../registry` (relative to the server directory, i.e., the repo root `registry/`).

**Validation logic:**

1. Scan `registry/skills/` — find all subdirectories containing a `SKILL.md`.
2. For each skill: parse front matter with `python-frontmatter`, validate against `SkillMetadata`, check that the markdown body is non-empty.
3. Flag directories under `registry/skills/` that are missing `SKILL.md`.
4. Scan `registry/mcp/` — find all `.yaml` files.
5. For each MCP definition: parse with `pyyaml`, validate against `McpDefinition`.
6. Collect all errors. Report in the requested format. Exit 0 on success, exit 1 on any failure.

**Human output format:**
```
FAIL  registry/skills/broken-skill/SKILL.md
  - Missing required field: description
  - Field 'name' contains invalid characters: "My Skill!"

OK    registry/skills/python/SKILL.md
OK    registry/mcp/context7.yaml

1 error in 1 file. Validation failed.
```

**JSON output format:**
```json
{
  "valid": false,
  "errors": [
    {
      "file": "registry/skills/broken-skill/SKILL.md",
      "field": "description",
      "message": "Missing required field: description"
    }
  ],
  "summary": { "total": 4, "passed": 3, "failed": 1 }
}
```

### 2.5 MCP Definition Examples

**`registry/mcp/context7.yaml`:**

```yaml
name: "Context7"
description: "Retrieves up-to-date documentation and code examples for any library using the Context7 documentation service."
config:
  context7:
    type: stdio
    command: npx
    args:
      - -y
      - "@upstash/context7-mcp@latest"
```

**`registry/mcp/playwright.yaml`:**

```yaml
name: "Playwright"
description: "Browser automation via Playwright. Enables web scraping, testing, and interaction with web pages through a headless browser."
config:
  playwright:
    type: stdio
    command: npx
    args:
      - -y
      - "@anthropic/playwright-mcp@latest"
```

### 2.6 Justfile

New file at repo root: `justfile`

```just
# Validate all registry entries against their schemas
validate-registry *ARGS:
    cd server && uv run python -m awos_recruitment_mcp.validate {{ARGS}}
```

Note: All `uv` commands run from `server/` since that's where `pyproject.toml` lives.

---

## 3. Impact and Risk Analysis

### System Dependencies

- The validation models (`SkillMetadata`, `McpDefinition`, `McpServerConfig`) are added to the server's `models/` package. They are available for reuse when the server needs to load registry entries at runtime in Phase 2.
- Two new runtime dependencies (`python-frontmatter`, `pyyaml`) are added to the server package.

### Potential Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Claude Code changes the SKILL.md schema in future versions | Validation may reject valid fields or accept invalid ones | Use `extra="forbid"` to catch unknown fields early; update the model when the upstream schema changes |
| `python-frontmatter` parsing edge cases (malformed YAML, missing delimiters) | Validation crashes instead of reporting an error | Wrap parsing in try/except, report parse errors as validation failures |
| Registry path assumption (`../registry`) breaks in CI | Validation can't find the registry | Provide `--registry-path` flag for explicit path override |
| Existing skills use `version` field not in official Claude Code schema | Would be rejected by strict validation | Include `version` as an optional field in `SkillMetadata` |

---

## 4. Testing Strategy

- **Framework:** pytest + pytest-asyncio (existing setup in `server/tests/`)
- **New test file:** `server/tests/test_validate.py`

| Test | Type | Validates |
|---|---|---|
| Valid skill SKILL.md passes validation | Unit | SkillMetadata model accepts correct front matter |
| Skill with missing `name` fails validation | Unit | Required field enforcement |
| Skill with invalid `name` (uppercase, spaces) fails | Unit | Name pattern constraint |
| Skill with unknown front matter field fails | Unit | `extra="forbid"` rejects unexpected fields |
| Skill with empty markdown body fails | Unit | Body non-empty check |
| Valid MCP YAML passes validation | Unit | McpDefinition model accepts correct structure |
| MCP YAML with missing `config` fails | Unit | Required field enforcement |
| MCP YAML with multiple config keys fails | Unit | Exactly-one-key constraint |
| Full registry scan finds all entries | Integration | Scanner discovers skills and MCP files correctly |
| Human output format matches expected structure | Integration | Output formatting |
| JSON output format is valid JSON with correct shape | Integration | Output formatting |
| Exit code is 0 for valid registry, 1 for invalid | Integration | CI compatibility |
| All example entries in `registry/` pass validation | Smoke | Seed data is correct |
