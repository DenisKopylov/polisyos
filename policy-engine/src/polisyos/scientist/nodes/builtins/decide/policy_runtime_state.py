"""State and registry helpers for policy runtime orchestration."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path
from tempfile import NamedTemporaryFile

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.methods.search.transfer_context import (
    TransferContext,
    TransferTenantScopeStatus,
    resolve_transfer_context,
)
from polisyos.scientist.methods.search.voi_scheduler import (
    PredictiveVOIScheduler,
    VOIModelSnapshot,
    VOITrainingConfig,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState

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
    transfer_context: Mapping[str, object] | TransferContext,
) -> Path | None:
    """Return the persisted VOI path for an authenticated or run-local scope.

    Authenticated tenant paths retain their existing location. Unknown and
    declared-unscoped scopes use a status-separated, run-bound candidate cache;
    an absent/sentinel run identity has no reusable cache path. Legacy global
    snapshots are never read or migrated into candidate scope.
    """
    store_root = getattr(ctx.store, "root", None)
    if store_root is None:
        raise ValueError("policy runtime VOI persistence requires a filesystem-backed store root")
    scope = resolve_transfer_context(context={"transfer_context": transfer_context})
    if scope.tenant_scope_status is TransferTenantScopeStatus.AUTHENTICATED:
        assert scope.tenant_hash is not None
        tenant_scope = scope.tenant_hash
    else:
        run_id = scope.run_id.strip()
        if not run_id or run_id.casefold() == "unknown":
            return None
        run_digest = hashlib.sha256(run_id.encode("utf-8")).hexdigest()
        tenant_scope = f"candidate-{scope.tenant_scope_status.value}-{run_digest}"
    safe_name = (
        f"{scope.task_family}::{scope.domain}::{tenant_scope}".replace("/", "_")
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
    if path is None or not path.exists():
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
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = scheduler.snapshot().model_dump_json(indent=2)
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as tmp:
        tmp.write(payload)
        temp_path = Path(tmp.name)
    temp_path.replace(path)
