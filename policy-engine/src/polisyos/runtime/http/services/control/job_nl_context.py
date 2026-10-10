"""Typed internal state shared by natural-language control-job lifecycle facets."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from contextlib import AbstractContextManager
    from decimal import Decimal
    from typing import Any

    from polisyos.core import run
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.runtime.http.services.control.job_scope_admission import (
        _ControlEvaluationSafetyResult,
    )
    from polisyos.runtime.quality.evaluation_modes import ExecutionIntentBand

    from ..control_plane_store import (
        ControlJobExecutionAdmission,
        ControlJobExecutionScope,
        ControlJobRecord,
    )
    from .generation_cycle import RecursiveBudgetResolution


@dataclass(slots=True)
class _ControlNLJobContext:
    """Prepared inputs shared by NL admission, execution, and publication."""

    job: ControlJobRecord
    admission: ControlJobExecutionAdmission
    execution_scope: ControlJobExecutionScope
    payload: dict[str, Any]
    capability_manifest_ref: str
    execution_intent_binding: dict[str, Any]
    intent_band: ExecutionIntentBand
    evaluation_safety: _ControlEvaluationSafetyResult | None
    execution_intent: str
    execution_intent_limitation: str | None
    model_name: str
    compiler_context: dict[str, object]
    trusted_source_context: dict[str, object | None]
    profile_id: object
    candidate_simulation_context_binding: dict[str, object] = field(default_factory=dict)
    candidate_simulation_currentness_resolver: Callable[[], bool] | None = None
    cycle_substrate_context_resolver: Callable[[object], object | None] | None = None
    recursive_leaf_context_owner: object | None = None
    recursive_budget_resolution: RecursiveBudgetResolution | None = None
    max_cycles: int | None = None
    budget_usd: Decimal | None = None
    producer_run_binding_scope: AbstractContextManager[Any] | None = None
    start_core_attempt_callback: Callable[[], tuple[str, run.RunContext]] | None = None
    core_run_id: str | None = None
    core_run_context: run.RunContext | None = None
    cycle_substrate_context_job_ref: str | None = None
    cycle_substrate_context_job_selected_ref: ArtifactRef | None = None

    def start_core_attempt(self) -> tuple[str, run.RunContext]:
        """Start or return the admitted Core attempt and retain its identity."""
        callback = self.start_core_attempt_callback
        if callback is None:
            raise RuntimeError("control_job_core_run_attempt_callback_not_established")
        self.core_run_id, self.core_run_context = callback()
        return self.core_run_id, self.core_run_context
