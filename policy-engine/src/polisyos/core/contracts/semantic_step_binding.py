"""Replayed temporal subjects for candidate model-input selections.

An exact step scope is a coordinate in a selected model invocation, not an
observation or permission.  The resolver reopens the original obligation set
and its selected model clock before a producer or consumer uses that coordinate.
"""

from __future__ import annotations

from polisyos.core.artifacts import ArtifactRef, ArtifactStore, artifact_ref_identity_key

from .model_input_period_steps import ModelInputStepScope


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

    if type(step_scope) is not ModelInputStepScope:
        raise ValueError("model_input_step_selection_scope_untyped")
    selected_set, members = load_model_input_obligation_set(store, obligation_set_ref)
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
