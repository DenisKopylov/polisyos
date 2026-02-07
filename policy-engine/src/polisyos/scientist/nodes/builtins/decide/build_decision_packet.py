from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Final

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.contracts.foundry import Metrics, SimulationResult
from polisyos.core.contracts.scientist import DecisionPacketRef
from polisyos.core.contracts.uncertainty import UncertaintyEnvelopeRef
from polisyos.ir.uncertainty import load_uncertainty_envelope
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.protocol import NodeOutcome, NodeSpec
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.governance.report import GovernanceReport
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_DECISION_CARD_REF,
    ARTIFACT_DECISION_PACKET_REF,
    ARTIFACT_ENVIRONMENT_MANIFEST_REF,
    ARTIFACT_EXEC_PLAN_REF,
    ARTIFACT_METRICS_REF,
    ARTIFACT_PROGRAM_GRAPH_REF,
    ARTIFACT_SIMULATION_RESULT_REF,
    ARTIFACT_STATE_SNAPSHOT_REF,
    INPUT_DATA_SNAPSHOT_REF,
    INPUT_KNOWLEDGE_BUNDLE_REF,
    INPUT_NORM_PACK_REF,
    INPUT_REGISTRY_BUNDLE_REF,
    INPUT_RESEARCH_INTENT_REF,
    INPUT_STATE_SNAPSHOT_REF,
    INPUT_TRINITY_BUNDLE_REF,
    REPORT_COMPILE_REPORT_REF,
    REPORT_GOVERNANCE_REPORT_REF,
    REPORT_LINK_REPORT_REF,
)

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_build_decision_packet@1.1.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Build Decision Packet",
    description="Create the DecisionPacket artifact from available reports and metrics.",
    tags=["builtin", "decide"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=[
        "run_id",
        "params.random_seed",
        "params.determinism_tier",
        "inputs",
        "reports_index",
        "artifacts_index",
    ],
    state_writes=[f"artifacts_index.{ARTIFACT_DECISION_PACKET_REF}"],
    produces=[ARTIFACT_DECISION_PACKET_REF],
)


