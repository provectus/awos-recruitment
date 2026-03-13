# ProRAG API Reference

Fallback reference for when the project is not yet set up. **Prefer reading the live installed source** (see SKILL.md "Reading the Live API" section).

## Package Imports

```python
# Top-level exports
from provrag import step, pipeline, Settings, LLMProvider, GenerateResult, get_settings

# Data models
from provrag.models.document import Document, Chunk, ScoredChunk

# LLM abstractions (use TYPE_CHECKING guard in production code)
from provrag.llm.embedder import BaseEmbedder, BedrockEmbedder, OpenAIEmbedder
from provrag.llm.generator import BaseLLM, GenerateResult, BedrockLLM, OpenAILLM
from provrag.llm.factory import create_embedder, create_llm

# Retrieval
from provrag.retrieval.opensearch_client import ProvragOpenSearchClient

# Built-in ingestion steps
from provrag.pipelines.ingestion import load_documents, chunk_documents, embed_chunks, index_chunks

# Built-in RAG steps
from provrag.pipelines.rag import embed_query, dense_retrieve, assemble_prompt, generate_answer
from provrag.pipelines.rag import semantic_rag_pipeline, DEFAULT_SYSTEM_PROMPT

# Storage
from provrag.storage.s3 import S3DocumentLoader

# Chunking
from provrag.chunking.text_chunker import RecursiveCharacterChunker

# API
from provrag.api import create_app

# Tracing
from provrag.tracing.setup import init_tracing

# Settings
from provrag.settings import Settings, get_settings, Environment, LLMProvider
```

## Decorators

### @step

```python
from provrag import step

@step(name="my-step", span_kind="CHAIN")
def my_step(data: list[str]) -> list[str]:
    ...
```

Parameters:
- `name`: Prefect task name + OTEL span name (defaults to function name)
- `span_kind`: OTEL span kind -- `"CHAIN"` (default), `"EMBEDDING"`, `"RETRIEVER"`, or `"LLM"`
- `retries` / `retry_delay_seconds`: Prefect retry configuration
- `tags`: Prefect task tags (set[str])
- Additional `**kwargs` passed to `prefect.task()`
- Cache policy is always `NONE`

### @pipeline

```python
from provrag import pipeline

@pipeline(name="my-pipeline")
def my_pipeline(query: str, ...) -> str:
    ...
```

Parameters:
- `name`: Prefect flow name (defaults to function name)
- `retries` / `retry_delay_seconds`: Prefect retry configuration
- `log_prints`: Capture print statements (default: `True`)
- Additional `**kwargs` passed to `prefect.flow()`

### Testing decorated functions

Call `.fn()` to bypass the Prefect wrapper:

```python
result = my_step.fn(data=["hello"])
count = my_pipeline.fn(settings=test_settings, index_name="test")
```

## Data Models

```python
from provrag.models.document import Document, Chunk, ScoredChunk

# Document -- a loaded source document
Document(
    id: str,                              # Unique identifier (typically SHA-256 hash)
    content: str,                         # Full text content
    metadata: dict[str, Any] = {},        # Arbitrary metadata
)

# Chunk -- a split piece of a document
Chunk(
    id: str,                              # Unique chunk identifier
    document_id: str,                     # Parent document ID
    content: str,                         # Chunk text
    metadata: dict[str, Any] = {},        # Metadata (inherits from document + chunk_index)
    embedding: list[float] | None = None, # Vector embedding (set after embed step)
)

# ScoredChunk -- a chunk with a retrieval score
ScoredChunk(
    id: str,
    document_id: str,
    content: str,
    metadata: dict[str, Any] = {},
    score: float = 0.0,                   # Retrieval relevance score
    embedding: list[float] | None = None,
)
```

Use `model_copy(update={...})` to create modified copies (Pydantic v2 pattern):

```python
updated = chunk.model_copy(update={"embedding": vector})
```

## LLM Abstractions

### Protocols (use with TYPE_CHECKING guard)

```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from provrag.llm.embedder import BaseEmbedder
    from provrag.llm.generator import BaseLLM

# BaseEmbedder protocol:
#   .model_name -> str
#   .embed_texts(texts: list[str]) -> list[list[float]]
#   .embed_query(text: str) -> list[float]

# BaseLLM protocol:
#   .model_name -> str
#   .generate(system_prompt: str, user_message: str) -> GenerateResult

# GenerateResult (frozen dataclass):
#   .response: str
#   .prompt_tokens: int | None
#   .completion_tokens: int | None
```

