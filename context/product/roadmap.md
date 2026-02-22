# Product Roadmap: AWOS Recruitment

_This roadmap outlines our strategic direction based on customer needs and business goals. It focuses on the "what" and "why," not the technical "how."_

---

### Phase 1

_The core infrastructure: get the MCP server running with a functional registry and basic search._

- [x] **MCP Server & Protocol Integration**
  - [x] **MCP Server Scaffold:** Stand up the remote MCP server with a health check and basic request/response lifecycle.
  - [x] **MCP Tool Endpoints:** Expose search and discovery as MCP tools that any compatible AI assistant can call natively.

- [x] **Capability Registry & Indexing**
  - [x] **Git-Managed Catalog:** Ingest and index a Git-managed library of skills, agents, and tools with structured metadata.
  - [x] **Metadata Schema & Validation:** Define and enforce a consistent metadata schema for all registered capabilities.

---

### Phase 2

_Once the registry is live, add semantic search and zero-friction installation._

- [x] **Semantic Capability Search**
  - [x] **Embedding-Based Indexing:** Generate and store vector embeddings for all capability metadata to enable semantic matching.
  - [x] **Natural Language Query:** Accept natural language search queries from clients and return ranked results based on semantic relevance.

- [x] **Capability Installation**
  - [x] **Install Discovered Skills:** Install discovered skills into the user's Claude Code configuration via an npx package.
  - [x] **Install MCP Server Definitions:** Install discovered MCP server definitions into the user's `.mcp.json` via an npx package.

---

### Phase 3

_With discovery and installation working, add visibility into real-world usage patterns._

- [ ] **Usage Telemetry**
  - [ ] **Event Tracking:** Log key events — what was searched, what was returned, what was selected, and what was installed.
  - [ ] **Telemetry Storage:** Persist telemetry data for querying and aggregation.

- [ ] **Analytics & Reporting**
  - [ ] **Usage Metrics API:** Expose an endpoint for querying aggregated usage data (most-searched terms, most-installed capabilities, adoption rates).
  - [ ] **Capability Value Signals:** Surface which skills and agents are driving the most real-world adoption, enabling data-driven curation of the registry.
