from __future__ import annotations

from decimal import Decimal
from typing import Any, Mapping

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins import state_keys as keys

_DEFAULT_KINDS: dict[str, str] = {
    keys.INPUT_TRINITY_BUNDLE_REF: "ir.trinity_bundle",
    keys.INPUT_POLICY_IR_REF: "ir.policy_surface",
    keys.INPUT_REGISTRY_BUNDLE_REF: "core.registry_bundle",
    keys.INPUT_DATA_SNAPSHOT_REF: "fabric.data_snapshot",
    keys.INPUT_STATE_SNAPSHOT_REF: "foundry.state_snapshot",
    keys.INPUT_DATA_VIEW_REQUEST_REF: "ir.data_view_request",
    keys.ARTIFACT_EXEC_PLAN_REF: "foundry.exec_plan",
    keys.ARTIFACT_PROGRAM_GRAPH_REF: "foundry.program_graph",
    keys.ARTIFACT_SIMULATION_RESULT_REF: "foundry.simulation_result",
    keys.ARTIFACT_METRICS_REF: "foundry.metrics",
    keys.ARTIFACT_STATE_DELTA_REF: "foundry.state_delta",
    keys.ARTIFACT_STATE_SNAPSHOT_REF: "foundry.state_snapshot",
    keys.ARTIFACT_CONSTRAINT_REPORT_REF: "foundry.constraint_report",
    keys.ARTIFACT_ENVIRONMENT_MANIFEST_REF: "foundry.environment_manifest",
    keys.ARTIFACT_SLOT_LAYOUT_REF: "foundry.slot_layout",
    keys.ARTIFACT_TREASURY_PLAN_REF: "foundry.treasury_plan",
    keys.ARTIFACT_DECISION_PACKET_REF: "scientist.decision_packet",
    keys.ARTIFACT_DECISION_CARD_REF: "scientist.decision_card",
    keys.REPORT_LINK_REPORT_REF: "compiler.link_report",
    keys.REPORT_COMPILE_REPORT_REF: "compiler.compile_report",
    keys.REPORT_GOVERNANCE_REPORT_REF: "scientist.governance_report",
    keys.REPORT_LEGAL_REPORT_REF: "lex.legal_report",
    keys.REPORT_CHANGE_PROPOSAL_REF: "lex.change_proposal",
}


def _coerce_artifact_ref(value: Any, *, key: str | None = None) -> ArtifactRef | None:
    if value is None:
        return None
    if isinstance(value, ArtifactRef):
        return value
    if hasattr(value, "model_dump"):
        try:
            data = value.model_dump()
        except Exception:
            data = None
        if isinstance(data, dict):
            value = data
    if not isinstance(value, Mapping):
        return None

    data = dict(value)
    if "artifact_id" not in data and data.get("cas_hash"):
        data["artifact_id"] = data.get("cas_hash")
    if "kind" not in data and key in _DEFAULT_KINDS:
        data["kind"] = _DEFAULT_KINDS[key]
    if "media_type" not in data:
        data["media_type"] = "application/json"

    if "artifact_id" not in data:
        return None

    try:
        return ArtifactRef.model_validate(data)
    except Exception:
        return None


def legacy_to_engine_state(legacy: Mapping[str, Any]) -> ExperimentState:
    run_id = str(legacy.get("run_id") or "")

    inputs: dict[str, ArtifactRef] = {}
    artifacts: dict[str, ArtifactRef] = {}
    reports: dict[str, ArtifactRef] = {}

    for key in [
        keys.INPUT_TRINITY_BUNDLE_REF,
        keys.INPUT_POLICY_IR_REF,
        keys.INPUT_REGISTRY_BUNDLE_REF,
        keys.INPUT_DATA_SNAPSHOT_REF,
        keys.INPUT_STATE_SNAPSHOT_REF,
        keys.INPUT_DATA_VIEW_REQUEST_REF,
    ]:
        ref = _coerce_artifact_ref(legacy.get(key), key=key)
        if ref is not None:
            inputs[key] = ref

    # Legacy simulation_results_ref -> engine simulation_result_ref
    sim_ref = _coerce_artifact_ref(legacy.get("simulation_results_ref"), key=keys.ARTIFACT_SIMULATION_RESULT_REF)
    if sim_ref is None:
        sim_ref = _coerce_artifact_ref(legacy.get(keys.ARTIFACT_SIMULATION_RESULT_REF), key=keys.ARTIFACT_SIMULATION_RESULT_REF)
    if sim_ref is not None:
        artifacts[keys.ARTIFACT_SIMULATION_RESULT_REF] = sim_ref

    for key in [
        keys.ARTIFACT_EXEC_PLAN_REF,
        keys.ARTIFACT_PROGRAM_GRAPH_REF,
        keys.ARTIFACT_METRICS_REF,
        keys.ARTIFACT_STATE_DELTA_REF,
        keys.ARTIFACT_STATE_SNAPSHOT_REF,
        keys.ARTIFACT_CONSTRAINT_REPORT_REF,
        keys.ARTIFACT_ENVIRONMENT_MANIFEST_REF,
        keys.ARTIFACT_SLOT_LAYOUT_REF,
        keys.ARTIFACT_TREASURY_PLAN_REF,
        keys.ARTIFACT_DECISION_PACKET_REF,
        keys.ARTIFACT_DECISION_CARD_REF,
    ]:
        ref = _coerce_artifact_ref(legacy.get(key), key=key)
        if ref is not None:
            artifacts[key] = ref

    for key in [
        keys.REPORT_LINK_REPORT_REF,
        keys.REPORT_COMPILE_REPORT_REF,
        keys.REPORT_GOVERNANCE_REPORT_REF,
        keys.REPORT_LEGAL_REPORT_REF,
        keys.REPORT_CHANGE_PROPOSAL_REF,
    ]:
        ref = _coerce_artifact_ref(legacy.get(key), key=key)
        if ref is not None:
            reports[key] = ref

    params: dict[str, str | int | bool | Decimal] = {}
    for name in ["random_seed", "require_human_gate", "pii_tier", "gate_decision"]:
        if name in legacy:
            value = legacy.get(name)
            if isinstance(value, (str, int, bool, Decimal)):
                params[name] = value

    budgets: dict[str, Decimal] = {}
    budget = legacy.get("budget")
    if isinstance(budget, Mapping):
        for key, value in budget.items():
            try:
                budgets[str(key)] = Decimal(str(value))
            except Exception:
                continue

    return ExperimentState(
        run_id=run_id,
        inputs=inputs,
        artifacts_index=artifacts,
        reports_index=reports,
        params=params,
        budgets=budgets,
    )


def apply_engine_to_legacy(engine_state: ExperimentState, legacy_state: Mapping[str, Any]) -> dict[str, Any]:
    updated = dict(legacy_state)
    updated["run_id"] = engine_state.run_id

    for key, ref in engine_state.inputs.items():
        updated[key] = ref.model_dump()

    for key, ref in engine_state.artifacts_index.items():
        updated[key] = ref.model_dump()

    # Legacy alias for simulation_results_ref
    if keys.ARTIFACT_SIMULATION_RESULT_REF in engine_state.artifacts_index:
        updated["simulation_results_ref"] = engine_state.artifacts_index[
            keys.ARTIFACT_SIMULATION_RESULT_REF
        ].model_dump()

    for key, ref in engine_state.reports_index.items():
        updated[key] = ref.model_dump()

    return updated


__all__ = ["legacy_to_engine_state", "apply_engine_to_legacy"]
