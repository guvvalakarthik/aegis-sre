"""Deterministic, redaction-first log sequence encoding and transformer contracts."""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from typing import Any


PARSER_VERSION = "log-parser/v1"
PAD_ID = 0
UNK_ID = 1

_SECRET = re.compile(
    r"(?i)\b(?:authorization|api[_-]?key|access[_-]?token|refresh[_-]?token|"
    r"password|passwd|secret|credential)\s*[:=]\s*(?:\S+\s+)?\S+"
)
_UUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f-]{27,}\b", re.I)
_IP = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_HEX = re.compile(r"\b[0-9a-f]{16,}\b", re.I)
_NUMBER = re.compile(r"(?<![a-z])[-+]?\d+(?:\.\d+)?(?![a-z])")
_TOKEN = re.compile(r"[a-z0-9_<>-]+")


@dataclass(frozen=True)
class LogEvent:
    template_id: str
    service: str
    tokens: tuple[str, ...]
    parser_version: str = PARSER_VERSION


@dataclass(frozen=True)
class LogSequence:
    input_ids: tuple[int, ...]
    attention_mask: tuple[bool, ...]
    parser_version: str
    vocabulary_version: str


@dataclass(frozen=True)
class TransformerConfig:
    vocabulary_size: int
    classes: int
    max_length: int = 256
    d_model: int = 128
    heads: int = 4
    layers: int = 2
    dropout: float = 0.1
    seed: int = 42


@dataclass(frozen=True)
class CheckpointMetadata:
    schema_version: str
    model_config: TransformerConfig
    parser_version: str
    vocabulary_version: str
    dataset_version: str
    split_hash: str
    seed: int


def redact_message(message: str) -> str:
    """Remove secrets and replace unstable values before any tokenization."""
    if not isinstance(message, str):
        raise TypeError("message must be a string")
    redacted = _SECRET.sub("<REDACTED>", message)
    redacted = _UUID.sub("<UUID>", redacted)
    redacted = _IP.sub("<IP>", redacted)
    redacted = _HEX.sub("<HEX>", redacted)
    return _NUMBER.sub("<NUM>", redacted.lower())


def parse_event(message: str, *, service: str) -> LogEvent:
    if not service or not re.fullmatch(r"[a-zA-Z0-9_.-]{1,128}", service):
        raise ValueError("service must be a bounded identifier")
    normalized = redact_message(message)
    tokens = tuple(_TOKEN.findall(normalized))
    if not tokens:
        raise ValueError("log message has no usable tokens")
    template = " ".join(tokens)
    digest = hashlib.sha256(f"{PARSER_VERSION}:{template}".encode()).hexdigest()[:16]
    return LogEvent(template_id=digest, service=service, tokens=tokens)


def build_vocabulary(events: list[LogEvent], *, version: str = "log-vocab/v1") -> dict[str, int]:
    tokens = sorted({token for event in events for token in event.tokens})
    return {"<PAD>": PAD_ID, "<UNK>": UNK_ID, **{token: index + 2 for index, token in enumerate(tokens)}}


def encode_event(
    event: LogEvent,
    vocabulary: dict[str, int],
    *,
    max_length: int,
    vocabulary_version: str = "log-vocab/v1",
) -> LogSequence:
    if max_length < 1:
        raise ValueError("max_length must be positive")
    ids = tuple(vocabulary.get(token, UNK_ID) for token in event.tokens[-max_length:])
    padding = max_length - len(ids)
    return LogSequence(
        input_ids=(PAD_ID,) * padding + ids,
        attention_mask=(False,) * padding + (True,) * len(ids),
        parser_version=event.parser_version,
        vocabulary_version=vocabulary_version,
    )


def masked_mean(values: Any, attention_mask: Any) -> Any:
    weights = attention_mask.to(dtype=values.dtype).unsqueeze(-1)
    return (values * weights).sum(dim=1) / weights.sum(dim=1).clamp_min(1.0)


def build_transformer(config: TransformerConfig) -> Any:
    import torch
    from torch import nn

    if config.vocabulary_size < 2 or config.classes < 1:
        raise ValueError("vocabulary_size must be >= 2 and classes must be positive")
    if config.d_model % config.heads:
        raise ValueError("d_model must be divisible by heads")
    if config.max_length < 1 or not 0.0 <= config.dropout < 1.0:
        raise ValueError("invalid sequence or dropout configuration")

    class LogTransformer(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.token = nn.Embedding(config.vocabulary_size, config.d_model, padding_idx=PAD_ID)
            self.position = nn.Embedding(config.max_length, config.d_model)
            layer = nn.TransformerEncoderLayer(
                d_model=config.d_model, nhead=config.heads,
                dropout=config.dropout, batch_first=True, norm_first=True,
            )
            self.encoder = nn.TransformerEncoder(layer, num_layers=config.layers)
            self.classifier = nn.Linear(config.d_model, config.classes)

        def forward(self, input_ids: Any, attention_mask: Any) -> Any:
            if input_ids.ndim != 2 or attention_mask.shape != input_ids.shape:
                raise ValueError("expected input_ids and attention_mask with shape [B,L]")
            if input_ids.shape[1] != config.max_length:
                raise ValueError("sequence length does not match config")
            positions = torch.arange(config.max_length, device=input_ids.device)
            hidden = self.token(input_ids) + self.position(positions)
            hidden = self.encoder(hidden, src_key_padding_mask=~attention_mask)
            return self.classifier(masked_mean(hidden, attention_mask))

        def embedding(self, input_ids: Any, attention_mask: Any) -> Any:
            if input_ids.shape[1] != config.max_length:
                raise ValueError("sequence length does not match config")
            positions = torch.arange(config.max_length, device=input_ids.device)
            hidden = self.encoder(
                self.token(input_ids) + self.position(positions),
                src_key_padding_mask=~attention_mask,
            )
            return masked_mean(hidden, attention_mask)

    torch.manual_seed(config.seed)
    return LogTransformer()


def save_checkpoint(model: Any, path: str, metadata: CheckpointMetadata) -> None:
    import torch

    torch.save({
        "schema_version": metadata.schema_version,
        "metadata": asdict(metadata),
        "state_dict": model.state_dict(),
    }, path)
