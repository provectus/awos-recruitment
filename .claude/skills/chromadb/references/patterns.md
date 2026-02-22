# ChromaDB Common Patterns

## Batch Ingestion

ChromaDB has a maximum batch size limit. For large datasets, split into chunks:

```python
BATCH_SIZE = 5000

for i in range(0, len(documents), BATCH_SIZE):
    batch_ids = ids[i : i + BATCH_SIZE]
    batch_docs = documents[i : i + BATCH_SIZE]
    batch_meta = metadatas[i : i + BATCH_SIZE]
    collection.add(
        ids=batch_ids,
        documents=batch_docs,
        metadatas=batch_meta,
    )
```

Use `upsert` instead of `add` when re-indexing data that may partially exist to avoid duplicate ID errors.

## Metadata Schema Design

### Use flat, typed metadata

ChromaDB metadata values must be strings, integers, floats, booleans, or lists of these primitive types. Nested objects are not supported.

```python
# Correct — flat values
metadata = {
    "source": "web",
    "year": 2024,
    "rating": 4.5,
    "is_reviewed": True,
}

# Wrong — nested objects not supported
metadata = {
    "author": {"name": "Alice", "email": "alice@example.com"},
}
```

### Flatten nested data

```python
# Flatten nested structures into prefixed keys
metadata = {
    "author_name": "Alice",
    "author_email": "alice@example.com",
}
```

### Use consistent types per key

All values for a given metadata key should be the same type across all records. Mixing types (e.g., string and int for the same key) can cause unexpected filter behavior.

### Design metadata for query patterns

Define metadata keys based on how data will be filtered, not just how it is structured at the source:

```python
# If filtering by date range is needed, store year/month as integers
metadata = {
    "year": 2024,
    "month": 6,
    "category": "research",
    "language": "en",
}
```

### Use list metadata for tags

```python
metadata = {
    "tags": ["python", "machine-learning", "tutorial"],
}
```

Filter with `$contains` / `$not_contains`:

```python
results = collection.query(
    query_texts=["ML tutorial"],
    where={"tags": {"$contains": "python"}},
)
```

## HNSW Configuration

HNSW (Hierarchical Navigable Small World) is the underlying index algorithm. Tuning parameters are set via collection metadata at creation time.

### Available parameters

| Parameter | Default | Description |
|---|---|---|
| `hnsw:space` | `"l2"` | Distance metric: `"l2"`, `"cosine"`, or `"ip"` |
| `hnsw:construction_ef` | `100` | Controls index build quality. Higher = better recall, slower build |
| `hnsw:search_ef` | `10` | Controls search quality. Higher = better recall, slower query |
| `hnsw:M` | `16` | Max connections per node. Higher = better recall, more memory |
| `hnsw:num_threads` | `4` | Threads for index operations |

### Example: optimized for recall

```python
collection = client.create_collection(
    name="high_recall",
    metadata={
        "hnsw:space": "cosine",
        "hnsw:construction_ef": 200,
        "hnsw:search_ef": 100,
        "hnsw:M": 32,
    },
)
```

### Example: optimized for speed

```python
collection = client.create_collection(
    name="fast_search",
    metadata={
        "hnsw:space": "cosine",
        "hnsw:construction_ef": 100,
        "hnsw:search_ef": 10,
        "hnsw:M": 16,
    },
)
```

### Choosing a distance metric

- **cosine** — best for normalized embeddings (most embedding models produce normalized vectors). The most common choice.
- **l2** (Euclidean) — default. Suitable when raw distance matters.
- **ip** (inner product) — use when vectors are pre-normalized and dot-product similarity is desired.

Set the metric at collection creation. It cannot be changed after creation.

## Collection Lifecycle

### Re-creating a collection (full re-index)

```python
# Delete and recreate for a clean re-index
client.delete_collection("my_collection")
collection = client.create_collection(
    name="my_collection",
    embedding_function=ef,
    metadata={"hnsw:space": "cosine"},
)
# Re-add all data...
```

### Incremental updates

Use `upsert` for incremental updates. It handles both new and existing records:

```python
# On each sync cycle, upsert all current documents
collection.upsert(
    ids=current_ids,
    documents=current_docs,
    metadatas=current_metas,
)

# Optionally delete removed documents
stale_ids = set(all_known_ids) - set(current_ids)
if stale_ids:
    collection.delete(ids=list(stale_ids))
```

## Common Query Patterns

### Semantic search with metadata pre-filter

```python
# Find similar documents only within a specific category
results = collection.query(
    query_texts=["machine learning optimization"],
    n_results=5,
    where={"category": "research"},
)
```

### Combined semantic + keyword search

```python
# Semantic similarity + document must contain specific term
results = collection.query(
    query_texts=["neural network training"],
    n_results=10,
    where_document={"$contains": "gradient descent"},
)
```

### Date range filtering

```python
results = collection.query(
    query_texts=["recent findings"],
    n_results=20,
    where={
        "$and": [
            {"year": {"$gte": 2023}},
            {"year": {"$lte": 2024}},
        ]
    },
)
```

### Multi-category filtering

```python
results = collection.query(
    query_texts=["portable device"],
    n_results=10,
    where={"category": {"$in": ["electronics", "wearables", "accessories"]}},
)
```

### Retrieving only IDs and distances (minimal response)

```python
results = collection.query(
    query_texts=["search term"],
    n_results=100,
    include=["distances"],  # omit documents and metadatas for speed
)
```

## Error Handling

### Common errors

| Error | Cause | Fix |
|---|---|---|
| `ValueError` on `add` | Duplicate ID | Use `upsert` instead, or check for existing IDs |
| `ValueError` on `delete` | No criteria specified | Provide at least `ids`, `where`, or `where_document` |
| Dimension mismatch | Embedding size doesn't match collection | Ensure all embeddings use the same model/dimension |
| Collection not found | `get_collection` on missing name | Use `get_or_create_collection` instead |

### Handling missing embedding function on get

```python
# Always pass the embedding function when getting an existing collection
ef = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
collection = client.get_collection("my_col", embedding_function=ef)
```

Chroma does not persist the embedding function. Forgetting to pass it when getting a collection means `query(query_texts=...)` will use the default ONNX model, producing wrong results.

## ID Generation Strategies

### Deterministic IDs (recommended for deduplication)

```python
import hashlib

def make_id(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()[:16]
```

Deterministic IDs enable idempotent `upsert` — re-indexing the same content produces the same ID.

### UUID-based IDs

```python
import uuid

doc_id = str(uuid.uuid4())
```

Simple but does not deduplicate. Use when each insert is guaranteed unique.

### Prefixed IDs

```python
doc_id = f"web_{source_id}"
doc_id = f"file_{path.stem}_{chunk_index}"
```

Prefixed IDs make filtering and debugging easier. Use a consistent scheme per data source.
