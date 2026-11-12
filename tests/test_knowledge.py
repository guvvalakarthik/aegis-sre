from __future__ import annotations

import pytest


def test_secret_content_is_rejected_before_chunking() -> None:
    from aegis_sre.knowledge import KnowledgeIndex, RestrictedContentError, SourceKind

    index = KnowledgeIndex()
    with pytest.raises(RestrictedContentError):
        index.ingest(
            content="password=super-secret",
            source_uri="https://example.test/runbook.md",
            source_kind=SourceKind.DOCUMENT,
            version="v1",
            commit="abc",
            environment="prod",
            timestamp="2026-01-01T00:00:00Z",
            acl={"operator"},
        )
    assert index.freshness().rejected_documents == 1


def test_reingest_is_idempotent_and_acl_is_enforced() -> None:
    from aegis_sre.knowledge import KnowledgeIndex, SourceKind

    index = KnowledgeIndex()
    args = dict(
        content="restart checkout service safely",
        source_uri="https://example.test/runbook.md",
        source_kind=SourceKind.DOCUMENT,
        version="v1",
        commit="abc",
        environment="prod",
        timestamp="2026-01-01T00:00:00Z",
        acl={"operator"},
    )
    first = index.ingest(**args)
    second = index.ingest(**args)
    assert first.document_id == second.document_id
    assert index.retrieve("restart", roles={"viewer"}) == []
    assert index.retrieve("restart", roles={"operator"})
    assert index.freshness().unchanged_documents == 1


def test_revocation_removes_retrieval() -> None:
    from aegis_sre.knowledge import KnowledgeIndex, SourceKind

    index = KnowledgeIndex()
    document = index.ingest(
        content="database rollback procedure",
        source_uri="https://example.test/runbook.md",
        source_kind=SourceKind.DOCUMENT,
        version="v1",
        commit="abc",
        environment="prod",
        timestamp="2026-01-01T00:00:00Z",
        acl={"operator"},
    )
    index.revoke(document.document_id)
    assert index.retrieve("rollback", roles={"operator"}) == []


def test_unsupported_binary_content_fails_closed() -> None:
    from aegis_sre.knowledge import KnowledgeIndex, SourceKind, UnsupportedContentError

    with pytest.raises(UnsupportedContentError):
        KnowledgeIndex().ingest(
            content="not a binary",
            source_uri="https://example.test/archive.zip",
            source_kind=SourceKind.DOCUMENT,
            version="v1",
            commit="abc",
            environment="prod",
            timestamp="now",
            acl={"operator"},
        )
