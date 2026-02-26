# Functional Specification: Agent Support

- **Roadmap Item:** Support agents in the registry and installer — index and serve agent definitions with structured metadata, and install discovered agents into the user's Claude Code configuration.
- **Status:** Completed
- **Author:** Poe (Product Analyst)

---

## 1. Overview and Rationale (The "Why")

The AWOS Recruitment system already enables teams to centrally manage and distribute **skills** and **MCP server definitions** through a full pipeline: a Git-managed registry, semantic search, server-side bundling, and CLI installation. However, **agents** — autonomous sub-agents with specialized expertise, system prompts, and skill bindings — are not yet part of this pipeline.

Without agent support, each developer must manually create or copy agent definition files. This leads to inconsistent agent configurations across the team, duplicated effort, and no way for a tech lead to curate and distribute a standard set of agents the way they already do for skills and MCP servers.

This feature closes that gap by extending the existing capability pipeline to support agents as a first-class capability type — discoverable via semantic search, installable via the CLI, and validated in CI like all other registry entries.

**Success looks like:** A developer can search for agents (e.g., "TypeScript expert"), discover one in the registry, install it with a single CLI command, and have both the agent and all its referenced skills ready to use — with zero manual file management.

---

## 2. Functional Requirements (The "What")

### 2.1. Agent Registry & Indexing

- The Git-managed registry must support a new `registry/agents/` directory containing agent definitions.
- Each agent is a **single markdown file** at `registry/agents/<name>.md`, mirroring the Claude Code convention.
- Agent files use YAML frontmatter with the following fields:
  - `name` (required): kebab-case identifier, 1–64 characters.
  - `description` (required): non-empty string describing the agent's purpose and expertise.
  - `model` (optional): target model identifier (e.g., `opus`, `sonnet`, `haiku`).
  - `skills` (optional): list of skill names this agent references.
- The markdown body contains the agent's system prompt.
- The registry loader must scan `registry/agents/` and produce `RegistryCapability` objects with `type="agent"`.
- Agents must be embedded and indexed in the search index (ChromaDB) alongside skills and MCP servers.
- The existing `search_capabilities` MCP tool must return agents in search results using the **same result shape** as skills and MCP servers (name, description, score).
- The existing `type="agent"` filter on the search tool must return matching agents.

  **Acceptance Criteria:**
  - [x] Agent `.md` files placed in `registry/agents/` are loaded by the registry loader with `type="agent"`.
  - [x] Agents appear in semantic search results when a relevant natural language query is submitted.
  - [x] Filtering by `type="agent"` returns only agent results.
  - [x] Agents without a description are silently skipped during loading (consistent with skills).

### 2.2. Agent Metadata Validation

- An agent metadata schema must be defined and enforced.
- CI validation must block merges that introduce agent files with invalid metadata (missing or malformed name, empty description, invalid name format).
- Validation behavior must be consistent with the existing skill and MCP validation pipeline.

  **Acceptance Criteria:**
  - [x] A valid agent file (correct frontmatter, non-empty description, kebab-case name) passes CI validation.
  - [x] An agent file with a missing `name` field fails CI validation.
  - [x] An agent file with an empty `description` field fails CI validation.
  - [x] An agent file with a non-kebab-case name fails CI validation.

### 2.3. Agent Bundling

- The server must expose a new endpoint `POST /bundle/agents` that accepts a list of agent names and returns a tar.gz archive containing the corresponding agent `.md` files.
- The request body must follow the same validation rules as existing bundle endpoints (1–20 names, kebab-case pattern).
- If a requested agent is not found in the registry, it is excluded from the archive (not an error), and the CLI handles reporting.

  **Acceptance Criteria:**
  - [x] `POST /bundle/agents` with valid agent names returns a tar.gz archive containing the requested `.md` files.
  - [x] Requesting a non-existent agent name does not cause a server error; the name is simply absent from the archive.
  - [x] The request is rejected if it contains more than 20 names or names with invalid format.

### 2.4. Agent Installation via CLI

- The CLI must support a new command: `npx @provectusinc/awos-recruitment agent <name1> [name2] ...`.
- The command downloads the agent bundle from the server and installs each agent file to `.claude/agents/<name>.md`.
- **Conflict handling:** If an agent file already exists at the target path, it is **skipped silently** (no error).
- **Automatic skill installation:** After installing agents, the CLI must:
  1. Collect all skill names referenced in the `skills` frontmatter field of the newly installed agents.
  2. Skip any skills that already exist in `.claude/skills/`.
  3. Install the remaining missing skills using the existing skill bundle flow.
- The CLI must print a summary showing:
  - Agents installed.
  - Agents skipped (already exist).
  - Skills auto-installed.
  - Skills skipped (already exist).
  - Items not found in the registry.

  **Acceptance Criteria:**
  - [x] Running `npx @provectusinc/awos-recruitment agent typescript-expert` installs the agent file to `.claude/agents/typescript-expert.md`.
  - [x] If `.claude/agents/typescript-expert.md` already exists, the agent is skipped without error.
  - [x] If the installed agent references skills `[typescript, npx-package]` and `typescript` already exists locally, only `npx-package` is installed.
  - [x] If the installed agent references skills `[typescript, npx-package]` and both already exist locally, no skills are installed and the summary reflects this.
  - [x] If a requested agent name does not exist in the registry, it is reported as "not found" in the summary.
  - [x] The `.claude/agents/` directory is created if it does not already exist.

---

## 3. Scope and Boundaries

### In-Scope

- Agent catalog structure in the Git-managed registry (`registry/agents/`).
- Agent metadata schema definition and CI validation.
- Registry loader extension to scan and index agents.
- Semantic search indexing and retrieval for agents.
- Server-side bundle endpoint for agents (`POST /bundle/agents`).
- CLI `agent` command for installation.
- Automatic installation of an agent's referenced skills.
- Conflict handling (skip existing agents and skills silently).

### Out-of-Scope

- **Usage Telemetry** — tracking agent installs and usage (Phase 3 roadmap item).
- **Analytics & Reporting** — surfacing agent adoption metrics (Phase 3 roadmap item).
- Agent authoring, publishing, or update workflows (capabilities are managed directly in Git).
- Agent versioning or upgrade-in-place mechanisms.
- A web UI or dashboard for browsing agents.
- Automatic MCP server installation for agents (agents reference skills, not MCP servers).
- User authentication or multi-tenant access control.
