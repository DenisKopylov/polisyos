from __future__ import annotations

import pytest

from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.quality.evidence_spine_handoff import (
    EVIDENCE_SPINE_HANDOFF_LEDGER_SCHEMA_VERSION,
    EvidenceSpineHandoff,
    EvidenceSpineHandoffSafetyError,
    assert_carrier_payload_safe,
    build_evidence_spine_handoff_ledger,
    build_runtime_async_handoff_ledger,
)


def test_carrier_rejects_secret_like_and_raw_text_values() -> None:
    unsafe_values = [
        {"carrier_ref": "postgresql://policyos:secret@localhost:5432/policyos"},
        {"carrier_ref": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ"},
        {"carrier_ref": "sk-live-provider-secret-abcdef1234567890"},
        {"raw_prompt": "Draft a policy recommendation from the private operator prompt."},
        {
            "raw_legal_corpus_excerpt": (
                "Article 4. The ministry shall administer credit eligibility rules "
                "for every applicant in the protected corpus excerpt."
            )
        },
        {
            "raw_recommendation_body": (
                "Launch a fiscal credit program with uncapped subsidy terms and "
                "publish the operator-only draft recommendation body."
            )
        },
    ]

    for payload in unsafe_values:
        with pytest.raises(EvidenceSpineHandoffSafetyError):
            assert_carrier_payload_safe(payload)

    assert_carrier_payload_safe(
        {
            "carrier_ref": "evidence-spine:abc123",
            "input_refs": ["quality_evidence/fabric_retrieval_trace.json"],
            "output_refs": ["quality_evidence/scenario_contract_propagation_graph.json"],
        }
    )


def test_async_handoff_links_job_progress_to_cas_bundle_and_readiness(tmp_path) -> None:
    store = ControlPlaneStore(
        backend="sqlite",
        sqlite_path=tmp_path / "control.sqlite3",
    )
    store.create_job(
        job_id="job-handoff",
        kind="natural_language_run",
        run_id="R_handoff",
        pipeline_id=None,
        requested_execution_profile="research",
        effective_execution_profile="research",
        policy_flags={},
        capability_manifest_ref="sha256:" + "1" * 64,
        payload_ref="sha256:" + "2" * 64,
        submitted_by="operator",
    )
    leased = store.lease_next_job(worker_id="worker-handoff", lease_seconds=30)
    assert leased is not None
    store.update_progress_state(
        job_id="job-handoff",
        state="running",
        progress={
            **leased.progress,
            "quality_evidence_bundle_path": "bundle://cloud-wave11",
            "evidence_refs": {
                "quality_scorecard": "quality_evidence/quality_scorecard.json",
                "readiness": "_build/.tmp/production-quality/final_readiness.json",
            },
            "artifacts": {
                "cas_ownership_manifest": (
                    "cas_manifests/quality_artifact_ownership.manifest.json"
                )
            },
        },
    )

    record = store.get_job("job-handoff")
    assert record is not None
    ledger = build_runtime_async_handoff_ledger(
        job_progress=record.progress,
        bundle_ref="bundle://cloud-wave11",
        carrier_ref="evidence-spine:carrier-job-handoff",
    )

    assert ledger["schema_version"] == EVIDENCE_SPINE_HANDOFF_LEDGER_SCHEMA_VERSION
    assert ledger["status"] == "pass"
    handoff_kinds = {handoff["handoff_kind"] for handoff in ledger["handoffs"]}
    assert {
        "nl_request_creation",
        "control_plane_job_lease",
        "workflow_state_persistence",
        "cas_artifact_write",
        "readiness_result",
    } <= handoff_kinds
    for handoff in ledger["handoffs"]:
        assert handoff["parent_spine_ref"]
        assert handoff["input_refs"]
        assert handoff["output_refs"]
        assert handoff["carrier_ref"] == "evidence-spine:carrier-job-handoff"
        assert handoff["integrity_status"] == "pass"


def test_handoff_ledger_fails_missing_refs_and_failed_redaction() -> None:
    ledger = build_evidence_spine_handoff_ledger(
        [
            {
                "handoff_id": "handoff-bad",
                "handoff_kind": "workflow_state_persistence",
                "producer_ref": "runtime.nl_pipeline",
                "consumer_ref": "runtime.nl_pipeline",
                "parent_spine_ref": None,
                "input_refs": [],
                "output_refs": [],
                "carrier_ref": None,
                "carrier_redaction_status": "fail",
                "integrity_status": "pass",
            }
        ],
        required_handoff_kinds=("workflow_state_persistence",),
    )

    codes = {finding["code"] for finding in ledger["findings"]}
    assert ledger["status"] == "fail"
    assert {
        "evidence_spine_handoff_parent_ref_missing",
        "evidence_spine_handoff_input_refs_missing",
        "evidence_spine_handoff_output_refs_missing",
        "evidence_spine_handoff_carrier_ref_missing",
        "evidence_spine_handoff_redaction_failed",
        "evidence_spine_handoff_producer_consumer_mismatch",
    } <= codes


def test_handoff_dataclass_rejects_secret_like_refs() -> None:
    with pytest.raises(EvidenceSpineHandoffSafetyError):
        EvidenceSpineHandoff(
            handoff_kind="canary_bundle_assembly",
            producer_ref="tools.ops_runners.runtime.canary_evidence",
            consumer_ref="quality.validation.inspect_evidence_bundles",
            parent_spine_ref="evidence-spine:parent",
            input_refs=("request.sanitized.json",),
            output_refs=("bundle.json",),
            carrier_ref="Bearer should-never-travel-in-handoff-ledgers",
        )
