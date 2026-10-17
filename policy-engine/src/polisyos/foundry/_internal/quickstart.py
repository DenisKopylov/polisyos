"""Build and run the minimal CAS-backed Foundry compile/execute quickstart."""

from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Protocol, runtime_checkable

import jax
import jax.numpy as jnp

from polisyos.core import registry as _core_registry_facade
from polisyos.core.artifacts import (
    ArtifactID,
    ArtifactRef,
    FileSystemCAS,
    InputRef,
    PutOptions,
    SchemaInfo,
    input_ref_from_artifact_ref,
)
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts import DataSnapshot
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

# Keep the README quickstart on the CPU path unless the caller explicitly chose
# a different backend. This avoids common Apple Silicon / Metal surprises.
os.environ.setdefault("JAX_PLATFORMS", "cpu")
os.environ.setdefault("JAX_PLATFORM_NAME", "cpu")

from polisyos.foundry.compile.api import compile as compile_foundry
from polisyos.foundry.contracts.state import AgentState, GlobalState
from polisyos.foundry.execute.api import execute as execute_foundry
from polisyos.foundry.execute.executor import put_state_snapshot
from polisyos.ir import ModelSpec, PolicySpec, ProblemDomain, ProblemFrame, TrinityBundle
from polisyos.ir.governance import InterventionSpec, ScheduleSpec, SelectorPredicate
from polisyos.ir.model_layer.types import SelectorOperator

build_default_registry_bundle = _core_registry_facade.build_default_registry_bundle
load_registry_bundle_content = _core_registry_facade.load_registry_bundle_content
del _core_registry_facade


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


@runtime_checkable
class _AgentIncomeUpdater(Protocol):
    def replace(
        self,
        *,
        income: jax.Array,
        reported_income: jax.Array,
    ) -> AgentState: ...


@runtime_checkable
class _GlobalAgentUpdater(Protocol):
    def replace(self, *, agents: AgentState) -> GlobalState: ...


def _feedback_result_without_exec_plan() -> FeedbackQuickstartRunResult:
    """Report a failed feedback quickstart when compilation emits no plan."""
    return FeedbackQuickstartRunResult(
        compile_ok=False,
        execute_ok=False,
        exec_plan_artifact_id=None,
        simulation_result_artifact_id=None,
        feedback_result_artifact_id=None,
        feedback_convergence_certificate_artifact_id=None,
        equilibrium_multiplicity_report_artifact_id=None,
    )


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
            kind=TrinityBundle.ARTIFACT_KIND,
            media_type=TrinityBundle.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=TrinityBundle.ARTIFACT_SCHEMA_NAME,
                version=TrinityBundle.ARTIFACT_SCHEMA_VERSION,
            ),
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
        agent_state: object = state.agents
        if not isinstance(agent_state, _AgentIncomeUpdater):
            raise TypeError("Foundry AgentState does not support immutable replacement")
        updated_agents = agent_state.replace(income=income, reported_income=income)
        global_state: object = state
        if not isinstance(global_state, _GlobalAgentUpdater):
            raise TypeError("Foundry GlobalState does not support immutable replacement")
        state = global_state.replace(agents=updated_agents)
    state_ref = put_state_snapshot(
        store,
        state=state,
        step=step,
        return_selected_profile=True,
    )
    state_snapshot_ref = StateSnapshotRef.model_validate(state_ref.model_dump(mode="python"))
    data_snapshot_ref = store.put_json(
        DataSnapshot(data_ref=state_snapshot_ref),
        PutOptions(
            kind=DataSnapshot.ARTIFACT_KIND,
            media_type=DataSnapshot.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=DataSnapshot.ARTIFACT_SCHEMA_NAME,
                version=DataSnapshot.ARTIFACT_SCHEMA_VERSION,
            ),
            inputs=[input_ref_from_artifact_ref(state_snapshot_ref, role="data_ref")],
        ),
        return_selected_profile=True,
    )
    input_bindings_ref = store.put_json(
        FoundryInputBindings(
            data_snapshot_ref=data_snapshot_ref,
            registry_bundle_ref=registry_bundle_ref,
            rules=[],
            bound_state_snapshot_ref=state_snapshot_ref,
        ),
        PutOptions(
            kind=FoundryInputBindings.ARTIFACT_KIND,
            media_type=FoundryInputBindings.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=FoundryInputBindings.ARTIFACT_SCHEMA_NAME,
                version=FoundryInputBindings.ARTIFACT_SCHEMA_VERSION,
            ),
            inputs=[
                input_ref_from_artifact_ref(
                    data_snapshot_ref,
                    role="input.data_snapshot_ref",
                ),
                input_ref_from_artifact_ref(
                    registry_bundle_ref,
                    role="input.registry_bundle_ref",
                ),
                input_ref_from_artifact_ref(
                    state_snapshot_ref,
                    role="artifact.bound_state_snapshot_ref",
                ),
            ],
        ),
        return_selected_profile=True,
    )
    return FoundryInputBindingsRef.model_validate(input_bindings_ref.model_dump(mode="python"))


