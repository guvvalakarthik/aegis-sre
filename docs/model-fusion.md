# Fusion and model-card protocol

Fusion preserves raw modality scores and availability flags in every decision record. A missing
modality reduces confidence and marks the result as degraded; it is never silently imputed.
The learned fusion head receives both score and availability features.

Candidate promotion requires held-out improvement over the baseline with an uncertainty interval,
plus latency, memory, cost, failure-mode, and missing-modality evidence. Aggregate accuracy alone
cannot approve a model. Ablation reports must isolate modality, feature, model-size, and
topology-context effects and must use the same frozen splits.

Model cards require data lineage, intended use, limitations, safety controls, operational cost,
metrics, and ablation references. Metrics must come from generated evaluation artifacts; the
card schema rejects empty metrics and invalid lifecycle states. This PR provides the contracts
and deterministic statistical utility but does not fabricate an ablation table or approval.
