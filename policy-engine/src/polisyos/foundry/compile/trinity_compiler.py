from __future__ import annotations

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.compiler.report import CompileReport, put_compile_report, put_link_report
from polisyos.core.contracts.foundry import (
    CompileRequest,
    CompileResult,
    DerivedArtifact,
    ExecPlan,
    ExecPlanRef,
    ProgramGraphRef,
)
from polisyos.core.registry import load_registry_bundle_content
from polisyos.foundry.conflict_checker import CompileTimeConflictChecker
from polisyos.foundry.cost_model import CostBudget, CostModel
from polisyos.foundry.layout import build_slot_layout
from polisyos.foundry.mechanisms import build_treasury_plan
from polisyos.ir.linker import link_trinity
from polisyos.ir.linker.reports import LinkSeverity
from polisyos.ir.registry_fragments import RegistryBundle
from polisyos.ir.trinity import TrinityBundle

from ._graph import build_exec_order, build_program_graph
from ._lowering import lower_trinity


def compile_trinity(store: FileSystemCAS, request: CompileRequest) -> CompileResult:
    policy_ref = request.policy_ref
    payload = from_canonical_bytes(store.get_bytes(policy_ref.artifact_id))
    bundle = TrinityBundle.model_validate(payload)

    registry_bundle_ref = _resolve_registry_bundle_ref(
        request.registry_bundle_ref, bundle.model_spec.registry_bundle_ref
    )
    if registry_bundle_ref is None:
        return _compile_error(
            store,
            ok=False,
            policy_ref=policy_ref,
            registry_bundle_ref=None,
            link_report_ref=None,
            notes=["missing_registry_bundle"],
            lowered_ir_ref=None,
            semantic_closure_notes=[],
        )

    registry_content = load_registry_bundle_content(store, registry_bundle_ref)

    registries = RegistryBundle(
        mechanisms=registry_content.mechanism_registry,
        slots=registry_content.slot_registry,
        merge_rules=registry_content.merge_registry,
        constraints=registry_content.constraint_registry,
        selector_fields=registry_content.selector_field_registry,
        units=registry_content.units_registry,
        metrics=registry_content.metric_registry,
    )

    link_inputs = [
        InputRef(artifact_id=policy_ref.artifact_id, role="ir"),
        InputRef(artifact_id=registry_bundle_ref.artifact_id, role="registry_bundle"),
    ]
    linked_bundle, link_report = link_trinity(
        bundle,
        registries,
        allow_extra_params=request.validation_flags.allow_extra_params,
        strict=request.validation_flags.strict_link,
    )
    link_report_ref = put_link_report(store, link_report, inputs=link_inputs)
    compile_notes = _link_warning_notes(link_report)

    if request.validation_flags.strict_link and not link_report.ok:
        return _compile_error(
            store,
            ok=False,
            policy_ref=policy_ref,
            registry_bundle_ref=registry_bundle_ref,
            link_report_ref=link_report_ref,
            notes=compile_notes + ["link_failed"],
            lowered_ir_ref=None,
            semantic_closure_notes=[],
        )

    try:
        lowered_ir_ref, lowered_ir, semantic_notes = lower_trinity(
            store,
            policy_ref=policy_ref,
            registry_bundle_ref=registry_bundle_ref,
            bundle=bundle,
            linked_bundle=linked_bundle,
            registry_content=registry_content,
            strict=request.validation_flags.strict_schema,
        )
    except Exception as exc:
        lowering_error = str(exc)
        lowering_notes = list(compile_notes)
        if lowering_error.startswith("missing_runtime_mechanism_support:"):
            lowering_notes.append(lowering_error)
        lowering_notes.append(f"semantic_lowering_failed:{lowering_error}")
        return _compile_error(
            store,
            ok=False,
            policy_ref=policy_ref,
            registry_bundle_ref=registry_bundle_ref,
            link_report_ref=link_report_ref,
            notes=lowering_notes,
            lowered_ir_ref=None,
            semantic_closure_notes=[],
        )

    program_graph, params_refs = build_program_graph(
        store,
        ir_ref=policy_ref,
        lowered_ir_ref=lowered_ir_ref,
        mechanisms=lowered_ir.mechanisms,
        constraint_ids=[item.constraint_id for item in lowered_ir.constraints],
    )

    conflict_checker = CompileTimeConflictChecker(
        slot_registry=registry_content.slot_registry,
        merge_registry=registry_content.merge_registry,
        strict_mode=request.validation_flags.strict_conflict_check,
    )
    conflict_report = conflict_checker.check(program_graph)
    if not conflict_report.ok and request.validation_flags.strict_conflict_check:
        return _compile_error(
            store,
            ok=False,
            policy_ref=policy_ref,
            registry_bundle_ref=registry_bundle_ref,
            link_report_ref=link_report_ref,
            notes=compile_notes
            + [
                f"conflict_check_failed:{len(conflict_report.conflicts)}",
            ],
            lowered_ir_ref=lowered_ir_ref,
            semantic_closure_notes=semantic_notes,
        )

    cost_budget = _build_cost_budget(request)
    if cost_budget is not None:
        cost_model = CostModel()
        n_agents = (
            request.compile_config.estimate_n_agents
            if request.compile_config.estimate_n_agents is not None
            else 1000
        )
        time_steps = (
            request.compile_config.estimate_time_steps
            if request.compile_config.estimate_time_steps is not None
            else 100
        )
        estimate = cost_model.estimate(
            program_graph,
            n_agents=n_agents,
            time_steps=time_steps,
            budget=cost_budget,
        )
        if estimate.exceeds_budget:
            return _compile_error(
                store,
                ok=False,
                policy_ref=policy_ref,
                registry_bundle_ref=registry_bundle_ref,
                link_report_ref=link_report_ref,
                notes=compile_notes + ["cost_budget_exceeded"],
                lowered_ir_ref=lowered_ir_ref,
                semantic_closure_notes=semantic_notes,
            )

    program_inputs = _program_graph_inputs(
        policy_ref=policy_ref,
        registry_bundle_ref=registry_bundle_ref,
        link_report_ref=link_report_ref,
        lowered_ir_ref=lowered_ir_ref,
        params_refs=params_refs,
    )
    program_ref = store.put_json(
        program_graph,
        PutOptions(
            kind="foundry.program_graph",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.ProgramGraph", version="0.2.0"),
            inputs=program_inputs,
        ),
    )
    program_graph_ref = ProgramGraphRef(artifact_id=program_ref.artifact_id)

    order = build_exec_order(program_graph)
    exec_plan = ExecPlan(
        program_ref=program_graph_ref,
        order=order,
        determinism_tier=request.compile_config.determinism_tier,
        random_seed=request.compile_config.random_seed,
        nan_guard_enabled=request.compile_config.nan_guard_enabled,
        policy_fidelity_level=lowered_ir.policy_fidelity_level,
        constraint_mode=lowered_ir.constraint_mode,
        mode=request.compile_config.mode,
        jit=request.compile_config.jit,
        max_steps=request.compile_config.max_steps,
        notes=semantic_notes,
    )
    exec_plan_payload_ref = store.put_json(
        exec_plan,
        PutOptions(
            kind="foundry.exec_plan",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.ExecPlan", version="0.2.0"),
            inputs=[InputRef(artifact_id=program_graph_ref.artifact_id, role="program_graph")],
        ),
    )
    exec_plan_ref = ExecPlanRef(artifact_id=exec_plan_payload_ref.artifact_id)

    slot_layout = build_slot_layout(registry_content.slot_registry)
    slot_layout_ref = store.put_json(
        slot_layout,
        PutOptions(
            kind="foundry.slot_layout",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.foundry.SlotLayout", version=slot_layout.schema_version),
            inputs=[InputRef(artifact_id=program_graph_ref.artifact_id, role="program_graph")],
        ),
    )

    treasury_plan = build_treasury_plan(program_graph)
    treasury_plan_ref = store.put_json(
        treasury_plan,
        PutOptions(
            kind="foundry.treasury_plan",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.foundry.TreasuryPlan", version=treasury_plan.schema_version
            ),
            inputs=[InputRef(artifact_id=program_ref.artifact_id, role="program_graph")],
        ),
    )

    compile_report = CompileReport(
        ok=True,
        policy_ref=policy_ref,
        registry_bundle_ref=registry_bundle_ref,
        link_report_ref=link_report_ref,
        lowered_ir_ref=lowered_ir_ref,
        program_graph_ref=program_graph_ref,
        exec_plan_ref=exec_plan_ref,
        slot_layout_ref=slot_layout_ref,
        treasury_plan_ref=treasury_plan_ref,
        semantic_closure_notes=semantic_notes,
        notes=compile_notes,
    )
    compile_inputs = _compile_inputs(
        policy_ref=policy_ref,
        registry_bundle_ref=registry_bundle_ref,
        link_report_ref=link_report_ref,
        lowered_ir_ref=lowered_ir_ref,
        program_graph_ref=program_graph_ref,
        exec_plan_ref=exec_plan_ref,
        slot_layout_ref=slot_layout_ref,
        treasury_plan_ref=treasury_plan_ref,
    )
    compile_report_ref = put_compile_report(store, compile_report, inputs=compile_inputs)

    derived_refs = [
        DerivedArtifact(role="lowered_ir", ref=lowered_ir_ref),
        DerivedArtifact(role="program_graph", ref=program_graph_ref),
        DerivedArtifact(role="exec_plan", ref=exec_plan_ref),
        DerivedArtifact(role="link_report", ref=link_report_ref),
        DerivedArtifact(role="slot_layout", ref=slot_layout_ref),
        DerivedArtifact(role="treasury_plan", ref=treasury_plan_ref),
    ]

    return CompileResult(
        ok=True,
        exec_plan_ref=exec_plan_ref,
        compile_report_ref=compile_report_ref,
        derived_refs=derived_refs,
        notes=_merge_notes(compile_notes, semantic_notes),
    )


