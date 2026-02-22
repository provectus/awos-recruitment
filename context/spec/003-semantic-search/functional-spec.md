# Functional Specification: Semantic Capability Search

- **Roadmap Item:** Semantic Capability Search — Enable embedding-based indexing and natural language querying of the capability registry.
- **Status:** Completed
- **Author:** AWOS

---

## 1. Overview and Rationale (The "Why")

Today, the AWOS Recruitment registry contains a growing catalog of skills, agents, and tools — but there is no way for a developer (or their AI assistant) to find the right capability without knowing its exact name. This forces manual browsing or guesswork, which slows down discovery and reduces adoption.

**Semantic Capability Search** solves this by letting clients search the registry using plain English. A developer working on a database migration can have their AI assistant query "PostgreSQL migration agent" and instantly receive a ranked list of the most relevant capabilities — without needing to know how the registry is organized or what specific names are used.

This is the foundation of the product's core value proposition: **zero-friction, intelligent discovery**.

**Success metric:** Discovery latency under 2 seconds — a developer finds the right skill/agent for their task in under 2 seconds via semantic search.

---

## 2. Functional Requirements (The "What")

### 2.1 Embedding-Based Indexing

- The system must generate vector embeddings for all capabilities in the registry.
- Embeddings are generated from the **description** field of each capability's metadata.
- Embeddings must be generated **on server startup**. When the server starts, it reads the current state of the Git-managed registry and indexes all capabilities.
  - **Acceptance Criteria:**
    - [x] When the server starts, embeddings are generated for every capability in the registry.
    - [x] If a capability has no description, it is skipped during indexing (it will not appear in search results).
    - [x] Indexing completes before the search tool becomes available to clients.

### 2.2 Natural Language Query (Search Tool)

- The system must expose an MCP tool that accepts a natural language search query and returns ranked results.
- **Input parameters:**
  - `query` (required, string) — The natural language search text. Must not be empty or blank.
  - `type` (optional, string) — Filter results by capability type. Accepted values: `skill`, `agent`, `tool`. If omitted, all types are included.
- **Output:** An ordered list of matching capabilities, ranked by semantic relevance (highest first). Each result includes:
  - `name` — The capability's name.
  - `description` — The capability's description.
  - `score` — A relevance score as an integer from 0 to 100 (where 100 is a perfect match).
- **Result limit:** Up to **10** results per query.
- **Relevance threshold:** Results with a relevance score below a minimum threshold are excluded, even if fewer than 10 results would be returned. [NEEDS CLARIFICATION: What should the exact threshold value be? This will likely be tuned during implementation.]
  - **Acceptance Criteria:**
    - [x] When a client sends a valid query (e.g., "PostgreSQL migration"), the tool returns up to 10 results ranked by relevance, highest score first.
    - [x] Each result contains `name`, `description`, and `score` (integer 0–100).
    - [x] Results below the minimum relevance threshold are not returned.
    - [x] When a client sends a query with a `type` filter (e.g., `type: "agent"`), only capabilities of that type are returned.
    - [x] When a client sends an invalid `type` value, the tool returns an error.
    - [x] When a client sends an empty or blank `query`, the tool returns an error indicating that a query is required.
    - [x] When no capabilities match the query (or all are below the threshold), the tool returns an empty list.
    - [x] Search results are returned within 2 seconds.

---

## 3. Scope and Boundaries

### In-Scope

- Generating vector embeddings from capability descriptions on server startup.
- An MCP search tool that accepts a natural language query and an optional type filter.
- Returning ranked results with name, description, and relevance score.
- Enforcing a minimum relevance score threshold.
- Returning an error for empty/blank queries and invalid type filters.

### Out-of-Scope

- **Capability Installation** (separate Phase 2 roadmap item — covered in its own spec).
- **Usage Telemetry** (Phase 3 roadmap item).
- **Analytics & Reporting** (Phase 3 roadmap item).
- Automatic re-indexing when the registry changes (requires server restart).
- Filtering by tags, stack compatibility, or any metadata beyond capability type.
- A web UI or dashboard for searching the registry.
- Configurable result limits (fixed at 10).
