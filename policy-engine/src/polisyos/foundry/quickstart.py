"""Build and run the minimal CAS-backed Foundry compile/execute quickstart."""

from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import jax.numpy as jnp

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.contracts.foundry import (
    CompileRequest,
    ExecPlan,
    ExecuteRequest,
    FeedbackConfig,
    FeedbackConfigRef,
    FeedbackDiagnosticSpec,
    FeedbackSolverConfig,
    FeedbackVariableSpec,
    FoundryInputBindings,
    FoundryInputBindingsRef,
    FoundryInputBindingTransform,
    ProgramGraph,
    StateSnapshotRef,
)
from polisyos.core.registry import build_default_registry_bundle, load_registry_bundle_content

# Keep the README quickstart on the CPU path unless the caller explicitly chose
# a different backend. This avoids common Apple Silicon / Metal surprises.
os.environ.setdefault("JAX_PLATFORMS", "cpu")
os.environ.setdefault("JAX_PLATFORM_NAME", "cpu")

from polisyos.foundry.compile.api import compile as compile_foundry
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.execute.api import execute as execute_foundry
from polisyos.foundry.executor import put_state_snapshot
from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.governance.selector_expr import SelectorPredicate
from polisyos.ir.model_spec import ModelSpec
from polisyos.ir.trinity import TrinityBundle
from polisyos.ir.types import SelectorOperator


@dataclass(frozen=True, slots=True)
class QuickstartRunResult:
    """Outcome summary for the documented trivial compile/execute run."""

    compile_ok: bool
    execute_ok: bool
    exec_plan_artifact_id: str | None
    simulation_result_artifact_id: str | None


@dataclass(frozen=True, slots=True)
class FeedbackQuickstartRunResult:
    """Outcome summary for the documented feedback-enabled compile/execute run."""

    compile_ok: bool
    execute_ok: bool
    exec_plan_artifact_id: str | None
    simulation_result_artifact_id: str | None
    feedback_result_artifact_id: str | None
    feedback_convergence_certificate_artifact_id: str | None
    equilibrium_multiplicity_report_artifact_id: str | None = None


def resolve_registry_bundle_ref(store: FileSystemCAS, bundle: TrinityBundle) -> ArtifactRef:
    """Resolve the registry bundle reference embedded in a Trinity bundle."""

    registry_bundle_id = bundle.model_spec.registry_bundle_ref
    if registry_bundle_id is None:
        raise ValueError("Trivial quickstart requires model_spec.registry_bundle_ref to be set.")
    registry_manifest = store.get_manifest(ArtifactID(registry_bundle_id))
    return ArtifactRef(
        artifact_id=registry_manifest.artifact_id,
        kind=registry_manifest.kind,
        media_type=registry_manifest.media_type,
    )


def build_trivial_trinity_bundle(registry_bundle_ref: str) -> TrinityBundle:
    """Build a minimal Trinity bundle used by docs and smoke tests."""

    return TrinityBundle(
        problem_frame=ProblemFrame(problem_id="demo", domain=ProblemDomain.FISCAL),
        policy_spec=PolicySpec(
            policy_id="demo_policy",
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
            model_id="demo_model",
            data_snapshot_ref="sha256:" + "0" * 64,
            registry_bundle_ref=registry_bundle_ref,
        ),
    )


def put_trivial_trinity_bundle(store: FileSystemCAS, bundle: TrinityBundle) -> ArtifactRef:
    """Persist a quickstart Trinity bundle into the local CAS."""

    return store.put_json(
        bundle,
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version=bundle.schema_version),
        ),
    )


