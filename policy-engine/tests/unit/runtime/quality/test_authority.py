# ruff: noqa: S101

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from polisyos.runtime.quality.authority import (
    AuthorityEnvelopeError,
    ConsumedInputMember,
    EvidenceAuthorityEnvelope,
    ProducerIdentity,
    SameInputClosure,
    assert_authority_bearing,
    assert_consumed_input_reuse,
    assert_runtime_emitted,
    assert_same_input_closure,
    authority_envelope_json_schema,
    classify_authority_role,
    deserialize_authority_envelope,
    seal_consumed_input_set,
    serialize_authority_envelope,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
FIXTURE_PATH = (
    REPO_ROOT
    / "tests/fixtures/runtime_quality/authority_envelopes/serious_runtime_emitted_pass.json"
)
SCHEMA_PATH = (
    REPO_ROOT
    / "schemas/runtime_quality/evidence_authority_envelope_v1.schema.json"
)


def _valid_payload() -> dict[str, object]:
    return deepcopy(json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))["payload"])


def _closed_input_closure() -> SameInputClosure:
    return SameInputClosure(
        closure_id="authority-owner-inputs",
        status="closed",
        run_id="run-1",
        job_id="job-1",
        tenant_id="tenant-1",
        closure_sha256="a" * 64,
    )


def _consumed_member(
    member_id: str,
    *,
    kind: str = "source",
    resolved_identity: str | None = None,
    predicate_class: str = "recomputed",
) -> ConsumedInputMember:
    return ConsumedInputMember(
        member_id=member_id,
        member_kind=kind,
        declared_identity=f"sha256:{member_id}",
        resolved_identity=resolved_identity or f"sha256:{member_id}",
        predicate_class=predicate_class,
    )


def test_consumed_input_set_seals_sorted_membership_and_closure_identity() -> None:
    sealed = seal_consumed_input_set(
        closure=_closed_input_closure(),
        members=[_consumed_member("z"), _consumed_member("a", kind="environment")],
    )

    assert [member.member_id for member in sealed.members] == ["a", "z"]
    assert sealed.same_input_closure == _closed_input_closure()
    assert sealed.membership_sha256.startswith("sha256:")


@pytest.mark.parametrize(
    "predicate_class",
    ["consumer_asserted", "institutionally_supplied", "not_established"],
)
def test_consumed_input_set_rejects_untrusted_decisive_predicate(
    predicate_class: str,
) -> None:
    with pytest.raises(
        AuthorityEnvelopeError,
        match=r"consumed_input_decisive_predicate_untrusted.*member=environment:runtime",
    ):
        seal_consumed_input_set(
            closure=_closed_input_closure(),
            members=[
                _consumed_member(
                    "runtime",
                    kind="environment",
                    predicate_class=predicate_class,
                )
            ],
        )


def test_consumed_input_reuse_exercises_identity_not_seal_marker() -> None:
    sealed = seal_consumed_input_set(
        closure=_closed_input_closure(),
        members=[_consumed_member("owner-source")],
    )
    substituted = _consumed_member(
        "owner-source",
        resolved_identity="sha256:substituted",
    )

    with pytest.raises(
        AuthorityEnvelopeError,
        match=r"consumed_input_member_substituted.*member=source:owner-source",
    ):
        assert_consumed_input_reuse(
            sealed,
            closure=_closed_input_closure(),
            fresh_members=[substituted],
        )


def test_consumed_input_set_names_an_unresolved_member() -> None:
    with pytest.raises(
        AuthorityEnvelopeError,
        match=r"consumed_input_member_unresolved.*member=artifact:ledger",
    ):
        seal_consumed_input_set(
            closure=_closed_input_closure(),
            members=[
                ConsumedInputMember(
                    member_id="ledger",
                    member_kind="artifact",
                    declared_identity="sha256:ledger",
                    predicate_class="recomputed",
                )
            ],
        )


def test_consumed_input_reuse_rejects_duplicate_missing_and_extra_members() -> None:
    sealed = seal_consumed_input_set(
        closure=_closed_input_closure(),
        members=[_consumed_member("source-a"), _consumed_member("source-b")],
    )

    with pytest.raises(AuthorityEnvelopeError, match="consumed_input_member_duplicate"):
        assert_consumed_input_reuse(
            sealed,
            closure=_closed_input_closure(),
            fresh_members=[_consumed_member("source-a"), _consumed_member("source-a")],
        )
    with pytest.raises(
        AuthorityEnvelopeError,
        match=r"consumed_input_member_missing.*member=source:source-b",
    ):
        assert_consumed_input_reuse(
            sealed,
            closure=_closed_input_closure(),
            fresh_members=[_consumed_member("source-a")],
        )
    with pytest.raises(
        AuthorityEnvelopeError,
        match=r"consumed_input_member_extra.*member=source:source-c",
    ):
        assert_consumed_input_reuse(
            sealed,
            closure=_closed_input_closure(),
            fresh_members=[
                _consumed_member("source-a"),
                _consumed_member("source-b"),
                _consumed_member("source-c"),
            ],
        )


