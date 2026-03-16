# ProRAG Customization Cookbook

Concrete recipes for customizing ProRAG-generated projects. Each recipe shows what to modify, the implementation, dependencies to add, and how to test.

## Recipe: PDF Ingestion

Replace the default text-based `load_documents` step with PDF parsing.

### What to modify

- `src/{package}/steps.py` -- Add `load_pdfs` step
- `src/{package}/ingestion.py` -- Replace `load_documents` with `load_pdfs`
- `pyproject.toml` -- Add `pymupdf4llm` dependency
- `tests/test_steps.py` -- Add `load_pdfs` tests

### Implementation

```python
# steps.py -- add this step

import hashlib
import tempfile
from pathlib import Path

from provrag import step
from provrag.storage.s3 import S3DocumentLoader

if TYPE_CHECKING:
    from provrag.models.document import Document
    from provrag.settings import Settings


@step(name="load-pdfs", span_kind="CHAIN")
def load_pdfs(settings: Settings, prefix: str = "") -> list[Document]:
    import pymupdf4llm

    loader = S3DocumentLoader(settings)
    keys = loader.list_objects(prefix=prefix)

    documents: list[Document] = []
    for key in keys:
        if not key.lower().endswith(".pdf"):
            continue
        response = loader._client.get_object(Bucket=loader._bucket, Key=key)
        pdf_bytes = response["Body"].read()

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name

        try:
            md_text = pymupdf4llm.to_markdown(tmp_path)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        doc_id = hashlib.sha256(key.encode()).hexdigest()[:16]
        documents.append(Document(
            id=doc_id,
            content=md_text,
            metadata={"s3_key": key, "s3_bucket": loader._bucket, "source_type": "pdf"},
        ))

    return documents
```

### Ingestion pipeline update

```python
# ingestion.py -- swap load_documents for load_pdfs

from {package}.steps import load_pdfs, preprocess

@pipeline(name="{slug}-ingestion")
def ingest_pipeline(settings: Settings, ...) -> int:
    ...
    docs = load_pdfs(settings=settings, prefix=s3_prefix)  # Changed
    cleaned = preprocess(documents=docs)
    ...
```

### Dependencies

```bash
uv add pymupdf4llm
```

### Test

```python
def test_load_pdfs_filters_non_pdf(self) -> None:
    mock_loader = MagicMock()
    mock_loader.list_objects.return_value = ["doc.pdf", "readme.txt", "data.pdf"]
    # ... assert only .pdf files are processed
```

---

## Recipe: Cross-Encoder Reranking

Replace the naive score-sort rerank with a cross-encoder model.

### What to modify

- `src/{package}/steps.py` -- Replace `rerank` implementation
- `pyproject.toml` -- Add `sentence-transformers` dependency
- `tests/test_steps.py` -- Update rerank tests

### Implementation

```python
# steps.py -- replace the rerank step

@step(name="cross-encoder-rerank", span_kind="CHAIN")
def rerank(chunks: list[ScoredChunk], query: str, top_k: int = 5) -> list[ScoredChunk]:
    from sentence_transformers import CrossEncoder

    if not chunks:
        return []

    model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    pairs = [(query, chunk.content) for chunk in chunks]
    scores = model.predict(pairs)

    scored = [
        chunk.model_copy(update={"score": float(score)})
        for chunk, score in zip(chunks, scores, strict=True)
    ]
    scored.sort(key=lambda c: c.score, reverse=True)
    return scored[:top_k]
```

### Dependencies

```bash
uv add sentence-transformers
```

### Performance note

The CrossEncoder model loads on first call (~200ms). For production, cache at module level:

```python
_RERANKER: CrossEncoder | None = None

def _get_reranker() -> CrossEncoder:
    global _RERANKER
    if _RERANKER is None:
        from sentence_transformers import CrossEncoder
        _RERANKER = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    return _RERANKER

@step(name="cross-encoder-rerank", span_kind="CHAIN")
def rerank(chunks: list[ScoredChunk], query: str, top_k: int = 5) -> list[ScoredChunk]:
    if not chunks:
        return []
    model = _get_reranker()
    ...
```

