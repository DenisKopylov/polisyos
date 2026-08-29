"""Strict transport contracts for the DS17 confidence risk-spend surface."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from pydantic import TypeAdapter, ValidationError

from polisyos.runtime.http.services.confidence_ledger_risk_spend_contracts import (
    STABLE_ADDRESS,
    AvailableConfidenceLedgerRiskSpendPacket,
    ConfidenceLedgerRiskSpendPacket,
    SourceBlockedConfidenceLedgerRiskSpendPacket,
)
from polisyos.runtime.http.services.confidence_ledger_risk_spend_projection import (
    ConfidenceLedgerRiskSpendProjectionService,
)
from polisyos.runtime.http.services.export_replay import (
    build_export_replay_address,
    hash_export_projection,
)

_ROOT = Path(__file__).resolve().parents[4]


def _available() -> AvailableConfidenceLedgerRiskSpendPacket:
    packet = ConfidenceLedgerRiskSpendProjectionService(_ROOT).get()
    assert isinstance(packet, AvailableConfidenceLedgerRiskSpendPacket)
    return packet


def _rebind_available_packet(candidate: dict[str, object]) -> None:
    semantic_body = deepcopy(candidate)
    semantic_body.pop("projection_hash")
    semantic_body.pop("replay_pins")
    semantic_body.pop("replay_address")
    freshness = semantic_body["freshness"]
    assert isinstance(freshness, dict)
    freshness.pop("observed_at")
    projection_hash = hash_export_projection(semantic_body)
    candidate["projection_hash"] = projection_hash
    replay_pins = candidate["replay_pins"]
    assert isinstance(replay_pins, dict)
    replay_pins["projection_hash"] = projection_hash
    candidate["replay_address"] = build_export_replay_address(
        STABLE_ADDRESS,
        replay_pins,
    )


def test_available_packet_is_strict_self_hashed_and_replay_bound() -> None:
    packet = _available()
    payload = packet.model_dump(mode="json")
    parsed = TypeAdapter(ConfidenceLedgerRiskSpendPacket).validate_json(
        packet.model_dump_json(),
        strict=True,
    )

    assert parsed == packet
    assert packet.projection_hash != packet.payload.projection_hash
    assert packet.source.artifact_content_hash != packet.registry_content_hash
    assert packet.worker_validation_receipt_hash.startswith("sha256:")
    assert packet.replay_pins.projection_hash == packet.projection_hash
    replay_query = parse_qs(urlsplit(packet.replay_address).query)
    assert replay_query["source_as_of"] == [
        packet.replay_pins.source_as_of.isoformat().replace("+00:00", "Z")
    ]

    for mutation in (
        lambda value: value.__setitem__("projection_hash", "sha256:" + "0" * 64),
        lambda value: value["replay_pins"].__setitem__(
            "source_dependency_hash", "sha256:" + "1" * 64
        ),
        lambda value: value.__setitem__("replay_address", "/forged"),
    ):
        candidate = deepcopy(payload)
        mutation(candidate)
        with pytest.raises(ValidationError):
            TypeAdapter(ConfidenceLedgerRiskSpendPacket).validate_json(
                json.dumps(candidate),
                strict=True,
            )


def test_source_blocked_packet_cannot_publish_rejected_source_detail() -> None:
    forbidden = {
        "payload",
        "registry_content_hash",
        "registry_projection_hash",
        "frozen_semantic_projection_hash",
        "issue_codes",
        "recomputed_total_spend",
        "registry_delta",
        "within_budget",
        "certificate_routes",
        "instrument_instances",
    }

    assert forbidden.isdisjoint(SourceBlockedConfidenceLedgerRiskSpendPacket.model_fields)


def test_transport_union_has_exactly_four_strict_arms() -> None:
    schema = TypeAdapter(ConfidenceLedgerRiskSpendPacket).json_schema()
    discriminator = schema["discriminator"]

    assert set(discriminator["mapping"]) == {
        "available",
        "source_blocked",
        "artifact_missing",
        "invalid_source",
    }
    payload = _available().model_dump(mode="json")
    with pytest.raises(ValidationError):
        TypeAdapter(ConfidenceLedgerRiskSpendPacket).validate_json(
            json.dumps({**payload, "caller_asserted_safe": True}),
            strict=True,
        )


def test_request_observation_time_is_not_stable_packet_identity() -> None:
    service = ConfidenceLedgerRiskSpendProjectionService(_ROOT)
    first = service.get()
    second = service.get()

    assert isinstance(first, AvailableConfidenceLedgerRiskSpendPacket)
    assert isinstance(second, AvailableConfidenceLedgerRiskSpendPacket)
    assert first.freshness.observed_at != second.freshness.observed_at
    assert first.projection_hash == second.projection_hash
    assert first.replay_address == second.replay_address


@pytest.mark.parametrize(
    "mutation",
    [
        "source_payload_equal",
        "nested_receipt",
        "available_issue",
        "source_path",
        "source_schema_version",
        "source_rule_version",
        "validator_id",
        "validator_version",
        "empty_authority",
        "empty_limitations",
    ],
)
def test_available_packet_rejects_coherently_rehashed_owner_fact_forgery(
    mutation: str,
) -> None:
    candidate = _available().model_dump(mode="json")
    source = candidate["source"]
    assert isinstance(source, dict)
    validation = source["validation"]
    assert isinstance(validation, dict)
    if mutation == "source_payload_equal":
        validation["source_payload_equal"] = False
    elif mutation == "nested_receipt":
        validation["worker_validation_receipt_hash"] = "sha256:" + "9" * 64
    elif mutation == "available_issue":
        validation["issue_codes"] = ["semantic_total_spend_drift"]
    elif mutation == "source_path":
        source["relative_path"] = "candidate/attacker-selected-ledger.json"
    elif mutation == "source_schema_version":
        candidate["source_schema_version"] = "candidate.schema.v999"
    elif mutation == "source_rule_version":
        candidate["source_rule_version"] = "candidate.rule.v999"
    elif mutation == "validator_id":
        validation["validator_id"] = "candidate.self_attested:validate_payload"
    elif mutation == "validator_version":
        validation["validator_version"] = "candidate.validator.v999"
    elif mutation == "empty_authority":
        candidate["authoritative_for"] = []
    elif mutation == "empty_limitations":
        candidate["may_not_use_for"] = []
    else:  # pragma: no cover - parameter denominator is closed above
        raise AssertionError(mutation)
    _rebind_available_packet(candidate)

    with pytest.raises(ValidationError):
        TypeAdapter(ConfidenceLedgerRiskSpendPacket).validate_json(
            json.dumps(candidate),
            strict=True,
        )