### Factory Functions

```python
from provrag.llm.factory import create_embedder, create_llm

embedder = create_embedder(settings)  # BedrockEmbedder if aws, OpenAIEmbedder if local
llm = create_llm(settings)            # BedrockLLM if aws, OpenAILLM if local
```

Never instantiate `BedrockEmbedder` or `OpenAILLM` directly -- always use the factory.

### Default Models

- Bedrock embedder: `amazon.titan-embed-text-v2:0` (1024 dims)
- Bedrock LLM: `anthropic.claude-3-sonnet-20240229-v1:0`
- OpenAI embedder: `text-embedding-3-small`
- OpenAI LLM: `gpt-4`

## OpenSearch Client

```python
from provrag.retrieval.opensearch_client import ProvragOpenSearchClient

os_client = ProvragOpenSearchClient(settings)

# Index management
os_client.create_index(index_name, dimension, engine="faiss", space_type="innerproduct",
                       ef_construction=256, m=48)  # Returns bool (False if exists)
os_client.delete_index(index_name)                  # Returns bool
os_client.list_indices()                             # Returns list[str]

# Indexing
os_client.bulk_index(index_name, chunks)             # Returns int (count indexed)

# Search
os_client.knn_search(index_name, query_vector, top_k=10)  # Returns list[ScoredChunk]

# Hybrid search (BM25 + k-NN)
os_client.create_hybrid_search_pipeline(
    pipeline_name, bm25_weight=0.3, knn_weight=0.7,
    normalization="min_max", combination="arithmetic_mean",
)
os_client.hybrid_search(
    index_name, query_text, query_vector, top_k=10,
    pipeline_name="hybrid-search-pipeline",
)  # Returns list[ScoredChunk]
```

## Built-in Steps

### Ingestion Steps

```python
from provrag.pipelines.ingestion import load_documents, chunk_documents, embed_chunks, index_chunks

load_documents(settings: Settings, prefix: str = "") -> list[Document]
chunk_documents(documents: list[Document], chunk_size: int = 512, chunk_overlap: int = 50) -> list[Chunk]
embed_chunks(chunks: list[Chunk], embedder: BaseEmbedder) -> list[Chunk]
index_chunks(chunks: list[Chunk], os_client: ProvragOpenSearchClient, index_name: str) -> int  # retries=3
```

### RAG Steps

```python
from provrag.pipelines.rag import embed_query, dense_retrieve, assemble_prompt, generate_answer

embed_query(query: str, embedder: BaseEmbedder) -> list[float]                    # span_kind="EMBEDDING"
dense_retrieve(query_vector: list[float], os_client, index_name, top_k=10)        # span_kind="RETRIEVER"
    -> list[ScoredChunk]
assemble_prompt(query: str, context: list[ScoredChunk]) -> str                    # span_kind="CHAIN"
generate_answer(query, assembled_prompt, llm, system_prompt=DEFAULT_SYSTEM_PROMPT) # span_kind="LLM"
    -> str
```

### Built-in RAG Pipeline

```python
from provrag.pipelines.rag import semantic_rag_pipeline
# Compose: embed_query -> dense_retrieve -> assemble_prompt -> generate_answer
```

## S3DocumentLoader

```python
from provrag.storage.s3 import S3DocumentLoader

loader = S3DocumentLoader(settings)
keys = loader.list_objects(prefix="pdfs/")      # list[str]
doc = loader.load_document(key)                  # Document (reads as UTF-8 text)
docs = loader.load_documents(prefix="")          # list[Document]

# Access the underlying boto3 client:
loader._client.get_object(Bucket=loader._bucket, Key=key)
```

## RecursiveCharacterChunker

```python
from provrag.chunking.text_chunker import RecursiveCharacterChunker

chunker = RecursiveCharacterChunker(chunk_size=512, chunk_overlap=50)
chunks = chunker.chunk(document)         # list[Chunk] from a single Document
chunks = chunker.chunk_batch(documents)  # list[Chunk] from multiple Documents
```

Separators tried in order: `["\n\n", "\n", ". ", " ", ""]`

## FastAPI App Factory

```python
from provrag.api import create_app

app = create_app(
    pipeline=rag_pipeline,       # The @pipeline function to serve
    name="my-project",           # App title
    path_prefix="/my-project",   # URL prefix
    **pipeline_kwargs,           # Passed to pipeline on each request
)
# Creates: GET {prefix}/health, POST {prefix}/query
```

## Tracing

