from __future__ import annotations

from decimal import Decimal

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.compiler.report import CompileReport
from polisyos.core.contracts.foundry import CompileRequest, ExecPlan, LoweredIR, ProgramGraph
from polisyos.core.registry import (
    build_default_registry_bundle,
    build_registry_bundle,
    load_registry_bundle_content,
)
from polisyos.foundry.compile.api import compile as compile_foundry
from polisyos.ir.governance.policy_spec import (
    InterventionSpec,
    MechanismBinding,
    PolicySpec,
)
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.kernel import (
    DEFAULT_CONSTRAINT_REGISTRY,
    DEFAULT_MECHANISM_REGISTRY,
    DEFAULT_MERGE_RULE_REGISTRY,
    DEFAULT_METRIC_REGISTRY,
    DEFAULT_SELECTOR_FIELD_REGISTRY,
    DEFAULT_SLOT_REGISTRY,
    DEFAULT_UNITS_REGISTRY,
    MechanismTypeSpec,
    ParamSpec,
    ParamType,
)
from polisyos.ir.linker import LinkIssueCode, LinkReport
from polisyos.ir.model_spec import FidelityLevel, ModelSpec
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
            schema=SchemaInfo(
                name="polisyos.ir.TrinityBundle", version=trinity_bundle.schema_version
            ),
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

    program_ref = next(ref.ref for ref in result.derived_refs if ref.role == "program_graph")
    payload = from_canonical_bytes(store.get_bytes(program_ref.artifact_id))
    graph = ProgramGraph.model_validate(payload)
    assert graph.ir_ref.kind == "ir.trinity_bundle"


