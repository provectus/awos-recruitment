# Tasks: Capability Registry & Indexing

---

## Slice 1: Registry Structure + Seed Data

- [x] **Slice 1: Registry directory structure with example capabilities**
  - [x] Create `registry/skills/` and `registry/mcp/` directories. Remove or replace the existing `registry/CLAUDE.md`. **[Agent: general-purpose]**
  - [x] Copy `.claude/skills/python/` to `registry/skills/python/` (SKILL.md + all reference files). Copy `.claude/skills/typescript/` to `registry/skills/typescript/` (SKILL.md + all reference files). **[Agent: general-purpose]**
  - [x] Create `registry/mcp/context7.yaml` with name, description, and stdio config for `@upstash/context7-mcp@latest`. Create `registry/mcp/playwright.yaml` with name, description, and stdio config for `@anthropic/playwright-mcp@latest`. **[Agent: general-purpose]**
  - [x] Verify: `registry/skills/python/SKILL.md` and `registry/skills/typescript/SKILL.md` exist with valid YAML front matter containing `name` and `description`. `registry/mcp/context7.yaml` and `registry/mcp/playwright.yaml` exist and contain `name`, `description`, and `config` fields. **[Agent: qa-tester]**
  - [x] Git commit. **[Agent: general-purpose]**

---

## Slice 2: Skill Validation Models + CLI (Human Output) + Justfile

- [ ] **Slice 2: Skill schema validation with human-readable CLI output**
  - [ ] Add `python-frontmatter` and `pyyaml` as runtime dependencies in `server/pyproject.toml`. Run `uv lock` to update the lock file. **[Agent: python-expert]**
  - [ ] Create `server/src/awos_recruitment_mcp/models/skill_metadata.py` — `SkillMetadata` Pydantic model with `extra="forbid"`, required `name` (pattern-validated) and `description`, optional fields with hyphen aliases (`argument-hint`, `disable-model-invocation`, `user-invocable`, etc.), and optional `version` field. Export from `models/__init__.py`. **[Agent: python-expert]**
  - [ ] Create `server/src/awos_recruitment_mcp/validate/__init__.py` — core validation logic: scan `registry/skills/` for subdirectories, parse SKILL.md front matter with `python-frontmatter`, validate against `SkillMetadata`, check non-empty markdown body, collect errors. **[Agent: python-expert]**
  - [ ] Create `server/src/awos_recruitment_mcp/validate/__main__.py` — CLI entry point with `argparse`: `--format human` (default), `--registry-path` (default `../registry`). Human output lists PASS/FAIL per file with error details. Exit code 0 on success, 1 on failure. **[Agent: python-expert]**
  - [ ] Create `justfile` at repo root with `validate-registry` task: `cd server && uv run python -m awos_recruitment_mcp.validate {{ARGS}}`. **[Agent: general-purpose]**
  - [ ] Write unit tests in `server/tests/test_validate.py`: valid skill passes, missing `name` fails, invalid `name` chars fails, unknown field fails, empty body fails. **[Agent: python-expert]**
  - [ ] Run `just validate-registry` against the real registry. Verify exit code 0 and human-readable output shows all skills passing. Run `pytest` to verify all tests (existing + new) pass. **[Agent: qa-tester]**
  - [ ] Git commit. **[Agent: general-purpose]**

---

## Slice 3: MCP Validation + JSON Output + Full Test Suite

- [ ] **Slice 3: MCP definition validation + JSON output format**
  - [ ] Create `server/src/awos_recruitment_mcp/models/mcp_definition.py` — `McpServerConfig` (with `extra="allow"`, required `type` field) and `McpDefinition` (required `name`, `description`, `config` with exactly-one-key validator). Export from `models/__init__.py`. **[Agent: python-expert]**
  - [ ] Extend validation logic in `validate/__init__.py` to scan `registry/mcp/` for `.yaml` files, parse with `pyyaml`, validate against `McpDefinition`. **[Agent: python-expert]**
  - [ ] Add `--format json` support to `validate/__main__.py` — output valid JSON with `valid`, `errors` array (each with `file`, `field`, `message`), and `summary` object (`total`, `passed`, `failed`). **[Agent: python-expert]**
  - [ ] Write unit tests: valid MCP YAML passes, missing `config` fails, multiple config keys fails, missing `type` in server config fails. Write integration tests: JSON output is valid JSON with correct shape, exit code 0 for valid registry / 1 for invalid, full registry scan discovers all entries. Add smoke test: all example entries in `registry/` pass validation. **[Agent: python-expert]**
  - [ ] Run `just validate-registry` and `just validate-registry --format json` against the real registry. Verify both produce correct output and exit code 0. Run full `pytest` suite to verify all tests pass. **[Agent: qa-tester]**
  - [ ] Git commit. **[Agent: general-purpose]**
