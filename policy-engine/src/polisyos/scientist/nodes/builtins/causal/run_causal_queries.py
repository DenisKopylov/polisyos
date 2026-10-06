"""Public causal run causal queries module API."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import nullcontext
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from polisyos.common.serialization import to_python_data
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef
from polisyos.core.canon import CanonSpec, from_canonical_bytes, to_canonical_bytes
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.foundry.methods import (
    causal_worker_execution_context,
    validate_source_bound_causal_estimator_interval,
    validate_source_bound_gcm_spec,
)
from polisyos.foundry.methods.catalog import (
    ensure_all_methods_registered as ensure_causal_methods_registered,
)
from polisyos.foundry.methods.catalog.causal.protocols import SCMQueryData
from polisyos.ir.analytics.causal_queries import (
    CausalQuery,
    CausalQueryResult,
    persist_causal_query_result,
)
from polisyos.ir.analytics.structural_causal_model import load_structural_causal_model_spec
from polisyos.ir.analytics.uncertainty import persist_uncertainty_envelope
from polisyos.ir.registry.refs import StructuralCausalModelSpecRef
from polisyos.scientist.compute.job_spec import JobSpec
from polisyos.scientist.compute.runner import run_job
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CAUSAL_ENVELOPE_REF,
    ARTIFACT_CAUSAL_QUERY_ENVELOPE_REF,
    ARTIFACT_CAUSAL_QUERY_METHOD_EVIDENCE_REF,
    ARTIFACT_CAUSAL_QUERY_METHOD_RESULT_REF,
    ARTIFACT_CAUSAL_QUERY_RESULT_REF,
    ARTIFACT_STRUCTURAL_CAUSAL_MODEL_SPEC_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.protocol import (
    NodeError,
    NodeEvent,
    NodeOutcome,
    NodeSpec,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state

_METHOD_FQN = "causal.structural.gcm_query@1.0.0"

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_run_causal_queries@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Run Causal Queries",
    description=(
        "Execute structural causal query (interventional/counterfactual), "
        "persist query result and uncertainty envelope."
    ),
    tags=["builtin", "causal", "query"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=[
        "params.random_seed",
        "params.causal_query",
        "params.causal_estimator_bootstrap_replicates",
        "params.structural_causal_model_ref",
        f"artifacts_index.{ARTIFACT_STRUCTURAL_CAUSAL_MODEL_SPEC_REF}",
    ],
    state_writes=[
        "params.query_treatment",
        f"artifacts_index.{ARTIFACT_STRUCTURAL_CAUSAL_MODEL_SPEC_REF}",
        f"artifacts_index.{ARTIFACT_CAUSAL_QUERY_RESULT_REF}",
        f"artifacts_index.{ARTIFACT_CAUSAL_QUERY_ENVELOPE_REF}",
        f"artifacts_index.{ARTIFACT_CAUSAL_QUERY_METHOD_RESULT_REF}",
        f"artifacts_index.{ARTIFACT_CAUSAL_QUERY_METHOD_EVIDENCE_REF}",
        f"artifacts_index.{ARTIFACT_CAUSAL_ENVELOPE_REF}",
    ],
    produces=[
        ARTIFACT_CAUSAL_QUERY_RESULT_REF,
        ARTIFACT_CAUSAL_QUERY_ENVELOPE_REF,
        ARTIFACT_CAUSAL_QUERY_METHOD_RESULT_REF,
        ARTIFACT_CAUSAL_QUERY_METHOD_EVIDENCE_REF,
        ARTIFACT_CAUSAL_ENVELOPE_REF,
    ],
)

_CAUSAL_QUERY_REF_ERRORS = (TypeError, ValueError, ValidationError)
_CAUSAL_QUERY_LOAD_ERRORS = (
    KeyError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
    ValidationError,
)


def _coerce_ref(raw: Any) -> ArtifactRef | None:
    if raw is None:
        return None
    if isinstance(raw, ArtifactRef):
        return raw
    if isinstance(raw, Mapping):
        try:
            return ArtifactRef.model_validate(raw)
        except _CAUSAL_QUERY_REF_ERRORS:
            return None
    if isinstance(raw, str):
        try:
            artifact_id = ArtifactID.model_validate(raw)
        except _CAUSAL_QUERY_REF_ERRORS:
            return None
        return ArtifactRef(
            artifact_id=artifact_id,
            kind="ir.structural_causal_model_spec",
            media_type="application/json",
        )
    return None


def _resolve_structural_model_ref(state: ExperimentState) -> ArtifactRef | None:
    explicit = _coerce_ref(state.params.get("structural_causal_model_ref"))
    if explicit is not None:
        return explicit
    return _coerce_ref(state.artifacts_index.get(ARTIFACT_STRUCTURAL_CAUSAL_MODEL_SPEC_REF))


def _append_input_ref(
    refs: list[InputRef],
    *,
    artifact_id: Any | None,
    role: str,
) -> None:
    if artifact_id is None:
        return
    refs.append(InputRef(artifact_id=artifact_id, role=role))


def _load_bound_query_result(
    ctx: ExecutionContext,
    result: Any,
    query: CausalQuery,
    scm_ref: ArtifactRef,
) -> CausalQueryResult:
    """Reconcile the complete job projection and requested query against actual CAS."""
    ref = result.method_result_ref
    if not isinstance(ref, ArtifactRef):
        raise ValueError("causal query method_result_ref is required")
    manifest = ctx.store.get_manifest(ref)
    schema = manifest.artifact_schema
    if (
        ref.kind != "scientist.method_result.causal.structural"
        or manifest.kind != ref.kind
        or ref.media_type != "application/json"
        or manifest.media_type != ref.media_type
        or schema is None
        or schema.name != "polisyos.scientist.MethodResult"
        or schema.version != "0.1.0"
        or not ctx.store.verify(ref).ok
    ):
        raise ValueError("causal query method-result artifact identity mismatch")
    if not any(
        item.artifact_id == scm_ref.artifact_id and item.role == "input:scm_spec"
        for item in manifest.inputs
    ):
        raise ValueError("causal query method result lacks original SCM input binding")
    source_bytes = ctx.store.get_bytes(ref)
    payload = from_canonical_bytes(source_bytes)
    if not isinstance(payload, dict) or not isinstance(result.final_state, dict):
        raise ValueError("causal query method result must be an object")
    # Use the same complete runtime-to-JSON projection as the canonical job writer.
    # This includes draws, both aliases, metadata, envelopes and ancillary outputs.
    peer_bytes = to_canonical_bytes(
        to_python_data(result.final_state, sort_keys=True), CanonSpec(forbid_floats=False)
    )
    if peer_bytes != source_bytes:
        raise ValueError("causal query peer output differs from canonical method-result payload")
    if "causal_query_result" not in payload or "query_result" not in payload:
        raise ValueError("causal query output requires canonical and historical result aliases")
    canonical = CausalQueryResult.model_validate(payload["causal_query_result"])
    historical_alias = CausalQueryResult.model_validate(payload["query_result"])
    if canonical.model_dump(mode="json") != historical_alias.model_dump(mode="json"):
        raise ValueError("causal query result aliases disagree")
    if canonical.query.model_dump(mode="json") != query.model_dump(mode="json"):
        raise ValueError("causal query result does not match original requested query")
    return canonical


@dataclass(frozen=True)
class RunCausalQueriesNode:
    """Execute the configured causal query against the resolved SCM artifact."""

    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        query_payload = state.params.get("causal_query")
        if query_payload is None:
            return NodeOutcome(
                status="skip",
                state=state,
                events=[
                    NodeEvent(
                        level="info",
                        message="No params.causal_query; skip causal query execution.",
                    )
                ],
            )

        scm_ref = _resolve_structural_model_ref(state)
        if scm_ref is None:
            return NodeOutcome(
                status="skip",
                state=state,
                events=[
                    NodeEvent(
                        level="info",
                        message=(
                            "No structural_causal_model_ref in params/artifacts_index; "
                            "skip causal query execution."
                        ),
                    )
                ],
            )

        try:
            query = CausalQuery.model_validate(query_payload)
        except _CAUSAL_QUERY_LOAD_ERRORS as exc:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_INVALID_STATE,
                    message=f"Invalid params.causal_query payload: {exc}",
                ),
            )

        try:
            scm_spec_ref = StructuralCausalModelSpecRef.model_validate(
                scm_ref.model_dump(mode="json")
            )
            scm_spec = load_structural_causal_model_spec(ctx.store, scm_spec_ref)
            validate_source_bound_gcm_spec(scm_spec, ctx.store)
        except _CAUSAL_QUERY_LOAD_ERRORS as exc:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_MISSING_INPUT,
                    message=f"Failed to load StructuralCausalModelSpec: {exc}",
                ),
            )

        seed = int(state.params.get("random_seed", 0) or 0)
        try:
            method_state = SCMQueryData(scm_spec=scm_spec, query=query)
        except _CAUSAL_QUERY_LOAD_ERRORS as exc:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_INVALID_STATE,
                    message=f"Invalid SCM/query combination: {exc}",
                ),
            )

        ensure_causal_methods_registered()
        bootstrap_replicates = state.params.get("causal_estimator_bootstrap_replicates", 0)
        execution_context = nullcontext()
        if bootstrap_replicates and scm_spec.training_rows is not None:
            execution_context = causal_worker_execution_context(
                store=ctx.store,
                source_ref=ArtifactRef.model_validate(
                    scm_spec.training_rows.source_ref.model_dump(mode="json")
                ),
            )
        try:
            with execution_context:
                result = run_job(
                    JobSpec(
                        job_kind="method",
                        method_fqn=_METHOD_FQN,
                        method_params={"bootstrap_replicates": bootstrap_replicates},
                        input_refs={"scm_spec": scm_ref},
                        seed=seed,
                    ),
                    cas_root=ctx.store.root,
                    method_state=method_state,
                )
        except _CAUSAL_QUERY_LOAD_ERRORS as exc:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_FOUNDRY_EXECUTE_FAILED,
                    message=f"Causal query source/refit execution failed: {exc}",
                ),
            )
        if result.issues:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_FOUNDRY_EXECUTE_FAILED,
                    message="Causal query method job failed",
                    details={"issues": result.issues},
                ),
            )

        try:
            query_result = _load_bound_query_result(ctx, result, query, scm_ref)
            if query_result.estimator_interval is not None:
                validate_source_bound_causal_estimator_interval(
                    query_result.estimator_interval,
                    scm_spec,
                    query,
                    ctx.store,
                )
        except _CAUSAL_QUERY_LOAD_ERRORS as exc:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_FOUNDRY_EXECUTE_FAILED,
                    message=f"Invalid causal query result payload: {exc}",
                ),
            )

        input_refs: list[InputRef] = [
            InputRef(artifact_id=scm_ref.artifact_id, role="structural_causal_model_spec")
        ]
        if result.method_result_ref is not None:
            _append_input_ref(
                input_refs,
                artifact_id=result.method_result_ref.artifact_id,
                role="causal_query_method_result",
            )
        if result.method_evidence_ref is not None:
            _append_input_ref(
                input_refs,
                artifact_id=result.method_evidence_ref.artifact_id,
                role="causal_query_method_evidence",
            )

        query_result_ref = persist_causal_query_result(
            ctx.store,
            query_result,
            inputs=input_refs,
            schema_version=query_result.schema_version,
        )

        # The typed result is the producer's source of truth.  A method output
        # envelope is only a peer projection and must not override its arms or
        # eligibility when the two disagree.
        envelope = query_result.to_uncertainty_envelope()
        member_gate_eligible = bool(
            query_result.metadata.get("abduction_gate_eligible", True)
        ) and not query_result.metadata.get("declared_root_hypothesis")
        if not member_gate_eligible:
            envelope_metadata = dict(envelope.metadata)
            envelope_metadata["member_gate_eligible"] = False
            if query_result.metadata.get("declared_root_hypothesis"):
                envelope_metadata["declared_root_hypothesis"] = query_result.metadata[
                    "declared_root_hypothesis"
                ]
            envelope = envelope.model_copy(
                update={
                    "gate_eligible": False,
                    "metadata": envelope_metadata,
                }
            )
        envelope_ref = persist_uncertainty_envelope(
            ctx.store,
            envelope,
            inputs=input_refs,
        )

        new_state = branch_state(state, write_paths=_SPEC.state_writes).state
        new_state.params["query_treatment"] = query.treatment_variable
        new_state.artifacts_index[ARTIFACT_STRUCTURAL_CAUSAL_MODEL_SPEC_REF] = scm_spec_ref
        new_state.artifacts_index[ARTIFACT_CAUSAL_QUERY_RESULT_REF] = query_result_ref
        new_state.artifacts_index[ARTIFACT_CAUSAL_QUERY_ENVELOPE_REF] = envelope_ref
        new_state.artifacts_index[ARTIFACT_CAUSAL_ENVELOPE_REF] = envelope_ref
        if result.method_result_ref is not None:
            new_state.artifacts_index[ARTIFACT_CAUSAL_QUERY_METHOD_RESULT_REF] = (
                result.method_result_ref
            )
        if result.method_evidence_ref is not None:
            new_state.artifacts_index[ARTIFACT_CAUSAL_QUERY_METHOD_EVIDENCE_REF] = (
                result.method_evidence_ref
            )

        produced: list[ArtifactRef] = [query_result_ref, envelope_ref]
        if result.method_result_ref is not None:
            produced.append(result.method_result_ref)
        if result.method_evidence_ref is not None:
            produced.append(result.method_evidence_ref)

        return NodeOutcome(
            status="ok",
            state=new_state,
            artifacts=produced,
            events=[
                NodeEvent(
                    level="info",
                    message=(
                        "Causal query completed: "
                        f"type={query.query_type.value}, "
                        f"treatment={query.treatment_variable}, "
                        f"outcome={query.outcome_variable}"
                    ),
                )
            ],
        )


__all__ = ["RunCausalQueriesNode"]
