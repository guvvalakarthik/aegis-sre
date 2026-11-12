from __future__ import annotations

import pytest


def node(node_id: str, environment: str = "prod"):
    from aegis_sre.knowledge_graph import GraphNode, NodeType

    return GraphNode(node_id, NodeType.SERVICE, environment, "2026-01-01", None, "trace://1", frozenset({"operator"}))


def test_historical_causal_path_and_inferred_flag() -> None:
    from aegis_sre.knowledge_graph import GraphEdge, IncidentGraph

    graph = IncidentGraph()
    graph.add_node(node("checkout"))
    graph.add_node(node("incident"))
    graph.add_node(node("deployment"))
    graph.add_edge(GraphEdge("checkout", "deployment", "changed-by", "prod", "2026-01-01", None, "git://1", True, 1.0, frozenset({"operator"})))
    graph.add_edge(GraphEdge("deployment", "incident", "caused", "prod", "2026-01-01", None, "model://1", False, 0.8, frozenset({"operator"})))
    paths = graph.traverse("checkout", "incident", at="2026-02-01", roles={"operator"}, environment="prod")
    assert len(paths) == 1
    assert paths[0].inferred is True


def test_cross_environment_and_unauthorized_paths_are_denied() -> None:
    from aegis_sre.knowledge_graph import GraphEdge, IncidentGraph

    graph = IncidentGraph()
    graph.add_node(node("prod-service", "prod"))
    graph.add_node(node("dev-incident", "dev"))
    with pytest.raises(ValueError, match="environment"):
        graph.add_edge(GraphEdge("prod-service", "dev-incident", "related", "prod", "2026-01-01", None, "trace://1", True, 1.0, frozenset({"operator"})))
    assert graph.traverse("prod-service", "dev-incident", at="2026-02-01", roles={"operator"}, environment="dev") == []


def test_expired_edges_are_not_used() -> None:
    from aegis_sre.knowledge_graph import GraphEdge, IncidentGraph

    graph = IncidentGraph()
    graph.add_node(node("a"))
    graph.add_node(node("b"))
    graph.add_edge(GraphEdge("a", "b", "related", "prod", "2026-01-01", "2026-02-01", "trace://1", True, 1.0, frozenset({"operator"})))
    assert graph.traverse("a", "b", at="2026-03-01", roles={"operator"}, environment="prod") == []
