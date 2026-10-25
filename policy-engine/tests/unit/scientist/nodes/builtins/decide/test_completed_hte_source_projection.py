from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace
from typing import Any

import pytest

from polisyos.core.contracts.owned_attempt_anchor import OwnedAttemptAnchorProjectionAssociation
from polisyos.core.contracts.runtime import (
    CompletedMethodHTESource,
    DirectMethodExecutionHTESummary,
)
from polisyos.scientist.nodes.builtins.decide.decision_packet import basis_sections, builder

_SOURCE_RUN = "source-run-controlled"
_SOURCE_JOB = "source-job-controlled"
_EVENT_ID = 7
_EVENT_DIGEST = "sha256:" + "9" * 64
_NOW = "2026-10-23T00:00:00+00:00"


def _ref(index: int, kind: str) -> dict[str, str]:
    digit = str(index)
    return {
        "artifact_id": "sha256:" + digit * 64,
        "kind": kind,
        "media_type": "application/json",
        "manifest_profile_sha256": "sha256:" + str((index + 1) % 10) * 64,
    }


def _selected_source() -> CompletedMethodHTESource:
    method = "causal.hte.double_ml@2.0.0"
    profile = "econml.dml.point_only@2.0"
    owner_policy_ref = _ref(1, "runtime.observational_input_resource_policy")
    resource_evidence = {
        "owner_policy_ref": owner_policy_ref,
        "owner_policy_digest": "f" * 64,
        "owner_policy_schema_version": ("polisyos.runtime.observational_input_resource_policy.v5"),
        "owner_policy_revision": "r5",
        "owner_policy_method_fqn": method,
        "owner_policy_method_profile_id": profile,
        "owner_policy_execution_scope": "producer_scoped_joblib_parallelism_one",
        "owner_policy_max_jobs": 1,
        "owner_policy_required_estimator_n_jobs": None,
        "execution_status": "returned",
        "estimator_observation_status": "not_applicable",
        "joblib_observation_status": "recomputed",
        "joblib_profile_id": "joblib.parallel_config.current_thread@1.0",
        "joblib_profile_revision": "1.0",
        "joblib_implementation": "joblib.parallel_config",
        "joblib_implementation_version": "1.5.3",
        "joblib_scope": "current_thread_joblib",
        "joblib_max_jobs": 1,
        "joblib_started": True,
        "joblib_finished": True,
        "joblib_exit_status": "returned",
        "joblib_entry_effective_jobs": 1,
        "joblib_entry_backend_fqn": "joblib._parallel_backends.LokyBackend",
        "joblib_entry_config_sha256": "a" * 64,
        "joblib_entry_implementation_version": "1.5.3",
        "joblib_exit_effective_jobs": 1,
        "joblib_exit_backend_fqn": "joblib._parallel_backends.LokyBackend",
        "joblib_exit_config_sha256": "a" * 64,
        "joblib_exit_implementation_version": "1.5.3",
    }
    target_relation = {
        "requested_scope_status": "declared",
        "requested_scope": "selected_evaluation_rows",
        "requested_guarantee_status": "declared",
        "requested_guarantee": "candidate_point",
        "computed_scope_status": "recomputed",
        "computed_scope": "selected_evaluation_rows",
        "computed_guarantee_status": "computed",
        "computed_guarantee": "candidate_point",
        "source_content_status": "content_bound",
        "row_order_status": "recomputed",
        "contrast_status": "recomputed",
        "estimand_status": "not_established",
        "alpha_status": "not_applicable",
        "profile_status": "point_only",
        "scope_disposition": "satisfied",
        "guarantee_disposition": "satisfied",
        "overall_disposition": "not_established",
    }
    summary_payload = {
        "kind": "point_estimate",
        "method_fqn": method,
        "method_abi_digest": "b" * 64,
        "method_profile_id": profile,
        "resolved_params_sha256": "c" * 64,
        "owned_attempt_anchor_ref": _ref(2, "runtime.owned_attempt_anchor"),
        "hte_outcome_ref": _ref(3, "ir.hte_outcome"),
        "point_result_ref": _ref(4, "ir.hte_point_result"),
        "method_result_ref": _ref(5, "scientist.method_result.causal.hte"),
        "method_evidence_ref": _ref(6, "scientist.method_evidence"),
        "source_data_ref": _ref(7, "ir.observation_method_input"),
        "materialization_binding_ref": _ref(
            8, "foundry.hte.physical_source_materialization_binding"
        ),
        "selected_rows_status": "recomputed",
        "n_selected_rows": 4,
        "selected_rows_sha256": "d" * 64,
        "selected_row_order_sha256": "e" * 64,
        "selected_x_sha256": "f" * 64,
        "computed_estimand_status": "recomputed",
        "computed_estimand": "mean_effect_over_selected_x",
        "computed_target_scope_status": "recomputed",
        "computed_target_scope": "selected_evaluation_rows",
        "measure_unit_status": "not_established",
        "request_estimand_status": "declared",
        "request_estimand": "mean_effect_over_selected_x",
        "request_target_scope_status": "declared",
        "request_target_scope": "selected_evaluation_rows",
        "outcome_variable_status": "declared",
        "outcome_variable_id": "outcome.effect",
        "treatment_variable_status": "declared",
        "treatment_variable_id": "treatment.policy",
        "request_contrast_status": "declared",
        "control_value": 0.0,
        "treated_value": 1.0,
        "request_alpha_status": "declared",
        "requested_alpha": 0.05,
        "requested_guarantee_status": "declared",
        "requested_guarantee": "candidate_point",
        "computed_guarantee_status": "computed",
        "computed_guarantee": "candidate_point",
        "target_relation": target_relation,
        "inference_status": "not_requested",
        "inference_reason": "inference_not_requested",
        "point_estimate": 0.25,
        "refusal_reason": None,
        "refusal_diagnostic_code": None,
        "resource_evidence": resource_evidence,
        "limitations": ["target_population_not_established_by_this_fit"],
    }
    summary = DirectMethodExecutionHTESummary.model_validate_json(
        json.dumps(summary_payload),
        strict=True,
    )
    summary_wire = summary.model_dump(mode="json")
    summary_digest = hashlib.sha256(
        json.dumps(
            summary_wire,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    association_payload = {
        "verified_at": _NOW,
        "anchor_ref": summary_wire["owned_attempt_anchor_ref"],
        "outcome_ref": summary_wire["hte_outcome_ref"],
        "outcome_kind": "point_estimate",
        "selected_summary_sha256": summary_digest,
        "source_data_ref": summary_wire["source_data_ref"],
        "materialization_binding_ref": summary_wire["materialization_binding_ref"],
        "resource_policy_ref": owner_policy_ref,
        "method_result_ref": summary_wire["method_result_ref"],
        "method_evidence_ref": summary_wire["method_evidence_ref"],
        "point_result_ref": summary_wire["point_result_ref"],
        "job_completed_event": {
            "event_id": _EVENT_ID,
            "job_id": _SOURCE_JOB,
            "event_type": "job_completed",
            "payload_sha256": _EVENT_DIGEST,
            "created_at": _NOW,
        },
        "job_id": _SOURCE_JOB,
        "run_id": _SOURCE_RUN,
        "tenant_id": "controlled-tenant",
        "cell_id": "controlled-cell",
        "attempt": 1,
    }
    association = OwnedAttemptAnchorProjectionAssociation.model_validate_json(
        json.dumps(association_payload),
        strict=True,
    )
    return CompletedMethodHTESource(
        source_run_id=_SOURCE_RUN,
        source_job_id=_SOURCE_JOB,
        source_attempt=1,
        completed_event_id=_EVENT_ID,
        completed_event_payload_sha256=_EVENT_DIGEST,
        summary=summary,
        association=association,
    )


class _Owner:
    def __init__(self, source: CompletedMethodHTESource) -> None:
        self.source = source
        self.calls: list[tuple[str, str, str | None]] = []

    def resolve_completed_method_hte_selection(
        self, *, source_run_id: str, tenant_id: str, cell_id: str | None
    ) -> CompletedMethodHTESource:
        self.calls.append((source_run_id, tenant_id, cell_id))
        return self.source


class _ManifestReader:
    def __init__(self) -> None:
        self.resolved: set[tuple[str, str, str, str | None]] = set()

    def get_manifest(self, ref: Any) -> object:
        self.resolved.add(
            (str(ref.artifact_id), ref.kind, ref.media_type, ref.manifest_profile_sha256)
        )
        return object()


def _context(source: CompletedMethodHTESource) -> tuple[SimpleNamespace, _ManifestReader]:
    reader = _ManifestReader()
    owner = _Owner(source)
    context = SimpleNamespace(
        run=SimpleNamespace(tenant_id="controlled-tenant", cell_id="controlled-cell"),
        completed_method_hte_selection_owner=owner,
        store=reader,
    )
    return context, reader


def test_selected_completed_source_survives_builder_and_strict_packet_consumer() -> None:
    """Keep required nullable owner fields through the packet's strict reader."""
    source = _selected_source()
    context, manifest_reader = _context(source)

    projected = builder._build_completed_hte_source_section(
        context,
        source_run_id=_SOURCE_RUN,
        request_status="requested",
    )

    assert projected["selection_status"] == "selected"
    owner_source = projected["owner_source"]
    assert isinstance(owner_source, dict)
    summary_wire = owner_source["summary"]
    assert isinstance(summary_wire, dict)
    assert summary_wire["refusal_reason"] is None
    assert summary_wire["refusal_diagnostic_code"] is None
    assert summary_wire["resource_evidence"]["owner_policy_required_estimator_n_jobs"] is None

    packet_payload: dict[str, object] = {
        "hte": summary_wire,
        "_completed_hte_source": projected,
    }
    dependencies, basis = basis_sections._completed_hte_basis_dependencies(
        context,
        packet_payload,
    )

    assert basis["completed_hte_source_status"] == "selected"
    assert basis["completed_hte_source_run_id"] == _SOURCE_RUN
    assert basis["completed_hte_currentness_status"] == "reconciled_at_completed_event"
    dependency_keys = {item.key for item in dependencies}
    assert f"hte_completed_source_run:{_SOURCE_RUN}" in dependency_keys
    assert (
        f"hte_completed_source_event:{_SOURCE_JOB}:{_EVENT_ID}:{_EVENT_DIGEST}" in dependency_keys
    )
    assert any(key.startswith("hte_completed_source_artifact:") for key in dependency_keys)
    owner = context.completed_method_hte_selection_owner
    assert owner.calls == [(_SOURCE_RUN, "controlled-tenant", "controlled-cell")]
    expected_refs = {
        (
            str(ref.artifact_id),
            ref.kind,
            ref.media_type,
            ref.manifest_profile_sha256,
        )
        for ref in (
            source.summary.owned_attempt_anchor_ref,
            source.summary.hte_outcome_ref,
            source.summary.point_result_ref,
            source.summary.method_result_ref,
            source.summary.method_evidence_ref,
            source.summary.source_data_ref,
            source.summary.materialization_binding_ref,
            source.summary.resource_evidence.owner_policy_ref,
        )
        if ref is not None
    }
    assert manifest_reader.resolved == expected_refs
    expected_artifact_dependencies = {
        f"hte_completed_source_artifact:{artifact_id}:{profile}"
        for artifact_id, _kind, _media_type, profile in expected_refs
        if profile is not None
    }
    assert expected_artifact_dependencies <= dependency_keys
    assert len(dependency_keys) == len(expected_refs) + 2


@pytest.mark.parametrize(
    "path",
    [
        pytest.param(("refusal_reason",), id="top_level_refusal_reason"),
        pytest.param(
            ("refusal_diagnostic_code",),
            id="top_level_refusal_diagnostic_code",
        ),
        pytest.param(
            ("resource_evidence", "owner_policy_required_estimator_n_jobs"),
            id="nested_resource_policy_n_jobs",
        ),
    ],
)
def test_selected_markers_do_not_replace_required_nullable_summary_fields(
    path: tuple[str, ...],
) -> None:
    """A removal control must fail closed even when selection markers remain."""
    source = _selected_source()
    context, _ = _context(source)
    projected = builder._build_completed_hte_source_section(
        context,
        source_run_id=_SOURCE_RUN,
        request_status="requested",
    )
    assert projected["selection_status"] == "selected"

    owner_source = projected["owner_source"]
    assert isinstance(owner_source, dict)
    summary_wire = source.summary.model_dump(mode="json")
    cursor: dict[str, Any] = summary_wire
    for key in path[:-1]:
        cursor = cursor[key]
    del cursor[path[-1]]
    owner_source["summary"] = summary_wire

    packet_payload: dict[str, object] = {
        "hte": summary_wire,
        "_completed_hte_source": projected,
    }
    dependencies, basis = basis_sections._completed_hte_basis_dependencies(
        context,
        packet_payload,
    )

    assert not dependencies
    assert basis["completed_hte_source_status"] == "verification_missing"
    assert basis["completed_hte_limitation_code"] == (
        "completed_hte_dependency_basis_not_established"
    )
    assert packet_payload["hte"] is None
    degraded = packet_payload["degraded_paths"]
    assert any(
        item["reason"] == "completed_hte_dependency_basis_not_established" for item in degraded
    )
