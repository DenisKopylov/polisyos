"""Exercise HTE contrast admission from the validated writer capture."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
from pydantic import ValidationError


def _fixture() -> tuple[Any, Any, Any, Any, dict[str, Any], Any, Any]:
    """Build matching Core owner and HTE producer captures with null contrast params."""
    from polisyos.core.contracts.owned_attempt_anchor import (
        OwnedAttemptAnchorDispatchContext,
        OwnedAttemptAnchorRef,
        OwnedAttemptPhysicalSourceBindingRef,
        OwnedHTERequestContextV1,
    )
    from polisyos.foundry.methods.catalog.causal.hte_v2 import (
        CausalForestEstimatorV2,
        _capture_facts,
        build_hte_data,
        build_owned_hte_input_capture,
    )
    from polisyos.foundry.methods.catalog.causal.protocols import HTEObservationalData

    row_count = 40
    row_ids = np.arange(row_count)
    data = HTEObservationalData(
        outcome=np.asarray([float(index) / 10 + (index % 2) * 0.5 for index in row_ids]),
        treatment=np.asarray([index % 2 for index in row_ids], dtype=int),
        covariates=np.asarray([[float(index), float(index % 5)] for index in row_ids]),
        confounders=np.asarray([[float(index % 7)] for index in row_ids]),
        feature_names=["x0", "x1"],
        confounder_names=["w0"],
    )
    method = CausalForestEstimatorV2
    params = {parameter.name: parameter.default for parameter in method.signature.parameters}
    params.update(
        alpha=0.05,
        control_value=None,
        treated_value=None,
        random_state=7,
        n_jobs=1,
    )
    binding = OwnedAttemptPhysicalSourceBindingRef(
        artifact_id="sha256:" + "5" * 64,
        kind="foundry.hte.physical_source_materialization_binding",
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "6" * 64,
    )
    request = OwnedHTERequestContextV1(
        request_estimand_status="declared",
        request_estimand="mean_effect_over_selected_x",
        request_target_scope_status="declared",
        request_target_scope="population",
        outcome_variable_status="declared",
        outcome_variable_id="outcome",
        treatment_variable_status="declared",
        treatment_variable_id="treatment",
        contrast_status="declared",
        control_value=0.0,
        treated_value=1.0,
        request_alpha_status="declared",
        requested_alpha=0.05,
        requested_guarantee_status="declared",
        requested_guarantee="backend_conditional_interval",
        materialization_binding_ref=binding,
    )
    source_ref = {
        "artifact_id": "sha256:" + "1" * 64,
        "kind": "ir.observation_method_input",
        "media_type": "application/json",
        "manifest_profile_sha256": "sha256:" + "2" * 64,
    }
    core_capture = build_owned_hte_input_capture(
        data,
        source_data_ref=source_ref,
        method_class=method,
        method_abi_digest=method.signature.abi_digest(),
        resolved_params=params,
        seed=7,
        request_context=request,
    )
    context = OwnedAttemptAnchorDispatchContext(
        anchor_ref=OwnedAttemptAnchorRef(
            artifact_id="sha256:" + "3" * 64,
            kind="runtime.owned_attempt_anchor",
            media_type="application/json",
            manifest_profile_sha256="sha256:" + "4" * 64,
        ),
        input_capture=core_capture,
        method_abi_digest=method.signature.abi_digest(),
    )
    writer_capture = _capture_facts(
        build_hte_data(data),
        data,
        {**params, "__seed__": 7},
        method_fqn=method.owned_hte_method_fqn,
        method_abi=method.owned_hte_method_abi,
        method_profile_id=method.owned_hte_profile_id,
        runtime_context=context,
    )
    anchor = SimpleNamespace(
        input_capture=core_capture,
        effective_input_ref=core_capture.source_data_ref,
    )
    return data, method, request, context, params, writer_capture, anchor


def test_relation_recomputes_contrast_from_owner_reconciled_writer_capture() -> None:
    """Use producer-captured (0, 1) when resolved method parameters are null."""
    from polisyos.ir.analytics.hte import HTETargetRelationV1
    from polisyos.scientist.compute.hte_outcome_bridge import (
        _target_relation,
        _validate_writer_capture,
    )

    _data, _method, request, context, _params, writer_capture, anchor = _fixture()
    assert context.input_capture.resolved_params["control_value"] is None
    assert context.input_capture.resolved_params["treated_value"] is None
    assert writer_capture.control_value == request.control_value == 0.0
    assert writer_capture.treated_value == request.treated_value == 1.0
    assert writer_capture.contrast_status == "declared"
    _validate_writer_capture(
        SimpleNamespace(capture=writer_capture),
        context,
        anchor,
    )

    relation = _target_relation(
        context.input_capture,
        request_context=request,
        validated_writer_capture=writer_capture,
        computed_guarantee="backend_conditional_interval",
        profile_status="qualified",
        interval_alpha=0.05,
        ir_model=HTETargetRelationV1,
    )
    assert relation.contrast_status == "recomputed"
    assert relation.alpha_status == "recomputed"
    assert relation.scope_disposition == "requested_claim_not_satisfied"
    assert relation.guarantee_disposition == "satisfied"
    assert relation.overall_disposition == "requested_claim_not_satisfied"
    assert relation.estimand_status == "not_established"


def test_prepare_refusal_without_writer_capture_does_not_infer_contrast() -> None:
    """A declared request alone cannot become a computed producer relation."""
    from polisyos.ir.analytics.hte import HTETargetRelationV1
    from polisyos.scientist.compute.hte_outcome_bridge import (
        _target_relation,
        _validate_writer_capture,
    )

    _data, method, request, context, _params, _writer_capture, anchor = _fixture()
    prepare_refusal = SimpleNamespace(
        capture=None,
        kind="refusal",
        refusal_stage="prepare",
        method_fqn=method.owned_hte_method_fqn,
        method_abi=method.owned_hte_method_abi,
        method_profile_id=method.owned_hte_profile_id,
    )
    _validate_writer_capture(prepare_refusal, context, anchor)
    relation = _target_relation(
        context.input_capture,
        request_context=request,
        validated_writer_capture=None,
        computed_guarantee=None,
        profile_status="not_established",
        interval_alpha=None,
        refusal=True,
        ir_model=HTETargetRelationV1,
    )
    assert relation.contrast_status == "not_established"
    assert relation.overall_disposition == "not_established"


def test_writer_capture_context_and_explicit_parameter_conflicts_refuse() -> None:
    """Keep writer-to-owner and method-parameter mismatch fences intact."""
    from polisyos.foundry.methods.catalog.causal.hte_v2 import (
        CausalForestEstimatorV2,
        build_owned_hte_input_capture,
    )
    from polisyos.scientist.compute.hte_outcome_bridge import _validate_writer_capture

    data, method, request, context, params, writer_capture, anchor = _fixture()
    wrong_writer_capture = writer_capture.model_copy(
        update={"control_value": 1.0, "treated_value": 0.0}
    )
    with pytest.raises(ValueError, match="hte_bridge_writer_capture_owner_mismatch"):
        _validate_writer_capture(
            SimpleNamespace(capture=wrong_writer_capture),
            context,
            anchor,
        )

    contradictory_params = {**params, "control_value": 1.0, "treated_value": 0.0}
    with pytest.raises(ValidationError, match="owned_attempt_input_resolved_contrast_mismatch"):
        build_owned_hte_input_capture(
            data,
            source_data_ref=context.input_capture.source_data_ref.model_dump(mode="python"),
            method_class=CausalForestEstimatorV2,
            method_abi_digest=method.signature.abi_digest(),
            resolved_params=contradictory_params,
            seed=7,
            request_context=request,
        )
