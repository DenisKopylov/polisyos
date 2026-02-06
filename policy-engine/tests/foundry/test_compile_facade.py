from __future__ import annotations

from decimal import Decimal

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.foundry import CompileRequest, ProgramGraph
from polisyos.core.registry import build_default_registry_bundle, load_registry_bundle_content
from polisyos.foundry.compile.api import compile as compile_foundry
from polisyos.ir.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.model_spec import ModelSpec
from polisyos.ir.trinity import TrinityBundle
from polisyos.ir.types import SelectorOperator


def _build_trinity_bundle(registry_bundle_ref: str) -> TrinityBundle:
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
        registry_bundle_ref=registry_bundle_ref,
    )
    return TrinityBundle(
        problem_frame=problem_frame,
        policy_spec=policy_spec,
        model_spec=model_spec,
    )


def _put_trinity_bundle(store: FileSystemCAS, trinity_bundle: TrinityBundle):
    return store.put_json(
        trinity_bundle,
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version=trinity_bundle.schema_version),
        ),
    )


def test_compile_auto_facade(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    bundle = build_default_registry_bundle(store)
    _ = load_registry_bundle_content(store, bundle.bundle_ref)
    trinity_bundle = _build_trinity_bundle(str(bundle.bundle_ref.artifact_id))
    policy_ref = _put_trinity_bundle(store, trinity_bundle)

    result = compile_foundry(
        store,
        CompileRequest(
            input_kind="auto",
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
    trinity_bundle = _build_trinity_bundle(str(bundle.bundle_ref.artifact_id))
    policy_ref = _put_trinity_bundle(store, trinity_bundle)

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
