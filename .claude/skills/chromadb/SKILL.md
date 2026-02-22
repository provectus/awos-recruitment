---
name: ChromaDB
description: This skill should be used when the user asks to "set up ChromaDB", "create a Chroma collection", "add embeddings to ChromaDB", "query ChromaDB", "search vectors", "semantic search with ChromaDB", "filter ChromaDB results", "ChromaDB metadata filtering", "configure Chroma", "use ChromaDB persistent client", "delete from ChromaDB", or when writing any code that interacts with the chromadb Python package. Provides up-to-date API patterns, filtering syntax, collection configuration, and embedding function integration.
version: 0.1.0
---

# ChromaDB Python Skill

ChromaDB is an open-source embedding database for building applications with semantic search and retrieval. This skill covers the Python client API for creating collections, storing documents with embeddings, and querying with semantic search and metadata filtering.

## Client Initialization

### In-memory (ephemeral)

```python
import chromadb

client = chromadb.Client()
```

Data is lost when the process exits. Use for testing and prototyping.

### Persistent (file-based)

```python
client = chromadb.PersistentClient(path="./chroma_data")
```

Data is saved to disk at the specified path. Use for local applications and development.

### HTTP client (remote server)

```python
client = chromadb.HttpClient(host="localhost", port=8000)
```

Connects to a standalone Chroma server. Use for production deployments.

## Collection Management

### Create or get a collection

```python
collection = client.get_or_create_collection(
    name="my_collection",
    embedding_function=embedding_fn,
    metadata={"hnsw:space": "cosine"}
)
```

- `get_or_create_collection` — idempotent; creates if absent, returns existing if present.
- `create_collection` — raises if the collection already exists.
- `get_collection` — raises if the collection does not exist.

### List, delete, count

```python
client.list_collections()                    # list all collections
client.delete_collection("my_collection")    # delete by name
collection.count()                           # number of records
```

## Adding Data

### Add documents (auto-embedded)

```python
collection.add(
    ids=["id1", "id2", "id3"],
    documents=["First document", "Second document", "Third document"],
    metadatas=[
        {"source": "web", "year": 2024},
        {"source": "api", "year": 2024},
        {"source": "manual", "year": 2023},
    ],
)
```

- `ids` — required, must be unique strings.
- `documents` — raw text; Chroma uses the collection's embedding function to generate embeddings.
- `metadatas` — optional dict per document for filtering.

### Add pre-computed embeddings

```python
collection.add(
    ids=["id1", "id2"],
    embeddings=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]],
    metadatas=[{"source": "precomputed"}, {"source": "precomputed"}],
    documents=["doc one", "doc two"],  # optional when embeddings provided
)
```

### Upsert (insert or update)

```python
collection.upsert(
    ids=["id1", "id2", "id3"],
    documents=["new content 1", "new content 2", "new content 3"],
    metadatas=[{"version": 2}, {"version": 2}, {"version": 2}],
)
```

Inserts records if the ID does not exist; updates if it does. Prefer `upsert` over `add` when re-indexing data that may already exist.

## Querying

### Semantic search with text

```python
results = collection.query(
    query_texts=["search phrase"],
    n_results=5,
)
```

Returns a dict with keys: `ids`, `documents`, `metadatas`, `distances`, `embeddings`. Each value is a **list of lists** (one inner list per query). Lower distance = more similar.

**Important:** `query()` returns nested lists, while `get()` returns flat lists. This is a common source of bugs:

```python
# query() — nested: results["ids"] == [["id1", "id2"]]
# get()   — flat:   results["ids"] == ["id1", "id2"]
```

### Semantic search with embeddings

```python
results = collection.query(
    query_embeddings=[[0.1, 0.2, 0.3]],
    n_results=10,
)
```

### Control returned fields with `include`

```python
results = collection.query(
    query_texts=["search phrase"],
    n_results=5,
    include=["documents", "metadatas", "distances"],
)
```

Valid include values: `"documents"`, `"metadatas"`, `"distances"`, `"embeddings"`.

### Get by ID (no search)

```python
results = collection.get(
    ids=["id1", "id2"],
    include=["documents", "metadatas"],
)
```

### Get with filter (no search)

```python
results = collection.get(
    where={"source": "web"},
    include=["documents", "metadatas"],
)
```

## Filtering

