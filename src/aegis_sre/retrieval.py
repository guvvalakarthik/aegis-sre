"""Deterministic ACL-aware hybrid retrieval contracts."""

from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass
from typing import Callable, Iterable, Protocol


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    text: str
    source_uri: str
    version: str
    service: str
    environment: str
    timestamp: str
    acl: frozenset[str]
    embedding: tuple[float, ...] = ()


@dataclass(frozen=True)
class RetrievalFilters:
    services: frozenset[str] = frozenset()
    environments: frozenset[str] = frozenset()
    start_timestamp: str | None = None
    end_timestamp: str | None = None


@dataclass(frozen=True)
class RetrievalResult:
    evidence: Evidence
    score: float
    keyword_score: float
    vector_score: float
    rank: int


@dataclass(frozen=True)
class RetrievalTrace:
    query: str
    subqueries: tuple[str, ...]
    keyword_available: bool
    vector_available: bool
    fallback_used: bool
    candidate_count: int
    returned_count: int
    latency_ms: float
    index_size: int
    embedding_cost: float | None


class RetrievalBackend(Protocol):
    def search(
        self, query: str, *, roles: frozenset[str], filters: RetrievalFilters, limit: int
    ) -> list[tuple[Evidence, float]]:
        ...


def _visible(evidence: Evidence, roles: frozenset[str], filters: RetrievalFilters) -> bool:
    if not evidence.acl.intersection(roles):
        return False
    if filters.services and evidence.service not in filters.services:
        return False
    if filters.environments and evidence.environment not in filters.environments:
        return False
    if filters.start_timestamp and evidence.timestamp < filters.start_timestamp:
        return False
    return not (filters.end_timestamp and evidence.timestamp > filters.end_timestamp)


def _terms(query: str) -> list[str]:
    return re.findall(r"[a-z0-9_:-]+", query.lower())[:64]


class KeywordBackend:
    """BM25-style in-memory backend; ACL and metadata filters run before scoring."""

    def __init__(self, evidence: Iterable[Evidence]) -> None:
        self._evidence = tuple(evidence)

    def search(self, query: str, *, roles: frozenset[str], filters: RetrievalFilters, limit: int):
        terms = _terms(query)
        visible = [item for item in self._evidence if _visible(item, roles, filters)]
        average_length = sum(len(_terms(item.text)) for item in visible) / max(1, len(visible))
        document_frequency = {term: sum(term in _terms(item.text) for item in visible) for term in terms}
        scored: list[tuple[Evidence, float]] = []
        for item in visible:
            tokens = _terms(item.text)
            score = 0.0
            for term in terms:
                frequency = tokens.count(term)
                if not frequency:
                    continue
                inverse = math.log((len(visible) - document_frequency[term] + 0.5) /
                                   (document_frequency[term] + 0.5) + 1.0)
                score += inverse * frequency / (frequency + 1.5 * (0.25 + 0.75 * len(tokens) / average_length))
            if score > 0:
                scored.append((item, score))
        scored.sort(key=lambda pair: (-pair[1], pair[0].evidence_id))
        return scored[:limit]


class VectorBackend:
    """Declared embedding adapter; caller supplies a deterministic query encoder."""

    def __init__(self, evidence: Iterable[Evidence], encoder: Callable[[str], tuple[float, ...]]):
        self._evidence = tuple(evidence)
        self._encoder = encoder

    def search(self, query: str, *, roles: frozenset[str], filters: RetrievalFilters, limit: int):
        vector = self._encoder(query)
        if not vector or not all(math.isfinite(value) for value in vector):
            raise ValueError("query embedding must be finite and non-empty")
        candidates: list[tuple[Evidence, float]] = []
        for item in self._evidence:
            if not _visible(item, roles, filters) or len(item.embedding) != len(vector):
                continue
            norm = math.sqrt(sum(value * value for value in vector) * sum(value * value for value in item.embedding))
            score = sum(a * b for a, b in zip(vector, item.embedding)) / norm if norm else 0.0
            candidates.append((item, score))
        candidates.sort(key=lambda pair: (-pair[1], pair[0].evidence_id))
        return candidates[:limit]


