"""Read actual persisted native state before a removal selector asserts."""

from __future__ import annotations

import hashlib
import inspect
import json


def install_observation(probe):
    from polisyos.scientist.methods.search.service import NativeSearchService

    original = NativeSearchService.run_search

    def observed(service, *args, **kwargs):
        result = original(service, *args, **kwargs)
        from polisyos.core.artifacts.store import FileSystemCAS
        from polisyos.scientist.methods.search.pareto_registry import ParetoRegistry
        from polisyos.scientist.methods.search.run_state import (
            SearchRunState,
            checkpoint_json,
        )
        from polisyos.scientist.methods.search.service import _decode_checkpoint

        snapshot = FileSystemCAS(service._store.root).get_verified_snapshot(
            service.checkpoint_ref
        )
        raw = _decode_checkpoint(snapshot.data)
        saved = SearchRunState.from_checkpoint(raw["run_state"])
        registry = service.controller._config.pareto_registry
        fresh_registry = (
            ParetoRegistry(registry._root).get_snapshot(result.search_id)
            if registry is not None
            else None
        )
        closure = inspect.getclosurevars(service.controller._stage_b).nonlocals
        spec = closure.get("spec")
        physical_calls = (
            spec.benchmark_evaluator.calls
            if spec is not None and hasattr(spec.benchmark_evaluator, "calls")
            else None
        )
        print(  # noqa: T201
            "REMOVAL_PERSISTED_OBSERVATION:"
            + json.dumps(
                {
                    "probe": probe,
                    "checkpoint_ref": service.checkpoint_ref.model_dump(mode="json"),
                    "checkpoint_sha256": hashlib.sha256(snapshot.data).hexdigest(),
                    "configuration": raw["configuration"],
                    "physical_calls": physical_calls,
                    "history": [checkpoint_json(row) for row in saved.history],
                    "best_candidate": saved.best_candidate,
                    "best_objective": checkpoint_json(saved.best_objective),
                    "pareto_points": [row.as_payload() for row in saved.pareto_points],
                    "registry_entries": (
                        {
                            key: row.model_dump(mode="json")
                            for key, row in fresh_registry.entries.items()
                        }
                        if fresh_registry is not None
                        else None
                    ),
                },
                default=str,
                sort_keys=True,
            ),
            flush=True,
        )
        return result

    NativeSearchService.run_search = observed
