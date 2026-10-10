"""Behavior tests for distributional-bounds admission and CAS outputs."""

from __future__ import annotations

import numpy as np

from polisyos.core.artifacts import ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import InputRef
from polisyos.core.artifacts.store import PutOptions
from polisyos.ir.analytics.distributional import (
    DistributionalFunctional,
    load_distributional_bounds_bundle,
    load_distributional_dual_certificate,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_bounds import (
    _prepare_distributional_bounds_request,
    _resolve_distributional_bounds,
)


def test_mtr_bounds_require_assumption_and_round_trip_certificate(
    execution_context,
    minimal_state,
    cas_store,
) -> None:
    baseline = np.asarray([10.0, 12.0, 15.0, 18.0])
    counterfactual = np.asarray([11.0, 13.0, 17.0, 20.0])
    request = {
        "theorem_family": "mtr_headcount",
        "assumptions": ["monotone_treatment_response_y1_ge_y0"],
        "outcome": [1.0, 3.0, 2.0, 4.0],
        "treatment": [1.0, 1.0, 0.0, 0.0],
        "poverty_lines": [2.5],
        "target_potential_outcome": "y1",
    }
    state = minimal_state.model_copy(deep=True)

    prepared = _prepare_distributional_bounds_request(
        request,
        config={},
        state=state,
        baseline_values=baseline,
        counterfactual_values=counterfactual,
    )
    alias_request = {key: value for key, value in request.items() if key != "theorem_family"}
    alias_request["method_family"] = request["theorem_family"]
    alias_prepared = _prepare_distributional_bounds_request(
        alias_request,
        config={},
        state=state,
        baseline_values=baseline,
        counterfactual_values=counterfactual,
    )
    assert prepared.skip_reason is None
    assert alias_prepared.skip_reason is None
    assert alias_prepared.family == prepared.family
    assert alias_prepared.state_payload is not None
    assert prepared.state_payload is not None
    np.testing.assert_array_equal(
        alias_prepared.state_payload["outcome"], prepared.state_payload["outcome"]
    )

    state.params["distributional_bounds"] = {"enabled": True, "requests": [request]}
    source_ref = cas_store.put_json(
        {"source": "distributional-bounds-test"},
        PutOptions(kind="test.distributional_input", media_type="application/json"),
    )
    resolution = _resolve_distributional_bounds(
        execution_context,
        state,
        baseline_values=baseline,
        counterfactual_values=counterfactual,
        inputs=[InputRef(artifact_id=source_ref.artifact_id, role="distributional_input")],
    )

    assert resolution.metadata["status"] == "bounded"
    assert resolution.refs
    assert resolution.functionals == [DistributionalFunctional.POVERTY_HEADCOUNT.value]
    store = ensure_ir_artifact_store(cas_store)
    bounds = load_distributional_bounds_bundle(store, resolution.refs[0])
    assert bounds.functional is DistributionalFunctional.POVERTY_HEADCOUNT
    assert bounds.dual_certificate_ref is not None
    certificate = load_distributional_dual_certificate(store, bounds.dual_certificate_ref)
    assert certificate.theorem_family == "mtr_headcount"
    assert certificate.assumption_class == "mtr"

    missing_assumption = minimal_state.model_copy(deep=True)
    missing_assumption.params["distributional_bounds"] = {
        "enabled": True,
        "requests": [{**request, "assumptions": []}],
    }
    refused = _resolve_distributional_bounds(
        execution_context,
        missing_assumption,
        baseline_values=baseline,
        counterfactual_values=counterfactual,
        inputs=[InputRef(artifact_id=source_ref.artifact_id, role="distributional_input")],
    )
    assert refused.refs == []
    assert refused.metadata["status"] == "requested_but_not_applicable"
    assert refused.metadata["skipped_reasons"] == ["request_0:missing_mtr_assumption"]