def _resolve_registry_bundle_ref(
    request_ref: ArtifactRef | None, model_spec_ref: str | None
) -> ArtifactRef | None:
    if request_ref is not None:
        return request_ref
    if model_spec_ref is None:
        return None
    return ArtifactRef(
        artifact_id=ArtifactID.model_validate(model_spec_ref),
        kind="core.registry_bundle",
        media_type="application/json",
    )


def _program_graph_inputs(
    *,
    policy_ref: ArtifactRef,
    registry_bundle_ref: ArtifactRef | None,
    link_report_ref: ArtifactRef | None,
    lowered_ir_ref: ArtifactRef | None,
    params_refs: dict[str, ArtifactRef],
) -> list[InputRef]:
    inputs = [InputRef(artifact_id=policy_ref.artifact_id, role="ir")]
    if registry_bundle_ref is not None:
        inputs.append(
            InputRef(artifact_id=registry_bundle_ref.artifact_id, role="registry_bundle")
        )
    if link_report_ref is not None:
        inputs.append(InputRef(artifact_id=link_report_ref.artifact_id, role="link_report"))
    if lowered_ir_ref is not None:
        inputs.append(InputRef(artifact_id=lowered_ir_ref.artifact_id, role="lowered_ir"))
    for node_id, ref in sorted(params_refs.items()):
        inputs.append(InputRef(artifact_id=ref.artifact_id, role=f"params:{node_id}"))
    return inputs


