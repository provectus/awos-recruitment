# Functional Specification: Capability Registry & Indexing

- **Roadmap Item:** Capability Registry & Indexing — Ingest and index a Git-managed library of skills, agents, and tools with structured metadata; Define and enforce a consistent metadata schema for all registered capabilities.
- **Status:** Draft
- **Author:** AI Assistant

---

## 1. Overview and Rationale (The "Why")

Developers using AI coding assistants need access to specialized skills and tools, but today there is no centralized, structured catalog to store and organize them. Without a registry, capabilities are scattered, inconsistently formatted, and impossible to search programmatically.

This specification defines the **foundation layer** — a Git-managed directory structure with enforced metadata schemas for two types of capabilities: **Claude Code skills** and **MCP server definitions**. It also includes a validation tool for CI pipelines to ensure the registry stays consistent as new capabilities are added.

This registry is the prerequisite for Phase 2 (semantic search and indexing) — without well-structured, validated entries, there is nothing to embed or search over.

**Success looks like:**
- A clear, documented directory structure that contributors can follow to add new capabilities.
- Every entry in the registry passes schema validation.
- The validation command runs in CI and blocks merges that introduce malformed entries.

---

## 2. Functional Requirements (The "What")

### 2.1 Registry Directory Structure

The registry lives at `/registry` in the repository root with the following layout:

```
registry/
├── skills/
│   ├── my-skill-name/
│   │   ├── SKILL.md          (required — front matter + instructions)
│   │   ├── reference.md      (optional)
│   │   ├── examples.md       (optional)
│   │   └── ...               (optional supporting files)
│   └── another-skill/
│       └── SKILL.md
└── mcp/
    ├── my-server.yaml
    └── another-server.yaml
```

- **Skills** live in subdirectories under `registry/skills/`. Each skill directory must contain a `SKILL.md` file and may contain additional supporting files (reference docs, templates, scripts, etc.).
- **MCP definitions** live as flat YAML files under `registry/mcp/`.

**Acceptance Criteria:**
- [ ] `registry/skills/` directory exists and is documented as the location for skill entries.
- [ ] `registry/mcp/` directory exists and is documented as the location for MCP definition entries.
- [ ] Each skill entry is a subdirectory containing at minimum a `SKILL.md` file.
- [ ] Each MCP entry is a single `.yaml` file directly under `registry/mcp/`.

### 2.2 Skill Metadata Schema

Skills use the **existing Claude Code SKILL.md front matter schema** exactly as defined by the Claude Code platform. We do not invent custom fields. The SKILL.md file consists of YAML front matter (between `---` markers) followed by markdown content.

**Supported front matter fields (from Claude Code):**

| Field | Required for Registry | Type | Description |
|-------|----------------------|------|-------------|
| `name` | Yes | string | Lowercase letters, numbers, and hyphens. Max 64 characters. |
| `description` | Yes | string | What the skill does and when to use it. |
| `argument-hint` | No | string | Hint for expected arguments (e.g., `[filename]`). |
| `disable-model-invocation` | No | boolean | Prevent auto-loading by Claude. Default: false. |
| `user-invocable` | No | boolean | Show/hide from `/` menu. Default: true. |
| `allowed-tools` | No | string | Comma-separated list of permitted tools. |
| `model` | No | string | Model override. |
| `context` | No | string | Set to `fork` for isolated subagent execution. |
| `agent` | No | string | Subagent type when `context: fork`. |
| `hooks` | No | object | Skill-scoped hooks. |

For registry validation purposes, `name` and `description` are **required**. All other fields are optional.

**Acceptance Criteria:**
- [ ] Every SKILL.md in the registry has valid YAML front matter with at least `name` and `description` fields.
- [ ] The `name` field contains only lowercase letters, numbers, and hyphens, and is at most 64 characters.
- [ ] The `description` field is a non-empty string.
- [ ] The markdown body below the front matter is non-empty.
- [ ] No unknown or custom front matter fields are present (only the fields defined in the Claude Code skill schema are accepted).

### 2.3 MCP Definition Schema

MCP definitions use YAML files containing metadata and a JSON-compatible configuration block that can be directly merged into a `.mcp.json` file.

**Schema:**

