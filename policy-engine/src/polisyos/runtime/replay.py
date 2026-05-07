"""Plan, measure, and verify deterministic replay from CAS decision packets.

The replay ABI is anchored on artifact ids and decision-packet payload shape.
Callers should expect best-effort environment comparison, explicit completeness
reports for missing/corrupted dependencies, and verification results that
distinguish bit-exact checks from tolerance-bounded metric comparisons.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any, cast

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.environment import (
    EnvironmentDiff,
    EnvironmentManifest,
    capture_environment,
    compare_environments,
)
from polisyos.core.artifacts.graph import (
    DependencyGraph,
    NodeStatus,
    resolve_dependency_graph,
)
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.foundry import ExecPlan, Metrics, SimulationResult
from polisyos.foundry.execute import resolve_execution_posture

if TYPE_CHECKING:
    from polisyos.core.artifacts.protocol import ArtifactStore

_SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")
_SHA256_PREF_RE = re.compile(r"^sha256:[0-9a-f]{64}$")

_STATE_SOURCE_ROLES = frozenset(
    {
        "input.input_bindings_ref",
        "input.data_snapshot_ref",
        "input.state_snapshot_ref",
        "artifact.state_snapshot_ref",
    }
)
logger = get_logger(__name__)


class ReplayStrategy(StrEnum):
    """Select the replay engine inferred from the packet dependency layout."""

    FOUNDRY = "foundry"
    SCIENTIST = "scientist"
    NONE = "none"


class CompletenessLevel(StrEnum):
    """Classify whether the artifact graph is replayable without intervention."""

    COMPLETE = "complete"
    RECOVERABLE = "recoverable"
    INCOMPLETE = "incomplete"


class VerificationMode(StrEnum):
    """Choose how a replay output should be compared with the original result."""

    BIT_EXACT = "bit_exact"
    CI_BOUNDED = "ci_bounded"
    SKIP = "skip"


@dataclass(frozen=True)
class SeedResolution:
    """Report the effective random seed and the source field it came from."""

    value: int
    source: str


@dataclass(frozen=True)
class MissingArtifact:
    """Describe a missing or corrupted dependency discovered during graph traversal."""

    artifact_id: str
    role: str
    kind: str | None
    critical: bool
    status: NodeStatus


@dataclass
class CompletenessReport:
    """Summarize dependency-graph completeness and replay-blocking reason codes."""

    level: CompletenessLevel
    strategy: ReplayStrategy
    total_artifacts: int
    present_artifacts: int
    missing: list[MissingArtifact] = field(default_factory=list)
    corrupted: list[MissingArtifact] = field(default_factory=list)
    total_size_bytes: int = 0
    reason_codes: list[str] = field(default_factory=list)
    graph: DependencyGraph | None = None

    @property
    def ok(self) -> bool:
        """Return `True` only when every critical dependency is present and valid."""
        return self.level == CompletenessLevel.COMPLETE

    def summary(self) -> str:
        """Render a compact human-readable status summary for CLI/debug output."""
        lines = [
            f"Completeness: {self.level.value}",
            f"Strategy: {self.strategy.value}",
            f"Artifacts: {self.present_artifacts}/{self.total_artifacts}",
        ]
        if self.reason_codes:
            lines.append(f"Reasons: {', '.join(self.reason_codes)}")
        if self.missing:
            lines.append(f"Missing: {len(self.missing)}")
        if self.corrupted:
            lines.append(f"Corrupted: {len(self.corrupted)}")
        return "\n".join(lines)


@dataclass(frozen=True)
class VerificationConfig:
    """Configure replay verification mode and numeric tolerance parameters."""

    mode: VerificationMode = VerificationMode.BIT_EXACT
    relative_tolerance: float = 1e-6
    confidence_level: float = 0.95


@dataclass
class VerificationResult:
    """Return replay verification status and comparison diagnostics."""

    passed: bool
    mode: VerificationMode
    details: dict[str, Any] = field(default_factory=dict)
    original_ref: str | None = None
    replay_ref: str | None = None


@dataclass
class ReplayPlan:
    """Bundle packet payload, inferred replay strategy, seed, and completeness state."""

    packet_ref: ArtifactID
    strategy: ReplayStrategy
    seed: SeedResolution
    completeness: CompletenessReport
    payload: dict[str, Any]


@dataclass(frozen=True)
class ReplayBundleMeasurement:
    """Describe replay readiness and similarity for a persisted replayable bundle."""

    replay_bundle_ref: ArtifactRef
    completeness: CompletenessReport
    verification_mode: str
    passed: bool
    overall_similarity: float
    reason_codes: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


def set_global_seeds(seed: int) -> None:
    """Initialize Python and NumPy RNGs before replay execution."""
    random.seed(seed)
    try:
        import numpy as np

        np.random.seed(seed)
    except ImportError as exc:
        logger.debug("Failed to initialize numpy random seed: %s", exc)


def normalize_artifact_id(value: str) -> ArtifactID:
    """Parse a `sha256:<hex>` or raw 64-hex digest into `ArtifactID`.

    Raises:
        ValueError: If `value` is not a supported CAS artifact identifier.
    """
    if _SHA256_PREF_RE.fullmatch(value):
        return ArtifactID.model_validate(value)
    if _SHA256_HEX_RE.fullmatch(value):
        return ArtifactID.from_sha256_hex(value)
    raise ValueError(f"Invalid artifact reference: {value}")


def try_parse_artifact_id(value: Any) -> ArtifactID | None:
    """Return a normalized artifact id or `None` for non-string/malformed values."""
    if not isinstance(value, str):
        return None
    try:
        return normalize_artifact_id(value)
    except ValueError:
        return None


def _dict_section(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    return value if isinstance(value, dict) else {}


def determine_replay_strategy(payload: dict[str, Any]) -> ReplayStrategy:
    """Infer the replay strategy from packet `inputs` and `artifacts` references."""
    inputs = _dict_section(payload, "inputs")
    artifacts = _dict_section(payload, "artifacts")
    has_exec_plan = isinstance(artifacts.get("exec_plan_ref"), str)
    has_registry = isinstance(inputs.get("registry_bundle_ref"), str)
    has_snapshot = any(
        isinstance(inputs.get(key), str)
        for key in ("input_bindings_ref", "data_snapshot_ref", "state_snapshot_ref")
    ) or isinstance(artifacts.get("state_snapshot_ref"), str)
    has_trinity = isinstance(inputs.get("trinity_bundle_ref"), str)

    if has_exec_plan and has_registry and has_snapshot:
        return ReplayStrategy.FOUNDRY
    if has_trinity and has_registry and has_snapshot:
        return ReplayStrategy.SCIENTIST
    return ReplayStrategy.NONE


def resolve_effective_seed(
    payload: dict[str, Any],
    *,
    store: ArtifactStore | None = None,
    default: int = 0,
) -> SeedResolution:
    """Resolve the replay seed from packet metadata, run records, or ExecPlan."""
    replay_block = payload.get("replay")
    if isinstance(replay_block, dict):
        replay_seed = replay_block.get("effective_seed")
        if isinstance(replay_seed, int):
            return SeedResolution(value=replay_seed, source="payload.replay.effective_seed")

    run_record = payload.get("run_record")
    if isinstance(run_record, dict):
        rr_seed = run_record.get("seed")
        if isinstance(rr_seed, int):
            return SeedResolution(value=rr_seed, source="payload.run_record.seed")

    seed = payload.get("seed")
    if isinstance(seed, int):
        return SeedResolution(value=seed, source="payload.seed")

    if store is not None:
        artifacts = _dict_section(payload, "artifacts")
        exec_plan_ref = try_parse_artifact_id(artifacts.get("exec_plan_ref"))
        if exec_plan_ref is not None:
            try:
                plan_payload = from_canonical_bytes(store.get_bytes(exec_plan_ref))
                plan = ExecPlan.model_validate(plan_payload)
                posture = resolve_execution_posture(plan, None)
                return SeedResolution(value=posture.seed, source=posture.seed_source)
            except (OSError, TypeError, ValueError, RuntimeError) as exc:
                logger.debug("Failed to resolve effective seed from exec plan: %s", exc)

    return SeedResolution(value=default, source="default")


def compare_current_environment(
    store: ArtifactStore,
    payload: dict[str, Any],
) -> list[EnvironmentDiff]:
    """Compare the captured environment manifest with the current process environment.

    Missing manifests or decode failures are treated as soft failures and return
    an empty diff list after debug logging.
    """
    inputs = _dict_section(payload, "inputs")
    env_ref = try_parse_artifact_id(inputs.get("environment_manifest_ref"))
    if env_ref is None:
        return []
    try:
        original_payload = from_canonical_bytes(store.get_bytes(env_ref))
        original_env = EnvironmentManifest.model_validate(original_payload)
        current_env = capture_environment(include_git=False, include_dependencies=True)
        return compare_environments(original_env, current_env)
    except (OSError, TypeError, ValueError, RuntimeError) as exc:
        logger.debug("Failed to compare environments: %s", exc)
        return []


def build_replay_plan(store: ArtifactStore, packet_ref: ArtifactID) -> ReplayPlan:
    """Load a decision packet, infer strategy/seed, and compute completeness."""
    payload = _load_packet_payload(store, packet_ref)
    completeness = completeness_check(store, packet_ref, payload=payload)
    strategy = determine_replay_strategy(payload)
    seed = resolve_effective_seed(payload, store=store)
    return ReplayPlan(
        packet_ref=packet_ref,
        strategy=strategy,
        seed=seed,
        completeness=completeness,
        payload=payload,
    )


def measure_replayable_audit_bundle(
    store: ArtifactStore,
    replay_bundle_ref: ArtifactRef,
) -> ReplayBundleMeasurement:
    """Check replay-bundle dependencies and run semantic replay when snapshots exist."""
    from polisyos.scientist.policy_design.output import load_replayable_audit_bundle

    bundle = load_replayable_audit_bundle(cast("Any", store), replay_bundle_ref)
    refs: list[ArtifactRef] = []
    if bundle.candidate_ref is not None:
        refs.append(bundle.candidate_ref)
    if bundle.evaluation_ref is not None:
        refs.append(bundle.evaluation_ref)
    if bundle.readiness_ref is not None:
        refs.append(bundle.readiness_ref)
    refs.extend(bundle.upstream_audit_refs)
    refs.extend(bundle.actionable_side_information_refs)
    refs.extend(bundle.artifact_refs.values())
    refs.extend(bundle.runtime_input_refs.values())
    refs.extend(bundle.runtime_artifacts_index.values())
    refs.extend(bundle.runtime_reports_index.values())

    missing: list[MissingArtifact] = []
    total_size_bytes = 0
    for ref in refs:
        try:
            manifest = store.get_manifest(ref.artifact_id)
            total_size_bytes += int(getattr(manifest, "size_bytes", 0) or 0)
        except FileNotFoundError:
            missing.append(
                MissingArtifact(
                    artifact_id=str(ref.artifact_id),
                    role=str(ref.kind or "artifact"),
                    kind=ref.kind,
                    critical=True,
                    status=NodeStatus.MISSING,
                )
            )

    reason_codes: list[str] = []
    if bundle.candidate_ref is None:
        reason_codes.append("candidate_ref_missing")
    if bundle.evaluation_ref is None:
        reason_codes.append("evaluation_ref_missing")
    if missing:
        reason_codes.append("bundle_dependency_missing")

    completeness_level = (
        CompletenessLevel.COMPLETE
        if not missing and not reason_codes
        else CompletenessLevel.INCOMPLETE
    )
    completeness = CompletenessReport(
        level=completeness_level,
        strategy=ReplayStrategy.SCIENTIST,
        total_artifacts=len(refs),
        present_artifacts=max(len(refs) - len(missing), 0),
        missing=missing,
        total_size_bytes=total_size_bytes,
        reason_codes=sorted(set(reason_codes)),
    )
    if completeness.level != CompletenessLevel.COMPLETE:
        return ReplayBundleMeasurement(
            replay_bundle_ref=replay_bundle_ref,
            completeness=completeness,
            verification_mode="artifact_snapshot",
            passed=False,
            overall_similarity=0.0,
            reason_codes=list(completeness.reason_codes),
            details={
                "artifact_ref_count": len(refs),
                "trace_notes": list(bundle.trace_notes),
            },
        )

    if _bundle_has_runtime_snapshot(bundle):
        try:
            measured = _measure_scientist_replay_from_bundle(store, replay_bundle_ref, bundle)
            return ReplayBundleMeasurement(
                replay_bundle_ref=replay_bundle_ref,
                completeness=completeness,
                verification_mode=measured["verification_mode"],
                passed=bool(measured["passed"]),
                overall_similarity=float(measured["overall_similarity"]),
                reason_codes=list(measured["reason_codes"]),
                details=dict(measured["details"]),
            )
        except Exception as exc:
            return ReplayBundleMeasurement(
                replay_bundle_ref=replay_bundle_ref,
                completeness=completeness,
                verification_mode="semantic_diff",
                passed=False,
                overall_similarity=0.0,
                reason_codes=["replay_execution_failed"],
                details={
                    "artifact_ref_count": len(refs),
                    "trace_notes": list(bundle.trace_notes),
                    "replay_error": f"{type(exc).__name__}: {exc}",
                },
            )

    return ReplayBundleMeasurement(
        replay_bundle_ref=replay_bundle_ref,
        completeness=completeness,
        verification_mode="artifact_snapshot",
        passed=True,
        overall_similarity=1.0,
        reason_codes=["replay_execution_not_available"],
        details={
            "artifact_ref_count": len(refs),
            "trace_notes": list(bundle.trace_notes),
            "snapshot_only": True,
        },
    )


def _bundle_has_runtime_snapshot(bundle: Any) -> bool:
    return bool(
        bundle.runtime_input_refs
        and bundle.runtime_params_snapshot
        and (bundle.workflow_id or bundle.runtime_params_snapshot.get("workflow_id"))
    )


def _measure_scientist_replay_from_bundle(
    store: ArtifactStore,
    replay_bundle_ref: ArtifactRef,
    bundle: Any,
) -> dict[str, Any]:
    from polisyos.scientist.orchestration.engine.state import ExperimentState
    from polisyos.scientist.nodes.builtins.state_keys import (
        ARTIFACT_DECISION_PACKET_REF,
        ARTIFACT_SIMULATION_RESULT_REF,
    )
    from polisyos.scientist.replay.diff import compute_replay_diff
    from polisyos.scientist.orchestration.workflows.builder import run_selected_workflow

    replay_run_id = f"replay_bundle_{str(replay_bundle_ref.artifact_id)[7:19]}"
    params_snapshot = dict(bundle.runtime_params_snapshot or {})
    if bundle.workflow_id is not None:
        params_snapshot.setdefault("workflow_id", bundle.workflow_id)
    params_snapshot.setdefault("replay_mode", True)
    state = ExperimentState(
        schema_version="1.3",
        run_id=replay_run_id,
        inputs=dict(bundle.runtime_input_refs),
        artifacts_index=dict(bundle.runtime_artifacts_index),
        reports_index=dict(bundle.runtime_reports_index),
        params=params_snapshot,
        execution_profile=bundle.execution_profile,
    )
    replay_result = run_selected_workflow(initial_state=state, store=store)
    replay_state = replay_result.state
    replay_evaluation_ref = _resolve_replay_evaluation_ref(replay_state)
    if bundle.evaluation_ref is None or replay_evaluation_ref is None:
        raise ValueError("Measured replay requires both original and replayed evaluation refs.")
    original_payload = _load_artifact_payload_for_diff(store, bundle.evaluation_ref)
    replayed_payload = _load_artifact_payload_for_diff(store, replay_evaluation_ref)
    diff = compute_replay_diff(original_payload, replayed_payload)
    reason_codes: list[str] = []
    if not diff.structural_match:
        reason_codes.append("semantic_diff_exceeded_tolerance")
    return {
        "verification_mode": "semantic_diff",
        "passed": diff.structural_match,
        "overall_similarity": diff.overall_similarity,
        "reason_codes": reason_codes,
        "details": {
            "replay_run_id": replay_run_id,
            "replay_decision_packet_ref": _artifact_id_from_index(
                replay_state.artifacts_index,
                ARTIFACT_DECISION_PACKET_REF,
            ),
            "replay_simulation_result_ref": _artifact_id_from_index(
                replay_state.artifacts_index,
                ARTIFACT_SIMULATION_RESULT_REF,
            ),
            "replay_evaluation_ref": str(replay_evaluation_ref.artifact_id),
            "environment_diffs": [],
            "semantic_diff_summary": {
                "overall_similarity": diff.overall_similarity,
                "structural_match": diff.structural_match,
                "field_diff_count": len(diff.field_diffs),
            },
            "field_diffs": [item.model_dump(mode="json") for item in diff.field_diffs[:50]],
            "reason_codes": reason_codes,
        },
    }


def _resolve_replay_evaluation_ref(state: Any) -> ArtifactRef | None:
    raw = state.params.get("policy_evaluation_ref")
    if isinstance(raw, ArtifactRef):
        return raw
    if isinstance(raw, dict):
        try:
            return ArtifactRef.model_validate(raw)
        except Exception:
            return None
    return None


def _load_artifact_payload_for_diff(
    store: ArtifactStore,
    ref: ArtifactRef,
) -> dict[str, Any]:
    payload = from_canonical_bytes(store.get_bytes(ref.artifact_id))
    if isinstance(payload, dict):
        return payload
    return {"value": payload}


def _artifact_id_from_index(index: dict[str, ArtifactRef], key: str) -> str | None:
    ref = index.get(key)
    return None if ref is None else str(ref.artifact_id)


def completeness_check(
    store: ArtifactStore,
    packet_ref: ArtifactID,
    *,
    payload: dict[str, Any] | None = None,
    max_depth: int = 200,
    max_nodes: int = 10_000,
    verify_integrity: bool = True,
) -> CompletenessReport:
    """Traverse packet dependencies and classify missing/corrupted replay inputs.

    The root packet itself is always treated as critical. Missing non-critical
    side artifacts downgrade the report to `RECOVERABLE`; unresolved strategy,
    missing required roles, or corruption yield `INCOMPLETE`.
    """
    reasons: list[str] = []
    try:
        packet_payload = payload or _load_packet_payload(store, packet_ref)
    except (FileNotFoundError, OSError, TypeError, ValueError, RuntimeError) as exc:
        logger.debug("Failed to load replay packet payload: %s", exc)
        return CompletenessReport(
            level=CompletenessLevel.INCOMPLETE,
            strategy=ReplayStrategy.NONE,
            total_artifacts=1,
            present_artifacts=0,
            missing=[
                MissingArtifact(
                    artifact_id=str(packet_ref),
                    role="root",
                    kind="scientist.decision_packet",
                    critical=True,
                    status=NodeStatus.MISSING,
                )
            ],
            reason_codes=["packet_unreadable"],
        )

    strategy = determine_replay_strategy(packet_payload)
    if strategy == ReplayStrategy.NONE:
        reasons.append("strategy_unresolved")

    graph = resolve_dependency_graph(
        store,
        packet_ref,
        root_role="root",
        max_depth=max_depth,
        max_nodes=max_nodes,
        verify_integrity=verify_integrity,
    )
    payload_refs = _extract_payload_refs(packet_payload)
    roles_by_id: dict[str, set[str]] = {}
    for role, artifact_id in payload_refs:
        roles_by_id.setdefault(str(artifact_id), set()).add(role)
        if artifact_id.hex in graph.nodes:
            continue
        subgraph = resolve_dependency_graph(
            store,
            artifact_id,
            root_role=role,
            max_depth=max_depth,
            max_nodes=max_nodes,
            verify_integrity=verify_integrity,
        )
        _merge_graph(graph, subgraph)

    critical_roles = _critical_roles(strategy)
    missing: list[MissingArtifact] = []
    corrupted: list[MissingArtifact] = []

    snapshot_status = _snapshot_presence_status(graph, roles_by_id)
    for hex_id, node in graph.nodes.items():
        if node.status == NodeStatus.PRESENT:
            continue
        role = _resolve_role(node.role, roles_by_id.get(str(node.artifact_id)))
        critical = _is_critical_role(
            role,
            strategy=strategy,
            critical_roles=critical_roles,
            snapshot_status=snapshot_status,
        )
        item = MissingArtifact(
            artifact_id=f"sha256:{hex_id}",
            role=role,
            kind=node.kind,
            critical=critical,
            status=node.status,
        )
        if node.status == NodeStatus.CORRUPTED:
            corrupted.append(item)
        else:
            missing.append(item)

    required_missing = _missing_required_roles(strategy, payload_refs, snapshot_status)
    if required_missing:
        reasons.extend(required_missing)
    has_critical_missing = any(item.critical for item in missing) or len(corrupted) > 0
    has_missing = len(missing) > 0
    if strategy == ReplayStrategy.NONE or has_critical_missing or required_missing:
        level = CompletenessLevel.INCOMPLETE
    elif has_missing:
        level = CompletenessLevel.RECOVERABLE
    else:
        level = CompletenessLevel.COMPLETE

    present_count = sum(1 for node in graph.nodes.values() if node.status == NodeStatus.PRESENT)
    return CompletenessReport(
        level=level,
        strategy=strategy,
        total_artifacts=graph.total_artifacts,
        present_artifacts=present_count,
        missing=missing,
        corrupted=corrupted,
        total_size_bytes=graph.total_size_bytes,
        reason_codes=sorted(set(reasons)),
        graph=graph,
    )


def verify_replay(
    store: ArtifactStore,
    *,
    original_payload: dict[str, Any],
    replay_simulation_ref: ArtifactID | None,
    config: VerificationConfig,
) -> VerificationResult:
    """Compare original and replayed simulation outputs using the selected mode."""
    if config.mode == VerificationMode.SKIP:
        return VerificationResult(
            passed=True,
            mode=VerificationMode.SKIP,
            details={"reason": "verification_skipped"},
        )

    original_sim_ref = _extract_simulation_result_ref(original_payload)
    if config.mode == VerificationMode.BIT_EXACT:
        if original_sim_ref is None or replay_simulation_ref is None:
            return VerificationResult(
                passed=False,
                mode=VerificationMode.BIT_EXACT,
                details={"reason": "missing_simulation_result_ref"},
                original_ref=str(original_sim_ref) if original_sim_ref else None,
                replay_ref=str(replay_simulation_ref) if replay_simulation_ref else None,
            )
        passed = original_sim_ref == replay_simulation_ref
        return VerificationResult(
            passed=passed,
            mode=VerificationMode.BIT_EXACT,
            details={"match": passed},
            original_ref=str(original_sim_ref),
            replay_ref=str(replay_simulation_ref),
        )

    if original_sim_ref is None or replay_simulation_ref is None:
        return VerificationResult(
            passed=False,
            mode=VerificationMode.CI_BOUNDED,
            details={"reason": "missing_simulation_result_ref"},
            original_ref=str(original_sim_ref) if original_sim_ref else None,
            replay_ref=str(replay_simulation_ref) if replay_simulation_ref else None,
        )

    original_metrics = _load_metrics_values(store, original_sim_ref)
    replay_metrics = _load_metrics_values(store, replay_simulation_ref)
    mismatches: dict[str, dict[str, Any]] = {}
    tolerance = max(float(config.relative_tolerance), 0.0)
    for key in sorted(set(original_metrics) | set(replay_metrics)):
        if key not in original_metrics or key not in replay_metrics:
            mismatches[key] = {"reason": "missing_key"}
            continue
        a_val = original_metrics[key]
        b_val = replay_metrics[key]
        if isinstance(a_val, (int, float)) and isinstance(b_val, (int, float)):
            baseline = abs(float(a_val))
            diff = abs(float(a_val) - float(b_val))
            relative = diff / baseline if baseline > 1e-12 else diff
            if relative > tolerance:
                mismatches[key] = {
                    "original": a_val,
                    "replay": b_val,
                    "relative_diff": relative,
                    "tolerance": tolerance,
                }
            continue
        if a_val != b_val:
            mismatches[key] = {
                "original": a_val,
                "replay": b_val,
                "reason": "non_numeric_mismatch",
            }

    return VerificationResult(
        passed=len(mismatches) == 0,
        mode=VerificationMode.CI_BOUNDED,
        details={
            "confidence_level": config.confidence_level,
            "mismatches": mismatches,
        },
        original_ref=str(original_sim_ref),
        replay_ref=str(replay_simulation_ref),
    )


def _load_packet_payload(store: ArtifactStore, packet_ref: ArtifactID) -> dict[str, Any]:
    payload = from_canonical_bytes(store.get_bytes(packet_ref))
    if not isinstance(payload, dict):
        raise ValueError(f"DecisionPacket payload must be object, got: {type(payload).__name__}")
    return payload


def _extract_payload_refs(payload: dict[str, Any]) -> list[tuple[str, ArtifactID]]:
    refs: list[tuple[str, ArtifactID]] = []
    for section_name, section_prefix in (("inputs", "input"), ("artifacts", "artifact")):
        section = payload.get(section_name)
        if not isinstance(section, dict):
            continue
        for role, value in section.items():
            artifact_id = try_parse_artifact_id(value)
            if artifact_id is None:
                continue
            refs.append((f"{section_prefix}.{role}", artifact_id))
    return refs


def _merge_graph(target: DependencyGraph, source: DependencyGraph) -> None:
    for hex_id, src_node in source.nodes.items():
        dst_node = target.nodes.get(hex_id)
        if dst_node is None:
            target.nodes[hex_id] = src_node
            continue
        if dst_node.status != NodeStatus.PRESENT and src_node.status == NodeStatus.PRESENT:
            target.nodes[hex_id] = src_node
            continue
        if dst_node.role is None and src_node.role is not None:
            dst_node.role = src_node.role
    target.edges.extend(source.edges)


def _critical_roles(strategy: ReplayStrategy) -> frozenset[str]:
    if strategy == ReplayStrategy.FOUNDRY:
        return frozenset(
            {
                "artifact.exec_plan_ref",
                "artifact.lowered_ir_ref",
                "input.registry_bundle_ref",
                "input.input_bindings_ref",
            }
        )
    if strategy == ReplayStrategy.SCIENTIST:
        return frozenset(
            {
                "input.trinity_bundle_ref",
                "input.registry_bundle_ref",
                "input.input_bindings_ref",
            }
        )
    return frozenset()


def _resolve_role(node_role: str | None, payload_roles: set[str] | None) -> str:
    if payload_roles:
        return sorted(payload_roles)[0]
    return node_role or "unknown"


def _snapshot_presence_status(
    graph: DependencyGraph,
    roles_by_id: dict[str, set[str]],
) -> dict[str, bool]:
    status = dict.fromkeys(_STATE_SOURCE_ROLES, False)
    for artifact_ref, roles in roles_by_id.items():
        node = graph.nodes.get(ArtifactID.model_validate(artifact_ref).hex)
        if node is None or node.status != NodeStatus.PRESENT:
            continue
        for role in roles:
            if role in status:
                status[role] = True
    return status


def _is_critical_role(
    role: str,
    *,
    strategy: ReplayStrategy,
    critical_roles: frozenset[str],
    snapshot_status: dict[str, bool],
) -> bool:
    if role in critical_roles:
        return True
    if role in _STATE_SOURCE_ROLES:
        return not any(snapshot_status.values())
    return strategy == ReplayStrategy.NONE


def _missing_required_roles(
    strategy: ReplayStrategy,
    payload_refs: list[tuple[str, ArtifactID]],
    snapshot_status: dict[str, bool],
) -> list[str]:
    roles_present = {role for role, _ in payload_refs}
    missing: list[str] = []
    if strategy == ReplayStrategy.FOUNDRY:
        for required in (
            "artifact.exec_plan_ref",
            "artifact.lowered_ir_ref",
            "input.registry_bundle_ref",
            "input.input_bindings_ref",
        ):
            if required not in roles_present:
                missing.append(f"missing_required_role:{required}")
    if strategy == ReplayStrategy.SCIENTIST:
        for required in (
            "input.trinity_bundle_ref",
            "input.registry_bundle_ref",
            "input.input_bindings_ref",
        ):
            if required not in roles_present:
                missing.append(f"missing_required_role:{required}")
    snapshot_roles_present = roles_present & _STATE_SOURCE_ROLES
    if strategy in (ReplayStrategy.FOUNDRY, ReplayStrategy.SCIENTIST):
        if not snapshot_roles_present:
            missing.append("missing_required_snapshot_ref")
        elif not any(snapshot_status.values()):
            missing.append("missing_all_snapshot_artifacts")
    return missing


def _extract_simulation_result_ref(payload: dict[str, Any]) -> ArtifactID | None:
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, dict):
        return None
    return try_parse_artifact_id(artifacts.get("simulation_result_ref"))


def _load_metrics_values(store: ArtifactStore, sim_ref: ArtifactID) -> dict[str, float | int | str]:
    sim_payload = from_canonical_bytes(store.get_bytes(sim_ref))
    simulation_result = SimulationResult.model_validate(sim_payload)
    metrics_payload = from_canonical_bytes(
        store.get_bytes(simulation_result.metrics_ref.artifact_id)
    )
    metrics = Metrics.model_validate(metrics_payload)
    return dict(metrics.values)


__all__ = [
    "CompletenessLevel",
    "CompletenessReport",
    "MissingArtifact",
    "ReplayBundleMeasurement",
    "ReplayPlan",
    "ReplayStrategy",
    "SeedResolution",
    "VerificationConfig",
    "VerificationMode",
    "VerificationResult",
    "build_replay_plan",
    "compare_current_environment",
    "completeness_check",
    "determine_replay_strategy",
    "measure_replayable_audit_bundle",
    "normalize_artifact_id",
    "resolve_effective_seed",
    "set_global_seeds",
    "try_parse_artifact_id",
    "verify_replay",
]
