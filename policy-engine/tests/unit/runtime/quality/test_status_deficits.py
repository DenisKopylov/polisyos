from __future__ import annotations

from datetime import UTC, datetime

from polisyos.runtime.quality.approval import build_production_approval_packet
from polisyos.runtime.quality.scorecard import build_quality_scorecard
from polisyos.runtime.quality.status_deficits import (
    build_status_envelope,
    status_envelope_scorecard_gates,
)


def _sha(char: str) -> str:
    return "sha256:" + char * 64


def _status_record(
    *,
    family: str,
    status: str,
    owner: str = "team-runtime-quality",
    ttl: str = "2099-01-01T00:00:00+00:00",
) -> dict[str, object]:
    return {
        "producer": f"producer.{family}",
        "status_family": family,
        "local_status": status,
        "owner": owner,
        "ttl_expires_at": ttl,
        "evidence_ref": _sha("a"),
    }


def _deficit(
    *,
    deficit_id: str,
    disposition: str,
    family: str = "missing_evidence",
    code: str | None = None,
) -> dict[str, object]:
    return {
        "deficit_id": deficit_id,
        "deficit_family": family,
        "deficit_code": code or f"{family}_{disposition}",
        "claim_ids": ["claim-1"],
        "authority_level": "governed",
        "audience_scope": "public",
        "disposition": disposition,
        "support_cap": "weak",
        "readiness_cap": "external_briefing",
        "max_audience": "public_with_limitation",
        "owner": "team-policy-semantics",
        "expires_at": "2099-01-01T00:00:00+00:00",
        "runtime_event_ref": "event://status-deficit/1",
        "evidence_ref": _sha("b"),
        "public_limitation_note": "Published result must disclose this limitation.",
        "review_refs": ["review://status-deficit/1"],
    }


def test_status_envelope_preserves_local_statuses_while_composing_shared_effects() -> None:
    envelope = build_status_envelope(
        local_statuses=[
            _status_record(family="claim_support", status="supported"),
            _status_record(family="citation_faithfulness", status="partially_supports"),
            _status_record(family="semantic_binding", status="pass"),
            _status_record(family="transportability", status="partially_identified"),
            _status_record(family="proof_composability", status="revalidate"),
            _status_record(family="decision_validity", status="warning"),
        ],
        deficits=[],
        now=datetime(2026, 5, 22, tzinfo=UTC),
    )

    local_pairs = {(entry.status_family, entry.local_status) for entry in envelope.entries}
    assert ("claim_support", "supported") in local_pairs
    assert ("citation_faithfulness", "partially_supports") in local_pairs
    assert ("transportability", "partially_identified") in local_pairs
    assert envelope.summary.publication_effect == "review_before_publication"
    assert envelope.summary.review_action == "human_review"
    assert envelope.summary.closeout_effect == "review_required"
    assert envelope.lifecycle_issues == ()


def test_deficit_crosswalk_keeps_accepted_limitation_review_reissue_and_block_distinct() -> None:
    envelope = build_status_envelope(
        local_statuses=[],
        deficits=[
            _deficit(deficit_id="deficit-accepted", disposition="accepted_deficit"),
            _deficit(deficit_id="deficit-limited", disposition="publish_with_limitation"),
            _deficit(deficit_id="deficit-review", disposition="human_review_required"),
            _deficit(deficit_id="deficit-reissue", disposition="reissue_required"),
            _deficit(deficit_id="deficit-block", disposition="hard_block"),
        ],
        now=datetime(2026, 5, 22, tzinfo=UTC),
    )

    effects = {row.deficit_id: row.closeout_effect for row in envelope.deficit_crosswalk}
    assert effects == {
        "deficit-accepted": "accepted_deficit",
        "deficit-limited": "limited_closeout",
        "deficit-review": "review_required",
        "deficit-reissue": "reissue_required",
        "deficit-block": "closeout_blocked",
    }
    publication_effects = {
        row.deficit_id: row.publication_effect for row in envelope.deficit_crosswalk
    }
    assert publication_effects["deficit-accepted"] == "internal_only"
    assert publication_effects["deficit-limited"] == "publish_with_limitation"
    assert publication_effects["deficit-review"] == "review_before_publication"
    assert publication_effects["deficit-reissue"] == "reissue_required"
    assert publication_effects["deficit-block"] == "publication_blocked"

    gates = status_envelope_scorecard_gates(envelope)
    gates_by_code = {gate["code"]: gate for gate in gates}
    assert gates_by_code["status_deficit_accepted"]["status"] == "pass"
    assert gates_by_code["status_deficit_publish_with_limitation"]["status"] == "pass"
    assert gates_by_code["status_deficit_review_required"]["closeout_effect"] == (
        "review_required"
    )
    assert gates_by_code["status_deficit_reissue_required"]["closeout_effect"] == (
        "reissue_required"
    )
    assert gates_by_code["status_deficit_hard_block"]["closeout_effect"] == (
        "closeout_blocked"
    )


