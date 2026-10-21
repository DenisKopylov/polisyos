"""Semantic contracts for selected observational method requests and run projections."""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts.bounded_liveness import BoundedLivenessResolution
from polisyos.core.contracts.control import (
    _OBSERVATIONAL_INPUT_CONSUMED_REQUEST_FIELDS,
    WorkflowRunRequest,
)
from polisyos.core.contracts.owned_attempt_anchor import OwnedHTERequestContextV1
from polisyos.core.contracts.runtime import (
    ContentAdmittedObservationalRunIntent,
    DirectMethodExecutionSelection,
    GraphMethodExecutionSelection,
    ObservationalInputResourcePolicy,
    ObservationalRunIntent,
    RunDetails,
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
        {
            "schema_version": "polisyos.runtime.observational_input_resource_policy.v2",
            "revision": "r2",
            "method_contract_target": (
                "polisyos.foundry.methods.catalog.causal.protocols.HTEObservationalData"
            ),
            "required_estimator_n_jobs": True,
        },
        {"revision": "r1", "required_estimator_n_jobs": 1},
    ):
        with pytest.raises(ValidationError):
            ObservationalInputResourcePolicy.model_validate(invalid)


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
        ({"n_jobs": 1}, "causal.hte.forest_dr@1.0.0", "1.0.0"),
    ):
        invalid = _requested_intent(
            method_fqn=fqn,
            method_version=version,
            resource_policy=serial,
            resolved_params=params,
        )
        with pytest.raises(ValidationError):
            ObservationalRunIntent.model_validate(invalid)


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

    graph = TypeAdapter(GraphMethodExecutionSelection).validate_python(_graph_selection())
    details = RunDetails.model_validate(
        {
            "run_id": "run-1",
            "source_kind": "core_run",
            "status": "candidate",
            "method_execution_selection": graph.model_dump(mode="json"),
        }
    )
    assert isinstance(details.method_execution_selection, GraphMethodExecutionSelection)
    assert details.method_execution_selection.method_result_ref is None
    assert details.method_execution_selection.simulation_result_ref.kind == (
        "foundry.simulation_result"
    )


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
