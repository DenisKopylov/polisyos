from __future__ import annotations

import json
from pathlib import Path

from polisyos.runtime.quality.semantic_binding import deserialize_semantic_binding_ledger
from tests._helpers.hds_quality import (
    bundle_local_runtime_refs,
    complete_job_payload,
    complete_quality_evidence,
    runtime_cas_refs,
)
from tools.ops_runners.runtime import canary_evidence
from tools.ops_runners.runtime.canary_evidence import assemble_canary_evidence


def _scorecard(output_dir: Path) -> dict[str, object]:
    return json.loads(
        (output_dir / "quality_evidence" / "quality_scorecard.json").read_text(
            encoding="utf-8"
        )
    )

def test_canary_bundle_generated_quality_evidence_paths_cannot_mint_runtime_refs(
    tmp_path: Path,
) -> None:
    runtime_refs = bundle_local_runtime_refs()
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
    } >= {"hds_bundle_ref_used_as_runtime_ref"}
    production_ref = scorecard["evidence_refs"]["production_data_quality_report_ref"]
    assert production_ref != runtime_refs["production_data_quality_report_ref"]
    assert production_ref.startswith("sha256:")

def test_quality_status_pass_in_input_progress_bundle_or_dashboard_is_projection_only(
    tmp_path: Path,
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


def test_serious_canary_evidence_dual_writes_legacy_migration_sandbox(
    tmp_path: Path,
) -> None:
    output = assemble_canary_evidence(
        output_root=tmp_path,
        output_dir=tmp_path / "bundle",
        canary_kind="production",
        command_metadata={"argv": ["policyos-canary", "--real"]},
        request_payload={"request": "Evaluate Ukraine MSME support."},
        job_payload=complete_job_payload(),
        provider_preflight={"status": "passed"},
        quality_evidence=complete_quality_evidence(),
    )

    legacy_path = output / "legacy_compat" / "quality_evidence" / "policy_grounding_matrix.json"
    authority_path = output / "authority" / "quality_evidence" / "policy_grounding_matrix.json"
    sandbox_path = output / "migration_sandbox" / "legacy_migration_sandbox.json"

    assert legacy_path.is_file()
    assert authority_path.is_file()
    assert sandbox_path.is_file()

    legacy_payload = json.loads(legacy_path.read_text(encoding="utf-8"))
    authority_payload = json.loads(authority_path.read_text(encoding="utf-8"))
    sandbox = json.loads(sandbox_path.read_text(encoding="utf-8"))

    assert "authority_envelope" not in legacy_payload
    assert legacy_payload["evidence_class"] == "legacy_quarantined"
    assert authority_payload["authority_envelope"]["evidence_class"] == "authority_bearing"
    assert sandbox["status"] == "pass"
    assert sandbox["closeout_policy"]["legacy_satisfies_serious_gates"] is False
    assert (
        sandbox["dual_write_policy"]["required_consecutive_weekly_closeout_baselines"]
        == 2
    )


def test_silent_fallback_requires_degradation_ledger_before_canary_closeout(
    tmp_path: Path,
) -> None:
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
    } >= {"hds_unallowed_fallback"}


def test_minimum_closeout_authority_events_name_runtime_ref_key(tmp_path: Path) -> None:
    output = assemble_canary_evidence(
        output_root=tmp_path,
        canary_kind="production",
        command_metadata={"argv": ["policyos-canary", "--real"]},
        request_payload={"request": "Evaluate Ukraine MSME support."},
        job_payload=complete_job_payload(),
        provider_preflight={"status": "passed"},
        quality_evidence=complete_quality_evidence(),
    )

    index = json.loads(
        (output / "quality_evidence" / "minimum_closeout_authority_index.json").read_text(
            encoding="utf-8"
        )
    )

    for event in index["diagnostic_events"]:
        ref_key = event["ref_key"]
        assert ref_key in event["event_name"]


def test_serious_canary_job_events_cover_aggregate_closeout_refs(tmp_path: Path) -> None:
    output = assemble_canary_evidence(
        output_root=tmp_path,
        canary_kind="production",
        command_metadata={"argv": ["policyos-canary", "--real"]},
        request_payload={"request": "Evaluate Ukraine MSME support."},
        job_payload=complete_job_payload(),
        provider_preflight={"status": "passed"},
        quality_evidence=complete_quality_evidence(),
    )

    job = json.loads((output / "job.json").read_text(encoding="utf-8"))
    index = json.loads(
        (output / "quality_evidence" / "minimum_closeout_authority_index.json").read_text(
            encoding="utf-8"
        )
    )
    approval_ref = index["records"]["approval_packet_ref"]["approval_packet_ref"]
    diagnostic_events = job["progress"]["details"]["diagnostic_events"]

    assert any(
        event.get("ref_key") == "approval_packet_ref"
        and event.get("artifact_ref") == approval_ref
        for event in diagnostic_events
    )


def test_serious_canary_semantic_binding_ledger_is_reader_valid(tmp_path: Path) -> None:
    output = assemble_canary_evidence(
        output_root=tmp_path,
        canary_kind="production",
        command_metadata={"argv": ["policyos-canary", "--real"]},
        request_payload={"request": "Evaluate Ukraine MSME support."},
        job_payload=complete_job_payload(),
        provider_preflight={"status": "passed"},
        quality_evidence=complete_quality_evidence(),
    )

    ledger = json.loads(
        (output / "quality_evidence" / "semantic_binding_ledger.json").read_text(
            encoding="utf-8"
        )
    )

    assert deserialize_semantic_binding_ledger(ledger).semantic_binding_ref


def test_closeout_authority_sync_updates_policy_design_case_pass1b_approval_ref() -> None:
    payload = {
        "policy_design_case": {
            "pass1b_tenant_cas_approval_governance": {
                "case_bindings": {
                    "approval_authority": {
                        "approval_packet_ref": "sha256:old",
                        "runtime_event_ref": "event://old",
                    }
                }
            }
        }
    }
    closeout_index = {
        "records": {
            "approval_packet_ref": {
                "approval_packet_ref": "sha256:new",
                "runtime_event_ref": "sha256:event",
            }
        }
    }

    synced = canary_evidence._quality_evidence_with_closeout_authority_refs(
        payload,
        closeout_index,
    )

    approval = synced["policy_design_case"]["pass1b_tenant_cas_approval_governance"][
        "case_bindings"
    ]["approval_authority"]
    assert approval["approval_packet_ref"] == "sha256:new"
    assert approval["runtime_event_ref"] == "sha256:event"


def test_semantic_binding_closeout_sanitizer_removes_reader_forbidden_ref() -> None:
    payload = {
        "semantic_binding_ledger": {
            "schema_version": "policyos.runtime.semantic_binding_ledger.v1",
            "semantic_binding_ref": "sha256:reader-valid",
            "semantic_binding_ledger_ref": "sha256:closeout-only",
        }
    }

    sanitized = canary_evidence._quality_evidence_with_reader_valid_semantic_binding(
        payload
    )

    assert "semantic_binding_ledger_ref" not in sanitized["semantic_binding_ledger"]
