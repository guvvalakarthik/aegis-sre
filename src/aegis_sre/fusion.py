"""Auditable multimodal fusion and evidence/model-card contracts."""

from __future__ import annotations

import json
import math
import random
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class FusionEvidence:
    modality_scores: dict[str, float]
    modality_available: dict[str, bool]
    fused_score: float
    confidence: float
    degraded: bool
    fusion_version: str = "fusion/v1"

    def __post_init__(self) -> None:
        if set(self.modality_scores) != set(self.modality_available):
            raise ValueError("scores and availability must contain the same modalities")
        if not all(math.isfinite(value) for value in self.modality_scores.values()):
            raise ValueError("modality scores must be finite")
        if not 0.0 <= self.fused_score <= 1.0 or not 0.0 <= self.confidence <= 1.0:
            raise ValueError("fused score and confidence must be in [0, 1]")
        if not any(self.modality_available.values()):
            raise ValueError("at least one modality must be available")


def late_fuse(
    scores: Mapping[str, float],
    available: Mapping[str, bool],
    *,
    weights: Mapping[str, float] | None = None,
    minimum_confidence: float = 0.0,
) -> FusionEvidence:
    """Combine available scores while retaining all raw evidence."""
    if set(scores) != set(available) or not scores:
        raise ValueError("scores and availability must contain the same non-empty modalities")
    if any(not math.isfinite(value) or not 0.0 <= value <= 1.0 for value in scores.values()):
        raise ValueError("modality scores must be finite probabilities in [0, 1]")
    weights = weights or {name: 1.0 for name in scores}
    if set(weights) != set(scores) or any(weight < 0 for weight in weights.values()):
        raise ValueError("weights must be non-negative and cover every modality")
    usable = [name for name in scores if available[name] and weights[name] > 0]
    if not usable:
        raise ValueError("no weighted modality is available")
    denominator = sum(weights[name] for name in usable)
    fused = sum(scores[name] * weights[name] for name in usable) / denominator
    availability = len(usable) / len(scores)
    confidence = max(0.0, min(1.0, availability * (1.0 - _weighted_disagreement(scores, usable, weights))))
    return FusionEvidence(
        modality_scores=dict(scores),
        modality_available=dict(available),
        fused_score=max(0.0, min(1.0, fused)),
        confidence=confidence,
        degraded=confidence < minimum_confidence or len(usable) < len(scores),
    )


def _weighted_disagreement(
    scores: Mapping[str, float], names: Sequence[str], weights: Mapping[str, float]
) -> float:
    center = sum(scores[name] * weights[name] for name in names) / sum(weights[name] for name in names)
    return min(1.0, sum(weights[name] * abs(scores[name] - center) for name in names) / sum(weights[name] for name in names))


def build_fusion_features(evidence: FusionEvidence) -> list[float]:
    """Expose scores and availability indicators without hiding missing modalities."""
    features: list[float] = []
    for name in sorted(evidence.modality_scores):
        features.extend([evidence.modality_scores[name], float(evidence.modality_available[name])])
    return features


def bootstrap_delta_ci(
    candidate: Sequence[float],
    baseline: Sequence[float],
    *,
    seed: int = 42,
    samples: int = 2000,
    confidence: float = 0.95,
) -> tuple[float, float, float]:
    """Return observed delta and a deterministic percentile bootstrap interval."""
    if len(candidate) != len(baseline) or not candidate:
        raise ValueError("candidate and baseline must be equally sized and non-empty")
    if samples < 100 or not 0.0 < confidence < 1.0:
        raise ValueError("invalid bootstrap configuration")
    deltas = [a - b for a, b in zip(candidate, baseline)]
    rng = random.Random(seed)
    means = [
        sum(rng.choice(deltas) for _ in deltas) / len(deltas)
        for _ in range(samples)
    ]
    means.sort()
    alpha = (1.0 - confidence) / 2.0
    low = means[max(0, int(alpha * samples))]
    high = means[min(samples - 1, int((1.0 - alpha) * samples))]
    return sum(deltas) / len(deltas), low, high


@dataclass(frozen=True)
class ModelCard:
    name: str
    version: str
    intended_use: str
    limitations: tuple[str, ...]
    training_data: str
    evaluation_data: str
    metrics: dict[str, float]
    safety_controls: tuple[str, ...]
    operational_cost: dict[str, float]
    ablation_reference: str
    status: str = "candidate"

    def to_json(self) -> str:
        if not self.name or not self.version or not self.training_data or not self.evaluation_data:
            raise ValueError("model card identity and data lineage are required")
        if not self.metrics or any(not math.isfinite(value) for value in self.metrics.values()):
            raise ValueError("model card metrics must be finite and non-empty")
        if self.status not in {"candidate", "approved", "retired"}:
            raise ValueError("invalid model-card status")
        return json.dumps(asdict(self), sort_keys=True, indent=2)


class LearnedFusion:
    """Small learned late-fusion head; modality masks are mandatory features."""

    def __init__(self, input_size: int, hidden_size: int = 32, seed: int = 42) -> None:
        import torch
        from torch import nn

        if input_size < 2 or hidden_size < 1:
            raise ValueError("invalid learned-fusion dimensions")
        torch.manual_seed(seed)
        self.model = nn.Sequential(
            nn.Linear(input_size, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, 1),
            nn.Sigmoid(),
        )

    def __call__(self, features: Any) -> Any:
        if features.ndim != 2:
            raise ValueError("fusion features must have shape [batch, features]")
        return self.model(features).squeeze(-1)
