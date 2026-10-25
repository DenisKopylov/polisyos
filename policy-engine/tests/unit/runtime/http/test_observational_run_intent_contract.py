"""Semantic contracts for selected observational method requests and run projections."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts.bounded_liveness import BoundedLivenessResolution
from polisyos.core.contracts.control import (
    _OBSERVATIONAL_INPUT_CONSUMED_REQUEST_FIELDS,
    WorkflowRunRequest,
)
from polisyos.core.contracts.owned_attempt_anchor import (
    OwnedHTERequestContextV1,
    SelectedArtifactRef,
)
from polisyos.core.contracts.runtime import (
    ContentAdmittedObservationalRunIntent,
    DirectMethodExecutionSelection,
    GraphMethodExecutionSelection,
    MethodExecutionSelection,
    ObservationalInputResourcePolicy,
    ObservationalRunIntent,
    SearchUncertaintyTaskAdmissionSnapshot,
)


def _ref(kind: str, marker: str, *, profile: bool = True) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=f"sha256:{marker * 64}",
        kind=kind,
        media_type="application/json",
        manifest_profile_sha256=f"sha256:{marker * 64}" if profile else None,
    )


def _observational_input(protocol: str = "method_input_envelope_v1") -> dict[str, object]:
    source_kind = (
        "ir.observation_method_input"
        if protocol == "method_input_envelope_v1"
        else "ir.observational_data"
    )
    return {
        "protocol": protocol,
        "source_ref": _ref(source_kind, "a").model_dump(mode="json"),
        "method": {"fqn": "causal.hte.forest_dr@1.0.0"},
    }


def _direct_selection() -> dict[str, object]:
    source = _ref("ir.observation_method_input", "a")
    return {
        "selection_kind": "direct_method",
        "job_id": "job-1",
        "run_id": "run-1",
        "attempt": 1,
        "requested_source_ref": source.model_dump(mode="json"),
        "observational_run_intent_ref": _ref("runtime.observational_run_intent", "b").model_dump(
            mode="json"
        ),
        "content_admitted_intent_ref": _ref(
            "runtime.content_admitted_observational_run_intent", "c"
        ).model_dump(mode="json"),
        "resource_policy_ref": _ref("runtime.observational_input_resource_policy", "f").model_dump(
            mode="json"
        ),
        "submitted_input_ref": source.model_dump(mode="json"),
        "effective_input_ref": source.model_dump(mode="json"),
        "method_result_ref": _ref("scientist.method_result.causal.hte", "d").model_dump(
            mode="json"
        ),
        "method_evidence_ref": _ref("scientist.method_evidence", "e").model_dump(mode="json"),
        "contract_target_id": "foundry.causal.hte_observational_data.v1",
        "contract_target": "polisyos.foundry.methods.catalog.causal.protocols.HTEObservationalData",
        "method_fqn": "causal.hte.forest_dr@1.0.0",
        "method_version": "1.0.0",
        "method_abi_digest": "f" * 64,
        "method_build_digest": "1" * 64,
        "method_build_digest_scope": "class_source_only",
        "resource_policy_digest": "2" * 64,
        "source_protocol": "method_input_envelope_v1",
        "normalization": "canonical_passthrough",
        "limitations": [
            "candidate_input_not_external_truth",
            "scientific_validity_not_established",
            "units_and_context_not_established",
        ],
        "method_dispatch_binding_status": "recomputed",
        "posterior_summary_refs": [],
    }


def _content_admitted_intent(
    protocol: str = "method_input_envelope_v1",
    normalization: str = "canonical_passthrough",
) -> dict[str, object]:
    source_kind = (
        "ir.observation_method_input"
        if protocol == "method_input_envelope_v1"
        else "ir.observational_data"
    )
    source = _ref(source_kind, "a")
    effective = (
        source
        if protocol == "method_input_envelope_v1"
        else _ref("ir.observation_method_input", "d")
    )
    return {
        "job_id": "job-1",
        "run_id": "run-1",
        "attempt": 1,
        "requested_intent_ref": _ref("runtime.observational_run_intent", "b").model_dump(
            mode="json"
        ),
        "requested_source_ref": source.model_dump(mode="json"),
        "source_manifest_sha256": "c" * 64,
        "resource_policy_ref": _ref("runtime.observational_input_resource_policy", "f").model_dump(
            mode="json"
        ),
        "submitted_input_ref": source.model_dump(mode="json"),
        "effective_input_ref": effective.model_dump(mode="json"),
        "contract_target_id": "foundry.causal.hte_observational_data.v1",
        "contract_target": "polisyos.foundry.methods.catalog.causal.protocols.HTEObservationalData",
        "method_fqn": "causal.hte.forest_dr@1.0.0",
        "source_protocol": protocol,
        "normalization": normalization,
        "limitations": [
            "candidate_input_not_external_truth",
            "scientific_validity_not_established",
            "units_and_context_not_established",
            *(["legacy_hte_json_v1_source_normalized"] if protocol == "legacy_hte_json_v1" else []),
        ],
        "source_governance": {"classification": "public"},
        "source_tenant_context": None,
        "observed_manifest_bytes": 100,
        "observed_manifest_selection_bytes": 100,
        "observed_manifest_verification_bytes": 100,
        "observed_payload_bytes": 20,
        "observed_source_bytes": 220,
        "payload_integrity_verified": True,
        "observed_bytes": 20,
        "observed_depth": 2,
        "observed_elements": 7,
        "resource_policy_digest": "e" * 64,
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("observed_manifest_bytes", 101),
        ("observed_source_bytes", 221),
    ],
)
def test_content_admitted_intent_rejects_incoherent_core_usage(
    field: str,
    value: int,
) -> None:
    payload = _content_admitted_intent()
    payload[field] = value

    with pytest.raises(ValidationError, match="content_admitted_observational_read_usage_mismatch"):
        ContentAdmittedObservationalRunIntent.model_validate(payload)


def test_historical_content_intent_target_omission_is_readable_but_selection_requires_target_id() -> (
    None
):
    admitted = _content_admitted_intent()
    admitted["contract_target_id"] = None
    ContentAdmittedObservationalRunIntent.model_validate(admitted)

    selection = _direct_selection()
    selection["contract_target_id"] = None
    with pytest.raises(ValidationError, match="direct_method_execution_input_selection_invalid"):
        DirectMethodExecutionSelection.model_validate(selection)


def _graph_selection() -> dict[str, object]:
    return {
        "selection_kind": "graph_method",
        "job_id": "job-1",
        "run_id": "run-1",
        "attempt": 2,
        "method_result_ref": None,
        "source_experiment_state_ref": _ref("scientist.experiment_state", "d").model_dump(
            mode="json"
        ),
        "simulation_result_ref": _ref("foundry.simulation_result", "a").model_dump(mode="json"),
        "method_execution_bundle_ref": _ref("foundry.method_execution_bundle", "b").model_dump(
            mode="json"
        ),
        "method_metric_binding_set_ref": _ref("foundry.method_metric_binding_set", "c").model_dump(
            mode="json"
        ),
        "metric_verification_status": "verification_missing",
        "method_metric_projection": None,
    }


def test_legacy_workflow_request_remains_available_when_observational_input_is_absent() -> None:
    request = WorkflowRunRequest.model_validate(
        {"data_source": {"input_bindings_ref": "sha256:" + "a" * 64}}
    )

    assert request.observational_input is None
    assert request.data_source is not None


def test_workflow_source_is_required_only_for_the_legacy_path() -> None:
    with pytest.raises(
        ValidationError, match="workflow_data_source_required_without_observational_input"
    ):
        WorkflowRunRequest.model_validate({})

    request = WorkflowRunRequest.model_validate({"observational_input": _observational_input()})
    assert request.data_source is None


def test_observational_input_omission_differs_from_explicit_null() -> None:
    request = WorkflowRunRequest.model_validate(
        {
            "data_source": {"input_bindings_ref": "sha256:" + "a" * 64},
        }
    )
    assert "observational_input" not in request.model_fields_set

    with pytest.raises(ValidationError, match="observational_input_explicit_null"):
        WorkflowRunRequest.model_validate(
            {
                "data_source": {"input_bindings_ref": "sha256:" + "a" * 64},
                "observational_input": None,
            }
        )


def test_observational_input_rejects_conflicting_data_source_and_top_level_params() -> None:
    with pytest.raises(ValidationError, match="observational_input_data_source_conflict"):
        WorkflowRunRequest.model_validate(
            {
                "data_source": {"input_bindings_ref": "sha256:" + "b" * 64},
                "observational_input": _observational_input(),
            }
        )

    with pytest.raises(ValidationError, match="observational_input_top_level_params_conflict"):
        WorkflowRunRequest.model_validate(
            {
                "observational_input": _observational_input(),
                "params": {"n_estimators": 9},
            }
        )


def test_observational_data_source_presence_conflicts_even_when_empty() -> None:
    for data_source in (
        {},
        {"input_bindings_ref": ""},
        {"data_snapshot_ref": ""},
    ):
        with pytest.raises(ValidationError, match="observational_input_data_source_conflict"):
            WorkflowRunRequest.model_validate(
                {"observational_input": _observational_input(), "data_source": data_source}
            )


def test_observational_input_rejects_every_explicitly_unconsumed_request_field() -> None:
    request_fields = set(WorkflowRunRequest.model_fields)
    ignored_fields = request_fields.difference(_OBSERVATIONAL_INPUT_CONSUMED_REQUEST_FIELDS)
    assert ignored_fields
    for name in sorted(ignored_fields):
        value: object = "strict" if name == "checkpoint_policy" else "sha256:" + "d" * 64
        with pytest.raises(ValidationError, match="observational_input_unconsumed_request_fields"):
            WorkflowRunRequest.model_validate(
                {"observational_input": _observational_input(), name: value}
            )

    optional_unconsumed_fields = [
        name
        for name in sorted(ignored_fields)
        if WorkflowRunRequest.model_fields[name].default is None
    ]
    for name in optional_unconsumed_fields:
        with pytest.raises(ValidationError, match="observational_input_unconsumed_request_fields"):
            WorkflowRunRequest.model_validate(
                {"observational_input": _observational_input(), name: None}
            )


def test_observational_input_accepts_only_consumed_shared_controls() -> None:
    request = WorkflowRunRequest.model_validate(
        {
            "observational_input": _observational_input(),
            "mode": "workflow",
            "execution_profile": "research",
            "policy_flags": {"allow_mock_fallback": False},
            "params": {},
        }
    )
    assert request.execution_profile == "research"
    assert request.policy_flags.allow_mock_fallback is False
    assert request.params == {}


def test_method_selection_accepts_latest_absence_and_exact_registered_version() -> None:
    for method, expected in (
        ("causal.hte.forest_dr", None),
        ("causal.hte.forest_dr@1.1.0", None),
        ("causal.hte.forest_dr", "1.1.0"),
    ):
        raw = _observational_input()
        raw["method"] = {"fqn": method, **({"version": expected} if expected else {})}
        parsed = WorkflowRunRequest.model_validate({"observational_input": raw})
        assert parsed.observational_input.method.fqn == method
        assert parsed.observational_input.method.version == expected

    conflict = _observational_input()
    conflict["method"] = {"fqn": "causal.hte.forest_dr@1.1.0", "version": "1.0.0"}
    with pytest.raises(ValidationError, match="observational_method_version_conflict"):
        WorkflowRunRequest.model_validate({"observational_input": conflict})


def test_resource_policy_keeps_r1_digest_and_pins_r2_target_and_required_n_jobs() -> None:
    historical = ObservationalInputResourcePolicy()
    assert historical.revision == "r1"
    assert historical.digest() == "7fe0e4ed811e07b52084f5713854a99c4acdf6a0376b581060f8fc97b078dc4a"

    serial = ObservationalInputResourcePolicy(
        schema_version="polisyos.runtime.observational_input_resource_policy.v2",
        revision="r2",
        method_contract_target=(
            "polisyos.foundry.methods.catalog.causal.protocols.HTEObservationalData"
        ),
        required_estimator_n_jobs=1,
    )
    assert serial.method_contract_target == (
        "polisyos.foundry.methods.catalog.causal.protocols.HTEObservationalData"
    )
    assert serial.required_estimator_n_jobs == 1
    assert serial.digest() != historical.digest()

    for invalid in (
        {
            "schema_version": "polisyos.runtime.observational_input_resource_policy.v2",
            "revision": "r2",
            "required_estimator_n_jobs": 1,
        },
        {
            "schema_version": "polisyos.runtime.observational_input_resource_policy.v2",
            "revision": "r2",
            "method_contract_target": (
                "polisyos.foundry.methods.catalog.causal.protocols.OtherData"
            ),
            "required_estimator_n_jobs": 1,
        },
        {
            "schema_version": "polisyos.runtime.observational_input_resource_policy.v2",
            "revision": "r2",
            "method_contract_target": (
                "polisyos.foundry.methods.catalog.causal.protocols.HTEObservationalData"
            ),
        },
        {
            "schema_version": "polisyos.runtime.observational_input_resource_policy.v2",
            "revision": "r2",
            "method_contract_target": (
                "polisyos.foundry.methods.catalog.causal.protocols.HTEObservationalData"
            ),
            "required_estimator_n_jobs": 2,
        },
        {"revision": "r1", "required_estimator_n_jobs": 1},
    ):
        with pytest.raises(ValidationError):
            ObservationalInputResourcePolicy.model_validate(invalid)

    with pytest.raises(
        ValidationError,
        match="observational_input_resource_policy_required_estimator_n_jobs_must_be_integer",
    ):
        ObservationalInputResourcePolicy.model_validate(
            {
                "schema_version": "polisyos.runtime.observational_input_resource_policy.v2",
                "revision": "r2",
                "method_contract_target": (
                    "polisyos.foundry.methods.catalog.causal.protocols.HTEObservationalData"
                ),
                "required_estimator_n_jobs": True,
            }
        )


def _requested_intent(
    *,
    method_fqn: str,
    method_version: str,
    resource_policy: ObservationalInputResourcePolicy,
    resolved_params: dict[str, object],
) -> dict[str, object]:
    source = _ref("ir.observation_method_input", "a")
    return {
        "job_id": "job-1",
        "run_id": "run-1",
        "requested_source_ref": source.model_dump(mode="json"),
        "source_manifest_sha256": "c" * 64,
        "protocol": "method_input_envelope_v1",
        "method_fqn": method_fqn,
        "method_version": method_version,
        "method_abi_digest": "a" * 64,
        "method_build_digest": "b" * 64,
        "submitted_params_present": False,
        "submitted_params": {},
        "resolved_params": resolved_params,
        "seed": 0,
        "resource_policy": resource_policy.model_dump(mode="json"),
        "resource_policy_digest": resource_policy.digest(),
        "source_governance": {"classification": "public"},
    }


def test_run_intent_preserves_r1_history_and_requires_r2_serial_parameter() -> None:
    historical = ObservationalInputResourcePolicy()
    old_intent = _requested_intent(
        method_fqn="causal.hte.forest_dr@1.0.0",
        method_version="1.0.0",
        resource_policy=historical,
        resolved_params={},
    )
    assert ObservationalRunIntent.model_validate(old_intent).method_version == "1.0.0"

    serial = ObservationalInputResourcePolicy(
        schema_version="polisyos.runtime.observational_input_resource_policy.v2",
        revision="r2",
        method_contract_target=(
            "polisyos.foundry.methods.catalog.causal.protocols.HTEObservationalData"
        ),
        required_estimator_n_jobs=1,
    )
    current_intent = _requested_intent(
        method_fqn="causal.hte.forest_dr@1.1.0",
        method_version="1.1.0",
        resource_policy=serial,
        resolved_params={"n_jobs": 1},
    )
    assert ObservationalRunIntent.model_validate(current_intent).resolved_params == {"n_jobs": 1}

    for params, fqn, version in (
        ({}, "causal.hte.forest_dr@1.1.0", "1.1.0"),
        ({"n_jobs": 2}, "causal.hte.forest_dr@1.1.0", "1.1.0"),
        ({"n_jobs": True}, "causal.hte.forest_dr@1.1.0", "1.1.0"),
    ):
        invalid = _requested_intent(
            method_fqn=fqn,
            method_version=version,
            resource_policy=serial,
            resolved_params=params,
        )
        with pytest.raises(ValidationError):
            ObservationalRunIntent.model_validate(invalid)

    incompatible_historical_intent = _requested_intent(
        method_fqn="causal.hte.forest_dr@1.0.0",
        method_version="1.0.0",
        resource_policy=serial,
        resolved_params={"n_jobs": 1},
    )
    with pytest.raises(
        ValidationError,
        match="observational_run_intent_method_resource_profile_invalid",
    ):
        ObservationalRunIntent.model_validate(incompatible_historical_intent)


def test_successor_run_intent_binds_typed_request_context_and_alpha() -> None:
    """Require the same exact Core request context that the worker anchor reads."""
    method_fqn = "causal.hte.double_ml@2.0.0"
    target = "polisyos.foundry.methods.catalog.causal.protocols.HTEObservationalData"
    context = OwnedHTERequestContextV1(
        request_estimand_status="declared",
        request_estimand="average_treatment_effect",
        request_target_scope_status="declared",
        request_target_scope="selected_evaluation_rows",
        outcome_variable_status="declared",
        outcome_variable_id="outcome",
        treatment_variable_status="declared",
        treatment_variable_id="treatment",
        contrast_status="declared",
        control_value=0.0,
        treated_value=1.0,
        request_alpha_status="declared",
        requested_alpha=0.05,
        requested_guarantee_status="not_established",
        requested_guarantee=None,
    )
    policy = ObservationalInputResourcePolicy(
        schema_version="polisyos.runtime.observational_input_resource_policy.v5",
        revision="r5",
        method_contract_target=target,
        method_execution_wait_policy=BoundedLivenessResolution(
            producer_key="runtime.observational_method_execution",
            deadline_s=60.0,
            retry_ceiling=0,
            config_id="runtime-test",
            config_version="1",
            owner="runtime-test",
            feature_flag="runtime-test",
        ),
        required_estimator_n_jobs=None,
        method_fqn=method_fqn,
        method_profile_id="econml.dml.point_only@2.0",
        execution_scope="producer_scoped_joblib_parallelism_one",
        max_jobs=1,
    )
    payload = _requested_intent(
        method_fqn=method_fqn,
        method_version="2.0.0",
        resource_policy=policy,
        resolved_params={"alpha": 0.05},
    )
    payload.update(
        {
            "schema_version": "polisyos.runtime.observational_run_intent.v2",
            "owned_hte_request_context": context.model_dump(mode="json"),
            "resource_policy_ref": _ref(
                "runtime.observational_input_resource_policy", "f"
            ).model_dump(mode="json"),
            "contract_target_id": "foundry.causal.hte_observational_data.v1",
            "contract_target_fqn": target,
        }
    )

    admitted = ObservationalRunIntent.model_validate(payload)

    assert admitted.owned_hte_request_context == context
    assert admitted.selection_digest() != ""

    mismatched_alpha = dict(payload, resolved_params={"alpha": 0.1})
    with pytest.raises(
        ValidationError,
        match="observational_run_intent_hte_successor_context_invalid",
    ):
        ObservationalRunIntent.model_validate(mismatched_alpha)

    misspelled_context = dict(context.model_dump(mode="json"))
    misspelled_context["request_guarantee_status"] = "not_established"
    with pytest.raises(ValidationError):
        ObservationalRunIntent.model_validate(
            dict(payload, owned_hte_request_context=misspelled_context)
        )


def test_observational_method_seed_is_pinned_by_runtime_not_request() -> None:
    raw = _observational_input()
    raw["method"] = {"fqn": "causal.hte.forest_dr@1.0.0", "seed": 7}
    with pytest.raises(ValidationError):
        WorkflowRunRequest.model_validate({"observational_input": raw})


def test_method_version_and_params_are_absent_or_nonnull_values() -> None:
    request = WorkflowRunRequest.model_validate({"observational_input": _observational_input()})
    method = request.observational_input.method
    assert "version" not in method.model_fields_set
    assert "params" not in method.model_fields_set
    assert method.fqn == "causal.hte.forest_dr@1.0.0"

    explicit_empty_params = _observational_input()
    explicit_empty_params["method"] = {
        "fqn": "causal.hte.forest_dr@1.0.0",
        "params": {},
    }
    parsed = WorkflowRunRequest.model_validate({"observational_input": explicit_empty_params})
    assert "params" in parsed.observational_input.method.model_fields_set
    assert parsed.observational_input.method.params == {}

    for method in (
        {"fqn": "causal.hte.forest_dr", "version": None},
        {"fqn": "causal.hte.forest_dr", "params": None},
    ):
        raw = _observational_input()
        raw["method"] = method
        with pytest.raises(ValidationError):
            WorkflowRunRequest.model_validate({"observational_input": raw})


def test_observational_source_requires_exact_profile_kind_and_media_type() -> None:
    for source_ref in (
        _ref("ir.observation_method_input", "a", profile=False),
        _ref("ir.observational_data", "a"),
    ):
        raw = _observational_input()
        raw["source_ref"] = source_ref.model_dump(mode="json")
        with pytest.raises(ValidationError):
            WorkflowRunRequest.model_validate({"observational_input": raw})


@pytest.mark.parametrize(
    ("protocol", "normalization"),
    [
        ("method_input_envelope_v1", "canonical_passthrough"),
        ("legacy_hte_json_v1", "legacy_to_method_input_envelope_v1"),
    ],
)
def test_content_admitted_protocols_accept_only_their_exact_normalization(
    protocol: str, normalization: str
) -> None:
    parsed = TypeAdapter(ContentAdmittedObservationalRunIntent).validate_python(
        _content_admitted_intent(protocol, normalization)
    )
    assert parsed.source_protocol == protocol
    assert parsed.normalization == normalization


@pytest.mark.parametrize(
    ("protocol", "normalization"),
    [
        ("method_input_envelope_v1", "legacy_to_method_input_envelope_v1"),
        ("legacy_hte_json_v1", "canonical_passthrough"),
    ],
)
def test_content_admitted_protocol_normalization_cross_pairs_refuse(
    protocol: str, normalization: str
) -> None:
    with pytest.raises(
        ValidationError, match="content_admitted_observational_protocol_normalization_mismatch"
    ):
        TypeAdapter(ContentAdmittedObservationalRunIntent).validate_python(
            _content_admitted_intent(protocol, normalization)
        )


def test_canonical_passthrough_must_keep_the_exact_submitted_source_ref() -> None:
    content_admitted = _content_admitted_intent()
    content_admitted["effective_input_ref"] = _ref("ir.observation_method_input", "d").model_dump(
        mode="json"
    )

    with pytest.raises(
        ValidationError, match="content_admitted_observational_passthrough_mismatch"
    ):
        TypeAdapter(ContentAdmittedObservationalRunIntent).validate_python(content_admitted)


def test_direct_selection_requires_exact_method_fqn_version_pair() -> None:
    selection = _direct_selection()
    selection["method_fqn"] = "causal.hte.forest_dr@1.1.0"
    selection["method_version"] = "1.1.0"
    assert TypeAdapter(DirectMethodExecutionSelection).validate_python(
        selection
    ).method_version == ("1.1.0")

    selection["method_version"] = "1.0.0"
    with pytest.raises(ValidationError, match="direct_method_execution_method_version_mismatch"):
        TypeAdapter(DirectMethodExecutionSelection).validate_python(selection)


def test_selection_union_keeps_direct_and_graph_result_identities_disjoint() -> None:
    direct = TypeAdapter(DirectMethodExecutionSelection).validate_python(_direct_selection())
    assert direct.selection_kind == "direct_method"
    assert direct.method_result_ref.kind.startswith("scientist.method_result.")

    graph = TypeAdapter(MethodExecutionSelection).validate_python(_graph_selection())
    assert isinstance(graph, GraphMethodExecutionSelection)
    assert graph.method_result_ref is None
    assert graph.simulation_result_ref.kind == "foundry.simulation_result"


@pytest.mark.parametrize(
    ("protocol", "normalization"),
    [
        ("method_input_envelope_v1", "legacy_to_method_input_envelope_v1"),
        ("legacy_hte_json_v1", "canonical_passthrough"),
    ],
)
def test_direct_selection_rejects_protocol_normalization_cross_pairs(
    protocol: str, normalization: str
) -> None:
    selection = _direct_selection()
    selection["source_protocol"] = protocol
    selection["normalization"] = normalization
    if protocol == "legacy_hte_json_v1":
        source = _ref("ir.observational_data", "a").model_dump(mode="json")
        selection["requested_source_ref"] = source
        selection["submitted_input_ref"] = source
        selection["limitations"] = (
            *selection["limitations"],
            "legacy_hte_json_v1_source_normalized",
        )
    with pytest.raises(
        ValidationError, match="direct_method_execution_protocol_normalization_mismatch"
    ):
        TypeAdapter(DirectMethodExecutionSelection).validate_python(selection)


def test_direct_selection_canonical_passthrough_must_preserve_source_identity() -> None:
    selection = _direct_selection()
    selection["effective_input_ref"] = _ref("ir.observation_method_input", "f").model_dump(
        mode="json"
    )

    with pytest.raises(ValidationError, match="direct_method_execution_passthrough_mismatch"):
        TypeAdapter(DirectMethodExecutionSelection).validate_python(selection)


def test_direct_selection_rejects_nonproducer_result_identity_and_target() -> None:
    for field, value in (
        ("method_result_ref", _ref("unrelated.output", "d").model_dump(mode="json")),
        ("method_evidence_ref", _ref("unrelated.evidence", "e").model_dump(mode="json")),
        ("contract_target", "polisyos.foundry.methods.catalog.other.Target"),
        ("method_fqn", "causal.hte.other@1.0.0"),
    ):
        selection = _direct_selection()
        selection[field] = value
        with pytest.raises(ValidationError):
            TypeAdapter(DirectMethodExecutionSelection).validate_python(selection)


def test_graph_projection_status_requires_exact_selected_vector() -> None:
    graph = _graph_selection()
    graph["metric_verification_status"] = "verified"
    with pytest.raises(ValidationError, match="graph_method_execution_projection_status_mismatch"):
        TypeAdapter(GraphMethodExecutionSelection).validate_python(graph)

    graph["metric_verification_status"] = "verification_missing"
    graph["method_metric_projection"] = {
        "vector_ref": _ref("scientist.policy_evaluation_vector", "d").model_dump(mode="json"),
        "verifier_revision": "1.0",
        "verifier_implementation_sha256": "sha256:" + "e" * 64,
    }
    with pytest.raises(ValidationError, match="graph_method_execution_projection_status_mismatch"):
        TypeAdapter(GraphMethodExecutionSelection).validate_python(graph)


def test_graph_selection_rejects_direct_method_result_alias() -> None:
    graph = _graph_selection()
    graph["method_result_ref"] = _ref("scientist.method_result.causal.hte", "d").model_dump(
        mode="json"
    )
    with pytest.raises(ValidationError):
        TypeAdapter(GraphMethodExecutionSelection).validate_python(graph)


def test_public_selection_rejects_unknown_fields() -> None:
    graph = _graph_selection()
    graph["observed_array"] = [1, 2, 3]
    with pytest.raises(ValidationError):
        TypeAdapter(GraphMethodExecutionSelection).validate_python(graph)


def test_run_intent_limitations_type_and_schema_preserve_three_or_four_exact_limits() -> None:
    policy = ObservationalInputResourcePolicy()
    base_payload = _requested_intent(
        method_fqn="causal.hte.forest_dr@1.0.0",
        method_version="1.0.0",
        resource_policy=policy,
        resolved_params={},
    )
    base = ObservationalRunIntent.model_validate(base_payload)
    assert len(base.limitations) == 3

    current_payload = dict(base_payload)
    current_payload["source_access_revalidation_status"] = "not_established"
    current_payload["limitations"] = (
        *base.limitations,
        "source_access_revalidation_not_established",
    )
    current = ObservationalRunIntent.model_validate(current_payload)
    assert len(current.limitations) == 4

    schema = ObservationalRunIntent.model_json_schema()["properties"]["limitations"]
    assert schema["minItems"] == 3
    assert schema["maxItems"] == 4
    assert set(schema["items"]["enum"]) == {
        "candidate_input_not_external_truth",
        "scientific_validity_not_established",
        "units_and_context_not_established",
        "source_access_revalidation_not_established",
    }

    for invalid_limits in (base.limitations[:2], (*current.limitations, current.limitations[0])):
        with pytest.raises(ValidationError):
            ObservationalRunIntent.model_validate({**base_payload, "limitations": invalid_limits})


@pytest.mark.parametrize("protocol", ["method_input_envelope_v1", "legacy_hte_json_v1"])
@pytest.mark.parametrize(
    ("status_present", "status"),
    [(False, None), (True, None), (True, "not_established")],
)
def test_requested_intent_schema_binds_protocol_status_and_exact_limitations(
    protocol: str,
    status_present: bool,
    status: str | None,
) -> None:
    """Keep generated wire constraints aligned with all requested-intent arms."""
    from jsonschema import Draft202012Validator

    policy = ObservationalInputResourcePolicy()
    payload = _requested_intent(
        method_fqn="causal.hte.forest_dr@1.0.0",
        method_version="1.0.0",
        resource_policy=policy,
        resolved_params={},
    )
    payload["protocol"] = protocol
    if protocol == "legacy_hte_json_v1":
        payload["requested_source_ref"] = _ref("ir.observational_data", "a").model_dump(mode="json")
    if status_present:
        payload["source_access_revalidation_status"] = status
    else:
        payload.pop("source_access_revalidation_status", None)
    expected_limitations = (
        "candidate_input_not_external_truth",
        "scientific_validity_not_established",
        "units_and_context_not_established",
    )
    if status == "not_established":
        expected_limitations += ("source_access_revalidation_not_established",)
    payload["limitations"] = list(expected_limitations)

    schema = ObservationalRunIntent.model_json_schema()
    schema_validator = Draft202012Validator(schema)
    assert schema_validator.is_valid(payload)
    parsed = ObservationalRunIntent.model_validate(payload)
    assert parsed.limitations == expected_limitations
    assert schema["properties"]["limitations"]["minItems"] == 3
    assert schema["properties"]["limitations"]["maxItems"] == 4

    wrong_status = dict(payload)
    wrong_status["source_access_revalidation_status"] = (
        None if status == "not_established" else "not_established"
    )
    assert not schema_validator.is_valid(wrong_status)
    with pytest.raises(ValidationError, match="observational_run_intent_limitations_invalid"):
        ObservationalRunIntent.model_validate(wrong_status)

    wrong_order = dict(payload)
    wrong_order["limitations"] = [
        expected_limitations[1],
        expected_limitations[0],
        *expected_limitations[2:],
    ]
    assert not schema_validator.is_valid(wrong_order)
    with pytest.raises(ValidationError, match="observational_run_intent_limitations_invalid"):
        ObservationalRunIntent.model_validate(wrong_order)


@pytest.mark.parametrize(
    ("schema_version", "method_fqn"),
    [
        (
            "polisyos.runtime.content_admitted_observational_run_intent.v1",
            "causal.hte.forest_dr@1.0.0",
        ),
        (
            "polisyos.runtime.content_admitted_observational_run_intent.v2",
            "causal.hte.double_ml@2.0.0",
        ),
    ],
)
@pytest.mark.parametrize(
    ("protocol", "normalization"),
    [
        ("method_input_envelope_v1", "canonical_passthrough"),
        ("legacy_hte_json_v1", "legacy_to_method_input_envelope_v1"),
    ],
)
@pytest.mark.parametrize(
    ("status_present", "status"),
    [(False, None), (True, None), (True, "not_established")],
)
def test_content_admitted_limitations_schema_and_wire_cover_all_status_arms(
    schema_version: str,
    method_fqn: str,
    protocol: str,
    normalization: str,
    status_present: bool,
    status: str | None,
) -> None:
    """Bind exact wire limits and both historical/current forms to caveat tuples."""
    import json

    from jsonschema import Draft202012Validator

    expected_limitations = (
        "candidate_input_not_external_truth",
        "scientific_validity_not_established",
        "units_and_context_not_established",
    )
    if status == "not_established":
        expected_limitations += ("source_access_revalidation_not_established",)
    if protocol == "legacy_hte_json_v1":
        expected_limitations += ("legacy_hte_json_v1_source_normalized",)
    payload = _content_admitted_intent(protocol, normalization)
    payload["schema_version"] = schema_version
    payload["method_fqn"] = method_fqn
    if status_present:
        payload["source_access_revalidation_status"] = status
    else:
        payload.pop("source_access_revalidation_status", None)
    payload["limitations"] = list(expected_limitations)
    if schema_version.endswith(".v2"):
        context = OwnedHTERequestContextV1(
            request_estimand_status="declared",
            request_estimand="average_treatment_effect",
            request_target_scope_status="declared",
            request_target_scope="selected_evaluation_rows",
            outcome_variable_status="declared",
            outcome_variable_id="outcome",
            treatment_variable_status="declared",
            treatment_variable_id="treatment",
            contrast_status="declared",
            control_value=0.0,
            treated_value=1.0,
            request_alpha_status="declared",
            requested_alpha=0.05,
            requested_guarantee_status="not_established",
            requested_guarantee=None,
        )
        payload["owned_hte_request_context"] = context.model_dump(mode="json")

    adapter = TypeAdapter(ContentAdmittedObservationalRunIntent)
    schema = adapter.json_schema()
    limitations_schema = schema["properties"]["limitations"]
    assert limitations_schema["minItems"] == 3
    assert limitations_schema["maxItems"] == 5
    assert set(limitations_schema["items"]["enum"]) == {
        "candidate_input_not_external_truth",
        "scientific_validity_not_established",
        "units_and_context_not_established",
        "source_access_revalidation_not_established",
        "legacy_hte_json_v1_source_normalized",
    }
    assert ContentAdmittedObservationalRunIntent.model_fields["limitations"].is_required()

    schema_validator = Draft202012Validator(schema)
    assert schema_validator.is_valid(payload)
    parsed = adapter.validate_python(payload)
    wire = adapter.dump_json(parsed)
    roundtrip = adapter.validate_json(wire)
    assert roundtrip.limitations == expected_limitations
    assert roundtrip.source_access_revalidation_status == status
    assert roundtrip.schema_version == schema_version
    artifact_payload = parsed.artifact_payload()
    assert schema_validator.is_valid(artifact_payload)
    artifact_roundtrip = adapter.validate_json(json.dumps(artifact_payload))
    assert artifact_roundtrip.limitations == expected_limitations

    wrong_status = dict(payload)
    wrong_status["source_access_revalidation_status"] = (
        None if status == "not_established" else "not_established"
    )
    assert not schema_validator.is_valid(wrong_status)
    with pytest.raises(
        ValidationError,
        match="content_admitted_observational_limitations_invalid",
    ):
        adapter.validate_python(wrong_status)

    wrong_order = dict(payload)
    wrong_order["limitations"] = [
        expected_limitations[1],
        expected_limitations[0],
        *expected_limitations[2:],
    ]
    assert not schema_validator.is_valid(wrong_order)
    with pytest.raises(
        ValidationError,
        match="content_admitted_observational_limitations_invalid",
    ):
        adapter.validate_python(wrong_order)

    wrong_in_range = dict(payload)
    wrong_limitations = list(expected_limitations)
    wrong_limitations[0] = "legacy_hte_json_v1_source_normalized"
    wrong_in_range["limitations"] = wrong_limitations
    assert not schema_validator.is_valid(wrong_in_range)
    with pytest.raises(
        ValidationError,
        match="content_admitted_observational_limitations_invalid",
    ):
        adapter.validate_python(wrong_in_range)

    too_short = dict(payload, limitations=list(expected_limitations[:2]))
    six_items = list(expected_limitations) + [expected_limitations[0]] * (
        6 - len(expected_limitations)
    )
    too_long = dict(payload, limitations=six_items)
    assert not schema_validator.is_valid(too_short)
    assert not schema_validator.is_valid(too_long)
    with pytest.raises(ValidationError):
        adapter.validate_python(too_short)
    with pytest.raises(ValidationError):
        adapter.validate_python(too_long)


def _search_bound_v3_intent_payload() -> tuple[
    dict[str, object], SearchUncertaintyTaskAdmissionSnapshot
]:
    """Build a strict v3 payload whose Search proof matches every selected request pin."""
    method_fqn = "causal.hte.double_ml@2.0.0"
    target = "polisyos.foundry.methods.catalog.causal.protocols.HTEObservationalData"
    source_ref = _ref("ir.observation_method_input", "a")
    binding_ref = _ref("scientist.search.uncertainty_task_binding", "1")
    context = OwnedHTERequestContextV1(
        request_estimand_status="declared",
        request_estimand="average_treatment_effect",
        request_target_scope_status="declared",
        request_target_scope="selected_evaluation_rows",
        outcome_variable_status="declared",
        outcome_variable_id="outcome",
        treatment_variable_status="declared",
        treatment_variable_id="treatment",
        contrast_status="declared",
        control_value=0.0,
        treated_value=1.0,
        request_alpha_status="declared",
        requested_alpha=0.05,
        requested_guarantee_status="not_established",
        requested_guarantee=None,
        search_uncertainty_task_binding_ref=SelectedArtifactRef.model_validate(
            binding_ref.model_dump(mode="json"), strict=True
        ),
    )
    params: dict[str, object] = {"alpha": 0.05}
    params_bytes = json.dumps(
        params, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")

    def owner_ref(kind: str, marker: str) -> ArtifactRef:
        return _ref(kind, marker)

    snapshot = SearchUncertaintyTaskAdmissionSnapshot(
        binding_ref=binding_ref,
        binding_content_sha256=binding_ref.artifact_id.hex,
        ticket_id="ticket-v3-contract",
        ticket_generation=1,
        owner_revision=2,
        projection_revision=2,
        projection_ref=owner_ref("scientist.search.uncertainty_ticket_projection", "2"),
        task_admission_ref=owner_ref("scientist.search.uncertainty_task_admission", "3"),
        task_epoch_ref=owner_ref("scientist.search.uncertainty_task_epoch", "4"),
        owner_context_ref=owner_ref("scientist.search.uncertainty_owner_task_context", "5"),
        basis_ref=owner_ref("scientist.search.uncertainty_basis", "6"),
        dependency_inventory_ref=owner_ref("scientist.search.uncertainty_input_inventory", "7"),
        dependency_inventory_sha256="8" * 64,
        source_projection_ref=owner_ref("scientist.search.uncertainty_ticket_projection", "9"),
        selected_method_fqn=method_fqn,
        selected_method_abi_version="2.0.0",
        selected_method_abi_digest="a" * 64,
        selected_method_params=params,
        selected_method_params_sha256=hashlib.sha256(params_bytes).hexdigest(),
        selected_method_seed=0,
        selected_inference_profile_id="econml.dml.point_only@2.0",
        selected_method_input_ref=source_ref,
        selected_method_input_content_sha256=source_ref.artifact_id.hex,
        tenant_id="tenant-1",
        cell_id="cell-1",
        resolved_at=datetime(2026, 10, 25, tzinfo=UTC),
    )
    policy = ObservationalInputResourcePolicy(
        schema_version="polisyos.runtime.observational_input_resource_policy.v5",
        revision="r5",
        method_contract_target=target,
        method_execution_wait_policy=BoundedLivenessResolution(
            producer_key="runtime.observational_method_execution",
            deadline_s=60.0,
            retry_ceiling=0,
            config_id="runtime-test",
            config_version="1",
            owner="runtime-test",
            feature_flag="runtime-test",
        ),
        required_estimator_n_jobs=None,
        method_fqn=method_fqn,
        method_profile_id="econml.dml.point_only@2.0",
        execution_scope="producer_scoped_joblib_parallelism_one",
        max_jobs=1,
    )
    payload = _requested_intent(
        method_fqn=method_fqn,
        method_version="2.0.0",
        resource_policy=policy,
        resolved_params=params,
    )
    payload.update(
        {
            "schema_version": "polisyos.runtime.observational_run_intent.v3",
            "created_at": datetime(2026, 10, 25, tzinfo=UTC),
            "owned_hte_request_context": context.model_dump(mode="json"),
            "search_binding_admission": snapshot.model_dump(mode="python"),
            "search_binding_tenant_id": "tenant-1",
            "search_binding_cell_id": "cell-1",
            "resource_policy_ref": _ref(
                "runtime.observational_input_resource_policy", "f"
            ).model_dump(mode="json"),
            "contract_target_id": "foundry.causal.hte_observational_data.v1",
            "contract_target_fqn": target,
            "source_access_revalidation_status": "not_established",
            "limitations": [
                "candidate_input_not_external_truth",
                "scientific_validity_not_established",
                "units_and_context_not_established",
                "source_access_revalidation_not_established",
            ],
        }
    )
    return payload, snapshot


def test_search_bound_intent_v3_is_strict_and_v1_v2_history_bytes_stay_pinned() -> None:
    """Bind new queued proof to exact request pins without rewriting v1/v2 history."""
    payload, snapshot = _search_bound_v3_intent_payload()
    parsed = ObservationalRunIntent.model_validate(payload)
    assert parsed.schema_version == "polisyos.runtime.observational_run_intent.v3"
    assert parsed.search_binding_admission == snapshot
    assert parsed.search_binding_tenant_id == snapshot.tenant_id
    assert parsed.search_binding_cell_id == snapshot.cell_id
    assert parsed.artifact_payload()["search_binding_admission"] == snapshot.model_dump(mode="json")

    missing_snapshot = dict(payload)
    missing_snapshot.pop("search_binding_admission")
    with pytest.raises(ValidationError):
        ObservationalRunIntent.model_validate(missing_snapshot)

    wrong_input = dict(payload)
    wrong_snapshot = dict(wrong_input["search_binding_admission"])
    wrong_snapshot["selected_method_input_ref"] = _ref(
        "ir.observation_method_input", "d"
    ).model_dump(mode="json")
    wrong_snapshot["selected_method_input_content_sha256"] = "d" * 64
    wrong_input["search_binding_admission"] = wrong_snapshot
    with pytest.raises(ValidationError):
        ObservationalRunIntent.model_validate(wrong_input)

    wrong_scope = dict(payload)
    wrong_scope["search_binding_cell_id"] = "another-cell"
    with pytest.raises(ValidationError):
        ObservationalRunIntent.model_validate(wrong_scope)

    wrong_abi = dict(payload)
    wrong_abi["method_abi_digest"] = "b" * 64
    with pytest.raises(ValidationError):
        ObservationalRunIntent.model_validate(wrong_abi)

    legacy_v1_payload = _requested_intent(
        method_fqn="causal.hte.forest_dr@1.0.0",
        method_version="1.0.0",
        resource_policy=ObservationalInputResourcePolicy(),
        resolved_params={},
    )
    legacy_v1_payload["created_at"] = datetime(2026, 10, 25, tzinfo=UTC)
    legacy_v1 = ObservationalRunIntent.model_validate(legacy_v1_payload)
    assert (
        legacy_v1.selection_digest()
        == "3b54fc70f3607c8bfb623485f3db94eaff0bda38d606d9a5c870d397c2864221"
    )
    assert "search_binding_admission" not in legacy_v1.artifact_payload()

    legacy_v2 = dict(payload)
    legacy_v2["schema_version"] = "polisyos.runtime.observational_run_intent.v2"
    legacy_v2.pop("search_binding_admission")
    legacy_v2_intent = ObservationalRunIntent.model_validate(legacy_v2)
    assert (
        legacy_v2_intent.selection_digest()
        == "f62f70c109a6d37af60dbb9032143015156c87570fa02915799a99f101047452"
    )
    assert "search_binding_admission" not in legacy_v2_intent.artifact_payload()


def test_search_bound_content_admission_v3_keeps_the_same_post_snapshot() -> None:
    """The worker's persisted content artifact carries the selected POST proof."""
    payload, snapshot = _search_bound_v3_intent_payload()
    requested = ObservationalRunIntent.model_validate(payload)
    content = _content_admitted_intent()
    content.update(
        {
            "schema_version": "polisyos.runtime.content_admitted_observational_run_intent.v3",
            "method_fqn": requested.method_fqn,
            "requested_intent_ref": _ref("runtime.observational_run_intent", "b").model_dump(
                mode="json"
            ),
            "selection_digest": requested.selection_digest(),
            "owned_hte_request_context": requested.owned_hte_request_context.model_dump(
                mode="json"
            ),
            "search_binding_admission": snapshot.model_dump(mode="python"),
            "search_binding_tenant_id": snapshot.tenant_id,
            "search_binding_cell_id": snapshot.cell_id,
            "source_access_revalidation_status": "not_established",
            "limitations": [
                "candidate_input_not_external_truth",
                "scientific_validity_not_established",
                "units_and_context_not_established",
                "source_access_revalidation_not_established",
            ],
        }
    )
    admitted = ContentAdmittedObservationalRunIntent.model_validate(content)
    assert admitted.search_binding_admission == snapshot
    assert admitted.method_fqn == requested.method_fqn

    wrong_input = dict(content)
    wrong_snapshot = dict(wrong_input["search_binding_admission"])
    wrong_snapshot["selected_method_input_ref"] = _ref(
        "ir.observation_method_input", "d"
    ).model_dump(mode="json")
    wrong_snapshot["selected_method_input_content_sha256"] = "d" * 64
    wrong_input["search_binding_admission"] = wrong_snapshot
    with pytest.raises(ValidationError):
        ContentAdmittedObservationalRunIntent.model_validate(wrong_input)


