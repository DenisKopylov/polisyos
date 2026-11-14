"""Replayed temporal subjects for candidate model-input selections.

An exact step scope is a coordinate in a selected model invocation, not an
observation or permission.  The resolver reopens the original obligation set
and its selected model clock before a producer or consumer uses that coordinate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from polisyos.core.artifacts import ArtifactRef, ArtifactStore, artifact_ref_identity_key

from .model_input_period_steps import ModelInputStepScope
from .model_input_step_coverage import (
    ModelInputStepCoverage,
    reconcile_model_input_step_coverage,
)

if TYPE_CHECKING:
    from .model_input_requirements import ModelInputObligation, ModelInputObligationSet
    from .semantic_input_binding import ResolvedDerivedInputAtStep, ResolvedInputBindingManifest


@dataclass(frozen=True)
class ModelInputStepSelectionResolution:
    """One operation's reopened subjects and computed scope coverage.

    This in-memory result is not an artifact or an execution admission.  It
    allows consumers to reuse the already reopened original set while replaying
    source and physical values, rather than reloading that set for every row.
    """

    obligation_set: ModelInputObligationSet
    obligations: tuple[ModelInputObligation, ...]
    coverage: ModelInputStepCoverage


def resolve_model_input_step_scope(
    store: ArtifactStore,
    *,
    obligation_set_ref: ArtifactRef,
    model_input_obligation_ref: ArtifactRef,
    step_scope: ModelInputStepScope,
) -> ModelInputStepScope:
    """Recompute one step subject and prove it was required by its origin.

    The original set is immutable.  Its full port-by-step denominator is
    independently recomputed by the Core loader from the selected declaration,
    graph and model clock.  An input can resolve only a step included in the
    referenced origin obligation's missing subset; a correct-looking scope
    beside an unrelated obligation is insufficient.

    This establishes the selected temporal subject only.  Source occurrence,
    arithmetic, physical encoding, currentness and authority remain separate
    predicates owned by the producer and its actual consumer.

    Args:
        store: Existing artifact store containing the selected model inputs.
        obligation_set_ref: Exact original full-horizon obligation set.
        model_input_obligation_ref: Exact member that originally required the value.
        step_scope: Proposed port and absolute model-step coordinate.

    Returns:
        The exact scope reopened and recomputed from the selected invocation.

    Raises:
        ValueError: If the selected origin, required step or exact scope differs.
    """
    from .model_input_requirements import load_model_input_obligation_set

    selected_set, members = load_model_input_obligation_set(store, obligation_set_ref)
    return _resolve_model_input_step_scope_from_origin(
        selected_set,
        members,
        model_input_obligation_ref=model_input_obligation_ref,
        step_scope=step_scope,
    )


def _resolve_model_input_step_scope_from_origin(
    selected_set: ModelInputObligationSet,
    members: tuple[ModelInputObligation, ...],
    *,
    model_input_obligation_ref: ArtifactRef,
    step_scope: ModelInputStepScope,
) -> ModelInputStepScope:
    """Apply one origin predicate to an already reopened operation denominator."""
    if type(step_scope) is not ModelInputStepScope:
        raise ValueError("model_input_step_selection_scope_untyped")
    if selected_set.schema_version != "1.2" or selected_set.required_step_scopes is None:
        raise ValueError("model_input_step_selection_set_profile_required")

    member = next(
        (
            member
            for ref, member in zip(selected_set.obligation_refs, members, strict=True)
            if artifact_ref_identity_key(ref)
            == artifact_ref_identity_key(model_input_obligation_ref)
        ),
        None,
    )
    if member is None:
        raise ValueError("model_input_step_selection_origin_not_member")
    if member.port.carrier != "method_input" or member.port.port_id != step_scope.port_id:
        raise ValueError("model_input_step_selection_origin_port_mismatch")

    expected = next(
        (
            row
            for row in selected_set.required_step_scopes
            if (row.port_id, row.step) == (step_scope.port_id, step_scope.step)
        ),
        None,
    )
    if expected is None:
        raise ValueError("model_input_step_selection_step_not_required")
    if step_scope != expected:
        raise ValueError("model_input_step_selection_scope_mismatch")

    allowed_steps: set[int] = set()
    for dependency in member.dependencies:
        if dependency.kind != "method_read":
            raise ValueError("model_input_step_selection_origin_step_not_required")
        allowed_steps.update(
            dependency.required_steps
            if dependency.required_steps is not None
            else (dependency.first_required_step,)
        )
    if step_scope.step not in allowed_steps:
        raise ValueError("model_input_step_selection_origin_step_not_required")
    return expected


def recompute_resolved_step_input_coverage(
    store: ArtifactStore,
    manifest: ResolvedInputBindingManifest,
) -> ModelInputStepCoverage:
    """Replay all selected temporal subjects with one original-set read.

    Partial source selections are valid candidate staging, so this function
    returns computed missing scopes rather than an execution status.  An
    executor must additionally reconcile source and physical values and call
    ``require_complete`` before admitting numerical work.  The manifest cannot
    declare its own denominator or completeness.

    Args:
        store: Existing store containing the immutable original obligation set.
        manifest: Version-3 step-qualified candidate input selections.

    Returns:
        Exact supplied and missing scope rows derived from the selected model.

    Raises:
        ValueError: If version, selected origin, scope or interface differs.
    """
    if manifest.schema_version != "3.0":
        raise ValueError("resolved_step_input_manifest_profile_required")
    return resolve_model_input_step_selections(
        store,
        obligation_set_ref=manifest.model_input_obligation_set_ref,
        selections=manifest.method_input_steps,
    ).coverage


def resolve_model_input_step_selections(
    store: ArtifactStore,
    *,
    obligation_set_ref: ArtifactRef,
    selections: tuple[ResolvedDerivedInputAtStep, ...],
) -> ModelInputStepSelectionResolution:
    """Resolve all temporal selections with one immutable original-set read.

    Empty or partial supplied coverage is not an execution admission.  The
    caller must separately replay values and require complete coverage before
    any numerical reservation or dispatch.

    Args:
        store: Existing store containing the original model and obligation set.
        obligation_set_ref: Exact original full-horizon set, never a new output.
        selections: Step-qualified derived selections from the manifest or owner.

    Returns:
        Reopened original subjects and their computed exact scope coverage.

    Raises:
        ValueError: If a source obligation, model interface or scope is inconsistent.
    """
    from .model_input_requirements import load_model_input_obligation_set
    from .semantic_input_binding import ResolvedDerivedInputAtStep

    selected_set, members = load_model_input_obligation_set(store, obligation_set_ref)
    if selected_set.required_step_scopes is None:
        raise ValueError("model_input_step_selection_set_profile_required")
    resolved: list[ModelInputStepScope] = []
    for row in selections:
        if type(row) is not ResolvedDerivedInputAtStep:
            raise ValueError("model_input_step_selection_row_untyped")
        if artifact_ref_identity_key(
            row.selection.model_interface_ref
        ) != artifact_ref_identity_key(selected_set.invocation.interface_ref):
            raise ValueError("model_input_step_selection_interface_mismatch")
        resolved.append(
            _resolve_model_input_step_scope_from_origin(
                selected_set,
                members,
                model_input_obligation_ref=row.selection.model_input_obligation_ref,
                step_scope=row.step_scope,
            )
        )
    return ModelInputStepSelectionResolution(
        obligation_set=selected_set,
        obligations=members,
        coverage=reconcile_model_input_step_coverage(
            required_step_scopes=selected_set.required_step_scopes,
            supplied_step_scopes=tuple(resolved),
        ),
    )
