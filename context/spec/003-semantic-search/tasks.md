# Tasks: Semantic Capability Search

---

- [x] **Slice 1: Add dependencies and expand configuration**
  - [x] Add `chromadb` and `sentence-transformers` to `pyproject.toml` runtime dependencies. **[Agent: python-expert]**
  - [x] Add `registry_path`, `embedding_model`, `search_threshold` fields to the `Config` dataclass in `config.py` with env vars `AWOS_REGISTRY_PATH`, `AWOS_EMBEDDING_MODEL`, `AWOS_SEARCH_THRESHOLD` and their defaults. **[Agent: python-expert]**
  - [x] Update `.env.example` to document the new env vars. **[Agent: python-expert]**
  - [x] Verify: run `uv sync` to install dependencies, start the server, and run the existing test suite — all must pass. **[Agent: qa-tester]**
  - [x] Git commit.

- [x] **Slice 2: Registry loader module**
  - [x] Create `RegistryCapability` Pydantic model in `models/` with fields `name`, `description`, `type`. Re-export from `models/__init__.py`. **[Agent: python-expert]**
  - [x] Create `registry.py` module: scan `registry/skills/*/SKILL.md` and `registry/mcp/*.yaml`, parse metadata, return a list of `RegistryCapability` objects. Skip capabilities without a description. Infer type from directory (`skills/` → `"skill"`, `mcp/` → `"tool"`). **[Agent: python-expert]**
  - [x] Write unit tests for the registry loader using `tmp_path` fixtures with known SKILL.md and MCP YAML files. Test: correct parsing, skip-without-description, type inference. **[Agent: python-expert]**
  - [x] Verify: run the full test suite — all existing and new tests pass, server starts. **[Agent: qa-tester]**
  - [x] Git commit.

- [x] **Slice 3: Search index module (ChromaDB)**
  - [x] Create `search_index.py` module with: (1) `build_index(capabilities, embedding_model)` — creates an ephemeral ChromaDB client and collection, adds capabilities as documents with metadata; (2) `query(collection, query_text, n_results, type_filter, threshold)` — queries the collection and returns results with scores (0–100). **[Agent: python-expert]**
  - [x] Write unit tests for the search index: build index from fixture data, query with relevant text returns ranked results, type filter works, threshold filtering excludes low-score results, unrelated query returns empty list. **[Agent: python-expert]**
  - [x] Verify: run the full test suite — all existing and new tests pass, server starts. **[Agent: qa-tester]**
  - [x] Git commit.

- [x] **Slice 4: Wire into server and update the search tool**
  - [x] Update `CapabilityResult` model: replace `tags: list[str]` with `score: int`. **[Agent: python-expert]**
  - [x] Add a FastMCP lifespan handler to `server.py` that calls registry loader → search index `build_index()` on startup, yielding the collection via `lifespan_context`. **[Agent: python-expert]**
  - [x] Rewrite `search_capabilities` tool in `tools/search.py`: remove mock data, accept `query` (required) and `type` (optional) parameters, validate inputs (empty query → error, invalid type → error), query ChromaDB via search index, return results as `list[dict]` with `name`, `description`, `score`. **[Agent: python-expert]**
  - [x] Update existing search tool tests (`test_search_tool.py`) to reflect new behavior and response shape. **[Agent: python-expert]**
  - [x] Write new integration tests: basic semantic search returns ranked results, type filtering returns only matching type, empty query returns error, invalid type returns error, threshold filtering excludes low-score results, completely unrelated query returns empty list. **[Agent: python-expert]**
  - [x] Verify: start the server, call `search_capabilities` via the MCP client with various queries (relevant, unrelated, filtered by type, empty), confirm correct behavior end-to-end. Run the full test suite. **[Agent: qa-tester]**
  - [x] Git commit.