def test_compile_trinity_lowers_bindings_and_fidelity(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    bundle = build_default_registry_bundle(store)
    trinity_bundle = TrinityBundle(
        problem_frame=ProblemFrame(problem_id="problem_warn", domain=ProblemDomain.FISCAL),
        policy_spec=PolicySpec(
            policy_id="policy_warn",
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
            mechanism_bindings=[
                MechanismBinding(
                    binding_id="binding_1",
                    mechanism_id="income_tax",
                    intervention_ids=["tax_cut"],
                )
            ],
        ),
        model_spec=ModelSpec(
            model_id="model_warn",
            data_snapshot_ref="sha256:0000000000000000000000000000000000000000000000000000000000000000",
            registry_bundle_ref=str(bundle.bundle_ref.artifact_id),
            fidelity_level=FidelityLevel.FULL_DISCRETE,
        ),
    )
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
    assert "link_warning:deprecated_mechanism_bindings" not in result.notes
    assert "link_warning:model_fidelity_level_ignored" not in result.notes
    lowered_ir_ref = next(ref.ref for ref in result.derived_refs if ref.role == "lowered_ir")
    lowered_ir_payload = from_canonical_bytes(store.get_bytes(lowered_ir_ref.artifact_id))
    lowered_ir = LoweredIR.model_validate(lowered_ir_payload)
    assert lowered_ir.mechanisms[0].binding_id == "binding_1"
    assert lowered_ir.mechanisms[0].selected_fidelity == "hard"

    compile_payload = from_canonical_bytes(store.get_bytes(result.compile_report_ref.artifact_id))
    compile_report = CompileReport.model_validate(compile_payload)
    assert compile_report.lowered_ir_ref is not None
    assert "trinity_coverage_audit:ok" in compile_report.semantic_closure_notes
    assert "link_warning:deprecated_mechanism_bindings" not in compile_report.notes
    assert "link_warning:model_fidelity_level_ignored" not in compile_report.notes

    exec_plan_payload = from_canonical_bytes(store.get_bytes(result.exec_plan_ref.artifact_id))
    exec_plan = ExecPlan.model_validate(exec_plan_payload)
    assert exec_plan.policy_fidelity_level == FidelityLevel.FULL_DISCRETE.value
    assert exec_plan.constraint_mode == "hard_soft_v1"

    link_payload = from_canonical_bytes(store.get_bytes(compile_report.link_report_ref.artifact_id))
    link_report = LinkReport.model_validate(link_payload)
    warning_codes = {
        issue.code for issue in link_report.issues if issue.severity.value == "warning"
    }
    assert LinkIssueCode.DEPRECATED_MECHANISM_BINDINGS not in warning_codes
    assert LinkIssueCode.MODEL_FIDELITY_LEVEL_IGNORED not in warning_codes


def test_compile_trinity_fails_on_binding_kind_mismatch(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    bundle = build_default_registry_bundle(store)
    trinity_bundle = TrinityBundle(
        problem_frame=ProblemFrame(
            problem_id="problem_binding_mismatch", domain=ProblemDomain.FISCAL
        ),
        policy_spec=PolicySpec(
            policy_id="policy_binding_mismatch",
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
            mechanism_bindings=[
                MechanismBinding(
                    binding_id="binding_1",
                    mechanism_id="tax_subsidy",
                    intervention_ids=["tax_cut"],
                )
            ],
        ),
        model_spec=ModelSpec(
            model_id="model_binding_mismatch",
            data_snapshot_ref="sha256:0000000000000000000000000000000000000000000000000000000000000000",
            registry_bundle_ref=str(bundle.bundle_ref.artifact_id),
        ),
    )
    policy_ref = _put_trinity_bundle(store, trinity_bundle)

    result = compile_foundry(
        store,
        CompileRequest(
            input_kind="trinity",
            policy_ref=policy_ref,
            registry_bundle_ref=bundle.bundle_ref,
        ),
    )

    assert result.ok is False
    assert (
        "semantic_lowering_failed:mechanism_binding_kind_mismatch:tax_cut:income_tax!=tax_subsidy"
        in result.notes
    )


def test_compile_trinity_fails_fast_when_mechanism_has_no_runtime_support(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    custom_registry = DEFAULT_MECHANISM_REGISTRY.model_copy(deep=True)
    custom_registry.mechanisms["custom_subsidy"] = MechanismTypeSpec(
        mechanism_id="custom_subsidy",
        params={
            "rate": ParamSpec(
                param_id="rate",
                required=True,
                value_type=ParamType.RATE,
            )
        },
        reads_slots=["agents.income"],
        writes_slots=["agents.income"],
        default_merge={"agents.income": "sum"},
    )
    bundle = build_registry_bundle(
        store,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        mechanism_registry=custom_registry,
        constraint_registry=DEFAULT_CONSTRAINT_REGISTRY,
        selector_field_registry=DEFAULT_SELECTOR_FIELD_REGISTRY,
        metric_registry=DEFAULT_METRIC_REGISTRY,
        units_registry=DEFAULT_UNITS_REGISTRY,
    )

    trinity_bundle = TrinityBundle(
        problem_frame=ProblemFrame(problem_id="problem_runtime_gap", domain=ProblemDomain.FISCAL),
        policy_spec=PolicySpec(
            policy_id="policy_runtime_gap",
            interventions=[
                InterventionSpec(
                    intervention_id="custom_tax_cut",
                    kind="custom_subsidy",
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
        ),
        model_spec=ModelSpec(
            model_id="model_runtime_gap",
            data_snapshot_ref="sha256:0000000000000000000000000000000000000000000000000000000000000000",
            registry_bundle_ref=str(bundle.bundle_ref.artifact_id),
        ),
    )
    policy_ref = _put_trinity_bundle(store, trinity_bundle)

    result = compile_foundry(
        store,
        CompileRequest(
            input_kind="trinity",
            policy_ref=policy_ref,
            registry_bundle_ref=bundle.bundle_ref,
        ),
    )

    assert result.ok is False
    assert result.exec_plan_ref is None
    assert "missing_runtime_mechanism_support:custom_subsidy" in result.notes

    compile_payload = from_canonical_bytes(store.get_bytes(result.compile_report_ref.artifact_id))
    compile_report = CompileReport.model_validate(compile_payload)
    assert "missing_runtime_mechanism_support:custom_subsidy" in compile_report.notes
