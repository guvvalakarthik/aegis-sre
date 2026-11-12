"""Versioned, access-controlled knowledge ingestion primitives."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable


class UnsupportedContentError(ValueError):
    pass


class RestrictedContentError(ValueError):
    pass


class SourceKind(StrEnum):
    REPOSITORY = "repository"
    DOCUMENT = "document"
    INCIDENT = "incident"
    API = "api"


_SECRET = re.compile(
    r"(?i)(?:-----begin [^-]+ key-----|\b(?:password|passwd|secret|api[_-]?key|"
    r"access[_-]?token|authorization)\s*[:=]\s*\S+)"
)
_ALLOWED_SUFFIXES = frozenset({".md", ".txt", ".rst", ".py", ".yaml", ".yml", ".json", ".toml"})


@dataclass(frozen=True)
class Document:
    document_id: str
    source_uri: str
    source_kind: SourceKind
    version: str
    commit: str
    environment: str
    timestamp: str
    acl: frozenset[str]
    content_hash: str
    active: bool = True


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    document_id: str
    ordinal: int
    text: str
    source_uri: str
    version: str
    commit: str
    environment: str
    timestamp: str
    acl: frozenset[str]
    parent_id: str | None


@dataclass(frozen=True)
class FreshnessReport:
    active_documents: int
    active_chunks: int
    revoked_documents: int
    rejected_documents: int
    unchanged_documents: int


def _canonical_document_id(source_uri: str, version: str, content_hash: str) -> str:
    return hashlib.sha256(f"{source_uri}\0{version}\0{content_hash}".encode()).hexdigest()


def _chunk_id(document_id: str, ordinal: int, text: str) -> str:
    return hashlib.sha256(f"{document_id}\0{ordinal}\0{text}".encode()).hexdigest()


def validate_source(source_uri: str, source_kind: SourceKind) -> None:
    if not source_uri or "://" not in source_uri:
        raise ValueError("source_uri must be an absolute URI")
    if source_kind == SourceKind.REPOSITORY and not source_uri.startswith(("git://", "https://")):
        raise ValueError("repository sources must use git:// or https://")


def sanitize_content(content: str, source_uri: str) -> str:
    if not isinstance(content, str) or "\x00" in content:
        raise UnsupportedContentError("binary content is not supported")
    suffix = "." + source_uri.rsplit(".", 1)[-1].lower() if "." in source_uri.rsplit("/", 1)[-1] else ""
    if suffix not in _ALLOWED_SUFFIXES:
        raise UnsupportedContentError(f"unsupported content format: {suffix or 'unknown'}")
    if _SECRET.search(content):
        raise RestrictedContentError("secret-like content is excluded before indexing")
    return content.replace("\r\n", "\n").replace("\r", "\n")


def chunk_content(content: str, *, size: int = 1200, overlap: int = 120) -> list[str]:
    if size < 1 or overlap < 0 or overlap >= size:
        raise ValueError("invalid chunk size or overlap")
    chunks: list[str] = []
    start = 0
    while start < len(content):
        end = min(len(content), start + size)
        chunks.append(content[start:end])
        if end == len(content):
            break
        start = end - overlap
    return chunks


class KnowledgeIndex:
    """Small deterministic index contract; embedding/vector storage is an adapter boundary."""

    def __init__(self) -> None:
        self._documents: dict[str, Document] = {}
        self._chunks: dict[str, Chunk] = {}
        self._source_versions: dict[tuple[str, str], str] = {}
        self._rejected = 0
        self._unchanged = 0

    def ingest(
        self,
        *,
        content: str,
        source_uri: str,
        source_kind: SourceKind,
        version: str,
        commit: str,
        environment: str,
        timestamp: str,
        acl: Iterable[str],
        parent_id: str | None = None,
    ) -> Document:
        validate_source(source_uri, source_kind)
        if not version or not commit or not environment or not timestamp:
            raise ValueError("version, commit, environment, and timestamp are required")
        roles = frozenset(role for role in acl if role)
        if not roles:
            raise PermissionError("ACL must contain at least one role")
        try:
            normalized = sanitize_content(content, source_uri)
        except (UnsupportedContentError, RestrictedContentError):
            self._rejected += 1
            raise
        content_hash = hashlib.sha256(normalized.encode()).hexdigest()
        key = (source_uri, version)
        existing_id = self._source_versions.get(key)
        if existing_id is not None:
            existing = self._documents[existing_id]
            if existing.content_hash == content_hash and existing.active:
                self._unchanged += 1
                return existing
            self.revoke(existing_id)
        document_id = _canonical_document_id(source_uri, version, content_hash)
        document = Document(
            document_id=document_id, source_uri=source_uri, source_kind=source_kind,
            version=version, commit=commit, environment=environment,
            timestamp=timestamp, acl=roles, content_hash=content_hash,
        )
        self._documents[document_id] = document
        self._source_versions[key] = document_id
        for ordinal, text in enumerate(chunk_content(normalized)):
            chunk_id = _chunk_id(document_id, ordinal, text)
            self._chunks[chunk_id] = Chunk(
                chunk_id=chunk_id, document_id=document_id, ordinal=ordinal, text=text,
                source_uri=source_uri, version=version, commit=commit,
                environment=environment, timestamp=timestamp, acl=roles, parent_id=parent_id,
            )
        return document

    def revoke(self, document_id: str) -> None:
        document = self._documents.get(document_id)
        if document is None:
            return
        self._documents[document_id] = Document(**{**document.__dict__, "active": False})
        for chunk_id, chunk in list(self._chunks.items()):
            if chunk.document_id == document_id:
                del self._chunks[chunk_id]

    def delete_source(self, source_uri: str) -> None:
        for document in list(self._documents.values()):
            if document.source_uri == source_uri and document.active:
                self.revoke(document.document_id)

    def retrieve(self, query: str, *, roles: Iterable[str], limit: int = 10) -> list[Chunk]:
        if not query or limit < 1:
            raise ValueError("query and positive limit are required")
        caller_roles = frozenset(roles)
        terms = set(query.lower().split())
        if not terms:
            return []
        visible = [
            chunk for chunk in self._chunks.values()
            if chunk.acl.intersection(caller_roles)
            and terms.intersection(chunk.text.lower().split())
        ]
        visible.sort(key=lambda chunk: (-len(terms.intersection(chunk.text.lower().split())), chunk.chunk_id))
        return visible[:limit]

    def freshness(self) -> FreshnessReport:
        active = [doc for doc in self._documents.values() if doc.active]
        return FreshnessReport(
            active_documents=len(active),
            active_chunks=len(self._chunks),
            revoked_documents=sum(not doc.active for doc in self._documents.values()),
            rejected_documents=self._rejected,
            unchanged_documents=self._unchanged,
        )
