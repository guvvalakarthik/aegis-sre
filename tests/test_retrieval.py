from __future__ import annotations

import pytest


def evidence():
    from aegis_sre.retrieval import Evidence

    return [
        Evidence("public", "checkout timeout remediation", "https://docs/public.md", "v1",
                 "checkout", "prod", "2026-01-01T00:00:00Z", frozenset({"operator"})),
        Evidence("secret", "checkout password rotation", "https://docs/secret.md", "v1",
                 "checkout", "prod", "2026-01-01T00:00:00Z", frozenset({"admin"})),
    ]


def test_acl_is_applied_before_keyword_results() -> None:
    from aegis_sre.retrieval import HybridRetriever, KeywordBackend

    results, _ = HybridRetriever(KeywordBackend(evidence()), None, index_size=2).retrieve(
        "checkout", roles={"operator"}
    )
    assert [item.evidence.evidence_id for item in results] == ["public"]


def test_vector_backend_fallback_is_recorded() -> None:
    from aegis_sre.retrieval import HybridRetriever, KeywordBackend

    def broken(_: str) -> tuple[float, ...]:
        raise RuntimeError("embedding unavailable")

    results, trace = HybridRetriever(
        KeywordBackend(evidence()), __import__("aegis_sre.retrieval", fromlist=["VectorBackend"]).VectorBackend(
            evidence(), broken
        ), index_size=2,
    ).retrieve("checkout", roles={"operator"})
    assert results
    assert trace.fallback_used is True
    assert trace.vector_available is False


def test_filters_and_empty_results() -> None:
    from aegis_sre.retrieval import HybridRetriever, KeywordBackend, RetrievalFilters

    results, trace = HybridRetriever(KeywordBackend(evidence()), None, index_size=2).retrieve(
        "does-not-exist", roles={"operator"}, filters=RetrievalFilters(services=frozenset({"payments"}))
    )
    assert results == []
    assert trace.returned_count == 0


def test_query_is_bounded_and_roles_required() -> None:
    from aegis_sre.retrieval import HybridRetriever, KeywordBackend

    with pytest.raises(PermissionError):
        HybridRetriever(KeywordBackend(evidence()), None, index_size=2).retrieve("x", roles=set())
