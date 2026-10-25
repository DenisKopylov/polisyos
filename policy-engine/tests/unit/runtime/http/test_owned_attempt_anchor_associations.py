from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Callable, Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal, get_type_hints

import pytest
from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import (
    ArtifactGovernanceInfo,
    ArtifactRef,
    SchemaInfo,
    artifact_reference_parts,
)
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.owned_attempt_anchor import (
    OwnedAttemptAnchor,
    OwnedAttemptAnchorRef,
    OwnedHTERequestContextV1,
    SelectedArtifactRef,
)
from polisyos.core.contracts.runtime import DirectMethodExecutionHTEResourceEvidence
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.ir.analytics.hte import HTEResourceExecutionEvidenceV1
from polisyos.runtime.http.services.control.owned_attempt_anchor import (
    OwnedAttemptAnchorVersionRefusalError,
    _read_owned_attempt_anchor,
    _read_profiled_model,
    _read_projection_manifest,
    _require_intent_request_context_pair,
    _require_successor_anchor_intent_pair,
    _resolve_historical_search_binding,
    _resource_evidence_matches_receipt,
    _resource_evidence_payload,
    _resource_evidence_payload_for_consumer,
    resolve_owned_attempt_anchor_association,
    resolve_owned_attempt_anchor_projection_association,
    resolve_owned_attempt_anchor_refusal_association,
)


class _IntentVersionFixture(BaseModel):
    """Minimal immutable owner-intent view for selector-version checks."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: str
    method_fqn: str
    method_version: str | None = None
    owned_hte_request_context: OwnedHTERequestContextV1 | None


def _cas_selector_id(selector: ArtifactID | ArtifactRef | str) -> str:
    """Return the same normalized CAS root used by ArtifactStore.get_bytes."""
    artifact_id, _profile_sha256, _ref = artifact_reference_parts(selector)
    return artifact_id.root


def _decision_validity_packet_key(packet_ref: ArtifactRef) -> str:
    """Return the canonical artifact ID key used by string-only validity APIs."""
    return str(packet_ref.artifact_id)


def _reject_output_payload_reader(
    original_get_bytes: Callable[[ArtifactID | ArtifactRef | str], bytes],
    forbidden_payload_ids: set[str],
) -> Callable[[ArtifactID | ArtifactRef | str], bytes]:
    """Build the projection test's no-output-payload-read tripwire."""

    def reject_output_payload(selector: ArtifactID | ArtifactRef | str) -> bytes:
        if _cas_selector_id(selector) in forbidden_payload_ids:
            raise AssertionError("bounded projection must not read HTE or source payload bytes")
        return original_get_bytes(selector)

    return reject_output_payload


def test_packet_association_json_normalizes_optional_nulls_and_rejects_invalid_selectors() -> None:
    """Normalize declared nullable fields through the strict wire DTO only."""
    from polisyos.core.contracts.owned_attempt_anchor import (
        OwnedAttemptAnchorProjectionAssociation,
    )
    from polisyos.runtime.http.services.candidate_hte_packet_projection import (
        CandidatePacketProjectionRefusalError,
        require_exact_candidate_packet_ref,
    )
    from tests.unit.scientist.nodes.builtins.decide.test_completed_hte_source_projection import (
        _selected_source,
    )

    association = _selected_source().association
    packet_wire = association.model_dump(mode="json", exclude_none=True)
    response_wire = association.model_dump(mode="json")
    nullable_refs = {
        "hte_result_ref",
        "inference_basis_ref",
        "invocation_basis_ref",
        "refusal_diagnostic_ref",
        "search_uncertainty_task_binding_ref",
    }
    assert all(getattr(association, name) is None for name in nullable_refs)
    assert nullable_refs.isdisjoint(packet_wire)
    assert all(response_wire[name] is None for name in nullable_refs)

    packet_model = OwnedAttemptAnchorProjectionAssociation.model_validate_json(
        json.dumps(packet_wire, ensure_ascii=False, allow_nan=False), strict=True
    )
    response_model = OwnedAttemptAnchorProjectionAssociation.model_validate_json(
        json.dumps(response_wire, ensure_ascii=False, allow_nan=False), strict=True
    )
    assert packet_model.model_dump(
        mode="python", exclude={"verified_at"}
    ) == response_model.model_dump(mode="python", exclude={"verified_at"})
    with pytest.raises(ValidationError):
        OwnedAttemptAnchorProjectionAssociation.model_validate_json(
            json.dumps(
                {**packet_wire, "unrecognized_association_field": "present"},
                ensure_ascii=False,
                allow_nan=False,
            ),
            strict=True,
        )

    packet_ref = ArtifactRef(
        artifact_id=ArtifactID.from_sha256_hex("8" * 64),
        kind="scientist.decision_packet",
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "1" * 64,
    )
    assert (
        require_exact_candidate_packet_ref(
            indexed_packet_ref=packet_ref,
            requested_packet_id=str(packet_ref.artifact_id),
            requested_manifest_profile_sha256=packet_ref.manifest_profile_sha256,
        )
        is packet_ref
    )
    with pytest.raises(
        CandidatePacketProjectionRefusalError, match="candidate_packet_profile_index_mismatch"
    ):
        require_exact_candidate_packet_ref(
            indexed_packet_ref=packet_ref,
            requested_packet_id=str(packet_ref.artifact_id),
            requested_manifest_profile_sha256="sha256:" + "2" * 64,
        )
    with pytest.raises(
        CandidatePacketProjectionRefusalError, match="candidate_packet_index_ref_incomplete"
    ):
        require_exact_candidate_packet_ref(
            indexed_packet_ref=packet_ref.model_copy(update={"kind": "scientist.other_packet"}),
            requested_packet_id=str(packet_ref.artifact_id),
            requested_manifest_profile_sha256=packet_ref.manifest_profile_sha256,
        )


def test_artifact_ref_identity_is_class_agnostic_and_binds_all_identity_fields() -> None:
    """Compare generic and typed refs by the complete four-field CAS identity."""
    from polisyos.core.artifacts import artifact_ref_identity_key
    from polisyos.core.contracts.scientist import DecisionPacketRef

    artifact_id = ArtifactID.from_sha256_hex("9" * 64)
    profile = "sha256:" + "a" * 64
    typed_packet_ref = DecisionPacketRef(
        artifact_id=artifact_id,
        manifest_profile_sha256=profile,
    )
    generic_packet_ref = ArtifactRef(
        artifact_id=artifact_id,
        kind="scientist.decision_packet",
        media_type="application/json",
        manifest_profile_sha256=profile,
    )
    expected_identity = (
        str(artifact_id),
        "scientist.decision_packet",
        "application/json",
        profile,
    )

    assert type(generic_packet_ref) is ArtifactRef
    assert type(typed_packet_ref) is DecisionPacketRef
    assert artifact_ref_identity_key(generic_packet_ref) == expected_identity
    assert artifact_ref_identity_key(typed_packet_ref) == expected_identity

    for mismatched_ref in (
        generic_packet_ref.model_copy(update={"kind": "scientist.other_packet"}),
        generic_packet_ref.model_copy(update={"media_type": "application/octet-stream"}),
        generic_packet_ref.model_copy(update={"manifest_profile_sha256": "sha256:" + "b" * 64}),
    ):
        assert mismatched_ref.artifact_id == artifact_id
        assert artifact_ref_identity_key(mismatched_ref) != expected_identity


def test_projection_payload_read_guard_uses_cas_selector_normalization() -> None:
    """Block equivalent ArtifactRef, ArtifactID, and wire-string selectors."""
    artifact_id = ArtifactID.from_sha256_hex("a" * 64)
    artifact_ref = ArtifactRef(
        artifact_id=artifact_id,
        kind="scientist.hte.outcome",
        media_type="application/json",
    )
    original_reads: list[ArtifactID | ArtifactRef | str] = []

    def original_get_bytes(selector: ArtifactID | ArtifactRef | str) -> bytes:
        original_reads.append(selector)
        return b"unexpected read"

    guarded_reader = _reject_output_payload_reader(
        original_get_bytes,
        {_cas_selector_id(artifact_ref)},
    )
    for selector in (artifact_ref, artifact_id, artifact_id.root):
        with pytest.raises(
            AssertionError,
            match="bounded projection must not read HTE or source payload bytes",
        ):
            guarded_reader(selector)
    assert original_reads == []


def test_decision_validity_packet_key_uses_artifact_id_with_profiled_ref() -> None:
    """Keep string-only state keys separate from profile-aware CAS selectors."""
    artifact_id = ArtifactID.from_sha256_hex("b" * 64)
    profile = "sha256:" + "c" * 64
    packet_ref = ArtifactRef(
        artifact_id=artifact_id,
        kind="scientist.decision_packet",
        media_type="application/json",
        manifest_profile_sha256=profile,
    )

    assert _decision_validity_packet_key(packet_ref) == str(artifact_id)
    assert artifact_reference_parts(packet_ref)[1] == profile


def _declared_request_context() -> OwnedHTERequestContextV1:
    """Return one strict successor request context with explicit selectors."""
    return OwnedHTERequestContextV1(
        request_estimand_status="declared",
        request_estimand="mean_effect_over_selected_x",
        request_target_scope_status="declared",
        request_target_scope="selected_evaluation_rows",
        outcome_variable_status="declared",
        outcome_variable_id="outcome.effect",
        treatment_variable_status="declared",
        treatment_variable_id="treatment.policy",
        contrast_status="declared",
        control_value=0.0,
        treated_value=1.0,
        request_alpha_status="declared",
        requested_alpha=0.05,
        requested_guarantee_status="not_established",
        requested_guarantee=None,
    )


def test_owner_intent_reader_enforces_legacy_and_successor_context_pairing() -> None:
    """Keep semantic and manifest intent versions bound to selector presence."""
    v2_context = _declared_request_context()
    requested = _IntentVersionFixture(
        schema_version="polisyos.runtime.observational_run_intent.v2",
        method_fqn="causal.hte.forest_dr@2.0.0",
        method_version="2.0.0",
        owned_hte_request_context=v2_context,
    )
    admitted = _IntentVersionFixture(
        schema_version="polisyos.runtime.content_admitted_observational_run_intent.v2",
        method_fqn="causal.hte.forest_dr@2.0.0",
        owned_hte_request_context=v2_context,
    )

    _require_intent_request_context_pair(requested, admitted)

    with pytest.raises(
        ValueError, match="owned_attempt_successor_intent_context_or_method_missing"
    ):
        _require_intent_request_context_pair(
            requested,
            _IntentVersionFixture(
                schema_version=admitted.schema_version,
                method_fqn=admitted.method_fqn,
                owned_hte_request_context=None,
            ),
        )

    mismatched_admission = _IntentVersionFixture(
        schema_version=admitted.schema_version,
        method_fqn=admitted.method_fqn,
        owned_hte_request_context=v2_context.model_copy(
            update={"request_target_scope": "population"}
        ),
    )
    with pytest.raises(ValueError, match="owned_attempt_request_and_admission_context_mismatch"):
        _require_intent_request_context_pair(requested, mismatched_admission)

    underdeclared_context = OwnedHTERequestContextV1.model_construct(
        **{
            **v2_context.model_dump(),
            "request_alpha_status": "not_established",
        }
    )
    underdeclared_request = _IntentVersionFixture.model_construct(
        schema_version=requested.schema_version,
        method_fqn=requested.method_fqn,
        method_version=requested.method_version,
        owned_hte_request_context=underdeclared_context,
    )
    with pytest.raises(ValueError, match="owned_attempt_successor_request_selector_not_declared"):
        _require_intent_request_context_pair(underdeclared_request, admitted)

    legacy = _IntentVersionFixture(
        schema_version="polisyos.runtime.observational_run_intent.v1",
        method_fqn="causal.hte.forest_dr@1.1.0",
        method_version="1.1.0",
        owned_hte_request_context=None,
    )
    legacy_admitted = _IntentVersionFixture(
        schema_version="polisyos.runtime.content_admitted_observational_run_intent.v1",
        method_fqn="causal.hte.forest_dr@1.1.0",
        owned_hte_request_context=None,
    )
    _require_intent_request_context_pair(legacy, legacy_admitted)

    with pytest.raises(ValueError, match="owned_attempt_legacy_intent_context_or_method_mismatch"):
        _require_intent_request_context_pair(
            _IntentVersionFixture(
                schema_version=legacy.schema_version,
                method_fqn=legacy.method_fqn,
                method_version=legacy.method_version,
                owned_hte_request_context=v2_context,
            ),
            legacy_admitted,
        )


class _SearchBindingFixture(BaseModel):
    """Typed binding payload returned by the Search owner."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["1.0"] = "1.0"


class _SearchBindingResolutionFixture(BaseModel):
    """Narrow structural return used to pin the Search owner callback boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["1.0"] = "1.0"
    resolution_status: Literal["current", "historical"]
    binding_ref: ArtifactRef
    binding: _SearchBindingFixture
    closure_status: Literal["recomputed", "not_established"]


class _R5ResourceReceiptFixture(BaseModel):
    """Strict status/scope with producer receipt observations retained as extras."""

    model_config = ConfigDict(extra="allow", frozen=True, strict=True)

    execution_status: Literal["not_started", "returned", "raised"]
    scope: Literal["producer_scoped_joblib_parallelism_one"]


def _r5_resource_anchor(
    *, method_fqn: str, profile_id: str, required_estimator_n_jobs: int | None
) -> SimpleNamespace:
    """Return an owner-selected R5 tuple for resource evidence reconciliation."""
    return SimpleNamespace(
        resource_policy_revision="r5",
        resource_policy_schema_version="polisyos.runtime.observational_input_resource_policy.v5",
        resource_policy_execution_scope="producer_scoped_joblib_parallelism_one",
        resource_policy_max_jobs=1,
        resource_policy_required_estimator_n_jobs=required_estimator_n_jobs,
        resource_policy_ref=ArtifactRef(
            artifact_id="sha256:" + "e" * 64,
            kind="runtime.observational_input_resource_policy",
            media_type="application/json",
            manifest_profile_sha256="sha256:" + "f" * 64,
        ),
        resource_policy_digest="a" * 64,
        resource_policy_method_fqn=method_fqn,
        resource_policy_method_profile_id=profile_id,
    )


def _r5_returned_resource_receipt(*, estimator_required: bool) -> _R5ResourceReceiptFixture:
    """Create one returned joblib receipt, with estimator observations when required."""
    payload: dict[str, object] = {
        "execution_status": "returned",
        "scope": "producer_scoped_joblib_parallelism_one",
        "joblib_started": True,
        "joblib_finished": True,
        "joblib_exit_status": "returned",
        "joblib_profile_id": "joblib.parallel_config.current_thread@1.0",
        "joblib_profile_revision": "1.0",
        "joblib_implementation": "joblib.parallel_config",
        "joblib_implementation_version": "1.5.0",
        "joblib_scope": "current_thread_joblib",
        "joblib_max_jobs": 1,
        "joblib_entry_effective_jobs": 1,
        "joblib_entry_backend_fqn": "joblib._parallel_backends.LokyBackend",
        "joblib_entry_config_sha256": "b" * 64,
        "joblib_entry_implementation_version": "1.5.0",
        "joblib_exit_effective_jobs": 1,
        "joblib_exit_backend_fqn": "joblib._parallel_backends.LokyBackend",
        "joblib_exit_config_sha256": "b" * 64,
        "joblib_exit_implementation_version": "1.5.0",
    }
    if estimator_required:
        payload.update(
            estimator_before_class_fqn="econml.dml.causal_forest.CausalForestDML",
            estimator_before_n_jobs=1,
            estimator_before_params_sha256="c" * 64,
            estimator_after_class_fqn="econml.dml.causal_forest.CausalForestDML",
            estimator_after_n_jobs=1,
            estimator_after_params_sha256="c" * 64,
        )
    return _R5ResourceReceiptFixture.model_validate(payload, strict=True)


