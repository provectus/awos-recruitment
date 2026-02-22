# Functional Specification: Capability Installation

- **Roadmap Item:** Install discovered skills and MCP server definitions via an npx CLI package.
- **Status:** Completed
- **Author:** Poe

---

## 1. Overview and Rationale (The "Why")

Today, the AWOS Recruitment server allows developers to discover skills and MCP tools through semantic search. However, after finding the right capability, there is no automated way to install it. The developer must manually copy files into their project configuration — defeating the product's core promise of zero-friction adoption.

**Capability Installation** closes this gap. It provides a standalone npx CLI that fetches discovered capabilities from the AWOS server and installs them directly into the developer's project. This completes the discovery-to-usage loop: search, select, install, use — all without leaving the editor or managing files manually.

**Success looks like:**
- A developer can go from search result to installed, working capability in a single command.
- Teams achieve consistent tooling setups across projects because installation is repeatable and deterministic.
- New team members can bootstrap their project's AI tooling in seconds.

---

## 2. Functional Requirements (The "What")

### 2.1 Skill Installation

- **As a** developer, **I want to** install a discovered skill into my project via a single CLI command, **so that** I can immediately use it in Claude Code without manually copying files.
  - **Acceptance Criteria:**
    - [x] Running `npx <package> skill <skill-name>` installs the skill's `SKILL.md` (and any reference files) into the project's `.claude/skills/<skill-name>/` directory.
    - [x] The CLI fetches the skill content from the AWOS Recruitment server (not from Git directly).
    - [x] On success, the CLI prints: `Installed skill '<skill-name>' to .claude/skills/<skill-name>/SKILL.md`
    - [x] The installed skill is immediately available in Claude Code without any further configuration.

### 2.2 MCP Tool Installation

- **As a** developer, **I want to** install a discovered MCP server definition into my project via a single CLI command, **so that** my AI assistant can connect to the tool without manual `.mcp.json` editing.
  - **Acceptance Criteria:**
    - [x] Running `npx <package> mcp <tool-name>` adds the MCP server's configuration to the project's `.mcp.json` file.
    - [x] The CLI fetches the MCP definition from the AWOS Recruitment server.
    - [x] If `.mcp.json` does not exist, the CLI creates it with the installed server definition.
    - [x] If `.mcp.json` already exists, the CLI merges the new server entry into the existing `mcpServers` object.
    - [x] On success, the CLI prints: `Installed MCP server '<tool-name>' to .mcp.json`

### 2.3 Multiple Capabilities in One Command

- **As a** developer, **I want to** install multiple capabilities in a single command, **so that** I can bootstrap my project quickly.
  - **Acceptance Criteria:**
    - [x] The CLI accepts multiple names: `npx <package> skill <name1> <name2> ...` and `npx <package> mcp <name1> <name2> ...`
    - [x] The CLI requests all capabilities from the server in a single bundled download (tar.gz), then unpacks and installs each one locally.
    - [x] Each capability is installed independently — a failure on one does not block the others.
    - [x] After all installs complete, the CLI prints a summary showing which succeeded and which failed.

### 2.4 Conflict Handling

- **As a** developer, **I want** the CLI to refuse to overwrite existing capabilities, **so that** I don't accidentally lose local customizations.
  - **Acceptance Criteria:**
    - [x] If a skill directory `.claude/skills/<skill-name>/` already exists, the CLI skips it and prints an error: `Error: skill '<skill-name>' already exists. Remove it first to reinstall.`
    - [x] If an MCP server key already exists in `.mcp.json`, the CLI skips it and prints an error: `Error: MCP server '<tool-name>' already exists in .mcp.json. Remove it first to reinstall.`
    - [x] In a multi-install command, conflicts on individual items are reported in the final summary but do not prevent other items from installing.

### 2.5 Error Handling

- The CLI must handle the following error cases gracefully:
  - **Acceptance Criteria:**
    - [x] If the AWOS server is unreachable, the CLI prints: `Error: could not connect to AWOS server at <url>.`
    - [x] If a requested capability name does not exist on the server, the CLI prints: `Error: capability '<name>' not found.`
    - [x] If the server returns an invalid or corrupt bundle, the CLI prints: `Error: failed to unpack server response.`
    - [x] All errors exit with a non-zero exit code.

### 2.6 Server-Side: Bundle Download Endpoint

- The AWOS server must expose a new HTTP endpoint that returns a tar.gz archive containing the requested capabilities.
  - **Acceptance Criteria:**
    - [x] The endpoint accepts a list of capability names and returns a single `.tar.gz` file containing all matching capabilities.
    - [x] Skills are included as their full directory (e.g., `skills/<name>/SKILL.md` plus any `references/` files).
    - [x] MCP definitions are included as their YAML files (e.g., `mcp/<name>.yaml`).
    - [x] If a requested name is not found, it is omitted from the archive and reported in a response header or metadata file inside the archive.

---

## 3. Scope and Boundaries

### In-Scope

- A standalone npx CLI package with `skill` and `mcp` subcommands.
- Fetching capability content from the AWOS Recruitment server via a new bundle HTTP endpoint.
- Installing skills into the project's `.claude/skills/` directory.
- Installing MCP definitions into the project's `.mcp.json` file.
- Creating `.mcp.json` if it doesn't exist.
- Multi-capability install with best-effort semantics and summary reporting.
- Conflict detection (refuse to overwrite existing capabilities).
- Clear error messages for server errors, missing capabilities, and conflicts.

### Out-of-Scope

- **Usage Telemetry** — tracking installs is a separate Phase 3 roadmap item.
- **Analytics & Reporting** — aggregating install data is a separate Phase 3 roadmap item.
- **User-level / global installation** — skills install to the project's `.claude/` directory only; `~/.claude/` is not supported in this version.
- **Uninstall command** — removing capabilities is manual (delete the files/entries).
- **Version management** — there is no capability versioning or update flow in this version.
- **Authentication** — the server does not require auth; the CLI makes unauthenticated requests.
- **Offline / cached mode** — the CLI always fetches fresh from the server.