def prepare_trivial_feedback_config(
    store: FileSystemCAS,
    *,
    exec_plan_ref: ArtifactRef,
    return_selected_profile: bool = False,
) -> FeedbackConfigRef:
    """Persist a minimal feedback config that endogenizes the income-tax rate."""
    from polisyos.core.artifacts import validate_core_model_json_artifact

    exec_plan = validate_core_model_json_artifact(ExecPlan, store, exec_plan_ref)
    program_graph = validate_core_model_json_artifact(ProgramGraph, store, exec_plan.program_ref)
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
            kind=FeedbackConfig.ARTIFACT_KIND,
            media_type=FeedbackConfig.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=FeedbackConfig.ARTIFACT_SCHEMA_NAME,
                version=FeedbackConfig.ARTIFACT_SCHEMA_VERSION,
            ),
            inputs=[InputRef(artifact_id=exec_plan_ref.artifact_id, role="exec_plan")],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=return_selected_profile,
    )
    return FeedbackConfigRef.model_validate(ref.model_dump(mode="python"))


def prepare_trivial_multiplicity_config(
    store: FileSystemCAS,
    *,
    exec_plan_ref: ArtifactRef,
) -> FeedbackConfigRef:
    """Persist the quickstart feedback config with multiplicity discovery enabled."""
    from polisyos.core.artifacts import validate_core_model_json_artifact

    feedback_ref = prepare_trivial_feedback_config(store, exec_plan_ref=exec_plan_ref)
    config = validate_core_model_json_artifact(FeedbackConfig, store, feedback_ref)
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
            kind=FeedbackConfig.ARTIFACT_KIND,
            media_type=FeedbackConfig.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=FeedbackConfig.ARTIFACT_SCHEMA_NAME,
                version=FeedbackConfig.ARTIFACT_SCHEMA_VERSION,
            ),
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
            str(compiled.exec_plan_ref.artifact_id) if compiled.exec_plan_ref is not None else None
        ),
        simulation_result_artifact_id=(
            str(executed.simulation_result_ref.artifact_id)
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
    exec_plan_ref = compiled.exec_plan_ref
    if exec_plan_ref is None:
        return _feedback_result_without_exec_plan()
    input_bindings_ref = prepare_trivial_input_bindings(
        store,
        registry_bundle_ref,
        agent_income=100.0,
    )
    feedback_config_ref = prepare_trivial_feedback_config(
        store,
        exec_plan_ref=exec_plan_ref,
    )
    executed = execute_foundry(
        store,
        ExecuteRequest(
            exec_plan_ref=exec_plan_ref,
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
        exec_plan_artifact_id=str(exec_plan_ref.artifact_id),
        simulation_result_artifact_id=(
            str(executed.simulation_result_ref.artifact_id)
            if executed.simulation_result_ref is not None
            else None
        ),
        feedback_result_artifact_id=(
            str(feedback_result_ref) if feedback_result_ref is not None else None
        ),
        feedback_convergence_certificate_artifact_id=(
            str(feedback_certificate_ref) if feedback_certificate_ref is not None else None
        ),
        equilibrium_multiplicity_report_artifact_id=(
            str(multiplicity_report_ref) if multiplicity_report_ref is not None else None
        ),
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
    exec_plan_ref = compiled.exec_plan_ref
    if exec_plan_ref is None:
        return _feedback_result_without_exec_plan()
    input_bindings_ref = prepare_trivial_input_bindings(
        store,
        registry_bundle_ref,
        agent_income=100.0,
    )
    feedback_config_ref = prepare_trivial_multiplicity_config(
        store,
        exec_plan_ref=exec_plan_ref,
    )
    executed = execute_foundry(
        store,
        ExecuteRequest(
            exec_plan_ref=exec_plan_ref,
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
        exec_plan_artifact_id=str(exec_plan_ref.artifact_id),
        simulation_result_artifact_id=(
            str(executed.simulation_result_ref.artifact_id)
            if executed.simulation_result_ref is not None
            else None
        ),
        feedback_result_artifact_id=(
            str(feedback_result_ref) if feedback_result_ref is not None else None
        ),
        feedback_convergence_certificate_artifact_id=(
            str(feedback_certificate_ref) if feedback_certificate_ref is not None else None
        ),
        equilibrium_multiplicity_report_artifact_id=(
            str(multiplicity_report_ref) if multiplicity_report_ref is not None else None
        ),
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
