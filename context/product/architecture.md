# System Architecture Overview: AWOS Recruitment

---

## 1. Application & Technology Stack

- **MCP Server Runtime:** Python with FastMCP
- **MCP Protocol Transport:** Streamable HTTP
- **CLI / Install Package:** TypeScript (npx)

---

## 2. Data & Persistence

- **Vector Store:** ChromaDB (embeddable, Python-native)
- **Metadata Storage:** SQLite
- **Capability Source of Truth:** Git-managed repository, baked into the server at build time

---

## 3. Infrastructure & Deployment

- **Hosting:** TBD (deferred — no deployment decisions for v1)
- **Registry Sync:** Capability registry is baked into the server; updates are part of the CI/CD build process

---

## 4. External Services & APIs

- **Embedding Generation:** Local model via sentence-transformers (e.g., all-MiniLM-L6-v2)
- **Usage Telemetry & Analytics:** PostHog — all telemetry events (searches, results, selections, installations) are sent to PostHog for tracking, dashboards, and usage analysis

---

## 5. Observability & Monitoring

- **Logging:** Standard Python logging with structured output
