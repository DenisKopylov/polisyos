"""Light preflight: canonical DesignProblem plus the real typed N5 builder."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from tempfile import TemporaryDirectory
from typing import Any

from polisyos.core.contracts.chronology import _canonical_raw_bytes
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.runtime.quality.generation_cycle import JointSimulationPort
from tests.unit.runtime.quality.test_generation_cycle import (
    REPO_ROOT,
    _owner_n5_case_with_selected_ncm_ref,
    _runtime_ncm_fixture_store,
)


def _float_paths(value: Any, path: str = "$") -> list[str]:
    """Enumerate every float in the complete runtime-hints object."""

    if isinstance(value, float):
        return [path]
    if isinstance(value, Mapping):
        return [
            found
            for key, item in value.items()
            for found in _float_paths(item, f"{path}.{key}")
        ]
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [
            found
            for index, item in enumerate(value)
            for found in _float_paths(item, f"{path}[{index}]")
        ]
    return []


def main() -> None:
    with TemporaryDirectory(prefix="n9-input-builder-preflight-") as temp_dir:
        store, expected_ncm, ncm_ref = _runtime_ncm_fixture_store(
            __import__("pathlib").Path(temp_dir)
        )
        try:
            problem, context, candidate = _owner_n5_case_with_selected_ncm_ref(
                ncm_ref,
                runtime_hints={"joint_simulation_baseline_state": {"firm_survival": 0}},
            )
            hint_float_paths = _float_paths(problem.runtime_hints)
            if hint_float_paths:
                raise AssertionError(f"runtime_hints_has_floats:{hint_float_paths}")
            canonical_bytes = _canonical_raw_bytes(problem.model_dump(mode="json"))
            if context.design_problem_ref is None:
                raise AssertionError("context_design_problem_ref_missing")

            port = JointSimulationPort(
                repo_root=REPO_ROOT,
                cycle_substrate_context=context,
                artifact_store=store,
            )
            with tenant_scope(None, tenant_id="tenant-n5-owner", cell_id="cell-n5-owner"):
                request = port._build_joint_simulation_request(
                    candidate=candidate,
                    problem=problem,
                )

            if request.baseline_state != {"firm_survival": 0.0}:
                raise AssertionError(
                    f"typed_builder_changed_baseline:{request.baseline_state!r}"
                )
            if request.engine_plan[0].engine_kind != "ncm_parallel_worlds":
                raise AssertionError(
                    f"typed_builder_changed_engine:{request.engine_plan[0].engine_kind!r}"
                )
            if request.engine_plan[0].ncm_spec != expected_ncm:
                raise AssertionError("typed_builder_changed_selected_ncm_semantics")
            if request.world_model_record.content_hash != context.world_model_record.content_hash:
                raise AssertionError("typed_builder_changed_wmr_binding")
            if tuple(request.intervention_atoms) != tuple(candidate.intervention_atoms):
                raise AssertionError("typed_builder_changed_atom_binding")

            print(
                "N9_INPUT_BUILDER_PREFLIGHT="
                + json.dumps(
                    {
                        "source_commit": "7ffbf5c71d6352f7712673a6591be5e553993745",
                        "source_tree": "221f31490189a5a2865f1ce2e4b335d6342d6bd6",
                        "design_problem_ref": context.design_problem_ref,
                        "canonical_problem_bytes_sha256": hashlib.sha256(
                            canonical_bytes
                        ).hexdigest(),
                        "canonical_problem_bytes": len(canonical_bytes),
                        "runtime_hints_float_paths": hint_float_paths,
                        "n5_invoked": False,
                        "typed_builder": "JointSimulationPort._build_joint_simulation_request",
                        "selected_engine": request.engine_plan[0].engine_kind,
                        "expected_baseline": {"firm_survival": 0.0},
                        "typed_baseline": request.baseline_state,
                        "expected_ncm_ref": ncm_ref,
                        "wmr_ncm_refs": context.world_model_record.simulation_model_ref.ncm_refs,
                        "ncm_model_matches_typed_builder": (
                            request.engine_plan[0].ncm_spec == expected_ncm
                        ),
                        "world_model_record_content_hash": (
                            request.world_model_record.content_hash
                        ),
                        "atom_ids": [atom.intervention_id for atom in request.intervention_atoms],
                        "selected_outcomes": list(request.selected_outcomes),
                        "horizon": request.horizon.model_dump(mode="json"),
                        "manifest_inputs": [],
                    },
                    sort_keys=True,
                    default=str,
                )
            )
        finally:
            store.close()


if __name__ == "__main__":
    main()
