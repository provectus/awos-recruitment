# Technical Specification: Semantic Capability Search

- **Functional Specification:** `context/spec/003-semantic-search/functional-spec.md`
- **Status:** Completed
- **Author(s):** AWOS

---

## 1. High-Level Technical Approach

On server startup, a FastMCP lifespan handler scans the `registry/` directory, parses all capability metadata, and loads descriptions into an **ephemeral ChromaDB collection** with embeddings generated locally by **sentence-transformers (all-MiniLM-L6-v2)**. The existing `search_capabilities` MCP tool is updated to query this collection with natural language input, apply an optional type filter, and return ranked results with relevance scores. No persistent storage is required — the registry is baked in at build time and re-indexed on every startup.

---

## 2. Proposed Solution & Implementation Plan (The "How")

### 2.1 Architecture Changes

A new **registry loader** module and a **search index** module are added to the server. The server's startup lifecycle is extended with a FastMCP lifespan handler that orchestrates indexing before the server accepts requests.

**New modules:**

| Module | Responsibility |
|---|---|
| `registry.py` | Scans `registry/` directory, parses SKILL.md front matter and MCP YAML files, returns a unified list of `RegistryCapability` objects |
| `search_index.py` | Manages the ChromaDB ephemeral client and collection; provides `build_index()` (startup) and `query()` (search-time) functions |

**Modified modules:**

| Module | Change |
|---|---|
| `server.py` | Add lifespan handler that calls registry loader → search index at startup |
| `tools/search.py` | Replace mock data with ChromaDB query via the search index; add `type` parameter and input validation |
| `models/capability.py` | Replace `tags: list[str]` with `score: int` in `CapabilityResult` |
| `config.py` | Add `registry_path`, `embedding_model`, `search_threshold` fields |

### 2.2 Data Model Changes

**`CapabilityResult`** (modified) — MCP tool response shape:

| Field | Type | Notes |
|---|---|---|
| `name` | `str` | Capability name |
| `description` | `str` | Capability description |
| `score` | `int` | Relevance score 0–100 (replaces `tags`) |

**`RegistryCapability`** (new, internal) — used during indexing:

| Field | Type | Notes |
|---|---|---|
| `name` | `str` | Capability name |
| `description` | `str` | Description text (embedded into ChromaDB) |
| `type` | `str` | `"skill"` or `"tool"` — inferred from registry directory structure (`skills/` → `"skill"`, `mcp/` → `"tool"`) |

### 2.3 ChromaDB Collection Design

- **Client:** `chromadb.EphemeralClient()` — in-memory, no persistence needed.
- **Collection name:** `"capabilities"`
- **Embedding function:** `SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")` from `chromadb.utils.embedding_functions`.
- **Distance metric:** Cosine (default).
- **Documents:** The `description` field of each capability.
- **Metadata per document:** `{"name": <name>, "type": <type>}`.
- **IDs:** The capability `name` (unique identifier).

### 2.4 Registry Loader (`registry.py`)

Scans the `registry/` directory and returns a list of `RegistryCapability` objects:

- **Skills:** Walks `registry/skills/*/SKILL.md`, parses YAML front matter (using `python-frontmatter`), extracts `name` and `description`. Assigns `type = "skill"`.
- **MCP definitions:** Walks `registry/mcp/*.yaml`, parses YAML, extracts `name` and `description`. Assigns `type = "tool"`.
- **Skip rule:** Capabilities without a `description` field are skipped (per functional spec).

### 2.5 Startup Lifecycle (Lifespan Handler)

The FastMCP lifespan context manager orchestrates the startup sequence:

1. Load configuration (registry path, embedding model, threshold).
2. Call registry loader → get list of `RegistryCapability` objects.
3. Initialize ChromaDB ephemeral client and create the `"capabilities"` collection with the sentence-transformer embedding function.
4. Add all capabilities to the collection (documents = descriptions, metadata = name + type, ids = name).
5. Yield the collection via `lifespan_context` so it's accessible to MCP tools at request time.