def test_warning_like_status_without_owner_or_ttl_becomes_lifecycle_blocker() -> None:
    envelope = build_status_envelope(
        local_statuses=[
            {
                "producer": "producer.decision_validity",
                "status_family": "decision_validity",
                "local_status": "warning",
                "evidence_ref": _sha("a"),
            }
        ],
        deficits=[],
        now=datetime(2026, 5, 22, tzinfo=UTC),
    )

    assert [issue.code for issue in envelope.lifecycle_issues] == [
        "status_lifecycle_owner_missing",
        "status_lifecycle_ttl_missing",
    ]
    assert envelope.summary.closeout_effect == "closeout_blocked"
    gates = status_envelope_scorecard_gates(envelope)
    assert {gate["code"] for gate in gates} == {
        "status_lifecycle_owner_missing",
        "status_lifecycle_ttl_missing",
        "status_crosswalk_lifecycle_blocker",
    }


def test_scorecard_surfaces_nonblocking_deficits_without_turning_them_into_review() -> None:
    scorecard = build_quality_scorecard(
        canary_kind="production",
        job_id="job-status",
        run_id="run-status",
        execution_status="completed",
        job_payload={
            "progress": {
                "details": {
                    "data_snapshot_ref": _sha("1"),
                    "input_bindings_ref": _sha("2"),
                    "registry_bundle_ref": _sha("3"),
                    "quality_report_ref": _sha("4"),
                    "run_performance_summary": {"status": "pass"},
                }
            }
        },
        run_payload=None,
        provider_preflight={"status": "passed"},
        quality_evidence={
            "runtime_status_records": [
                _status_record(family="claim_support", status="supported"),
            ],
            "deficit_records": [
                _deficit(deficit_id="deficit-accepted", disposition="accepted_deficit"),
                _deficit(
                    deficit_id="deficit-limited",
                    disposition="publish_with_limitation",
                    code="proxy_evidence_public_limitation",
                ),
            ],
        },
    )

    assert scorecard["status_envelope"]["summary"]["closeout_effect"] == (
        "limited_closeout"
    )
    assert [row["disposition"] for row in scorecard["deficit_crosswalk"]] == [
        "accepted_deficit",
        "publish_with_limitation",
    ]
    status_codes = {gate["code"] for gate in scorecard["quality_gates"]}
    assert "status_deficit_accepted" in status_codes
    assert "status_deficit_publish_with_limitation" in status_codes
    assert "status_deficit_review_required" not in status_codes


def test_approval_blocks_review_reissue_and_hard_block_deficits_with_distinct_reasons() -> None:
    scorecard = {
        "schema_version": "policyos.quality_scorecard.v1",
        "generated_at": "2026-05-22T09:00:00+00:00",
        "canary_kind": "production",
        "job_id": "job-status",
        "run_id": "run-status",
        "execution_status": "completed",
        "quality_status": "pass",
        "performance_status": "pass",
        "conflict_status": "pass",
        "approval_state": "approval_ready",
        "quality_gates": [],
        "blocking_quality_failures": [],
        "warnings": [],
        "deficit_crosswalk": [
            row.model_dump(mode="json")
            for row in build_status_envelope(
                local_statuses=[],
                deficits=[
                    _deficit(
                        deficit_id="deficit-review",
                        disposition="expert_review_required",
                    ),
                    _deficit(deficit_id="deficit-reissue", disposition="reissue_required"),
                    _deficit(deficit_id="deficit-block", disposition="hard_block"),
                ],
                now=datetime(2026, 5, 22, tzinfo=UTC),
            ).deficit_crosswalk
        ],
        "evidence_refs": {"quality_scorecard": _sha("c")},
        "quality_scorecard_ref": _sha("c"),
        "scorecard_identity_ref": _sha("c"),
        "scorecard_identity_verified": True,
    }

    packet = build_production_approval_packet(
        scorecard=scorecard,
        now=datetime(2026, 5, 22, 10, 0, tzinfo=UTC),
    )

    assert packet.decision == "blocked"
    assert packet.eligibility.eligible is False
    assert packet.eligibility.reasons == [
        "non_overridable_blocker",
        "status_deficit_hard_block",
        "status_deficit_reissue_required",
        "status_deficit_review_required",
    ]
