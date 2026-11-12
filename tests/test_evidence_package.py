from __future__ import annotations

import pytest


def item(item_id: str, value: dict[str, str]):
    from aegis_sre.evidence_package import EvidenceItem, EvidenceKind, Provenance

    return EvidenceItem(
        item_id=item_id,
        kind=EvidenceKind.MODEL_SIGNAL,
        value=value,
        provenance=Provenance("source", "v1", "2026-01-01T00:00:00Z", "hash"),
        confidence=0.8,
        environment="prod",
        authorized_roles=frozenset({"operator"}),
    )


def package(items, status="grounded", missing=(), contradictions=(), abstained=False):
    from aegis_sre.evidence_package import EvidencePackage, PackageStatus

    return EvidencePackage(
        package_id="pkg", incident_id="inc", incident_time="2026-01-01T00:00:00Z",
        environment="prod", package_version="v1", items=tuple(items),
        status=PackageStatus(status), missing_evidence=missing,
        contradictions=contradictions, abstained=abstained,
    )


def test_contradictions_remain_visible() -> None:
    from aegis_sre.evidence_package import detect_contradictions

    assert detect_contradictions((item("a", {"cause": "deploy"}), item("b", {"cause": "config"})), field="cause") == (("a", "b"),)


def test_package_round_trip_and_authorization() -> None:
    from aegis_sre.evidence_package import replay_package

    original = package((item("a", {"cause": "deploy"}),)).approve("Karthik", "grounded").approve("Trivedi", "reproduced")
    restored = replay_package(original.to_json())
    assert restored.approved_by(("Karthik", "Trivedi"))
    assert len(restored.authorized_items(("operator",))) == 1
    assert restored.authorized_items(("viewer",)) == ()


def test_contradictory_package_requires_pairs() -> None:
    with pytest.raises(ValueError, match="contradiction"):
        package((item("a", {"cause": "deploy"}),), status="contradictory").validate()


def test_empty_package_must_abstain_or_explain_missing_evidence() -> None:
    with pytest.raises(ValueError, match="empty"):
        package((), status="grounded").validate()
