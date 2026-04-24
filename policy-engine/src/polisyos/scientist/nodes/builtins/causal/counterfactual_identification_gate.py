"""Simulation gate that blocks policy candidates with unidentified counterfactual queries.

The node runs after `RunCausalReadinessNode` and before simulation. It reads the
persisted readiness bundle and an optional allow-list of required query ids,
then writes a compact gate summary into `state.params` for downstream search and
governance diagnostics.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.ir.observation.causal_readiness import (
    CausalReadinessBundle,
    CounterfactualCheckEntry,
    load_causal_readiness_bundle,
)
from polisyos.ir.refs import CausalReadinessBundleRef
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.protocol import NodeError, NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.engine.state_branching import branch_state
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_CAUSAL_READINESS_BUNDLE_REF

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_counterfactual_identification_gate@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Counterfactual Identification Gate",
    description="Block simulation when required counterfactual queries are not identified.",
    tags=["builtin", "causal", "counterfactual", "gate", "c6c"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=[
        f"artifacts_index.{ARTIFACT_CAUSAL_READINESS_BUNDLE_REF}",
        "params.required_counterfactual_query_ids",
    ],
    state_writes=[
        "params.counterfactual_gate_blocked",
        "params.counterfactual_gate_summary",
    ],
    produces=[],
)

_COUNTERFACTUAL_GATE_LOAD_ERRORS = (
    TypeError,
    ValueError,
    ValidationError,
    FileNotFoundError,
    OSError,
)


@dataclass(frozen=True)
class CounterfactualGateDecision:
    """Represent the normalized pass/fail decision for required counterfactual queries.

    Attributes:
        blocked: Whether simulation must stop for the current candidate.
        summary: JSON-compatible explanation containing checked query ids,
            failure metadata, or a skip reason.
    """

    blocked: bool
    summary: dict[str, Any]


@dataclass(frozen=True)
class CounterfactualIdentificationGateNode:
    """Fail the DAG branch when required counterfactual checks are not identified.

    Upstream assumptions: `artifacts_index.causal_readiness_bundle_ref` should
    contain the bundle emitted by `RunCausalReadinessNode`; if it is absent the
    gate records a skipped summary and lets the DAG continue. Required query ids
    are read from `params.required_counterfactual_query_ids`.

    Writes to state:
        `params.counterfactual_gate_blocked` and
        `params.counterfactual_gate_summary`.
    """

    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        """Evaluate the gate and convert blocked decisions into a failing `NodeOutcome`."""
        decision = evaluate_counterfactual_gate(ctx, state)
        new_state = branch_state(
            state,
            write_paths=(
                "params.counterfactual_gate_blocked",
                "params.counterfactual_gate_summary",
            ),
        ).state
        new_state.params["counterfactual_gate_blocked"] = decision.blocked
        new_state.params["counterfactual_gate_summary"] = dict(decision.summary)
        if not decision.blocked:
            return NodeOutcome(
                status="ok",
                state=new_state,
                events=[
                    NodeEvent(
                        level="info",
                        message="Counterfactual identification gate passed.",
                    )
                ],
            )
        return NodeOutcome(
            status="fail",
            state=new_state,
            error=NodeError(
                code=node_errors.ERROR_COUNTERFACTUAL_GATE_BLOCKED,
                message="Counterfactual identification gate blocked simulation.",
                details=dict(decision.summary),
            ),
            events=[
                NodeEvent(
                    level="warn",
                    code=node_errors.ERROR_COUNTERFACTUAL_GATE_BLOCKED,
                    message="Counterfactual identification gate blocked simulation.",
                    attrs={
                        "query_id": str(decision.summary.get("query_id") or ""),
                    },
                )
            ],
        )


def evaluate_counterfactual_gate(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> CounterfactualGateDecision:
    """Evaluate the counterfactual gate using readiness artifacts already in state.

    Args:
        ctx: Execution context used to load the persisted readiness bundle.
        state: Current DAG state containing `artifacts_index` and `params`.

    Returns:
        `CounterfactualGateDecision` with either a pass/skip summary or a
        blocker payload for the first failing required query.
    """

    readiness_ref = state.artifacts_index.get(ARTIFACT_CAUSAL_READINESS_BUNDLE_REF)
    required_query_ids = _required_query_ids(state.params)
    if readiness_ref is None:
        return CounterfactualGateDecision(
            blocked=False,
            summary={
                "status": "skipped",
                "blocked": False,
                "reason": "causal_readiness_bundle_missing",
                "required_query_ids": required_query_ids,
            },
        )
    try:
        bundle = load_causal_readiness_bundle(
            ctx.store,
            CausalReadinessBundleRef.model_validate(readiness_ref.model_dump(mode="json")),
        )
    except _COUNTERFACTUAL_GATE_LOAD_ERRORS as exc:
        return CounterfactualGateDecision(
            blocked=True,
            summary={
                "status": "invalid",
                "blocked": True,
                "query_id": None,
                "normalized_reason": f"causal_readiness_bundle_unreadable:{exc}",
                "required_query_ids": required_query_ids,
            },
        )
    return evaluate_counterfactual_readiness_bundle(
        bundle,
        required_query_ids=required_query_ids,
    )


def evaluate_counterfactual_readiness_bundle(
    bundle: CausalReadinessBundle,
    *,
    required_query_ids: tuple[str, ...] = (),
) -> CounterfactualGateDecision:
    """Check the supplied readiness bundle against required counterfactual query ids.

    Args:
        bundle: Readiness bundle emitted by `RunCausalReadinessNode`.
        required_query_ids: Optional subset of query ids that must be identified.

    Returns:
        Gate decision summarizing pass, skip, or blocked status.
    """

    results = list(bundle.counterfactual_results)
    if required_query_ids:
        results = [item for item in results if item.query_id in set(required_query_ids)]
    if not results:
        return CounterfactualGateDecision(
            blocked=False,
            summary={
                "status": "skipped",
                "blocked": False,
                "reason": "no_counterfactual_queries",
                "required_query_ids": list(required_query_ids),
            },
        )

    failing = [item for item in results if not _is_identified_counterfactual(item)]
    if not failing:
        return CounterfactualGateDecision(
            blocked=False,
            summary={
                "status": "pass",
                "blocked": False,
                "required_query_ids": [item.query_id for item in results],
                "checked_query_count": len(results),
            },
        )

    primary = failing[0]
    return CounterfactualGateDecision(
        blocked=True,
        summary={
            "status": "blocked",
            "blocked": True,
            "query_id": primary.query_id,
            "algorithm_version": primary.algorithm_version,
            "normalized_reason": primary.normalized_reason,
            "required_query_ids": [item.query_id for item in results],
            "failing_queries": [_counterfactual_failure_payload(item) for item in failing],
        },
    )


def _required_query_ids(params: Mapping[str, Any]) -> tuple[str, ...]:
    raw = params.get("required_counterfactual_query_ids")
    if not isinstance(raw, list):
        return ()
    values = [str(item).strip() for item in raw if str(item).strip()]
    return tuple(sorted(set(values)))


def _is_identified_counterfactual(entry: CounterfactualCheckEntry) -> bool:
    status = str(entry.status).strip().lower()
    if status == "identified":
        return True
    if "conflict" in status:
        return False
    return False


def _counterfactual_failure_payload(
    entry: CounterfactualCheckEntry,
) -> dict[str, Any]:
    return {
        "query_id": entry.query_id,
        "status": entry.status,
        "algorithm_version": entry.algorithm_version,
        "normalized_reason": entry.normalized_reason,
    }


__all__ = [
    "CounterfactualGateDecision",
    "CounterfactualIdentificationGateNode",
    "evaluate_counterfactual_gate",
    "evaluate_counterfactual_readiness_bundle",
]
