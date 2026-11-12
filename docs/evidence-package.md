# Evidence-grounded diagnosis gate

An evidence package is a replayable snapshot of model signals, graph evidence, retrieval results,
citations, and ground truth. Every item carries source/version, capture timestamp, source hash,
environment, confidence, and authorization metadata.

Packages preserve contradictory values as explicit pairs and never silently choose a winner.
Missing evidence and abstention are first-class states. Authorization is rechecked when a package
is consumed, and cross-environment items are rejected.

The serialized package contains no live handles, so replay does not require production access.
Both contributors must approve the grounding and authorization review before the package can
enter agent work. Held-out package rebuilds, representative correct/incorrect/ambiguous/OOD
cases, and known-gap documentation remain required integration validation.