```python
from provrag.tracing.setup import init_tracing

init_tracing(
    phoenix_endpoint="http://localhost:6006/v1/traces",
    project_name="my-project",
)
```

## Settings

```python
from provrag.settings import Settings, get_settings, Environment, LLMProvider

settings = get_settings()  # Cached singleton, reads PROVRAG_* env vars

settings.environment    # Environment.LOCAL or Environment.AWS
settings.llm_provider   # LLMProvider.BEDROCK or LLMProvider.OPENAI (auto-derived)
settings.is_local       # Computed: True if LOCAL
settings.debug          # bool
settings.log_level      # str: DEBUG|INFO|WARNING|ERROR|CRITICAL

settings.opensearch.host          # default: "localhost"
settings.opensearch.port          # default: 9200
settings.opensearch.use_ssl       # default: False
settings.opensearch.signing_host  # For SSM tunnel SigV4 signing

settings.s3.bucket                # default: "provrag-documents"
settings.s3.endpoint_url          # default: "http://localhost:9005" (MinIO)

settings.bedrock.embedding_model_id  # default: "amazon.titan-embed-text-v2:0"
settings.bedrock.llm_model_id        # default: "anthropic.claude-3-sonnet-20240229-v1:0"

settings.phoenix.endpoint         # default: "http://localhost:6006/v1/traces"
settings.phoenix.project_name     # default: "provrag"
```

Env var convention: `PROVRAG_` prefix, `__` for nesting. Example: `PROVRAG_OPENSEARCH__HOST=localhost`

For full settings reference, read `references/settings-reference.md`.

## Template-Generated Project Structure

After `provrag init`, the project has:

```
src/{package}/
  __init__.py       # Package version
  app.py            # FastAPI app using create_app(rag_pipeline, ...)
  pipeline.py       # RAG pipeline: embed_query -> dense_retrieve -> rerank -> assemble -> generate
  ingestion.py      # Ingestion pipeline: load_documents -> preprocess -> chunk -> embed -> index
  steps.py          # Custom steps: rerank (score-sort), preprocess (whitespace normalization)
tests/
  test_pipeline.py  # Pipeline registration test
  test_steps.py     # Step unit tests
  test_ingestion.py # Ingestion pipeline test (mocked)
pyproject.toml      # Dependencies (provrag from CodeArtifact)
Taskfile.yml        # Dev commands (setup, test, lint, serve, ingest, connect, disconnect, etc.)
.env                # PROVRAG_* environment variables
Dockerfile          # Multi-stage build for ECS deployment
infra/              # Pulumi infrastructure-as-code
.gitlab-ci.yml      # CI/CD pipeline
CLAUDE.md           # Developer guide
```

### Generated steps.py (starting point for customization)

```python
from __future__ import annotations
import re
from typing import TYPE_CHECKING
from provrag import step

if TYPE_CHECKING:
    from provrag.models.document import Document, ScoredChunk

@step(name="rerank", span_kind="CHAIN")
def rerank(chunks: list[ScoredChunk], query: str, top_k: int = 5) -> list[ScoredChunk]:
    return sorted(chunks, key=lambda c: c.score, reverse=True)[:top_k]

@step(name="preprocess", span_kind="CHAIN")
def preprocess(documents: list[Document]) -> list[Document]:
    cleaned: list[Document] = []
    for doc in documents:
        content = re.sub(r"\s+", " ", doc.content).strip()
        cleaned.append(doc.model_copy(update={"content": content}))
    return cleaned
```

### Generated pipeline.py

```python
from __future__ import annotations
from typing import TYPE_CHECKING, cast
from provrag import pipeline
from provrag.pipelines.rag import assemble_prompt, dense_retrieve, embed_query, generate_answer
from {package}.steps import rerank

if TYPE_CHECKING:
    from provrag.llm.embedder import BaseEmbedder
    from provrag.llm.generator import BaseLLM
    from provrag.retrieval.opensearch_client import ProvragOpenSearchClient

@pipeline(name="{slug}-rag")
def rag_pipeline(
    query: str, embedder: BaseEmbedder, llm: BaseLLM,
    os_client: ProvragOpenSearchClient,
    index_name: str = "{index}", top_k: int = 10,
) -> str:
    query_vector = embed_query(query=query, embedder=embedder)
    raw_chunks = dense_retrieve(query_vector=query_vector, os_client=os_client,
                                index_name=index_name, top_k=top_k * 2)
    reranked = rerank(chunks=raw_chunks, query=query, top_k=top_k)
    prompt = assemble_prompt(query=query, context=reranked)
    return cast("str", generate_answer(query=query, assembled_prompt=prompt, llm=llm))
```