@pytest.mark.parametrize(
    ("method_fqn", "profile_id", "estimator_required"),
    [
        (
            "causal.hte.causal_forest@2.0.0",
            "econml.causal_forest_dml.native_mean@2.0",
            True,
        ),
        ("causal.hte.double_ml@2.0.0", "econml.dml.point_only@2.0", False),
        ("causal.hte.meta_learner@2.0.0", "econml.meta_learner.point_only@2.0", False),
        (
            "causal.hte.forest_dr@2.0.0",
            "econml.forest_dr.native_mean@2.0",
            True,
        ),
    ],
)
def test_r5_resource_evidence_requires_joblib_and_method_specific_estimator_observation(
    method_fqn: str,
    profile_id: str,
    estimator_required: bool,
) -> None:
    anchor = _r5_resource_anchor(
        method_fqn=method_fqn,
        profile_id=profile_id,
        required_estimator_n_jobs=1 if estimator_required else None,
    )
    receipt = _r5_returned_resource_receipt(estimator_required=estimator_required)

    evidence = _resource_evidence_payload(anchor=anchor, receipt=receipt)

    assert evidence is not None
    assert evidence["owner_policy_schema_version"] == (
        "polisyos.runtime.observational_input_resource_policy.v5"
    )
    assert evidence["owner_policy_revision"] == "r5"
    assert evidence["owner_policy_execution_scope"] == ("producer_scoped_joblib_parallelism_one")
    assert evidence["joblib_observation_status"] == "recomputed"
    assert evidence["joblib_started"] is True
    assert evidence["joblib_finished"] is True
    assert evidence["joblib_entry_effective_jobs"] == 1
    assert evidence["joblib_exit_effective_jobs"] == 1
    assert evidence["estimator_observation_status"] == (
        "recomputed" if estimator_required else "not_applicable"
    )


@pytest.mark.parametrize(
    "mutation",
    ["joblib_oversubscribed", "required_estimator_observation_missing"],
)
def test_r5_resource_evidence_refuses_missing_or_wrong_runtime_observation(
    mutation: str,
) -> None:
    anchor = _r5_resource_anchor(
        method_fqn="causal.hte.causal_forest@2.0.0",
        profile_id="econml.causal_forest_dml.native_mean@2.0",
        required_estimator_n_jobs=1,
    )
    receipt_payload = _r5_returned_resource_receipt(estimator_required=True).model_dump(mode="json")
    if mutation == "joblib_oversubscribed":
        receipt_payload["joblib_entry_effective_jobs"] = 2
        receipt_payload["joblib_exit_effective_jobs"] = 2
    else:
        receipt_payload["estimator_before_n_jobs"] = None
    receipt = _R5ResourceReceiptFixture.model_validate(receipt_payload, strict=True)

    assert _resource_evidence_payload(anchor=anchor, receipt=receipt) is None


def test_r5_resource_evidence_projection_preserves_consumer_schema() -> None:
    anchor = _r5_resource_anchor(
        method_fqn="causal.hte.double_ml@2.0.0",
        profile_id="econml.dml.point_only@2.0",
        required_estimator_n_jobs=None,
    )
    receipt = _r5_returned_resource_receipt(estimator_required=False)
    payload = _resource_evidence_payload(anchor=anchor, receipt=receipt)

    assert payload is not None
    ir_evidence = HTEResourceExecutionEvidenceV1.model_validate(payload, strict=True)
    core_evidence = DirectMethodExecutionHTEResourceEvidence.model_validate(payload, strict=True)
    ir_projection = _resource_evidence_payload_for_consumer(
        payload=payload,
        consumer=ir_evidence,
    )
    core_projection = _resource_evidence_payload_for_consumer(
        payload=payload,
        consumer=core_evidence,
    )

    assert ir_projection == ir_evidence.model_dump(mode="json")
    assert ir_projection is not None and ir_projection["schema_version"] == "1.0"
    assert core_projection == core_evidence.model_dump(mode="json")
    assert core_projection is not None and "schema_version" not in core_projection
    assert _resource_evidence_matches_receipt(
        evidence=ir_evidence,
        anchor=anchor,
        receipt=receipt,
    )
    assert _resource_evidence_matches_receipt(
        evidence=core_evidence,
        anchor=anchor,
        receipt=receipt,
    )


@pytest.mark.parametrize("mutation", ["extra_field", "tuple_value", "wrong_schema_version"])
def test_r5_resource_evidence_projection_refuses_malformed_expected_payload(
    mutation: str,
) -> None:
    anchor = _r5_resource_anchor(
        method_fqn="causal.hte.double_ml@2.0.0",
        profile_id="econml.dml.point_only@2.0",
        required_estimator_n_jobs=None,
    )
    receipt = _r5_returned_resource_receipt(estimator_required=False)
    payload = _resource_evidence_payload(anchor=anchor, receipt=receipt)

    assert payload is not None
    evidence = HTEResourceExecutionEvidenceV1.model_validate(payload, strict=True)
    malformed = dict(payload)
    if mutation == "extra_field":
        malformed["not_in_contract"] = True
    elif mutation == "tuple_value":
        malformed["joblib_entry_backend_fqn"] = ("not", "json")
    else:
        malformed["schema_version"] = "2.0"

    assert (
        _resource_evidence_payload_for_consumer(
            payload=malformed,
            consumer=evidence,
        )
        is None
    )


def test_r5_resource_evidence_join_refuses_fake_evidence_and_receipt_profile() -> None:
    anchor = _r5_resource_anchor(
        method_fqn="causal.hte.double_ml@2.0.0",
        profile_id="econml.dml.point_only@2.0",
        required_estimator_n_jobs=None,
    )
    receipt = _r5_returned_resource_receipt(estimator_required=False)
    payload = _resource_evidence_payload(anchor=anchor, receipt=receipt)

    assert payload is not None
    evidence = HTEResourceExecutionEvidenceV1.model_validate(payload, strict=True)
    fake_payload = dict(payload)
    fake_payload["owner_policy_digest"] = "b" * 64
    fake_evidence = HTEResourceExecutionEvidenceV1.model_validate(fake_payload, strict=True)
    assert not _resource_evidence_matches_receipt(
        evidence=fake_evidence,
        anchor=anchor,
        receipt=receipt,
    )

    wrong_profile_payload = receipt.model_dump(mode="json")
    wrong_profile_payload["joblib_profile_id"] = "joblib.parallel_config.other@1.0"
    wrong_profile_receipt = _R5ResourceReceiptFixture.model_validate(
        wrong_profile_payload,
        strict=True,
    )
    assert not _resource_evidence_matches_receipt(
        evidence=evidence,
        anchor=anchor,
        receipt=wrong_profile_receipt,
    )


def test_search_binding_full_association_requires_typed_historical_recompute() -> None:
    binding_ref = ArtifactRef(
        artifact_id="sha256:" + "c" * 64,
        kind="scientist.search.uncertainty_task_binding",
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "f" * 64,
    )
    association = type("Association", (), {"search_uncertainty_task_binding_ref": binding_ref})()
    service = type(
        "Owner",
        (),
        {
            "resolve_historical_search_uncertainty_task_binding": staticmethod(
                lambda *, binding_ref, owner_association: _SearchBindingResolutionFixture(
                    binding_ref=binding_ref,
                    binding=_SearchBindingFixture(),
                    closure_status="recomputed",
                    resolution_status="historical",
                )
            )
        },
    )()

    _resolve_historical_search_binding(service=service, association=association)


@pytest.mark.parametrize(
    "resolution",
    [
        object(),
        _SearchBindingResolutionFixture(
            binding_ref=ArtifactRef(
                artifact_id="sha256:" + "d" * 64,
                kind="scientist.search.uncertainty_task_binding",
                media_type="application/json",
                manifest_profile_sha256="sha256:" + "f" * 64,
            ),
            binding=_SearchBindingFixture(),
            closure_status="recomputed",
            resolution_status="historical",
        ),
        _SearchBindingResolutionFixture(
            binding_ref=ArtifactRef(
                artifact_id="sha256:" + "c" * 64,
                kind="scientist.search.uncertainty_task_binding",
                media_type="application/json",
                manifest_profile_sha256="sha256:" + "f" * 64,
            ),
            binding=_SearchBindingFixture(),
            closure_status="not_established",
            resolution_status="historical",
        ),
        _SearchBindingResolutionFixture(
            binding_ref=ArtifactRef(
                artifact_id="sha256:" + "c" * 64,
                kind="scientist.search.uncertainty_task_binding",
                media_type="application/json",
                manifest_profile_sha256="sha256:" + "f" * 64,
            ),
            binding=_SearchBindingFixture(),
            closure_status="recomputed",
            resolution_status="current",
        ),
        _SearchBindingResolutionFixture.model_construct(
            schema_version="2.0",
            resolution_status="historical",
            binding_ref=ArtifactRef(
                artifact_id="sha256:" + "c" * 64,
                kind="scientist.search.uncertainty_task_binding",
                media_type="application/json",
                manifest_profile_sha256="sha256:" + "f" * 64,
            ),
            binding=_SearchBindingFixture(),
            closure_status="recomputed",
        ),
    ],
)
def test_search_binding_full_association_rejects_untyped_or_mismatched_resolution(
    resolution: object,
) -> None:
    binding_ref = ArtifactRef(
        artifact_id="sha256:" + "c" * 64,
        kind="scientist.search.uncertainty_task_binding",
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "f" * 64,
    )
    association = type("Association", (), {"search_uncertainty_task_binding_ref": binding_ref})()
    service = type(
        "Owner",
        (),
        {
            "resolve_historical_search_uncertainty_task_binding": staticmethod(
                lambda *, binding_ref, owner_association: resolution
            )
        },
    )()

    with pytest.raises(ValueError, match="owned_attempt_historical_search_binding"):
        _resolve_historical_search_binding(service=service, association=association)


def test_search_binding_full_association_fails_closed_without_owner_callback() -> None:
    binding_ref = ArtifactRef(
        artifact_id="sha256:" + "c" * 64,
        kind="scientist.search.uncertainty_task_binding",
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "f" * 64,
    )
    association = type("Association", (), {"search_uncertainty_task_binding_ref": binding_ref})()

    with pytest.raises(ValueError, match="owned_attempt_historical_search_resolver_unavailable"):
        _resolve_historical_search_binding(service=object(), association=association)


def test_search_binding_refusal_does_not_require_a_score_association() -> None:
    association = type("RefusalAssociation", (), {"search_uncertainty_task_binding_ref": None})()
    _resolve_historical_search_binding(service=object(), association=association)


