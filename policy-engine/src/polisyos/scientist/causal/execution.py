"""Public causal execution module API."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from polisyos.foundry.methods.catalog.causal.bounds_engine import BoundsEngineMethod
from polisyos.ir.analytics.partial_identification import BoundsBundle, persist_bounds_bundle
from polisyos.ir.artifacts import ArtifactStore, InputRef
from polisyos.ir.observation.causal_execution import BoundsEstimationEntry, BoundsEstimationTask


class BoundsEstimationRunner:
    """Runner that executes bounds-estimation tasks against Foundry methods.

    Consumes observation-layer `BoundsEstimationTask` contracts, invokes the
    partial-identification engine, persists any resulting `BoundsBundle`, and
    returns normalized execution entries for Scientist state.
    """

    def __init__(self, *, store: ArtifactStore) -> None:
        self.store = store

    def run(
        self,
        tasks: Sequence[BoundsEstimationTask | Mapping[str, Any]],
        *,
        inputs: Sequence[InputRef] | None = None,
    ) -> list[BoundsEstimationEntry]:
        """Execute one or more bounds-estimation tasks.

        Args:
            tasks: Typed tasks or task-like mappings resolved into IR contracts.
            inputs: Optional upstream artifact refs to attach as lineage inputs.

        Returns:
            Normalized bounds execution entries, one per task.
        """

        base_inputs = list(inputs or [])
        entries: list[BoundsEstimationEntry] = []
        for task in tasks:
            resolved_task = (
                task if isinstance(task, BoundsEstimationTask) else BoundsEstimationTask.model_validate(task)
            )
            family = resolved_task.bundle.channels[0].family
            warnings: list[str] = []
            try:
                params = self._effective_params(resolved_task)
                result = BoundsEngineMethod.pure_step(resolved_task.bounds_input, params)
                bundle = BoundsBundle.model_validate(result["bounds_report"])
                warnings.extend(bundle.warnings)
                bounds_ref = persist_bounds_bundle(
                    self.store,
                    bundle,
                    inputs=base_inputs,
                )
                interval = None
                width = None
                if bundle.lower_bound is not None and bundle.upper_bound is not None:
                    interval = (float(bundle.lower_bound), float(bundle.upper_bound))
                    width = float(bundle.upper_bound - bundle.lower_bound)
                informative_threshold = float(params.get("informative_threshold", 0.5))
                entries.append(
                    BoundsEstimationEntry(
                        task_id=resolved_task.task_id,
                        family=family,
                        status="ok",
                        interval=interval,
                        width=width,
                        informative=bool(width is not None and width < informative_threshold),
                        warnings=warnings,
                        bounds_bundle_ref=bounds_ref,
                        metadata={
                            "available_estimators": list(resolved_task.bundle.available_estimators),
                            "channel_strategies": [
                                channel.bound_strategy for channel in resolved_task.bundle.channels
                            ],
                            **dict(resolved_task.metadata),
                        },
                    )
                )
            except Exception as exc:
                warnings.append(str(exc))
                entries.append(
                    BoundsEstimationEntry(
                        task_id=resolved_task.task_id,
                        family=family,
                        status="blocked",
                        warnings=warnings,
                        metadata=dict(resolved_task.metadata),
                    )
                )
        return entries

    def _effective_params(self, task: BoundsEstimationTask) -> dict[str, Any]:
        """Infer execution flags from the task payload and merge explicit params."""

        inferred = {
            "has_iv": task.bounds_input.instrument is not None,
            "has_selection": task.bounds_input.selected is not None,
            "has_monotone": any(
                "mtr" in channel.bound_strategy.lower() or "monotone" in channel.bound_strategy.lower()
                for channel in task.bundle.channels
            ),
            "run_all": task.bounds_input.miv_proxy is not None,
            "use_auto_bounds": False,
        }
        return {**inferred, **dict(task.params)}


__all__ = ["BoundsEstimationRunner"]