### Generated ingestion.py

```python
from __future__ import annotations
from typing import TYPE_CHECKING, cast
from provrag import pipeline
from provrag.llm.factory import create_embedder
from provrag.pipelines.ingestion import chunk_documents, embed_chunks, index_chunks, load_documents
from provrag.retrieval.opensearch_client import ProvragOpenSearchClient
from {package}.steps import preprocess

if TYPE_CHECKING:
    from provrag.settings import Settings

@pipeline(name="{slug}-ingestion")
def ingest_pipeline(
    settings: Settings, index_name: str = "{index}",
    s3_prefix: str = "", chunk_size: int = 512,
    chunk_overlap: int = 50, dimension: int = 1024,
) -> int:
    embedder = create_embedder(settings)
    os_client = ProvragOpenSearchClient(settings)
    os_client.create_index(index_name, dimension=dimension)
    docs = load_documents(settings=settings, prefix=s3_prefix)
    cleaned = preprocess(documents=docs)
    chunks = chunk_documents(documents=cleaned, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    embedded = embed_chunks(chunks=chunks, embedder=embedder)
    return cast("int", index_chunks(chunks=embedded, os_client=os_client, index_name=index_name))
```

## Customization Patterns

For detailed recipes with complete implementations, read `references/customization-cookbook.md`.

Key customization points:

1. **Replace a step**: Write a new `@step` function in `steps.py`, swap the call in the pipeline
2. **Add a step**: Write a new `@step`, insert the call at the right position in the pipeline function
3. **Change retrieval**: Switch from `knn_search` to `hybrid_search` on the OpenSearch client
4. **Custom system prompt**: Pass `system_prompt=` parameter to `generate_answer`
5. **Different file types**: Replace `load_documents` with a custom loader step
6. **Add dependencies**: Edit `pyproject.toml`, run `uv sync --extra dev`

## Testing Patterns

```python
# Call .fn() to bypass Prefect wrapper
result = my_step.fn(data=["test"])

# Mock external services
from unittest.mock import MagicMock, patch

@patch("{package}.ingestion.ProvragOpenSearchClient")
@patch("{package}.ingestion.create_embedder")
@patch("provrag.pipelines.ingestion.S3DocumentLoader")
def test_ingest(mock_loader_cls, mock_embedder, mock_os):
    mock_loader = MagicMock()
    mock_loader_cls.return_value = mock_loader
    mock_loader.load_documents.return_value = [
        Document(id="d1", content="test content"),
    ]
    ...

# Settings in tests
from provrag.settings import Settings, Environment
settings = Settings(environment=Environment.LOCAL)
```

## Code Style

- Python 3.13: `str | None` not `Optional[str]`, `StrEnum` not `str, Enum`
- `from __future__ import annotations` at top of every file
- `TYPE_CHECKING` guards for protocol types (`BaseEmbedder`, `BaseLLM`, `ProvragOpenSearchClient`, `Settings`)
- Ruff formatting: line-length 120
- mypy strict mode
- No unnecessary comments or docstrings
- TDD: write failing test first, then implement
- Use `cast("str", ...)` for Prefect-wrapped return types

## CLI Reference

For full CLI commands and flags, read `references/cli-reference.md`.

Quick reference:
- `provrag init` -- Scaffold a new project
- `provrag ingest` -- Run ingestion pipeline
- `provrag serve` -- Start API server
- `provrag status` -- Check project lifecycle stage
- `provrag list` -- List OpenSearch indices
- `provrag clean --index <name> --yes` -- Delete an index

## ProRAG Installation

ProRAG is distributed via **AWS CodeArtifact**, not PyPI:

```bash
# In a generated project:
task ca:login    # Authenticates to CodeArtifact, writes token to .env
task setup       # Runs uv sync with CodeArtifact auth

# The pyproject.toml has a custom index:
# [[tool.uv.index]]
# name = "provrag"
# url = "https://provrag-257394491982.d.codeartifact.us-east-2.amazonaws.com/pypi/provrag/simple/"
```

## AWS Connectivity

For AWS environments, use SSM tunnels to access services behind VPC:

```bash
task connect      # Start SSM tunnels: OpenSearch :9200, Prefect :4200, Phoenix :6006, API :8080
task disconnect   # Kill all SSM tunnel sessions
```

Requires: AWS SSO login (`aws sso login --profile provectus-demos`), bastion host running.
