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

- [x] **Agent Support**
  - [x] **Agent Registry & Indexing:** Index and serve agent definitions with structured metadata, enabling agents to be discovered alongside skills and MCP servers.
  - [x] **Agent Installation:** Install discovered agents into the user's Claude Code configuration via the npx package.

---

### Phase 3

_Deploy the MCP server to AWS so it's accessible as a hosted service._

- [x] **MCP Deployment on AWS**
  - [x] **AWS Infrastructure Provisioning:** Set up the compute, networking, and storage resources needed to run the MCP server in AWS.
  - [x] **Server Deployment:** Deploy the MCP server to AWS and verify it is reachable and functional from external clients.
  - [x] **Environment Configuration:** Manage environment-specific configuration (secrets, environment variables, registry path) for the hosted deployment.

---

### Phase 4

_With the server deployed, add visibility into real-world usage patterns._

- [ ] **Usage Telemetry**
  - [ ] **Event Tracking:** Log key events — what was searched, what was returned, what was selected, and what was installed.
  - [ ] **Telemetry Storage:** Persist telemetry data for querying and aggregation.
