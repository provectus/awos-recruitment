"""Search index backed by ChromaDB for semantic capability discovery."""

from __future__ import annotations

import chromadb
from chromadb.api.collection_configuration import CreateCollectionConfiguration, HNSWConfiguration
from chromadb.api.models.Collection import Collection
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

from awos_recruitment_mcp.models.capability import RegistryCapability


def build_index(
    capabilities: list[RegistryCapability],
) -> Collection:
    """Build an in-memory ChromaDB collection from *capabilities*.

    Creates an ephemeral ChromaDB client, initialises a ``"capabilities"``
    collection using the default ONNX-based embedding function
    (``all-MiniLM-L6-v2``), and populates it with all provided capabilities.

    Args:
        capabilities: Registry capabilities to index.

    Returns:
        The populated :class:`chromadb.Collection` ready for querying.
    """
    embedding_fn = DefaultEmbeddingFunction()

    client = chromadb.EphemeralClient()

    # Drop any stale collection so we always start with a clean slate.
    # EphemeralClient() may return the same underlying client within a
    # single process, so an old collection could still be present.
    try:
        client.delete_collection(name="capabilities")
    except Exception:  # noqa: BLE001 — collection may not exist
        pass

    collection = client.create_collection(
        name="capabilities",
        embedding_function=embedding_fn,
        configuration=CreateCollectionConfiguration(
            hnsw=HNSWConfiguration(space="cosine"),
        ),
    )

    if not capabilities:
        return collection

    collection.add(
        ids=[cap.name for cap in capabilities],
        documents=[cap.description for cap in capabilities],
        metadatas=[{"name": cap.name, "type": cap.type} for cap in capabilities],
    )

    return collection


def query(
    collection: Collection,
    query_text: str,
    n_results: int = 10,
    type_filter: str | None = None,
    threshold: int = 20,
) -> list[dict]:
    """Query the capability index for semantically similar results.

    Args:
        collection: A ChromaDB collection built by :func:`build_index`.
        query_text: Free-text search query.
        n_results: Maximum number of results to request from ChromaDB.
        type_filter: If provided, restrict results to this capability type
            (``"skill"``, ``"tool"``, ``"agent"``, or ``"hook"``).
        threshold: Minimum similarity score (0--100). Results scoring below
            this value are excluded.

    Returns:
        A list of dicts with keys ``"name"``, ``"type"`` (``"skill"``,
        ``"tool"``, ``"agent"``, or ``"hook"``), ``"description"``, and
        ``"score"`` (int, 0--100), ordered by score descending. The caller
        needs ``"type"`` to pick the install command for a result.
    """
    query_kwargs: dict = {
        "query_texts": [query_text],
        "n_results": n_results,
    }

    if type_filter is not None:
        query_kwargs["where"] = {"type": type_filter}

    raw = collection.query(**query_kwargs)

    # ChromaDB returns nested lists (one per query text).  We always
    # supply a single query, so we unpack the outer list.
    ids: list[str] = raw["ids"][0]
    documents: list[str] = raw["documents"][0]
    distances: list[float] = raw["distances"][0]
    metadatas: list[dict] = raw["metadatas"][0]

    results: list[dict] = []
    for doc_id, document, distance, metadata in zip(ids, documents, distances, metadatas):
        score = round((1 - distance) * 100)
        if score < threshold:
            continue
        results.append(
            {
                "name": doc_id,
                "type": metadata["type"],
                "description": document,
                "score": score,
            }
        )

    # Ensure results are ordered by score descending.
    results.sort(key=lambda r: r["score"], reverse=True)

    return results