def test_request_only_intent_reader_accepts_v3_and_pair_reader_rejects_mixed_version(
    tmp_path: Path,
) -> None:
    """Exercise the bounded request-only reader and retain strict pair versioning."""
    from polisyos.core.artifacts import CoreJsonReadLimits, FileSystemCAS, PutOptions, SchemaInfo
    from polisyos.core.canon import CanonSpec
    from polisyos.core.contracts.runtime import _expected_content_admitted_limitations
    from polisyos.runtime.http.services.control.owned_attempt_anchor import (
        _owner_request_context,
        _read_intents,
        _read_requested_intent,
    )

    requested_payload, snapshot = _search_bound_v3_intent_payload()
    requested = ObservationalRunIntent.model_validate(requested_payload)
    store = FileSystemCAS(tmp_path / "cas")
    read_limits = CoreJsonReadLimits(
        max_bytes=1_000_000,
        max_depth=128,
        max_elements=100_000,
        max_manifest_bytes=100_000,
    )

    class _SelectedIntentReader:
        def _observational_read_limits(self) -> CoreJsonReadLimits:
            return read_limits

        def _require_owned_attempt_anchor_bounded_store(
            self, *, limits: CoreJsonReadLimits
        ) -> FileSystemCAS:
            assert limits == read_limits
            return store

    service = _SelectedIntentReader()

    def put_intent(value: BaseModel, *, kind: str, name: str, version: str) -> ArtifactRef:
        ref = store.put_json(
            value.artifact_payload(),
            PutOptions(
                kind=kind,
                media_type="application/json",
                schema=SchemaInfo(name=name, version=version),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        return ArtifactRef.model_validate(ref, strict=True)

    requested_ref = put_intent(
        requested,
        kind="runtime.observational_run_intent",
        name="polisyos.runtime.ObservationalRunIntent",
        version="3.0",
    )
    loaded_request = _read_requested_intent(
        service=service,
        requested_intent_ref=requested_ref,
    )
    assert loaded_request == requested
    assert _owner_request_context(loaded_request) == requested.owned_hte_request_context

    content_payload = _content_admitted_intent()
    content_payload.update(
        {
            "schema_version": "polisyos.runtime.content_admitted_observational_run_intent.v3",
            "job_id": requested.job_id,
            "run_id": requested.run_id,
            "requested_intent_ref": requested_ref.model_dump(mode="json"),
            "requested_source_ref": requested.requested_source_ref.model_dump(mode="json"),
            "source_manifest_sha256": requested.source_manifest_sha256,
            "resource_policy_ref": requested.resource_policy_ref.model_dump(mode="json"),
            "submitted_input_ref": requested.requested_source_ref.model_dump(mode="json"),
            "effective_input_ref": requested.requested_source_ref.model_dump(mode="json"),
            "contract_target_id": requested.contract_target_id,
            "contract_target": requested.contract_target_fqn,
            "selection_digest": requested.selection_digest(),
            "method_fqn": requested.method_fqn,
            "owned_hte_request_context": requested.owned_hte_request_context.model_dump(
                mode="json"
            ),
            "search_binding_admission": snapshot.model_dump(mode="python"),
            "search_binding_tenant_id": snapshot.tenant_id,
            "search_binding_cell_id": snapshot.cell_id,
            "source_access_revalidation_status": "not_established",
            "source_protocol": requested.protocol,
            "normalization": "canonical_passthrough",
            "limitations": list(
                _expected_content_admitted_limitations(
                    requested.protocol,
                    source_access_revalidation_status="not_established",
                )
            ),
            "source_governance": requested.source_governance.model_dump(mode="json"),
            "source_tenant_context": (
                requested.source_tenant_context.model_dump(mode="json")
                if requested.source_tenant_context is not None
                else None
            ),
            "resource_policy_digest": requested.resource_policy_digest,
        }
    )
    admitted = ContentAdmittedObservationalRunIntent.model_validate(content_payload)
    admitted_ref = put_intent(
        admitted,
        kind="runtime.content_admitted_observational_run_intent",
        name="polisyos.runtime.ContentAdmittedObservationalRunIntent",
        version="3.0",
    )
    loaded_request_pair, loaded_admitted_pair = _read_intents(
        service=service,
        requested_intent_ref=requested_ref,
        content_admitted_ref=admitted_ref,
    )
    assert loaded_request_pair.search_binding_admission == snapshot
    assert loaded_admitted_pair.search_binding_admission == snapshot

    changed_snapshot = snapshot.model_copy(
        update={"resolved_at": snapshot.resolved_at + timedelta(seconds=1)}
    )
    changed_snapshot_payload = admitted.model_dump(mode="python")
    changed_snapshot_payload["search_binding_admission"] = changed_snapshot.model_dump(
        mode="python"
    )
    changed_snapshot_admitted = ContentAdmittedObservationalRunIntent.model_validate(
        changed_snapshot_payload, strict=True
    )
    changed_snapshot_ref = put_intent(
        changed_snapshot_admitted,
        kind="runtime.content_admitted_observational_run_intent",
        name="polisyos.runtime.ContentAdmittedObservationalRunIntent",
        version="3.0",
    )
    with pytest.raises(
        ValueError,
        match="owned_attempt_request_and_admission_search_snapshot_mismatch",
    ):
        _read_intents(
            service=service,
            requested_intent_ref=requested_ref,
            content_admitted_ref=changed_snapshot_ref,
        )

    mixed_payload = admitted.model_dump(mode="python")
    mixed_payload["schema_version"] = (
        "polisyos.runtime.content_admitted_observational_run_intent.v2"
    )
    mixed_admitted = ContentAdmittedObservationalRunIntent.model_validate(
        mixed_payload,
        strict=True,
    )
    mixed_ref = put_intent(
        mixed_admitted,
        kind="runtime.content_admitted_observational_run_intent",
        name="polisyos.runtime.ContentAdmittedObservationalRunIntent",
        version="2.0",
    )
    with pytest.raises(
        ValueError,
        match="owned_attempt_request_and_admission_schema_version_mismatch",
    ):
        _read_intents(
            service=service,
            requested_intent_ref=requested_ref,
            content_admitted_ref=mixed_ref,
        )
