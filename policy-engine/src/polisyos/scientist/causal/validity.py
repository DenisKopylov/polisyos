"""Helpers for causal validity checks and bundle persistence.

This module keeps auxiliary causal-validity diagnostics out of the main node
body so builtin orchestration can stay readable. All checks are best-effort and
non-blocking: when optional inputs are missing, the bundle records a typed
``skipped`` status instead of failing the main causal estimate.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any

import numpy as np

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.foundry.methods.catalog.causal.pag_completion import (
    apply_pag_orientation_rules,
    cpdag_to_pag,
    validate_pag,
)
from polisyos.foundry.methods.causal import (
    GraphCausalData,
    GraphCausalDataV1,
    HTEObservationalData,
    PanelObservationalData,
    RDDObservationalData,
)
from polisyos.ir.analytics.causal import CausalEffectReport, CausalMethod
from polisyos.ir.analytics.causal_graph import (
    CausalGraphModel,
    GraphType,
    load_causal_graph_model,
    persist_causal_graph_model,
)
from polisyos.ir.refs import CausalGraphModelRef
from polisyos.scientist.claims.ledger import persist_claim_ledger
from polisyos.scientist.claims.projections import project_causal_validity_bundle_claims
from polisyos.scientist.compute.job_spec import JobResult, JobSpec
from polisyos.scientist.compute.runner import run_job
from polisyos.scientist.frontier_runtime import (
    FrontierRuntimeConfig,
    build_frontier_runtime_report,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_LITERATURE_PRIOR_GRAPH_REF,
    ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF,
)

if TYPE_CHECKING:
    from polisyos.scientist.engine.context import ExecutionContext
    from polisyos.scientist.engine.state import ExperimentState

_ICP_METHOD_FQN = "causal.diagnostics.invariance.icp_invariance@1.0.0"
_PROXIMAL_METHOD_FQN = "causal.proximal.proximal_bridge@1.0.0"
_RECOVERABILITY_METHOD_FQN = "causal.missing_data.recoverability_test@1.0.0"
_ORDERED_RECOVERY_METHOD_FQN = "causal.missing_data.ordered_recovery@1.0.0"
_SCHEMA_NAME = "polisyos.scientist.CausalValidityBundle"
_SCHEMA_VERSION = "1.0"
_GRAPH_REF_KEYS: tuple[str, ...] = (
    ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF,
    ARTIFACT_LITERATURE_PRIOR_GRAPH_REF,
)


def persist_causal_validity_bundle(
    *,
    ctx: ExecutionContext,
    state: ExperimentState,
    report: CausalEffectReport,
    method_fqn: str,
    method_params: Mapping[str, Any],
    observational_data: (
        PanelObservationalData
        | RDDObservationalData
        | HTEObservationalData
        | GraphCausalData
        | GraphCausalDataV1
    ),
    seed: int,
    sensitivity_ref: ArtifactRef | None,
    sensitivity_auto: Mapping[str, Any],
    inputs: Sequence[InputRef],
) -> ArtifactRef | None:
    """Persist a best-effort causal-validity bundle for the latest estimate."""

    settings = _extract_validity_settings(state=state, observational_data=observational_data)
    if not _setting_bool(settings, "enabled", default=True):
        return None

    bundle_inputs = list(inputs)
    graph_data = _coerce_graph_validity_data(
        observational_data=observational_data,
        settings=settings,
    )
    confidence = _build_confidence_surface(
        report=report,
        method_fqn=method_fqn,
        method_params=method_params,
    )
    checks: dict[str, dict[str, Any]] = {
        "sensitivity": _build_sensitivity_check(
            sensitivity_ref=sensitivity_ref,
            sensitivity_auto=sensitivity_auto,
        ),
        "spatial_interference": _build_spatial_interference_check(
            report=report,
            method_fqn=method_fqn,
            method_params=method_params,
            observational_data=observational_data,
        ),
        "icp_invariance": _run_icp_check(
            ctx=ctx,
            seed=seed,
            graph_data=graph_data,
            settings=settings,
            bundle_inputs=bundle_inputs,
        ),
        "proximal_bridge": _run_proximal_check(
            ctx=ctx,
            seed=seed,
            observational_data=observational_data,
            settings=settings,
            bundle_inputs=bundle_inputs,
        ),
        "recoverability": _run_recoverability_check(
            ctx=ctx,
            state=state,
            seed=seed,
            settings=settings,
            bundle_inputs=bundle_inputs,
        ),
        "pag_refinement": _run_pag_refinement_check(
            ctx=ctx,
            state=state,
            settings=settings,
            bundle_inputs=bundle_inputs,
        ),
    }

    warnings = _collect_bundle_warnings(checks)
    frontier_payload = state.params.get("frontier_runtime")
    frontier_config = (
        FrontierRuntimeConfig.model_validate(frontier_payload)
        if isinstance(frontier_payload, Mapping)
        else FrontierRuntimeConfig(
            enable_proximal_causal=_setting_bool(settings, "enable_proximal", default=True),
        )
    )
    frontier_report = build_frontier_runtime_report(frontier_config)
    payload = {
        "schema_version": _SCHEMA_VERSION,
        "base_method_fqn": method_fqn,
        "base_method": report.method.value,
        "base_status": report.status.value,
        "confidence": confidence,
        "checks": checks,
        "capability_matrix": _build_capability_matrix(checks=checks),
        "experimental_methods": [
            {
                "name": capability.capability_id,
                "status": capability.status.value,
                "method_fqns": list(capability.method_fqns),
                "offline_validation_ref": capability.offline_validation_ref,
                "benchmark_pack_ref": capability.benchmark_pack_ref,
            }
            for capability in frontier_report.capabilities
            if capability.status.value != "disabled"
        ],
        "frontier_runtime": frontier_report.model_dump(mode="python"),
        "warnings": warnings,
    }
    claim_source_refs = [ref for ref in (sensitivity_ref,) if ref is not None]
    claim_ledger = project_causal_validity_bundle_claims(
        payload,
        run_id=state.run_id,
        source_artifact_refs=claim_source_refs,
    )
    claims_ref = persist_claim_ledger(
        ctx.store,
        claim_ledger,
        inputs=bundle_inputs or None,
    )
    payload["claims_ref"] = str(claims_ref.artifact_id)
    return ctx.store.put_json(
        payload,
        PutOptions(
            kind="scientist.causal_validity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name=_SCHEMA_NAME, version=_SCHEMA_VERSION),
            inputs=bundle_inputs or None,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def _extract_validity_settings(
    *,
    state: ExperimentState,
    observational_data: (
        PanelObservationalData
        | RDDObservationalData
        | HTEObservationalData
        | GraphCausalData
        | GraphCausalDataV1
    ),
) -> dict[str, Any]:
    settings: dict[str, Any] = {}
    metadata = getattr(observational_data, "metadata", None)
    if isinstance(metadata, Mapping):
        raw = metadata.get("causal_validity")
        if isinstance(raw, Mapping):
            settings.update({str(key): value for key, value in raw.items()})
    state_settings = state.params.get("causal_validity")
    if isinstance(state_settings, Mapping):
        settings.update({str(key): value for key, value in state_settings.items()})
    return settings


def _build_confidence_surface(
    *,
    report: CausalEffectReport,
    method_fqn: str,
    method_params: Mapping[str, Any],
) -> dict[str, Any]:
    confidence_interval = None
    interval_valid = False
    if report.confidence_interval is not None:
        lower = float(report.confidence_interval[0])
        upper = float(report.confidence_interval[1])
        confidence_interval = [lower, upper]
        interval_valid = lower <= float(report.point_estimate) <= upper

    honest_hte = None
    if report.method in {CausalMethod.CAUSAL_FOREST, CausalMethod.FOREST_DR}:
        honest_hte = {
            "enabled": bool(method_params.get("honest", True)),
            "confidence_level": float(method_params.get("confidence_level", 0.95)),
            "bootstrap_inference_samples": int(
                method_params.get("bootstrap_inference_samples", 0) or 0
            ),
            "inference_method": report.inference_method,
            "valid_confidence_interval": interval_valid,
        }

    return {
        "method_fqn": method_fqn,
        "point_estimate": report.point_estimate,
        "confidence_interval": confidence_interval,
        "confidence_interval_present": confidence_interval is not None,
        "confidence_interval_valid": interval_valid,
        "inference_method": report.inference_method,
        "honest_hte": honest_hte,
    }


def _build_sensitivity_check(
    *,
    sensitivity_ref: ArtifactRef | None,
    sensitivity_auto: Mapping[str, Any],
) -> dict[str, Any]:
    status = str(sensitivity_auto.get("status", "skipped"))
    payload = {
        "status": status,
        "method_fqn": str(
            sensitivity_auto.get(
                "method_fqn",
                "causal.sensitivity.sensitivity_metrics@1.0.0",
            )
        ),
        "artifact_id": (
            str(sensitivity_ref.artifact_id)
            if sensitivity_ref is not None
            else _normalize_optional_string(sensitivity_auto.get("artifact_id"))
        ),
        "e_value": _normalize_optional_float(sensitivity_auto.get("e_value")),
        "rosenbaum_gamma": _normalize_optional_float(sensitivity_auto.get("rosenbaum_gamma")),
        "is_robust": (
            bool(sensitivity_auto.get("is_robust")) if "is_robust" in sensitivity_auto else None
        ),
        "warnings": _string_list(sensitivity_auto.get("warnings")),
    }
    reason = _normalize_optional_string(sensitivity_auto.get("reason"))
    if reason is not None:
        payload["reason"] = reason
    if isinstance(sensitivity_auto.get("issues"), list):
        payload["issues"] = list(sensitivity_auto["issues"])
    return payload


def _build_spatial_interference_check(
    *,
    report: CausalEffectReport,
    method_fqn: str,
    method_params: Mapping[str, Any],
    observational_data: (
        PanelObservationalData
        | RDDObservationalData
        | HTEObservationalData
        | GraphCausalData
        | GraphCausalDataV1
    ),
) -> dict[str, Any]:
    def _first_present(*values: object) -> object | None:
        for value in values:
            if value is not None:
                return value
        return None

    metadata = report.metadata if isinstance(report.metadata, Mapping) else {}
    typed_diagnostics = _mapping(getattr(report, "spatial_hodge_diagnostics", None))
    typed_maup = _mapping(getattr(report, "maup_invariance_certificate", None))
    summary = _mapping(
        _first_present(
            getattr(report, "spatial_hodge_summary", None),
            typed_diagnostics or None,
            metadata.get("spatial_hodge_summary"),
        )
    )
    diagnostics = typed_diagnostics or _mapping(metadata.get("spatial_hodge_diagnostics"))
    maup = typed_maup or _mapping(metadata.get("maup_invariance_certificate"))
    if not summary and not diagnostics and not maup:
        return _skipped_check(
            "causal.diagnostics.spatial_interference", reason="missing_spatial_diagnostics"
        )

    observed_metadata = getattr(observational_data, "metadata", None)
    observed_spatial = _mapping(
        observed_metadata.get("spatial_interference")
        if isinstance(observed_metadata, Mapping)
        else None
    )
    declared_scale_id = _normalize_optional_string(
        summary.get("declared_scale_id")
        or diagnostics.get("declared_scale_id")
        or observed_spatial.get("scale_id")
        or method_params.get("scale_id")
    )
    declared_zoning_id = _normalize_optional_string(
        summary.get("declared_zoning_id")
        or diagnostics.get("declared_zoning_id")
        or observed_spatial.get("zoning_id")
        or method_params.get("zoning_id")
    )
    aggregation_rule = _normalize_optional_string(
        summary.get("aggregation_rule")
        or diagnostics.get("aggregation_rule")
        or observed_spatial.get("aggregation_rule")
        or method_params.get("aggregation_rule")
    )
    weight_spec = _normalize_optional_string(
        summary.get("weight_spec")
        or diagnostics.get("weight_spec")
        or observed_spatial.get("weight_spec")
        or method_params.get("weight_spec")
    )
    warnings = _string_list(summary.get("warnings")) + _string_list(maup.get("warnings"))
    blocker_codes = _string_list(summary.get("blocker_codes")) + _string_list(
        maup.get("blocker_codes")
    )

    return {
        "status": "success",
        "method_fqn": "causal.diagnostics.spatial_interference",
        "base_method_fqn": method_fqn,
        "declared_scale_id": declared_scale_id,
        "declared_zoning_id": declared_zoning_id,
        "aggregation_rule": aggregation_rule,
        "weight_spec": weight_spec,
        "zoning_hash": _normalize_optional_string(
            _first_present(summary.get("zoning_hash"), diagnostics.get("zoning_hash"))
        ),
        "weight_hash": _normalize_optional_string(
            _first_present(summary.get("weight_hash"), diagnostics.get("weight_hash"))
        ),
        "aggregation_hash": _normalize_optional_string(
            _first_present(summary.get("aggregation_hash"), diagnostics.get("aggregation_hash"))
        ),
        "eta_grad": _normalize_optional_float(
            _first_present(summary.get("eta_grad"), diagnostics.get("eta_grad"))
        ),
        "eta_curl": _normalize_optional_float(
            _first_present(summary.get("eta_curl"), diagnostics.get("eta_curl"))
        ),
        "eta_harm": _normalize_optional_float(
            _first_present(summary.get("eta_harm"), diagnostics.get("eta_harm"))
        ),
        "dominant_component": _normalize_optional_string(
            _first_present(summary.get("dominant_component"), diagnostics.get("dominant_component"))
        ),
        "max_profile_l1_gap": _normalize_optional_float(
            _first_present(
                summary.get("max_profile_l1_gap"),
                diagnostics.get("max_profile_l1_gap"),
            )
        ),
        "scale_instability": _normalize_optional_float(
            _first_present(summary.get("scale_instability"), diagnostics.get("scale_instability"))
        ),
        "zoning_instability": _normalize_optional_float(
            _first_present(
                summary.get("zoning_instability"),
                diagnostics.get("zoning_instability"),
            )
        ),
        "topology_sensitivity": _normalize_optional_float(
            _first_present(
                summary.get("topology_sensitivity"),
                diagnostics.get("topology_sensitivity"),
            )
        ),
        "candidate_partition_ids": list(
            summary.get("candidate_partition_ids")
            or diagnostics.get("candidate_partition_ids")
            or ()
        ),
        "maup_status": _normalize_optional_string(maup.get("status")),
        "maup_partitions_tested": (int(maup.get("partitions_tested", 0) or 0) if maup else None),
        "warnings": warnings,
        "blocker_codes": blocker_codes,
        "experimental": True,
    }


def _run_icp_check(
    *,
    ctx: ExecutionContext,
    seed: int,
    graph_data: GraphCausalData | None,
    settings: Mapping[str, Any],
    bundle_inputs: list[InputRef],
) -> dict[str, Any]:
    if not _setting_bool(settings, "enable_icp", default=True):
        return _skipped_check(_ICP_METHOD_FQN, reason="disabled")
    if graph_data is None:
        return _skipped_check(_ICP_METHOD_FQN, reason="unsupported_input")

    domain_labels = _normalize_domain_labels(settings.get("domain_labels"))
    if domain_labels is None:
        return _skipped_check(_ICP_METHOD_FQN, reason="missing_domain_labels")
    if len(domain_labels) != graph_data.sample_size:
        return _failed_check(
            _ICP_METHOD_FQN,
            reason="invalid_domain_labels_length",
            details={
                "expected": int(graph_data.sample_size),
                "received": len(domain_labels),
            },
        )
    if len(set(domain_labels)) < 2:
        return _skipped_check(_ICP_METHOD_FQN, reason="insufficient_domains")

    target_col = graph_data.column_names.index(graph_data.outcome)
    icp_cfg = _mapping(settings.get("icp"))
    result = run_job(
        JobSpec(
            job_kind="method",
            method_fqn=_ICP_METHOD_FQN,
            method_params={
                "alpha": float(icp_cfg.get("alpha", 0.05)),
                "correction": str(icp_cfg.get("correction", "bh")),
            },
            seed=seed,
        ),
        cas_root=ctx.store.root,
        method_state={
            "data": np.asarray(graph_data.data, dtype=float),
            "domain_labels": np.asarray(domain_labels),
            "target_col": target_col,
        },
    )
    payload = _method_payload(
        result,
        role_prefix="causal_validity_icp",
        bundle_inputs=bundle_inputs,
    )
    if result.issues:
        return _failed_check(_ICP_METHOD_FQN, reason="method_issues", details=payload)

    output = result.final_state if isinstance(result.final_state, dict) else {}
    icp_result = output.get("result")
    if not isinstance(icp_result, Mapping):
        return _failed_check(
            _ICP_METHOD_FQN,
            reason="missing_result_payload",
            details=payload,
        )
    return {
        **payload,
        "status": "success",
        "experimental": True,
        "passed": bool(icp_result.get("passed", False)),
        "n_rejected": int(icp_result.get("n_rejected", 0) or 0),
        "invariant_features": list(icp_result.get("invariant_features", [])),
        "variant_features": list(icp_result.get("variant_features", [])),
        "p_values": dict(icp_result.get("p_values", {})),
        "correction_method": _normalize_optional_string(icp_result.get("correction_method")),
        "metadata": dict(icp_result.get("metadata", {})),
        "warnings": ["simplified_icp_surface"],
    }


def _run_proximal_check(
    *,
    ctx: ExecutionContext,
    seed: int,
    observational_data: (
        PanelObservationalData
        | RDDObservationalData
        | HTEObservationalData
        | GraphCausalData
        | GraphCausalDataV1
    ),
    settings: Mapping[str, Any],
    bundle_inputs: list[InputRef],
) -> dict[str, Any]:
    if not _setting_bool(settings, "enable_proximal", default=True):
        return _skipped_check(_PROXIMAL_METHOD_FQN, reason="disabled")
    proximal_state = _build_proximal_state(observational_data=observational_data, settings=settings)
    if proximal_state is None:
        return _skipped_check(_PROXIMAL_METHOD_FQN, reason="missing_proxy_inputs")

    proximal_cfg = _mapping(settings.get("proximal"))
    result = run_job(
        JobSpec(
            job_kind="method",
            method_fqn=_PROXIMAL_METHOD_FQN,
            method_params={
                "n_bootstrap": int(proximal_cfg.get("n_bootstrap", 200) or 200),
                "confidence_level": float(proximal_cfg.get("confidence_level", 0.95)),
                "ridge": float(proximal_cfg.get("ridge", 1.0e-4)),
            },
            seed=seed,
        ),
        cas_root=ctx.store.root,
        method_state=proximal_state,
    )
    payload = _method_payload(
        result,
        role_prefix="causal_validity_proximal",
        bundle_inputs=bundle_inputs,
    )
    if result.issues:
        return _failed_check(_PROXIMAL_METHOD_FQN, reason="method_issues", details=payload)

    output = result.final_state if isinstance(result.final_state, dict) else {}
    report_payload = output.get("report")
    proximal_payload = output.get("proximal_result")
    bridge_report = output.get("bridge_plausibility_report")
    if not isinstance(bridge_report, Mapping) and isinstance(proximal_payload, Mapping):
        nested_bridge_report = proximal_payload.get("bridge_plausibility_report")
        if isinstance(nested_bridge_report, Mapping):
            bridge_report = nested_bridge_report
    if not isinstance(report_payload, Mapping) or not isinstance(proximal_payload, Mapping):
        failure_details = {
            **payload,
            "method_status": (
                _normalize_optional_string(report_payload.get("status"))
                if isinstance(report_payload, Mapping)
                else None
            ),
            "method_reason": (
                _normalize_optional_string(report_payload.get("status_reason"))
                if isinstance(report_payload, Mapping)
                else None
            ),
            "bridge_plausibility_report": (
                dict(bridge_report) if isinstance(bridge_report, Mapping) else None
            ),
            "bounds_bundle": (
                output.get("bounds_bundle")
                if isinstance(output.get("bounds_bundle"), Mapping)
                else None
            ),
            "negative_certificate": (
                output.get("negative_certificate")
                if isinstance(output.get("negative_certificate"), Mapping)
                else None
            ),
        }
        return _failed_check(
            _PROXIMAL_METHOD_FQN,
            reason="proximal_bridge_point_estimate_not_available",
            details=failure_details,
        )
    confidence_interval = proximal_payload.get("confidence_interval")
    return {
        **payload,
        "status": "success",
        "experimental": True,
        "point_estimate": _normalize_optional_float(proximal_payload.get("point_estimate")),
        "confidence_interval": (
            [float(confidence_interval[0]), float(confidence_interval[1])]
            if isinstance(confidence_interval, list) and len(confidence_interval) == 2
            else None
        ),
        "bridge_r_squared": _normalize_optional_float(proximal_payload.get("bridge_r_squared")),
        "proxy_strength": _normalize_optional_float(proximal_payload.get("proxy_strength")),
        "bridge_plausibility_report": (
            dict(bridge_report) if isinstance(bridge_report, Mapping) else None
        ),
        "bridge_plausibility_severity": _normalize_optional_string(
            proximal_payload.get("bridge_plausibility_severity")
            or (bridge_report.get("severity") if isinstance(bridge_report, Mapping) else None)
        ),
        "bridge_failure_mode": _normalize_optional_string(
            proximal_payload.get("bridge_failure_mode")
            or (
                bridge_report.get("suspected_failure_mode")
                if isinstance(bridge_report, Mapping)
                else None
            )
        ),
        "bridge_fallback_disposition": _normalize_optional_string(
            proximal_payload.get("bridge_fallback_disposition")
            or (
                bridge_report.get("fallback_disposition")
                if isinstance(bridge_report, Mapping)
                else None
            )
        ),
        "bridge_residual_r": _normalize_optional_float(
            bridge_report.get("residual_r") if isinstance(bridge_report, Mapping) else None
        ),
        "bridge_effective_rank": _normalize_optional_float(
            bridge_report.get("effective_rank") if isinstance(bridge_report, Mapping) else None
        ),
        "bridge_sigma_min": _normalize_optional_float(
            bridge_report.get("sigma_min") if isinstance(bridge_report, Mapping) else None
        ),
        "bridge_ill_posedness_index": _normalize_optional_float(
            bridge_report.get("ill_posedness_index") if isinstance(bridge_report, Mapping) else None
        ),
        "method_status": _normalize_optional_string(report_payload.get("status")),
        "method_reason": _normalize_optional_string(report_payload.get("status_reason")),
    }


def _run_recoverability_check(
    *,
    ctx: ExecutionContext,
    state: ExperimentState,
    seed: int,
    settings: Mapping[str, Any],
    bundle_inputs: list[InputRef],
) -> dict[str, Any]:
    if not _setting_bool(settings, "enable_recoverability", default=True):
        return _skipped_check(_RECOVERABILITY_METHOD_FQN, reason="disabled")
    mgraph_data = _resolve_mgraph_data(ctx=ctx, state=state, settings=settings)
    if mgraph_data is None:
        return _skipped_check(_RECOVERABILITY_METHOD_FQN, reason="missing_mgraph")

    recoverability_cfg = _mapping(settings.get("recoverability"))
    query_variables = recoverability_cfg.get("query_variables", settings.get("query_variables", []))
    result = run_job(
        JobSpec(
            job_kind="method",
            method_fqn=_RECOVERABILITY_METHOD_FQN,
            method_params={"query_variables": list(query_variables or [])},
            seed=seed,
        ),
        cas_root=ctx.store.root,
        method_state={"mgraph_data": mgraph_data},
    )
    payload = _method_payload(
        result,
        role_prefix="causal_validity_recoverability",
        bundle_inputs=bundle_inputs,
    )
    if result.issues:
        return _failed_check(_RECOVERABILITY_METHOD_FQN, reason="method_issues", details=payload)

    output = result.final_state if isinstance(result.final_state, dict) else {}
    recoverability_result = output.get("recoverability_result")
    if not isinstance(recoverability_result, Mapping):
        return _failed_check(
            _RECOVERABILITY_METHOD_FQN,
            reason="missing_result_payload",
            details=payload,
        )

    status = str(recoverability_result.get("status", "unknown"))
    response = {
        **payload,
        "status": "success",
        "recoverability_status": status,
        "query_variables": list(recoverability_result.get("query_variables", [])),
        "blocking_r_nodes": list(recoverability_result.get("blocking_r_nodes", [])),
        "algorithm_version": _normalize_optional_string(
            recoverability_result.get("algorithm_version")
        ),
        "trace_length": len(recoverability_result.get("trace", []))
        if isinstance(recoverability_result.get("trace"), list)
        else None,
    }
    if status == "recoverable":
        ordered = run_job(
            JobSpec(
                job_kind="method",
                method_fqn=_ORDERED_RECOVERY_METHOD_FQN,
                method_params={},
                seed=seed,
            ),
            cas_root=ctx.store.root,
            method_state={"mgraph_data": mgraph_data},
        )
        ordered_payload = _method_payload(
            ordered,
            role_prefix="causal_validity_ordered_recovery",
            bundle_inputs=bundle_inputs,
        )
        if not ordered.issues:
            ordered_state = ordered.final_state if isinstance(ordered.final_state, dict) else {}
            steps = ordered_state.get("ordered_recovery_steps")
            response["ordered_recovery"] = {
                **ordered_payload,
                "status": "success",
                "step_count": len(steps) if isinstance(steps, list) else 0,
            }
        else:
            response["ordered_recovery"] = _failed_check(
                _ORDERED_RECOVERY_METHOD_FQN,
                reason="method_issues",
                details=ordered_payload,
            )
    return response


def _run_pag_refinement_check(
    *,
    ctx: ExecutionContext,
    state: ExperimentState,
    settings: Mapping[str, Any],
    bundle_inputs: list[InputRef],
) -> dict[str, Any]:
    if not _setting_bool(settings, "enable_pag_refinement", default=True):
        return _skipped_check("causal.pag.refinement", reason="disabled")
    graph_ref, graph = _load_candidate_graph(ctx=ctx, state=state, settings=settings)
    if graph is None:
        return _skipped_check("causal.pag.refinement", reason="missing_graph")
    if graph.graph_type not in {GraphType.CPDAG, GraphType.PAG}:
        return _skipped_check(
            "causal.pag.refinement",
            reason=f"unsupported_graph_type:{graph.graph_type.value}",
        )

    pag = cpdag_to_pag(graph) if graph.graph_type is GraphType.CPDAG else graph
    refined, orientation_warnings = apply_pag_orientation_rules(pag)
    violations = validate_pag(refined)
    persisted_ref = persist_causal_graph_model(
        ctx.store,
        refined,
        inputs=(
            [InputRef(artifact_id=str(graph_ref.artifact_id), role="causal_validity_input_graph")]
            if graph_ref is not None
            else None
        ),
    )
    bundle_inputs.append(
        InputRef(
            artifact_id=str(persisted_ref.artifact_id),
            role="causal_validity_refined_pag_graph",
        )
    )
    changed_edges = _count_changed_pag_edges(before=pag, after=refined)
    return {
        "status": "success",
        "method_fqn": "causal.pag.refinement",
        "input_graph_ref": str(graph_ref.artifact_id) if graph_ref is not None else None,
        "refined_graph_ref": str(persisted_ref.artifact_id),
        "input_graph_type": graph.graph_type.value,
        "output_graph_type": refined.graph_type.value,
        "oriented_edge_count": changed_edges,
        "warning_count": len(orientation_warnings),
        "warnings": list(orientation_warnings),
        "violation_count": len(violations),
        "violations": list(violations),
        "pag_identification_policy": refined.pag_identification_policy.value,
        "id_confidence_under_pag": refined.id_confidence_under_pag,
    }


def _resolve_mgraph_data(
    *,
    ctx: ExecutionContext,
    state: ExperimentState,
    settings: Mapping[str, Any],
) -> dict[str, Any] | None:
    raw = settings.get("mgraph_data")
    if isinstance(raw, Mapping):
        return dict(raw)
    _, graph = _load_candidate_graph(ctx=ctx, state=state, settings=settings)
    if graph is not None and graph.graph_type is GraphType.MGRAPH:
        return graph.model_dump(mode="json")
    return None


def _load_candidate_graph(
    *,
    ctx: ExecutionContext,
    state: ExperimentState,
    settings: Mapping[str, Any],
) -> tuple[ArtifactRef | None, Any | None]:
    raw_graph = settings.get("causal_graph")
    if isinstance(raw_graph, Mapping):
        try:
            return None, CausalGraphModel.model_validate(raw_graph)
        except Exception:
            return None, None
    for key in _GRAPH_REF_KEYS:
        ref = state.artifacts_index.get(key)
        if ref is None:
            continue
        graph = None
        try:
            graph = load_causal_graph_model(
                ctx.store,
                CausalGraphModelRef.model_validate(ref.model_dump(mode="json")),
            )
        except Exception:
            graph = None
        if graph is None:
            continue
        return ref, graph
    return None, None


def _coerce_graph_validity_data(
    *,
    observational_data: (
        PanelObservationalData
        | RDDObservationalData
        | HTEObservationalData
        | GraphCausalData
        | GraphCausalDataV1
    ),
    settings: Mapping[str, Any],
) -> GraphCausalData | None:
    if isinstance(observational_data, GraphCausalData):
        return observational_data
    if isinstance(observational_data, GraphCausalDataV1):
        return GraphCausalData(
            data=observational_data.data,
            column_names=list(observational_data.column_names),
            treatment=observational_data.treatment,
            outcome=observational_data.outcome,
            graph_dot=observational_data.graph_gml,
            graph_ref=observational_data.graph_ref,
            covariates=list(observational_data.covariates),
        )
    if not isinstance(observational_data, HTEObservationalData):
        return None

    treatment_name = str(settings.get("treatment_name", "treatment"))
    outcome_name = str(settings.get("outcome_name", "outcome"))
    feature_names = _feature_names(
        explicit=observational_data.feature_names,
        prefix="x",
        count=observational_data.covariates.shape[1],
    )
    confounders = observational_data.confounders
    confounder_names: list[str] = []
    matrices = [
        np.asarray(observational_data.treatment, dtype=float).reshape(-1, 1),
        np.asarray(observational_data.outcome, dtype=float).reshape(-1, 1),
        np.asarray(observational_data.covariates, dtype=float),
    ]
    if confounders is not None:
        confounder_names = _feature_names(
            explicit=observational_data.confounder_names,
            prefix="w",
            count=confounders.shape[1],
        )
        matrices.append(np.asarray(confounders, dtype=float))

    return GraphCausalData(
        data=np.column_stack(matrices),
        column_names=[treatment_name, outcome_name, *feature_names, *confounder_names],
        treatment=treatment_name,
        outcome=outcome_name,
        graph_dot=None,
        graph_ref=_normalize_optional_string(settings.get("graph_ref")),
        covariates=[*feature_names, *confounder_names],
    )


def _build_proximal_state(
    *,
    observational_data: (
        PanelObservationalData
        | RDDObservationalData
        | HTEObservationalData
        | GraphCausalData
        | GraphCausalDataV1
    ),
    settings: Mapping[str, Any],
) -> dict[str, Any] | None:
    proximal_cfg = _mapping(settings.get("proximal"))
    if isinstance(observational_data, HTEObservationalData):
        treatment_proxy = proximal_cfg.get("treatment_proxy")
        outcome_proxy = proximal_cfg.get("outcome_proxy")
        if not isinstance(treatment_proxy, Sequence) or not isinstance(outcome_proxy, Sequence):
            return None
        return {
            "outcome": np.asarray(observational_data.outcome, dtype=float),
            "treatment": np.asarray(observational_data.treatment, dtype=float),
            "covariates": np.asarray(observational_data.covariates, dtype=float),
            "treatment_proxy": np.asarray(treatment_proxy, dtype=float),
            "outcome_proxy": np.asarray(outcome_proxy, dtype=float),
        }

    graph_data = _coerce_graph_validity_data(
        observational_data=observational_data,
        settings=settings,
    )
    if graph_data is None:
        return None
    treatment_proxy_name = _normalize_optional_string(proximal_cfg.get("treatment_proxy_name"))
    outcome_proxy_name = _normalize_optional_string(proximal_cfg.get("outcome_proxy_name"))
    if treatment_proxy_name is None or outcome_proxy_name is None:
        return None
    try:
        treatment_idx = graph_data.column_names.index(graph_data.treatment)
        outcome_idx = graph_data.column_names.index(graph_data.outcome)
        treatment_proxy_idx = graph_data.column_names.index(treatment_proxy_name)
        outcome_proxy_idx = graph_data.column_names.index(outcome_proxy_name)
    except ValueError:
        return None

    covariate_names = [
        name
        for name in (graph_data.covariates or graph_data.column_names)
        if name
        not in {
            graph_data.treatment,
            graph_data.outcome,
            treatment_proxy_name,
            outcome_proxy_name,
        }
    ]
    if not covariate_names:
        return None
    covariate_indices = [graph_data.column_names.index(name) for name in covariate_names]
    matrix = np.asarray(graph_data.data, dtype=float)
    return {
        "outcome": matrix[:, outcome_idx],
        "treatment": matrix[:, treatment_idx],
        "covariates": matrix[:, covariate_indices],
        "treatment_proxy": matrix[:, treatment_proxy_idx],
        "outcome_proxy": matrix[:, outcome_proxy_idx],
    }


def _build_capability_matrix(
    *,
    checks: Mapping[str, Mapping[str, Any]],
) -> dict[str, str]:
    return {
        "e_values": "available",
        "sensitivity_reporting": "available",
        "honest_causal_forest_ci": "available",
        "spatial_interference_hodge": _capability_state(checks.get("spatial_interference")),
        "maup_stability_surface": _capability_state(checks.get("spatial_interference")),
        "icp_invariance": _capability_state(checks.get("icp_invariance")),
        "proximal_causal_inference": _capability_state(checks.get("proximal_bridge")),
        "selection_bias_recoverability": _capability_state(checks.get("recoverability")),
        "pag_refinement": _capability_state(checks.get("pag_refinement")),
        "anchor_regression": "experimental_not_wired",
        "bayesian_causal_discovery": "experimental_not_wired",
        "neural_causal_discovery": "experimental_not_wired",
        "causal_representation_learning": "experimental_not_wired",
    }


def _capability_state(check: Mapping[str, Any] | None) -> str:
    if not isinstance(check, Mapping):
        return "not_available"
    status = str(check.get("status", "not_available"))
    if status == "success":
        return "available"
    if status == "skipped":
        return "available_when_inputs_present"
    return status


def _count_changed_pag_edges(*, before: CausalGraphModel, after: CausalGraphModel) -> int:
    before_edges = {
        (edge.src, edge.dst): (edge.mark_src.value, edge.mark_dst.value) for edge in before.edges
    }
    changed = 0
    for edge in after.edges:
        marks = (edge.mark_src.value, edge.mark_dst.value)
        if before_edges.get((edge.src, edge.dst)) != marks:
            changed += 1
    return changed


def _collect_bundle_warnings(checks: Mapping[str, Mapping[str, Any]]) -> list[str]:
    warnings: list[str] = []
    for name, payload in checks.items():
        status = str(payload.get("status", "unknown"))
        if status == "failed":
            warnings.append(f"{name}:failed")
        elif status == "skipped":
            reason = _normalize_optional_string(payload.get("reason")) or "not_run"
            warnings.append(f"{name}:skipped:{reason}")
    return warnings


def _method_payload(
    result: JobResult,
    *,
    role_prefix: str,
    bundle_inputs: list[InputRef],
) -> dict[str, Any]:
    payload: dict[str, Any] = {"method_result_ref": None, "method_evidence_ref": None}
    if result.method_result_ref is not None:
        payload["method_result_ref"] = str(result.method_result_ref.artifact_id)
        bundle_inputs.append(
            InputRef(
                artifact_id=str(result.method_result_ref.artifact_id),
                role=f"{role_prefix}_method_result",
            )
        )
    if result.method_evidence_ref is not None:
        payload["method_evidence_ref"] = str(result.method_evidence_ref.artifact_id)
        bundle_inputs.append(
            InputRef(
                artifact_id=str(result.method_evidence_ref.artifact_id),
                role=f"{role_prefix}_method_evidence",
            )
        )
    return payload


def _skipped_check(method_fqn: str, *, reason: str) -> dict[str, Any]:
    return {
        "status": "skipped",
        "method_fqn": method_fqn,
        "reason": reason,
    }


def _failed_check(
    method_fqn: str,
    *,
    reason: str,
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "status": "failed",
        "method_fqn": method_fqn,
        "reason": reason,
    }
    if details:
        payload["details"] = dict(details)
    return payload


def _mapping(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return {str(key): item for key, item in value.items()}
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        payload = model_dump(mode="python")
        if isinstance(payload, Mapping):
            return {str(key): item for key, item in payload.items()}
    return {}


def _setting_bool(settings: Mapping[str, Any], key: str, *, default: bool) -> bool:
    if key not in settings:
        return default
    value = settings.get(key)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False
    return bool(value)


def _normalize_optional_string(value: object) -> str | None:
    if value is None:
        return None
    candidate = str(value).strip()
    return candidate or None


def _normalize_optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        scalar = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(scalar):
        return None
    return scalar


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _normalize_domain_labels(value: object) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return None
    labels = [str(item) for item in value]
    return labels or None


def _feature_names(*, explicit: Sequence[str] | None, prefix: str, count: int) -> list[str]:
    if explicit is not None and len(explicit) == count:
        return [str(item) for item in explicit]
    return [f"{prefix}{idx}" for idx in range(count)]


__all__ = ["persist_causal_validity_bundle"]