### Alternative cross-encoder models

| Model | Speed | Quality | Use case |
|-------|-------|---------|----------|
| `cross-encoder/ms-marco-MiniLM-L-6-v2` | Fast | Good | General purpose |
| `cross-encoder/ms-marco-MiniLM-L-12-v2` | Medium | Better | Higher quality |
| `BAAI/bge-reranker-base` | Medium | Good | Multilingual |
| `BAAI/bge-reranker-large` | Slow | Best | Maximum quality |

### Test

```python
def test_rerank_uses_cross_encoder(self) -> None:
    with patch("{package}.steps.CrossEncoder") as mock_ce:
        mock_model = MagicMock()
        mock_ce.return_value = mock_model
        mock_model.predict.return_value = [0.9, 0.1, 0.5]

        chunks = [
            ScoredChunk(id="1", document_id="d1", content="relevant", score=0.0),
            ScoredChunk(id="2", document_id="d1", content="irrelevant", score=0.0),
            ScoredChunk(id="3", document_id="d1", content="somewhat", score=0.0),
        ]
        result = rerank.fn(chunks=chunks, query="test", top_k=2)

        assert len(result) == 2
        assert result[0].score == 0.9
        assert result[1].score == 0.5
```

---

## Recipe: Hybrid Search (BM25 + Semantic)

Replace dense-only retrieval with hybrid search combining BM25 lexical and k-NN semantic search.

### What to modify

- `src/{package}/steps.py` -- Add `hybrid_retrieve` step and `setup_hybrid_pipeline` step
- `src/{package}/pipeline.py` -- Replace `dense_retrieve` with `hybrid_retrieve`
- `src/{package}/ingestion.py` -- Add hybrid pipeline setup after index creation

### Implementation

```python
# steps.py -- add hybrid retrieval steps

@step(name="setup-hybrid-pipeline", span_kind="CHAIN")
def setup_hybrid_pipeline(
    os_client: ProvragOpenSearchClient,
    pipeline_name: str = "hybrid-search-pipeline",
    bm25_weight: float = 0.3,
    knn_weight: float = 0.7,
) -> str:
    os_client.create_hybrid_search_pipeline(
        pipeline_name=pipeline_name,
        bm25_weight=bm25_weight,
        knn_weight=knn_weight,
    )
    return pipeline_name


@step(name="hybrid-retrieve", span_kind="RETRIEVER")
def hybrid_retrieve(
    query: str,
    query_vector: list[float],
    os_client: ProvragOpenSearchClient,
    index_name: str,
    top_k: int = 10,
    pipeline_name: str = "hybrid-search-pipeline",
) -> list[ScoredChunk]:
    return os_client.hybrid_search(
        index_name=index_name,
        query_text=query,
        query_vector=query_vector,
        top_k=top_k,
        pipeline_name=pipeline_name,
    )
```

### Pipeline update

```python
# pipeline.py -- use hybrid_retrieve

from {package}.steps import rerank, hybrid_retrieve

@pipeline(name="{slug}-rag")
def rag_pipeline(
    query: str, embedder: BaseEmbedder, llm: BaseLLM,
    os_client: ProvragOpenSearchClient,
    index_name: str = "{index}", top_k: int = 10,
) -> str:
    query_vector = embed_query(query=query, embedder=embedder)
    raw_chunks = hybrid_retrieve(
        query=query,
        query_vector=query_vector,
        os_client=os_client,
        index_name=index_name,
        top_k=top_k * 2,
    )
    reranked = rerank(chunks=raw_chunks, query=query, top_k=top_k)
    prompt = assemble_prompt(query=query, context=reranked)
    return cast("str", generate_answer(query=query, assembled_prompt=prompt, llm=llm))
```

### Ingestion pipeline update

Add hybrid pipeline setup after index creation:

```python
# ingestion.py -- add setup_hybrid_pipeline after create_index

from {package}.steps import preprocess, setup_hybrid_pipeline

@pipeline(name="{slug}-ingestion")
def ingest_pipeline(settings: Settings, ...) -> int:
    embedder = create_embedder(settings)
    os_client = ProvragOpenSearchClient(settings)
    os_client.create_index(index_name, dimension=dimension)
    setup_hybrid_pipeline(os_client=os_client)  # Add this
    docs = load_documents(settings=settings, prefix=s3_prefix)
    ...
```

