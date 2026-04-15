"""State and registry helpers for policy runtime orchestration."""

from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.search.voi_scheduler import (
    PredictiveVOIScheduler,
    VOIModelSnapshot,
    VOITrainingConfig,
)

__all__ = [
    "load_predictive_voi_scheduler",
    "maybe_artifact_ref",
    "persist_predictive_voi_scheduler",
    "policy_runtime_input_signature",
    "predictive_voi_snapshot_path",
]


def maybe_artifact_ref(value: object) -> ArtifactRef | None:
    """Best-effort artifact-ref normalization for runtime payloads."""
    if isinstance(value, ArtifactRef):
        return value
    if isinstance(value, dict):
        try:
            return ArtifactRef.model_validate(value)
        except (TypeError, ValueError):
            return None
    return None


def policy_runtime_input_signature(
    *,
    candidate_ref: ArtifactRef,
    state: ExperimentState,
) -> str:
    """Build a stable signature for policy-runtime input materialization."""
    parts = [
        str(candidate_ref.artifact_id),
        str(state.artifacts_index.get("causal_report_ref", "")),
        str(state.artifacts_index.get("distributional_report_ref", "")),
        str(state.artifacts_index.get("cross_graph_evidence_profile_ref", "")),
        str(state.artifacts_index.get("causal_envelope_ref", "")),
        str(state.reports_index.get("governance_report_ref", "")),
    ]
    return "|".join(parts)


def predictive_voi_snapshot_path(
    ctx: ExecutionContext,
    *,
    transfer_context: dict[str, object],
) -> Path:
    """Return the persisted VOI snapshot location for one policy runtime scope."""
    store_root = getattr(ctx.store, "root", None)
    if store_root is None:
        raise ValueError("policy runtime VOI persistence requires a filesystem-backed store root")
    task_family = str(transfer_context.get("task_family") or "policy").strip() or "policy"
    domain = str(transfer_context.get("domain") or "unknown").strip() or "unknown"
    tenant_scope = str(transfer_context.get("tenant_hash") or "global").strip() or "global"
    safe_name = (
        f"{task_family}::{domain}::{tenant_scope}"
        .replace("/", "_")
        .replace("\\", "_")
        .replace(":", "_")
    )
    return Path(store_root) / "search_registry" / "voi" / f"{safe_name}.json"


def load_predictive_voi_scheduler(
    ctx: ExecutionContext,
    *,
    transfer_context: dict[str, object],
) -> PredictiveVOIScheduler:
    """Load a bounded VOI snapshot when present, otherwise create a cold scheduler."""
    path = predictive_voi_snapshot_path(ctx, transfer_context=transfer_context)
    if not path.exists():
        return PredictiveVOIScheduler(training_config=VOITrainingConfig(cross_domain_weight=0.0))
    snapshot = VOIModelSnapshot.model_validate_json(path.read_text(encoding="utf-8"))
    return PredictiveVOIScheduler.from_snapshot(snapshot)


def persist_predictive_voi_scheduler(
    ctx: ExecutionContext,
    *,
    transfer_context: dict[str, object],
    scheduler: PredictiveVOIScheduler,
) -> None:
    """Persist VOI scheduler state atomically to the registry snapshot path."""
    path = predictive_voi_snapshot_path(ctx, transfer_context=transfer_context)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = scheduler.snapshot().model_dump_json(indent=2)
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as tmp:
        tmp.write(payload)
        temp_path = Path(tmp.name)
    temp_path.replace(path)
