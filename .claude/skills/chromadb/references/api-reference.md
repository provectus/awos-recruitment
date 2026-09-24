# ChromaDB Python API Reference

## Client Types

### chromadb.Client()

Ephemeral in-memory client. All data is lost when the process exits.

```python
import chromadb
client = chromadb.Client()
```

### chromadb.PersistentClient(path)

Persistent file-based client. Data is stored at the specified path.

```python
client = chromadb.PersistentClient(path="./chroma_data")
```

### chromadb.HttpClient(host, port)

HTTP client for connecting to a remote Chroma server.

```python
client = chromadb.HttpClient(host="localhost", port=8000)
```

## Client Methods

### Collection management

```python
# Create — raises if exists
collection = client.create_collection(
    name="my_collection",
    embedding_function=ef,           # optional
    metadata={"hnsw:space": "cosine"},  # optional
)

# Get — raises if not found
collection = client.get_collection(
    name="my_collection",
    embedding_function=ef,           # optional; overrides the stored configuration
)

# Get or create — idempotent
collection = client.get_or_create_collection(
    name="my_collection",
    embedding_function=ef,
    metadata={"hnsw:space": "cosine"},
)

# List all collections
collections = client.list_collections()

# Delete collection
client.delete_collection("my_collection")
```

**Important:** Chroma stores the embedding function's *configuration* with the collection, so `get_collection` and `get_or_create_collection` rebuild it for you. Passing `embedding_function` again is optional — and when you do pass one, it overrides whatever was stored, so passing a *different* function silently produces vectors the index cannot compare.

The exception is a custom function that implements only `__call__`: it is stored as `{"type": "legacy"}` and cannot be rebuilt, so it must be passed on every access. See "Custom embedding function" below.

### Utility

```python
client.heartbeat()  # health check, returns nanosecond timestamp
```

## Collection Methods

### add()

Add new records.

IDs must be unique. An ID that is already in the collection is **dropped
silently** — `add` raises nothing, warns about nothing, `count()` does not
move, and the existing record keeps its old document, metadata and embedding.
Nothing in the return value signals the skip, so `add` cannot be used to detect
collisions; reach for `upsert` whenever a record may already exist.

```python
collection.add(
    ids=["id1", "id2"],                              # required, unique strings
    documents=["text one", "text two"],               # optional if embeddings provided
    embeddings=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]],  # optional if documents provided
    metadatas=[{"key": "val1"}, {"key": "val2"}],     # optional
)
```

- Provide `documents` to have Chroma auto-embed using the collection's embedding function.
- Provide `embeddings` to bypass the embedding function.
- Both can be provided simultaneously (embeddings are used, documents stored as text).

### query()

Perform semantic search. Returns the nearest neighbors.

```python
results = collection.query(
    query_texts=["search phrase"],          # or query_embeddings
    n_results=10,                           # default 10
    where={"key": "value"},                 # metadata filter, optional
    where_document={"$contains": "text"},   # document filter, optional
    include=["documents", "metadatas", "distances"],  # optional
)
```

**Return structure:**

```python
{
    "ids": [["id1", "id2"]],           # list of lists (one per query)
    "documents": [["doc1", "doc2"]],
    "metadatas": [[{...}, {...}]],
    "distances": [[0.12, 0.34]],
    "embeddings": [[[...], [...]]],     # only if requested in include
}
```

- Lower distance = more similar.
- Multiple queries return multiple inner lists.
- Fields only appear if requested via `include` (except `ids`, always returned).

### get()

Retrieve records by ID or filter. No similarity search is performed.

```python
# By ID
results = collection.get(
    ids=["id1", "id2"],
    include=["documents", "metadatas"],
)

# By metadata filter
results = collection.get(
    where={"category": "science"},
    include=["documents", "metadatas"],
)

# By document content filter
results = collection.get(
    where_document={"$contains": "keyword"},
    include=["documents"],
)

# Combined
results = collection.get(
    where={"year": {"$gte": 2024}},
    where_document={"$contains": "important"},
    include=["documents", "metadatas"],
)
```

**Return structure:**

```python
{
    "ids": ["id1", "id2"],          # flat list (not nested)
    "documents": ["doc1", "doc2"],
    "metadatas": [{...}, {...}],
    "embeddings": [[...], [...]],
}
```