def _compile_inputs(
    *,
    policy_ref: ArtifactRef,
    registry_bundle_ref: ArtifactRef | None,
    link_report_ref: ArtifactRef | None,
    lowered_ir_ref: ArtifactRef | None,
    program_graph_ref: ArtifactRef | None,
    exec_plan_ref: ArtifactRef | None,
    slot_layout_ref: ArtifactRef | None,
    treasury_plan_ref: ArtifactRef | None,
) -> list[InputRef]:
    inputs = [InputRef(artifact_id=policy_ref.artifact_id, role="ir")]
    if registry_bundle_ref is not None:
        inputs.append(
            InputRef(artifact_id=registry_bundle_ref.artifact_id, role="registry_bundle")
        )
    if link_report_ref is not None:
        inputs.append(InputRef(artifact_id=link_report_ref.artifact_id, role="link_report"))
    if lowered_ir_ref is not None:
        inputs.append(InputRef(artifact_id=lowered_ir_ref.artifact_id, role="lowered_ir"))
    if program_graph_ref is not None:
        inputs.append(
            InputRef(artifact_id=program_graph_ref.artifact_id, role="program_graph")
        )
    if exec_plan_ref is not None:
        inputs.append(InputRef(artifact_id=exec_plan_ref.artifact_id, role="exec_plan"))
    if slot_layout_ref is not None:
        inputs.append(InputRef(artifact_id=slot_layout_ref.artifact_id, role="slot_layout"))
    if treasury_plan_ref is not None:
        inputs.append(
            InputRef(artifact_id=treasury_plan_ref.artifact_id, role="treasury_plan")
        )
    return inputs


