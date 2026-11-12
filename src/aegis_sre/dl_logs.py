"""Redaction-first log tokenization and deterministic sequence anomaly models."""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from typing import Any, Literal


_KIND = Literal["lstm", "autoencoder", "bert"]
_SECRET = re.compile(r"(?i)\b(?:password|secret|token|api[_-]?key|authorization)\s*[:=]\s*(?:\S+\s+)?\S+")
_UUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f-]{27,}\b", re.I)
_NUMBER = re.compile(r"(?<![a-z])\d+(?![a-z])")
_TOKEN = re.compile(r"[a-z0-9_<>-]+")
PAD_ID = 0
UNK_ID = 1


@dataclass(frozen=True)
class LogParserConfig:
    parser_version: str = "log-parser/v1"
    vocabulary_version: str = "log-vocab/v1"
    max_length: int = 256


@dataclass(frozen=True)
class LogModelConfig:
    kind: _KIND
    vocabulary_size: int
    max_length: int
    embedding_dim: int = 64
    hidden_dim: int = 128
    layers: int = 2
    heads: int = 4
    seed: int = 42


@dataclass(frozen=True)
class LogModelMetadata:
    config: LogModelConfig
    parser: LogParserConfig
    dataset_version: str
    split_hash: str
    model_version: str


def normalize_log(message: str) -> tuple[str, ...]:
    if not isinstance(message, str):
        raise TypeError("message must be a string")
    value = _SECRET.sub("<REDACTED>", message.lower())
    value = _UUID.sub("<UUID>", value)
    value = _NUMBER.sub("<NUM>", value)
    tokens = tuple(_TOKEN.findall(value))
    if not tokens:
        raise ValueError("log message has no tokens")
    return tokens


def build_vocabulary(messages: list[str]) -> dict[str, int]:
    tokens = sorted({token for message in messages for token in normalize_log(message)})
    return {"<PAD>": PAD_ID, "<UNK>": UNK_ID, **{token: index + 2 for index, token in enumerate(tokens)}}


def encode_log(message: str, vocabulary: dict[str, int], config: LogParserConfig) -> tuple[tuple[int, ...], tuple[bool, ...]]:
    if config.max_length < 1:
        raise ValueError("max_length must be positive")
    tokens = normalize_log(message)[-config.max_length:]
    ids = tuple(vocabulary.get(token, UNK_ID) for token in tokens)
    padding = config.max_length - len(ids)
    return (PAD_ID,) * padding + ids, (False,) * padding + (True,) * len(ids)


def build_model(config: LogModelConfig) -> Any:
    import torch
    from torch import nn

    if config.vocabulary_size < 2 or config.max_length < 1 or config.layers < 1:
        raise ValueError("invalid log model dimensions")
    if config.kind == "bert" and config.embedding_dim % config.heads:
        raise ValueError("embedding dimension must divide attention heads")
    torch.manual_seed(config.seed)

    class LogAnomalyModel(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.embedding = nn.Embedding(config.vocabulary_size, config.embedding_dim, padding_idx=PAD_ID)
            if config.kind in ("lstm", "autoencoder"):
                self.encoder = nn.LSTM(
                    config.embedding_dim, config.hidden_dim, config.layers,
                    batch_first=True, dropout=0.0,
                )
                output_dim = config.hidden_dim
            else:
                layer = nn.TransformerEncoderLayer(
                    d_model=config.embedding_dim, nhead=config.heads,
                    batch_first=True, dropout=0.0, norm_first=True,
                )
                self.encoder = nn.TransformerEncoder(layer, num_layers=config.layers)
                output_dim = config.embedding_dim
            self.output = nn.Linear(output_dim, config.vocabulary_size)

        def forward(self, input_ids: Any, attention_mask: Any) -> Any:
            if input_ids.ndim != 2 or attention_mask.shape != input_ids.shape:
                raise ValueError("expected input_ids and attention_mask with shape [B,L]")
            if input_ids.shape[1] != config.max_length:
                raise ValueError("sequence length does not match config")
            hidden = self.embedding(input_ids)
            if config.kind == "bert":
                hidden = self.encoder(hidden, src_key_padding_mask=~attention_mask)
            else:
                hidden, _ = self.encoder(hidden)
            return self.output(hidden)

    return LogAnomalyModel()


def anomaly_scores(model: Any, input_ids: Any, attention_mask: Any) -> Any:
    import torch

    model.eval()
    with torch.no_grad():
        logits = model(input_ids, attention_mask)
        log_probabilities = torch.log_softmax(logits, dim=-1)
        token_scores = -log_probabilities.gather(-1, input_ids.unsqueeze(-1)).squeeze(-1)
        weights = attention_mask.to(dtype=token_scores.dtype)
        return (token_scores * weights).sum(dim=1) / weights.sum(dim=1).clamp_min(1.0)


def save_checkpoint(model: Any, path: str, metadata: LogModelMetadata) -> None:
    import torch

    torch.save({
        "schema_version": "log-anomaly/v1",
        "metadata": asdict(metadata),
        "state_dict": model.state_dict(),
    }, path)


def load_checkpoint(path: str, *, map_location: str = "cpu") -> tuple[Any, LogModelMetadata]:
    import torch

    payload = torch.load(path, map_location=map_location, weights_only=False)
    if payload.get("schema_version") != "log-anomaly/v1":
        raise ValueError("unsupported checkpoint schema")
    raw = payload["metadata"]
    config = LogModelConfig(**raw["config"])
    parser = LogParserConfig(**raw["parser"])
    metadata = LogModelMetadata(config, parser, raw["dataset_version"], raw["split_hash"], raw["model_version"])
    model = build_model(config)
    model.load_state_dict(payload["state_dict"])
    model.eval()
    return model, metadata
