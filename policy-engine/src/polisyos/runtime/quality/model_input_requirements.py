"""Produce the complete missing-input set of the selected ProgramGraph."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from polisyos.core.artifacts import (
    ArtifactRef,
    validate_core_model_json_artifact,
)
from polisyos.core.contracts import (
    ExecPlanRef,
    FoundryInputBindingsRef,
    ModelInputContext,
    ModelInputObligationSet,
    ParameterOverrideBundleRef,
    ProgramGraph,
    ProgramGraphInputInterface,
    ProgramGraphInputInvocation,
    ProgramGraphRef,
    persist_model_input_obligation,
    persist_model_input_obligation_set,
    persist_program_graph_input_interface,
)
from polisyos.foundry.execute import (
    recompute_program_graph_inputs,
    resolve_program_graph_input_declaration,
    verify_program_graph_input_preflight,
)

if TYPE_CHECKING:
    from polisyos.core.artifacts import CoreJSONArtifactStore
    from polisyos.core.contracts import ModelInputObligation, ModelInputStepScope, StateSnapshotRef


@dataclass(frozen=True)
class ProgramGraphInputPreflight:
    """Current preflight facts before the numerical producer opens the plan."""

    obligation_refs: tuple[ArtifactRef, ...]
    supplied_initial_slots: tuple[str, ...]
    parameter_override_bundle_ref: ParameterOverrideBundleRef | None
    obligation_set_ref: ArtifactRef
    invocation: ProgramGraphInputInvocation


@dataclass(frozen=True)
class SelectedProgramGraphInputBasis:
    """Invocation facts from the active job, candidate, and selected execution."""

    context: ModelInputContext
    program_graph_ref: ProgramGraphRef
    exec_plan_ref: ExecPlanRef
    registry_bundle_ref: ArtifactRef
    input_bindings_ref: FoundryInputBindingsRef
    steps: tuple[int, ...]
    parameter_override_bundle_ref: ParameterOverrideBundleRef | None = None

    def invocation(self, interface_ref: ArtifactRef) -> ProgramGraphInputInvocation:
        """Bind independently selected facts to an interface for Foundry replay."""
        return ProgramGraphInputInvocation(
            context=self.context,
            interface_ref=interface_ref,
            program_graph_ref=self.program_graph_ref,
            exec_plan_ref=self.exec_plan_ref,
            registry_bundle_ref=self.registry_bundle_ref,
            input_bindings_ref=self.input_bindings_ref,
            steps=self.steps,
            parameter_override_bundle_ref=self.parameter_override_bundle_ref,
        )


def replay_selected_program_graph_input_obligations(
    store: CoreJSONArtifactStore,
    *,
    obligation_set_ref: ArtifactRef,
    selected_basis: SelectedProgramGraphInputBasis,
) -> ModelInputObligationSet:
    """Read the exact set and replay its members against the current selection.

    The set supplies the interface locator. Foundry independently compares
    that interface with the compiled model's declaration during replay.
    """
    selected_set = validate_core_model_json_artifact(
        ModelInputObligationSet, store, obligation_set_ref
    )
    return verify_program_graph_input_preflight(
        store,
        obligation_set_ref=obligation_set_ref,
        expected_invocation=selected_basis.invocation(selected_set.invocation.interface_ref),
    )


def derive_program_graph_input_interface(
    store: CoreJSONArtifactStore,
    *,
    program_graph_ref: ProgramGraphRef,
    exec_plan_ref: ExecPlanRef,
    registry_bundle_ref: ArtifactRef,
) -> ArtifactRef | None:
    """Derive the interface from the selected graph's actual compiled ModelSpec."""
    selected = resolve_program_graph_input_declaration(
        store,
        program_graph_ref=program_graph_ref,
        exec_plan_ref=exec_plan_ref,
        registry_bundle_ref=registry_bundle_ref,
    )
    if selected is None:
        return None
    advanced_method_input_profile = any(
        port.carrier == "method_input"
        and (port.period_step_profile is not None or port.entity_axis_ref is not None)
        for port in selected.declaration.ports
    )
    method_input_profile = any(
        port.carrier == "method_input" for port in selected.declaration.ports
    )
    return persist_program_graph_input_interface(
        store,
        ProgramGraphInputInterface(
            schema_version=("1.2" if advanced_method_input_profile else "1.1")
            if method_input_profile
            else "1.0",
            program_graph_ref=program_graph_ref,
            exec_plan_ref=exec_plan_ref,
            registry_bundle_ref=registry_bundle_ref,
            ports=selected.declaration.ports,
            declaration_ref=selected.declaration_ref,
            trinity_bundle_ref=selected.trinity_bundle_ref,
        ),
    )


