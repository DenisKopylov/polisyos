# ruff: noqa: S101

from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts import (
    FileSystemCAS,
    ProducerInfo,
    PutOptions,
    SchemaInfo,
)
from polisyos.runtime.http.services.temporal import (
    build_time_source_consistency_audit_projection,
)
from polisyos.runtime.quality.authority import (
    AuthorityEnvelopeError,
    ConsumedInputMember,
    EvidenceAuthorityEnvelope,
    OutcomeReplayProof,
    OutputCASManifestProfile,
    OutputCASManifestProfileRefusalError,
    ProducerIdentity,
    SameInputClosure,
    SealedConsumedInputSet,
    assert_authority_bearing,
    assert_consumed_input_reuse,
    assert_runtime_emitted,
    assert_same_input_closure,
    authority_envelope_json_schema,
    authority_surface_decision,
    build_outcome_replay_proof,
    classify_authority_role,
    deserialize_authority_envelope,
    seal_consumed_input_set,
    serialize_authority_envelope,
)
from polisyos.runtime.quality.evaluation_safety import (
    EvalSafetyMetricsProjection,
    evaluation_safety_metrics_projection_identity,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
FIXTURE_PATH = (
    REPO_ROOT
    / "tests/fixtures/runtime_quality/authority_envelopes/serious_runtime_emitted_pass.json"
)
SCHEMA_PATH = REPO_ROOT / "schemas/runtime_quality/evidence_authority_envelope_v2.schema.json"
_TIME_SOURCE_PROJECTION_KIND = "time_source_consistency_audit_projection"
_TIME_SOURCE_PRODUCER_REF = (
    "polisyos.runtime.http.services.temporal.build_time_source_consistency_audit_projection"
)
_TIME_SOURCE_PROJECTION_SCOPE = "catalog_source_runtime_time_role_consistency"


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


def _surface_authority_payload() -> dict[str, object]:
    return {
        "authority_result": "authority",
        "legacy_path_disposition": "authority_path",
        "authority_boundary": {
            "boundary_id": "boundary://runtime-quality/time-source-test",
            "source_authority": "runtime_quality",
            "posture": "authority",
            "authoritative_for": ["runtime_closeout_authority", "publication"],
            "may_not_use_for": ["scorecard_authority"],
            "rule_version_refs": ["rule://runtime-quality/time-source-test"],
        },
    }


def _time_source_projection(
    disposition: str,
    *,
    projection_kind: str = _TIME_SOURCE_PROJECTION_KIND,
    producer_ref: str = _TIME_SOURCE_PRODUCER_REF,
    projection_scope: str = _TIME_SOURCE_PROJECTION_SCOPE,
) -> dict[str, object]:
    base = datetime(2026, 6, 16, 12, 5, 11, tzinfo=UTC)
    projection = build_time_source_consistency_audit_projection(
        catalog_watermark=base,
        source_observed_at=base,
        source_published_at=base,
        source_updated_at=base,
        ingested_at=base,
        effective_time=base,
        legal_valid_time=base,
        transaction_time=base,
        as_of_time=base,
        replay_time=base,
        run_started_at=base,
        run_finished_at=base + timedelta(seconds=5),
        node_started_at=base,
        node_finished_at=base + timedelta(seconds=1),
        retention_or_expiry=base + timedelta(days=30),
    ).model_dump(mode="json")
    projection.update(
        {
            "projection_kind": projection_kind,
            "producer_ref": producer_ref,
            "projection_scope": projection_scope,
            "mismatch_disposition": disposition,
        }
    )
    return projection


def _time_source_decision(payload: dict[str, object]):
    return authority_surface_decision(
        payload,
        surface="artifact",
        enforce_s12=False,
        enforce_candidate_firewall=False,
    )


def _eval_safety_metrics_projection_payload() -> dict[str, object]:
    boundary = {
        "boundary_id": "eval-safety-egress-test-v1",
        "authoritative_for": ["runtime_closeout_authority", "dashboard_display"],
        "may_not_use_for": [
            "attempted_evaluation_admission",
            "promotion",
            "evaluation_execution",
        ],
        "source_authority": "deterministic_producer",
        "posture": "advisory",
        "rule_version_refs": ["policyos.runtime.eval_safety.metrics_projection.v1"],
        "evidence_kind": "derivation",
        "decision_grade": "descriptive_only",
        "known_limits": ["informational_projection_only"],
    }
    denied_uses = [
        "attempted_evaluation_admission",
        "promotion",
        "evaluation_execution",
    ]
    projection = EvalSafetyMetricsProjection.model_validate(
        {
            "attempt_disposition": "passed",
            "selected_decision_artifact_refs": [],
            "reconciled_decision_artifact_refs": [],
            "unreconciled_decision_artifact_refs": [],
            "conflicting_decision_artifact_refs": [],
            "denominator_decision_ids": [],
            "unsafe_attempt_blocked_count": 0,
            "near_miss_count": 0,
            "near_miss_classification_status": "complete",
            "unclassified_blocked_decision_ids": [],
            "reconciliation_status": "complete",
            "generated_at": "2026-08-28T08:00:00Z",
            "source_event_refs": [],
            "authority_boundary": boundary,
            "authority_surface_packet": {
                "schema_version": "policyos.runtime.eval_safety_surface_packet.v1",
                "boundary": boundary,
                "surfaces": {
                    "run": {
                        "surface": "run",
                        "purpose": "runtime_closeout_authority",
                        "status": "allow",
                        "authority_result": "informational_projection_only",
                        "consumed_boundary_id": "eval-safety-egress-test-v1",
                        "projection_scope": "faithful_eval_safety_projection",
                        "may_not_use_for": denied_uses,
                    },
                    "artifact": {
                        "surface": "artifact",
                        "purpose": "runtime_closeout_authority",
                        "status": "allow",
                        "authority_result": "informational_projection_only",
                        "consumed_boundary_id": "eval-safety-egress-test-v1",
                        "projection_scope": "faithful_eval_safety_projection",
                        "may_not_use_for": denied_uses,
                    },
                    "lineage": {
                        "surface": "lineage",
                        "purpose": "runtime_closeout_authority",
                        "status": "allow",
                        "authority_result": "informational_projection_only",
                        "consumed_boundary_id": "eval-safety-egress-test-v1",
                        "projection_scope": "faithful_eval_safety_projection",
                        "may_not_use_for": denied_uses,
                    },
                    "dashboard": {
                        "surface": "dashboard",
                        "purpose": "dashboard_display",
                        "status": "allow",
                        "authority_result": "informational_projection_only",
                        "consumed_boundary_id": "eval-safety-egress-test-v1",
                        "projection_scope": "faithful_eval_safety_projection",
                        "may_not_use_for": denied_uses,
                    },
                },
            },
        }
    )
    return projection.model_dump(mode="json")


def test_eval_safety_surface_rejects_removed_packet_with_boundary_intact(
    tmp_path: Path,
) -> None:
    identity = evaluation_safety_metrics_projection_identity("artifact")
    artifact_store = FileSystemCAS(tmp_path / "cas").for_tenant(
        "tenant-1",
        cell_id="cell-a",
    )

    def persist(
        payload: dict[str, object],
        *,
        kind: str = identity.kind,
        schema_name: str = identity.schema_name,
        schema_version: str = identity.schema_version,
    ):
        artifact_ref = artifact_store.put_json(
            payload,
            PutOptions(
                kind=kind,
                media_type="application/json",
                schema=SchemaInfo(
                    name=schema_name,
                    version=schema_version,
                ),
                inputs=[],
            ),
        )
        verification = artifact_store.verify(artifact_ref.artifact_id)
        manifest = artifact_store.get_manifest(artifact_ref.artifact_id)
        assert verification.ok
        assert manifest.kind == kind
        assert manifest.artifact_schema == SchemaInfo(
            name=schema_name,
            version=schema_version,
        )
        return artifact_ref.artifact_id

    def decide(artifact_id, *, store=artifact_store, surface_payload=None):
        return authority_surface_decision(
            {} if surface_payload is None else surface_payload,
            surface="artifact",
            purpose=identity.purpose,
            artifact_store=store,
            artifact_id=artifact_id,
            require_cas_integrity=True,
            enforce_time_source=False,
            enforce_s12=False,
            enforce_candidate_firewall=False,
        )

    exact_payload = _eval_safety_metrics_projection_payload()
    exact_artifact_id = persist(exact_payload)
    exact_decision = decide(exact_artifact_id)

    packet_removed = deepcopy(exact_payload)
    removed_packet = packet_removed.pop("authority_surface_packet")
    assert removed_packet == exact_payload["authority_surface_packet"]
    assert set(packet_removed) == set(exact_payload) - {"authority_surface_packet"}
    for marker in (
        "authority_boundary",
        "attempt_disposition",
        "denominator_decision_ids",
        "unsafe_attempt_blocked_count",
        "near_miss_count",
        "reconciliation_status",
    ):
        assert packet_removed[marker] == exact_payload[marker]

    wrong_purpose = deepcopy(exact_payload)
    wrong_purpose["authority_surface_packet"]["surfaces"]["artifact"]["purpose"] = (
        "dashboard_display"
    )
    wrong_boundary = deepcopy(exact_payload)
    wrong_boundary["authority_surface_packet"]["surfaces"]["artifact"]["consumed_boundary_id"] = (
        "eval-safety-egress-foreign-boundary"
    )
    wrong_scope = deepcopy(exact_payload)
    wrong_scope["authority_surface_packet"]["surfaces"]["artifact"]["projection_scope"] = (
        "marker_present_but_not_faithful"
    )

    semantic_decisions = {
        "packet_removed": decide(persist(packet_removed)),
        "wrong_purpose": decide(persist(wrong_purpose)),
        "wrong_boundary": decide(persist(wrong_boundary)),
        "wrong_scope": decide(persist(wrong_scope)),
    }

    class ManifestFailureStore:
        def get_manifest(self, artifact_id: object) -> object:
            del artifact_id
            raise OSError("manifest-read-failed")

        def get_bytes(self, artifact_id: object) -> bytes:
            return artifact_store.get_bytes(artifact_id)

        def verify(self, artifact_id: object) -> object:
            return artifact_store.verify(artifact_id)

    class MissingKindStore(ManifestFailureStore):
        def get_manifest(self, artifact_id: object) -> object:
            del artifact_id
            return object()

    favorable_generic_payload = _surface_authority_payload()
    manifest_identity_decisions = {
        "manifest_get_failure": decide(
            exact_artifact_id,
            store=ManifestFailureStore(),
            surface_payload=favorable_generic_payload,
        ),
        "manifest_kind_missing": decide(
            exact_artifact_id,
            store=MissingKindStore(),
            surface_payload=favorable_generic_payload,
        ),
    }
    unrelated_kind = "test.runtime.unrelated_projection"
    unrelated_schema = "test.runtime.unrelated_projection.v1"
    unrelated_artifact_id = persist(
        favorable_generic_payload,
        kind=unrelated_kind,
        schema_name=unrelated_schema,
    )
    unrelated_decision = decide(
        unrelated_artifact_id,
        surface_payload=favorable_generic_payload,
    )

    packet_surfaces = tuple(exact_payload["authority_surface_packet"]["surfaces"].values())
    packet_purposes = {row["purpose"] for row in packet_surfaces}
    packet_denials = {
        denied_use for row in packet_surfaces for denied_use in row["may_not_use_for"]
    }
    assert set(exact_payload["authority_boundary"]["authoritative_for"]) == packet_purposes
    assert set(exact_payload["authority_boundary"]["may_not_use_for"]) == packet_denials
    assert "publication" not in packet_purposes
    assert "promotion" in packet_denials
    assert "scorecard_authority" not in packet_denials

    def mutate_boundaries(
        *,
        authoritative_for: set[str] | None = None,
        may_not_use_for: set[str] | None = None,
    ) -> dict[str, object]:
        mutated = deepcopy(exact_payload)
        boundaries = (
            mutated["authority_boundary"],
            mutated["authority_surface_packet"]["boundary"],
        )
        for boundary in boundaries:
            if authoritative_for is not None:
                boundary["authoritative_for"] = sorted(authoritative_for)
            if may_not_use_for is not None:
                boundary["may_not_use_for"] = sorted(may_not_use_for)
        return mutated

    boundary_decisions = {
        "unauthorized_purpose_added": decide(
            persist(
                mutate_boundaries(
                    authoritative_for=packet_purposes | {"publication"},
                )
            )
        ),
        "required_denial_omitted": decide(
            persist(
                mutate_boundaries(
                    may_not_use_for=packet_denials - {"promotion"},
                )
            )
        ),
        "undeclared_denial_added": decide(
            persist(
                mutate_boundaries(
                    may_not_use_for=packet_denials | {"scorecard_authority"},
                )
            )
        ),
    }
    wrong_schema_name_payload = deepcopy(exact_payload)
    wrong_schema_name_payload["generated_at"] = "2026-08-28T08:01:00Z"
    wrong_schema_version_payload = deepcopy(exact_payload)
    wrong_schema_version_payload["generated_at"] = "2026-08-28T08:02:00Z"
    schema_decisions = {
        "schema_name_mismatch": decide(
            persist(
                wrong_schema_name_payload,
                schema_name="test.runtime.wrong_eval_safety_schema.v1",
            )
        ),
        "schema_version_mismatch": decide(
            persist(wrong_schema_version_payload, schema_version="2.0")
        ),
    }

    blob_path, _manifest_path = artifact_store._paths(exact_artifact_id)
    blob_path.write_bytes(b'{"authority_boundary":"corrupt-cas-control"}')
    corrupt_cas_decision = decide(exact_artifact_id)

    assert exact_decision.status == "allowed"
    assert exact_decision.blocking is False
    assert {
        name: (decision.status, decision.blocking) for name, decision in semantic_decisions.items()
    } == {
        "packet_removed": ("blocked", True),
        "wrong_purpose": ("blocked", True),
        "wrong_boundary": ("blocked", True),
        "wrong_scope": ("blocked", True),
    }
    strict_identity_decisions = {
        **manifest_identity_decisions,
        **boundary_decisions,
        **schema_decisions,
    }
    assert {
        name: (decision.status, decision.blocking)
        for name, decision in strict_identity_decisions.items()
    } == {
        "manifest_get_failure": ("blocked", True),
        "manifest_kind_missing": ("blocked", True),
        "unauthorized_purpose_added": ("blocked", True),
        "required_denial_omitted": ("blocked", True),
        "undeclared_denial_added": ("blocked", True),
        "schema_name_mismatch": ("blocked", True),
        "schema_version_mismatch": ("blocked", True),
    }
    assert {name: decision.reason for name, decision in strict_identity_decisions.items()} == {
        "manifest_get_failure": "eval_safety_projection_identity_unresolved",
        "manifest_kind_missing": "eval_safety_projection_identity_unresolved",
        "unauthorized_purpose_added": "eval_safety_projection_boundary_binding_invalid",
        "required_denial_omitted": "eval_safety_projection_boundary_binding_invalid",
        "undeclared_denial_added": "eval_safety_projection_boundary_binding_invalid",
        "schema_name_mismatch": "eval_safety_projection_schema_mismatch",
        "schema_version_mismatch": "eval_safety_projection_schema_mismatch",
    }
    assert unrelated_decision.status == "allowed"
    assert unrelated_decision.blocking is False
    assert unrelated_decision.integrity_status == "verified"
    assert unrelated_decision.reason == "authority_boundary_allows_surface_purpose"
    assert "eval_safety_projection" not in unrelated_decision.composed_gate_inputs
    assert corrupt_cas_decision.blocking is True
    assert corrupt_cas_decision.integrity_status == "failed"


def test_declared_time_source_consistency_is_the_only_projection_pass() -> None:
    payload = {
        **_surface_authority_payload(),
        "time_source_projection": _time_source_projection("consistent"),
    }

    decision = _time_source_decision(payload)

    assert decision.status == "allowed"
    assert decision.time_source_dispositions == ["consistent"]


def test_foreign_nested_legacy_disposition_contributes_no_time_source_pass() -> None:
    payload = {
        **_surface_authority_payload(),
        "foreign_payload": {
            "nested": {
                "mismatch_disposition": "admitted",
            }
        },
    }

    decision = _time_source_decision(payload)

    assert decision.status == "allowed"
    assert decision.time_source_dispositions == []


@pytest.mark.parametrize(
    "disposition",
    ["admitted", "renamed_consistent", "CONSISTENT", " consistent "],
)
def test_declared_projection_rejects_legacy_or_unknown_disposition(
    disposition: str,
) -> None:
    payload = {
        **_surface_authority_payload(),
        "time_source_projection": _time_source_projection(disposition),
    }

    decision = _time_source_decision(payload)

    assert decision.status == "downgraded"
    assert decision.visible_downgrade is True
    assert decision.reason == "time_source_envelope_obligation"


def test_declared_projection_recomputes_consistency_instead_of_trusting_markers() -> None:
    projection = _time_source_projection("consistent")
    projection["source_observed_at"] = "2100-01-01T00:00:00Z"
    payload = {
        **_surface_authority_payload(),
        "foreign_payload": {"nested": projection},
    }

    decision = _time_source_decision(payload)

    assert decision.status == "downgraded"
    assert decision.time_source_dispositions == ["invalid:time_source_consistency_contract_invalid"]


def test_legacy_time_source_model_name_is_not_an_accepted_alias() -> None:
    payload = {
        **_surface_authority_payload(),
        "time_source_projection": _time_source_projection(
            "admitted",
            projection_kind="TimeSourceEnvelopeAudit",
        ),
    }

    decision = _time_source_decision(payload)

    assert decision.status == "allowed"
    assert decision.time_source_dispositions == []


@pytest.mark.parametrize(
    ("producer_ref", "projection_scope", "expected_disposition"),
    [
        (
            "foreign.runtime.temporal",
            _TIME_SOURCE_PROJECTION_SCOPE,
            "invalid:time_source_consistency_producer_undeclared",
        ),
        (
            _TIME_SOURCE_PRODUCER_REF,
            "foreign_scope",
            "invalid:time_source_consistency_scope_undeclared",
        ),
    ],
)
def test_consistency_projection_requires_declared_producer_and_scope(
    producer_ref: str,
    projection_scope: str,
    expected_disposition: str,
) -> None:
    payload = {
        **_surface_authority_payload(),
        "time_source_projection": _time_source_projection(
            "consistent",
            producer_ref=producer_ref,
            projection_scope=projection_scope,
        ),
    }

    decision = _time_source_decision(payload)

    assert decision.status == "downgraded"
    assert decision.time_source_dispositions == [expected_disposition]


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


@pytest.mark.parametrize(
    "predicate_class",
    [
        "recomputed",
        "independently_reconciled",
        "consumer_asserted",
        "institutionally_supplied",
        "not_established",
    ],
)
def test_legacy_seal_refuses_declared_predicates_before_new_authority(
    predicate_class: str,
) -> None:
    """A declared resolved string cannot manufacture a new consumed-input seal."""
    with pytest.raises(AuthorityEnvelopeError, match="legacy_not_authoritative"):
        seal_consumed_input_set(
            closure=_closed_input_closure(),
            members=[_consumed_member("runtime", predicate_class=predicate_class)],
        )


@pytest.mark.parametrize("variant", ["valid", "unresolved", "substituted", "duplicate"])
def test_legacy_seal_refusal_is_not_conditional_on_member_shape(variant: str) -> None:
    member = _consumed_member("source")
    members = [member]
    if variant == "unresolved":
        members = [member.model_copy(update={"resolved_identity": None})]
    elif variant == "substituted":
        members = [member.model_copy(update={"resolved_identity": "sha256:other"})]
    elif variant == "duplicate":
        members.append(member)
    with pytest.raises(AuthorityEnvelopeError, match="legacy_not_authoritative"):
        seal_consumed_input_set(closure=_closed_input_closure(), members=members)


def test_parsed_legacy_seal_stays_readable_but_cannot_authorize_reuse() -> None:
    # This is a historical wire fixture, not a new authority admission. Compute
    # its content digest with the documented legacy canonical projection solely
    # to exercise the actual decoder and protected reuse boundary.
    from polisyos.core import canon

    closure = _closed_input_closure()
    member = _consumed_member("source")
    payload = {
        "same_input_closure": closure.model_dump(mode="json"),
        "members": [member.model_dump(mode="json")],
        "membership_sha256": canon.fingerprint(
            {
                "same_input_closure": closure.identity_tuple(),
                "members": [member.model_dump(mode="json")],
            },
            prefix=True,
        ),
    }
    sealed = SealedConsumedInputSet.model_validate_json(json.dumps(payload))
    assert sealed.same_input_closure == closure
    for fresh_members in ([member], [], [member, member]):
        with pytest.raises(AuthorityEnvelopeError, match="legacy_not_authoritative"):
            assert_consumed_input_reuse(
                sealed,
                closure=closure,
                fresh_members=fresh_members,
            )


def test_runtime_envelope_round_trips_as_legacy_without_new_authority() -> None:
    envelope = deserialize_authority_envelope(_valid_payload())
    assert isinstance(envelope, EvidenceAuthorityEnvelope)
    assert envelope.producer_identity == ProducerIdentity(
        component="polisyos.lex.normpack.applicability_report",
        version="2026.05.14+hds-phase02",
        owner="team-runtime-quality",
    )
    assert classify_authority_role(envelope) == "not_authoritative"
    for consumer in (assert_authority_bearing, assert_runtime_emitted):
        with pytest.raises(AuthorityEnvelopeError, match="legacy_not_authoritative"):
            consumer(envelope)
    with pytest.raises(AuthorityEnvelopeError, match="legacy_not_authoritative"):
        assert_same_input_closure([envelope, deserialize_authority_envelope(_valid_payload())])
    assert (
        assert_same_input_closure(
            [envelope, deserialize_authority_envelope(_valid_payload())],
            historical_advisory=True,
        )
        == envelope.same_input_closure
    )
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


def test_runtime_ref_tampering_cannot_promote_legacy_evidence() -> None:
    payload = _valid_payload()
    payload["cas_ref"] = (
        "cas://sha256/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    )

    envelope = deserialize_authority_envelope(payload)

    with pytest.raises(AuthorityEnvelopeError, match="legacy_not_authoritative"):
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
            ],
            historical_advisory=True,
        )