def prepare_trivial_input_bindings(
    store: FileSystemCAS,
    registry_bundle_ref: ArtifactRef,
    *,
    n_agents: int = 2,
    n_firms: int = 1,
    step: int = 0,
    agent_income: float = 0.0,
) -> FoundryInputBindingsRef:
    """Create the default state snapshot and input bindings for the README demo."""

    state = GlobalState.empty(n_agents=n_agents, n_firms=n_firms)
    if agent_income != 0.0:
        income = jnp.full((n_agents,), float(agent_income), dtype=jnp.float32)
        state = state.replace(
            agents=state.agents.replace(
                income=income,
                reported_income=income,
            )
        )
    state_ref = put_state_snapshot(
        store,
        state=state,
        step=step,
    )
    state_snapshot_ref = StateSnapshotRef(artifact_id=state_ref.artifact_id)
    data_snapshot_ref = store.put_json(
        DataSnapshot(data_ref=state_snapshot_ref),
        PutOptions(kind="fabric.data_snapshot", media_type="application/json"),
    )
    input_bindings_ref = store.put_json(
        FoundryInputBindings(
            data_snapshot_ref=data_snapshot_ref,
            registry_bundle_ref=registry_bundle_ref,
            rules=[],
            bound_state_snapshot_ref=state_snapshot_ref,
        ),
        PutOptions(kind="foundry.input_bindings", media_type="application/json"),
    )
    return FoundryInputBindingsRef(artifact_id=input_bindings_ref.artifact_id)


