"""Bound the native HTE result identity before persistence."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from polisyos.foundry.methods.catalog.causal.hte_v2 import (
    HTEWriterReadyIntervalV1,
    HTEWriterReadyPointV1,
    HTEWriterReadyV1,
    _NativeInferenceCaptureV1,
    _sha256,
)
from polisyos.ir.analytics.hte import _native_inference_profile_v1
from polisyos.scientist.compute.hte_outcome_bridge import _validate_native_writer_identity

_NATIVE_PROFILES = [
    (
        "causal.hte.causal_forest@2.0.0",
        "2.0.0",
        "econml.causal_forest_dml.native_mean@2.0",
    ),
    (
        "causal.hte.forest_dr@2.0.0",
        "2.0.0",
        "econml.forest_dr.native_mean@2.0",
    ),
]


def _native_capture(
    method_fqn: str,
    method_abi: str,
    method_profile_id: str,
    digest: str,
) -> _NativeInferenceCaptureV1:
    """Create one complete, validated capture using the producer schema."""
    profile = _native_inference_profile_v1(method_fqn, method_abi, method_profile_id)
    stderr_values = (0.1,)
    return _NativeInferenceCaptureV1.model_validate(
        {
            "inference_profile_id": "econml_native_mean_over_selected_x@1.0",
            "method_fqn": method_fqn,
            "method_abi": method_abi,
            "method_abi_digest": digest,
            "method_profile_id": method_profile_id,
            "estimator_class": profile.estimator_class,
            "inference_class": profile.inference_class,
            "econml_version": profile.econml_version,
            "econml_source_profile_sha256": profile.econml_source_profile_sha256,
            "ate_inference_method": profile.ate_inference_method,
            "conf_int_mean_method": profile.conf_int_mean_method,
            "native_result_class": profile.native_result_class,
            "inference_route": profile.inference_route,
            "resolved_params_sha256": "c" * 64,
            "source_data_sha256": "d" * 64,
            "input_profile_id": "all_source_rows_in_input_order@1.0",
            "selected_input_sha256": "e" * 64,
            "selected_rows_sha256": "f" * 64,
            "selected_x_sha256": "1" * 64,
            "selected_row_order_sha256": "2" * 64,
            "fit_rows_sha256": "3" * 64,
            "eval_rows_sha256": "4" * 64,
            "fit_eval_relation": "same_selected_rows",
            "sample_ids_status": "not_established",
            "sample_ids_sha256": None,
            "n_selected_rows": 1,
            "resolved_params": {},
            "seed": 7,
            "estimator_params_sha256": "5" * 64,
            "estimator_params": {},
            "nuisance_model_classes": (),
            "alpha": 0.05,
            "confidence_level": 0.95,
            "native_point": 0.5,
            "native_lower_bound": 0.25,
            "native_upper_bound": 0.75,
            "native_mean_pred": 0.5,
            "native_mean_pred_stderr": 0.1,
            "native_stderr_mean": None,
            "standard_error_source": "mean_pred_stderr",
            "standard_error_value": 0.1,
            "native_pred_stderr_values": stderr_values,
            "native_pred_sha256": "6" * 64,
            "native_pred_stderr_sha256": _sha256(list(stderr_values)),
            "conditional_assumptions": ("conditional_on_selected_rows",),
        },
        strict=True,
    )


def _writer(disposition: str, native: _NativeInferenceCaptureV1) -> HTEWriterReadyV1:
    """Place a validated native capture in either supported writer-ready path."""
    if disposition == "interval":
        return HTEWriterReadyIntervalV1.model_construct(native_capture=native)
    return HTEWriterReadyPointV1.model_construct(native_diagnostic=native)


@pytest.mark.parametrize(("method_fqn", "method_abi", "profile_id"), _NATIVE_PROFILES)
@pytest.mark.parametrize("disposition", ["interval", "rejected_point"])
def test_native_capture_must_match_full_owner_identity_before_persistence(
    method_fqn: str,
    method_abi: str,
    profile_id: str,
    disposition: str,
) -> None:
    """Both native outcomes and both profiles bind the nested digest as identity."""
    owner_digest = "a" * 64
    valid_capture = _native_capture(method_fqn, method_abi, profile_id, owner_digest)
    valid_writer = _writer(disposition, valid_capture)

    _validate_native_writer_identity(
        valid_writer,
        method_fqn=method_fqn,
        method_abi=method_abi,
        method_abi_digest=owner_digest,
        method_profile_id=profile_id,
    )

    different_valid_digest = "b" * 64
    mismatched_payload = valid_capture.model_dump(mode="python")
    mismatched_payload["method_abi_digest"] = different_valid_digest
    mismatched_capture = _NativeInferenceCaptureV1.model_validate(
        mismatched_payload,
        strict=True,
    )
    mismatched_writer = _writer(disposition, mismatched_capture)
    with pytest.raises(ValueError, match="hte_bridge_native_method_identity_mismatch"):
        _validate_native_writer_identity(
            mismatched_writer,
            method_fqn=method_fqn,
            method_abi=method_abi,
            method_abi_digest=owner_digest,
            method_profile_id=profile_id,
        )


def test_native_capture_contract_rejects_malformed_abi_digest() -> None:
    """The producer schema keeps malformed digest rejection distinct from mismatch."""
    payload = _native_capture(
        "causal.hte.causal_forest@2.0.0",
        "2.0.0",
        "econml.causal_forest_dml.native_mean@2.0",
        "a" * 64,
    ).model_dump(mode="python")
    payload["method_abi_digest"] = "not-a-sha256"
    with pytest.raises(ValidationError) as exc_info:
        _NativeInferenceCaptureV1.model_validate(payload, strict=True)

    assert any(error["loc"] == ("method_abi_digest",) for error in exc_info.value.errors())


def test_point_only_writer_without_native_inference_skips_identity_gate() -> None:
    """Native inference absence leaves the existing point-only path available."""
    writer = HTEWriterReadyPointV1.model_construct(native_diagnostic=None)

    _validate_native_writer_identity(
        writer,
        method_fqn="causal.hte.double_ml@2.0.0",
        method_abi="2.0.0",
        method_abi_digest="a" * 64,
        method_profile_id="econml.dml.point_only@2.0",
    )
