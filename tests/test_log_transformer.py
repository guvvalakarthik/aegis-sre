from __future__ import annotations

import pytest


def test_redaction_removes_secrets_and_unstable_values() -> None:
    from aegis_sre.log_transformer import redact_message

    cleaned = redact_message(
        "Authorization: Bearer secret-value user=abc id=550e8400-e29b-41d4-a716-446655440000"
    )
    assert "secret-value" not in cleaned
    assert "550e8400" not in cleaned
    assert "<REDACTED>" in cleaned
    assert "<UUID>" in cleaned


def test_template_ids_are_deterministic() -> None:
    from aegis_sre.log_transformer import parse_event

    first = parse_event("request id=123 latency=42ms", service="checkout")
    second = parse_event("request id=999 latency=88ms", service="checkout")
    assert first.template_id == second.template_id
    assert first.parser_version == "log-parser/v1"


def test_truncation_and_padding_are_explicit() -> None:
    from aegis_sre.log_transformer import (
        build_vocabulary,
        encode_event,
        parse_event,
    )

    event = parse_event("one two three four", service="api")
    encoded = encode_event(event, build_vocabulary([event]), max_length=3)
    assert len(encoded.input_ids) == 3
    assert encoded.attention_mask == (True, True, True)


def test_transformer_has_embeddings_and_logits() -> None:
    torch = pytest.importorskip("torch")
    from aegis_sre.log_transformer import TransformerConfig, build_transformer

    model = build_transformer(TransformerConfig(vocabulary_size=10, classes=3, max_length=4))
    ids = torch.ones((2, 4), dtype=torch.long)
    mask = torch.ones((2, 4), dtype=torch.bool)
    assert model(ids, mask).shape == (2, 3)
    assert model.embedding(ids, mask).shape == (2, 128)