def _compile_error(
    store: FileSystemCAS,
    *,
    ok: bool,
    policy_ref: ArtifactRef,
    registry_bundle_ref: ArtifactRef | None,
    link_report_ref: ArtifactRef | None,
    lowered_ir_ref: ArtifactRef | None,
    semantic_closure_notes: list[str],
    notes: list[str],
) -> CompileResult:
    compile_report = CompileReport(
        ok=ok,
        policy_ref=policy_ref,
        registry_bundle_ref=registry_bundle_ref,
        link_report_ref=link_report_ref,
        lowered_ir_ref=lowered_ir_ref,
        semantic_closure_notes=semantic_closure_notes,
        notes=notes,
    )
    compile_inputs = _compile_inputs(
        policy_ref=policy_ref,
        registry_bundle_ref=registry_bundle_ref,
        link_report_ref=link_report_ref,
        lowered_ir_ref=lowered_ir_ref,
        program_graph_ref=None,
        exec_plan_ref=None,
        slot_layout_ref=None,
        treasury_plan_ref=None,
    )
    compile_report_ref = put_compile_report(store, compile_report, inputs=compile_inputs)

    derived_refs: list[DerivedArtifact] = []
    if lowered_ir_ref is not None:
        derived_refs.append(DerivedArtifact(role="lowered_ir", ref=lowered_ir_ref))
    if link_report_ref is not None:
        derived_refs.append(DerivedArtifact(role="link_report", ref=link_report_ref))
    return CompileResult(
        ok=ok,
        exec_plan_ref=None,
        compile_report_ref=compile_report_ref,
        derived_refs=derived_refs,
        notes=notes,
    )


def _build_cost_budget(request: CompileRequest) -> CostBudget | None:
    config = request.compile_config
    if (
        config.cost_budget_max_total_ms is None
        and config.cost_budget_max_memory_mb is None
        and config.cost_budget_max_compile_ms is None
        and config.cost_budget_max_per_mechanism_ms is None
    ):
        return None
    defaults = CostBudget()
    return CostBudget(
        max_total_ms=(
            config.cost_budget_max_total_ms
            if config.cost_budget_max_total_ms is not None
            else defaults.max_total_ms
        ),
        max_memory_mb=(
            config.cost_budget_max_memory_mb
            if config.cost_budget_max_memory_mb is not None
            else defaults.max_memory_mb
        ),
        max_compile_ms=(
            config.cost_budget_max_compile_ms
            if config.cost_budget_max_compile_ms is not None
            else defaults.max_compile_ms
        ),
        max_per_mechanism_ms=(
            config.cost_budget_max_per_mechanism_ms
            if config.cost_budget_max_per_mechanism_ms is not None
            else defaults.max_per_mechanism_ms
        ),
    )


def _link_warning_notes(link_report) -> list[str]:
    notes: list[str] = []
    for issue in getattr(link_report, "issues", []):
        if issue.severity != LinkSeverity.WARNING:
            continue
        token = f"link_warning:{issue.code.value}"
        if token not in notes:
            notes.append(token)
    return notes


def _merge_notes(*note_groups: list[str]) -> list[str]:
    merged: list[str] = []
    for notes in note_groups:
        for note in notes:
            if note not in merged:
                merged.append(note)
    return merged
