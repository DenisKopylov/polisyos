"""Public causal run causal queries module API."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
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
from polisyos.ir.analytics.uncertainty import UncertaintyEnvelope, persist_uncertainty_envelope
from polisyos.ir.refs import StructuralCausalModelSpecRef
from polisyos.scientist.compute.job_spec import JobSpec
from polisyos.scientist.compute.runner import run_job
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.protocol import NodeError, NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CAUSAL_ENVELOPE_REF,
    ARTIFACT_CAUSAL_QUERY_ENVELOPE_REF,
    ARTIFACT_CAUSAL_QUERY_METHOD_EVIDENCE_REF,
    ARTIFACT_CAUSAL_QUERY_METHOD_RESULT_REF,
    ARTIFACT_CAUSAL_QUERY_RESULT_REF,
    ARTIFACT_STRUCTURAL_CAUSAL_MODEL_SPEC_REF,
)

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


def _coerce_ref(raw: Any) -> ArtifactRef | None:
    if raw is None:
        return None
    if isinstance(raw, ArtifactRef):
        return raw
    if isinstance(raw, Mapping):
        try:
            return ArtifactRef.model_validate(raw)
        except Exception:
            return None
    if isinstance(raw, str):
        try:
            artifact_id = ArtifactID.model_validate(raw)
        except Exception:
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
        except Exception as exc:
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
        except Exception as exc:
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
        except Exception as exc:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_INVALID_STATE,
                    message=f"Invalid SCM/query combination: {exc}",
                ),
            )

        ensure_causal_methods_registered()
        result = run_job(
            JobSpec(
                job_kind="method",
                method_fqn=_METHOD_FQN,
                method_params={},
                seed=seed,
            ),
            cas_root=ctx.store.root,
            method_state=method_state,
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

        output = result.final_state if isinstance(result.final_state, dict) else {}
        raw_query_result = output.get("query_result")
        if raw_query_result is None:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_FOUNDRY_EXECUTE_FAILED,
                    message="Causal query output missing query_result",
                ),
            )

        try:
            query_result = CausalQueryResult.model_validate(raw_query_result)
        except Exception as exc:
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
        )

        envelope_payload = output.get("envelope")
        if envelope_payload is not None:
            envelope = UncertaintyEnvelope.model_validate(envelope_payload)
        else:
            envelope = query_result.to_uncertainty_envelope()
        envelope_ref = persist_uncertainty_envelope(
            ctx.store,
            envelope,
            inputs=input_refs,
        )

        new_state = state.model_copy(deep=True)
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