@pytest.mark.usefixtures("_runtime_api_owner_tenant_scope")
def test_search_binding_anchor_read_normalizes_typed_ref_before_context_refusal(
    runtime_api_env: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reach the real anchor reader, then refuse an unbound Search association.

    The typed resolver stub only advances this negative path to the selected
    anchor read; the real persisted anchor must still fail its binding check.
    """
    service, _accepted, _terminal_event, anchor_ref = _dispatch_refused_request(runtime_api_env)
    from datetime import datetime

    parsed_anchor = _read_profiled_model(
        service=service,
        selected_ref=anchor_ref,
        limits=service._observational_read_limits(),
        model=OwnedAttemptAnchor,
        expected_kind=OwnedAttemptAnchor.ARTIFACT_KIND,
        expected_schema_name=OwnedAttemptAnchor.ARTIFACT_SCHEMA_NAME,
        expected_schema_version=OwnedAttemptAnchor.ARTIFACT_SCHEMA_VERSION,
    )
    assert parsed_anchor.job_id == _accepted["job_id"]
    assert parsed_anchor.run_id == _accepted["run_id"]
    assert type(parsed_anchor.captured_at) is datetime
    assert type(parsed_anchor.lease_expires_at) is datetime
    assert type(parsed_anchor.job_created_event.created_at) is datetime
    assert type(parsed_anchor.job_running_event.created_at) is datetime

    import polisyos.scientist.methods.search.uncertainty as search_uncertainty_module
    from polisyos.core.contracts.owned_attempt_anchor import OwnedAttemptAnchorAssociation
    from polisyos.scientist.methods.search.uncertainty import (
        SearchUncertaintyTaskBinding,
        SearchUncertaintyTaskBindingResolution,
    )

    binding_ref = ArtifactRef(
        artifact_id="sha256:" + "c" * 64,
        kind="scientist.search.uncertainty_task_binding",
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "f" * 64,
    )
    selected_binding_ref = SelectedArtifactRef.model_validate(
        binding_ref.model_dump(mode="python"),
        strict=True,
    )
    binding = SearchUncertaintyTaskBinding.model_construct()
    resolution = SearchUncertaintyTaskBindingResolution.model_construct(
        schema_version="1.0",
        resolution_status="historical",
        closure_status="recomputed",
        binding_ref=selected_binding_ref,
        binding=binding,
        binding_content_sha256=binding_ref.artifact_id.hex,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
    )
    # This controlled resolver only reaches the persisted-anchor read; it
    # cannot produce a successful association for this unbound refusal anchor.
    owner_association = OwnedAttemptAnchorAssociation.model_construct(
        anchor_ref=anchor_ref,
        search_uncertainty_task_binding_ref=selected_binding_ref,
    )
    monkeypatch.setattr(
        search_uncertainty_module,
        "resolve_historical_search_uncertainty_task_binding",
        lambda **_kwargs: resolution,
    )
    monkeypatch.setattr(service, "_require_search_uncertainty_store", lambda: object())

    with pytest.raises(
        ValueError,
        match="runtime_historical_search_anchor_binding_mismatch",
    ):
        service.resolve_historical_search_uncertainty_task_binding(
            binding_ref=selected_binding_ref,
            owner_association=owner_association,
        )


def test_anchor_intake_refuses_a_valid_legacy_pair_with_a_typed_version_reason() -> None:
    """Generic v1 intent compatibility must not authorize a v2-only anchor."""
    legacy = _IntentVersionFixture(
        schema_version="polisyos.runtime.observational_run_intent.v1",
        method_fqn="causal.hte.forest_dr@1.1.0",
        method_version="1.1.0",
        owned_hte_request_context=None,
    )
    legacy_admitted = _IntentVersionFixture(
        schema_version="polisyos.runtime.content_admitted_observational_run_intent.v1",
        method_fqn="causal.hte.forest_dr@1.1.0",
        owned_hte_request_context=None,
    )

    # The generic reader still understands the immutable compatibility pair.
    _require_intent_request_context_pair(legacy, legacy_admitted)
    with pytest.raises(
        OwnedAttemptAnchorVersionRefusalError,
        match="owned_attempt_successor_intent_required",
    ):
        _require_successor_anchor_intent_pair(legacy, legacy_admitted)

    successor = _IntentVersionFixture(
        schema_version="polisyos.runtime.observational_run_intent.v2",
        method_fqn="causal.hte.forest_dr@2.0.0",
        method_version="2.0.0",
        owned_hte_request_context=_declared_request_context(),
    )
    successor_admitted = _IntentVersionFixture(
        schema_version="polisyos.runtime.content_admitted_observational_run_intent.v2",
        method_fqn="causal.hte.forest_dr@2.0.0",
        owned_hte_request_context=_declared_request_context(),
    )
    _require_successor_anchor_intent_pair(successor, successor_admitted)


def _put_hte_input(
    service: Any,
    *,
    wrong_target: bool,
    empty: bool,
    tenant_id: str,
    cell_id: str,
) -> ArtifactRef:
    """Persist one profile-qualified HTE source for a real worker refusal."""
    row_count = 0 if empty else 40
    source_payload = {
        "outcome": [float(index) / 10 + (index % 2) * 0.5 for index in range(row_count)],
        "treatment": [index % 2 for index in range(row_count)],
        "covariates": [[float(index), float(index % 5)] for index in range(row_count)],
        "confounders": [[float(index % 7)] for index in range(row_count)],
        "feature_names": ["age", "baseline"],
        "confounder_names": ["risk"],
        "sample_ids": [f"candidate-{index}" for index in range(row_count)],
        "metadata": {"source": "synthetic_candidate"},
    }
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        ref = service._artifact_store.put_json(
            {
                "schema_version": "policyos.ir.observation.method_input_envelope.v1",
                "contract_target": {
                    "contract_id": (
                        "foundry.causal.hte_observational_data.v0"
                        if wrong_target
                        else "foundry.causal.hte_observational_data.v1"
                    ),
                    "contract_fqn": (
                        "polisyos.foundry.methods.catalog.causal.protocols.HTEObservationalData"
                    ),
                },
                "contract_payload": source_payload,
            },
            PutOptions(
                kind="ir.observation_method_input",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.ir.ObservationMethodInputEnvelope",
                    version="1.0",
                ),
                inputs=[],
                governance=ArtifactGovernanceInfo(classification="public"),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
    return ArtifactRef.model_validate(ref, strict=True)


def _dispatch_refused_request(
    runtime_api_env: dict[str, Any],
    *,
    wrong_target: bool = True,
    empty: bool = False,
) -> tuple[Any, dict[str, Any], Any, OwnedAttemptAnchorRef]:
    """Run the real HTTP worker through input preparation and its failure event."""
    pytest.importorskip("econml")
    from _helpers.control_worker import dispatch_one_control_job, stop_embedded_control_worker

    service = runtime_api_env["app"].state._control_service
    stop_embedded_control_worker(service)
    source_ref = _put_hte_input(
        service,
        wrong_target=wrong_target,
        empty=empty,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
    )
    response = runtime_api_env["client"].post(
        "/api/v1/control/runs",
        json={
            "observational_input": {
                "protocol": "method_input_envelope_v1",
                "source_ref": source_ref.model_dump(mode="json"),
                "method": {"fqn": "causal.hte.forest_dr@2.0.0"},
                "hte_request": {
                    "schema_version": "polisyos.runtime.observational_hte_request.v2",
                    "estimand": "mean_effect_over_selected_x",
                    "target_scope": "selected_evaluation_rows",
                    "outcome_variable_id": "outcome.effect",
                    "treatment_variable_id": "treatment.policy",
                    "control_value": 0.0,
                    "treated_value": 1.0,
                    "alpha": 0.05,
                    "requested_guarantee": "candidate_point",
                },
            }
        },
    )
    assert response.status_code == 200, response.text
    accepted = response.json()
    job_id = accepted["job_id"]
    run_id = accepted["run_id"]

    dispatched = dispatch_one_control_job(
        store=service._control_store,
        handler=service._process_control_job,
        expected_job_id=job_id,
    )
    assert dispatched == job_id
    record = service._control_store.get_job(job_id)
    assert record is not None and record.state == "failed"
    assert record.method_execution_selection is None
    terminal_event = service._control_store.get_job_terminal_source_event_record(job_id)
    assert terminal_event.event_type == "job_failed"
    assert terminal_event.payload["owned_attempt_failure_disposition"] == "input_refused"
    anchor_ref = OwnedAttemptAnchorRef.model_validate(
        terminal_event.payload["owned_attempt_anchor_ref"], strict=True
    )
    assert anchor_ref.manifest_profile_sha256 is not None
    assert record.run_id == run_id
    return service, accepted, terminal_event, anchor_ref


def _read_anchor(service: Any, anchor_ref: OwnedAttemptAnchorRef) -> OwnedAttemptAnchor:
    """Read an anchor through the owner seam that normalizes exact Core refs."""
    return _read_owned_attempt_anchor(service=service, anchor_ref=anchor_ref)


@pytest.mark.usefixtures("_runtime_api_owner_tenant_scope")
def test_projection_manifest_reader_checks_selected_profile_without_reading_payload(
    runtime_api_env: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = runtime_api_env["app"].state._control_service
    source_ref = _put_hte_input(
        service,
        wrong_target=False,
        empty=False,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
    )

    def reject_payload_read(*_args: Any, **_kwargs: Any) -> bytes:
        raise AssertionError("bounded projection must not read artifact payload bytes")

    monkeypatch.setattr(service._artifact_store, "get_bytes", reject_payload_read)
    manifest = _read_projection_manifest(
        service=service,
        selected_ref=source_ref,
        expected_kind="ir.observation_method_input",
        expected_schema_name="polisyos.ir.ObservationMethodInputEnvelope",
        expected_schema_version="1.0",
    )

    assert manifest.artifact_id == source_ref.artifact_id
    assert manifest.kind == "ir.observation_method_input"

    forged_profile = source_ref.model_copy(update={"manifest_profile_sha256": "sha256:" + "0" * 64})
    with pytest.raises(ValueError, match="owned_attempt_projection_manifest_unavailable"):
        _read_projection_manifest(
            service=service,
            selected_ref=forged_profile,
            expected_kind="ir.observation_method_input",
            expected_schema_name="polisyos.ir.ObservationMethodInputEnvelope",
            expected_schema_version="1.0",
        )


def test_runtime_api_fixture_forwards_explicit_repo_root(
    runtime_api_env: dict[str, Any],
    tmp_path: Path,
    pytestconfig: pytest.Config,
) -> None:
    """Keep the runtime test helper's explicit source root on its materialized owners."""
    from _helpers import runtime_http

    expected_root = Path(pytestconfig.rootpath).resolve(strict=True)
    service = runtime_api_env["app"].state._control_service
    assert service._repo_root == expected_root
    catalog_path = (
        expected_root
        / "production_data/datasets_full_phase3full_20260327_183054/dataset_catalog.duckdb"
    )
    assert service._retrieval_catalog.database_path == catalog_path
    assert catalog_path.is_file()

    standalone = runtime_http._build_control_service(
        tmp_path / "standalone",
        repo_root=expected_root,
    )
    try:
        assert standalone._repo_root == expected_root
    finally:
        standalone.close()


@pytest.fixture
def _runtime_api_owner_tenant_scope(
    runtime_api_env: dict[str, Any],
) -> Iterator[None]:
    """Scope direct CAS and Runtime owner calls to the fixture's tenant and cell."""
    with tenant_scope(
        None,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
    ):
        yield


@pytest.mark.parametrize(
    "outcome_mutation",
    [
        None,
        "resource_policy_digest",
        "resource_policy_profile",
        "producer_limitation_missing",
        "producer_limitation_extra",
        "producer_limitation_duplicate",
    ],
    ids=[
        "selected_r5_positive",
        "forged_outcome_digest_refused",
        "forged_outcome_profile_refused",
        "producer_limitation_missing_refused",
        "producer_limitation_extra_refused",
        "producer_limitation_duplicate_refused",
    ],
)
@pytest.mark.usefixtures("_runtime_api_owner_tenant_scope")
def test_completed_attempt_projection_matches_full_association_without_output_payload_reads(
    runtime_api_env: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    pytestconfig: pytest.Config,
    outcome_mutation: Literal[
        "resource_policy_digest",
        "resource_policy_profile",
        "producer_limitation_missing",
        "producer_limitation_extra",
        "producer_limitation_duplicate",
    ]
    | None,
) -> None:
    """A completed owner summary is reconciled from refs/manifests, not output bytes."""
    pytest.importorskip("econml")
    from _helpers.control_worker import dispatch_one_control_job, stop_embedded_control_worker

    service = runtime_api_env["app"].state._control_service
    stop_embedded_control_worker(service)

    from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
    from polisyos.foundry.methods.selection.history import SelectionHistoryStore
    from polisyos.runtime.http.services.control import run_lifecycle as run_lifecycle_module
    from polisyos.scientist.compute.runner import MethodExecutionRefOutcome

    history_path = tmp_path / "selection-history" / "executions.jsonl"
    selection_history = SelectionHistoryStore(persist_path=history_path, auto_persist=True)
    monkeypatch.setattr(
        MethodDispatcher,
        "_instance",
        MethodDispatcher(runtime_history=selection_history),
    )
    original_require_shared_execution_value = run_lifecycle_module.require_shared_execution_value
    captured_producer_outputs: list[tuple[Any, Any, Any]] = []

    def rebuild_outcome(
        outcome: MethodExecutionRefOutcome,
        *,
        resource_policy_ref: ArtifactRef | None = None,
        resource_policy_digest: str | None = None,
        limitations: tuple[str, ...] | None = None,
    ) -> MethodExecutionRefOutcome:
        return MethodExecutionRefOutcome(
            job_id=outcome.job_id,
            run_id=outcome.run_id,
            attempt=outcome.attempt,
            requested_source_ref=outcome.requested_source_ref,
            observational_run_intent_ref=outcome.observational_run_intent_ref,
            content_admitted_intent_ref=outcome.content_admitted_intent_ref,
            submitted_input_ref=outcome.submitted_input_ref,
            effective_input_ref=outcome.effective_input_ref,
            method_result_ref=outcome.method_result_ref,
            method_evidence_ref=outcome.method_evidence_ref,
            resource_policy_ref=(
                outcome.resource_policy_ref if resource_policy_ref is None else resource_policy_ref
            ),
            method_fqn=outcome.method_fqn,
            method_version=outcome.method_version,
            method_abi_digest=outcome.method_abi_digest,
            method_build_digest=outcome.method_build_digest,
            method_build_digest_scope=outcome.method_build_digest_scope,
            resource_policy_digest=(
                outcome.resource_policy_digest
                if resource_policy_digest is None
                else resource_policy_digest
            ),
            source_protocol=outcome.source_protocol,
            normalization=outcome.normalization,
            limitations=outcome.limitations if limitations is None else limitations,
            method_dispatch_binding_status=outcome.method_dispatch_binding_status,
            candidate_outcome=outcome.candidate_outcome,
            posterior_summary_refs=outcome.posterior_summary_refs,
            owned_attempt_anchor_ref=outcome.owned_attempt_anchor_ref,
            hte_outcome_ref=outcome.hte_outcome_ref,
            point_result_ref=outcome.point_result_ref,
            hte_result_ref=outcome.hte_result_ref,
            inference_basis_ref=outcome.inference_basis_ref,
            refusal_diagnostic_ref=outcome.refusal_diagnostic_ref,
            invocation_basis_ref=outcome.invocation_basis_ref,
            hte_summary=outcome.hte_summary,
        )

    def capture_real_producer_outcome(*args: Any, **kwargs: Any) -> Any:
        outcome = original_require_shared_execution_value(*args, **kwargs)
        if type(outcome) is not MethodExecutionRefOutcome:
            return outcome
        from polisyos.core.contracts.runtime import (
            ContentAdmittedObservationalRunIntent,
            ObservationalRunIntent,
            _expected_content_admitted_limitations,
        )

        admitted_payload = service._read_bounded_intent_artifact(
            outcome.content_admitted_intent_ref
        )
        requested_payload = service._read_bounded_intent_artifact(
            outcome.observational_run_intent_ref
        )
        admitted = ContentAdmittedObservationalRunIntent.model_validate_json(
            json.dumps(admitted_payload, ensure_ascii=False, allow_nan=False),
            strict=True,
        )
        requested = ObservationalRunIntent.model_validate_json(
            json.dumps(requested_payload, ensure_ascii=False, allow_nan=False),
            strict=True,
        )
        captured_producer_outputs.append((outcome, requested, admitted))
        if outcome_mutation == "resource_policy_digest":
            return rebuild_outcome(outcome, resource_policy_digest="0" * 64)
        if outcome_mutation == "resource_policy_profile":
            forged_ref = outcome.resource_policy_ref.model_copy(
                update={"manifest_profile_sha256": "sha256:" + "0" * 64}
            )
            return rebuild_outcome(outcome, resource_policy_ref=forged_ref)
        producer_limitations = _expected_content_admitted_limitations(
            outcome.source_protocol,
            source_access_revalidation_status=None,
        )
        if outcome_mutation == "producer_limitation_missing":
            assert len(producer_limitations) > 1
            return rebuild_outcome(
                outcome,
                limitations=producer_limitations[:-1],
            )
        if outcome_mutation == "producer_limitation_extra":
            return rebuild_outcome(
                outcome,
                limitations=(
                    *producer_limitations,
                    "source_access_revalidation_not_established",
                ),
            )
        if outcome_mutation == "producer_limitation_duplicate":
            return rebuild_outcome(
                outcome,
                limitations=(*producer_limitations, producer_limitations[0]),
            )
        return outcome

    monkeypatch.setattr(
        run_lifecycle_module,
        "require_shared_execution_value",
        capture_real_producer_outcome,
    )
    source_ref = _put_hte_input(
        service,
        wrong_target=False,
        empty=False,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
    )
    unknown_protocol_response = runtime_api_env["client"].post(
        "/api/v1/control/runs",
        json={
            "observational_input": {
                "protocol": "candidate_unknown_v1",
                "source_ref": source_ref.model_dump(mode="json"),
                "method": {"fqn": "causal.hte.double_ml@2.0.0"},
                "hte_request": {
                    "schema_version": "polisyos.runtime.observational_hte_request.v2",
                    "estimand": "mean_effect_over_selected_x",
                    "target_scope": "selected_evaluation_rows",
                    "outcome_variable_id": "outcome.effect",
                    "treatment_variable_id": "treatment.policy",
                    "control_value": 0.0,
                    "treated_value": 1.0,
                    "alpha": 0.05,
                    "requested_guarantee": "candidate_point",
                },
            }
        },
    )
    assert unknown_protocol_response.status_code == 422, unknown_protocol_response.text
    assert "protocol" in unknown_protocol_response.text

    response = runtime_api_env["client"].post(
        "/api/v1/control/runs",
        json={
            "observational_input": {
                "protocol": "method_input_envelope_v1",
                "source_ref": source_ref.model_dump(mode="json"),
                "method": {"fqn": "causal.hte.double_ml@2.0.0"},
                "hte_request": {
                    "schema_version": "polisyos.runtime.observational_hte_request.v2",
                    "estimand": "mean_effect_over_selected_x",
                    "target_scope": "selected_evaluation_rows",
                    "outcome_variable_id": "outcome.effect",
                    "treatment_variable_id": "treatment.policy",
                    "control_value": 0.0,
                    "treated_value": 1.0,
                    "alpha": 0.05,
                    "requested_guarantee": "candidate_point",
                },
            }
        },
    )
    assert response.status_code == 200, response.text
    accepted = response.json()
    job_id = accepted["job_id"]
    run_id = accepted["run_id"]

    from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
    from polisyos.core.artifacts.manifest import SchemaInfo
    from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
    from polisyos.core.canon import from_canonical_bytes
    from polisyos.core.contracts.decision_validity import (
        DecisionTriggerType,
        DecisionValidityStatus,
    )
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.core.run.context import RunContext
    from polisyos.ir.governance.policy_spec import PolicySpec
    from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
    from polisyos.ir.model_layer.model_spec import ModelSpec
    from polisyos.ir.trinity import TrinityBundle
    from polisyos.ir.trinity.loaders import (
        TrinityLoadError,
        load_trinity_bundle_artifact,
        persist_trinity_bundle_artifact,
    )
    from polisyos.scientist.nodes.builtins.decide.decision_packet.builder import (
        BuildDecisionPacketNode,
    )
    from polisyos.scientist.nodes.builtins.state_keys import (
        INPUT_DATA_SNAPSHOT_REF,
        INPUT_REGISTRY_BUNDLE_REF,
        INPUT_TRINITY_BUNDLE_REF,
    )
    from polisyos.scientist.orchestration.engine.context import ExecutionContext
    from polisyos.scientist.orchestration.engine.state import ExperimentState

    store = service._artifact_store
    with tenant_scope(
        None,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
    ):
        registry_bundle_ref = build_default_registry_bundle(
            store,
            return_selected_profile=True,
        ).bundle_ref
        assert registry_bundle_ref.manifest_profile_sha256 is not None
        state_snapshot_ref = store.put_json(
            {"state": {}},
            PutOptions(kind="foundry.state_snapshot", media_type="application/json"),
        )
        data_snapshot_ref = store.put_json(
            {
                "data_ref": {
                    "artifact_id": str(state_snapshot_ref.artifact_id),
                    "kind": "foundry.state_snapshot",
                    "media_type": "application/json",
                }
            },
            PutOptions(kind="fabric.data_snapshot", media_type="application/json"),
        )
        trinity_bundle = TrinityBundle(
            problem_frame=ProblemFrame(
                problem_id="problem_followup",
                domain=ProblemDomain.FISCAL,
            ),
            policy_spec=PolicySpec(policy_id="policy_followup"),
            model_spec=ModelSpec(
                model_id="model_followup",
                data_snapshot_ref=str(data_snapshot_ref.artifact_id),
                registry_bundle_ref=str(registry_bundle_ref.artifact_id),
            ),
        )
        selected_trinity_ref = persist_trinity_bundle_artifact(
            _ensure_ir_artifact_store(store),
            trinity_bundle,
        )
        assert selected_trinity_ref.manifest_profile_sha256 is not None
        trinity_ref = ArtifactRef.model_validate(
            selected_trinity_ref.model_dump(mode="json"),
            strict=True,
        )

    if outcome_mutation is None:
        unadmitted_cas_root = tmp_path / "unadmitted-trinity-cas"
        unadmitted_store = FileSystemCAS(unadmitted_cas_root)
        raw_profile_ref = unadmitted_store.put_json(
            trinity_bundle,
            PutOptions(
                kind="ir.trinity_bundle",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.ir.TrinityBundle",
                    version=trinity_bundle.schema_version,
                ),
            ),
            return_selected_profile=True,
        )
        assert raw_profile_ref.manifest_profile_sha256 is not None
        fresh_unadmitted_store = FileSystemCAS(unadmitted_cas_root)
        with pytest.raises(TrinityLoadError, match="profile"):
            load_trinity_bundle_artifact(
                _ensure_ir_artifact_store(fresh_unadmitted_store),
                raw_profile_ref,
            )

    def build_followup_packet(
        packet_run_id: str,
        *,
        requested_source_run_id: str | None = None,
        trinity_bundle_ref: ArtifactRef | None = None,
    ) -> tuple[ArtifactRef, dict[str, Any]]:
        source_selector = requested_source_run_id or run_id
        with tenant_scope(
            None,
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=runtime_api_env["cell_a"],
        ):
            run_context = RunContext.start(
                store=store,
                registry_bundle=registry_bundle_ref,
                run_id=packet_run_id,
                run_dir=(
                    runtime_api_env["app"].state.runtime_api_ctx.core_runs_root / packet_run_id
                ),
                tenant_id=runtime_api_env["tenant_a"],
                cell_id=runtime_api_env["cell_a"],
            )
        execution = ExecutionContext(
            store=store,
            run=run_context,
            logger=logging.getLogger("test.completed_hte_packet"),
            completed_method_hte_selection_owner=service,
        )
        packet_state = ExperimentState(
            run_id=packet_run_id,
            inputs={
                INPUT_TRINITY_BUNDLE_REF: trinity_bundle_ref or trinity_ref,
                INPUT_REGISTRY_BUNDLE_REF: registry_bundle_ref,
                INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
            },
            params={"random_seed": 41, "completed_hte_source_run_id": source_selector},
        )
        with tenant_scope(
            None,
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=runtime_api_env["cell_a"],
        ):
            outcome = BuildDecisionPacketNode().execute(execution, packet_state)
            assert outcome.status == "ok", outcome.error
            packet = outcome.artifacts[0]
            run_context.add_output(packet)
            run_context.finalize(status="completed")
            runtime_api_env["app"].state.runtime_api_ctx.run_index.refresh(force=True)
            payload = from_canonical_bytes(store.get_bytes(packet))
        assert isinstance(payload, dict)
        return packet, payload

    packet_ref, initial_packet_payload = build_followup_packet("dp-followup-before")
    from polisyos.core.artifacts.ownership import ArtifactOwnershipError
    from polisyos.core.security.tenant_context import clear_tenant_context

    # Retain the ownership boundary as an explicit negative while the rest of
    # the test runs inside its fixture-provided tenant and cell scope.
    with (
        clear_tenant_context(),
        pytest.raises(
            ArtifactOwnershipError,
            match="active owner is required for read",
        ),
    ):
        store.get_bytes(packet_ref)
    initial_packet_bytes = store.get_bytes(packet_ref)
    initial_hte = initial_packet_payload["decision_validity_envelope"]["data_basis"]["summary"]
    assert initial_packet_payload["hte"] is None
    assert initial_hte["completed_hte_source_status"] == "verification_missing"
    assert initial_hte["completed_hte_requested_source_run_id"] == run_id
    assert initial_hte["completed_hte_publication_authorization"] == "not_established"
    dependency_key = f"hte_completed_source_run:{run_id}"

    def assert_unresolved_source_warning(evaluation: Any) -> None:
        """Keep an immutable preselection packet limited while its source is unresolved."""
        assert evaluation.status == DecisionValidityStatus.WARNING
        assert evaluation.reasons == ["completed_hte_source_not_established"]
        assert len(evaluation.triggers) == 1
        trigger = evaluation.triggers[0]
        assert trigger.trigger_type == DecisionTriggerType.METRIC_INVALIDATION
        assert trigger.status == DecisionValidityStatus.WARNING
        assert trigger.reason == "completed_hte_source_not_established"
        assert trigger.dependency_key is None
        assert trigger.details == {
            "request_status": "requested",
            "selection_status": "verification_missing",
            "requested_source_run_id": run_id,
            "source_run_id": run_id,
            "source_job_id": None,
            "source_attempt": None,
            "authority_purpose": "candidate_method_evidence",
            "publication_authorization": "not_established",
        }

    initial_evaluation, _ = service._decision_validity_service.get_evaluation(
        _decision_validity_packet_key(packet_ref),
        force=True,
    )
    assert_unresolved_source_warning(initial_evaluation)
    assert not any(
        trigger.dependency_key == dependency_key for trigger in initial_evaluation.triggers
    )

    monkeypatch.setattr(
        service,
        "_dispatch_completed_hte_source_validity_for_job",
        lambda **_kwargs: None,
    )
    assert (
        dispatch_one_control_job(
            store=service._control_store,
            handler=service._process_control_job,
            expected_job_id=job_id,
        )
        == job_id
    )
    record = service._control_store.get_latest_job_by_run(run_id)
    assert record is not None and record.job_id == job_id
    assert len(captured_producer_outputs) == 1
    producer_outcome, requested_intent, admitted_intent = captured_producer_outputs[0]
    assert producer_outcome.method_fqn == "causal.hte.double_ml@2.0.0"
    from polisyos.core.contracts.runtime import _expected_content_admitted_limitations

    expected_producer_limitations = _expected_content_admitted_limitations(
        producer_outcome.source_protocol,
        source_access_revalidation_status=None,
    )
    expected_admitted_limitations = _expected_content_admitted_limitations(
        producer_outcome.source_protocol,
        source_access_revalidation_status="not_established",
    )
    assert producer_outcome.limitations == expected_producer_limitations
    assert admitted_intent.limitations == expected_admitted_limitations
    assert requested_intent.resource_policy.revision == "r5"
    expected_resource_policy_digest = requested_intent.resource_policy.digest()
    assert producer_outcome.resource_policy_ref == requested_intent.resource_policy_ref
    assert producer_outcome.resource_policy_ref == admitted_intent.resource_policy_ref
    assert producer_outcome.resource_policy_ref.manifest_profile_sha256 is not None
    assert producer_outcome.resource_policy_digest == expected_resource_policy_digest
    assert requested_intent.resource_policy_digest == expected_resource_policy_digest
    assert admitted_intent.resource_policy_digest == expected_resource_policy_digest
    assert history_path.is_file()
    persisted_history = [
        json.loads(line) for line in history_path.read_text(encoding="utf-8").splitlines() if line
    ]
    assert persisted_history
    assert len(persisted_history) == len(selection_history.all_records())
    assert any(item["success"] is True for item in persisted_history)
    assert not selection_history.persistence_issues()
    if outcome_mutation is not None:
        assert record.state == "failed"
        assert record.method_execution_selection is None
        assert record.error_message == "observational_method_execution_outcome_binding_mismatch"
        terminal_event = service._control_store.get_job_terminal_source_event_record(job_id)
        assert terminal_event.event_type == "job_failed"
        return
    assert record.state == "completed"
    selection_payload = record.method_execution_selection
    assert isinstance(selection_payload, dict)
    anchor_ref = OwnedAttemptAnchorRef.model_validate(
        selection_payload["owned_attempt_anchor_ref"], strict=True
    )
    anchor = _read_anchor(service, anchor_ref)
    assert type(anchor.requested_source_ref) is SelectedArtifactRef
    assert type(anchor.submitted_input_ref) is SelectedArtifactRef
    assert type(anchor.effective_input_ref) is SelectedArtifactRef
    assert type(anchor.observational_run_intent_ref) is SelectedArtifactRef
    assert type(anchor.content_admitted_intent_ref) is SelectedArtifactRef
    assert type(anchor.resource_policy_ref) is SelectedArtifactRef
    assert anchor.input_capture.source_feature_names == ("age", "baseline")
    assert (anchor.input_capture.n_treated, anchor.input_capture.n_control) == (20, 20)
    assert (
        anchor.input_capture.n_treated + anchor.input_capture.n_control
        == anchor.input_capture.n_selected_rows
    )

    # The full assessment resolver verifies the actual writer-ready and point
    # payloads once. The protected projection below must not read them again.
    full_association = resolve_owned_attempt_anchor_association(
        service=service,
        anchor_ref=anchor_ref,
    )
    assert full_association.outcome_kind == "point_estimate"
    assert full_association.point_result_ref is not None

    from pydantic import ValidationError

    from polisyos.core.contracts.runtime import (
        DirectMethodExecutionSelection,
        _validate_method_execution_selection_wire_payload,
    )

    selected = _validate_method_execution_selection_wire_payload(selection_payload)
    assert selected.model_dump(mode="json") == selection_payload
    malformed_extra = {**selection_payload, "unexpected_wire_field": True}
    with pytest.raises(ValidationError):
        _validate_method_execution_selection_wire_payload(malformed_extra)
    malformed_tuple_field = {**selection_payload, "limitations": "not-a-list"}
    with pytest.raises(ValidationError):
        _validate_method_execution_selection_wire_payload(malformed_tuple_field)
    python_tuple_input = {
        **selection_payload,
        "limitations": tuple(selection_payload["limitations"]),
    }
    with pytest.raises(ValueError, match="method_execution_selection_wire_payload_invalid"):
        _validate_method_execution_selection_wire_payload(python_tuple_input)
    assert type(selected) is DirectMethodExecutionSelection
    assert selected.hte is not None
    assert selected.limitations == expected_admitted_limitations
    assert "source_access_revalidation_not_established" in selected.limitations
    fresh_run_details = runtime_api_env["client"].get(f"/api/v1/runs/{run_id}")
    assert fresh_run_details.status_code == 200, fresh_run_details.text
    served_projection = fresh_run_details.json()["run"]["method_execution_selection"]
    assert served_projection["status"] == "selected"
    assert served_projection["selection"]["limitations"] == list(expected_admitted_limitations)
    expected_digest = hashlib.sha256(
        json.dumps(
            selected.hte.model_dump(mode="json"),
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    forbidden_payload_ids = {
        _cas_selector_id(ref)
        for ref in (
            selected.method_result_ref,
            selected.method_evidence_ref,
            selected.hte.hte_outcome_ref,
            selected.hte.point_result_ref,
            selected.hte.hte_result_ref,
            selected.hte.inference_basis_ref,
            selected.hte.refusal_diagnostic_ref,
            selected.hte.source_data_ref,
        )
        if ref is not None
    }
    original_get_bytes = service._artifact_store.get_bytes
    reject_output_payload = _reject_output_payload_reader(
        original_get_bytes,
        forbidden_payload_ids,
    )

    original_public_selection_getter = service.get_method_execution_selection

    def reject_public_selection_getter(**_kwargs: object) -> object:
        raise AssertionError("bounded projection must reconcile the owner row directly")

    monkeypatch.setattr(service._artifact_store, "get_bytes", reject_output_payload)
    monkeypatch.setattr(
        service,
        "get_method_execution_selection",
        reject_public_selection_getter,
    )
    projection = resolve_owned_attempt_anchor_projection_association(
        service=service,
        run_id=run_id,
        expected_job_id=job_id,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
    )

    assert projection.status == "owner_projection_reconciled"
    assert projection.content_validation_status == "worker_admitted_not_recomputed"
    assert projection.manifest_identity_status == "independently_reconciled"
    assert projection.selected_summary_sha256 == expected_digest
    assert projection.job_id == job_id and projection.run_id == run_id
    assert projection.attempt == record.attempt
    assert projection.point_result_ref == full_association.point_result_ref
    assert projection.outcome_ref == full_association.outcome_ref
    assert type(service) is run_lifecycle_module.ControlPlaneService
    completed_source = service.resolve_completed_method_hte_selection(
        source_run_id=run_id,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
    )
    assert completed_source is not None
    assert completed_source.source_job_id == job_id
    assert completed_source.source_attempt == record.attempt
    assert completed_source.completed_event_id == projection.job_completed_event.event_id
    assert completed_source.completed_event_payload_sha256 == (
        projection.job_completed_event.payload_sha256
    )
    from polisyos.core.contracts import (
        CompletedMethodHTESource as FacadeCompletedMethodHTESource,
    )
    from polisyos.core.contracts.runtime import (
        CompletedMethodHTESource as CoreCompletedMethodHTESource,
    )
    from polisyos.core.contracts.runtime import (
        DirectMethodExecutionHTESummary,
        _validate_strict_json_wire_payload,
    )
    from polisyos.runtime.http.services.control.run_lifecycle import (
        CompletedMethodHTESource as RuntimeCompletedMethodHTESource,
    )

    assert RuntimeCompletedMethodHTESource is CoreCompletedMethodHTESource
    assert FacadeCompletedMethodHTESource is CoreCompletedMethodHTESource
    assert type(completed_source) is CoreCompletedMethodHTESource
    assert (
        get_type_hints(CoreCompletedMethodHTESource)["summary"] is DirectMethodExecutionHTESummary
    )
    assert completed_source.summary == selected.hte
    assert completed_source.association.selected_summary_sha256 == expected_digest
    assert completed_source.association.job_completed_event == projection.job_completed_event

    # This route witness runs before the independent outbox-failure scenario. Its
    # distinct packet lineage keeps that scenario's original packet assertions isolated.
    def candidate_packet_response(owner_run_id: str, selected_ref: ArtifactRef):
        path = (
            f"/api/v1/runs/{owner_run_id}/decision-packets/"
            f"{selected_ref.artifact_id!s}/candidate-hte"
        )
        return runtime_api_env["client"].get(
            path,
            params={"manifest_profile_sha256": selected_ref.manifest_profile_sha256},
        )

    # Exercise selected packet routing with the completed owner's canonical
    # stable run alias as both the packet owner and candidate source identity.
    packet_owner_run_id = completed_source.source_run_id
    packet_owner_run_dir = (
        runtime_api_env["app"].state.runtime_api_ctx.core_runs_root / packet_owner_run_id
    )
    assert not packet_owner_run_dir.exists(), (
        "the stable completed-owner alias already has a Core packet-owner trace"
    )
    candidate_route_trinity = TrinityBundle(
        problem_frame=ProblemFrame(
            problem_id="problem_candidate_route",
            domain=ProblemDomain.FISCAL,
        ),
        policy_spec=PolicySpec(policy_id="policy_candidate_route"),
        model_spec=ModelSpec(
            model_id="model_candidate_route",
            data_snapshot_ref=str(data_snapshot_ref.artifact_id),
            registry_bundle_ref=str(registry_bundle_ref.artifact_id),
        ),
    )
    with tenant_scope(
        None,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
    ):
        selected_candidate_route_ref = persist_trinity_bundle_artifact(
            _ensure_ir_artifact_store(store),
            candidate_route_trinity,
        )
        assert selected_candidate_route_ref.manifest_profile_sha256 is not None
        candidate_route_trinity_ref = ArtifactRef.model_validate(
            selected_candidate_route_ref.model_dump(mode="json"),
            strict=True,
        )
    selected_owner_ref, selected_owner_payload = build_followup_packet(
        packet_owner_run_id,
        requested_source_run_id=packet_owner_run_id,
        trinity_bundle_ref=candidate_route_trinity_ref,
    )
    selected_owner_basis = selected_owner_payload["decision_validity_envelope"]["data_basis"][
        "summary"
    ]
    assert selected_owner_payload["hte"] == selected.hte.model_dump(mode="json")
    assert selected_owner_basis["completed_hte_source_status"] == "selected"
    assert selected_owner_basis["completed_hte_source_run_id"] == packet_owner_run_id
    assert selected_owner_basis["completed_hte_requested_source_run_id"] == packet_owner_run_id
    assert selected_owner_basis["completed_hte_publication_authorization"] == "not_established"
    assert selected_owner_basis["completed_hte_authority_purpose"] == "candidate_method_evidence"

    selected_candidate = candidate_packet_response(packet_owner_run_id, selected_owner_ref)
    assert selected_candidate.status_code == 200, selected_candidate.text
    selected_projection = selected_candidate.json()
    assert selected_projection["candidate_only"] is True
    assert selected_projection["packet_run_id"] == packet_owner_run_id
    from polisyos.core.artifacts import artifact_ref_identity_key

    response_packet_ref = ArtifactRef.model_validate_json(
        json.dumps(
            selected_projection["decision_packet_ref"],
            ensure_ascii=False,
            allow_nan=False,
        ),
        strict=True,
    )
    assert artifact_ref_identity_key(response_packet_ref) == artifact_ref_identity_key(
        selected_owner_ref
    )
    assert response_packet_ref.artifact_id == selected_owner_ref.artifact_id
    assert response_packet_ref.manifest_profile_sha256 == selected_owner_ref.manifest_profile_sha256
    assert selected_projection["candidate_status"] == "selected"
    assert selected_projection["publication_authorization"] == "not_established"
    assert selected_projection["live_source_currentness"] == "not_established"

    selected_source_wire = selected_projection["source"]
    assert selected_source_wire["source_run_id"] == packet_owner_run_id
    assert selected_source_wire["source_job_id"] == job_id
    assert selected_source_wire["source_attempt"] == record.attempt
    assert selected_source_wire["completed_event_id"] == completed_source.completed_event_id
    assert selected_source_wire["completed_event_payload_sha256"] == (
        completed_source.completed_event_payload_sha256
    )
    assert selected_source_wire["summary"] == selected_owner_payload["hte"]
    packet_association = selected_owner_basis["completed_hte_owner_association"]
    projected_association = selected_source_wire["association"]
    assert "verified_at" in packet_association
    assert "verified_at" in projected_association
    from polisyos.core.contracts.owned_attempt_anchor import (
        OwnedAttemptAnchorProjectionAssociation,
    )

    packet_association_model = OwnedAttemptAnchorProjectionAssociation.model_validate_json(
        json.dumps(packet_association, ensure_ascii=False, allow_nan=False), strict=True
    )
    projected_association_model = OwnedAttemptAnchorProjectionAssociation.model_validate_json(
        json.dumps(projected_association, ensure_ascii=False, allow_nan=False), strict=True
    )
    stable_association_fields = {"verified_at"}
    assert packet_association_model.model_dump(
        mode="python", exclude=stable_association_fields
    ) == projected_association_model.model_dump(mode="python", exclude=stable_association_fields)
    assert packet_association_model.model_dump(
        mode="python", exclude=stable_association_fields
    ) == completed_source.association.model_dump(mode="python", exclude=stable_association_fields)
    from datetime import datetime

    packet_verified_at = datetime.fromisoformat(
        packet_association["verified_at"].replace("Z", "+00:00")
    )
    projected_verified_at = datetime.fromisoformat(
        projected_association["verified_at"].replace("Z", "+00:00")
    )
    projection_reader_at = datetime.fromisoformat(
        selected_projection["reader_at"].replace("Z", "+00:00")
    )
    assert packet_verified_at.utcoffset() is not None
    assert projected_verified_at.utcoffset() is not None
    assert projection_reader_at.utcoffset() is not None
    assert projected_verified_at > packet_verified_at
    assert projection_reader_at >= projected_verified_at

    # A profile dropped from the indexed output fails before either packet reader.
    from dataclasses import replace

    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.runtime.http.routes import runs as runs_route_module

    route_context = runtime_api_env["app"].state.runtime_api_ctx
    route_run_index = route_context.run_index
    route_indexed_owner = route_run_index.get_run(packet_owner_run_id)
    assert route_indexed_owner.run_id == packet_owner_run_id
    assert route_indexed_owner.details.tenant_id == runtime_api_env["tenant_a"]
    indexed_packet_ref = route_indexed_owner.decision_packet_ref
    assert indexed_packet_ref is not None
    assert artifact_ref_identity_key(indexed_packet_ref) == artifact_ref_identity_key(
        selected_owner_ref
    )
    assert indexed_packet_ref.manifest_profile_sha256 == selected_owner_ref.manifest_profile_sha256
    profileless_ref = indexed_packet_ref.model_copy(update={"manifest_profile_sha256": None})
    profileless_owner = replace(route_indexed_owner, decision_packet_ref=profileless_ref)
    original_get_run = route_run_index.get_run
    original_file_system_get_bytes = FileSystemCAS.get_bytes
    profile_drop_reads: list[str] = []

    def profileless_run_lookup(requested_run_id: str) -> Any:
        if requested_run_id == packet_owner_run_id:
            return profileless_owner
        return original_get_run(requested_run_id)

    def reject_profileless_packet_bytes(
        store_instance: FileSystemCAS,
        selector: ArtifactID | ArtifactRef | str,
    ) -> bytes:
        if _cas_selector_id(selector) == _cas_selector_id(selected_owner_ref):
            profile_drop_reads.append("selected_packet_get_bytes_called")
            raise AssertionError("profileless indexed packet bytes must stay unread")
        return original_file_system_get_bytes(store_instance, selector)

    def reject_profileless_bounded_read(*_args: Any, **_kwargs: Any) -> Any:
        profile_drop_reads.append("bounded_packet_reader_called")
        raise AssertionError("profileless indexed packet must fail before bounded read")

    with monkeypatch.context() as profile_drop_patch:
        profile_drop_patch.setattr(route_run_index, "get_run", profileless_run_lookup)
        profile_drop_patch.setattr(FileSystemCAS, "get_bytes", reject_profileless_packet_bytes)
        profile_drop_patch.setattr(
            runs_route_module,
            "read_core_json_artifact_bounded",
            reject_profileless_bounded_read,
        )
        profileless_candidate = candidate_packet_response(packet_owner_run_id, selected_owner_ref)
    assert profileless_candidate.status_code == 409, profileless_candidate.text
    assert profileless_candidate.json()["code"] == "candidate_packet_index_ref_incomplete"
    assert profile_drop_reads == []

    # A same-tenant VIEWER is denied on this exact run/packet/profile before
    # the route can read the bounded DecisionPacket payload.
    from polisyos.core.security.identity import PolicyOSRole
    from polisyos.runtime.http.permissions import RuntimePermission
    from polisyos.runtime.http.routes import runs as runs_route_module
    from tests.unit.runtime.http.test_runtime_api_authz import (
        _AllowOPA,
        _build_secure_client,
        _claims,
        _fixture_bearer,
    )

    viewer_client, viewer_cell, identity_provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
        raise_server_exceptions=False,
    )
    viewer_token = _fixture_bearer("r24-candidate-hte-viewer")
    identity_provider.put_claim(
        viewer_token,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=viewer_cell.cell_id,
            jti="jwt-r24-candidate-hte-viewer",
            roles=frozenset({PolicyOSRole.VIEWER}),
        ),
    )
    indexed_packet_owner = viewer_client.app.state.runtime_api_ctx.run_index.get_run(
        packet_owner_run_id
    )
    assert indexed_packet_owner.run_id == packet_owner_run_id
    assert indexed_packet_owner.details.tenant_id == runtime_api_env["tenant_a"]
    assert selected_owner_ref.manifest_profile_sha256 is not None
    viewer_indexed_packet_ref = indexed_packet_owner.decision_packet_ref
    assert viewer_indexed_packet_ref is not None
    assert artifact_ref_identity_key(viewer_indexed_packet_ref) == artifact_ref_identity_key(
        selected_owner_ref
    )
    assert viewer_indexed_packet_ref.manifest_profile_sha256 == (
        selected_owner_ref.manifest_profile_sha256
    )

    packet_read_attempts: list[str] = []
    from polisyos.core.artifacts.store import FileSystemCAS

    packet_artifact_id = _cas_selector_id(selected_owner_ref)
    original_file_system_get_bytes = FileSystemCAS.get_bytes

    def reject_selected_packet_bytes(
        store_instance: FileSystemCAS,
        selector: ArtifactID | ArtifactRef | str,
    ) -> bytes:
        if _cas_selector_id(selector) == packet_artifact_id:
            packet_read_attempts.append("selected_packet_get_bytes_called")
            raise AssertionError("selected packet CAS bytes read before RUNS_REVIEW denial")
        return original_file_system_get_bytes(store_instance, selector)

    def reject_packet_payload_read(*_args: Any, **_kwargs: Any) -> Any:
        packet_read_attempts.append("bounded_packet_reader_called")
        raise AssertionError("candidate packet payload read before RUNS_REVIEW denial")

    with monkeypatch.context() as denial_patch:
        denial_patch.setattr(FileSystemCAS, "get_bytes", reject_selected_packet_bytes)
        denial_patch.setattr(
            runs_route_module,
            "read_core_json_artifact_bounded",
            reject_packet_payload_read,
        )
        try:
            denied_candidate = viewer_client.get(
                (
                    f"/api/v1/runs/{packet_owner_run_id}/decision-packets/"
                    f"{selected_owner_ref.artifact_id!s}/candidate-hte"
                ),
                params={
                    "manifest_profile_sha256": selected_owner_ref.manifest_profile_sha256,
                },
                headers={
                    "Authorization": f"Bearer {viewer_token}",
                    "X-Tenant-ID": runtime_api_env["tenant_a"],
                },
            )
        finally:
            viewer_client.close()
    assert denied_candidate.status_code == 403, denied_candidate.text
    assert denied_candidate.json()["code"] == "action_permission_denied"
    assert RuntimePermission.RUNS_REVIEW.value in denied_candidate.json()["detail"]
    assert packet_read_attempts == []

    from polisyos.runtime.http.services.control_plane_store import (
        _COMPLETED_HTE_VALIDITY_OUTBOX_TOPIC,
    )

    dependency_key = f"hte_completed_source_run:{run_id}"
    dedupe_key = service._completed_hte_source_invalidation_dedupe_key(
        source_run_id=completed_source.source_run_id,
        source_job_id=completed_source.source_job_id,
        source_attempt=completed_source.source_attempt,
        completed_event_id=completed_source.completed_event_id,
        completed_event_payload_sha256=completed_source.completed_event_payload_sha256,
    )
    completion_event_key = f"{job_id}:job_completed:{completed_source.completed_event_id}"
    completion_intent = service._control_store.get_outbox_topic_event(
        topic=_COMPLETED_HTE_VALIDITY_OUTBOX_TOPIC,
        event_key=completion_event_key,
        job_id=job_id,
    )
    assert completion_intent is not None and completion_intent.state == "pending"
    assert completion_intent.payload["dedupe_key"] == dedupe_key
    assert not [
        event
        for event in service._control_store.list_outbox_events(state=None, limit=500)
        if event.topic == "control.decision_validity.event_published"
        and event.event_key == dedupe_key
    ]

    current_evaluation, _ = service._decision_validity_service.get_evaluation(
        _decision_validity_packet_key(packet_ref),
        force=True,
    )
    # The persisted packet predates source selection; producer completion must
    # not silently upgrade its immutable verification snapshot.
    assert_unresolved_source_warning(current_evaluation)

    original_enqueue = service._control_store.enqueue_outbox_event

    def fail_notification_enqueue(*, topic: str, **kwargs: Any):
        if topic == "control.decision_validity.event_published":
            raise OSError("injected notification persistence failure")
        return original_enqueue(topic=topic, **kwargs)

    monkeypatch.setattr(
        service._control_store,
        "enqueue_outbox_event",
        fail_notification_enqueue,
    )
    assert service.reconcile_pending_completed_hte_source_validity_events() == 0
    completion_intent = service._control_store.get_outbox_topic_event(
        topic=_COMPLETED_HTE_VALIDITY_OUTBOX_TOPIC,
        event_key=completion_event_key,
        job_id=job_id,
    )
    assert completion_intent is not None
    assert completion_intent.state == "pending"
    assert completion_intent.attempt == 1
    assert completion_intent.error_message == "completed_hte_validity_delivery_failed"
    failed_delivery_evaluation, _ = service._decision_validity_service.get_evaluation(
        _decision_validity_packet_key(packet_ref),
        force=True,
    )
    assert failed_delivery_evaluation.status == DecisionValidityStatus.STALE
    assert any(
        trigger.trigger_type == DecisionTriggerType.METRIC_INVALIDATION
        and trigger.status == DecisionValidityStatus.STALE
        and trigger.dependency_key == dependency_key
        for trigger in failed_delivery_evaluation.triggers
    )
    assert not [
        event
        for event in service._control_store.list_outbox_events(state=None, limit=500)
        if event.topic == "control.decision_validity.event_published"
        and event.event_key == dedupe_key
    ]

    monkeypatch.setattr(
        service._control_store,
        "enqueue_outbox_event",
        original_enqueue,
    )
    from _helpers.runtime_http import (
        build_runtime_api_env_from_fixture_seed,
        close_runtime_api_env,
    )

    restarted_env = build_runtime_api_env_from_fixture_seed(
        runtime_api_env,
        include_test_client=False,
        app_kwargs={"repo_root": Path(pytestconfig.rootpath).resolve(strict=True)},
    )
    try:
        restarted_service = restarted_env["app"].state._control_service
        assert restarted_service is not service
        assert restarted_service._control_store is not service._control_store
        assert (
            restarted_service._decision_validity_service is not service._decision_validity_service
        )
        assert restarted_service._completed_hte_validity_outbox_cursor is None
        assert restarted_service._completed_hte_validity_outbox_watermark is None
        restart_pending = restarted_service._control_store.get_outbox_topic_event(
            topic=_COMPLETED_HTE_VALIDITY_OUTBOX_TOPIC,
            event_key=completion_event_key,
            job_id=job_id,
        )
        assert restart_pending is not None
        assert restart_pending.state == "pending"
        assert restart_pending.attempt == 1
        assert restarted_service.reconcile_pending_completed_hte_source_validity_events() == 1
        completion_intent = restarted_service._control_store.get_outbox_topic_event(
            topic=_COMPLETED_HTE_VALIDITY_OUTBOX_TOPIC,
            event_key=completion_event_key,
            job_id=job_id,
        )
        assert completion_intent is not None and completion_intent.state == "published"
        restarted_packet_state = restarted_service._decision_validity_service._state.load_packet(
            _decision_validity_packet_key(packet_ref)
        )
        assert restarted_packet_state is not None
        restarted_events = [
            event
            for event in restarted_packet_state.lifecycle_events
            if event.trigger_type == DecisionTriggerType.METRIC_INVALIDATION
            and dependency_key in event.dependency_keys
        ]
        assert len(restarted_events) == 1
        assert restarted_events[0].event_id == service._completed_hte_source_validity_event_id(
            dedupe_key=dedupe_key
        )
        restarted_outbox_rows = [
            event
            for event in restarted_service._control_store.list_outbox_events(
                state=None,
                limit=500,
            )
            if event.topic == "control.decision_validity.event_published"
            and event.event_key == dedupe_key
        ]
        assert len(restarted_outbox_rows) == 1
    finally:
        close_runtime_api_env(restarted_env)

    current_evaluation, _ = service._decision_validity_service.get_evaluation(
        _decision_validity_packet_key(packet_ref),
        force=True,
    )
    assert current_evaluation.status == DecisionValidityStatus.STALE
    assert any(
        trigger.trigger_type == DecisionTriggerType.METRIC_INVALIDATION
        and trigger.status == DecisionValidityStatus.STALE
        and trigger.dependency_key == dependency_key
        for trigger in current_evaluation.triggers
    )
    packet_state = service._decision_validity_service._state.load_packet(
        _decision_validity_packet_key(packet_ref)
    )
    assert packet_state is not None
    recorded_events = [
        event
        for event in packet_state.lifecycle_events
        if event.trigger_type == DecisionTriggerType.METRIC_INVALIDATION
        and dependency_key in event.dependency_keys
    ]
    assert len(recorded_events) == 1
    recorded_event = recorded_events[0]
    assert recorded_event.dedupe_key == dedupe_key
    assert recorded_event.event_id == service._completed_hte_source_validity_event_id(
        dedupe_key=dedupe_key
    )
    assert recorded_event.payload == {
        "source_run_id": completed_source.source_run_id,
        "source_job_id": completed_source.source_job_id,
        "source_attempt": completed_source.source_attempt,
        "completed_event_id": completed_source.completed_event_id,
        "completed_event_payload_sha256": completed_source.completed_event_payload_sha256,
    }
    outbox_rows = [
        event
        for event in service._control_store.list_outbox_events(state=None, limit=500)
        if event.topic == "control.decision_validity.event_published"
        and event.event_key == dedupe_key
    ]
    assert len(outbox_rows) == 1

    for changed in (
        {"source_job_id": f"{completed_source.source_job_id}.next"},
        {"source_attempt": completed_source.source_attempt + 1},
        {"completed_event_id": completed_source.completed_event_id + 1},
        {"completed_event_payload_sha256": f"sha256:{'f' * 64}"},
    ):
        identity = {
            "source_run_id": completed_source.source_run_id,
            "source_job_id": completed_source.source_job_id,
            "source_attempt": completed_source.source_attempt,
            "completed_event_id": completed_source.completed_event_id,
            "completed_event_payload_sha256": (completed_source.completed_event_payload_sha256),
            **changed,
        }
        assert service._completed_hte_source_invalidation_dedupe_key(**identity) != dedupe_key

    assert service._dispatch_completed_hte_source_validity_for_job(job_id=job_id) is None
    replayed_events = [
        event
        for event in service._decision_validity_service._state.load_packet(
            _decision_validity_packet_key(packet_ref)
        ).lifecycle_events
        if event.trigger_type == DecisionTriggerType.METRIC_INVALIDATION
        and dependency_key in event.dependency_keys
    ]
    assert len(replayed_events) == 1
    outbox_rows = [
        event
        for event in service._control_store.list_outbox_events(state=None, limit=500)
        if event.topic == "control.decision_validity.event_published"
        and event.event_key == dedupe_key
    ]
    assert len(outbox_rows) == 1

    with pytest.raises(
        ValueError,
        match="owned_attempt_projection_current_completed_winner_mismatch",
    ):
        resolve_owned_attempt_anchor_projection_association(
            service=service,
            run_id=run_id,
            expected_job_id=f"{job_id}.substituted",
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=runtime_api_env["cell_a"],
        )

    from dataclasses import replace

    original_get_job = service._control_store.get_job

    def mismatched_selection(job_id_value: str):
        record_value = original_get_job(job_id_value)
        if job_id_value != job_id or record_value is None:
            return record_value
        return replace(
            record_value,
            method_execution_selection={"attempt": record_value.attempt + 1},
        )

    monkeypatch.setattr(service._control_store, "get_job", mismatched_selection)
    assert service._completed_hte_source_validity_request(job_id=job_id) is None
    unchanged_outbox_rows = [
        event
        for event in service._control_store.list_outbox_events(state=None, limit=500)
        if event.topic == "control.decision_validity.event_published"
        and event.event_key == dedupe_key
    ]
    assert len(unchanged_outbox_rows) == 1

    monkeypatch.setattr(service._control_store, "get_job", original_get_job)
    original_terminal_event_reader = service._control_store.get_job_terminal_source_event_record

    def malformed_terminal_event(job_id_value: str):
        event = original_terminal_event_reader(job_id_value)
        return replace(event, payload_sha256="f" * 64) if job_id_value == job_id else event

    monkeypatch.setattr(
        service._control_store,
        "get_job_terminal_source_event_record",
        malformed_terminal_event,
    )
    assert service._completed_hte_source_validity_request(job_id=job_id) is None
    malformed_hash_outbox_rows = [
        event
        for event in service._control_store.list_outbox_events(state=None, limit=500)
        if event.topic == "control.decision_validity.event_published"
        and event.event_key == dedupe_key
    ]
    assert len(malformed_hash_outbox_rows) == 1

    monkeypatch.setattr(
        service._control_store,
        "get_job_terminal_source_event_record",
        original_terminal_event_reader,
    )
    monkeypatch.setattr(service._artifact_store, "get_bytes", original_get_bytes)
    monkeypatch.setattr(
        service,
        "get_method_execution_selection",
        original_public_selection_getter,
    )
    successor_ref, successor_payload = build_followup_packet("dp-followup-after")
    successor_bytes = store.get_bytes(successor_ref)
    assert successor_payload["hte"] is not None
    selected_summary = _validate_strict_json_wire_payload(
        successor_payload["hte"],
        TypeAdapter(DirectMethodExecutionHTESummary),
        invalid_code="direct_method_execution_hte_summary_wire_payload_invalid",
    )
    successor_basis = successor_payload["decision_validity_envelope"]["data_basis"]["summary"]
    assert successor_basis["completed_hte_source_status"] == "selected"
    assert successor_basis["completed_hte_source_run_id"] == run_id
    assert successor_basis["completed_hte_source_job_id"] == job_id
    assert successor_basis["completed_hte_source_attempt"] == record.attempt
    assert successor_basis["completed_hte_completion_event_id"] == (
        completed_source.completed_event_id
    )
    assert successor_basis["completed_hte_publication_authorization"] == "not_established"
    assert successor_basis["completed_hte_currentness_status"] == "reconciled_at_completed_event"
    successor_association = successor_basis["completed_hte_owner_association"]
    completed_association = completed_source.association.model_dump(mode="json", exclude_none=True)
    assert "verified_at" in successor_association
    assert "verified_at" in completed_association
    assert set(successor_association) == set(completed_association)
    assert {key: value for key, value in successor_association.items() if key != "verified_at"} == {
        key: value for key, value in completed_association.items() if key != "verified_at"
    }
    from datetime import datetime

    successor_verified_at = datetime.fromisoformat(
        successor_association["verified_at"].replace("Z", "+00:00")
    )
    completed_verified_at = datetime.fromisoformat(
        completed_association["verified_at"].replace("Z", "+00:00")
    )
    association_checked_at = datetime.now().astimezone()
    assert successor_verified_at.utcoffset() is not None
    assert completed_verified_at.utcoffset() is not None
    assert association_checked_at.utcoffset() is not None
    assert successor_verified_at > completed_verified_at
    assert successor_verified_at <= association_checked_at
    assert dependency_key in successor_basis["completed_hte_dependency_keys"]
    assert (
        f"hte_completed_source_event:{job_id}:{completed_source.completed_event_id}:"
        f"{completed_source.completed_event_payload_sha256}"
    ) in successor_basis["completed_hte_dependency_keys"]
    successor_manifest = store.get_manifest(successor_ref)
    assert successor_manifest is not None
    manifest_bindings = {
        (str(item.artifact_id), item.manifest_profile_sha256) for item in successor_manifest.inputs
    }

    def selected_ref_bindings(value: object):
        if isinstance(value, dict):
            if {"artifact_id", "kind", "media_type", "manifest_profile_sha256"} <= value.keys():
                yield (str(value["artifact_id"]), value["manifest_profile_sha256"])
                return
            for nested in value.values():
                yield from selected_ref_bindings(nested)
        elif isinstance(value, list):
            for nested in value:
                yield from selected_ref_bindings(nested)

    expected_manifest_bindings = set(
        selected_ref_bindings(successor_basis["completed_hte_owner_association"])
    ) | set(selected_ref_bindings(successor_payload["hte"]))
    assert expected_manifest_bindings
    assert expected_manifest_bindings <= manifest_bindings

    old_evaluation, _ = service._decision_validity_service.get_evaluation(
        _decision_validity_packet_key(packet_ref),
        force=True,
    )
    new_evaluation, _ = service._decision_validity_service.get_evaluation(
        _decision_validity_packet_key(successor_ref),
        force=True,
    )
    assert old_evaluation.decision_lineage_key == new_evaluation.decision_lineage_key
    assert old_evaluation.status == DecisionValidityStatus.SUPERSEDED
    assert old_evaluation.superseded_by_ref == str(successor_ref.artifact_id)
    assert new_evaluation.status != DecisionValidityStatus.SUPERSEDED
    assert not any(trigger.dependency_key == dependency_key for trigger in new_evaluation.triggers)
    assert any(
        trigger.trigger_type == DecisionTriggerType.METRIC_INVALIDATION
        and trigger.dependency_key == dependency_key
        for trigger in old_evaluation.triggers
    )
    assert store.get_bytes(packet_ref) == initial_packet_bytes
    assert store.get_bytes(successor_ref) == successor_bytes

    old_content = runtime_api_env["client"].get(
        f"/api/v1/artifacts/{packet_ref.artifact_id!s}/content"
    )
    new_content = runtime_api_env["client"].get(
        f"/api/v1/artifacts/{successor_ref.artifact_id!s}/content"
    )
    for content_response in (old_content, new_content):
        assert content_response.status_code == 409, content_response.text
        content_decision = content_response.json()["extensions"]["authority_surface_decision"]
        assert content_response.json()["code"] == "authority_surface_admission_blocked"
        assert content_decision["purpose"] == "runtime_closeout_authority"
        assert content_decision["reason"] == "authority_surface_signal_missing"
        assert content_decision["consumed_authority_boundary"] is False

    old_candidate = candidate_packet_response("dp-followup-before", packet_ref)
    new_candidate = candidate_packet_response("dp-followup-after", successor_ref)
    for candidate_response in (old_candidate, new_candidate):
        assert candidate_response.status_code == 409, candidate_response.text
        assert candidate_response.json()["code"] == "cross_run_authorization_not_established"

    wrong_profile = runtime_api_env["client"].get(
        f"/api/v1/runs/dp-followup-before/decision-packets/{packet_ref.artifact_id!s}/candidate-hte",
        params={"manifest_profile_sha256": "sha256:" + "0" * 64},
    )
    assert wrong_profile.status_code == 409, wrong_profile.text
    assert wrong_profile.json()["code"] == "candidate_packet_profile_index_mismatch"

    wrong_packet = runtime_api_env["client"].get(
        f"/api/v1/runs/dp-followup-before/decision-packets/{successor_ref.artifact_id!s}/candidate-hte",
        params={"manifest_profile_sha256": successor_ref.manifest_profile_sha256},
    )
    assert wrong_packet.status_code == 409, wrong_packet.text
    assert wrong_packet.json()["code"] == "candidate_packet_id_index_mismatch"

    self_run_id = "dp-followup-self-absent"
    self_ref, self_payload = build_followup_packet(
        self_run_id,
        requested_source_run_id=self_run_id,
    )
    assert self_payload["hte"] is None
    self_basis = self_payload["decision_validity_envelope"]["data_basis"]["summary"]
    assert self_basis["completed_hte_source_status"] == "verification_missing"
    self_candidate = candidate_packet_response(self_run_id, self_ref)
    assert self_candidate.status_code == 200, self_candidate.text
    self_projection = self_candidate.json()
    assert self_projection["candidate_only"] is True
    assert self_projection["packet_run_id"] == self_run_id
    assert self_projection["decision_packet_ref"]["artifact_id"] == str(self_ref.artifact_id)
    assert self_projection["candidate_status"] == "absent"
    assert self_projection["source"] is None
    assert self_projection["publication_authorization"] == "not_established"
    assert self_projection["live_source_currentness"] == "not_established"
    old_validity = runtime_api_env["client"].get(
        f"/api/v1/control/decision-packets/{packet_ref.artifact_id!s}/decision-validity"
    )
    assert old_validity.status_code == 200, old_validity.text
    assert old_validity.json()["status"] == DecisionValidityStatus.SUPERSEDED.value
    assert old_validity.json()["superseded_by_ref"]["artifact_id"] == str(successor_ref.artifact_id)
    assert any(
        trigger["trigger_type"] == DecisionTriggerType.METRIC_INVALIDATION.value
        and trigger["dependency_key"] == dependency_key
        for trigger in old_validity.json()["triggers"]
    )

    # Reuse the selected packet created by the earlier route witness. Its owner
    # run already exists; re-read it here after the outbox/freshness checks.
    selected_owner_basis = selected_owner_payload["decision_validity_envelope"]["data_basis"][
        "summary"
    ]
    assert selected_owner_payload["hte"] == selected_summary.model_dump(mode="json")
    assert selected_owner_basis["completed_hte_source_status"] == "selected"
    assert selected_owner_basis["completed_hte_source_run_id"] == packet_owner_run_id
    assert selected_owner_basis["completed_hte_requested_source_run_id"] == packet_owner_run_id
    assert selected_owner_basis["completed_hte_publication_authorization"] == "not_established"
    assert selected_owner_basis["completed_hte_authority_purpose"] == "candidate_method_evidence"

    selected_candidate = candidate_packet_response(packet_owner_run_id, selected_owner_ref)
    assert selected_candidate.status_code == 200, selected_candidate.text
    selected_projection = selected_candidate.json()
    assert selected_projection["candidate_only"] is True
    assert selected_projection["packet_run_id"] == packet_owner_run_id
    assert selected_projection["decision_packet_ref"]["artifact_id"] == str(
        selected_owner_ref.artifact_id
    )
    assert selected_projection["decision_packet_ref"]["manifest_profile_sha256"] == (
        selected_owner_ref.manifest_profile_sha256
    )
    assert selected_projection["candidate_status"] == "selected"
    assert selected_projection["publication_authorization"] == "not_established"
    assert selected_projection["live_source_currentness"] == "not_established"

    selected_source_wire = selected_projection["source"]
    assert selected_source_wire["source_run_id"] == packet_owner_run_id
    assert selected_source_wire["source_job_id"] == job_id
    assert selected_source_wire["source_attempt"] == record.attempt
    assert selected_source_wire["completed_event_id"] == completed_source.completed_event_id
    assert selected_source_wire["completed_event_payload_sha256"] == (
        completed_source.completed_event_payload_sha256
    )
    assert selected_source_wire["summary"] == selected_owner_payload["hte"]
    packet_association = selected_owner_basis["completed_hte_owner_association"]
    projected_association = selected_source_wire["association"]
    assert "verified_at" in packet_association
    assert "verified_at" in projected_association
    packet_association_model = OwnedAttemptAnchorProjectionAssociation.model_validate_json(
        json.dumps(packet_association, ensure_ascii=False, allow_nan=False), strict=True
    )
    projected_association_model = OwnedAttemptAnchorProjectionAssociation.model_validate_json(
        json.dumps(projected_association, ensure_ascii=False, allow_nan=False), strict=True
    )
    stable_association_fields = {"verified_at"}
    assert packet_association_model.model_dump(
        mode="python", exclude=stable_association_fields
    ) == projected_association_model.model_dump(mode="python", exclude=stable_association_fields)
    from datetime import datetime

    packet_verified_at = datetime.fromisoformat(
        packet_association["verified_at"].replace("Z", "+00:00")
    )
    projected_verified_at = datetime.fromisoformat(
        projected_association["verified_at"].replace("Z", "+00:00")
    )
    projection_reader_at = datetime.fromisoformat(
        selected_projection["reader_at"].replace("Z", "+00:00")
    )
    assert packet_verified_at.utcoffset() is not None
    assert projected_verified_at.utcoffset() is not None
    assert projection_reader_at.utcoffset() is not None
    assert projected_verified_at > packet_verified_at
    assert projection_reader_at >= projected_verified_at

    # A same-tenant VIEWER is denied on this exact run/packet/profile before
    # the route can read the bounded DecisionPacket payload.
    from polisyos.core.security.identity import PolicyOSRole
    from polisyos.runtime.http.permissions import RuntimePermission
    from polisyos.runtime.http.routes import runs as runs_route_module
    from tests.unit.runtime.http.test_runtime_api_authz import (
        _AllowOPA,
        _build_secure_client,
        _claims,
        _fixture_bearer,
    )

    viewer_client, viewer_cell, identity_provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
        raise_server_exceptions=False,
    )
    viewer_token = _fixture_bearer("r24-candidate-hte-viewer")
    identity_provider.put_claim(
        viewer_token,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=viewer_cell.cell_id,
            jti="jwt-r24-candidate-hte-viewer",
            roles=frozenset({PolicyOSRole.VIEWER}),
        ),
    )
    indexed_packet_owner = viewer_client.app.state.runtime_api_ctx.run_index.get_run(
        packet_owner_run_id
    )
    assert indexed_packet_owner.run_id == packet_owner_run_id
    assert indexed_packet_owner.details.tenant_id == runtime_api_env["tenant_a"]
    indexed_packet_ref = indexed_packet_owner.decision_packet_ref
    assert indexed_packet_ref is not None
    assert artifact_ref_identity_key(indexed_packet_ref) == artifact_ref_identity_key(
        selected_owner_ref
    )
    assert indexed_packet_ref.manifest_profile_sha256 == (
        selected_owner_ref.manifest_profile_sha256
    )

    packet_read_attempts: list[str] = []
    from polisyos.core.artifacts.store import FileSystemCAS

    packet_artifact_id = _cas_selector_id(selected_owner_ref)
    original_file_system_get_bytes = FileSystemCAS.get_bytes

    def reject_selected_packet_bytes(
        store_instance: FileSystemCAS,
        selector: ArtifactID | ArtifactRef | str,
    ) -> bytes:
        if _cas_selector_id(selector) == packet_artifact_id:
            packet_read_attempts.append("selected_packet_get_bytes_called")
            raise AssertionError("selected packet CAS bytes read before RUNS_REVIEW denial")
        return original_file_system_get_bytes(store_instance, selector)

    monkeypatch.setattr(FileSystemCAS, "get_bytes", reject_selected_packet_bytes)

    def reject_packet_payload_read(*_args: Any, **_kwargs: Any) -> Any:
        packet_read_attempts.append("bounded_packet_reader_called")
        raise AssertionError("candidate packet payload read before RUNS_REVIEW denial")

    monkeypatch.setattr(
        runs_route_module,
        "read_core_json_artifact_bounded",
        reject_packet_payload_read,
    )
    try:
        denied_candidate = viewer_client.get(
            (
                f"/api/v1/runs/{packet_owner_run_id}/decision-packets/"
                f"{selected_owner_ref.artifact_id!s}/candidate-hte"
            ),
            params={
                "manifest_profile_sha256": selected_owner_ref.manifest_profile_sha256,
            },
            headers={
                "Authorization": f"Bearer {viewer_token}",
                "X-Tenant-ID": runtime_api_env["tenant_a"],
            },
        )
    finally:
        viewer_client.close()
    assert denied_candidate.status_code == 403, denied_candidate.text
    assert denied_candidate.json()["code"] == "action_permission_denied"
    assert RuntimePermission.RUNS_REVIEW.value in denied_candidate.json()["detail"]
    assert packet_read_attempts == []

    # Exercise the production facade, selected policy-design workflow, context
    # owner injection, and real packet node. Upstream scientific stages are
    # pass-through substitutes here; this proves routing and owner transport,
    # not policy admissibility or publication authority.
    from copy import deepcopy

    import polisyos.scientist.orchestration.workflows.builder as workflow_builder
    from polisyos.scientist.api import run_experiment
    from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_DECISION_PACKET_REF
    from polisyos.scientist.orchestration.engine.protocol import NodeOutcome, NodeSpec
    from polisyos.scientist.orchestration.engine.registry import NodeRegistry

    class _PassThroughNode:
        def __init__(self, spec: NodeSpec) -> None:
            self.spec = spec

        def execute(self, ctx: Any, state: ExperimentState) -> NodeOutcome:
            del ctx
            return NodeOutcome(status="ok", state=state)

    real_registry_builder = workflow_builder.build_registry_with_builtin_nodes
    decision_packet_node_id = str(BuildDecisionPacketNode().spec.metadata.component_id)

    def build_route_registry(**kwargs: Any) -> NodeRegistry:
        registry = real_registry_builder(**kwargs)
        for node in registry.values():
            if str(node.spec.metadata.component_id) == decision_packet_node_id:
                continue
            registry.register(_PassThroughNode(node.spec), override=True)
        return registry

    monkeypatch.setattr(
        workflow_builder,
        "build_registry_with_builtin_nodes",
        build_route_registry,
    )
    routed_run_id = "dp-followup-workflow-after"
    routed_state = ExperimentState(
        run_id=routed_run_id,
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle_ref,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
        params={
            "workflow_id": "scientist_policy_design",
            "random_seed": 41,
            "completed_hte_source_run_id": run_id,
        },
    )
    with tenant_scope(
        None,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
    ):
        routed_result = run_experiment(
            routed_state,
            store=store,
            completed_method_hte_selection_owner=service,
        )
        routed_packet_ref = ArtifactRef.model_validate(
            routed_result["artifacts_index"][ARTIFACT_DECISION_PACKET_REF],
            strict=True,
        )
        routed_manifest = store.get_manifest(routed_packet_ref)
        assert routed_manifest is not None
        routed_manifest_bindings = {
            (str(item.artifact_id), item.manifest_profile_sha256) for item in routed_manifest.inputs
        }
        assert {
            (str(trinity_ref.artifact_id), trinity_ref.manifest_profile_sha256),
            (str(registry_bundle_ref.artifact_id), registry_bundle_ref.manifest_profile_sha256),
        } <= routed_manifest_bindings
        routed_packet_bytes = store.get_bytes(routed_packet_ref)
        routed_packet_payload = from_canonical_bytes(routed_packet_bytes)

    assert routed_result["params"]["workflow_id"] == "scientist_policy_design"
    assert routed_packet_payload["hte"] is not None
    routed_summary = _validate_strict_json_wire_payload(
        routed_packet_payload["hte"],
        TypeAdapter(DirectMethodExecutionHTESummary),
        invalid_code="direct_method_execution_hte_summary_wire_payload_invalid",
    )
    assert routed_summary == selected_summary
    routed_basis = routed_packet_payload["decision_validity_envelope"]["data_basis"]["summary"]
    assert routed_basis["completed_hte_source_status"] == "selected"
    assert routed_basis["completed_hte_source_run_id"] == run_id
    assert routed_basis["completed_hte_owner_association"]["job_id"] == job_id
    assert routed_basis["completed_hte_authority_purpose"] == "candidate_method_evidence"
    assert routed_basis["completed_hte_publication_authorization"] == "not_established"

    routed_owner = runtime_api_env["app"].state.runtime_api_ctx.run_index.get_run(routed_run_id)
    assert routed_owner.details.tenant_id == runtime_api_env["tenant_a"]
    assert routed_owner.decision_packet_ref is not None
    assert artifact_ref_identity_key(routed_owner.decision_packet_ref) == artifact_ref_identity_key(
        routed_packet_ref
    )

    routed_content = runtime_api_env["client"].get(
        f"/api/v1/artifacts/{routed_packet_ref.artifact_id!s}/content"
    )
    assert routed_content.status_code == 409, routed_content.text
    assert routed_content.json()["code"] == "authority_surface_admission_blocked"
    routed_decision = routed_content.json()["extensions"]["authority_surface_decision"]
    assert routed_decision["purpose"] == "runtime_closeout_authority"
    assert routed_decision["reason"] == "authority_surface_signal_missing"
    assert routed_decision["consumed_authority_boundary"] is False
    routed_validity = runtime_api_env["client"].get(
        f"/api/v1/control/decision-packets/{routed_packet_ref.artifact_id!s}/decision-validity"
    )
    assert routed_validity.status_code == 200, routed_validity.text
    routed_validity_payload = routed_validity.json()
    assert routed_validity_payload["decision_packet_ref"]["artifact_id"] == str(
        routed_packet_ref.artifact_id
    )
    assert routed_validity_payload["status"] == DecisionValidityStatus.ACTIVE.value
    assert routed_validity_payload["lifecycle_status"] == routed_validity_payload["status"]

    routed_raw_content = runtime_api_env["client"].get(
        f"/api/v1/artifacts/{routed_packet_ref.artifact_id!s}/content",
        headers={"Accept": "application/octet-stream"},
    )
    assert routed_raw_content.status_code == 409, routed_raw_content.text
    routed_refusal = routed_raw_content.json()
    assert routed_refusal["code"] == "authority_surface_admission_blocked"
    routed_decision = routed_refusal["extensions"]["authority_surface_decision"]
    assert routed_decision["surface"] == "artifact"
    assert routed_decision["purpose"] == "runtime_closeout_authority"
    assert routed_decision["reason"] == "authority_surface_signal_missing"
    assert routed_decision["blocking"] is True
    assert routed_decision["consumed_authority_boundary"] is False
    assert store.get_manifest(routed_packet_ref) == routed_manifest
    assert store.get_bytes(routed_packet_ref) == routed_packet_bytes

    unscoped_ref = store.put_json(
        {"producer_output": "unlinked"},
        PutOptions(
            kind="scientist.decision_packet",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.scientist.DecisionPacket", version="3.4"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    unscoped_content = runtime_api_env["client"].get(
        f"/api/v1/artifacts/{unscoped_ref.artifact_id!s}/content"
    )
    assert unscoped_content.status_code == 403, unscoped_content.text
    assert unscoped_content.json()["code"] == "artifact_tenant_unscoped"

    for mutation in (
        "remove_owner_association",
        "foreign_owner_run",
        "duplicate_conflicting_dependency",
    ):
        mutated_payload = deepcopy(routed_packet_payload)
        mutated_envelope = mutated_payload["decision_validity_envelope"]
        mutated_basis = mutated_envelope["data_basis"]["summary"]
        if mutation == "remove_owner_association":
            mutated_basis.pop("completed_hte_owner_association")
        elif mutation == "foreign_owner_run":
            mutated_basis["completed_hte_owner_association"]["run_id"] = "foreign-run"
        else:
            dependency_rows = mutated_envelope["data_basis"]["dependencies"]
            selected_row_index = next(
                index
                for index, row in enumerate(dependency_rows)
                if row["key"].startswith("hte_completed_source_")
            )
            original_row = dependency_rows[selected_row_index]
            duplicate_row = deepcopy(original_row)
            duplicate_row["metadata"]["source_job_id"] = (
                f"{original_row['metadata']['source_job_id']}.conflict"
            )
            dependency_rows.insert(selected_row_index, duplicate_row)
        assert mutated_payload["hte"] == routed_packet_payload["hte"]
        assert mutated_basis["completed_hte_source_status"] == "selected"
        assert (
            mutated_basis["completed_hte_dependency_keys"]
            == (routed_basis["completed_hte_dependency_keys"])
        )
        if mutation == "duplicate_conflicting_dependency":
            duplicate_rows = [
                row
                for row in mutated_envelope["data_basis"]["dependencies"]
                if row["key"] == original_row["key"]
            ]
            assert len(duplicate_rows) == 2
            assert duplicate_rows[0]["metadata"]["source_job_id"].endswith(".conflict")
            assert duplicate_rows[1] == original_row
        with tenant_scope(
            None,
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=runtime_api_env["cell_a"],
        ):
            mutated_ref = store.put_json(
                mutated_payload,
                PutOptions(
                    kind="scientist.decision_packet",
                    media_type="application/json",
                    schema=SchemaInfo(name="polisyos.scientist.DecisionPacket", version="3.4"),
                    inputs=[],
                ),
                canon_spec=CanonSpec(forbid_floats=False),
                return_selected_profile=True,
            )
            mutated_evaluation, _ = service._decision_validity_service.get_evaluation(
                _decision_validity_packet_key(mutated_ref),
                force=True,
            )
        assert mutated_evaluation.status == DecisionValidityStatus.WARNING
        assert any(
            trigger.trigger_type == DecisionTriggerType.METRIC_INVALIDATION
            and trigger.reason == "completed_hte_dependency_basis_not_established"
            for trigger in mutated_evaluation.triggers
        )
        assert store.get_bytes(routed_packet_ref) == routed_packet_bytes

    # The caller-provided run ID is only a lookup request. The same standard
    # workflow without the in-process owner cannot recover or authorize it.
    unowned_state = ExperimentState(
        run_id="dp-followup-workflow-without-owner",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle_ref,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
        params={
            "workflow_id": "scientist_policy_design",
            "random_seed": 41,
            "completed_hte_source_run_id": run_id,
        },
    )
    with tenant_scope(
        None,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
    ):
        unowned_result = run_experiment(unowned_state, store=store)
        unowned_packet_ref = ArtifactRef.model_validate(
            unowned_result["artifacts_index"][ARTIFACT_DECISION_PACKET_REF],
            strict=True,
        )
        unowned_payload = from_canonical_bytes(store.get_bytes(unowned_packet_ref))
    unowned_basis = unowned_payload["decision_validity_envelope"]["data_basis"]["summary"]
    assert unowned_payload["hte"] is None
    assert unowned_basis["completed_hte_source_status"] == "verification_missing"
    assert unowned_basis["completed_hte_requested_source_run_id"] == run_id
    assert unowned_basis["completed_hte_publication_authorization"] == "not_established"


@pytest.mark.usefixtures("_runtime_api_owner_tenant_scope")
def test_current_failed_event_reconciles_input_refusal_without_output_association(
    runtime_api_env: dict[str, Any],
) -> None:
    service, accepted, terminal_event, anchor_ref = _dispatch_refused_request(runtime_api_env)
    assert service._completed_hte_source_validity_request(job_id=accepted["job_id"]) is None
    anchor = _read_anchor(service, anchor_ref)

    assert anchor.input_admission.admission_status == "input_admission_refused"
    assert anchor.predicate_origins.actual_execution_resource_context == "not_established"
    assert anchor.predicate_origins.completed_output_owner_association == "not_established"
    association = resolve_owned_attempt_anchor_refusal_association(
        service=service,
        anchor_ref=anchor_ref,
    )
    assert association.status == "input_refusal_reconciled"
    assert association.anchor_ref == anchor_ref
    assert association.job_failed_event.event_id == terminal_event.event_id
    assert association.job_id == accepted["job_id"]
    assert association.run_id == accepted["run_id"]
    assert type(association.attempt) is int
    assert association.refusal.refusal_code == "hte_contract_target_mismatch"
    assert not hasattr(association, "method_result_ref")
    assert not hasattr(association, "outcome_ref")

    with pytest.raises(
        ValueError, match="owned_attempt_refused_input_has_no_method_output_association"
    ):
        resolve_owned_attempt_anchor_association(service=service, anchor_ref=anchor_ref)

    # Progress is mutable diagnostic state; a forged ref there must not replace
    # the exact full-profile ref selected by the append-only failed event.
    progress = dict(service._control_store.get_job(accepted["job_id"]).progress)
    progress["owned_attempt_anchor_ref"] = {
        **anchor_ref.model_dump(mode="json"),
        "manifest_profile_sha256": "sha256:" + "0" * 64,
    }
    service._control_store.upsert_progress(job_id=accepted["job_id"], progress=progress)
    assert (
        resolve_owned_attempt_anchor_refusal_association(
            service=service,
            anchor_ref=anchor_ref,
        ).anchor_ref
        == anchor_ref
    )


@pytest.mark.usefixtures("_runtime_api_owner_tenant_scope")
def test_empty_selected_input_uses_refusal_anchor_before_content_admission(
    runtime_api_env: dict[str, Any],
) -> None:
    service, _accepted, _terminal_event, anchor_ref = _dispatch_refused_request(
        runtime_api_env,
        wrong_target=False,
        empty=True,
    )
    anchor = _read_anchor(service, anchor_ref)

    assert anchor.input_admission.admission_status == "input_admission_refused"
    assert anchor.input_admission.refusal.refusal_code == "invalid_hte_observational_data"
    with pytest.raises(ValueError, match="owned_attempt_input_admission_refused"):
        _ = anchor.content_admitted_intent_ref
    association = resolve_owned_attempt_anchor_refusal_association(
        service=service,
        anchor_ref=anchor_ref,
    )
    assert association.status == "input_refusal_reconciled"


@pytest.mark.parametrize(
    "mutation",
    ["missing_anchor", "wrong_disposition", "wrong_profile", "wrong_fence", "stale_attempt"],
)
def test_refusal_resolver_rejects_terminal_event_without_exact_anchor_fence(
    runtime_api_env: dict[str, Any],
    mutation: str,
) -> None:
    service, accepted, original_event, anchor_ref = _dispatch_refused_request(runtime_api_env)
    payload = dict(original_event.payload)
    if mutation == "missing_anchor":
        payload.pop("owned_attempt_anchor_ref")
    elif mutation == "wrong_disposition":
        payload["owned_attempt_failure_disposition"] = "execution_failed"
    elif mutation == "wrong_profile":
        selected = dict(payload["owned_attempt_anchor_ref"])
        selected["manifest_profile_sha256"] = "sha256:" + "f" * 64
        payload["owned_attempt_anchor_ref"] = selected
    elif mutation == "wrong_fence":
        payload["lease_owner"] = "different-worker"
    elif mutation == "stale_attempt":
        current = service._control_store.get_job(accepted["job_id"])
        assert current is not None
        payload["attempt"] = current.attempt + 1
    service._control_store.append_event(
        job_id=accepted["job_id"],
        event_type="job_failed",
        payload=payload,
    )

    with pytest.raises(ValueError):
        resolve_owned_attempt_anchor_refusal_association(
            service=service,
            anchor_ref=anchor_ref,
        )


@pytest.mark.usefixtures("_runtime_api_owner_tenant_scope")
def test_refusal_anchor_cannot_replay_after_a_newer_failed_job_for_the_run(
    runtime_api_env: dict[str, Any],
) -> None:
    service, accepted, _terminal_event, anchor_ref = _dispatch_refused_request(runtime_api_env)
    record = service._control_store.get_job(accepted["job_id"])
    assert record is not None
    replacement_job_id = f"{record.job_id}.replacement"
    service._control_store.create_job(
        job_id=replacement_job_id,
        kind="workflow_run",
        run_id=record.run_id,
        pipeline_id=None,
        requested_execution_profile=None,
        effective_execution_profile=record.effective_execution_profile,
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="owned-attempt-anchor-test",
        creation_event_payload={
            "job_id": replacement_job_id,
            "run_id": record.run_id,
            "job_kind": "workflow_run",
            "execution_scope": {
                "tenant_id": runtime_api_env["tenant_a"],
                "cell_id": runtime_api_env["cell_a"],
            },
        },
    )
    worker_id = "owned-attempt-anchor-replacement-worker"
    service._control_store.mark_running(
        job_id=replacement_job_id,
        worker_id=worker_id,
        lease_seconds=60,
    )
    replacement = service._control_store.get_job(replacement_job_id)
    assert replacement is not None and replacement.lease_owner == worker_id
    service._control_store.fail_job(
        job_id=replacement_job_id,
        error_message="superseded failure for current-run probe",
        progress={"state": "failed"},
        expected_lease_owner=worker_id,
        expected_attempt=replacement.attempt,
    )

    with pytest.raises(ValueError, match="not_current_failed_winner"):
        resolve_owned_attempt_anchor_refusal_association(
            service=service,
            anchor_ref=anchor_ref,
        )


def test_same_anchor_artifact_with_forged_profile_is_not_an_owner_selected_ref(
    runtime_api_env: dict[str, Any],
) -> None:
    service, _accepted, _terminal_event, anchor_ref = _dispatch_refused_request(runtime_api_env)
    forged_profile_ref = anchor_ref.model_copy(
        update={"manifest_profile_sha256": "sha256:" + "e" * 64}
    )

    with pytest.raises(ValueError):
        resolve_owned_attempt_anchor_refusal_association(
            service=service,
            anchor_ref=forged_profile_ref,
        )


def test_run_lifecycle_completed_anchor_wrapper_forwards_optional_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep omitted, explicit-null, and string cell selectors distinct."""
    from typing import NoReturn

    from polisyos.core.artifacts.ids import ArtifactID
    from polisyos.core.contracts.owned_attempt_anchor import OwnedAttemptAnchorRef
    from polisyos.runtime.http.services.control import owned_attempt_anchor as owner_anchor
    from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService

    anchor_ref = OwnedAttemptAnchorRef(
        artifact_id=ArtifactID.from_sha256_hex("0" * 64),
        manifest_profile_sha256="sha256:" + "1" * 64,
    )
    owner = object()
    calls: list[tuple[object, OwnedAttemptAnchorRef, dict[str, object]]] = []

    class ResolverCallCapturedError(Exception):
        """Stop the local resolver call after capturing its exact keyword boundary."""

    def capture_resolver_call(
        *,
        service: object,
        anchor_ref: OwnedAttemptAnchorRef,
        **selectors: object,
    ) -> NoReturn:
        calls.append((service, anchor_ref, selectors))
        raise ResolverCallCapturedError

    monkeypatch.setattr(
        owner_anchor,
        "resolve_owned_attempt_anchor_association",
        capture_resolver_call,
    )

    with pytest.raises(ResolverCallCapturedError):
        ControlPlaneService.resolve_owned_attempt_anchor_association(owner, anchor_ref=anchor_ref)
    assert calls[-1] == (owner, anchor_ref, {})

    with pytest.raises(ResolverCallCapturedError):
        ControlPlaneService.resolve_owned_attempt_anchor_association(
            owner,
            anchor_ref=anchor_ref,
            expected_completed_event_id=17,
            expected_job_id="job-17",
            expected_tenant_id="tenant-a",
            expected_cell_id=None,
        )
    assert calls[-1][2] == {
        "expected_completed_event_id": 17,
        "expected_job_id": "job-17",
        "expected_tenant_id": "tenant-a",
        "expected_cell_id": None,
    }

    with pytest.raises(ResolverCallCapturedError):
        ControlPlaneService.resolve_owned_attempt_anchor_association(
            owner,
            anchor_ref=anchor_ref,
            expected_completed_event_id=17,
            expected_job_id="job-17",
            expected_tenant_id="tenant-a",
            expected_cell_id="cell-a",
        )
    assert calls[-1][2]["expected_cell_id"] == "cell-a"

    with pytest.raises(TypeError, match="method_execution_expected_cell_id_invalid"):
        ControlPlaneService.resolve_owned_attempt_anchor_association(
            owner, anchor_ref=anchor_ref, expected_cell_id=object()
        )
    assert len(calls) == 3


def test_hte_lineage_recipes_bind_optional_basis_and_both_owner_edges() -> None:
    """Keep writer output, full-reader, and projection input recipes identical."""
    from polisyos.core.artifacts import input_ref_from_artifact_ref
    from polisyos.runtime.http.services.control.owned_attempt_anchor import (
        _numeric_hte_manifest_input_roles,
        _numeric_hte_outcome_input_roles,
        _owner_binding_inputs,
        _require_manifest_input_roles,
        _require_projection_manifest_inputs,
    )
    from polisyos.scientist.compute.hte_outcome_bridge import (
        _numeric_outcome_inputs as _producer_numeric_outcome_inputs,
    )
    from polisyos.scientist.compute.hte_outcome_bridge import (
        _owner_binding_inputs as _producer_owner_binding_inputs,
    )
    from polisyos.scientist.compute.hte_outcome_bridge import (
        _refusal_diagnostic_inputs as _producer_refusal_diagnostic_inputs,
    )
    from polisyos.scientist.compute.hte_outcome_bridge import (
        _refusal_outcome_inputs as _producer_refusal_outcome_inputs,
    )

    def ref(digit: str, kind: str) -> ArtifactRef:
        profile_digit = format((int(digit, 16) + 1) % 16, "x")
        return ArtifactRef(
            artifact_id="sha256:" + digit * 64,
            kind=kind,
            media_type="application/json",
            manifest_profile_sha256="sha256:" + profile_digit * 64,
        )

    anchor_ref = ref("1", "runtime.owned_attempt_anchor")
    source_ref = ref("2", "ir.observation_method_input")
    method_result_ref = ref("3", "scientist.method_result.causal.hte")
    method_evidence_ref = ref("4", "scientist.method_evidence")
    resource_policy_ref = ref("5", "runtime.observational_input_resource_policy")
    point_result_ref = ref("6", "ir.hte_point_result")
    hte_result_ref = ref("7", "ir.hte_result")
    inference_basis_ref = ref("8", "ir.ate_inference_basis")
    refusal_diagnostic_ref = ref("9", "ir.hte_refusal_diagnostic")
    physical_ref = ref("a", "foundry.hte.physical_source_materialization_binding")
    search_ref = ref("b", "scientist.search.uncertainty_task_binding")
    owner_bindings = _owner_binding_inputs(
        physical_binding_ref=physical_ref,
        search_binding_ref=search_ref,
    )
    producer_owner_bindings = _producer_owner_binding_inputs(
        materialization_binding_ref=physical_ref,
        search_uncertainty_task_binding_ref=search_ref,
    )
    assert producer_owner_bindings == owner_bindings
    assert tuple(role for _ref, role in owner_bindings) == (
        "physical_source_materialization_binding",
        "search_uncertainty_task_binding",
    )

    common = {
        "anchor_ref": anchor_ref,
        "source_data_ref": source_ref,
        "method_result_ref": method_result_ref,
        "method_evidence_ref": method_evidence_ref,
        "resource_policy_ref": resource_policy_ref,
        "owner_binding_inputs": owner_bindings,
    }

    def manifest_for(inputs: tuple[tuple[ArtifactRef, str], ...]) -> SimpleNamespace:
        return SimpleNamespace(
            inputs=tuple(
                input_ref_from_artifact_ref(selected, role=role) for selected, role in inputs
            )
        )

    def assert_both_readers(inputs: tuple[tuple[ArtifactRef, str], ...]) -> None:
        manifest = manifest_for(inputs)
        _require_manifest_input_roles(
            bounded=SimpleNamespace(manifest=manifest),
            inputs=inputs,
            code="lineage_recipe_mismatch",
        )
        _require_projection_manifest_inputs(
            manifest=manifest,
            inputs=inputs,
            code="lineage_recipe_mismatch",
        )

    point_result_inputs = _numeric_hte_manifest_input_roles(prefix=(), **common)
    point_basis_inputs = _numeric_hte_manifest_input_roles(
        prefix=((point_result_ref, "point_result"),), **common
    )
    point_outcome_without_basis = _numeric_hte_outcome_input_roles(
        result_ref=point_result_ref,
        result_role="point_result",
        inference_basis_ref=None,
        **common,
    )
    point_outcome_with_basis = _numeric_hte_outcome_input_roles(
        result_ref=point_result_ref,
        result_role="point_result",
        inference_basis_ref=inference_basis_ref,
        **common,
    )
    interval_result_inputs = _numeric_hte_manifest_input_roles(prefix=(), **common)
    interval_basis_inputs = _numeric_hte_manifest_input_roles(
        prefix=((hte_result_ref, "hte_result"),), **common
    )
    interval_outcome_inputs = _numeric_hte_outcome_input_roles(
        result_ref=hte_result_ref,
        result_role="hte_result",
        inference_basis_ref=inference_basis_ref,
        **common,
    )
    refusal_diagnostic_inputs = (
        (anchor_ref, "owned_attempt_anchor"),
        (method_result_ref, "method_result"),
        (method_evidence_ref, "method_evidence"),
        (resource_policy_ref, "resource_policy"),
        *owner_bindings,
    )
    refusal_outcome_inputs = (
        (refusal_diagnostic_ref, "refusal_diagnostic"),
        (anchor_ref, "owned_attempt_anchor"),
        (method_result_ref, "method_result"),
        (method_evidence_ref, "method_evidence"),
        (resource_policy_ref, "resource_policy"),
        (source_ref, "source_data"),
        *owner_bindings,
    )
    producer_base_inputs = (
        (anchor_ref, "owned_attempt_anchor"),
        (source_ref, "source_data"),
        (method_result_ref, "method_result"),
        (method_evidence_ref, "method_evidence"),
        (resource_policy_ref, "resource_policy"),
        *producer_owner_bindings,
    )
    producer_point_without_basis = _producer_numeric_outcome_inputs(
        result_ref=point_result_ref,
        result_role="point_result",
        inference_basis_ref=None,
        base_inputs=producer_base_inputs,
    )
    producer_point_with_basis = _producer_numeric_outcome_inputs(
        result_ref=point_result_ref,
        result_role="point_result",
        inference_basis_ref=inference_basis_ref,
        base_inputs=producer_base_inputs,
    )
    producer_interval_with_basis = _producer_numeric_outcome_inputs(
        result_ref=hte_result_ref,
        result_role="hte_result",
        inference_basis_ref=inference_basis_ref,
        base_inputs=producer_base_inputs,
    )
    producer_refusal_diagnostic_inputs = _producer_refusal_diagnostic_inputs(
        anchor_ref=anchor_ref,
        method_result_ref=method_result_ref,
        method_evidence_ref=method_evidence_ref,
        resource_policy_ref=resource_policy_ref,
        owner_binding_inputs=producer_owner_bindings,
    )
    producer_refusal_outcome_inputs = _producer_refusal_outcome_inputs(
        refusal_diagnostic_ref=refusal_diagnostic_ref,
        anchor_ref=anchor_ref,
        method_result_ref=method_result_ref,
        method_evidence_ref=method_evidence_ref,
        resource_policy_ref=resource_policy_ref,
        source_data_ref=source_ref,
        owner_binding_inputs=producer_owner_bindings,
    )
    assert producer_point_without_basis == point_outcome_without_basis
    assert producer_point_with_basis == point_outcome_with_basis
    assert producer_interval_with_basis == interval_outcome_inputs
    assert producer_refusal_diagnostic_inputs == refusal_diagnostic_inputs
    assert producer_refusal_outcome_inputs == refusal_outcome_inputs
    for producer_recipe in (
        producer_point_without_basis,
        producer_point_with_basis,
        producer_interval_with_basis,
        producer_refusal_diagnostic_inputs,
        producer_refusal_outcome_inputs,
    ):
        assert_both_readers(producer_recipe)
    for recipe in (
        point_result_inputs,
        point_basis_inputs,
        point_outcome_without_basis,
        point_outcome_with_basis,
        interval_result_inputs,
        interval_basis_inputs,
        interval_outcome_inputs,
        refusal_diagnostic_inputs,
        refusal_outcome_inputs,
    ):
        assert_both_readers(recipe)

    wrong_order_bindings = tuple(reversed(owner_bindings))
    wrong_order_inputs = _producer_numeric_outcome_inputs(
        result_ref=point_result_ref,
        result_role="point_result",
        inference_basis_ref=inference_basis_ref,
        base_inputs=(*producer_base_inputs[:-2], *wrong_order_bindings),
    )
    wrong_order_manifest = manifest_for(wrong_order_inputs)
    with pytest.raises(ValueError, match="lineage_recipe_mismatch"):
        _require_manifest_input_roles(
            bounded=SimpleNamespace(manifest=wrong_order_manifest),
            inputs=point_outcome_with_basis,
            code="lineage_recipe_mismatch",
        )
    with pytest.raises(ValueError, match="lineage_recipe_mismatch"):
        _require_projection_manifest_inputs(
            manifest=wrong_order_manifest,
            inputs=point_outcome_with_basis,
            code="lineage_recipe_mismatch",
        )

    dropped_basis_manifest = manifest_for(point_outcome_without_basis)
    with pytest.raises(ValueError, match="lineage_recipe_mismatch"):
        _require_manifest_input_roles(
            bounded=SimpleNamespace(manifest=dropped_basis_manifest),
            inputs=point_outcome_with_basis,
            code="lineage_recipe_mismatch",
        )
    with pytest.raises(ValueError, match="lineage_recipe_mismatch"):
        _require_projection_manifest_inputs(
            manifest=dropped_basis_manifest,
            inputs=point_outcome_with_basis,
            code="lineage_recipe_mismatch",
        )

    wrong_profile_search = search_ref.model_copy(
        update={"manifest_profile_sha256": "sha256:" + "d" * 64}
    )
    wrong_profile_inputs = _producer_numeric_outcome_inputs(
        result_ref=point_result_ref,
        result_role="point_result",
        inference_basis_ref=inference_basis_ref,
        base_inputs=(
            *producer_base_inputs[:-2],
            (physical_ref, "physical_source_materialization_binding"),
            (wrong_profile_search, "search_uncertainty_task_binding"),
        ),
    )
    wrong_profile_manifest = manifest_for(wrong_profile_inputs)
    with pytest.raises(ValueError, match="lineage_recipe_mismatch"):
        _require_manifest_input_roles(
            bounded=SimpleNamespace(manifest=wrong_profile_manifest),
            inputs=point_outcome_with_basis,
            code="lineage_recipe_mismatch",
        )
    with pytest.raises(ValueError, match="lineage_recipe_mismatch"):
        _require_projection_manifest_inputs(
            manifest=wrong_profile_manifest,
            inputs=point_outcome_with_basis,
            code="lineage_recipe_mismatch",
        )
