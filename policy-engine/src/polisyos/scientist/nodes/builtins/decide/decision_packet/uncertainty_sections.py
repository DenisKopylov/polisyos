"""Decision-packet uncertainty projections."""

from __future__ import annotations

from collections.abc import Mapping

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.contracts.foundry import SimulationResult
from polisyos.core.contracts.uncertainty import UncertaintyEnvelopeRef
from polisyos.ir.analytics.uncertainty import (
    load_simulation_result_uncertainty_admission,
    load_uncertainty_envelope,
)
from polisyos.ir.artifacts import normalize_artifact_ref
from polisyos.scientist.nodes.builtins.decide.decision_packet.validation import (
    _DECISION_PACKET_LOAD_ERRORS,
    _record_decision_packet_section_degraded,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CAUSAL_ENVELOPE_REF,
    ARTIFACT_ECONOMETRIC_ENVELOPE_REF,
    ARTIFACT_SIMULATION_RESULT_REF,
    INPUT_DATA_SNAPSHOT_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext


def _build_uncertainty_section(
    ctx: ExecutionContext,
    state_inputs: dict[str, ArtifactRef],
    state_artifacts: dict[str, ArtifactRef],
    *,
    packet_payload: dict[str, object] | None = None,
) -> dict[str, object]:
    envelope_refs: set[str] = set()
    legacy_bounds_refs: set[str] = set()
    output_envelope_refs: dict[str, str] = {}
    warnings: list[str] = []

    data_snapshot_ref = state_inputs.get(INPUT_DATA_SNAPSHOT_REF)
    if data_snapshot_ref is not None:
        try:
            payload = from_canonical_bytes(ctx.store.get_bytes(data_snapshot_ref))
            snapshot = DataSnapshot.model_validate(payload)
            if snapshot.uncertainty_envelope_ref is not None:
                envelope_refs.add(str(snapshot.uncertainty_envelope_ref.artifact_id))
            if snapshot.uncertainty_ref is not None:
                legacy_bounds_refs.add(str(snapshot.uncertainty_ref.artifact_id))
        except _DECISION_PACKET_LOAD_ERRORS as exc:
            warnings.append("data_snapshot_uncertainty_parse_failed")
            _record_decision_packet_section_degraded(
                packet_payload,
                operation="load_uncertainty_data_snapshot",
                reason="uncertainty_data_snapshot_load_failed",
                exc=exc,
                ref=data_snapshot_ref,
                artifact_key=INPUT_DATA_SNAPSHOT_REF,
            )

    simulation_result_ref = state_artifacts.get(ARTIFACT_SIMULATION_RESULT_REF)
    simulation_result_selector_ref: dict[str, str] | None = None
    if simulation_result_ref is not None:
        try:
            simulation_result_selector_ref = normalize_artifact_ref(simulation_result_ref)
            payload = from_canonical_bytes(ctx.store.get_bytes(simulation_result_ref))
            sim_result = SimulationResult.model_validate(payload)
            if sim_result.uncertainty_envelopes:
                for metric_id, ref in sim_result.uncertainty_envelopes.items():
                    ref_str = str(ref.artifact_id)
                    output_envelope_refs[str(metric_id)] = ref_str
                    envelope_refs.add(ref_str)
        except _DECISION_PACKET_LOAD_ERRORS as exc:
            warnings.append("simulation_result_uncertainty_parse_failed")
            _record_decision_packet_section_degraded(
                packet_payload,
                operation="load_uncertainty_simulation_result",
                reason="uncertainty_simulation_result_load_failed",
                exc=exc,
                ref=simulation_result_ref,
                artifact_key=ARTIFACT_SIMULATION_RESULT_REF,
            )

    causal_env_ref = state_artifacts.get(ARTIFACT_CAUSAL_ENVELOPE_REF)
    if causal_env_ref is not None:
        envelope_refs.add(str(causal_env_ref.artifact_id))
    econometric_env_ref = state_artifacts.get(ARTIFACT_ECONOMETRIC_ENVELOPE_REF)
    if econometric_env_ref is not None:
        envelope_refs.add(str(econometric_env_ref.artifact_id))

    return {
        "envelope_refs": sorted(envelope_refs),
        "legacy_bounds_refs": sorted(legacy_bounds_refs),
        "output_envelope_refs": output_envelope_refs,
        "simulation_result_ref": (
            str(simulation_result_ref.artifact_id) if simulation_result_ref is not None else None
        ),
        "simulation_result_selector_ref": simulation_result_selector_ref,
        "causal_envelope_ref": str(causal_env_ref.artifact_id)
        if causal_env_ref is not None
        else None,
        "econometric_envelope_ref": str(econometric_env_ref.artifact_id)
        if econometric_env_ref is not None
        else None,
        "envelope_count": len(envelope_refs),
        "legacy_bounds_count": len(legacy_bounds_refs),
        "output_envelope_count": len(output_envelope_refs),
        "warnings": warnings,
    }


def _build_uncertainty_bounds(
    ctx: ExecutionContext,
    uncertainty_section: dict[str, object],
    *,
    packet_payload: dict[str, object] | None = None,
) -> dict[str, float] | None:
    output_refs = uncertainty_section.get("output_envelope_refs")
    if not isinstance(output_refs, dict):
        return None

    bounds = _output_envelope_bounds(
        ctx,
        uncertainty_section,
        output_refs,
        packet_payload=packet_payload,
    )
    _named_envelope_bounds(
        ctx,
        uncertainty_section.get("causal_envelope_ref"),
        bounds,
        bound_prefix="causal_effect",
        operation="load_uncertainty_causal_envelope",
        reason="uncertainty_causal_envelope_load_failed",
        artifact_key="uncertainty.causal_envelope_ref",
        packet_payload=packet_payload,
    )
    _named_envelope_bounds(
        ctx,
        uncertainty_section.get("econometric_envelope_ref"),
        bounds,
        bound_prefix="econometric_effect",
        operation="load_uncertainty_econometric_envelope",
        reason="uncertainty_econometric_envelope_load_failed",
        artifact_key="uncertainty.econometric_envelope_ref",
        packet_payload=packet_payload,
    )

    return bounds or None


def _output_envelope_bounds(
    ctx: ExecutionContext,
    uncertainty_section: dict[str, object],
    output_refs: dict[object, object],
    *,
    packet_payload: dict[str, object] | None,
) -> dict[str, float]:
    bounds: dict[str, float] = {}
    if "simulation_result_selector_ref" in uncertainty_section:
        simulation_result_selector = uncertainty_section.get("simulation_result_selector_ref")
    else:
        # Legacy section payloads carry only an ID and therefore select the default view.
        simulation_result_selector = uncertainty_section.get("simulation_result_ref")
    for metric_id, ref_str in output_refs.items():
        if not isinstance(metric_id, str) or not isinstance(ref_str, str):
            continue
        if not isinstance(simulation_result_selector, (str, Mapping)):
            limitation_codes = ("simulation_result_ref_missing",)
            admission = None
        else:
            admission = load_simulation_result_uncertainty_admission(
                _ensure_ir_artifact_store(ctx.store),
                simulation_result_selector,
                metric_id,
            )
            limitation_codes = admission.limitation_codes
        if admission is None or not admission.admitted or admission.envelope is None:
            limitations = ",".join(limitation_codes) or "admission_not_established"
            warnings = uncertainty_section.get("warnings")
            if isinstance(warnings, list):
                warning = f"uncertainty_output_admission_limited:{metric_id}:{limitations}"
                if warning not in warnings:
                    warnings.append(warning)
            _record_decision_packet_section_degraded(
                packet_payload,
                operation="admit_uncertainty_output_envelope",
                reason="uncertainty_output_admission_limited",
                exc=ValueError(limitations),
                artifact_id=ref_str,
                artifact_key=f"uncertainty.output_envelope_refs.{metric_id}",
            )
            continue
        env = admission.envelope
        bounds[f"{metric_id}_lower"] = float(env.confidence_interval[0])
        bounds[f"{metric_id}_upper"] = float(env.confidence_interval[1])
        bounds[f"{metric_id}_point"] = float(env.point_estimate)
        if env.confidence_level is not None:
            bounds[f"{metric_id}_ci_level"] = float(env.confidence_level)
    return bounds


def _named_envelope_bounds(
    ctx: ExecutionContext,
    envelope_ref: object,
    bounds: dict[str, float],
    *,
    bound_prefix: str,
    operation: str,
    reason: str,
    artifact_key: str,
    packet_payload: dict[str, object] | None,
) -> None:
    if isinstance(envelope_ref, str):
        try:
            ref = UncertaintyEnvelopeRef(artifact_id=ArtifactID.model_validate(envelope_ref))
            env = load_uncertainty_envelope(_ensure_ir_artifact_store(ctx.store), ref)
            bounds[f"{bound_prefix}_lower"] = float(env.confidence_interval[0])
            bounds[f"{bound_prefix}_upper"] = float(env.confidence_interval[1])
            bounds[f"{bound_prefix}_point"] = float(env.point_estimate)
            if env.confidence_level is not None:
                bounds[f"{bound_prefix}_ci_level"] = float(env.confidence_level)
        except _DECISION_PACKET_LOAD_ERRORS as exc:
            _record_decision_packet_section_degraded(
                packet_payload,
                operation=operation,
                reason=reason,
                exc=exc,
                artifact_id=envelope_ref,
                artifact_key=artifact_key,
            )
