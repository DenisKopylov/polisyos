from __future__ import annotations

from decimal import Decimal

from polisyos.core.registry import build_default_registry_bundle, load_registry_bundle_content
from polisyos.core.contracts.foundry import CompileRequest
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.compile.api import compile as compile_foundry
from polisyos.foundry.compiler import put_policy_surface
from polisyos.ir.surface import PolicySemantic, PolicySurfaceIR
from polisyos.ir.types import SelectorOperator


def _program_ref(result):
    return next(ref.ref for ref in result.derived_refs if ref.role == "program_graph")


def test_compile_determinism(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    bundle = build_default_registry_bundle(store)
    registries = load_registry_bundle_content(store, bundle.bundle_ref)

    policy = PolicySurfaceIR(
        semantic=PolicySemantic(
            context_snapshot_ref="sha256:0000000000000000000000000000000000000000000000000000000000000000",
            interventions=[
                {
                    "intervention_id": "tax_cut",
                    "kind": "income_tax",
                    "target": {
                        "kind": "predicate",
                        "field": "id",
                        "operator": SelectorOperator.EQUALS,
                        "value": "all",
                    },
                    "schedule": {"start_step": 0, "duration_steps": 1},
                    "params": {"rate": Decimal("0.1")},
                }
            ],
        )
    )

    policy_ref = put_policy_surface(
        store,
        policy,
        mechanism_registry=registries.mechanism_registry,
        units_registry=registries.units_registry,
    )
    request = CompileRequest(
        input_kind="surface",
        policy_ref=policy_ref,
        registry_bundle_ref=bundle.bundle_ref,
    )

    result_a = compile_foundry(store, request)
    result_b = compile_foundry(store, request)

    assert result_a.exec_plan_ref is not None
    assert result_b.exec_plan_ref is not None
    assert (
        result_a.exec_plan_ref.artifact_id == result_b.exec_plan_ref.artifact_id
    )
    assert _program_ref(result_a).artifact_id == _program_ref(result_b).artifact_id