def prepare_trivial_feedback_config(
    store: FileSystemCAS,
    *,
    exec_plan_ref: ArtifactRef,
) -> FeedbackConfigRef:
    """Persist a minimal feedback config that endogenizes the income-tax rate."""

    exec_plan = ExecPlan.model_validate(
        from_canonical_bytes(store.get_bytes(exec_plan_ref.artifact_id))
    )
    program_graph = ProgramGraph.model_validate(
        from_canonical_bytes(store.get_bytes(exec_plan.program_ref.artifact_id))
    )
    income_tax_node = next(
        (node.node_id for node in program_graph.nodes if node.mechanism_type == "income_tax"),
        None,
    )
    if income_tax_node is None:
        raise ValueError(
            "Quickstart feedback demo requires an income_tax node in the program graph"
        )

    config = FeedbackConfig(
        variables=[
            FeedbackVariableSpec(
                variable_id="endogenous_tax_rate",
                source_kind="state_path",
                source_ref="agents.income",
                reduction="mean",
                transforms=[
                    FoundryInputBindingTransform(op="scale", params={"factor": 0.01}),
                ],
                target_kind="parameter_override",
                target_ref=income_tax_node,
                target_param="rate",
                initial_value=1.0,
                lower_bound=0.0,
                upper_bound=1.0,
                scale=1.0,
            )
        ],
        diagnostics=[
            FeedbackDiagnosticSpec(
                diagnostic_id="government_balance",
                source_kind="state_path",
                source_ref="government_balance",
            )
        ],
        solver=FeedbackSolverConfig(
            homotopy_grid=[0.0, 0.5, 1.0],
            damping_init=0.5,
            max_iter=20,
        ),
        notes=["quickstart_feedback_demo"],
    )
    ref = store.put_json(
        config,
        PutOptions(
            kind="foundry.feedback_config",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.FeedbackConfig", version="1.0"),
            inputs=[InputRef(artifact_id=exec_plan_ref.artifact_id, role="exec_plan")],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return FeedbackConfigRef(artifact_id=ref.artifact_id)


def prepare_trivial_multiplicity_config(
    store: FileSystemCAS,
    *,
    exec_plan_ref: ArtifactRef,
) -> FeedbackConfigRef:
    """Persist the quickstart feedback config with multiplicity discovery enabled."""

    feedback_ref = prepare_trivial_feedback_config(store, exec_plan_ref=exec_plan_ref)
    config = FeedbackConfig.model_validate(
        from_canonical_bytes(store.get_bytes(feedback_ref.artifact_id))
    )
    multiplicity_config = config.model_copy(
        update={
            "solver": config.solver.model_copy(
                update={
                    "detect_multiplicity": True,
                    "multiplicity_mode": "baseline",
                    "multiplicity_max_attempts": 8,
                    "multiplicity_sobol_draws": 6,
                    "basin_draws": 8,
                    "basin_seed": 17,
                }
            ),
            "notes": [*config.notes, "quickstart_multiplicity_demo"],
        }
    )
    ref = store.put_json(
        multiplicity_config,
        PutOptions(
            kind="foundry.feedback_config",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.FeedbackConfig", version="1.0"),
            inputs=[InputRef(artifact_id=exec_plan_ref.artifact_id, role="exec_plan")],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return FeedbackConfigRef(artifact_id=ref.artifact_id)


def run_trivial_compile_execute(
    bundle: TrinityBundle | None = None,
    cas_root: str | Path = ".polisyos/cas",
) -> QuickstartRunResult:
    """Compile and execute a tiny end-to-end Foundry run.

    When ``bundle`` is omitted, the helper provisions a registry bundle in the
    target CAS root and builds a default fiscal demo bundle automatically.
    """

    store = FileSystemCAS(Path(cas_root))

    if bundle is None:
        registry = build_default_registry_bundle(store)
        load_registry_bundle_content(store, registry.bundle_ref)
        bundle = build_trivial_trinity_bundle(str(registry.bundle_ref.artifact_id))

    registry_bundle_ref = resolve_registry_bundle_ref(store, bundle)
    policy_ref = put_trivial_trinity_bundle(store, bundle)
    compiled = compile_foundry(
        store,
        CompileRequest(
            input_kind="trinity",
            policy_ref=policy_ref,
            registry_bundle_ref=registry_bundle_ref,
        ),
    )
    input_bindings_ref = prepare_trivial_input_bindings(store, registry_bundle_ref)
    executed = execute_foundry(
        store,
        ExecuteRequest(
            exec_plan_ref=compiled.exec_plan_ref,
            input_bindings_ref=input_bindings_ref,
            registry_bundle_ref=registry_bundle_ref,
        ),
    )

    return QuickstartRunResult(
        compile_ok=compiled.ok,
        execute_ok=executed.ok,
        exec_plan_artifact_id=(
            compiled.exec_plan_ref.artifact_id if compiled.exec_plan_ref is not None else None
        ),
        simulation_result_artifact_id=(
            executed.simulation_result_ref.artifact_id
            if executed.simulation_result_ref is not None
            else None
        ),
    )


def run_feedback_compile_execute(
    bundle: TrinityBundle | None = None,
    cas_root: str | Path = ".polisyos/cas",
) -> FeedbackQuickstartRunResult:
    """Compile and execute the minimal feedback-enabled Foundry demo."""

    store = FileSystemCAS(Path(cas_root))

    if bundle is None:
        registry = build_default_registry_bundle(store)
        load_registry_bundle_content(store, registry.bundle_ref)
        bundle = build_trivial_trinity_bundle(str(registry.bundle_ref.artifact_id))

    registry_bundle_ref = resolve_registry_bundle_ref(store, bundle)
    policy_ref = put_trivial_trinity_bundle(store, bundle)
    compiled = compile_foundry(
        store,
        CompileRequest(
            input_kind="trinity",
            policy_ref=policy_ref,
            registry_bundle_ref=registry_bundle_ref,
        ),
    )
    input_bindings_ref = prepare_trivial_input_bindings(
        store,
        registry_bundle_ref,
        agent_income=100.0,
    )
    feedback_config_ref = prepare_trivial_feedback_config(
        store,
        exec_plan_ref=compiled.exec_plan_ref,
    )
    executed = execute_foundry(
        store,
        ExecuteRequest(
            exec_plan_ref=compiled.exec_plan_ref,
            input_bindings_ref=input_bindings_ref,
            registry_bundle_ref=registry_bundle_ref,
            feedback_config_ref=feedback_config_ref,
        ),
    )
    feedback_result_ref = next(
        (
            artifact.ref.artifact_id
            for artifact in executed.derived_refs
            if artifact.role == "feedback_result"
        ),
        None,
    )
    feedback_certificate_ref = next(
        (
            artifact.ref.artifact_id
            for artifact in executed.derived_refs
            if artifact.role == "feedback_convergence_certificate"
        ),
        None,
    )
    multiplicity_report_ref = next(
        (
            artifact.ref.artifact_id
            for artifact in executed.derived_refs
            if artifact.role == "equilibrium_multiplicity_report"
        ),
        None,
    )

    return FeedbackQuickstartRunResult(
        compile_ok=compiled.ok,
        execute_ok=executed.ok,
        exec_plan_artifact_id=(
            compiled.exec_plan_ref.artifact_id if compiled.exec_plan_ref is not None else None
        ),
        simulation_result_artifact_id=(
            executed.simulation_result_ref.artifact_id
            if executed.simulation_result_ref is not None
            else None
        ),
        feedback_result_artifact_id=feedback_result_ref,
        feedback_convergence_certificate_artifact_id=feedback_certificate_ref,
        equilibrium_multiplicity_report_artifact_id=multiplicity_report_ref,
    )


def run_feedback_multiplicity_demo(
    bundle: TrinityBundle | None = None,
    cas_root: str | Path = ".polisyos/cas",
) -> FeedbackQuickstartRunResult:
    """Compile and execute the quickstart with multiplicity reporting enabled."""

    store = FileSystemCAS(Path(cas_root))

    if bundle is None:
        registry = build_default_registry_bundle(store)
        load_registry_bundle_content(store, registry.bundle_ref)
        bundle = build_trivial_trinity_bundle(str(registry.bundle_ref.artifact_id))

    registry_bundle_ref = resolve_registry_bundle_ref(store, bundle)
    policy_ref = put_trivial_trinity_bundle(store, bundle)
    compiled = compile_foundry(
        store,
        CompileRequest(
            input_kind="trinity",
            policy_ref=policy_ref,
            registry_bundle_ref=registry_bundle_ref,
        ),
    )
    input_bindings_ref = prepare_trivial_input_bindings(
        store,
        registry_bundle_ref,
        agent_income=100.0,
    )
    feedback_config_ref = prepare_trivial_multiplicity_config(
        store,
        exec_plan_ref=compiled.exec_plan_ref,
    )
    executed = execute_foundry(
        store,
        ExecuteRequest(
            exec_plan_ref=compiled.exec_plan_ref,
            input_bindings_ref=input_bindings_ref,
            registry_bundle_ref=registry_bundle_ref,
            feedback_config_ref=feedback_config_ref,
        ),
    )
    feedback_result_ref = next(
        (
            artifact.ref.artifact_id
            for artifact in executed.derived_refs
            if artifact.role == "feedback_result"
        ),
        None,
    )
    feedback_certificate_ref = next(
        (
            artifact.ref.artifact_id
            for artifact in executed.derived_refs
            if artifact.role == "feedback_convergence_certificate"
        ),
        None,
    )
    multiplicity_report_ref = next(
        (
            artifact.ref.artifact_id
            for artifact in executed.derived_refs
            if artifact.role == "equilibrium_multiplicity_report"
        ),
        None,
    )
    return FeedbackQuickstartRunResult(
        compile_ok=compiled.ok,
        execute_ok=executed.ok,
        exec_plan_artifact_id=(
            compiled.exec_plan_ref.artifact_id if compiled.exec_plan_ref is not None else None
        ),
        simulation_result_artifact_id=(
            executed.simulation_result_ref.artifact_id
            if executed.simulation_result_ref is not None
            else None
        ),
        feedback_result_artifact_id=feedback_result_ref,
        feedback_convergence_certificate_artifact_id=feedback_certificate_ref,
        equilibrium_multiplicity_report_artifact_id=multiplicity_report_ref,
    )


__all__ = [
    "FeedbackQuickstartRunResult",
    "QuickstartRunResult",
    "build_trivial_trinity_bundle",
    "prepare_trivial_feedback_config",
    "prepare_trivial_input_bindings",
    "prepare_trivial_multiplicity_config",
    "put_trivial_trinity_bundle",
    "resolve_registry_bundle_ref",
    "run_feedback_compile_execute",
    "run_feedback_multiplicity_demo",
    "run_trivial_compile_execute",
]