Note: `get()` returns flat lists, while `query()` returns nested lists.

### update()

Update existing records. Only provided fields are changed.

```python
# Update documents and metadata
collection.update(
    ids=["id1"],
    documents=["new content"],
    metadatas=[{"version": 2}],
)

# Update only metadata
collection.update(
    ids=["id1"],
    metadatas=[{"reviewed": True}],
)

# Update with new embeddings
collection.update(
    ids=["id1"],
    embeddings=[[0.1, 0.2, 0.3]],
)
```

Issues a warning if an ID is not found (does not raise).

### upsert()

Insert or update. If the ID exists, the record is updated; otherwise, a new record is created.

```python
collection.upsert(
    ids=["id1", "id2", "new_id"],
    documents=["updated 1", "updated 2", "brand new"],
    metadatas=[{"v": 2}, {"v": 2}, {"v": 1}],
)
```

Prefer `upsert` over `add` when re-indexing data that may partially exist.

### delete()

Remove records by ID, metadata filter, or document filter.

```python
# By ID
collection.delete(ids=["id1", "id2"])

# By metadata filter
collection.delete(where={"status": "archived"})

# By document content
collection.delete(where_document={"$contains": "deprecated"})
```

Raises `ValueError` if no deletion criteria are specified.

### count()

Return the number of records in the collection.

```python
n = collection.count()
```

### peek()

Return a sample of records from the collection.

```python
sample = collection.peek(limit=5)  # default limit=10
```

## Filter Operators (Complete Reference)

### Metadata filters (`where`)

| Operator | Description | Example |
|---|---|---|
| (shorthand) | Equality | `{"status": "active"}` |
| `$eq` | Explicit equality | `{"status": {"$eq": "active"}}` |
| `$ne` | Not equal | `{"status": {"$ne": "archived"}}` |
| `$gt` | Greater than (numeric) | `{"price": {"$gt": 100}}` |
| `$gte` | Greater than or equal (numeric) | `{"rating": {"$gte": 4.5}}` |
| `$lt` | Less than (numeric) | `{"price": {"$lt": 50}}` |
| `$lte` | Less than or equal (numeric) | `{"count": {"$lte": 10}}` |
| `$in` | Value in list | `{"category": {"$in": ["a", "b"]}}` |
| `$nin` | Value not in list | `{"tag": {"$nin": ["spam"]}}` |
| `$contains` | Array contains value | `{"tags": {"$contains": "python"}}` |
| `$not_contains` | Array does not contain | `{"tags": {"$not_contains": "draft"}}` |
| `$regex` | Regex match (string) | `{"name": {"$regex": "^test.*"}}` |
| `$not_regex` | Regex does not match | `{"name": {"$not_regex": "^draft"}}` |

### Logical operators

```python
# AND — all conditions must match
where={
    "$and": [
        {"category": "electronics"},
        {"price": {"$gte": 500}},
        {"price": {"$lte": 1000}},
    ]
}

# OR — any condition must match
where={
    "$or": [
        {"category": "electronics"},
        {"category": "wearables"},
    ]
}

# Nested logical operators
where={
    "$and": [
        {"$or": [{"category": "electronics"}, {"category": "wearables"}]},
        {"price": {"$lt": 1000}},
    ]
}
```

### Document content filters (`where_document`)

| Operator | Description | Example |
|---|---|---|
| `$contains` | Document contains substring | `{"$contains": "search term"}` |
| `$not_contains` | Document does not contain | `{"$not_contains": "excluded"}` |

### Combining metadata and document filters

```python
results = collection.query(
    query_texts=["search phrase"],
    n_results=10,
    where={"category": "science"},
    where_document={"$contains": "experiment"},
)
```

Both `where` and `where_document` can be used simultaneously on `query()` and `get()`.

## Include Parameter

Controls which fields are returned. Applies to both `query()` and `get()`.

| Value | Description |
|---|---|
| `"documents"` | Return document text |
| `"metadatas"` | Return metadata dicts |
| `"distances"` | Return similarity distances (query only) |
| `"embeddings"` | Return embedding vectors |

Default for `query()`: `["documents", "metadatas", "distances"]`
Default for `get()`: `["documents", "metadatas"]`

`ids` are always returned regardless of `include`.

## Embedding Functions