Filters are applied via `where` (metadata) and `where_document` (text content) parameters on both `query` and `get`.

### Filter operators quick reference

| Operator | Type | Example |
|---|---|---|
| `$eq` | Equality | `{"status": {"$eq": "active"}}` |
| `$ne` | Inequality | `{"status": {"$ne": "archived"}}` |
| `$gt` | Greater than | `{"price": {"$gt": 100}}` |
| `$gte` | Greater or equal | `{"rating": {"$gte": 4.5}}` |
| `$lt` | Less than | `{"price": {"$lt": 50}}` |
| `$lte` | Less or equal | `{"count": {"$lte": 10}}` |
| `$in` | In list | `{"category": {"$in": ["a", "b"]}}` |
| `$nin` | Not in list | `{"tag": {"$nin": ["spam"]}}` |
| `$contains` | Array contains | `{"tags": {"$contains": "python"}}` |
| `$not_contains` | Array excludes | `{"tags": {"$not_contains": "draft"}}` |

Shorthand: `{"key": "value"}` is equivalent to `{"key": {"$eq": "value"}}`.

### Logical operators

```python
# AND
where={"$and": [{"category": "electronics"}, {"price": {"$gte": 500}}]}

# OR
where={"$or": [{"category": "electronics"}, {"category": "wearables"}]}
```

### Document content filtering

```python
results = collection.query(
    query_texts=["search"],
    where_document={"$contains": "specific phrase"},
)
```

For complete filter operator details and advanced patterns, consult `references/api-reference.md`.

## Embedding Functions

Chroma supports pluggable embedding functions. Set the embedding function when creating a collection — it is used automatically for `add`, `update`, `upsert`, and `query` operations.

### SentenceTransformers (local, no API key)

```python
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

ef = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
collection = client.get_or_create_collection("my_col", embedding_function=ef)
```

### OpenAI

```python
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

ef = OpenAIEmbeddingFunction(model_name="text-embedding-3-small")
collection = client.create_collection("my_col", embedding_function=ef)
```

Requires the `OPENAI_API_KEY` environment variable.

### Default embedding function

If no `embedding_function` is specified, Chroma uses its built-in default (all-MiniLM-L6-v2 via ONNX). This is suitable for prototyping but should be replaced with a purpose-chosen model for production.

## Collection Configuration

### Distance metrics

Set via the `hnsw:space` metadata key at creation time:

| Metric | Value | Use case |
|---|---|---|
| Cosine | `"cosine"` | Normalized embeddings (most common) |
| L2 (Euclidean) | `"l2"` | Default; raw distance |
| Inner product | `"ip"` | Pre-normalized, dot-product similarity |

```python
collection = client.create_collection(
    name="my_col",
    metadata={"hnsw:space": "cosine"},
)
```

For HNSW tuning parameters and advanced configuration, consult `references/patterns.md`.

## Update and Delete

### Update existing records

```python
collection.update(
    ids=["id1"],
    documents=["updated content"],
    metadatas=[{"version": 3}],
)
```

Only provided fields are updated. Omitted fields remain unchanged.

### Delete records

```python
collection.delete(ids=["id1", "id2"])
collection.delete(where={"status": "archived"})
collection.delete(where_document={"$contains": "deprecated"})
```

## Peek (sample data)

```python
sample = collection.peek(limit=5)  # returns a sample of records (default 10)
```

Useful for inspecting collection contents during development.

## Common Errors

| Error | Cause | Fix |
|---|---|---|
| `ValueError` on `add` | Duplicate ID | Use `upsert` instead |
| Dimension mismatch | Embedding size differs from collection | Ensure consistent embedding model |
| Wrong results after `get_collection` | Missing `embedding_function` | Always pass the same `embedding_function` used at creation |
| `ValueError` on `delete` | No criteria given | Provide `ids`, `where`, or `where_document` |

Chroma does not persist the embedding function. Omitting it when calling `get_collection` causes `query(query_texts=...)` to silently use the default ONNX model, producing incorrect results.

## Additional Resources

### Reference Files

For detailed API documentation and advanced patterns, consult:
- **`references/api-reference.md`** — Complete method signatures, all filter operators with examples, include options, result structure
- **`references/patterns.md`** — Batch ingestion, metadata schema design, HNSW tuning, collection lifecycle, common query patterns, error handling