Indexing must complete before the server accepts MCP requests — this is guaranteed by the lifespan handler pattern.

### 2.6 API Contract (MCP Tool)

**Tool:** `search_capabilities`

**Input parameters:**

| Parameter | Type | Required | Validation |
|---|---|---|---|
| `query` | `str` | Yes | Must not be empty or blank. Returns error if so. |
| `type` | `str \| None` | No | If provided, must be one of `"skill"`, `"agent"`, `"tool"`. Returns error for invalid values. |

**Output:** `list[dict]` — each dict contains:

| Field | Type | Description |
|---|---|---|
| `name` | `str` | Capability name |
| `description` | `str` | Capability description |
| `score` | `int` | Relevance score 0–100 |

**Query logic:**

1. Validate inputs (empty query → error, invalid type → error).
2. Build ChromaDB query: `collection.query(query_texts=[query], n_results=10)`. If `type` is provided, add `where={"type": type}`.
3. Convert cosine distances to scores: `score = round((1 - distance) * 100)`.
4. Filter results where `score < 20` (configurable via `AWOS_SEARCH_THRESHOLD`).
5. Return remaining results ordered by score descending.

### 2.7 Configuration Additions

New fields in the `Config` dataclass:

| Env Var | Field | Type | Default | Purpose |
|---|---|---|---|---|
| `AWOS_REGISTRY_PATH` | `registry_path` | `str` | `"../registry"` | Path to registry directory |
| `AWOS_EMBEDDING_MODEL` | `embedding_model` | `str` | `"all-MiniLM-L6-v2"` | sentence-transformers model name |
| `AWOS_SEARCH_THRESHOLD` | `search_threshold` | `int` | `20` | Minimum relevance score to include in results |

### 2.8 Dependencies

Add to `pyproject.toml` runtime dependencies:

| Package | Purpose |
|---|---|
| `chromadb` | Vector database for embedding storage and semantic search |
| `sentence-transformers` | Local embedding model (all-MiniLM-L6-v2) |

---

## 3. Impact and Risk Analysis

### System Dependencies

- **Registry directory:** The loader depends on the `registry/` directory structure. Changes to directory layout (e.g., new capability types) would require loader updates.
- **Startup time:** Embedding generation adds time to server startup. With 4 capabilities and a small model this should be negligible, but the first startup will also download the model (~80MB) from Hugging Face.

### Potential Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| First startup downloads the embedding model from Hugging Face | Slow first start; fails without internet | Document this in `.env.example`. In production, the model can be pre-downloaded during the Docker build step. |
| `type: "agent"` is a valid filter value but no agents exist in the registry yet | Empty results for agent queries | This is expected behavior — returns empty list. No action needed. |
| Registry grows large (hundreds of capabilities) | Slower startup indexing | ChromaDB batch insertion and sentence-transformers batch encoding handle this efficiently. Not a concern at current scale. |
| Cosine distance → score mapping may need tuning | Threshold of 20 may be too lenient or strict | Threshold is configurable via `AWOS_SEARCH_THRESHOLD`. Can be adjusted without code changes. |

---

## 4. Testing Strategy

All tests use the existing patterns: `pytest` + `pytest-asyncio`, in-process MCP client via `Client(mcp)`.

| Test | What it verifies |
|---|---|
| **Startup indexing** | Given a test registry fixture with known capabilities, when the server starts, then all capabilities with descriptions are indexed and searchable. |
| **Basic search** | Given indexed capabilities, when a relevant query is sent, then results are returned ranked by score with `name`, `description`, `score` fields. |
| **Type filtering** | Given indexed capabilities, when a query includes `type: "skill"`, then only skills are returned. |
| **Invalid type** | When a query includes an invalid type value, then an error is returned. |
| **Empty query** | When a blank or empty query is sent, then an error is returned. |
| **Threshold filtering** | Given a query with low relevance to any capability, then results below the threshold score are excluded. |
| **No results** | Given a completely unrelated query, then an empty list is returned. |

Test fixtures will create temporary registry directories with known SKILL.md and MCP YAML files to ensure deterministic results.
