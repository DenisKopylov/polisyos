from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from polisyos.core.artifacts.manifest import InputRef
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.foundry.methods.catalog.causal.graph_reconciliation import ReconcileCausalGraph
from polisyos.foundry.methods.catalog.causal.protocols import (
    GraphReconciliationData,
    LLMStructuralHint,
)
from polisyos.ir.analytics.causal_graph import CausalGraphModel, persist_causal_graph_model
from polisyos.ir.analytics.literature import load_literature_causal_prior
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.protocol import NodeError, NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CAUSAL_METHOD_RESULT_REF,
    ARTIFACT_LITERATURE_PRIOR_REF,
    ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF,
)

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_reconcile_causal_graph@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Reconcile Causal Graph",
    description="Merge data graph, literature prior, and LLM hints into reconciled graph.",
    tags=["builtin", "causal", "prior", "reconciliation"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=[
        f"artifacts_index.{ARTIFACT_LITERATURE_PRIOR_REF}",
        f"artifacts_index.{ARTIFACT_CAUSAL_METHOD_RESULT_REF}",
        "params.data_causal_graph",
        "params.llm_structural_hints",
        "params.reconciliation_min_edge_confidence",
        "params.reconciliation_max_lag_depth",
        "params.reconciliation_max_lagged_edges",
        "params.reconciliation_max_cycles_to_resolve",
    ],
    state_writes=[
        f"artifacts_index.{ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF}",
        "params.needs_expert_review",
        "params.reconciliation_diagnostics",
        "params.reconciliation_warnings",
    ],
    produces=[ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF],
)


def _optional_float(value: Any, *, default: float) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _optional_int(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _extract_graph(payload: Any) -> CausalGraphModel | None:
    if isinstance(payload, CausalGraphModel):
        return payload
    if isinstance(payload, dict):
        if {"graph_type", "nodes", "edges"}.issubset(payload.keys()):
            try:
                return CausalGraphModel.model_validate(payload)
            except Exception:
                return None
        for key in ("graph", "causal_graph", "reconciled_graph", "literature_prior_graph"):
            if key not in payload:
                continue
            try:
                return CausalGraphModel.model_validate(payload[key])
            except Exception:
                continue
    return None


def _load_data_graph(ctx: ExecutionContext, state: ExperimentState) -> tuple[CausalGraphModel | None, Any | None]:
    if "data_causal_graph" in state.params:
        graph = _extract_graph(state.params.get("data_causal_graph"))
        if graph is not None:
            return graph, None

    method_ref = state.artifacts_index.get(ARTIFACT_CAUSAL_METHOD_RESULT_REF)
    if method_ref is not None:
        try:
            payload = from_canonical_bytes(ctx.store.get_bytes(method_ref.artifact_id))
            graph = _extract_graph(payload)
            if graph is not None:
                return graph, method_ref
        except Exception:
            pass

    return None, None


def _parse_llm_hints(raw: Any) -> list[LLMStructuralHint]:
    if not isinstance(raw, list):
        return []
    hints: list[LLMStructuralHint] = []
    for item in raw:
        try:
            hints.append(LLMStructuralHint.model_validate(item))
        except Exception:
            continue
    return hints


@dataclass(frozen=True)
class ReconcileCausalGraphNode:
    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        if ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF in state.artifacts_index:
            return NodeOutcome(status="ok", state=state)

        data_graph, data_graph_ref = _load_data_graph(ctx, state)
        if data_graph is None:
            return NodeOutcome(
                status="skip",
                state=state,
                events=[NodeEvent(level="info", message="No data causal graph; skip reconciliation.")],
            )

        literature_prior_ref = state.artifacts_index.get(ARTIFACT_LITERATURE_PRIOR_REF)
        literature_prior = None
        if literature_prior_ref is not None:
            try:
                literature_prior = load_literature_causal_prior(ctx.store, literature_prior_ref)
            except Exception:
                literature_prior = None

        llm_hints = _parse_llm_hints(state.params.get("llm_structural_hints"))

        try:
            request = GraphReconciliationData(
                data_graph=data_graph,
                literature_prior=literature_prior,
                llm_hints=llm_hints,
                min_edge_confidence=_optional_float(
                    state.params.get("reconciliation_min_edge_confidence"),
                    default=0.1,
                ),
                max_lag_depth=_optional_int(
                    state.params.get("reconciliation_max_lag_depth"),
                    default=2,
                ),
                max_lagged_edges=_optional_int(
                    state.params.get("reconciliation_max_lagged_edges"),
                    default=10,
                ),
                max_cycles_to_resolve=_optional_int(
                    state.params.get("reconciliation_max_cycles_to_resolve"),
                    default=8,
                ),
            )
            result = ReconcileCausalGraph.pure_step(request, params={})
        except Exception as exc:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_FOUNDRY_EXECUTE_FAILED,
                    message=f"reconcile_causal_graph execution failed: {exc}",
                ),
            )

        reconciled_graph = result.get("reconciled_graph")
        diagnostics = result.get("diagnostics")
        if reconciled_graph is None or diagnostics is None:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_INVALID_STATE,
                    message="reconcile_causal_graph did not return graph and diagnostics",
                ),
            )

        inputs: list[InputRef] = []
        if data_graph_ref is not None:
            inputs.append(InputRef(artifact_id=str(data_graph_ref.artifact_id), role="data_graph"))
        if literature_prior_ref is not None:
            inputs.append(
                InputRef(
                    artifact_id=str(literature_prior_ref.artifact_id),
                    role="literature_prior",
                )
            )
        graph_ref = persist_causal_graph_model(ctx.store, reconciled_graph, inputs=inputs)

        new_state = state.model_copy(deep=True)
        new_state.artifacts_index[ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF] = graph_ref
        new_state.params["needs_expert_review"] = bool(result.get("needs_expert_review", False))
        new_state.params["reconciliation_diagnostics"] = diagnostics.model_dump(mode="json")
        new_state.params["reconciliation_warnings"] = [
            str(item) for item in result.get("warnings", [])
        ]

        return NodeOutcome(
            status="ok",
            state=new_state,
            artifacts=[graph_ref],
            events=[
                NodeEvent(
                    level="info",
                    message=(
                        "Causal graph reconciled; "
                        f"needs_expert_review={new_state.params['needs_expert_review']}."
                    ),
                )
            ],
        )


__all__ = ["ReconcileCausalGraphNode"]
