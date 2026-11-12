from __future__ import annotations

import pytest


def test_log_redaction_and_deterministic_encoding() -> None:
    from aegis_sre.dl_logs import LogParserConfig, build_vocabulary, encode_log, normalize_log

    message = "Authorization: Bearer secret-value request id=123"
    assert "secret-value" not in normalize_log(message)
    vocabulary = build_vocabulary([message])
    first = encode_log(message, vocabulary, LogParserConfig(max_length=8))
    assert first == encode_log(message, vocabulary, LogParserConfig(max_length=8))


def test_lstm_autoencoder_and_bert_shapes() -> None:
    torch = pytest.importorskip("torch")
    from aegis_sre.dl_logs import LogModelConfig, build_model

    ids = torch.ones((2, 6), dtype=torch.long)
    mask = torch.ones((2, 6), dtype=torch.bool)
    for kind in ("lstm", "autoencoder", "bert"):
        model = build_model(LogModelConfig(kind=kind, vocabulary_size=20, max_length=6, embedding_dim=8, hidden_dim=8))
        assert model(ids, mask).shape == (2, 6, 20)


def test_anomaly_scores_are_finite_and_masked() -> None:
    torch = pytest.importorskip("torch")
    from aegis_sre.dl_logs import LogModelConfig, anomaly_scores, build_model

    model = build_model(LogModelConfig(kind="bert", vocabulary_size=20, max_length=4, embedding_dim=8))
    ids = torch.ones((2, 4), dtype=torch.long)
    mask = torch.tensor([[False, True, True, False], [True, True, True, True]])
    scores = anomaly_scores(model, ids, mask)
    assert scores.shape == (2,)
    assert torch.isfinite(scores).all()