---

## Recipe: Custom System Prompt

Override the default RAG system prompt for domain-specific responses.

### What to modify

- `src/{package}/pipeline.py` -- Add custom system prompt

### Implementation

```python
# pipeline.py -- add custom system prompt

SYSTEM_PROMPT = """\
You are a legal research assistant for Acme Corp.
Answer questions based only on the provided context from company legal documents.
Always cite the source document by its metadata s3_key.
If the context does not contain an answer, say "I could not find this in the provided documents."
Never provide legal advice -- only summarize what the documents say.
"""

@pipeline(name="{slug}-rag")
def rag_pipeline(
    query: str, embedder: BaseEmbedder, llm: BaseLLM,
    os_client: ProvragOpenSearchClient,
    index_name: str = "{index}", top_k: int = 10,
) -> str:
    query_vector = embed_query(query=query, embedder=embedder)
    raw_chunks = dense_retrieve(
        query_vector=query_vector, os_client=os_client,
        index_name=index_name, top_k=top_k * 2,
    )
    reranked = rerank(chunks=raw_chunks, query=query, top_k=top_k)
    prompt = assemble_prompt(query=query, context=reranked)
    return cast("str", generate_answer(
        query=query,
        assembled_prompt=prompt,
        llm=llm,
        system_prompt=SYSTEM_PROMPT,  # Override default
    ))
```

---

## Recipe: Custom Chunking Strategy

Replace recursive character chunking with a domain-specific strategy.

### Sentence-based chunking

```python
# steps.py

@step(name="sentence-chunk", span_kind="CHAIN")
def sentence_chunk(
    documents: list[Document],
    sentences_per_chunk: int = 5,
    overlap_sentences: int = 1,
) -> list[Chunk]:
    import re
    all_chunks: list[Chunk] = []
    for doc in documents:
        sentences = re.split(r'(?<=[.!?])\s+', doc.content)
        for i in range(0, len(sentences), sentences_per_chunk - overlap_sentences):
            chunk_sentences = sentences[i:i + sentences_per_chunk]
            if not chunk_sentences:
                continue
            content = " ".join(chunk_sentences)
            chunk_id = hashlib.sha256(f"{doc.id}:{i}".encode()).hexdigest()[:16]
            all_chunks.append(Chunk(
                id=chunk_id,
                document_id=doc.id,
                content=content,
                metadata={**doc.metadata, "chunk_index": i},
            ))
    return all_chunks
```

Then replace `chunk_documents` in the ingestion pipeline:

```python
# ingestion.py
from {package}.steps import preprocess, sentence_chunk

@pipeline(name="{slug}-ingestion")
def ingest_pipeline(settings: Settings, ...) -> int:
    ...
    docs = load_documents(settings=settings, prefix=s3_prefix)
    cleaned = preprocess(documents=docs)
    chunks = sentence_chunk(documents=cleaned, sentences_per_chunk=5)  # Changed
    embedded = embed_chunks(chunks=chunks, embedder=embedder)
    ...
```

### Markdown-aware chunking

For documents that are already markdown (e.g., from PDF-to-markdown conversion):

```python
@step(name="markdown-chunk", span_kind="CHAIN")
def markdown_chunk(
    documents: list[Document],
    chunk_size: int = 512,
    chunk_overlap: int = 50,
) -> list[Chunk]:
    """Split on markdown headers first, then by size."""
    import re
    all_chunks: list[Chunk] = []
    for doc in documents:
        sections = re.split(r'\n(?=#{1,3}\s)', doc.content)
        chunker = RecursiveCharacterChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        for section in sections:
            if not section.strip():
                continue
            section_doc = doc.model_copy(update={"content": section})
            all_chunks.extend(chunker.chunk(section_doc))
    return all_chunks
```

---

## Recipe: Metadata Enrichment

