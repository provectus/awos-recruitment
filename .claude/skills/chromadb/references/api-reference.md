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
    embedding_function=ef,           # must match the one used at creation
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

**Important:** When using `get_collection` or `get_or_create_collection`, always pass the same `embedding_function` that was used at creation. Chroma does not store the embedding function — it must be provided on every access.

### Utility

```python
client.heartbeat()  # health check, returns nanosecond timestamp
```

## Collection Methods

### add()

Add new records. All IDs must be unique and not already exist in the collection.

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

| Function | Import | Requires |
|---|---|---|
| SentenceTransformer | `SentenceTransformerEmbeddingFunction` | `sentence-transformers` package |
| OpenAI | `OpenAIEmbeddingFunction` | `OPENAI_API_KEY` env var |
| Cohere | `CohereEmbeddingFunction` | `COHERE_API_KEY` env var |
| HuggingFace | `HuggingFaceEmbeddingFunction` | `HUGGINGFACE_API_KEY` env var |
| Default (ONNX) | (none — used automatically) | Built-in, no setup |

All embedding functions are in `chromadb.utils.embedding_functions`.

### Custom embedding function

Implement the `EmbeddingFunction` protocol:

```python
from chromadb import EmbeddingFunction, Documents, Embeddings

class MyEmbeddingFunction(EmbeddingFunction[Documents]):
    def __call__(self, input: Documents) -> Embeddings:
        # input is list[str], return list[list[float]]
        return [embed(doc) for doc in input]
```
