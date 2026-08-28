# ruff: noqa: S101

from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts import FileSystemCAS, PutOptions, SchemaInfo
from polisyos.runtime.http.services.temporal import (
    build_time_source_consistency_audit_projection,
)
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
    authority_surface_decision,
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
SCHEMA_PATH = (
    REPO_ROOT
    / "schemas/runtime_quality/evidence_authority_envelope_v1.schema.json"
)
_TIME_SOURCE_PROJECTION_KIND = "time_source_consistency_audit_projection"
_TIME_SOURCE_PRODUCER_REF = (
    "polisyos.runtime.http.services.temporal."
    "build_time_source_consistency_audit_projection"
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
    wrong_boundary["authority_surface_packet"]["surfaces"]["artifact"][
        "consumed_boundary_id"
    ] = "eval-safety-egress-foreign-boundary"
    wrong_scope = deepcopy(exact_payload)
    wrong_scope["authority_surface_packet"]["surfaces"]["artifact"][
        "projection_scope"
    ] = "marker_present_but_not_faithful"

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

    packet_surfaces = tuple(
        exact_payload["authority_surface_packet"]["surfaces"].values()
    )
    packet_purposes = {row["purpose"] for row in packet_surfaces}
    packet_denials = {
        denied_use
        for row in packet_surfaces
        for denied_use in row["may_not_use_for"]
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

    blob_path, _manifest_path = artifact_store.get_paths(exact_artifact_id)
    blob_path.write_bytes(b'{"authority_boundary":"corrupt-cas-control"}')
    corrupt_cas_decision = decide(exact_artifact_id)

    assert exact_decision.status == "allowed"
    assert exact_decision.blocking is False
    assert {
        name: (decision.status, decision.blocking)
        for name, decision in semantic_decisions.items()
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
    assert {
        name: decision.reason for name, decision in strict_identity_decisions.items()
    } == {
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
    assert decision.time_source_dispositions == [
        "invalid:time_source_consistency_contract_invalid"
    ]


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