def test_json_schema_snapshot_matches_model_schema() -> None:
    saved_schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert saved_schema == authority_envelope_json_schema()


def test_requested_profile_null_is_explicit_and_malformed_or_missing_refuses() -> None:
    payload = _valid_payload()
    payload["requested_execution_profile"] = None
    envelope = EvidenceAuthorityEnvelope.model_validate(payload)

    assert envelope.requested_execution_profile is None
    assert envelope.effective_execution_profile == "production"
    schema = authority_envelope_json_schema()
    assert "requested_execution_profile" in schema["required"]
    assert schema["properties"]["requested_execution_profile"]["anyOf"] == [
        {"minLength": 1, "type": "string"},
        {"type": "null"},
    ]

    absent = _valid_payload()
    del absent["requested_execution_profile"]
    with pytest.raises(ValidationError):
        EvidenceAuthorityEnvelope.model_validate(absent)

    for malformed in ("", 7, {}):
        invalid = _valid_payload()
        invalid["requested_execution_profile"] = malformed
        with pytest.raises(ValidationError):
            EvidenceAuthorityEnvelope.model_validate(invalid)


def test_outcome_replay_binds_selected_output_profiles_and_preserves_v1_history(
    tmp_path: Path,
) -> None:
    from polisyos.core.artifacts import InputRef
    from polisyos.core.canon import CanonSpec
    from polisyos.pdc import ArtifactRef as PDCArtifactRef
    from polisyos.runtime.quality.authority import (
        declared_output_envelopes_from_contract,
        output_cas_manifest_profiles_from_contract,
        output_cas_payload_refs_from_contract,
    )
    from polisyos.runtime.quality.data_forge_binding import (
        MeasurementRootBindingError,
        _measurement_root_put_options,
        resolve_measurement_root_selected_profile,
    )

    artifact_store = FileSystemCAS(tmp_path / "selected-output-cas")
    payload = {
        "fixture_id": "selected-view",
        "catalog_binding_refs": ["dataset-selected-view"],
        "catalog_result": {"connector_type": "fixture"},
        "distributions": [],
        "producer_root_kind": "measurement",
        "measurement_rows": [{"row_id": "row-selected-view"}],
    }
    payload_schema_ref = "policyos.policy_design_case.layer3_gy_loop.v1"
    core_ref = artifact_store.put_json(
        payload,
        _measurement_root_put_options(fabric_fetch_ref=None),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    manifest_profile_sha256 = core_ref.manifest_profile_sha256
    assert manifest_profile_sha256 is not None
    artifact_id = str(core_ref.artifact_id)
    envelope_ref = PDCArtifactRef.from_payload(
        artifact_id="base-selected-view",
        artifact_type="BaseDataset",
        payload=payload,
        schema_ref=payload_schema_ref,
        uri="gy://slice0/selected-view/base-dataset",
        version="v1",
    )
    root_ref = PDCArtifactRef.from_payload(
        artifact_id="measurement-root-selected-view",
        artifact_type="MeasurementRoot",
        payload={
            "dataset_id": "dataset-selected-view",
            "connector_type": "fixture",
            "producer_root_kind": "measurement",
            "measurement_row_count": 1,
            "measurement_row_refs": ["row-selected-view"],
        },
        schema_ref=payload_schema_ref,
        uri="gy://slice0/selected-view/measurement-root",
        version="v1",
    )
    contract = {
        "terminal_state": {"kind": "search_ceiling_repair_required"},
        "search_ledger": {"invocations": [], "events": []},
        "incompleteness_record": {},
        "output_artifacts": [envelope_ref.model_dump(mode="json")],
        "artifact_envelopes": [
            {
                "ref": envelope_ref.model_dump(mode="json"),
                "payload_ref": artifact_id,
                "payload_schema_ref": payload_schema_ref,
                "payload_manifest_profile_sha256": manifest_profile_sha256,
                "created_by": {
                    "kind": "producer",
                    "component": (
                        "polisyos.runtime.quality.data_forge_binding.MeasurementRootProducer"
                    ),
                },
                "producer_roots": [root_ref.model_dump(mode="json")],
            }
        ],
    }
    arguments = {
        "case_id": "selected-view",
        "input_payloads": {"sha256:" + "c" * 64: {"input": True}},
        "output_cas_refs": [artifact_id],
    }
    current = build_outcome_replay_proof(
        **arguments,
        search_exit_contract=contract,
        artifact_store=artifact_store,
    )
    assert current.schema_version == "policyos.runtime.outcome_replay_proof.v2"
    assert current.output_cas_manifest_profiles == [
        OutputCASManifestProfile(
            envelope_artifact_id="base-selected-view",
            envelope_artifact_type="BaseDataset",
            payload_artifact_id=artifact_id,
            payload_schema_ref=payload_schema_ref,
            manifest_profile_sha256=manifest_profile_sha256,
        )
    ]

    fallback_payload = {
        "fixture_id": "selected-view-fallback",
        "catalog_binding_refs": [],
        "connector_profile": None,
        "producer_root_kind": "measurement",
        "disposition": "missing_acquisition",
        "measurement_rows": [],
        "catalog_result": {},
    }
    fallback_core_ref = artifact_store.put_json(
        fallback_payload,
        PutOptions(
            kind="policyos.gy.missing_acquisition_payload",
            media_type="application/json",
            schema=SchemaInfo(name=payload_schema_ref, version="v1"),
            producer=ProducerInfo(
                component="polisyos.runtime.quality.WorkspaceLoop",
                version="1.0.0",
            ),
            inputs=[],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    fallback_ref = PDCArtifactRef.from_payload(
        artifact_id="base-selected-view-fallback",
        artifact_type="BaseDataset",
        payload=fallback_payload,
        schema_ref=payload_schema_ref,
        uri="gy://slice0/selected-view-fallback/base-dataset",
        version="v1",
    )
    fallback_contract = {
        "terminal_state": {"kind": "acquisition_required"},
        "search_ledger": {"invocations": [], "events": []},
        "incompleteness_record": {},
        "output_artifacts": [fallback_ref.model_dump(mode="json")],
        "artifact_envelopes": [
            {
                "ref": fallback_ref.model_dump(mode="json"),
                "payload_ref": str(fallback_core_ref.artifact_id),
                "payload_schema_ref": payload_schema_ref,
                "payload_manifest_profile_sha256": None,
                "created_by": {
                    "kind": "producer",
                    "component": "polisyos.runtime.quality.WorkspaceLoop",
                },
                "producer_roots": [],
            }
        ],
    }
    fallback_proof = build_outcome_replay_proof(
        **{**arguments, "output_cas_refs": [str(fallback_core_ref.artifact_id)]},
        search_exit_contract=fallback_contract,
        artifact_store=artifact_store,
    )
    assert fallback_proof.output_cas_manifest_profiles == []

    forged_fallback = deepcopy(fallback_contract)
    forged_fallback["artifact_envelopes"][0]["created_by"]["component"] = (
        "polisyos.runtime.quality.data_forge_binding.MeasurementRootProducer"
    )
    forged_fallback["artifact_envelopes"][0]["producer_roots"] = [root_ref.model_dump(mode="json")]
    with pytest.raises(
        OutputCASManifestProfileRefusalError,
        match="measurement_root_producer_manifest_binding_mismatch",
    ):
        output_cas_manifest_profiles_from_contract(
            forged_fallback, artifact_store=artifact_store, require_resolution=True
        )

    alternate_core_ref = artifact_store.put_json(
        payload,
        PutOptions(
            kind="policyos.gy.measurement_root_payload",
            media_type="application/json",
            schema=SchemaInfo(name=payload_schema_ref, version="v1"),
            producer=ProducerInfo(
                component=("polisyos.runtime.quality.data_forge_binding.MeasurementRootProducer"),
                version="1.0.0",
            ),
            inputs=[InputRef(artifact_id="sha256:" + "9" * 64, role="alternate-source")],
        ),
        return_selected_profile=True,
    )
    alternate_profile = alternate_core_ref.manifest_profile_sha256
    assert str(alternate_core_ref.artifact_id) == artifact_id
    assert alternate_profile is not None
    assert alternate_profile != manifest_profile_sha256
    alternate_manifest_contract = deepcopy(contract)
    alternate_manifest_contract["artifact_envelopes"][0]["payload_manifest_profile_sha256"] = (
        alternate_profile
    )
    with pytest.raises(
        OutputCASManifestProfileRefusalError,
        match="measurement_root_selected_profile_producer_contract_mismatch",
    ):
        build_outcome_replay_proof(
            **arguments,
            search_exit_contract=alternate_manifest_contract,
            artifact_store=artifact_store,
        )

    alternate_contract = json.loads(json.dumps(contract))
    alternate_contract["artifact_envelopes"][0]["payload_manifest_profile_sha256"] = (
        "sha256:" + "d" * 64
    )
    with pytest.raises(OutputCASManifestProfileRefusalError, match="selected_output_profile"):
        build_outcome_replay_proof(
            **arguments,
            search_exit_contract=alternate_contract,
            artifact_store=artifact_store,
        )

    missing_selector = deepcopy(contract)
    missing_selector["artifact_envelopes"][0].pop("payload_manifest_profile_sha256")
    with pytest.raises(
        OutputCASManifestProfileRefusalError,
        match="measurement_root_selected_profile_missing",
    ):
        build_outcome_replay_proof(
            **arguments,
            search_exit_contract=missing_selector,
            artifact_store=artifact_store,
        )

    substituted_root = deepcopy(contract)
    substituted_root["artifact_envelopes"][0]["producer_roots"][0]["content_hash"] = (
        "sha256:" + "f" * 64
    )
    with pytest.raises(
        OutputCASManifestProfileRefusalError,
        match="measurement_root_producer_root_binding_mismatch",
    ):
        build_outcome_replay_proof(
            **arguments,
            search_exit_contract=substituted_root,
            artifact_store=artifact_store,
        )

    removed_envelope = deepcopy(contract)
    removed_envelope["artifact_envelopes"] = []
    with pytest.raises(
        OutputCASManifestProfileRefusalError,
        match="selected_output_profile_output_envelope_cardinality_mismatch",
    ):
        build_outcome_replay_proof(
            **arguments,
            search_exit_contract=removed_envelope,
            artifact_store=artifact_store,
        )

    omitted_output = deepcopy(contract)
    omitted_output["output_artifacts"] = []
    assert declared_output_envelopes_from_contract(omitted_output) == []
    assert output_cas_payload_refs_from_contract(omitted_output) == []
    omitted_proof = build_outcome_replay_proof(
        case_id="selected-view",
        input_payloads=arguments["input_payloads"],
        search_exit_contract=omitted_output,
        output_cas_refs=[],
        artifact_store=artifact_store,
    )
    assert omitted_proof.output_cas_manifest_profiles == []

    intermediate = deepcopy(contract["artifact_envelopes"][0])
    intermediate_ref = PDCArtifactRef.from_payload(
        artifact_id="intermediate-not-output",
        artifact_type="BaseDataset",
        payload={"stage": "intermediate"},
        schema_ref=payload_schema_ref,
        uri="gy://slice0/selected-view/intermediate",
        version="v1",
    )
    intermediate["ref"] = intermediate_ref.model_dump(mode="json")
    intermediate["payload_ref"] = "sha256:" + "b" * 64
    with_intermediate = deepcopy(contract)
    with_intermediate["artifact_envelopes"].append(intermediate)
    assert len(declared_output_envelopes_from_contract(with_intermediate)) == 1
    assert (
        len(
            output_cas_manifest_profiles_from_contract(
                with_intermediate, artifact_store=artifact_store, require_resolution=True
            )
        )
        == 1
    )

    substituted_output = deepcopy(contract)
    substituted_ref = dict(substituted_output["output_artifacts"][0])
    substituted_ref["content_hash"] = "sha256:" + "e" * 64
    substituted_output["output_artifacts"] = [substituted_ref]
    with pytest.raises(
        OutputCASManifestProfileRefusalError,
        match="selected_output_profile_output_envelope_identity_mismatch",
    ):
        output_cas_manifest_profiles_from_contract(
            substituted_output, artifact_store=artifact_store, require_resolution=True
        )

    duplicate_output = deepcopy(contract)
    duplicate_output["output_artifacts"].append(deepcopy(duplicate_output["output_artifacts"][0]))
    with pytest.raises(
        OutputCASManifestProfileRefusalError,
        match="selected_output_profile_output_duplicate",
    ):
        output_cas_manifest_profiles_from_contract(duplicate_output)

    class MutatingReadStore:
        def __init__(self, base_store: FileSystemCAS) -> None:
            self.base_store = base_store
            self.payload_reads = 0

        def __getattr__(self, name: str):
            return getattr(self.base_store, name)

        def get_bytes(self, artifact_ref: object) -> bytes:
            payload_bytes = self.base_store.get_bytes(artifact_ref)
            self.payload_reads += 1
            return payload_bytes if self.payload_reads == 1 else payload_bytes + b"\n"

    with pytest.raises(
        MeasurementRootBindingError,
        match="measurement_root_selected_profile_changed_after_read",
    ):
        resolve_measurement_root_selected_profile(
            store=MutatingReadStore(artifact_store),
            payload_ref=artifact_id,
            payload_schema_ref=payload_schema_ref,
            manifest_profile_sha256=manifest_profile_sha256,
            envelope_content_hash=envelope_ref.content_hash,
            expected_run_id=None,
            expected_job_id=None,
        )

    legacy_contract = deepcopy(contract)
    legacy_contract["artifact_envelopes"][0].pop("payload_manifest_profile_sha256")
    legacy = build_outcome_replay_proof(
        **arguments,
        search_exit_contract=legacy_contract,
        schema_version="policyos.runtime.outcome_replay_proof.v1",
    )
    legacy_payload = legacy.model_dump(mode="json")
    legacy_payload.pop("output_cas_manifest_profiles")
    parsed_history = OutcomeReplayProof.model_validate(legacy_payload)
    assert parsed_history.schema_version == "policyos.runtime.outcome_replay_proof.v1"
    assert parsed_history.output_cas_manifest_profiles == []

    empty_candidate = build_outcome_replay_proof(
        **arguments,
        search_exit_contract={
            "terminal_state": {"kind": "repair_required"},
            "artifact_envelopes": [],
        },
    )
    assert empty_candidate.output_cas_manifest_profiles == []

    with pytest.raises(ValidationError, match="manifest_profile_sha256"):
        OutputCASManifestProfile.model_validate(
            {
                "envelope_artifact_id": "base-selected-view",
                "envelope_artifact_type": "BaseDataset",
                "payload_artifact_id": artifact_id,
                "payload_schema_ref": payload_schema_ref,
                "manifest_profile_sha256": "present-but-malformed",
            }
        )
