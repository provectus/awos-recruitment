# Functional Specification: MCP Server & Protocol Integration

- **Roadmap Item:** MCP Server & Protocol Integration — Stand up the remote MCP server and expose search and discovery as MCP tools.
- **Status:** Draft
- **Author:** AWOS

---

## 1. Overview and Rationale (The "Why")

AWOS Recruitment aims to give AI coding assistants a zero-setup discovery engine for skills, agents, and tools. Before any search intelligence or installation flows can exist, there must be a running MCP server that clients can connect to.

**The problem:** Today, there is no server for AI assistants to communicate with. Without a live MCP endpoint, none of the downstream features (semantic search, capability installation, telemetry) can function.

**The goal of this specification:** Establish the foundational MCP server infrastructure — a running server that accepts connections over Streamable HTTP, responds to health checks, and exposes a search tool that returns mock data. This is a **proof of connectivity**: the value is demonstrating that a client (primarily Claude Code) can connect to the server, invoke an MCP tool, and receive a well-formed response.

**Success criteria:** A Claude Code client can connect to the deployed MCP server and successfully call the `search_capabilities` tool, receiving a valid response.

---

## 2. Functional Requirements (The "What")

### 2.1. MCP Server Scaffold

The system must provide a running MCP server accessible over the network.

- The server must communicate using the **Streamable HTTP** MCP transport.
- The server must accept incoming MCP client connections and complete the MCP handshake/initialization successfully.
- The server must expose a **health check endpoint** that returns:
  - **status**: A string indicating the server's health (e.g., `"ok"`).
  - **version**: A string indicating the server's version (e.g., `"0.1.0"`).
- **Acceptance Criteria:**
  - [ ] The server starts and listens for incoming Streamable HTTP connections.
  - [ ] An MCP client (e.g., Claude Code) can connect to the server and complete the MCP initialization handshake.
  - [ ] A request to the health check endpoint returns a JSON response containing `status` and `version` fields.
  - [ ] The health check returns HTTP 200 when the server is operational.

### 2.2. MCP Tool: `search_capabilities`

The server must expose a single MCP tool named `search_capabilities` that clients can invoke.

- **Input:** The tool accepts a `query` parameter (string) representing the user's search query.
- **Output:** The tool returns a list of capability results. Each result contains:
  - `name` (string): The name of the capability.
  - `description` (string): A short description of what the capability does.
  - `tags` (list of strings): Tags associated with the capability.
- **Result limit:** The tool returns at most **10 results**.
- **No-match behavior:** If no results match, the tool returns an **empty list** with a success status. The client is responsible for communicating "no results" to the user.
- **Phase 1 behavior:** The search tool returns **mock/hardcoded data** regardless of the query content. Actual search logic will be implemented in later phases.
- **Acceptance Criteria:**
  - [ ] The `search_capabilities` tool is listed when the client requests the server's available tools.
  - [ ] Calling `search_capabilities` with any query string returns a valid response containing a list of results.
  - [ ] Each result in the response contains `name`, `description`, and `tags` fields.
  - [ ] The response contains no more than 10 results.
  - [ ] Calling `search_capabilities` returns a successful response (not an error) even if the query is an empty string.

---

## 3. Scope and Boundaries

### In-Scope

- A running MCP server using the Streamable HTTP transport.
- MCP handshake and initialization lifecycle.
- A health check endpoint returning status and version.
- A single MCP tool (`search_capabilities`) that accepts a query and returns mock results.
- Mock/hardcoded capability data for proof-of-connectivity testing.

### Out-of-Scope

- **Authentication and authorization** — the server is open and unauthenticated in Phase 1.
- **Rate limiting** — no request throttling in Phase 1.
- **Actual search logic** — real keyword, tag, or semantic matching (covered by Phase 2: Semantic Capability Search).
- **Capability Registry & Indexing** — Git-managed catalog ingestion and metadata validation (separate Phase 1 roadmap item).
- **Semantic Capability Search** — Embedding-based indexing and natural language queries (Phase 2).
- **Capability Installation** — npx install flow and client-initiated discovery loop (Phase 2).
- **Usage Telemetry** — Event tracking and telemetry storage (Phase 3).
- **Analytics & Reporting** — Usage metrics API and capability value signals (Phase 3).
