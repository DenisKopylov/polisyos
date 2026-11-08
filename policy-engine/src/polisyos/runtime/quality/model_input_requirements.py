"""Produce the complete missing-input set of the selected ProgramGraph."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from polisyos.core.artifacts import validate_core_model_json_artifact
from polisyos.core.contracts.model_input_requirements import (
    ModelInputContext,
    ModelInputObligationSet,
    ProgramGraphInputInterface,
    ProgramGraphInputInvocation,
    persist_model_input_obligation,
    persist_model_input_obligation_set,
    persist_program_graph_input_interface,
)
from polisyos.foundry.execute.model_input_requirements import (
    recompute_program_graph_inputs,
    resolve_program_graph_input_declaration,
    verify_program_graph_input_preflight,
)

if TYPE_CHECKING:
    from polisyos.core.artifacts import CoreJSONArtifactStore
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.contracts.foundry import (
        ExecPlanRef,
        FoundryInputBindingsRef,
        ParameterOverrideBundleRef,
        ProgramGraphRef,
    )


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
    return persist_program_graph_input_interface(
        store,
        ProgramGraphInputInterface(
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
    origin before using its ports. This bounded
    profile supports one compiled additive mechanism, structural all-entity masks
    and merge steps. Unsupported graph operations, dynamic selectors and
    unexplained inputs refuse before invoking a numerical producer.

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
    refs = tuple(
        persist_model_input_obligation(store, obligation)
        for obligation in recomputed.missing_obligations
    )
    set_ref = persist_model_input_obligation_set(
        store,
        ModelInputObligationSet(
            invocation=invocation,
            prestate_ref=recomputed.prestate_ref,
            supplied_initial_slots=recomputed.supplied_initial_slots,
            obligation_refs=refs,
        ),
    )
    return ProgramGraphInputPreflight(
        obligation_refs=refs,
        supplied_initial_slots=recomputed.supplied_initial_slots,
        parameter_override_bundle_ref=parameter_override_bundle_ref,
        obligation_set_ref=set_ref,
        invocation=invocation,
    )
