# Product Definition: AWOS Recruitment

- **Version:** 1.0
- **Status:** Proposed

---

## 1. The Big Picture (The "Why")

### 1.1. Project Vision & Purpose

To provide AI coding assistants with a zero-setup, intelligent discovery engine that dynamically matches the right skills, agents, and tools to the developer's specific needs — eliminating local dependency management, ensuring consistent AI tooling across distributed teams, and providing critical visibility into which AI capabilities are actually driving value in the real world.

### 1.2. Target Audience

Software developers and engineering teams working with AI coding assistants (such as Claude Code) who need to discover and leverage specialized development skills, agents, and tools without manual setup or dependency management.

### 1.3. User Personas

- **Persona 1: "Alex the Tech Lead"**
  - **Role:** Tech lead at a mid-size startup, managing a team of 6 engineers all using Claude Code.
  - **Goal:** Ensure the whole team has consistent access to the best AI skills for their stack (e.g., React, PostgreSQL, Kubernetes) without each developer manually configuring plugins.
  - **Frustration:** Every developer has a different local setup. New hires waste time figuring out which plugins to install. There's no visibility into which AI tools the team actually uses or finds valuable.

### 1.4. Success Metrics

- **Discovery latency:** Developers find the right skill/agent for their task in under 2 seconds via semantic search.
- **Zero-setup onboarding:** A new developer on a team can connect to the recruitment server and have full access to the team's curated AI tooling with zero local configuration.
- **Adoption consistency:** 90%+ of a team's developers are using the same recommended skill set for their stack.
- **Telemetry visibility:** Team leads can see which AI skills are being used, how often, and by whom — enabling data-driven decisions about which skills to invest in.

---

## 2. The Product Experience (The "What")

### 2.1. Core Features

- **Semantic Capability Search** — Query the registry using natural language (e.g., "PostgreSQL migration agent") and get ranked, relevant results via embedding-based matching.
- **Capability Registry & Indexing** — A centralized, Git-managed catalog of skills, agents, and tools with rich metadata (stack compatibility, maturity, author, description).
- **Client-Initiated Discovery** — All discovery is driven by the client's search queries; the server has no knowledge of project architecture and simply returns the best matches for the query.
- **Capability Installation** — Install discovered capabilities directly via an npx package, enabling zero-friction adoption.
- **Usage Telemetry & Analytics** — Track which capabilities are discovered, installed, and actively used to provide visibility into real-world value.
- **MCP Protocol Integration** — Expose all functionality as an MCP server so any compatible AI assistant can connect natively with zero custom integration.

### 2.2. User Journey

A developer using Claude Code encounters a task that requires specialized tooling. Their AI assistant formulates a search query and sends it to the AWOS Recruitment server via MCP. The server performs a semantic search against its registry and returns the top-matching skills ranked by relevance and quality. The assistant presents these to the developer, who selects and activates the best match. The capability is installed via npx, the usage is logged for telemetry, and the developer completes their task with the right AI skill — all without leaving their editor or managing dependencies manually.

---

## 3. Project Boundaries

### 3.1. What's In-Scope for this Version

- MCP server exposing search and discovery endpoints.
- Semantic search over a Git-managed registry of skills, agents, and tools.
- Embedding-based indexing of capability metadata (descriptions, tags, stack compatibility).
- Installation of discovered capabilities via an npx package.
- Basic usage telemetry (what was searched, what was returned, what was selected).
- Support for Claude Code as the primary client.

### 3.2. What's Out-of-Scope (Non-Goals)

- Project architecture awareness or context inference on the server side.
- A web UI or dashboard for browsing the registry.
- User authentication / multi-tenant access control.
- Capability authoring or publishing workflows (skills are managed directly in Git).
- Support for non-MCP clients.