class QueryPlanner:
    def plan(self, query: str) -> tuple[str, ...]:
        cleaned = " ".join(query.split())
        if not cleaned or len(cleaned) > 2000:
            raise ValueError("query must be non-empty and bounded")
        parts = tuple(part.strip() for part in re.split(r"\b(?:and|also|then)\b", cleaned, flags=re.I))
        return tuple(part for part in parts if part)[:8]


class HybridRetriever:
    def __init__(self, keyword: RetrievalBackend | None, vector: RetrievalBackend | None, *, index_size: int):
        if keyword is None and vector is None:
            raise ValueError("at least one retrieval backend is required")
        self.keyword = keyword
        self.vector = vector
        self.index_size = index_size
        self.planner = QueryPlanner()

    def retrieve(
        self,
        query: str,
        *,
        roles: Iterable[str],
        filters: RetrievalFilters | None = None,
        limit: int = 10,
        embedding_cost: float | None = None,
    ) -> tuple[list[RetrievalResult], RetrievalTrace]:
        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")
        started = time.perf_counter()
        filters = filters or RetrievalFilters()
        role_set = frozenset(roles)
        if not role_set:
            raise PermissionError("at least one caller role is required")
        subqueries = self.planner.plan(query)
        keyword_hits: dict[str, tuple[Evidence, float]] = {}
        vector_hits: dict[str, tuple[Evidence, float]] = {}
        keyword_available = self.keyword is not None
        vector_available = self.vector is not None
        fallback = False
        for subquery in subqueries:
            if self.keyword is not None:
                try:
                    for item, score in self.keyword.search(subquery, roles=role_set, filters=filters, limit=limit * 3):
                        keyword_hits[item.evidence_id] = (item, max(score, keyword_hits.get(item.evidence_id, (item, 0.0))[1]))
                except Exception:
                    keyword_available = False
                    fallback = True
            if self.vector is not None:
                try:
                    for item, score in self.vector.search(subquery, roles=role_set, filters=filters, limit=limit * 3):
                        vector_hits[item.evidence_id] = (item, max(score, vector_hits.get(item.evidence_id, (item, 0.0))[1]))
                except Exception:
                    vector_available = False
                    fallback = True
        ids = set(keyword_hits) | set(vector_hits)
        fused: list[RetrievalResult] = []
        for evidence_id in ids:
            item = keyword_hits.get(evidence_id, vector_hits.get(evidence_id))[0]
            keyword_score = keyword_hits.get(evidence_id, (item, 0.0))[1]
            vector_score = vector_hits.get(evidence_id, (item, 0.0))[1]
            ranks = 0.0
            if evidence_id in keyword_hits:
                ranks += 1.0 / (60 + sorted(keyword_hits, key=lambda key: -keyword_hits[key][1]).index(evidence_id) + 1)
            if evidence_id in vector_hits:
                ranks += 1.0 / (60 + sorted(vector_hits, key=lambda key: -vector_hits[key][1]).index(evidence_id) + 1)
            fused.append(RetrievalResult(item, ranks + 0.01 * (keyword_score + vector_score), keyword_score, vector_score, 0))
        fused.sort(key=lambda item: (-item.score, item.evidence.evidence_id))
        results = [RetrievalResult(item.evidence, item.score, item.keyword_score, item.vector_score, index + 1)
                   for index, item in enumerate(fused[:limit])]
        trace = RetrievalTrace(
            query=query, subqueries=subqueries, keyword_available=keyword_available,
            vector_available=vector_available, fallback_used=fallback,
            candidate_count=len(ids), returned_count=len(results),
            latency_ms=(time.perf_counter() - started) * 1000,
            index_size=self.index_size, embedding_cost=embedding_cost,
        )
        return results, trace
