# Technical Specification: Agent Support

- **Functional Specification:** `context/spec/005-agent-support/functional-spec.md`
- **Status:** Completed
- **Author(s):** Technical Architect

---

## 1. High-Level Technical Approach

This feature extends the existing capability pipeline to support **agents** as a third capability type alongside skills and MCP servers. The implementation follows established patterns in both the Python server and TypeScript CLI, keeping new abstractions to a minimum.

**Server (Python):** A new `registry/agents/` catalog of `.md` files (YAML frontmatter + system prompt body) is loaded by the registry, indexed in ChromaDB, validated in CI, and bundled via a new endpoint. The search index and search tool require zero changes — agents flow through naturally once loaded.

**CLI (TypeScript):** A new `agent` subcommand downloads agent bundles, installs `.md` files to `.claude/agents/`, parses frontmatter to extract referenced skills, and auto-installs missing skills via the existing skill bundle flow. Shared install logic is extracted from the existing skill command to enable reuse without side effects.

---

## 2. Proposed Solution & Implementation Plan (The "How")

### 2.1. Registry Catalog Structure

New directory in the Git-managed registry:

```
registry/
├── skills/<name>/SKILL.md          (existing)
├── mcp/<name>.yaml                 (existing)
└── agents/<name>.md                (new)
```

Each agent is a single markdown file with YAML frontmatter:

| Field | Required | Type | Constraints |
|-------|----------|------|-------------|
| `name` | Yes | string | Kebab-case, 1–64 chars (`^[a-z0-9-]{1,64}$`) |
| `description` | Yes | string | Non-empty (min_length=1) |
| `model` | No | string | Any non-empty string |
| `skills` | No | list[string] | Each entry must be kebab-case |

The markdown body (after frontmatter) contains the agent's system prompt.

### 2.2. Server: Data Model

**New file:** `server/src/awos_recruitment_mcp/models/agent_metadata.py`

- Pydantic `BaseModel` named `AgentMetadata`
- `model_config = ConfigDict(extra="forbid")` — strict, consistent with `SkillMetadata`
- Fields: `name` (required, regex-validated), `description` (required, min_length=1), `model` (optional string), `skills` (optional list of kebab-case strings)

**Modified file:** `server/src/awos_recruitment_mcp/models/capability.py`

- Expand `RegistryCapability.type` from `Literal["skill", "tool"]` to `Literal["skill", "tool", "agent"]`

### 2.3. Server: Registry Loader

**Modified file:** `server/src/awos_recruitment_mcp/registry.py`

**New function `_load_agents(root: Path)`:** Follows the `_load_skills` pattern:
1. Scan `root / "agents"` for `*.md` files (sorted)
2. Parse each with `frontmatter.load()` to extract YAML metadata
3. Extract `name` and `description`; skip entries with missing or empty values
4. Return `RegistryCapability(name=..., description=..., type="agent")`

**New function `resolve_agent_paths(names, registry_path)`:** Follows the `resolve_mcp_paths` pattern:
- For each name, check if `agents/<name>.md` exists
- Return `(found_paths, not_found_names)` tuple

**Modified function `load_registry()`:** Add `capabilities.extend(_load_agents(root))`

### 2.4. Server: Bundle Endpoint

**Modified file:** `server/src/awos_recruitment_mcp/server.py`

**New route `POST /bundle/agents`:** Follows the existing `/bundle/mcp` pattern:
1. Parse and validate `BundleRequest` (1–20 kebab-case names)
2. Deduplicate names
3. Resolve via `resolve_agent_paths()`
4. Build tar.gz archive with each agent's `.md` file (arcname: `<name>.md`)
5. Return `Response(content=..., media_type="application/gzip")`

### 2.5. Server: Validation

**Modified file:** `server/src/awos_recruitment_mcp/validate/__init__.py`

**New function `validate_agents(registry_path)`:** Follows the `validate_mcp_definitions` pattern:
1. Scan `registry_path / "agents"` for `*.md` files
2. Parse frontmatter with `frontmatter.load()`
3. Validate metadata against `AgentMetadata.model_validate()`
4. Extra check: filename stem must match `name` field
5. Extra check: markdown body (system prompt) must be non-empty
6. **Cross-validation:** For each entry in the `skills` list, verify that `registry_path / "skills" / skill_name` exists as a directory. Missing references produce a validation error that blocks the merge.

**Modified function `validate_registry()`:** Add `results.extend(validate_agents(registry_path))`

### 2.6. Server: Search (No Changes)

- `search_index.py` — agents flow through naturally as `RegistryCapability` objects. No code changes.
- `tools/search.py` — already accepts `type="agent"` in `VALID_TYPES`. No code changes.

### 2.7. CLI: Command Registration

**Modified file:** `cli/src/cli.ts`
- Add `"agent"` to the subcommand guard condition
- Add `"agent"` to the `USAGE` string
- Add `case "agent":` to the switch statement, calling `installAgents(names)`

### 2.8. CLI: Shared Logic Extraction

**Modified file:** `cli/src/commands/skill.ts`

Extract the file-copy and conflict-detection logic into a reusable function:

- `processSkills(tempDir: string, requestedNames: string[]): InstallResult[]` — handles directory existence checks, `fs.cpSync`, and result tracking. No `process.exit` or print side effects.
- The existing `installSkills` function calls `processSkills` internally, preserving its current behavior.

**New file:** `cli/src/lib/frontmatter.ts`

Small utility (~15 lines) using the existing `yaml` package:
- `parseFrontmatter(content: string): Record<string, unknown> | null` — extracts YAML block between `---` delimiters, parses with `YAML.parse()`, returns the parsed object or `null` if no frontmatter found.

