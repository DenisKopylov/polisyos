from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace
from typing import Any, Literal

import pytest
from pydantic import BaseModel, ConfigDict

from polisyos.core.artifacts.canonical_profile import (
    read_core_json_artifact_bounded,
    validate_core_model_bounded_read,
)
from polisyos.core.artifacts.manifest import (
    ArtifactGovernanceInfo,
    ArtifactRef,
    SchemaInfo,
)
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.owned_attempt_anchor import (
    OwnedAttemptAnchor,
    OwnedAttemptAnchorRef,
    OwnedHTERequestContextV1,
)
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.runtime.http.services.control.owned_attempt_anchor import (
    OwnedAttemptAnchorVersionRefusalError,
    _read_projection_manifest,
    _require_intent_request_context_pair,
    _require_successor_anchor_intent_pair,
    _resolve_historical_search_binding,
    _resource_evidence_payload,
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
    bounded = read_core_json_artifact_bounded(
        service._artifact_store,
        anchor_ref,
        limits=service._observational_read_limits(),
    )
    return validate_core_model_bounded_read(OwnedAttemptAnchor, bounded)


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


def test_completed_attempt_projection_matches_full_association_without_output_payload_reads(
    runtime_api_env: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A completed owner summary is reconciled from refs/manifests, not output bytes."""
    pytest.importorskip("econml")
    from _helpers.control_worker import dispatch_one_control_job, stop_embedded_control_worker

    service = runtime_api_env["app"].state._control_service
    stop_embedded_control_worker(service)
    source_ref = _put_hte_input(
        service,
        wrong_target=False,
        empty=False,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
    )
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
    assert (
        dispatch_one_control_job(
            store=service._control_store,
            handler=service._process_control_job,
            expected_job_id=job_id,
        )
        == job_id
    )
    record = service._control_store.get_latest_job_by_run(run_id)
    assert record is not None and record.job_id == job_id and record.state == "completed"
    selection_payload = record.method_execution_selection
    assert isinstance(selection_payload, dict)
    anchor_ref = OwnedAttemptAnchorRef.model_validate(
        selection_payload["owned_attempt_anchor_ref"], strict=True
    )
    anchor = _read_anchor(service, anchor_ref)
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

    from pydantic import TypeAdapter

    from polisyos.core.contracts.runtime import (
        DirectMethodExecutionSelection,
        MethodExecutionSelection,
    )

    selected = TypeAdapter(MethodExecutionSelection).validate_python(
        selection_payload,
        strict=True,
    )
    assert type(selected) is DirectMethodExecutionSelection
    assert selected.hte is not None
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
        ref.artifact_id
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

    def reject_output_payload(selector: object) -> bytes:
        artifact_id = getattr(selector, "artifact_id", selector)
        if artifact_id in forbidden_payload_ids:
            raise AssertionError("bounded projection must not read HTE or source payload bytes")
        return original_get_bytes(selector)

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
    assert completed_source.summary == selected.hte
    assert completed_source.association.selected_summary_sha256 == expected_digest
    assert completed_source.association.job_completed_event == projection.job_completed_event
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


def test_current_failed_event_reconciles_input_refusal_without_output_association(
    runtime_api_env: dict[str, Any],
) -> None:
    service, accepted, terminal_event, anchor_ref = _dispatch_refused_request(runtime_api_env)
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
