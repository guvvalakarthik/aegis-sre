# RAG grounding and injection evaluation protocol

Only active evidence authorized for the caller is placed into context. Claims must cite an exact
quote from an evidence record; unsupported claims are expected to abstain. Revoked or stale
records never become citations.

Evaluation reports persist dataset, retriever, prompt, model, and fixture versions plus a context
hash. Metrics cover groundedness, citation correctness, completeness, authorization, and
injection resistance. Red-team fixtures contain instruction-like content, but the evaluation
layer marks it as untrusted data and never grants it tool or system authority.

The contract does not fabricate answer quality. Real approved-incident fixtures must add retrieval
Recall@K, citation entailment, freshness, empty-evidence, conflicting-evidence, and per-category
failure reports, then run in CI with bounded red-team cases.