Add document-level metadata before chunking for better filtering.

```python
@step(name="enrich-metadata", span_kind="CHAIN")
def enrich_metadata(documents: list[Document]) -> list[Document]:
    enriched: list[Document] = []
    for doc in documents:
        key = doc.metadata.get("s3_key", "")
        # Extract category from S3 path: docs/legal/contract.pdf -> "legal"
        parts = key.split("/")
        category = parts[1] if len(parts) > 2 else "general"

        enriched.append(doc.model_copy(update={
            "metadata": {
                **doc.metadata,
                "category": category,
                "char_count": len(doc.content),
                "word_count": len(doc.content.split()),
            },
        }))
    return enriched
```

Insert in ingestion pipeline after loading, before preprocessing:

```python
docs = load_documents(settings=settings, prefix=s3_prefix)
docs = enrich_metadata(documents=docs)  # Add this
cleaned = preprocess(documents=docs)
```

---

## Recipe: Mixed File Type Ingestion

Handle both PDF and text files in a single ingestion pipeline.

```python
@step(name="load-mixed-documents", span_kind="CHAIN")
def load_mixed_documents(settings: Settings, prefix: str = "") -> list[Document]:
    import pymupdf4llm

    loader = S3DocumentLoader(settings)
    keys = loader.list_objects(prefix=prefix)
    documents: list[Document] = []

    for key in keys:
        if key.lower().endswith(".pdf"):
            response = loader._client.get_object(Bucket=loader._bucket, Key=key)
            pdf_bytes = response["Body"].read()
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(pdf_bytes)
                tmp_path = tmp.name
            try:
                content = pymupdf4llm.to_markdown(tmp_path)
            finally:
                Path(tmp_path).unlink(missing_ok=True)
            source_type = "pdf"
        elif key.lower().endswith((".txt", ".md", ".csv")):
            response = loader._client.get_object(Bucket=loader._bucket, Key=key)
            content = response["Body"].read().decode("utf-8")
            source_type = "text"
        else:
            continue

        doc_id = hashlib.sha256(key.encode()).hexdigest()[:16]
        documents.append(Document(
            id=doc_id,
            content=content,
            metadata={"s3_key": key, "s3_bucket": loader._bucket, "source_type": source_type},
        ))

    return documents
```

---

## Recipe: Query Expansion

Add a query expansion step before embedding for better retrieval coverage.

```python
@step(name="expand-query", span_kind="LLM")
def expand_query(query: str, llm: BaseLLM) -> str:
    system_prompt = (
        "You are a query expansion assistant. Given a user question, "
        "generate 3 alternative phrasings separated by newlines. "
        "Return ONLY the alternative queries, no numbering or explanation."
    )
    result = llm.generate(system_prompt=system_prompt, user_message=query)
    expanded = f"{query}\n{result.response}"
    return expanded
```

Use in the RAG pipeline before embedding:

```python
@pipeline(name="{slug}-rag")
def rag_pipeline(query, embedder, llm, os_client, index_name, top_k=10):
    expanded = expand_query(query=query, llm=llm)
    # Embed the original query for vector search
    query_vector = embed_query(query=query, embedder=embedder)
    # Use expanded query for hybrid text search
    raw_chunks = hybrid_retrieve(
        query=expanded,
        query_vector=query_vector,
        os_client=os_client,
        index_name=index_name,
        top_k=top_k * 2,
    )
    ...
```

---

## General Pattern: Adding a New Step

Template for any new step:

```python
from __future__ import annotations
from typing import TYPE_CHECKING
from provrag import step

if TYPE_CHECKING:
    # Import types only for type checking
    from provrag.models.document import Document, ScoredChunk

@step(name="my-step-name", span_kind="CHAIN")
def my_step(input_data: InputType, param: str = "default") -> OutputType:
    # Transform data
    result = ...
    return result
```

Then insert the call in the appropriate pipeline function at the right position.

`span_kind` choices:
- `"CHAIN"` -- general transformation (default)
- `"EMBEDDING"` -- embedding operation
- `"RETRIEVER"` -- search/retrieval operation
- `"LLM"` -- language model call
