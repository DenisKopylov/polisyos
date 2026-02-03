from __future__ import annotations

from decimal import Decimal

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.foundry import CompileRequest
from polisyos.core.registry import build_default_registry_bundle, load_registry_bundle_content
from polisyos.foundry.compile.api import compile as compile_foundry
from polisyos.foundry.compiler import put_policy_surface
from polisyos.ir.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.surface import PolicySemantic, PolicySurfaceIR
from polisyos.ir.trinity import TrinityBundle
from polisyos.ir.model_spec import ModelSpec
from polisyos.ir.types import SelectorOperator
from polisyos.core.contracts.foundry import ProgramGraph


def test_compile_surface_facade(tmp_path) -> None:
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

    result = compile_foundry(
        store,
        CompileRequest(
            input_kind="surface",
            policy_ref=policy_ref,
            registry_bundle_ref=bundle.bundle_ref,
        ),
    )

    assert result.ok is True
    assert result.exec_plan_ref is not None
    assert result.exec_plan_ref.kind == "foundry.exec_plan"
    assert any(ref.role == "program_graph" for ref in result.derived_refs)


def test_compile_trinity_facade(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    bundle = build_default_registry_bundle(store)

    problem_frame = ProblemFrame(problem_id="problem_1", domain=ProblemDomain.FISCAL)
    policy_spec = PolicySpec(
        policy_id="policy_1",
        interventions=[
            InterventionSpec(
                intervention_id="tax_cut",
                kind="income_tax",
                target={
                    "kind": "predicate",
                    "field": "id",
                    "operator": SelectorOperator.EQUALS,
                    "value": "all",
                },
                schedule={"start_step": 0, "duration_steps": 1},
                params={"rate": Decimal("0.1")},
            )
        ],
    )
    model_spec = ModelSpec(
        model_id="model_1",
        data_snapshot_ref="sha256:0000000000000000000000000000000000000000000000000000000000000000",
        registry_bundle_ref=str(bundle.bundle_ref.artifact_id),
    )
    trinity_bundle = TrinityBundle(
        problem_frame=problem_frame,
        policy_spec=policy_spec,
        model_spec=model_spec,
    )

    policy_ref = store.put_json(
        trinity_bundle,
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version=trinity_bundle.schema_version),
        ),
    )

    result = compile_foundry(
        store,
        CompileRequest(
            input_kind="trinity",
            policy_ref=policy_ref,
            registry_bundle_ref=bundle.bundle_ref,
        ),
    )

    assert result.ok is True
    assert result.exec_plan_ref is not None

    program_ref = next(
        ref.ref for ref in result.derived_refs if ref.role == "program_graph"
    )
    payload = from_canonical_bytes(store.get_bytes(program_ref.artifact_id))
    graph = ProgramGraph.model_validate(payload)
    assert graph.ir_ref.kind == "ir.trinity_bundle"