def preflight_program_graph_inputs(
    store: CoreJSONArtifactStore,
    *,
    interface_ref: ArtifactRef,
    program_graph_ref: ProgramGraphRef,
    exec_plan_ref: ExecPlanRef,
    registry_bundle_ref: ArtifactRef,
    input_bindings_ref: FoundryInputBindingsRef,
    context: ModelInputContext,
    steps: tuple[int, ...],
    parameter_override_bundle_ref: ParameterOverrideBundleRef | None = None,
) -> ProgramGraphInputPreflight:
    """Produce the missing-input facts of an actual selected graph before execution.

    The caller derives the interface from the graph's compiled ModelSpec.
    The producer independently verifies that selection against the compiled
    origin before using its ports. The bounded profile supports registered
    mechanisms and methods, structural all-entity masks, and merge steps.
    Method reads join the selected method ABI; external scalar method inputs
    require one exact model transition. Unsupported graph operations, dynamic
    selectors and unexplained inputs refuse before invoking a numerical producer.

    Parameter overrides are reopened from the same exact bundle as the
    numerical request. A missing state port stays missing even when the
    unbound snapshot has a numerically usable initialization placeholder.
    """
    invocation = SelectedProgramGraphInputBasis(
        context=context,
        program_graph_ref=program_graph_ref,
        exec_plan_ref=exec_plan_ref,
        registry_bundle_ref=registry_bundle_ref,
        input_bindings_ref=input_bindings_ref,
        steps=steps,
        parameter_override_bundle_ref=parameter_override_bundle_ref,
    ).invocation(interface_ref)
    recomputed = recompute_program_graph_inputs(store, invocation=invocation)
    graph = validate_core_model_json_artifact(ProgramGraph, store, program_graph_ref)
    interface = validate_core_model_json_artifact(ProgramGraphInputInterface, store, interface_ref)
    method_profile = any(node.node_kind == "method" for node in graph.nodes)
    method_obligation_profile = any(
        obligation.schema_version in {"1.1", "1.2"} for obligation in recomputed.missing_obligations
    )
    advanced_execution_profile = any(
        port.purpose in {"initial_state", "simulation_input"}
        and (port.period_step_profile is not None or port.entity_axis_ref is not None)
        for port in interface.ports
    )
    schema_version: Literal["1.0", "1.1", "1.2"] = (
        "1.2"
        if advanced_execution_profile
        else "1.1"
        if method_profile or method_obligation_profile
        else "1.0"
    )
    return _persist_program_graph_input_preflight(
        store,
        invocation=invocation,
        schema_version=schema_version,
        prestate_ref=recomputed.prestate_ref,
        supplied_initial_slots=recomputed.supplied_initial_slots,
        missing_obligations=recomputed.missing_obligations,
        required_step_scopes=recomputed.required_step_scopes,
    )


def preflight_current_use_method_input_revalidation(
    store: CoreJSONArtifactStore,
    *,
    interface_ref: ArtifactRef,
    program_graph_ref: ProgramGraphRef,
    exec_plan_ref: ExecPlanRef,
    registry_bundle_ref: ArtifactRef,
    input_bindings_ref: FoundryInputBindingsRef,
    context: ModelInputContext,
    steps: tuple[int, ...],
    parameter_override_bundle_ref: ParameterOverrideBundleRef | None = None,
) -> ProgramGraphInputPreflight:
    """Produce and reconcile fresh method obligations for the actual current subject.

    Historical selected values are replayed against their own original subject
    by Foundry. They do not become supplied values for the new invocation.
    This purpose is candidate input revalidation, not execution admission,
    acquisition authority, or permission for a protected action.
    """
    from polisyos.foundry.execute import (
        recompute_current_use_method_input_revalidation,
        verify_current_use_method_input_revalidation,
    )

    invocation = SelectedProgramGraphInputBasis(
        context=context,
        program_graph_ref=program_graph_ref,
        exec_plan_ref=exec_plan_ref,
        registry_bundle_ref=registry_bundle_ref,
        input_bindings_ref=input_bindings_ref,
        steps=steps,
        parameter_override_bundle_ref=parameter_override_bundle_ref,
    ).invocation(interface_ref)
    recomputed = recompute_current_use_method_input_revalidation(store, invocation=invocation)
    # The canonical owner verifies the one-step, non-temporal/axis profile.
    # Its ordinary clock facts can be nonempty without a temporal opt-in;
    # Set 1.3 retains those facts through its invocation and ordinary members.
    result = _persist_program_graph_input_preflight(
        store,
        invocation=invocation,
        schema_version="1.3",
        prestate_ref=recomputed.prestate_ref,
        supplied_initial_slots=recomputed.supplied_initial_slots,
        missing_obligations=recomputed.missing_obligations,
        required_step_scopes=(),
    )
    verified = verify_current_use_method_input_revalidation(
        store,
        obligation_set_ref=result.obligation_set_ref,
        expected_invocation=invocation,
    )
    if (
        verified.obligation_refs != result.obligation_refs
        or verified.supplied_initial_slots != result.supplied_initial_slots
        or verified.invocation != result.invocation
    ):
        raise ValueError("current_method_input_revalidation_persistence_mismatch")
    return result


def _persist_program_graph_input_preflight(
    store: CoreJSONArtifactStore,
    *,
    invocation: ProgramGraphInputInvocation,
    schema_version: Literal["1.0", "1.1", "1.2", "1.3"],
    prestate_ref: StateSnapshotRef,
    supplied_initial_slots: tuple[str, ...],
    missing_obligations: tuple[ModelInputObligation, ...],
    required_step_scopes: tuple[ModelInputStepScope, ...],
) -> ProgramGraphInputPreflight:
    """Share the existing exact Core member/set writer across typed purposes."""
    refs = tuple(persist_model_input_obligation(store, item) for item in missing_obligations)
    set_ref = persist_model_input_obligation_set(
        store,
        ModelInputObligationSet(
            schema_version=schema_version,
            invocation=invocation,
            prestate_ref=prestate_ref,
            supplied_initial_slots=supplied_initial_slots,
            obligation_refs=refs,
            **(
                {"required_step_scopes": required_step_scopes}
                if schema_version == "1.2"
                else {
                    "purpose": "current_use_method_input_revalidation",
                    "authority_purpose": "candidate_execution_input_revalidation_only",
                }
                if schema_version == "1.3"
                else {}
            ),
        ),
    )
    return ProgramGraphInputPreflight(
        obligation_refs=refs,
        supplied_initial_slots=supplied_initial_slots,
        parameter_override_bundle_ref=invocation.parameter_override_bundle_ref,
        obligation_set_ref=set_ref,
        invocation=invocation,
    )
