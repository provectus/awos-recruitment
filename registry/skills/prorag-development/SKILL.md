---
name: prorag-development
description: >-
  Build and customize ProRAG applications. Use when scaffolding ProRAG projects,
  writing custom pipeline steps with @step/@pipeline decorators, modifying
  ingestion or RAG pipelines, configuring settings, writing tests, or operating
  the ProRAG lifecycle (ingest, serve, status, index management).
version: 0.1.0
---

# ProRAG Framework Development

Build, customize, and operate RAG applications using ProRAG — a Python framework for composable retrieval-augmented generation pipelines with OpenSearch, S3, and LLM abstractions.

## Core Architecture

- `@step` = Prefect `@task` + Phoenix OpenTelemetry tracing span
- `@pipeline` = Prefect `@flow`
- Steps are plain Python functions called inside pipeline functions
- Data flows through Python variables — no YAML, no DAG builder
- Settings use Pydantic v2 BaseSettings with `PROVRAG_*` env prefix

```python
from provrag.decorators import step, pipeline
from provrag.models import Document, Chunk

@step(span_kind="CHAIN")
def preprocess(docs: list[Document]) -> list[Document]:
    return [d.model_copy(update={"content": d.content.strip()}) for d in docs]

@pipeline
def my_ingestion(source: str) -> None:
    docs = load(source)
    docs = preprocess(docs)
    chunks = chunk(docs)
    embedded = embed(chunks)
    index(embedded)
```

## Data Models

```python
from provrag.models import Document, Chunk, ScoredChunk

# Document — raw content with metadata
doc = Document(content="...", metadata={"source": "file.pdf"})

# Chunk — split document with embeddings
chunk = Chunk(content="...", metadata={}, embedding=[0.1, 0.2, ...])

# ScoredChunk — retrieval result with relevance score
scored = ScoredChunk(content="...", metadata={}, score=0.95)
```

Use `model_copy(update={...})` to create modified copies (immutable pattern).

## LLM Abstractions

```python
from provrag.llm import create_embedder, create_llm

embedder = create_embedder()  # Auto-selects based on environment
llm = create_llm()            # OpenAI locally, Bedrock on AWS
```

Protocols: `BaseEmbedder` (embed method) and `BaseLLM` (generate method). Factory functions select provider based on `PROVRAG_ENVIRONMENT`:
- `local` → OpenAI
- `aws` → Amazon Bedrock (Titan Embed v2, Claude 3 Sonnet)

## Settings System

Pydantic v2 BaseSettings with `PROVRAG_*` prefix and `__` nested delimiter:

```bash
# Core
PROVRAG_ENVIRONMENT=local          # local | aws
PROVRAG_DEBUG=false
PROVRAG_LOG_LEVEL=INFO

# OpenSearch
PROVRAG_OPENSEARCH__HOST=localhost
PROVRAG_OPENSEARCH__PORT=9200

# S3 / MinIO
PROVRAG_S3__ENDPOINT_URL=http://localhost:9005  # null for AWS
PROVRAG_S3__BUCKET=provrag-documents

# Bedrock (AWS only)
PROVRAG_BEDROCK__REGION=us-east-2
PROVRAG_BEDROCK__EMBEDDING_MODEL=amazon.titan-embed-text-v2:0
```

## CLI Operations

```bash
provrag init --name my-project     # Scaffold new project
provrag ingest --index my-index    # Run ingestion pipeline
provrag serve --port 8000          # Start FastAPI server
provrag status                     # Check lifecycle stage
provrag list                       # List indices
provrag clean --index my-index     # Delete index (permanent!)
```

Taskfile commands: `task setup`, `task test`, `task lint`, `task check`, `task serve`, `task ingest`, `task connect` (SSM tunnel to AWS VPC).

## Code Style

- Python 3.13: `str | None`, `StrEnum`, `from __future__ import annotations`
- `TYPE_CHECKING` guards for protocol imports
- Ruff (line-length 120), mypy strict
- No unnecessary comments or docstrings
- TDD: write failing test first, then implement

## Testing

Use `.fn()` to bypass Prefect wrappers in tests:

```python
def test_preprocess():
    docs = [Document(content="  hello  ", metadata={})]
    result = preprocess.fn(docs)  # .fn() skips Prefect/OTEL
    assert result[0].content == "hello"
```

## Customization Recipes

Detailed implementation patterns in `references/customization-cookbook.md`:
- PDF ingestion with pymupdf4llm
- Cross-encoder reranking with SentenceTransformers
- Hybrid search (BM25 + semantic)
- Custom system prompts
- Custom chunking strategies
- Metadata enrichment
- Mixed file type ingestion
- Query expansion with LLM

## Deep Dives

| Topic | Reference |
|---|---|
| Full API: imports, decorators, models, built-in steps | `references/api-reference.md` |
| CLI commands, Taskfile, installation, AWS connectivity | `references/cli-reference.md` |
| PROVRAG_* environment variables and configuration | `references/settings-reference.md` |
| Implementation recipes (PDF, reranking, hybrid search) | `references/customization-cookbook.md` |
