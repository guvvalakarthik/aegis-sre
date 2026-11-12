"""Deterministic LogBERT-style masked-token anomaly model."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any


PAD_ID = 0
MASK_ID = 2


@dataclass(frozen=True)
class LogTransformerConfig:
    vocabulary_size: int
    max_length: int
    embedding_dim: int = 128
    heads: int = 4
    layers: int = 2
    mask_probability: float = 0.15
    seed: int = 42


@dataclass(frozen=True)
class LogTransformerMetadata:
    config: LogTransformerConfig
    tokenizer_version: str
    dataset_version: str
    split_hash: str
    model_version: str


def mask_tokens(input_ids: Any, attention_mask: Any, *, probability: float, seed: int) -> tuple[Any, Any]:
    import torch

    if not hasattr(input_ids, "shape") or not hasattr(attention_mask, "shape") or input_ids.shape != attention_mask.shape:
        raise ValueError("input IDs and attention mask must have equal shape")
    if not 0.0 < probability < 1.0 or seed < 0:
        raise ValueError("invalid masking configuration")
    generator = torch.Generator(device=input_ids.device).manual_seed(seed)
    selected = torch.rand(input_ids.shape, generator=generator, device=input_ids.device) < probability
    selected &= attention_mask
    selected &= input_ids != PAD_ID
    masked = input_ids.clone()
    masked[selected] = MASK_ID
    labels = input_ids.clone()
    labels[~selected] = -100
    return masked, labels


def build_model(config: LogTransformerConfig) -> Any:
    import torch
    from torch import nn

    if config.vocabulary_size <= MASK_ID or config.max_length < 1:
        raise ValueError("vocabulary and sequence dimensions are invalid")
    if config.embedding_dim % config.heads or config.layers < 1:
        raise ValueError("embedding dimension must divide heads and layers must be positive")
    torch.manual_seed(config.seed)

    class AttentionLayer(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.attention = nn.MultiheadAttention(
                config.embedding_dim, config.heads, batch_first=True, dropout=0.0,
            )
            self.norm1 = nn.LayerNorm(config.embedding_dim)
            self.ffn = nn.Sequential(
                nn.Linear(config.embedding_dim, config.embedding_dim * 4),
                nn.GELU(),
                nn.Linear(config.embedding_dim * 4, config.embedding_dim),
            )
            self.norm2 = nn.LayerNorm(config.embedding_dim)

        def forward(self, hidden: Any, mask: Any) -> tuple[Any, Any]:
            attended, weights = self.attention(
                hidden, hidden, hidden, key_padding_mask=~mask,
                need_weights=True, average_attn_weights=False,
            )
            hidden = self.norm1(hidden + attended)
            return self.norm2(hidden + self.ffn(hidden)), weights

    class LogBERT(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.tokens = nn.Embedding(config.vocabulary_size, config.embedding_dim, padding_idx=PAD_ID)
            self.positions = nn.Embedding(config.max_length, config.embedding_dim)
            self.layers = nn.ModuleList(AttentionLayer() for _ in range(config.layers))
            self.head = nn.Linear(config.embedding_dim, config.vocabulary_size)

        def forward(self, input_ids: Any, attention_mask: Any, *, return_attention: bool = False) -> Any:
            if input_ids.ndim != 2 or attention_mask.shape != input_ids.shape:
                raise ValueError("expected input_ids and mask [batch, length]")
            if input_ids.shape[1] != config.max_length:
                raise ValueError("sequence length does not match config")
            positions = torch.arange(config.max_length, device=input_ids.device)
            hidden = self.tokens(input_ids) + self.positions(positions)
            attentions = []
            for layer in self.layers:
                hidden, weights = layer(hidden, attention_mask)
                attentions.append(weights)
            logits = self.head(hidden)
            return (logits, torch.stack(attentions)) if return_attention else logits

    return LogBERT()


def anomaly_scores(model: Any, input_ids: Any, attention_mask: Any) -> Any:
    import torch

    model.eval()
    with torch.no_grad():
        logits = model(input_ids, attention_mask)
        negative_log_likelihood = -torch.log_softmax(logits, dim=-1).gather(
            -1, input_ids.unsqueeze(-1)
        ).squeeze(-1)
        weights = attention_mask.to(dtype=negative_log_likelihood.dtype)
        return (negative_log_likelihood * weights) / weights.clamp_min(1.0)


def attention_attribution(model: Any, input_ids: Any, attention_mask: Any) -> Any:
    model.eval()
    _, attention = model(input_ids, attention_mask, return_attention=True)
    return attention.detach().mean(dim=(0, 1, 2))


def train_masked_language_model(
    model: Any,
    train_batches: tuple[tuple[Any, Any], ...],
    validation_batches: tuple[tuple[Any, Any], ...],
    *,
    config: LogTransformerConfig,
    epochs: int = 20,
    patience: int = 3,
) -> tuple[float, ...]:
    import torch
    from torch import nn

    if not train_batches or not validation_batches or epochs < 1 or patience < 1:
        raise ValueError("training batches and early-stopping configuration are required")
    torch.manual_seed(config.seed)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.CrossEntropyLoss(ignore_index=-100)
    validation_history: list[float] = []
    best_loss = float("inf")
    best_state: dict[str, Any] | None = None
    stale = 0
    for epoch in range(epochs):
        model.train()
        for input_ids, mask in train_batches:
            masked, labels = mask_tokens(input_ids, mask, probability=config.mask_probability, seed=config.seed + epoch)
            optimizer.zero_grad()
            logits = model(masked, mask)
            loss = loss_fn(logits.reshape(-1, config.vocabulary_size), labels.reshape(-1))
            loss.backward()
            optimizer.step()
        model.eval()
        with torch.no_grad():
            losses = []
            for input_ids, mask in validation_batches:
                masked, labels = mask_tokens(input_ids, mask, probability=config.mask_probability, seed=config.seed + 10000 + epoch)
                logits = model(masked, mask)
                losses.append(float(loss_fn(logits.reshape(-1, config.vocabulary_size), labels.reshape(-1)).item()))
        if not losses:
            raise ValueError("validation batches cannot be empty")
        current = sum(losses) / len(losses)
        validation_history.append(current)
        if current < best_loss:
            best_loss = current
            best_state = {key: value.detach().clone() for key, value in model.state_dict().items()}
            stale = 0
        else:
            stale += 1
            if stale >= patience:
                break
    if best_state is None:
        raise RuntimeError("no checkpoint was produced")
    model.load_state_dict(best_state)
    return tuple(validation_history)


def save_checkpoint(model: Any, path: str, metadata: LogTransformerMetadata) -> None:
    import torch

    torch.save({
        "schema_version": "log-transformer/v1",
        "metadata": asdict(metadata),
        "state_dict": model.state_dict(),
    }, path)


def load_checkpoint(path: str, *, map_location: str = "cpu") -> tuple[Any, LogTransformerMetadata]:
    import torch

    payload = torch.load(path, map_location=map_location, weights_only=False)
    if payload.get("schema_version") != "log-transformer/v1":
        raise ValueError("unsupported checkpoint schema")
    raw = payload["metadata"]
    config = LogTransformerConfig(**raw["config"])
    metadata = LogTransformerMetadata(config, raw["tokenizer_version"], raw["dataset_version"], raw["split_hash"], raw["model_version"])
    model = build_model(config)
    model.load_state_dict(payload["state_dict"])
    model.eval()
    return model, metadata