```yaml
name: "human-readable-name"
description: "What this MCP server provides and when to use it."
config:
  server-key-name:
    type: "stdio" | "sse" | "http" | "websocket"
    command: "command-to-run"
    args:
      - "arg1"
      - "arg2"
    env:
      KEY: "value"
```

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `name` | Yes | string | Human-readable display name for the MCP server. |
| `description` | Yes | string | What the server provides and when to use it. |
| `config` | Yes | object | Full server entry object, structured exactly as it would appear in `.mcp.json`. Contains one key (the server name) with its configuration. |

The `config` block is a **complete `.mcp.json` server entry** — the key is the server identifier, and the value is the server configuration. This allows direct extraction and insertion into `.mcp.json`.

**Acceptance Criteria:**
- [ ] Every `.yaml` file in `registry/mcp/` has `name`, `description`, and `config` fields.
- [ ] The `name` field is a non-empty string.
- [ ] The `description` field is a non-empty string.
- [ ] The `config` field is an object containing exactly one key (the server identifier) whose value is a valid server configuration object.
- [ ] The server configuration within `config` contains at least a `type` field.

### 2.4 Registry Validation Command

A **Python script** validates all entries in the registry against their respective schemas. A **Just task** wraps the script for convenience.

**Behavior:**

- The script scans `registry/skills/` and `registry/mcp/` and validates every entry.
- For skills: checks SKILL.md exists, front matter is valid YAML, required fields are present, field values conform to constraints.
- For MCP definitions: checks YAML is valid, required fields are present, `config` structure is correct.
- Supports a `--format` flag:
  - `--format human` (default): Human-readable output listing each issue with file path, field, and problem.
  - `--format json`: Structured JSON output for machine parsing in CI.
- Exits with **non-zero exit code** on any validation failure.
- Exits with **zero** when all entries are valid.

**Example human output on failure:**
```
FAIL  registry/skills/broken-skill/SKILL.md
  - Missing required field: description
  - Field 'name' contains invalid characters: "My Skill!"

FAIL  registry/mcp/bad-server.yaml
  - Missing required field: config

2 errors in 2 files. Validation failed.
```

**Just task:**
```
just validate-registry                  # human-readable (default)
just validate-registry --format json    # JSON output for CI
```

**Acceptance Criteria:**
- [ ] Running `just validate-registry` executes the Python validation script against all entries in `registry/`.
- [ ] A valid registry produces zero exit code and a success message.
- [ ] An invalid registry produces non-zero exit code.
- [ ] With `--format human` (or no flag), output lists each error with file path, field name, and problem description.
- [ ] With `--format json`, output is valid JSON containing the same error information.
- [ ] The script correctly identifies: missing required fields, invalid field values, malformed YAML, missing SKILL.md files, and structural issues in MCP config blocks.

### 2.5 Example Capabilities

The registry is seeded with **2–3 real, useful** examples for each capability type. These serve as both documentation-by-example and initial registry content.

**Acceptance Criteria:**
- [ ] The registry contains at least 2 real, useful skill entries under `registry/skills/`.
- [ ] The registry contains at least 2 real, useful MCP definition entries under `registry/mcp/`.
- [ ] All example entries pass the validation command.
- [ ] Examples demonstrate different configurations (e.g., one skill with `context: fork`, one without; one MCP with `stdio` type, one with another type).

---

## 3. Scope and Boundaries

### In-Scope

- Registry directory structure (`registry/skills/`, `registry/mcp/`).
- Metadata schema for skills (reusing Claude Code SKILL.md front matter).
- Metadata schema for MCP definitions (YAML with name, description, config).
- Python validation script with human-readable and JSON output modes.
- Just task to run the validation script.
- 2–3 real example entries for each capability type.

### Out-of-Scope

- **Semantic Capability Search** — Embedding-based indexing, vector storage, and natural language query matching (Phase 2).
- **Capability Installation** — npx install flow and client-initiated discovery loop (Phase 2).
- **MCP Tool Endpoints** — Exposing search/discovery as MCP tools (Phase 2).
- **Usage Telemetry & Analytics** — Event tracking, telemetry storage, usage metrics API, capability value signals (Phase 3).
- **Project architecture awareness** — Server does not infer project context.
- **Web UI or dashboard** — No browsing interface.
- **Authentication / access control** — No multi-tenant features.
- **Capability authoring workflows** — Capabilities are managed directly in Git.