def test_consumed_input_reuse_is_order_independent() -> None:
    source = _consumed_member("source")
    environment = _consumed_member("environment", kind="environment")
    sealed = seal_consumed_input_set(
        closure=_closed_input_closure(),
        members=[source, environment],
    )

    assert assert_consumed_input_reuse(
        sealed,
        closure=_closed_input_closure(),
        fresh_members=[environment, source],
    ) == sealed


def test_valid_runtime_emitted_envelope_round_trips_and_asserts_authority() -> None:
    envelope = deserialize_authority_envelope(_valid_payload())

    assert isinstance(envelope, EvidenceAuthorityEnvelope)
    assert envelope.producer_identity == ProducerIdentity(
        component="polisyos.lex.normpack.applicability_report",
        version="2026.05.14+hds-phase02",
        owner="team-runtime-quality",
    )
    assert classify_authority_role(envelope) == "producer_authority"
    assert_authority_bearing(envelope)
    assert_runtime_emitted(envelope)
    assert_same_input_closure([envelope, deserialize_authority_envelope(_valid_payload())])

    encoded = serialize_authority_envelope(envelope)
    assert deserialize_authority_envelope(encoded) == envelope


@pytest.mark.parametrize(
    "field",
    [
        "producer_component",
        "producer_version",
        "owner",
        "run_id",
        "job_id",
        "tenant_id",
        "trace_id",
        "schema_name",
        "schema_version",
    ],
)
def test_deserializer_rejects_missing_identity_fields(field: str) -> None:
    payload = _valid_payload()
    payload.pop(field)

    with pytest.raises(ValidationError):
        deserialize_authority_envelope(payload)


def test_deserializer_rejects_unknown_authority_role() -> None:
    payload = _valid_payload()
    payload["authority_role"] = "runtime_superuser"

    with pytest.raises(ValidationError):
        deserialize_authority_envelope(payload)


def test_deserializer_rejects_unknown_provenance_kind() -> None:
    payload = _valid_payload()
    payload["provenance_kind"] = "fixture"

    with pytest.raises(ValidationError):
        deserialize_authority_envelope(payload)


def test_projection_only_envelope_cannot_be_used_as_authority() -> None:
    payload = _valid_payload()
    payload["authority_role"] = "projection_only"
    payload["provenance_kind"] = "runtime_projection"

    envelope = deserialize_authority_envelope(payload)

    with pytest.raises(AuthorityEnvelopeError, match="projection_used_as_authority"):
        assert_authority_bearing(envelope)


def test_fixture_input_envelope_is_blocked_for_serious_profiles() -> None:
    payload = _valid_payload()
    payload["provenance_kind"] = "fixture_input"

    envelope = deserialize_authority_envelope(payload)

    with pytest.raises(
        AuthorityEnvelopeError,
        match="fixture_input_disallowed_for_serious_profile",
    ):
        assert_authority_bearing(envelope)


def test_runtime_emitted_envelope_rejects_runtime_ref_mismatch() -> None:
    payload = _valid_payload()
    payload["cas_ref"] = "cas://sha256/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"

    envelope = deserialize_authority_envelope(payload)

    with pytest.raises(AuthorityEnvelopeError, match="authority_runtime_ref_mismatch"):
        assert_runtime_emitted(envelope)


def test_same_input_closure_rejects_mixed_closure_identities() -> None:
    mismatched_payload = _valid_payload()
    assert isinstance(mismatched_payload["same_input_closure"], dict)
    mismatched_payload["same_input_closure"]["closure_sha256"] = (
        "9999999999999999999999999999999999999999999999999999999999999999"
    )

    with pytest.raises(AuthorityEnvelopeError, match="same_input_closure_mismatch"):
        assert_same_input_closure(
            [
                deserialize_authority_envelope(_valid_payload()),
                deserialize_authority_envelope(mismatched_payload),
            ]
        )


def test_json_schema_snapshot_matches_model_schema() -> None:
    saved_schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert saved_schema == authority_envelope_json_schema()
