from __future__ import annotations

import json

import pytest

from tests._helpers.hds_quality import (
    HDS_XFAIL_REASON,
    complete_job_payload,
    complete_quality_evidence,
    runtime_cas_refs,
)
from tools.ops_runners.runtime.canary_evidence import assemble_canary_evidence

HDS_RED_XFAIL = pytest.mark.xfail(strict=True, reason=HDS_XFAIL_REASON)


def _scorecard(output_dir) -> dict[str, object]:
    return json.loads(
        (output_dir / "quality_evidence" / "quality_scorecard.json").read_text(
            encoding="utf-8"
        )
    )


@HDS_RED_XFAIL
def test_canary_bundle_generated_quality_evidence_paths_cannot_mint_runtime_refs(
    tmp_path,
) -> None:
    runtime_refs = runtime_cas_refs()
    output = assemble_canary_evidence(
        output_root=tmp_path,
        canary_kind="production",
        command_metadata={"argv": ["policyos-canary", "--real"]},
        request_payload={"request": "Evaluate Ukraine MSME support."},
        job_payload=complete_job_payload(runtime_refs=runtime_refs),
        provider_preflight={"status": "passed"},
        quality_evidence=complete_quality_evidence(),
    )

    scorecard = _scorecard(output)

    assert scorecard["quality_status"] == "fail"
    assert {
        failure["code"]
        for failure in scorecard["blocking_quality_failures"]
        if isinstance(failure, dict)
    } >= {"bundle_generated_runtime_ref_not_authority"}
    assert scorecard["evidence_refs"]["production_data_quality_report_ref"] == (
        runtime_refs["production_data_quality_report_ref"]
    )


@HDS_RED_XFAIL
def test_quality_status_pass_in_input_progress_bundle_or_dashboard_is_projection_only(
    tmp_path,
) -> None:
    spoofed_refs = runtime_cas_refs()
    output = assemble_canary_evidence(
        output_root=tmp_path,
        canary_kind="production",
        command_metadata={"argv": ["policyos-canary", "--real"]},
        request_payload={
            "request": "Evaluate Ukraine MSME support.",
            "quality_status": "pass",
            "params": {
                "quality_status": "pass",
                "runtime_quality_refs": spoofed_refs,
            },
        },
        job_payload=complete_job_payload(
            runtime_refs={},
            details={
                "quality_status": "pass",
                "quality_scorecard": {"quality_status": "pass"},
            },
        ),
        provider_preflight={"status": "passed"},
        quality_evidence=complete_quality_evidence(),
        dashboard_evidence={
            "quality_status": "pass",
            "approval_state": "approval_ready",
            "projection": "runtime-dashboard",
        },
    )

    scorecard = _scorecard(output)
    bundle = json.loads((output / "bundle.json").read_text(encoding="utf-8"))

    assert bundle["quality_status"] == "fail"
    assert scorecard["quality_status"] == "fail"
    assert {
        failure["code"]
        for failure in scorecard["blocking_quality_failures"]
        if isinstance(failure, dict)
    } >= {"projection_quality_status_not_authority"}


@HDS_RED_XFAIL
def test_silent_fallback_requires_degradation_ledger_before_canary_closeout(tmp_path) -> None:
    output = assemble_canary_evidence(
        output_root=tmp_path,
        canary_kind="production",
        command_metadata={"argv": ["policyos-canary", "--real"]},
        request_payload={"request": "Evaluate Ukraine MSME support."},
        job_payload=complete_job_payload(
            details={
                "fallback_used": True,
                "fallback_reason": "llm_gateway_timeout",
                "effective_mode": "production",
                "degradation_ledger_ref": None,
            }
        ),
        provider_preflight={"status": "passed"},
        quality_evidence=complete_quality_evidence(),
    )

    scorecard = _scorecard(output)

    assert scorecard["quality_status"] == "fail"
    assert {
        failure["code"]
        for failure in scorecard["blocking_quality_failures"]
        if isinstance(failure, dict)
    } >= {"silent_fallback_degradation_ledger_missing"}
