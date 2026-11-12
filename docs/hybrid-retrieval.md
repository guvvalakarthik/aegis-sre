# Hybrid retrieval protocol

Retrieval backends receive caller roles and metadata filters and must apply them before scoring.
Unauthorized evidence is never returned to the model. Keyword retrieval uses deterministic BM25-
style scoring; vector retrieval uses a declared encoder and cosine similarity. Reciprocal-rank
fusion preserves keyword and vector scores in every result.

Queries are normalized and decomposed into a bounded number of subqueries. Backend failure is
recorded in the retrieval trace and the healthy backend remains usable. Empty results are valid
and observable. Every result carries source URI, version, service, environment, timestamp, and
ACL metadata.

The implementation records latency, index size, and optional embedding cost. Real vector-store
and embedding adapters must add pinned model/version metadata and contract tests before Issue #27
is considered complete; this PR does not fabricate retrieval metrics.