class ReplayReadiness(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    INCOMPLETE = "incomplete"


_REQUIRED_INPUT_KEYS: Final[frozenset[str]] = frozenset(
    {
        INPUT_TRINITY_BUNDLE_REF,
        INPUT_REGISTRY_BUNDLE_REF,
    }
)

_OPTIONAL_INPUT_KEYS: Final[frozenset[str]] = frozenset(
    {
        INPUT_NORM_PACK_REF,
        INPUT_KNOWLEDGE_BUNDLE_REF,
        INPUT_RESEARCH_INTENT_REF,
        ARTIFACT_ENVIRONMENT_MANIFEST_REF,
    }
)


@dataclass(frozen=True)
class BuildDecisionPacketNode:
    """Build a DecisionPacket from the engine state."""

    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        seed = int(state.params.get("random_seed", 0) or 0)
        inputs_section = _build_inputs_section(state.inputs, state.artifacts_index)
        artifacts_section = _build_artifacts_section(state.artifacts_index, state.reports_index)
        readiness = _compute_replay_readiness(inputs_section)
        strategy_hint = _determine_strategy_hint(inputs_section, artifacts_section)

        packet_payload: dict[str, object] = {
            "schema_version": "3.1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "run_id": state.run_id,
            "seed": seed,
            "run_record": {
                "schema_version": "3.1",
                "run_id": state.run_id,
                "seed": seed,
                "engine": "scientist.engine",
            },
            "simulation_results": None,
            "governance": None,
            "uncertainty": _build_uncertainty_section(ctx, state.inputs, state.artifacts_index),
            "uncertainty_bounds": None,
            "inputs": inputs_section,
            "artifacts": artifacts_section,
            "replay": {
                "readiness": readiness.value,
                "strategy_hint": strategy_hint,
                "effective_seed": seed,
                "seed_source": "params.random_seed",
                "determinism_tier": (
                    state.params.get("determinism_tier")
                    if isinstance(state.params.get("determinism_tier"), str)
                    else None
                ),
            },
            "notes": [],
        }

        metrics_ref = state.artifacts_index.get(ARTIFACT_METRICS_REF)
        if metrics_ref is not None:
            try:
                payload = from_canonical_bytes(ctx.store.get_bytes(metrics_ref.artifact_id))
                metrics = Metrics.model_validate(payload)
                packet_payload["simulation_results"] = dict(metrics.values)
            except Exception:
                packet_payload["simulation_results"] = None

        governance_ref = state.reports_index.get(REPORT_GOVERNANCE_REPORT_REF)
        if governance_ref is not None:
            try:
                payload = from_canonical_bytes(ctx.store.get_bytes(governance_ref.artifact_id))
                report = GovernanceReport.model_validate(payload)
                packet_payload["governance"] = {
                    "verdict": report.verdict,
                    "issues": report.issues,
                    "notes": report.notes,
                }
            except Exception:
                packet_payload["governance"] = None

        uncertainty_bounds = _build_uncertainty_bounds(
            ctx,
            (
                packet_payload["uncertainty"]
                if isinstance(packet_payload["uncertainty"], dict)
                else {}
            ),
        )
        packet_payload["uncertainty_bounds"] = uncertainty_bounds

        inputs = _build_manifest_inputs(packet_payload)

        packet_ref_payload = ctx.store.put_json(
            packet_payload,
            PutOptions(
                kind="scientist.decision_packet",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.scientist.DecisionPacket",
                    version="3.1",
                ),
                inputs=inputs or None,
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        packet_ref = DecisionPacketRef(artifact_id=packet_ref_payload.artifact_id)

        new_state = state.model_copy(deep=True)
        new_state.artifacts_index[ARTIFACT_DECISION_PACKET_REF] = packet_ref

        return NodeOutcome(status="ok", state=new_state, artifacts=[packet_ref])


def _build_inputs_section(
    state_inputs: dict[str, ArtifactRef],
    artifacts_index: dict[str, ArtifactRef],
) -> dict[str, str | None]:
    return {
        INPUT_TRINITY_BUNDLE_REF: _ref_from_dict(state_inputs, INPUT_TRINITY_BUNDLE_REF),
        INPUT_DATA_SNAPSHOT_REF: _ref_from_dict(state_inputs, INPUT_DATA_SNAPSHOT_REF),
        INPUT_STATE_SNAPSHOT_REF: _ref_from_dict(state_inputs, INPUT_STATE_SNAPSHOT_REF),
        INPUT_REGISTRY_BUNDLE_REF: _ref_from_dict(state_inputs, INPUT_REGISTRY_BUNDLE_REF),
        INPUT_NORM_PACK_REF: _ref_from_dict(state_inputs, INPUT_NORM_PACK_REF),
        INPUT_KNOWLEDGE_BUNDLE_REF: _ref_from_dict(state_inputs, INPUT_KNOWLEDGE_BUNDLE_REF),
        INPUT_RESEARCH_INTENT_REF: _ref_from_dict(state_inputs, INPUT_RESEARCH_INTENT_REF),
        ARTIFACT_ENVIRONMENT_MANIFEST_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_ENVIRONMENT_MANIFEST_REF
        ),
    }


def _build_artifacts_section(
    artifacts_index: dict[str, ArtifactRef],
    reports_index: dict[str, ArtifactRef],
) -> dict[str, str | None]:
    return {
        ARTIFACT_EXEC_PLAN_REF: _ref_from_dict(artifacts_index, ARTIFACT_EXEC_PLAN_REF),
        ARTIFACT_PROGRAM_GRAPH_REF: _ref_from_dict(artifacts_index, ARTIFACT_PROGRAM_GRAPH_REF),
        ARTIFACT_SIMULATION_RESULT_REF: _ref_from_dict(
            artifacts_index, ARTIFACT_SIMULATION_RESULT_REF
        ),
        ARTIFACT_STATE_SNAPSHOT_REF: _ref_from_dict(artifacts_index, ARTIFACT_STATE_SNAPSHOT_REF),
        ARTIFACT_METRICS_REF: _ref_from_dict(artifacts_index, ARTIFACT_METRICS_REF),
        REPORT_GOVERNANCE_REPORT_REF: _ref_from_dict(reports_index, REPORT_GOVERNANCE_REPORT_REF),
        REPORT_COMPILE_REPORT_REF: _ref_from_dict(reports_index, REPORT_COMPILE_REPORT_REF),
        REPORT_LINK_REPORT_REF: _ref_from_dict(reports_index, REPORT_LINK_REPORT_REF),
        ARTIFACT_DECISION_CARD_REF: _ref_from_dict(artifacts_index, ARTIFACT_DECISION_CARD_REF),
    }


def _ref_from_dict(index: dict[str, ArtifactRef], key: str) -> str | None:
    ref = index.get(key)
    return str(ref.artifact_id) if ref is not None else None


def _compute_replay_readiness(inputs_section: dict[str, str | None]) -> ReplayReadiness:
    missing_required = [key for key in _REQUIRED_INPUT_KEYS if inputs_section.get(key) is None]
    has_snapshot = bool(
        inputs_section.get(INPUT_DATA_SNAPSHOT_REF) or inputs_section.get(INPUT_STATE_SNAPSHOT_REF)
    )
    if missing_required or not has_snapshot:
        return ReplayReadiness.INCOMPLETE
    missing_optional = [key for key in _OPTIONAL_INPUT_KEYS if inputs_section.get(key) is None]
    if missing_optional:
        return ReplayReadiness.PARTIAL
    return ReplayReadiness.COMPLETE


def _determine_strategy_hint(
    inputs_section: dict[str, str | None],
    artifacts_section: dict[str, str | None],
) -> str:
    has_registry = inputs_section.get(INPUT_REGISTRY_BUNDLE_REF) is not None
    has_snapshot = bool(
        inputs_section.get(INPUT_DATA_SNAPSHOT_REF)
        or inputs_section.get(INPUT_STATE_SNAPSHOT_REF)
        or artifacts_section.get(ARTIFACT_STATE_SNAPSHOT_REF)
    )
    has_exec_plan = artifacts_section.get(ARTIFACT_EXEC_PLAN_REF) is not None
    has_trinity = inputs_section.get(INPUT_TRINITY_BUNDLE_REF) is not None
    if has_exec_plan and has_registry and has_snapshot:
        return "foundry"
    if has_trinity and has_registry and has_snapshot:
        return "scientist"
    return "none"


def _build_manifest_inputs(packet_payload: dict[str, object]) -> list[InputRef]:
    collected: dict[tuple[str, str], InputRef] = {}
    for section_name, prefix in (
        ("inputs", "input"),
        ("artifacts", "artifact"),
        ("uncertainty", "uncertainty"),
    ):
        section = packet_payload.get(section_name)
        _collect_manifest_refs(section, prefix, collected)
    return list(collected.values())


def _collect_manifest_refs(
    value: object,
    role_prefix: str,
    collected: dict[tuple[str, str], InputRef],
) -> None:
    if isinstance(value, str):
        try:
            artifact_id = ArtifactID.model_validate(value)
        except Exception:
            return
        collected[(artifact_id.hex, role_prefix)] = InputRef(
            artifact_id=artifact_id,
            role=role_prefix,
        )
        return

    if isinstance(value, list):
        for idx, nested in enumerate(value):
            _collect_manifest_refs(nested, f"{role_prefix}[{idx}]", collected)
        return

    if isinstance(value, dict):
        for key, nested in value.items():
            _collect_manifest_refs(nested, f"{role_prefix}.{key}", collected)


def _build_uncertainty_section(
    ctx: ExecutionContext,
    state_inputs: dict[str, ArtifactRef],
    state_artifacts: dict[str, ArtifactRef],
) -> dict[str, object]:
    envelope_refs: set[str] = set()
    legacy_bounds_refs: set[str] = set()
    output_envelope_refs: dict[str, str] = {}
    warnings: list[str] = []

    data_snapshot_ref = state_inputs.get(INPUT_DATA_SNAPSHOT_REF)
    if data_snapshot_ref is not None:
        try:
            payload = from_canonical_bytes(ctx.store.get_bytes(data_snapshot_ref.artifact_id))
            snapshot = DataSnapshot.model_validate(payload)
            if snapshot.uncertainty_envelope_ref is not None:
                envelope_refs.add(str(snapshot.uncertainty_envelope_ref.artifact_id))
            if snapshot.uncertainty_ref is not None:
                legacy_bounds_refs.add(str(snapshot.uncertainty_ref.artifact_id))
        except Exception:
            warnings.append("data_snapshot_uncertainty_parse_failed")

    simulation_result_ref = state_artifacts.get(ARTIFACT_SIMULATION_RESULT_REF)
    if simulation_result_ref is not None:
        try:
            payload = from_canonical_bytes(ctx.store.get_bytes(simulation_result_ref.artifact_id))
            sim_result = SimulationResult.model_validate(payload)
            if sim_result.uncertainty_envelopes:
                for metric_id, ref in sim_result.uncertainty_envelopes.items():
                    ref_str = str(ref.artifact_id)
                    output_envelope_refs[str(metric_id)] = ref_str
                    envelope_refs.add(ref_str)
        except Exception:
            warnings.append("simulation_result_uncertainty_parse_failed")

    return {
        "envelope_refs": sorted(envelope_refs),
        "legacy_bounds_refs": sorted(legacy_bounds_refs),
        "output_envelope_refs": output_envelope_refs,
        "envelope_count": len(envelope_refs),
        "legacy_bounds_count": len(legacy_bounds_refs),
        "output_envelope_count": len(output_envelope_refs),
        "warnings": warnings,
    }


def _build_uncertainty_bounds(
    ctx: ExecutionContext,
    uncertainty_section: dict[str, object],
) -> dict[str, float] | None:
    output_refs = uncertainty_section.get("output_envelope_refs")
    if not isinstance(output_refs, dict):
        return None

    bounds: dict[str, float] = {}
    for metric_id, ref_str in output_refs.items():
        if not isinstance(metric_id, str) or not isinstance(ref_str, str):
            continue
        try:
            ref = UncertaintyEnvelopeRef(artifact_id=ArtifactID.model_validate(ref_str))
            env = load_uncertainty_envelope(ctx.store, ref)
        except Exception:
            continue
        bounds[f"{metric_id}_lower"] = float(env.confidence_interval[0])
        bounds[f"{metric_id}_upper"] = float(env.confidence_interval[1])
        bounds[f"{metric_id}_point"] = float(env.point_estimate)
        if env.confidence_level is not None:
            bounds[f"{metric_id}_ci_level"] = float(env.confidence_level)

    return bounds or None
