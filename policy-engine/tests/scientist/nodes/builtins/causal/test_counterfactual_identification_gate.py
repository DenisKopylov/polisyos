from __future__ import annotations

from unittest.mock import patch

import pytest

from polisyos.ir.observation.causal_readiness import (
    CausalReadinessBundle,
    CounterfactualCheckEntry,
    persist_causal_readiness_bundle,
)
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.causal.counterfactual_identification_gate import (
    CounterfactualIdentificationGateNode,
)
from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_CAUSAL_READINESS_BUNDLE_REF


def test_counterfactual_gate_passes_when_all_queries_identified(
    execution_context,
    minimal_state,
) -> None:
    bundle_ref = persist_causal_readiness_bundle(
        execution_context.store,
        CausalReadinessBundle(
            counterfactual_results=[
                CounterfactualCheckEntry(
                    query_id="cf_1",
                    status="identified",
                    algorithm_version="id_star_v1",
                    normalized_reason="identified",
                )
            ]
        ),
    )
    state = minimal_state.model_copy(deep=True)
    state.artifacts_index[ARTIFACT_CAUSAL_READINESS_BUNDLE_REF] = bundle_ref

    outcome = CounterfactualIdentificationGateNode().execute(execution_context, state)

    assert outcome.status == "ok"
    assert outcome.state.params["counterfactual_gate_blocked"] is False
    assert outcome.state.params["counterfactual_gate_summary"]["status"] == "pass"


def test_counterfactual_gate_blocks_when_query_not_identified(
    execution_context,
    minimal_state,
) -> None:
    bundle_ref = persist_causal_readiness_bundle(
        execution_context.store,
        CausalReadinessBundle(
            counterfactual_results=[
                CounterfactualCheckEntry(
                    query_id="cf_blocked",
                    status="hedge_conflict",
                    algorithm_version="id_star_v1",
                    normalized_reason="hedge_detected",
                )
            ]
        ),
    )
    state = minimal_state.model_copy(deep=True)
    state.artifacts_index[ARTIFACT_CAUSAL_READINESS_BUNDLE_REF] = bundle_ref

    outcome = CounterfactualIdentificationGateNode().execute(execution_context, state)

    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == node_errors.ERROR_COUNTERFACTUAL_GATE_BLOCKED
    assert outcome.state.params["counterfactual_gate_blocked"] is True
    assert outcome.state.params["counterfactual_gate_summary"]["query_id"] == "cf_blocked"
    assert (
        outcome.state.params["counterfactual_gate_summary"]["normalized_reason"] == "hedge_detected"
    )


def test_counterfactual_gate_bundle_assertion_is_not_swallowed(
    execution_context,
    minimal_state,
    artifact_ref_factory,
) -> None:
    state = minimal_state.model_copy(deep=True)
    state.artifacts_index[ARTIFACT_CAUSAL_READINESS_BUNDLE_REF] = artifact_ref_factory(
        kind="ir.causal_readiness_bundle"
    )

    with patch(
        "polisyos.scientist.nodes.builtins.causal.counterfactual_identification_gate.load_causal_readiness_bundle",
        side_effect=AssertionError("readiness invariant"),
    ):
        with pytest.raises(AssertionError, match="readiness invariant"):
            CounterfactualIdentificationGateNode().execute(execution_context, state)
