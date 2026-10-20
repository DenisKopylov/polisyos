"""Recompute currentness for artifacts emitted by an engine-owned producer attempt.

This module verifies a narrow in-process selected implementation and the complete
state projection declared by that producer's current NodeSpec. It is not deployment,
transitive-plugin, or external release attestation.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

from polisyos.core.artifacts.manifest import ArtifactRef, artifact_ref_identity_key
from polisyos.core.canon import CanonSpec, from_canonical_bytes, to_canonical_bytes
from polisyos.core.run.manifest import RunInvocationStarted
from polisyos.scientist.orchestration.engine.context import (
    ExecutionContext,
    _EngineInvocationBinding,
    _load_engine_owned_invocation_input_state,
)
from polisyos.scientist.orchestration.engine.finalization import (
    FINAL_WORKFLOW_REPORT_STATE_PATH,
    FINALIZATION_KIND,
    FINALIZATION_OUTPUT_KINDS,
    FINALIZATION_SCHEMA_NAME,
    FINALIZATION_SCHEMA_VERSION,
    WorkflowStateFinalization,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState

ProducerArtifactCurrentness = Literal["current", "stale", "not_established", "invalid"]
_STATE_PROJECTION_CANON = CanonSpec(forbid_floats=False, exclude_none=False)
_MISSING = object()


@dataclass(frozen=True)
class ProducerArtifactAdmission:
    """Source-currentness result for one producer artifact reference."""

    status: ProducerArtifactCurrentness
    reason_code: str

    @property
    def is_current(self) -> bool:
        """Return whether an exact successful producer and source basis were recomputed."""
        return self.status == "current"


def engine_invocation_identity_is_current(
    ctx: ExecutionContext,
    basis: RunInvocationStarted,
    *,
    expected_component_id: str,
) -> bool:
    """Recompute the selected builtin implementation from its engine-owned workflow."""
    try:
        params = _workflow_invocation_params(ctx, basis)
        from polisyos.scientist.orchestration.engine.component_identity import (
            matches_engine_component_identity,
        )

        return matches_engine_component_identity(
            basis.implementation_identity,
            expected_component_id,
            params,
        )
    except Exception:
        return False


def resolve_engine_produced_artifact(
    ctx: ExecutionContext,
    state: ExperimentState,
    artifact_ref: ArtifactRef,
    *,
    expected_component_id: str,
    expected_node_spec: object,
    source_read_paths: tuple[str, ...],
    expected_attempt_id: str | None = None,
    expected_basis_ref: ArtifactRef | None = None,
) -> ProducerArtifactAdmission:
    """Admit an artifact only after replaying its exact engine producer and source basis.

    Multiple successful attempts may share content-addressed bytes. Any one exact,
    current, owner-linked producer is sufficient; an unbound output alone is not.
    """
    if artifact_ref.manifest_profile_sha256 is None:
        return ProducerArtifactAdmission("not_established", "producer_artifact_profile_missing")
    try:
        if state.run_id != ctx.run.run_manifest.run_id:
            return ProducerArtifactAdmission("stale", "producer_artifact_run_mismatch")
        if str(getattr(expected_node_spec.metadata, "component_id", "")) != expected_component_id:
            return ProducerArtifactAdmission("not_established", "producer_node_spec_owner_mismatch")
        if tuple(getattr(expected_node_spec, "state_reads", ())) != source_read_paths:
            return ProducerArtifactAdmission(
                "not_established", "producer_source_basis_contract_mismatch"
            )
        attempts = ctx.run.read_runtime_invocation_attempts()
    except Exception:
        return ProducerArtifactAdmission("not_established", "producer_invocation_chain_unavailable")

    selected_key = artifact_ref_identity_key(artifact_ref)
    linked = []
    for attempt in attempts:
        basis = attempt.basis
        outcome = attempt.outcome
        if (
            outcome is None
            or outcome.status != "ok"
            or outcome.outcome_state_ref is None
            or basis.component_id != expected_component_id
            or not any(
                artifact_ref_identity_key(ref) == selected_key for ref in outcome.output_refs
            )
        ):
            continue
        if expected_attempt_id is not None and basis.attempt_id != expected_attempt_id:
            continue
        if expected_basis_ref is not None and artifact_ref_identity_key(
            attempt.basis_ref
        ) != artifact_ref_identity_key(expected_basis_ref):
            continue
        linked.append(attempt)
    if not linked:
        return ProducerArtifactAdmission("not_established", "producer_artifact_not_owner_linked")

    stale_seen = False
    identity_seen = False
    for attempt in linked:
        basis = attempt.basis
        if not engine_invocation_identity_is_current(
            ctx, basis, expected_component_id=expected_component_id
        ):
            identity_seen = True
            continue
        try:
            bound_ctx = replace(
                ctx,
                _engine_invocation=_EngineInvocationBinding(
                    run_id=basis.run_id,
                    attempt_id=basis.attempt_id,
                    basis_ref=attempt.basis_ref,
                    require_successful_completion=True,
                ),
            )
            producer_input = _load_engine_owned_invocation_input_state(bound_ctx, state)
            if producer_input is None:
                continue
            producer_output = _load_invocation_output_state(ctx, attempt.outcome.outcome_state_ref)
            current_source = _verified_finalization_predecessor(ctx, state) or state
            if not state_read_projection(
                producer_input,
                producer_output,
                current_source,
                expected_node_spec,
                source_read_paths=source_read_paths,
            ):
                stale_seen = True
                continue
            return ProducerArtifactAdmission("current", "producer_artifact_source_current")
        except Exception:
            continue
    if stale_seen:
        return ProducerArtifactAdmission("stale", "producer_source_projection_changed")
    if identity_seen:
        return ProducerArtifactAdmission(
            "not_established", "producer_implementation_identity_not_established"
        )
    return ProducerArtifactAdmission("not_established", "producer_source_basis_not_established")


def _workflow_invocation_params(
    ctx: ExecutionContext, basis: RunInvocationStarted
) -> dict[str, object]:
    """Read the exact selected node parameters from the linked workflow artifact."""
    from polisyos.scientist.orchestration.engine.workflow_spec import WorkflowSpec

    workflow_ref = basis.workflow_spec_ref
    if workflow_ref.manifest_profile_sha256 is None or not ctx.store.verify(workflow_ref).ok:
        raise ValueError("producer_workflow_spec_profile_or_cas_invalid")
    manifest = ctx.store.get_manifest(workflow_ref)
    if (
        manifest.kind != "scientist.workflow_spec"
        or manifest.artifact_schema is None
        or manifest.artifact_schema.name != "polisyos.scientist.orchestration.engine.WorkflowSpec"
        or manifest.artifact_schema.version != "1.0"
    ):
        raise ValueError("producer_workflow_spec_contract_invalid")
    workflow = WorkflowSpec.model_validate(from_canonical_bytes(ctx.store.get_bytes(workflow_ref)))
    alias = basis.node_alias
    component_id = basis.component_id
    selected = [item for item in workflow.nodes if item.alias == alias]
    if len(selected) != 1 or str(selected[0].node_id) != component_id:
        raise ValueError("producer_workflow_node_binding_invalid")
    return dict(selected[0].params)


def _load_invocation_output_state(ctx: ExecutionContext, ref: ArtifactRef) -> ExperimentState:
    """Read the exact successful outcome state snapshot from the run owner chain."""
    if ref.manifest_profile_sha256 is None or not ctx.store.verify(ref).ok:
        raise ValueError("producer_outcome_state_profile_or_cas_invalid")
    manifest = ctx.store.get_manifest(ref)
    if (
        ref.kind != "scientist.experiment_state"
        or manifest.kind != "scientist.experiment_state"
        or manifest.artifact_schema is None
        or manifest.artifact_schema.name
        != "polisyos.scientist.orchestration.engine.ExperimentState"
    ):
        raise ValueError("producer_outcome_state_contract_invalid")
    state = ExperimentState.model_validate(from_canonical_bytes(ctx.store.get_bytes(ref)))
    if state.schema_version != manifest.artifact_schema.version:
        raise ValueError("producer_outcome_state_schema_mismatch")
    return state


def state_read_projection(
    producer_input: ExperimentState,
    producer_output: ExperimentState,
    current: ExperimentState,
    spec: object,
    *,
    source_read_paths: tuple[str, ...],
) -> bool:
    """Recompute every declared producer read against the consumer's source state.

    A read path overlapping a producer write is compared with the engine-persisted
    successful output; all other reads are compared with the selected input state.
    """
    reads = _minimal_paths(source_read_paths)
    writes = tuple(
        tuple(part for part in path.split(".") if part)
        for path in getattr(spec, "state_writes", ())
    )
    current_payload = current.model_dump(mode="json")
    input_payload = producer_input.model_dump(mode="json")
    output_payload = producer_output.model_dump(mode="json")
    for path in reads:
        source = (
            output_payload
            if any(_paths_overlap(path, write) for write in writes)
            else input_payload
        )
        expected_present, expected = _lookup(source, path)
        current_present, actual = _lookup(current_payload, path)
        if expected_present != current_present:
            return False
        if expected_present and to_canonical_bytes(
            expected, _STATE_PROJECTION_CANON
        ) != to_canonical_bytes(actual, _STATE_PROJECTION_CANON):
            return False
    return True


def _verified_finalization_predecessor(
    ctx: ExecutionContext, current: ExperimentState
) -> ExperimentState | None:
    """Reverse only a persisted, owner-linked, exactly recomputed finalizer transition.

    The engine's post-workflow state is not treated as its terminal node output. A
    transition is usable only when the exact before/after states and every changed
    state reference are present in this run's CAS output chain. This preserves later
    node or caller edits because any edit beyond the terminal transition remains in
    the prior state or makes the recorded final state fail equality.
    """
    try:
        run_manifest = ctx.run.run_manifest
        outputs = ctx.run.read_runtime_owner_output_refs()
        engine_finalization_ref = ctx.run.read_runtime_workflow_finalization_ref()
        inputs = tuple(run_manifest.inputs)
        output_keys = {artifact_ref_identity_key(ref) for ref in outputs}
        input_keys = {artifact_ref_identity_key(ref) for ref in inputs}
        if current.run_id != run_manifest.run_id:
            return None
        current_payload = current.model_dump(mode="json")
        for receipt_ref in reversed(outputs):
            if (
                receipt_ref != engine_finalization_ref
                or receipt_ref.kind != FINALIZATION_KIND
                or receipt_ref.manifest_profile_sha256 is None
            ):
                continue
            if not ctx.store.verify(receipt_ref).ok:
                continue
            receipt_manifest = ctx.store.get_manifest(receipt_ref)
            schema = receipt_manifest.artifact_schema
            if (
                receipt_manifest.kind != FINALIZATION_KIND
                or schema is None
                or schema.name != FINALIZATION_SCHEMA_NAME
                or schema.version != FINALIZATION_SCHEMA_VERSION
            ):
                continue
            receipt = WorkflowStateFinalization.model_validate(
                from_canonical_bytes(ctx.store.get_bytes(receipt_ref))
            )
            if receipt.run_id != current.run_id:
                continue
            workflow_spec_ref = receipt.workflow_spec_ref
            if (
                workflow_spec_ref.manifest_profile_sha256 is None
                or artifact_ref_identity_key(workflow_spec_ref) not in input_keys
                or not ctx.store.verify(workflow_spec_ref).ok
            ):
                continue
            workflow_spec_manifest = ctx.store.get_manifest(workflow_spec_ref)
            workflow_spec_schema = workflow_spec_manifest.artifact_schema
            if (
                workflow_spec_manifest.kind != "scientist.workflow_spec"
                or workflow_spec_schema is None
                or workflow_spec_schema.name
                != "polisyos.scientist.orchestration.engine.WorkflowSpec"
                or workflow_spec_schema.version != "1.0"
            ):
                continue
            from polisyos.scientist.orchestration.engine.workflow_spec import WorkflowSpec

            workflow_spec = WorkflowSpec.model_validate(
                from_canonical_bytes(ctx.store.get_bytes(workflow_spec_ref))
            )
            if workflow_spec.workflow_id != receipt.workflow_id:
                continue
            prior_ref = receipt.prior_state_ref
            final_ref = receipt.final_state_ref
            if (
                prior_ref.manifest_profile_sha256 is None
                or final_ref.manifest_profile_sha256 is None
                or artifact_ref_identity_key(prior_ref) not in output_keys
                or artifact_ref_identity_key(final_ref) not in output_keys
            ):
                continue
            prior_state = _load_invocation_output_state(ctx, prior_ref)
            final_state = _load_invocation_output_state(ctx, final_ref)
            if (
                prior_state.run_id != current.run_id
                or final_state.run_id != current.run_id
                or final_state.model_dump(mode="json") != current_payload
            ):
                continue
            bindings = {
                binding.state_path: binding.artifact_ref for binding in receipt.output_bindings
            }
            if (
                len(bindings) != len(receipt.output_bindings)
                or FINAL_WORKFLOW_REPORT_STATE_PATH not in bindings
            ):
                continue
            if set(bindings) - set(FINALIZATION_OUTPUT_KINDS):
                continue
            final_payload = final_state.model_dump(mode="json")
            valid_bindings = True
            for path, ref in bindings.items():
                if (
                    ref.kind != FINALIZATION_OUTPUT_KINDS[path]
                    or artifact_ref_identity_key(ref) not in output_keys
                    or not ctx.store.verify(ref).ok
                ):
                    valid_bindings = False
                    break
                present, raw_ref = _lookup(final_payload, tuple(path.split(".")))
                try:
                    actual_ref = ArtifactRef.model_validate(raw_ref) if present else None
                except (TypeError, ValueError):
                    actual_ref = None
                if actual_ref is None or artifact_ref_identity_key(
                    actual_ref
                ) != artifact_ref_identity_key(ref):
                    valid_bindings = False
                    break
                output_manifest = ctx.store.get_manifest(ref)
                if output_manifest.kind != FINALIZATION_OUTPUT_KINDS[path]:
                    valid_bindings = False
                    break
            if not valid_bindings:
                continue
            report_ref = bindings[FINAL_WORKFLOW_REPORT_STATE_PATH]
            report_manifest = ctx.store.get_manifest(report_ref)
            report_schema = report_manifest.artifact_schema
            if (
                report_manifest.kind != "scientist.workflow_report"
                or report_schema is None
                or report_schema.name != "polisyos.scientist.orchestration.engine.WorkflowReport"
                or report_schema.version != "1.0"
            ):
                continue
            report_payload = from_canonical_bytes(ctx.store.get_bytes(report_ref))
            if (
                not isinstance(report_payload, dict)
                or report_payload.get("run_id") != receipt.run_id
                or report_payload.get("workflow_id") != receipt.workflow_id
            ):
                continue
            changed_paths = _state_diff_paths(
                prior_state.model_dump(mode="json"),
                final_payload,
                binding_paths={tuple(path.split(".")) for path in bindings},
            )
            if changed_paths - {tuple(path.split(".")) for path in bindings}:
                continue
            return prior_state
    except Exception:
        return None
    return None


def _state_diff_paths(
    before: object,
    after: object,
    *,
    binding_paths: set[tuple[str, ...]],
) -> set[tuple[str, ...]]:
    """Return the generic state diff, treating verified artifact bindings as leaves."""
    changed: set[tuple[str, ...]] = set()

    def visit(left: object, right: object, path: tuple[str, ...]) -> None:
        if path in binding_paths:
            if left != right:
                changed.add(path)
            return
        if isinstance(left, dict) and isinstance(right, dict):
            for key in left.keys() | right.keys():
                child = (*path, str(key))
                if key not in left or key not in right:
                    changed.add(child)
                else:
                    visit(left[key], right[key], child)
            return
        if left != right:
            changed.add(path)

    visit(before, after, ())
    return changed


def _minimal_paths(raw_paths: tuple[str, ...]) -> tuple[tuple[str, ...], ...]:
    paths = sorted({tuple(part for part in item.split(".") if part) for item in raw_paths})
    return tuple(
        path
        for path in paths
        if not any(other != path and _is_prefix(other, path) for other in paths)
    )


def _is_prefix(prefix: tuple[str, ...], path: tuple[str, ...]) -> bool:
    return len(prefix) <= len(path) and path[: len(prefix)] == prefix


def _paths_overlap(left: tuple[str, ...], right: tuple[str, ...]) -> bool:
    return _is_prefix(left, right) or _is_prefix(right, left)


def _lookup(value: object, path: tuple[str, ...]) -> tuple[bool, object]:
    current = value
    for part in path:
        if not isinstance(current, dict) or part not in current:
            return False, _MISSING
        current = current[part]
    return True, current


__all__ = [
    "ProducerArtifactAdmission",
    "ProducerArtifactCurrentness",
    "engine_invocation_identity_is_current",
    "resolve_engine_produced_artifact",
    "state_read_projection",
]
