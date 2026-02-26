"""Tests for the search_index module (ChromaDB-backed semantic search).

Uses real ChromaDB (ephemeral) and real sentence-transformers -- no mocks.
"""

from __future__ import annotations

import pytest
from chromadb.api.models.Collection import Collection

from awos_recruitment_mcp.models.capability import RegistryCapability
from awos_recruitment_mcp.search_index import build_index, query

EMBEDDING_MODEL = "all-MiniLM-L6-v2"

SAMPLE_CAPABILITIES = [
    RegistryCapability(
        name="python-development",
        description="Expert Python programming including FastAPI, Django, and async patterns",
        type="skill",
    ),
    RegistryCapability(
        name="react-frontend",
        description="React and TypeScript frontend development with modern hooks and state management",
        type="skill",
    ),
    RegistryCapability(
        name="postgresql-database",
        description="PostgreSQL database administration, query optimization, and schema design",
        type="tool",
    ),
    RegistryCapability(
        name="kubernetes-ops",
        description="Kubernetes cluster management, container orchestration, and deployment pipelines",
        type="tool",
    ),
    RegistryCapability(
        name="pytest-testing",
        description="Automated testing with pytest including fixtures, parametrize, and coverage reports",
        type="skill",
    ),
    RegistryCapability(
        name="qa-automation-agent",
        description="Autonomous QA agent that writes and runs test suites for Python and TypeScript projects",
        type="agent",
    ),
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def sample_capabilities() -> list[RegistryCapability]:
    """A small, diverse set of capabilities for testing."""
    return list(SAMPLE_CAPABILITIES)


@pytest.fixture(scope="module")
def capabilities_collection() -> Collection:
    """Build a ChromaDB collection from the sample capabilities."""
    return build_index(SAMPLE_CAPABILITIES, embedding_model=EMBEDDING_MODEL)


# ---------------------------------------------------------------------------
# Build index — basic checks
# ---------------------------------------------------------------------------


class TestBuildIndex:
    """Given a list of RegistryCapability objects, build_index creates a
    collection and all items are queryable."""

    def test_collection_contains_all_items(
        self,
        capabilities_collection: Collection,
        sample_capabilities: list[RegistryCapability],
    ) -> None:
        assert capabilities_collection.count() == len(sample_capabilities)

    def test_all_ids_present(
        self,
        capabilities_collection: Collection,
        sample_capabilities: list[RegistryCapability],
    ) -> None:
        all_data = capabilities_collection.get()
        stored_ids = set(all_data["ids"])
        expected_ids = {cap.name for cap in sample_capabilities}
        assert stored_ids == expected_ids


# ---------------------------------------------------------------------------
# Query with relevant text
# ---------------------------------------------------------------------------


class TestQueryRelevant:
    """A query with relevant text returns results ranked by score."""

    def test_returns_results_for_relevant_query(
        self,
        capabilities_collection: Collection,
    ) -> None:
        results = query(capabilities_collection, "Python development")
        assert len(results) > 0

    def test_results_have_required_keys(
        self,
        capabilities_collection: Collection,
    ) -> None:
        results = query(capabilities_collection, "Python development")
        assert len(results) > 0
        for result in results:
            assert "name" in result
            assert "description" in result
            assert "score" in result

    def test_scores_are_integers_in_range(
        self,
        capabilities_collection: Collection,
    ) -> None:
        results = query(capabilities_collection, "Python development")
        for result in results:
            assert isinstance(result["score"], int)
            assert 0 <= result["score"] <= 100

    def test_results_ordered_by_score_descending(
        self,
        capabilities_collection: Collection,
    ) -> None:
        results = query(capabilities_collection, "Python development")
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_most_relevant_result_ranks_first(
        self,
        capabilities_collection: Collection,
    ) -> None:
        results = query(capabilities_collection, "Python development")
        assert len(results) > 0
        assert results[0]["name"] == "python-development"
        assert results[0]["score"] > 20


# ---------------------------------------------------------------------------
# Type filter
# ---------------------------------------------------------------------------


class TestTypeFilter:
    """A query with type_filter restricts results to that type."""

    def test_filter_skills_only(
        self,
        capabilities_collection: Collection,
    ) -> None:
        results = query(
            capabilities_collection,
            "programming",
            type_filter="skill",
        )
        for result in results:
            assert result["name"] in {
                "python-development",
                "react-frontend",
                "pytest-testing",
            }, f"Expected only skills, got {result['name']}"

    def test_filter_tools_only(
        self,
        capabilities_collection: Collection,
    ) -> None:
        results = query(
            capabilities_collection,
            "database management",
            type_filter="tool",
        )
        for result in results:
            assert result["name"] in {
                "postgresql-database",
                "kubernetes-ops",
            }, f"Expected only tools, got {result['name']}"

    def test_filter_agents_only(
        self,
        capabilities_collection: Collection,
    ) -> None:
        results = query(
            capabilities_collection,
            "testing automation",
            type_filter="agent",
        )
        for result in results:
            assert result["name"] in {
                "qa-automation-agent",
            }, f"Expected only agents, got {result['name']}"

    def test_filter_excludes_other_type(
        self,
        capabilities_collection: Collection,
    ) -> None:
        results = query(
            capabilities_collection,
            "Python programming",
            type_filter="tool",
        )
        skill_names = {"python-development", "react-frontend", "pytest-testing"}
        returned_names = {r["name"] for r in results}
        assert returned_names.isdisjoint(skill_names), (
            f"Skills should not appear with type_filter='tool': {returned_names & skill_names}"
        )


# ---------------------------------------------------------------------------
# Threshold filtering
# ---------------------------------------------------------------------------


class TestThresholdFiltering:
    """Results below the threshold score are excluded."""

    def test_high_threshold_reduces_results(
        self,
        capabilities_collection: Collection,
    ) -> None:
        low_threshold = query(
            capabilities_collection,
            "Python development",
            threshold=10,
        )
        high_threshold = query(
            capabilities_collection,
            "Python development",
            threshold=50,
        )
        assert len(high_threshold) <= len(low_threshold)

    def test_all_returned_scores_above_threshold(
        self,
        capabilities_collection: Collection,
    ) -> None:
        threshold = 30
        results = query(
            capabilities_collection,
            "Python development",
            threshold=threshold,
        )
        for result in results:
            assert result["score"] >= threshold, (
                f"Result {result['name']} has score {result['score']} "
                f"which is below threshold {threshold}"
            )

    def test_threshold_zero_returns_all(
        self,
        capabilities_collection: Collection,
        sample_capabilities: list[RegistryCapability],
    ) -> None:
        results = query(
            capabilities_collection,
            "Python development",
            threshold=0,
        )
        # With threshold=0 and n_results=10 (default), we should get all 5 items
        # because even low-scoring results will have score >= 0.
        assert len(results) == len(sample_capabilities)


# ---------------------------------------------------------------------------
# Unrelated query
# ---------------------------------------------------------------------------


class TestUnrelatedQuery:
    """A completely unrelated query returns an empty list."""

    def test_unrelated_query_returns_empty(
        self,
        capabilities_collection: Collection,
    ) -> None:
        results = query(
            capabilities_collection,
            "quantum cooking recipes for aliens on Mars",
            threshold=60,
        )
        assert results == [], (
            f"Expected empty list for unrelated query, got {len(results)} results: "
            f"{[r['name'] for r in results]}"
        )


# ---------------------------------------------------------------------------
# Build index — empty capabilities (placed last because build_index
# deletes and recreates the "capabilities" collection, which invalidates
# the module-scoped fixture used by tests above).
# ---------------------------------------------------------------------------


class TestBuildIndexEmpty:
    """Building an index from an empty list produces an empty collection."""

    def test_empty_capabilities_list(self) -> None:
        collection = build_index([], embedding_model=EMBEDDING_MODEL)
        assert collection.count() == 0
