# Incident knowledge graph protocol

Nodes and edges carry environment, validity windows, provenance, ACLs, and confidence. Edges
explicitly declare whether they are observed evidence or inferred relationships. Cross-environment
edges are rejected at insertion.

Traversal requires caller roles, target environment, time, depth, fan-out, and confidence bounds.
Expired nodes and edges are excluded, authorization is checked on both endpoints and edges, and
cycles are bounded. Historical incident queries therefore reconstruct only the topology valid at
the requested time.

Graph-enriched retrieval must publish an ablation result comparing with-graph and without-graph
quality. This PR supplies the secure graph contract and bounded traversal; real K-06/T-08
ingestion, causal-path fixtures, and retrieval ablation metrics remain required validation.
