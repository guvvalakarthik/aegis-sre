"""Bounded, time-aware and ACL-aware incident knowledge graph contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable


class NodeType(StrEnum):
    SERVICE = "service"
    RESOURCE = "resource"
    TRACE = "trace"
    DEPLOYMENT = "deployment"
    CODE = "code"
    ALERT = "alert"
    INCIDENT = "incident"
    HYPOTHESIS = "hypothesis"
    REMEDIATION = "remediation"
    OUTCOME = "outcome"


@dataclass(frozen=True)
class GraphNode:
    node_id: str
    node_type: NodeType
    environment: str
    valid_from: str
    valid_to: str | None
    provenance: str
    acl: frozenset[str]


@dataclass(frozen=True)
class GraphEdge:
    source_id: str
    target_id: str
    relation: str
    environment: str
    valid_from: str
    valid_to: str | None
    provenance: str
    observed: bool
    confidence: float
    acl: frozenset[str]


@dataclass(frozen=True)
class GraphPath:
    node_ids: tuple[str, ...]
    relations: tuple[str, ...]
    inferred: bool
    minimum_confidence: float


@dataclass(frozen=True)
class AblationResult:
    with_graph: float
    without_graph: float
    delta: float

    @classmethod
    def from_scores(cls, with_graph: float, without_graph: float) -> "AblationResult":
        return cls(with_graph, without_graph, with_graph - without_graph)


def _active(valid_from: str, valid_to: str | None, at: str) -> bool:
    return valid_from <= at and (valid_to is None or at < valid_to)


class IncidentGraph:
    def __init__(self) -> None:
        self._nodes: dict[str, GraphNode] = {}
        self._edges: list[GraphEdge] = []

    def add_node(self, node: GraphNode) -> None:
        if not node.node_id or not node.environment or not node.provenance:
            raise ValueError("node identity, environment, and provenance are required")
        if node.valid_to is not None and node.valid_to <= node.valid_from:
            raise ValueError("node validity window is invalid")
        if not node.acl:
            raise PermissionError("node ACL cannot be empty")
        existing = self._nodes.get(node.node_id)
        if existing is not None and existing != node:
            raise ValueError("node ID collision with different content")
        self._nodes[node.node_id] = node

    def add_edge(self, edge: GraphEdge) -> None:
        source = self._nodes.get(edge.source_id)
        target = self._nodes.get(edge.target_id)
        if source is None or target is None:
            raise KeyError("edge endpoints must exist")
        if source.environment != edge.environment or target.environment != edge.environment:
            raise ValueError("cross-environment edges are forbidden")
        if edge.valid_to is not None and edge.valid_to <= edge.valid_from:
            raise ValueError("edge validity window is invalid")
        if not edge.relation or not edge.provenance or not edge.acl:
            raise ValueError("edge relation, provenance, and ACL are required")
        if not 0.0 <= edge.confidence <= 1.0:
            raise ValueError("edge confidence must be in [0, 1]")
        self._edges.append(edge)

    def traverse(
        self,
        start_id: str,
        target_id: str,
        *,
        at: str,
        roles: Iterable[str],
        environment: str,
        max_depth: int = 4,
        max_fanout: int = 20,
        minimum_confidence: float = 0.0,
    ) -> list[GraphPath]:
        if max_depth < 1 or max_fanout < 1 or not 0.0 <= minimum_confidence <= 1.0:
            raise ValueError("invalid traversal bounds")
        roles = frozenset(roles)
        if not roles:
            raise PermissionError("at least one role is required")
        start = self._nodes.get(start_id)
        target = self._nodes.get(target_id)
        if start is None or target is None or start.environment != environment or target.environment != environment:
            return []
        if not start.acl.intersection(roles) or not target.acl.intersection(roles):
            return []
        paths: list[GraphPath] = []
        queue: list[tuple[str, tuple[str, ...], tuple[str, ...], float, bool]] = [
            (start_id, (start_id,), (), 1.0, False)
        ]
        while queue and len(paths) < max_fanout:
            current, nodes, relations, confidence, inferred = queue.pop(0)
            if current == target_id and len(nodes) > 1:
                paths.append(GraphPath(nodes, relations, inferred, confidence))
                continue
            if len(relations) >= max_depth:
                continue
            outgoing = [
                edge for edge in self._edges
                if edge.source_id == current
                and edge.environment == environment
                and _active(edge.valid_from, edge.valid_to, at)
                and edge.confidence >= minimum_confidence
                and edge.acl.intersection(roles)
                and self._nodes[edge.target_id].acl.intersection(roles)
                and _active(self._nodes[edge.target_id].valid_from, self._nodes[edge.target_id].valid_to, at)
            ]
            outgoing.sort(key=lambda edge: (edge.target_id, edge.relation))
            for edge in outgoing[:max_fanout]:
                if edge.target_id in nodes:
                    continue
                queue.append((
                    edge.target_id, nodes + (edge.target_id,), relations + (edge.relation,),
                    min(confidence, edge.confidence), inferred or not edge.observed,
                ))
        return paths

    def related_nodes(
        self, start_id: str, *, at: str, roles: Iterable[str], environment: str, max_depth: int = 2
    ) -> set[str]:
        results: set[str] = set()
        for node_id in self._nodes:
            if self.traverse(start_id, node_id, at=at, roles=roles, environment=environment, max_depth=max_depth):
                results.add(node_id)
        return results