Chroma provides built-in wrappers for common embedding providers:

| Function | Import | Package | Default key env var |
|---|---|---|---|
| SentenceTransformer | `SentenceTransformerEmbeddingFunction` | `sentence-transformers` | (none — runs locally) |
| OpenAI | `OpenAIEmbeddingFunction` | `openai` | `CHROMA_OPENAI_API_KEY` |
| Cohere | `CohereEmbeddingFunction` | `cohere`, `pillow` | `CHROMA_COHERE_API_KEY` |
| HuggingFace | `HuggingFaceEmbeddingFunction` | `httpx` | `CHROMA_HUGGINGFACE_API_KEY` |
| Default (ONNX) | (none — used automatically) | Built-in | (none) |

All embedding functions are in `chromadb.utils.embedding_functions`.

### API keys

Each hosted provider wrapper takes an `api_key_env_var` argument naming the
variable to read, and it defaults to the `CHROMA_`-prefixed form in the table
above. Two things are easy to get wrong:

- The unprefixed legacy variable (`OPENAI_API_KEY`, `COHERE_API_KEY`,
  `HUGGINGFACE_API_KEY`) is still honoured, and when it is set it **overrides**
  `api_key_env_var` — including a value you passed explicitly. If both are set,
  the unprefixed one wins.
- `api_key="sk-…"` passed inline raises a `DeprecationWarning` and is not
  written to the collection configuration ("Direct api_key configuration will
  not be persisted"), so reopening the collection in a new process cannot
  recover it.

```python
# Reads MY_OPENAI_KEY; the variable name is persisted with the collection.
ef = OpenAIEmbeddingFunction(
    model_name="text-embedding-3-small",
    api_key_env_var="MY_OPENAI_KEY",
)
```

If no key is found, construction fails with
`ValueError: The <VAR> environment variable is not set.` — the message names
whichever variable the function settled on, which is the quickest way to see
which one it is actually looking at.

### Custom embedding function

A class with only `__call__` still runs, but Chroma emits two
`DeprecationWarning`s ("does not implement `__init__`", "does not implement
`name()`") and stores it as `{"type": "legacy"}`. A legacy function cannot be
rebuilt from the collection configuration, so reopening the collection falls
back to the default 384-dimension ONNX model and the next `add` fails with
`Collection expecting embedding with dimension of N, got 384`.

Implement the full protocol instead, so the function is stored as `known` and
survives `get_collection`:

```python
from typing import Any

import numpy as np
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings, Space
from chromadb.utils.embedding_functions import register_embedding_function


@register_embedding_function
class MyEmbeddingFunction(EmbeddingFunction[Documents]):
    """Embeddings from a locally hosted model."""

    def __init__(self, endpoint: str, dimensions: int = 768) -> None:
        self._endpoint = endpoint
        self._dimensions = dimensions

    def __call__(self, input: Documents) -> Embeddings:
        # input is list[str]; return one vector per document.
        return [np.asarray(embed(doc, self._endpoint), dtype=np.float32) for doc in input]

    @staticmethod
    def name() -> str:
        # Stable registry key. Changing it orphans existing collections.
        return "my_embedding_function"

    def get_config(self) -> dict[str, Any]:
        # Serialised into the collection configuration — keep it JSON-safe and
        # never put a secret here.
        return {"endpoint": self._endpoint, "dimensions": self._dimensions}

    @staticmethod
    def build_from_config(config: dict[str, Any]) -> "MyEmbeddingFunction":
        return MyEmbeddingFunction(endpoint=config["endpoint"], dimensions=config["dimensions"])

    def default_space(self) -> Space:
        # Optional; without it Chroma defaults the collection to "l2".
        return "cosine"
```

Two details that bite:

- `@register_embedding_function` matters for *reading*, not writing. Chroma
  registers the class automatically when the collection is created, so a
  round-trip inside one process works either way. A different process that
  opens the collection only has the stored name, and without the decorator (and
  an import of the module that defines the class) `get_collection` raises
  `ValueError: Embedding function my_embedding_function not found. Add
  @register_embedding_function decorator to the class definition.`
- `get_config()` output is stored in plain text alongside the collection. Pass
  credentials by environment-variable *name*, the way the built-in wrappers do
  with `api_key_env_var`, rather than by value.