**Modified file:** `cli/src/lib/types.ts`

Add `AgentFrontmatter` interface:
- `name: string`, `description: string`, `model?: string`, `skills?: string[]`

### 2.9. CLI: Agent Install Command

**New file:** `cli/src/commands/agent.ts`

`installAgents(names: string[])` — two-phase install:

**Phase 1 — Install agents:**
1. Call `downloadBundle(serverUrl + "/bundle/agents", names)` to get extracted temp directory
2. Read extracted `.md` files, map filenames (strip `.md`) to a set of found names
3. For each requested name:
   - If not found in archive: record as `"not-found"`
   - If `.claude/agents/<name>.md` already exists: record as `"skipped"` (silent, no error)
   - Otherwise: copy file to `.claude/agents/<name>.md`, record as `"installed"`
4. Create `.claude/agents/` directory if it doesn't exist (`fs.mkdirSync` with `recursive: true`)

**Phase 2 — Auto-install referenced skills:**
1. For each newly installed agent file, parse frontmatter and collect all unique skill names from `skills` fields
2. Filter out skills that already exist in `.claude/skills/`
3. If any missing skills remain, call `downloadBundle(serverUrl + "/bundle/skills", missingSkillNames)` and then `processSkills(tempDir, missingSkillNames)`
4. Merge skill install results into the overall summary

**Output:** Print a combined summary:
- Agents: installed / skipped (already exist) / not found
- Skills: auto-installed / skipped (already exist) / not found

**Exit code:** `process.exit(1)` only if any agent or skill has `"not-found"` status. Skipped items are not errors.

---

## 3. Impact and Risk Analysis

### System Dependencies

- **Search index:** No changes. Agents are indexed identically to skills and MCP servers.
- **Search tool:** No changes. Already accepts `type="agent"`.
- **Existing skill command:** Refactored to extract `processSkills`, but external behavior is unchanged.
- **Bundle infrastructure:** New endpoint follows identical patterns; no changes to shared code (e.g., `BundleRequest` model).

### Potential Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Skill cross-validation creates ordering dependency (agents can't be added before their skills) | Document that skills must be added to the registry before agents that reference them. CI will enforce this. |
| Frontmatter parsing edge cases (malformed YAML, missing delimiters) | The `parseFrontmatter` utility returns `null` for unparseable content. Agent install treats unparseable agents as installed-but-no-skills (graceful degradation). |
| Extracting `processSkills` from `skill.ts` could break existing behavior | Existing `installSkills` tests will catch regressions. The refactor is internal only — no API changes. |
| Auto skill install makes a second HTTP request to the server | Only occurs when referenced skills are missing. The request is identical to a manual `skill` install. No performance concern for typical usage (1–5 skills per agent). |

---

## 4. Testing Strategy

### Server (Python — pytest)

| Area | Test File | Tests |
|------|-----------|-------|
| `AgentMetadata` model | `test_validate.py` | Valid metadata, missing name, empty description, invalid name format, extra fields rejected, optional fields |
| `_load_agents()` | `test_registry.py` | Correct parsing, skip without description, type inference (`type="agent"`), mixed types with skills/tools |
| `validate_agents()` | `test_validate.py` | Valid agent passes, invalid metadata fails, filename-name mismatch fails, empty body fails, missing skill reference fails cross-validation |
| `/bundle/agents` | `test_bundle.py` | Valid request returns tar.gz, partial matches, all not-found, empty names (400), too many names (400), invalid name (400) |
| Search integration | `test_search_index.py`, `test_search_tool.py` | Agent appears in search results, `type="agent"` filter works |
| Real registry | `test_registry.py`, `test_validate.py` | Smoke tests updated to include agent count |

### CLI (TypeScript — vitest)

| Area | Test File | Tests |
|------|-----------|-------|
| Agent install (Phase 1) | `commands/__tests__/agent.test.ts` | Successful install, skip existing, not found, mixed results, `.claude/agents/` directory creation |
| Auto skill install (Phase 2) | `commands/__tests__/agent.test.ts` | Skills auto-installed, existing skills skipped, all skills already present, no skills referenced, skill not found in registry |
| Frontmatter parser | `lib/__tests__/frontmatter.test.ts` | Valid frontmatter, no frontmatter, malformed YAML, empty skills list |
| `processSkills` extraction | `commands/__tests__/skill.test.ts` | Existing tests continue to pass after refactor |

---

## Files Changed Summary

| File | Action |
|------|--------|
| `registry/agents/` | **Create** directory |
| `server/src/awos_recruitment_mcp/models/agent_metadata.py` | **Create** |
| `server/src/awos_recruitment_mcp/models/capability.py` | Modify — expand type literal |
| `server/src/awos_recruitment_mcp/models/__init__.py` | Modify — export `AgentMetadata` |
| `server/src/awos_recruitment_mcp/registry.py` | Modify — add `_load_agents()`, `resolve_agent_paths()` |
| `server/src/awos_recruitment_mcp/validate/__init__.py` | Modify — add `validate_agents()` with cross-validation |
| `server/src/awos_recruitment_mcp/server.py` | Modify — add `/bundle/agents` route |
| `cli/src/cli.ts` | Modify — add `"agent"` subcommand |
| `cli/src/commands/agent.ts` | **Create** |
| `cli/src/commands/skill.ts` | Modify — extract `processSkills()` |
| `cli/src/lib/frontmatter.ts` | **Create** |
| `cli/src/lib/types.ts` | Modify — add `AgentFrontmatter` |
| Server tests (5 files) | Modify — add agent test cases |
| CLI tests (3 files) | **Create** / Modify |
