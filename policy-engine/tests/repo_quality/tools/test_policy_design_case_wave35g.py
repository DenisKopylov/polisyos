from __future__ import annotations

# ruff: noqa: S101
import json
from pathlib import Path

from tools.quality.validation import (
    build_policy_design_case_wave35e as wave35e,
)
from tools.quality.validation import (
    build_policy_design_case_wave35f_integrity as wave35f,
)
from tools.quality.validation import (
    build_policy_design_case_wave35g_backfill as backfill,
)
from tools.quality.validation import (
    build_policy_design_case_wave35g_institutional_provenance as institutional,
)
from tools.quality.validation import (
    check_policy_design_case_wave35g_backfill as check_backfill,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
ARTIFACT_PATH = (
    REPO_ROOT / "_build/policy-design-case/rebaseline/wave-35G/"
    "projection_fail_closed_runtime_backfill.json"
)
MEMORY_ARTIFACT_PATH = (
    REPO_ROOT / "_build/policy-design-case/rebaseline/wave-35G/"
    "memory_authority_runtime_abstention_trace.json"
)
TRUST_ARTIFACT_PATH = (
    REPO_ROOT / "_build/policy-design-case/rebaseline/wave-35G/"
    "trust_framing_ui_negative_trace_bundle.json"
)
MASKING_CASES = {
    "missing",
    "stale",
    "conflicting",
    "reissued",
    "withdrawn",
    "non_authoritative",
    "projection_only",
}
INSTITUTIONAL_BLOCKERS = {
    "PDD-097-F001",
    "PDD-097-F002",
    "PDD-097-F003",
    "PDD-099-F001",
    "PDD-099-F002",
    "PDD-099-F003",
}
TRUST_FRAMING_SCENARIOS = {
    "low_confidence",
    "disputed",
    "untraced",
    "simulated",
    "stale",
    "draft",
    "override_approved",
    "frontend_signed",
}
TRUST_TRACE_ROOT = "_build/policy-design-case/rebaseline/wave-35G/trust-framing-ui-negative-traces"
TRUST_TRACE_SUFFIXES = {".png", ".zip", ".webm"}
WAVE35G_RELEASE_BLOCKERS = {
    "PDD-034-F001",
    "PDD-034-F002",
    "PDD-034-F003",
    "PDD-069-F001",
    "PDD-069-F002",
    "PDD-069-F003",
    "PDD-083-F001",
    "PDD-083-F002",
    "PDD-083-F003",
    "PDD-097-F001",
    "PDD-097-F002",
    "PDD-097-F003",
    "PDD-099-F001",
    "PDD-099-F002",
    "PDD-099-F003",
    "PDD-103-F001",
    "PDD-103-F002",
    "PDD-103-F003",
    "PDD-103-F004",
}


def _generated_trust_media_refs(row: dict | object) -> list[str]:
    if not isinstance(row, dict):
        return []
    refs = row.get("trace_or_screenshot_refs")
    if not isinstance(refs, list):
        return []
    media_refs: list[str] = []
    for ref in refs:
        if not isinstance(ref, str):
            continue
        suffix = Path(ref.split("#", 1)[0]).suffix
        if ref.startswith(TRUST_TRACE_ROOT) and suffix in TRUST_TRACE_SUFFIXES:
            media_refs.append(ref)
    return media_refs


def test_wave35g_backfill_builder_closes_all_wave35f_release_blockers(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "wave-35G"

    outputs = backfill.build_wave35g_backfill_outputs(
        repo_root=REPO_ROOT,
        wave35g_dir=output_dir,
        diagnostics_root=tmp_path / "diagnostics",
        refresh_wave35f=False,
        update_wave35e=False,
    )

    report = outputs["integrity_report"]
    assert report["status"] == "pass"
    assert report["command"] == backfill.BACKFILL_CHECK_COMMAND
    assert report["exit_code"] == 0
    assert report["blocker_closure_counts"] == {
        "required_release_blocker_count": 19,
        "runtime_or_test_evidence_count": 19,
        "non_closeout_authority_boundary_count": 0,
        "closed_release_blocker_count": 19,
        "remaining_release_blocker_count": 0,
    }
    assert report["remaining_blocker_rows"] == []
    assert {row["finding_id"] for row in report["blocker_closure_rows"]} == (
        WAVE35G_RELEASE_BLOCKERS
    )

    exit_fence = outputs["exit_fence"]
    assert exit_fence["status"] == "pass"
    assert exit_fence["wave36_release_decision"] == "allowed"
    assert set(exit_fence["covered_release_blocker_ids"]) == WAVE35G_RELEASE_BLOCKERS

    assert (
        check_backfill.validate_wave35g_backfill(
            repo_root=REPO_ROOT,
            wave35g_dir=output_dir,
            require_wave35f_release_allowed=False,
        )
        == []
    )


def test_wave35g_backfill_validator_rejects_missing_runtime_or_boundary(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "wave-35G"
    backfill.build_wave35g_backfill_outputs(
        repo_root=REPO_ROOT,
        wave35g_dir=output_dir,
        diagnostics_root=tmp_path / "diagnostics",
        refresh_wave35f=False,
        update_wave35e=False,
    )
    memory_path = output_dir / "memory_authority_runtime_abstention_trace.json"
    memory = json.loads(memory_path.read_text(encoding="utf-8"))
    memory["evidence_rows"] = [
        row for row in memory["evidence_rows"] if row["finding_id"] != "PDD-083-F002"
    ]
    memory_path.write_text(json.dumps(memory, indent=2) + "\n", encoding="utf-8")

    errors = check_backfill.validate_wave35g_backfill(
        repo_root=REPO_ROOT,
        wave35g_dir=output_dir,
        require_wave35f_release_allowed=False,
    )

    assert any(
        "PDD-083-F002 lacks runtime/test evidence or non-closeout boundary" in error
        for error in errors
    )


def test_wave35f_integrity_allows_wave36_after_wave35g_backfill(
    tmp_path: Path,
) -> None:
    wave35g_dir = tmp_path / "wave-35G"
    wave35f_dir = tmp_path / "wave-35F"
    backfill.build_wave35g_backfill_outputs(
        repo_root=REPO_ROOT,
        wave35g_dir=wave35g_dir,
        diagnostics_root=tmp_path / "diagnostics",
        refresh_wave35f=False,
        update_wave35e=False,
    )

    outputs = wave35f.build_wave35f_integrity_outputs(
        repo_root=REPO_ROOT,
        wave35f_dir=wave35f_dir,
        wave35g_dir=wave35g_dir,
    )

    assert outputs["gap_ledger"]["summary"]["wave36_release_blocking_gap_count"] == 0
    assert outputs["exit_fence"]["status"] == "pass"
    assert outputs["exit_fence"]["wave36_release_decision"] == "allowed"


def test_wave35g_projection_fail_closed_backfill_records_runtime_test_evidence() -> None:
    payload = json.loads(ARTIFACT_PATH.read_text(encoding="utf-8"))

    assert payload["status"] == "complete"
    assert payload["phase"] == "35G.1"
    assert payload["required_output_artifact"] == str(ARTIFACT_PATH.relative_to(REPO_ROOT))
    assert (
        payload["wave35f_closeout_rule"][
            "projection_overlays_without_backfill_count_toward_deterministic_closeout"
        ]
        is False
    )
    assert payload["wave35f_closeout_rule"]["runtime_or_test_backfill_required"] is True

    rows = payload["evidence_rows"]
    assert {row["masking_case"] for row in rows} == MASKING_CASES
    assert all(row["evidence_authority"] in {"runtime_emitted", "test_observed"} for row in rows)
    assert all(row["command"]["exit_code"] == 0 for row in rows)
    assert all(row["source_refs"] for row in rows)
    assert all(row["trace_or_assertion_refs"] for row in rows)
    assert all(
        row["runtime_api_boundary"]["observed_result"] == "blocked_fail_closed" for row in rows
    )
    assert all(
        row["dashboard_public_boundary"]["observed_result"] == "blocked_fail_closed" for row in rows
    )
    assert all(row["counts_toward_deterministic_closeout"] is True for row in rows)


def test_wave35g_trust_framing_negative_bundle_records_ui_trace_backfill() -> None:
    payload = json.loads(TRUST_ARTIFACT_PATH.read_text(encoding="utf-8"))

    assert payload["status"] == "complete"
    assert payload["phase"] == "35G.3"
    assert payload["required_output_artifact"] == str(TRUST_ARTIFACT_PATH.relative_to(REPO_ROOT))
    assert set(payload["affected_findings"]) == {
        "PDD-103-F001",
        "PDD-103-F002",
        "PDD-103-F003",
        "PDD-103-F004",
    }
    assert (
        payload["wave36_gate"]["blocked_if_any_required_scenario_remains_synthetic_overlay"] is True
    )
    assert payload["wave36_gate"]["synthetic_overlay_remaining_scenarios"] == []
    assert payload["wave36_gate"]["wave36_release_decision"] == "allowed_for_35g3"

    rows = payload["scenario_rows"]
    assert {row["scenario"] for row in rows} == TRUST_FRAMING_SCENARIOS
    assert all(row["authority_classification"] == "test_observed" for row in rows)
    assert all(row["command"]["exit_code"] == 0 for row in rows)
    assert all(row["trace_or_screenshot_refs"] for row in rows)
    for row in rows:
        media_refs = _generated_trust_media_refs(row)
        assert media_refs, row["scenario"]
        for ref in media_refs:
            assert (REPO_ROOT / ref).exists(), ref
    assert all(row["source_refs"] for row in rows)
    assert all(row["ui_assertions"]["visible_authority_caveat"] is True for row in rows)
    assert all(
        row["ui_assertions"]["frontend_signature_promoted_to_closeout"] is False for row in rows
    )
    assert all(row["ui_assertions"]["badge_or_label_promoted_to_closeout"] is False for row in rows)
    assert all(row["ui_assertions"]["projection_promoted_to_closeout"] is False for row in rows)
    assert all(row["counts_toward_deterministic_closeout"] is True for row in rows)


def test_wave35g_validator_rejects_trust_source_anchors_without_generated_media(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "wave-35G"
    backfill.build_wave35g_backfill_outputs(
        repo_root=REPO_ROOT,
        wave35g_dir=output_dir,
        diagnostics_root=tmp_path / "diagnostics",
        refresh_wave35f=False,
        update_wave35e=False,
    )
    trust_path = output_dir / "trust_framing_ui_negative_trace_bundle.json"
    trust = json.loads(trust_path.read_text(encoding="utf-8"))
    for row in trust["scenario_rows"]:
        row["trace_or_screenshot_refs"] = [
            (
                "apps/runtime-dashboard/src/features/runs/components/"
                f"PublicationPacketPanel.test.tsx#trust-framing-{row['scenario']}"
            )
        ]
    trust_path.write_text(json.dumps(trust, indent=2) + "\n", encoding="utf-8")

    errors = check_backfill.validate_wave35g_backfill(
        repo_root=REPO_ROOT,
        wave35g_dir=output_dir,
        require_wave35f_release_allowed=False,
    )

    assert any("trust: missing generated UI trace or screenshot" in error for error in errors)


def test_wave35g_wave35e_trust_artifact_is_refreshed_with_observed_trace_backfill(
    tmp_path: Path,
) -> None:
    wave35e_dir = tmp_path / "wave-35E"
    backfill.build_wave35g_backfill_outputs(
        repo_root=REPO_ROOT,
        wave35e_dir=wave35e_dir,
        wave35g_dir=tmp_path / "wave-35G",
        diagnostics_root=tmp_path / "diagnostics",
        refresh_wave35f=False,
        update_wave35e=True,
    )

    payload = json.loads(
        (wave35e_dir / "trust_framing_ui_negative_tests.json").read_text(encoding="utf-8")
    )
    runtime_evidence = payload["runtime_enforcement_evidence"]

    assert runtime_evidence["evidence_authority_class"] == "test_observed"
    assert runtime_evidence["scenario_specific_screenshot_coverage"] is True
    assert runtime_evidence["synthetic_overlay_rows"] == []
    assert runtime_evidence["wave35f_followup_required"] is False
    assert set(runtime_evidence["covered_scenarios"]) == TRUST_FRAMING_SCENARIOS
    assert all(
        ref.startswith(TRUST_TRACE_ROOT)
        for ref in runtime_evidence["scenario_specific_screenshot_refs"]
    )


def test_wave35g_institutional_boundary_records_manual_ledgers_as_not_closeout_authority(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "wave-35G"
    wave35e_dir = tmp_path / "wave-35E"
    wave35e.build_wave35e_outputs(
        repo_root=REPO_ROOT,
        wave35e_dir=wave35e_dir,
        run_rerun=False,
        update_disposition=False,
    )

    payload = institutional.build_institutional_provenance_boundary_ledger(
        repo_root=REPO_ROOT,
        wave35e_dir=wave35e_dir,
        wave35g_dir=output_dir,
    )

    assert payload["status"] == "complete_with_enforceable_boundaries"
    assert payload["phase"] == "35G.4"
    assert payload["required_output_artifact"] == str(
        (output_dir / "institutional_provenance_boundary_ledger.json").resolve()
    )
    assert set(payload["affected_findings"]) == INSTITUTIONAL_BLOCKERS
    assert payload["summary"] == {
        "affected_finding_count": 6,
        "source_ledger_row_count": 4,
        "runtime_owned_provenance_count": 0,
        "not_closeout_authority_count": 6,
        "final_publication_allowed_by_manual_ledgers": False,
        "deterministic_closeout_allowed_by_manual_ledgers": False,
    }

    rows = payload["rows"]
    assert {row["finding_id"] for row in rows} == INSTITUTIONAL_BLOCKERS
    assert {row["surface"] for row in rows} == {
        "implementation_feasibility",
        "contestability_appeals",
    }
    assert all(row["evidence_authority"] == "not_closeout_authority" for row in rows)
    assert all(row["runtime_owned_provenance_present"] is False for row in rows)
    assert all(row["counts_toward_final_publication"] is False for row in rows)
    assert all(row["counts_toward_deterministic_closeout"] is False for row in rows)
    assert all(row["explicit_caveat"] for row in rows)
    assert all(
        row["enforceable_boundary"]["boundary_decision"] == "not_closeout_authority" for row in rows
    )
    assert all(
        row["enforceable_boundary"]["blocks_final_publication_closeout_authority"] is True
        for row in rows
    )
    assert all(
        row["enforceable_boundary"]["blocks_deterministic_closeout_authority"] is True
        for row in rows
    )


def test_wave35g_institutional_boundary_validator_rejects_manual_closeout_use(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "wave-35G"
    payload = institutional.build_institutional_provenance_boundary_ledger(
        repo_root=REPO_ROOT,
        wave35g_dir=output_dir,
    )
    payload["rows"][0]["evidence_authority"] = "manual_assertion"
    payload["rows"][0]["counts_toward_final_publication"] = True
    payload["rows"][0]["counts_toward_deterministic_closeout"] = True
    payload["rows"][0]["enforceable_boundary"] = None

    errors = institutional.validate_institutional_provenance_boundary_ledger(payload)

    assert any(
        "manual institutional ledger cannot count toward final publication" in error
        for error in errors
    )
    assert any(
        "manual institutional ledger cannot count toward deterministic closeout" in error
        for error in errors
    )
    assert any("missing enforceable not_closeout_authority boundary" in error for error in errors)


def test_wave35g_runtime_owned_provenance_can_count_as_closeout_authority() -> None:
    row = {
        "evidence_authority": "runtime_emitted",
        "runtime_owned_provenance_present": True,
        "runtime_owned_provenance": {
            "producer": "runtime.institutional_provenance",
            "event_refs": ["runtime-event://appeal/outcome/applied"],
            "artifact_refs": ["quality_evidence/continuous_governance_reissue_report.json"],
        },
        "counts_toward_final_publication": True,
        "counts_toward_deterministic_closeout": True,
        "enforceable_boundary": None,
    }

    assert institutional.row_has_closeout_authority(row) is True


def test_wave35g_memory_authority_runtime_abstention_trace_records_runtime_gate() -> None:
    payload = json.loads(MEMORY_ARTIFACT_PATH.read_text(encoding="utf-8"))

    assert payload["status"] == "complete"
    assert payload["phase"] == "35G.2"
    assert payload["required_output_artifact"] == str(MEMORY_ARTIFACT_PATH.relative_to(REPO_ROOT))
    assert set(payload["affected_wave35f_blockers"]) == {
        "PDD-083-F001",
        "PDD-083-F002",
        "PDD-083-F003",
    }

    records = payload["runtime_authority_records"]
    assert {record["authority_kind"] for record in records} == {
        "no_memory_abstention",
        "memory_use_authority",
    }
    assert all(record["runtime_owned"] is True for record in records)
    assert all(
        record["emission_order"] < record["serious_output_influence_order"] for record in records
    )
    assert all(record["tenant_scope"]["tenant_id"] for record in records)
    assert all(record["tenant_scope"]["cell_id"] for record in records)
    assert all(record["prompt_authority_refs"] for record in records)
    assert all(record["tool_authority_refs"] for record in records)
    assert all(record["contamination_checks"] for record in records)

    abstention = next(
        record for record in records if record["authority_kind"] == "no_memory_abstention"
    )
    assert abstention["memory_used"] is False
    assert abstention["replay_surface_empty"] is True
    assert abstention["selected_memory_refs"] == []
    assert abstention["empty_replay_surface_accepted_without_runtime_record"] is False

    handoff = next(
        record for record in records if record["authority_kind"] == "memory_use_authority"
    )
    assert handoff["memory_used"] is True
    assert handoff["selected_memory_refs"]
    assert handoff["retrieval_event_refs"]
    assert handoff["applicability_refs"]

    empty_replay_proof = payload["empty_replay_surface_proof"]
    assert empty_replay_proof["empty_replay_without_record_authorized"] is False
    assert empty_replay_proof["empty_replay_with_runtime_abstention_authorized"] is True
    assert (
        "empty replay surface is not memory abstention" in empty_replay_proof["negative_assertion"]
    )

    assert payload["reviewer_commands"]
    assert all(command["exit_code"] == 0 for command in payload["reviewer_commands"])
    assert all(row["evidence_authority"] == "runtime_emitted" for row in payload["evidence_rows"])
    assert all(
        row["counts_toward_deterministic_closeout"] is True for row in payload["evidence_rows"]
    )
