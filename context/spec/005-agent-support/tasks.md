# Tasks: Agent Support (005)

- [x] **Slice 1: Agent model, registry loader, and search — an agent appears in search results**
  - [x] Create `AgentMetadata` Pydantic model in `server/src/awos_recruitment_mcp/models/agent_metadata.py` with `name` (required, regex-validated), `description` (required, min_length=1), `model` (optional string), `skills` (optional list of kebab-case strings). Use `ConfigDict(extra="forbid")`. Export from `models/__init__.py`. **[Agent: python-expert]**
  - [x] Expand `RegistryCapability.type` in `server/src/awos_recruitment_mcp/models/capability.py` from `Literal["skill", "tool"]` to `Literal["skill", "tool", "agent"]`. **[Agent: python-expert]**
  - [x] Add `_load_agents(root: Path)` function to `server/src/awos_recruitment_mcp/registry.py` — scan `root / "agents"` for `*.md` files, parse with `frontmatter.load()`, extract name/description, skip entries with missing or empty values, return `RegistryCapability(type="agent")`. Call from `load_registry()`. **[Agent: python-expert]**
  - [x] Create `registry/agents/` directory with at least one sample agent `.md` file (e.g., `registry/agents/test-agent.md`) containing valid YAML frontmatter (`name`, `description`, `model`, `skills` referencing existing skills) and a system prompt body. **[Agent: python-expert]**
  - [x] Write tests in `server/tests/test_registry.py`: agent correct parsing, skip without description, type inference (`type="agent"`), mixed types. Add agent to `sample_capabilities` in `test_search_index.py` and add `type="agent"` filter test. Update real registry smoke test expected count. **[Agent: python-expert]**
  - [x] Run all server tests (`pytest`) to verify agents are loaded, indexed, and searchable. Verify `type="agent"` filter returns only agents. **[Agent: qa-tester]**
  - [x] **Git commit**

- [x] **Slice 2: Agent CI validation — invalid agent files are rejected**
  - [x] Add `validate_agents(registry_path)` function to `server/src/awos_recruitment_mcp/validate/__init__.py` — scan `agents/*.md`, parse frontmatter, validate against `AgentMetadata.model_validate()`, check filename-name match, check non-empty body, cross-validate `skills` entries against `registry/skills/`. Add to `validate_registry()`. **[Agent: python-expert]**
  - [x] Write tests in `server/tests/test_validate.py`: `AgentMetadata` model tests (valid, missing name, empty description, invalid name, extra fields), `validate_agents()` tests (valid passes, invalid fails, name mismatch fails, empty body fails, missing skill reference fails cross-validation). Update real registry smoke test. **[Agent: python-expert]**
  - [x] Run all server tests (`pytest`) including validation tests. Verify that the real registry passes validation with the sample agent file. **[Agent: qa-tester]**
  - [x] **Git commit**

- [x] **Slice 3: Agent bundle endpoint — server can serve agent files as tar.gz**
  - [x] Add `resolve_agent_paths(names, registry_path)` function to `server/src/awos_recruitment_mcp/registry.py` — for each name, check if `agents/<name>.md` exists, return `(found_paths, not_found_names)`. **[Agent: python-expert]**
  - [x] Add `POST /bundle/agents` route to `server/src/awos_recruitment_mcp/server.py` — parse `BundleRequest`, deduplicate, resolve via `resolve_agent_paths()`, build tar.gz with `.md` files, return gzip response. **[Agent: python-expert]**
  - [x] Write tests in `server/tests/test_bundle.py`: valid request returns tar.gz with correct `.md` files, partial matches, all not-found returns empty archive, empty names returns 400, too many names returns 400, invalid name pattern returns 400. **[Agent: python-expert]**
  - [x] Run all server tests (`pytest`) to verify the bundle endpoint works. **[Agent: qa-tester]**
  - [x] **Git commit**

- [x] **Slice 4: Extract shared skill install logic — refactor without behavior change**
  - [x] Extract `processSkills(tempDir: string, requestedNames: string[]): InstallResult[]` from `cli/src/commands/skill.ts` — handles directory existence checks, `fs.cpSync`, and result tracking with no `process.exit` or print side effects. The existing `installSkills` calls `processSkills` internally, preserving current behavior. Export `processSkills`. **[Agent: typescript-expert]**
  - [x] Run existing CLI tests (`vitest`) to verify the skill command still works identically after refactor. **[Agent: qa-tester]**
  - [x] **Git commit**

- [x] **Slice 5: CLI agent install (Phase 1) — agents are installed without auto-skill**
  - [x] Create `cli/src/lib/frontmatter.ts` — `parseFrontmatter(content: string): Record<string, unknown> | null` utility using the existing `yaml` package. Extracts YAML block between `---` delimiters, returns parsed object or `null`. **[Agent: typescript-expert]**
  - [x] Add `AgentFrontmatter` interface to `cli/src/lib/types.ts` — `name: string`, `description: string`, `model?: string`, `skills?: string[]`. **[Agent: typescript-expert]**
  - [x] Create `cli/src/commands/agent.ts` with `installAgents(names: string[])` — Phase 1 only: download bundle from `/bundle/agents`, extract `.md` files, copy to `.claude/agents/<name>.md`, skip existing silently, create `.claude/agents/` directory if needed, print summary, exit(1) only on not-found. **[Agent: typescript-expert]**
  - [x] Register `agent` subcommand in `cli/src/cli.ts` — add to guard condition, USAGE string, and switch statement. **[Agent: typescript-expert]**
  - [x] Write tests: `cli/src/lib/__tests__/frontmatter.test.ts` (valid frontmatter, no frontmatter, malformed YAML, empty skills) and `cli/src/commands/__tests__/agent.test.ts` (successful install, skip existing, not found, mixed results, directory creation). **[Agent: typescript-expert]**
  - [x] Run all CLI tests (`vitest`) to verify agent install works. **[Agent: qa-tester]**
  - [x] **Git commit**

- [x] **Slice 6: CLI agent install (Phase 2) — auto-install referenced skills**
  - [x] Add Phase 2 logic to `installAgents` in `cli/src/commands/agent.ts` — after installing agents, parse frontmatter of each newly installed agent, collect unique skill names, filter out skills that already exist in `.claude/skills/`, call `downloadBundle` + `processSkills` for missing skills, merge skill results into combined summary. **[Agent: typescript-expert]**
  - [x] Write tests in `cli/src/commands/__tests__/agent.test.ts`: skills auto-installed from frontmatter, existing skills skipped, all skills already present (no HTTP call), no skills referenced in frontmatter, referenced skill not found in registry. **[Agent: typescript-expert]**
  - [x] Run all CLI tests (`vitest`) to verify the full two-phase install flow. **[Agent: qa-tester]**
  - [x] **Git commit**
