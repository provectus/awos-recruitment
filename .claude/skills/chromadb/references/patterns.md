# ChromaDB Common Patterns

## Contents

- [Batch Ingestion](#batch-ingestion) — chunking large writes, and why `add` is the wrong verb for a re-index
- [Metadata Schema Design](#metadata-schema-design) — flat typed values, flattening nested data, designing for the queries you will run
- [HNSW Configuration](#hnsw-configuration) — parameters and defaults, the `configuration=` argument, the legacy `hnsw:*` keys, what `modify` can change
- [Collection Lifecycle](#collection-lifecycle) — full re-index vs incremental upsert
- [Common Query Patterns](#common-query-patterns) — metadata pre-filters, keyword + semantic, date ranges, minimal responses
- [Error Handling](#error-handling) — the failures that are silent, and the embedding function on `get`
- [ID Generation Strategies](#id-generation-strategies) — deterministic, UUID, prefixed

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

Use `upsert` instead of `add` when re-indexing data that may partially exist. A
duplicate ID does not raise — `add` drops the write silently, so a re-index
built on `add` looks like it succeeded while leaving stale content in place.

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

HNSW (Hierarchical Navigable Small World) is the underlying index algorithm.
Tuning parameters are set through the `configuration` argument at creation
time.

### Available parameters

| Parameter | Default | Description |
|---|---|---|
| `space` | `"l2"` | Distance metric: `"l2"`, `"cosine"`, or `"ip"` |
| `ef_construction` | `100` | Index build quality. Higher = better recall, slower build |
| `ef_search` | `100` | Search breadth. Higher = better recall, slower query |
| `max_neighbors` | `16` | Max connections per node. Higher = better recall, more memory |
| `resize_factor` | `1.2` | Growth factor when the index is resized |
| `sync_threshold` | `1000` | Records buffered before the index is flushed to disk |

Read the effective values back with `collection.configuration["hnsw"]` — that
is the authoritative answer for a given build, and the fastest way to confirm a
setting was accepted.

`num_threads` and `batch_size` are accepted by the type but are not part of the
persisted configuration, so setting them has no durable effect.

### Example: optimized for recall

```python
collection = client.create_collection(
    name="high_recall",
    configuration={
        "hnsw": {
            "space": "cosine",
            "ef_construction": 200,
            "ef_search": 200,
            "max_neighbors": 32,
        }
    },
)
```

### Example: optimized for speed

```python
collection = client.create_collection(
    name="fast_search",
    configuration={
        "hnsw": {
            "space": "cosine",
            "ef_construction": 100,
            "ef_search": 50,
            "max_neighbors": 16,
        }
    },
)
```

### The older `hnsw:*` metadata form

Pre-1.x code sets the same knobs through collection metadata, and Chroma still
accepts it without warning — `metadata={"hnsw:space": "cosine",
"hnsw:construction_ef": 200, "hnsw:search_ef": 50, "hnsw:M": 32}` produces the
same configuration as the `configuration` block above. Two reasons to prefer
the new form in new code: the key names differ from what the configuration
actually stores (`hnsw:M` → `max_neighbors`, `hnsw:construction_ef` →
`ef_construction`), and unrecognised keys such as `hnsw:num_threads` are kept
verbatim in `collection.metadata` while doing nothing, which reads as if they
took effect.

### Changing parameters after creation

`space` and `ef_construction` are baked in at build time — `modify` rejects
them with `InvalidArgumentError: unknown field ...`, and changing the metric
means recreating the collection. Search-time breadth is adjustable, which makes
`ef_search` the one knob worth tuning against a live index:

```python
collection.modify(configuration={"hnsw": {"ef_search": 200}})
```

Re-read `collection.configuration["hnsw"]` afterwards. `modify` accepts
`max_neighbors` without error but does not apply it to an existing index, so
the returned configuration — not the absence of an exception — is what tells
you whether a change landed.

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
    configuration={"hnsw": {"space": "cosine"}},
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

| Symptom | Cause | Fix |
|---|---|---|
| `add` succeeds but nothing changes | Duplicate ID — the write is dropped silently | Use `upsert`, or diff against `collection.get(ids=...)` first if you need to know which IDs collided |
| `ValueError` on `delete` | No criteria specified | Provide at least `ids`, `where`, or `where_document` |
| `ValueError: Expected where operator to be one of …` | Operator used on the wrong filter, e.g. `$regex` in `where` | `$regex` / `$not_regex` belong in `where_document` |
| Dimension mismatch | Embedding size doesn't match collection | Ensure all embeddings use the same model/dimension |
| Collection not found | `get_collection` on missing name | Use `get_or_create_collection` instead |

### Embedding function on get

Chroma persists the embedding function's configuration with the collection, so
a built-in wrapper is rebuilt automatically:

```python
# The SentenceTransformer config was stored at creation — nothing to pass.
collection = client.get_collection("my_col")
```

Passing one explicitly is still allowed and overrides the stored config, which
is the failure mode worth guarding against: passing a *different* function than
the collection was built with produces vectors the index cannot compare, with
no error.

The one case that genuinely requires passing it every time is a legacy custom
function — one implementing only `__call__`, stored as `{"type": "legacy"}`.
Reopening that collection falls back to the default ONNX model and
`query(query_texts=...)` returns wrong results. See "Custom embedding function"
in `api-reference.md` for the full protocol that avoids this.

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
