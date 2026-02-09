from __future__ import annotations

from decimal import Decimal

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.registry import build_default_registry_bundle, load_registry_bundle_content
from polisyos.core.contracts.foundry import CompileRequest
from polisyos.foundry.compile.api import compile as compile_foundry
from polisyos.ir.model_spec import ModelSpec
from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.governance.selector_expr import SelectorPredicate
from polisyos.ir.trinity import TrinityBundle
from polisyos.ir.types import SelectorOperator


def _program_ref(result):
    return next(ref.ref for ref in result.derived_refs if ref.role == "program_graph")


def _put_trinity_bundle(store: FileSystemCAS, registry_bundle_ref: str) -> object:
    bundle = TrinityBundle(
        problem_frame=ProblemFrame(problem_id="problem_1", domain=ProblemDomain.FISCAL),
        policy_spec=PolicySpec(
            policy_id="policy_1",
            interventions=[
                InterventionSpec(
                    intervention_id="tax_cut",
                    kind="income_tax",
                    target=SelectorPredicate(
                        field="id",
                        operator=SelectorOperator.EQUALS,
                        value="all",
                    ),
                    schedule=ScheduleSpec(start_step=0, duration_steps=1),
                    params={"rate": Decimal("0.1")},
                )
            ],
        ),
        model_spec=ModelSpec(
            model_id="model_1",
            data_snapshot_ref="sha256:0000000000000000000000000000000000000000000000000000000000000000",
            registry_bundle_ref=registry_bundle_ref,
        ),
    )
    return store.put_json(
        bundle,
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version=bundle.schema_version),
        ),
    )


def test_compile_determinism(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    bundle = build_default_registry_bundle(store)
    load_registry_bundle_content(store, bundle.bundle_ref)
    policy_ref = _put_trinity_bundle(store, str(bundle.bundle_ref.artifact_id))
    request = CompileRequest(
        input_kind="trinity",
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
