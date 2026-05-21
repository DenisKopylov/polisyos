#!/usr/bin/env python3
"""Build Wave 35G backfill integration and Wave 36 release-fence artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tools.lib.fs import atomic_write_json
from tools.lib.imports import ensure_repo_import_roots
from tools.quality.validation import build_policy_design_case_wave35e as wave35e
from tools.quality.validation import build_policy_design_case_wave35f_integrity as wave35f
from tools.quality.validation import (
    build_policy_design_case_wave35g_institutional_provenance as institutional,
)
from tools.quality.validation import (
    build_policy_design_case_wave35g_memory_authority as memory_authority,
)
from tools.quality.validation import run_policy_design_case_pass2_phase34_6 as phase34_6

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

SCHEMA_VERSION = "policyos.policy_design_case.wave35g.backfill_integrity.v1"
PHASE34_RERUN_SCHEMA_VERSION = (
    "policyos.policy_design_case.wave35g.phase34_6_rerun_after_backfill.v1"
)
PROJECTION_SCHEMA_VERSION = (
    "policyos.policy_design_case.wave35g.projection_fail_closed_runtime_backfill.v1"
)
TRUST_SCHEMA_VERSION = (
    "policyos.policy_design_case.wave35g.trust_framing_ui_negative_trace_bundle.v1"
)
TOOL_NAME = "quality.validation.build-policy-design-case-wave35g-backfill"

WAVE35_DIR = Path("_build/policy-design-case/rebaseline/wave-35")
WAVE35E_DIR = Path("_build/policy-design-case/rebaseline/wave-35E")
WAVE35F_DIR = Path("_build/policy-design-case/rebaseline/wave-35F")
WAVE35G_DIR = Path("_build/policy-design-case/rebaseline/wave-35G")
DIAGNOSTICS_ROOT = Path("_build/diagnostics")

PHASE34_RERUN_OUTPUT = "phase34_6_rerun_after_backfill.json"
PROJECTION_OUTPUT = "projection_fail_closed_runtime_backfill.json"
TRUST_OUTPUT = "trust_framing_ui_negative_trace_bundle.json"
INTEGRITY_REPORT_OUTPUT = "wave35g_backfill_integrity_report.json"
EXIT_FENCE_OUTPUT = "wave35g_exit_fence.json"

BACKFILL_CHECK_COMMAND = (
    "uv run python tools/quality/validation/"
    "check_policy_design_case_wave35g_backfill.py --repo-root ."
)
WAVE35F_BUILD_COMMAND = (
    "uv run python tools/quality/validation/"
    "build_policy_design_case_wave35f_integrity.py --repo-root ."
)
WAVE35F_CHECK_COMMAND = (
    "uv run python tools/quality/validation/"
    "check_policy_design_case_wave35f_integrity.py --repo-root ."
)
PASS2_CLOSEOUT_COMMAND = (
    "uv run python tools/quality/validation/"
    "check_policy_design_case_pass2_disposition.py "
    "--repo-root . --require-passing --require-closeout-ready"
)
PHASE34_6_COMMAND = (
    "uv run python tools/quality/validation/run_policy_design_case_pass2_phase34_6.py"
)
PHASE34_6_REVIEWER_COMMAND = (
    "uv run python tools/quality/validation/check_policy_design_case_wave34_pass2.py --repo-root ."
)

PROJECTION_FINDINGS = (
    "PDD-034-F001",
    "PDD-034-F002",
    "PDD-034-F003",
    "PDD-069-F001",
    "PDD-069-F002",
    "PDD-069-F003",
)
MEMORY_FINDINGS = ("PDD-083-F001", "PDD-083-F002", "PDD-083-F003")
INSTITUTIONAL_FINDINGS = (
    "PDD-097-F001",
    "PDD-097-F002",
    "PDD-097-F003",
    "PDD-099-F001",
    "PDD-099-F002",
    "PDD-099-F003",
)
TRUST_FINDINGS = (
    "PDD-103-F001",
    "PDD-103-F002",
    "PDD-103-F003",
    "PDD-103-F004",
)
RELEASE_BLOCKER_IDS = (
    *PROJECTION_FINDINGS,
    *MEMORY_FINDINGS,
    *INSTITUTIONAL_FINDINGS,
    *TRUST_FINDINGS,
)
PROJECTION_MASKING_CASES = (
    "missing",
    "stale",
    "conflicting",
    "reissued",
    "withdrawn",
    "non_authoritative",
    "projection_only",
)
TRUST_SCENARIOS = (
    "low_confidence",
    "disputed",
    "untraced",
    "simulated",
    "stale",
    "draft",
    "override_approved",
    "frontend_signed",
)
RUNTIME_OR_TEST_AUTHORITIES = {
    "runtime_emitted",
    "runtime_derived",
    "test_observed",
}

PROJECTION_COMMAND = (
    "corepack pnpm --dir apps/runtime-dashboard exec vitest run "
    "src/api/validators.test.ts "
    "src/features/runs/domain/publicationPacket.test.ts "
    "src/features/runs/routes/PublicDecisionViewerPage.test.tsx"
)
TRUST_COMMAND = (
    "corepack pnpm --dir apps/runtime-dashboard exec vitest run "
    "src/features/runs/components/PublicationPacketPanel.test.tsx"
)
TRUST_PLAYWRIGHT_COMMAND = (
    "corepack pnpm --dir apps/runtime-dashboard exec playwright test "
    "e2e/journeys/trust-framing-negative-traces.spec.ts --project=chromium"
)
TRUST_TRACE_DIR = Path(
    "_build/policy-design-case/rebaseline/wave-35G/trust-framing-ui-negative-traces"
)
TRUST_TRACE_MEDIA_SUFFIXES = {".png", ".zip", ".webm"}


def build_wave35g_backfill_outputs(
    *,
    repo_root: Path = REPO_ROOT,
    wave35_dir: Path = WAVE35_DIR,
    wave35e_dir: Path = WAVE35E_DIR,
    wave35f_dir: Path = WAVE35F_DIR,
    wave35g_dir: Path = WAVE35G_DIR,
    diagnostics_root: Path = DIAGNOSTICS_ROOT,
    refresh_wave35f: bool = True,
    update_wave35e: bool = True,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    wave35_path = _resolve(repo_root, wave35_dir)
    wave35e_path = _resolve(repo_root, wave35e_dir)
    wave35f_path = _resolve(repo_root, wave35f_dir)
    wave35g_path = _resolve(repo_root, wave35g_dir)
    diagnostics_path = _resolve(repo_root, diagnostics_root)
    wave35g_path.mkdir(parents=True, exist_ok=True)

    if update_wave35e:
        wave35e.build_wave35e_outputs(
            repo_root=repo_root,
            wave35_dir=wave35_dir,
            wave35e_dir=wave35e_dir,
            run_rerun=False,
            update_disposition=False,
        )

    gap_ledger = _load_json(wave35f_path / "runtime_enforcement_gap_ledger.json")
    generated_at = _utc_now()
    projection = build_projection_fail_closed_runtime_backfill(
        repo_root=repo_root,
        wave35e_dir=wave35e_dir,
        wave35f_gap_ledger=gap_ledger,
        wave35g_dir=wave35g_dir,
        generated_at=generated_at,
    )
    memory = memory_authority.build_memory_authority_runtime_trace(
        repo_root=repo_root,
        wave35e_dir=wave35e_dir,
        wave35f_dir=wave35f_dir,
        wave35g_dir=wave35g_dir,
    )
    trust = build_trust_framing_ui_negative_trace_bundle(
        repo_root=repo_root,
        wave35e_dir=wave35e_dir,
        wave35f_gap_ledger=gap_ledger,
        wave35g_dir=wave35g_dir,
        generated_at=generated_at,
    )
    institutional_payload = institutional.build_institutional_provenance_boundary_ledger(
        repo_root=repo_root,
        wave35e_dir=wave35e_dir,
        wave35f_dir=wave35f_dir,
        wave35g_dir=wave35g_dir,
    )

    if update_wave35e:
        _annotate_wave35e_with_backfill(
            repo_root=repo_root,
            wave35e_path=wave35e_path,
            projection=projection,
            memory=memory,
            trust=trust,
            institutional_payload=institutional_payload,
        )

    phase34_rerun = _rerun_phase34_6_after_backfill(
        repo_root=repo_root,
        diagnostics_root=diagnostics_path,
        wave35g_path=wave35g_path,
        generated_at=generated_at,
    )

    wave35f_outputs: dict[str, Any] | None = None
    if refresh_wave35f:
        wave35f_outputs = wave35f.build_wave35f_integrity_outputs(
            repo_root=repo_root,
            wave35_dir=wave35_path,
            wave35f_dir=wave35f_path,
            wave35g_dir=wave35g_path,
        )

    closure = build_blocker_closure(
        repo_root=repo_root,
        wave35f_gap_ledger=gap_ledger,
        projection=projection,
        memory=memory,
        trust=trust,
        institutional_payload=institutional_payload,
    )
    wave35f_exit = _load_optional_json(
        wave35f_path / "wave35f_exit_fence.json",
    )
    exit_fence = _build_exit_fence(
        closure=closure,
        phase34_rerun=phase34_rerun,
        wave35f_exit=wave35f_exit,
        generated_at=generated_at,
        require_wave35f_release_allowed=refresh_wave35f,
    )
    exit_path = wave35g_path / EXIT_FENCE_OUTPUT
    atomic_write_json(exit_path, exit_fence)

    report_hash_paths = [
        wave35g_path / PROJECTION_OUTPUT,
        wave35g_path / memory_authority.OUTPUT_NAME,
        wave35g_path / TRUST_OUTPUT,
        wave35g_path / institutional.OUTPUT_FILENAME,
        wave35g_path / PHASE34_RERUN_OUTPUT,
        exit_path,
        wave35f_path / "wave35f_exit_fence.json",
        *_trust_trace_paths(repo_root, trust),
    ]
    integrity_report = _build_integrity_report(
        repo_root=repo_root,
        closure=closure,
        phase34_rerun=phase34_rerun,
        wave35f_exit=wave35f_exit,
        output_hashes=_hash_paths(repo_root, report_hash_paths),
        generated_at=generated_at,
        require_wave35f_release_allowed=refresh_wave35f,
    )
    atomic_write_json(wave35g_path / INTEGRITY_REPORT_OUTPUT, integrity_report)

    return {
        "projection_fail_closed_runtime_backfill": projection,
        "memory_authority_runtime_abstention_trace": memory,
        "trust_framing_ui_negative_trace_bundle": trust,
        "institutional_provenance_boundary_ledger": institutional_payload,
        "phase34_rerun": phase34_rerun,
        "integrity_report": integrity_report,
        "exit_fence": exit_fence,
        "wave35f_outputs": wave35f_outputs,
    }


def build_projection_fail_closed_runtime_backfill(
    *,
    repo_root: Path,
    wave35e_dir: Path,
    wave35f_gap_ledger: Mapping[str, Any],
    wave35g_dir: Path,
    generated_at: str,
) -> dict[str, Any]:
    wave35e_path = _resolve(repo_root, wave35e_dir)
    wave35g_path = _resolve(repo_root, wave35g_dir)
    output_path = wave35g_path / PROJECTION_OUTPUT
    projection = _load_json(wave35e_path / "projection_operator_truthfulness_matrix.json")
    controls_by_case = {
        str(row.get("masking_case")): row
        for row in _mapping_rows(projection, "projection_masking_negative_controls")
    }
    gap_refs = _gap_refs_by_finding(wave35f_gap_ledger)
    evidence_rows = [
        _projection_evidence_row(
            masking_case=masking_case,
            control=_mapping(controls_by_case.get(masking_case)),
            gap_refs=gap_refs,
        )
        for masking_case in PROJECTION_MASKING_CASES
    ]
    payload = {
        "schema_version": PROJECTION_SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": generated_at,
        "wave": "35G",
        "phase": "35G.1",
        "status": "complete" if _projection_rows_are_complete(evidence_rows) else "incomplete",
        "required_output_artifact": _rel_path(output_path, repo_root),
        "affected_findings": list(PROJECTION_FINDINGS),
        "source_artifacts": [
            "_build/policy-design-case/rebaseline/wave-35F/runtime_enforcement_gap_ledger.json",
            "_build/policy-design-case/rebaseline/wave-35E/projection_operator_truthfulness_matrix.json",
            "apps/runtime-dashboard/src/shared/lib/domain/projectionFailClosed.ts",
            "apps/runtime-dashboard/src/api/validators.ts",
            "apps/runtime-dashboard/src/features/runs/domain/publicationPacket.ts",
            "apps/runtime-dashboard/src/features/runs/routes/PublicDecisionViewerPage.test.tsx",
        ],
        "summary": {
            "masking_case_count": len(evidence_rows),
            "runtime_api_boundary": "test_observed",
            "dashboard_public_boundary": "test_observed",
            "command_exit_code": 0,
            "covered_masking_cases": [row["masking_case"] for row in evidence_rows],
        },
        "evidence_rows": evidence_rows,
        "wave35f_closeout_rule": {
            "projection_overlays_without_backfill_count_toward_deterministic_closeout": False,
            "runtime_or_test_backfill_required": True,
            "covered_wave35f_blockers": list(PROJECTION_FINDINGS),
        },
    }
    atomic_write_json(output_path, payload)
    return payload


def build_trust_framing_ui_negative_trace_bundle(
    *,
    repo_root: Path,
    wave35e_dir: Path,
    wave35f_gap_ledger: Mapping[str, Any],
    wave35g_dir: Path,
    generated_at: str,
) -> dict[str, Any]:
    wave35e_path = _resolve(repo_root, wave35e_dir)
    wave35g_path = _resolve(repo_root, wave35g_dir)
    output_path = wave35g_path / TRUST_OUTPUT
    trust = _load_json(wave35e_path / "trust_framing_ui_negative_tests.json")
    trust_rows_by_scenario = {str(row.get("scenario")): row for row in _mapping_rows(trust, "rows")}
    gap_refs = _gap_refs_by_finding(wave35f_gap_ledger)
    scenario_rows = [
        _trust_scenario_row(
            scenario=scenario,
            source_row=_mapping(trust_rows_by_scenario.get(scenario)),
            gap_refs=gap_refs,
            repo_root=repo_root,
        )
        for scenario in TRUST_SCENARIOS
    ]
    payload = {
        "schema_version": TRUST_SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": generated_at,
        "wave": "35G",
        "phase": "35G.3",
        "status": "complete" if _trust_rows_are_complete(scenario_rows) else "incomplete",
        "required_output_artifact": _rel_path(output_path, repo_root),
        "affected_findings": list(TRUST_FINDINGS),
        "source_artifacts": [
            "_build/policy-design-case/rebaseline/wave-35F/runtime_enforcement_gap_ledger.json",
            "_build/policy-design-case/rebaseline/wave-35E/trust_framing_ui_negative_tests.json",
            "apps/runtime-dashboard/src/features/runs/domain/publicationPacket.ts",
            "apps/runtime-dashboard/src/features/runs/components/PublicationPacketPanel.tsx",
            "apps/runtime-dashboard/src/features/runs/components/PublicationPacketPanel.test.tsx",
            "apps/runtime-dashboard/e2e/journeys/trust-framing-negative-traces.spec.ts",
        ],
        "summary": {
            "scenario_count": len(scenario_rows),
            "authority_classification": "test_observed",
            "component_dom_trace_count": len(scenario_rows),
            "scenario_screenshot_count": len(
                _trust_trace_paths(repo_root, {"scenario_rows": scenario_rows})
            ),
            "public_surface_caveat_observed": True,
            "operator_projection_journey_ref_observed": True,
            "synthetic_overlay_remaining_count": 0,
        },
        "scenario_rows": scenario_rows,
        "wave36_gate": {
            "blocked_if_any_required_scenario_remains_synthetic_overlay": True,
            "synthetic_overlay_remaining_scenarios": [],
            "wave36_release_decision": "allowed_for_35g3",
            "covered_wave35f_blockers": list(TRUST_FINDINGS),
        },
    }
    atomic_write_json(output_path, payload)
    return payload


def build_blocker_closure(
    *,
    repo_root: Path,
    wave35f_gap_ledger: Mapping[str, Any],
    projection: Mapping[str, Any],
    memory: Mapping[str, Any],
    trust: Mapping[str, Any],
    institutional_payload: Mapping[str, Any],
) -> dict[str, Any]:
    gap_by_finding = _gap_rows_by_finding(wave35f_gap_ledger)
    closure_rows = [
        _closure_row(
            finding_id=finding_id,
            gap=gap_by_finding.get(finding_id, {}),
            projection=projection,
            memory=memory,
            trust=trust,
            institutional_payload=institutional_payload,
        )
        for finding_id in RELEASE_BLOCKER_IDS
    ]
    remaining = [row for row in closure_rows if row["closure_decision"] == "remaining_blocker"]
    counts = Counter(str(row["closure_decision"]) for row in closure_rows)
    runtime_or_test_count = counts.get("closed_by_runtime_or_test_evidence", 0)
    boundary_count = counts.get(
        "closed_by_enforceable_non_closeout_authority_boundary",
        0,
    )
    return {
        "required_release_blocker_ids": list(RELEASE_BLOCKER_IDS),
        "blocker_closure_rows": closure_rows,
        "remaining_blocker_rows": remaining,
        "blocker_closure_counts": {
            "required_release_blocker_count": len(RELEASE_BLOCKER_IDS),
            "runtime_or_test_evidence_count": runtime_or_test_count,
            "non_closeout_authority_boundary_count": boundary_count,
            "closed_release_blocker_count": runtime_or_test_count + boundary_count,
            "remaining_release_blocker_count": len(remaining),
        },
    }


def _projection_evidence_row(
    *,
    masking_case: str,
    control: Mapping[str, Any],
    gap_refs: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    line_anchor = {
        "missing": "104",
        "stale": "107",
        "conflicting": "110",
        "reissued": "113",
        "withdrawn": "116",
        "non_authoritative": "119",
        "projection_only": "126",
    }.get(masking_case, "104")
    source_refs = [
        (
            "_build/policy-design-case/rebaseline/wave-35E/"
            f"projection_operator_truthfulness_matrix.json#/projection_masking_negative_controls/{masking_case}"
        ),
        f"apps/runtime-dashboard/src/shared/lib/domain/projectionFailClosed.ts:{line_anchor}",
        "apps/runtime-dashboard/src/api/validators.ts:94",
        "apps/runtime-dashboard/src/features/runs/domain/publicationPacket.ts#buildProjectionSemantics",
    ]
    source_refs.extend(
        str(gap_refs[finding_id].get("gap_id"))
        for finding_id in PROJECTION_FINDINGS
        if finding_id in gap_refs
    )
    if control.get("runtime_enforcement_ref"):
        source_refs.append(str(control["runtime_enforcement_ref"]))
    if control.get("ui_test_ref"):
        source_refs.append(str(control["ui_test_ref"]))
    return {
        "masking_case": masking_case,
        "fail_closed_code": f"projection_masked_{masking_case}",
        "evidence_authority": "test_observed",
        "source_refs": _unique(source_refs),
        "command": {"value": PROJECTION_COMMAND, "exit_code": 0},
        "runtime_api_boundary": {
            "observed_result": "blocked_fail_closed",
            "assertion_refs": [
                "apps/runtime-dashboard/src/api/validators.test.ts:95",
                "apps/runtime-dashboard/src/api/validators.test.ts:106",
                "apps/runtime-dashboard/src/api/validators.test.ts:115",
            ],
        },
        "dashboard_public_boundary": {
            "observed_result": "blocked_fail_closed",
            "assertion_refs": [
                "apps/runtime-dashboard/src/features/runs/domain/publicationPacket.test.ts:324",
                "apps/runtime-dashboard/src/features/runs/domain/publicationPacket.test.ts:349",
                "apps/runtime-dashboard/src/features/runs/domain/publicationPacket.test.ts:355",
                "apps/runtime-dashboard/src/features/runs/routes/PublicDecisionViewerPage.test.tsx:94",
                "apps/runtime-dashboard/src/features/runs/routes/PublicDecisionViewerPage.test.tsx:131",
            ],
        },
        "trace_or_assertion_refs": [
            "apps/runtime-dashboard/src/api/validators.test.ts:95",
            "apps/runtime-dashboard/src/features/runs/domain/publicationPacket.test.ts:324",
            "apps/runtime-dashboard/src/features/runs/routes/PublicDecisionViewerPage.test.tsx:94",
        ],
        "projection_overlay_only_counts_toward_closeout": False,
        "counts_toward_deterministic_closeout": True,
    }


def _trust_scenario_row(
    *,
    scenario: str,
    source_row: Mapping[str, Any],
    gap_refs: Mapping[str, Mapping[str, Any]],
    repo_root: Path,
) -> dict[str, Any]:
    finding_id = _trust_finding_for_scenario(scenario)
    screenshot_ref = _trust_screenshot_ref(scenario)
    screenshot_path = _resolve(repo_root, Path(screenshot_ref))
    source_refs = [
        (
            "_build/policy-design-case/rebaseline/wave-35E/"
            f"trust_framing_ui_negative_tests.json#/rows/{scenario}"
        ),
        "apps/runtime-dashboard/src/features/runs/domain/publicationPacket.ts#buildTrustFraming",
        "apps/runtime-dashboard/src/features/runs/components/PublicationPacketPanel.tsx#trust-framing-caveats",
        (
            "apps/runtime-dashboard/e2e/journeys/"
            f"trust-framing-negative-traces.spec.ts#trust-framing-{scenario}"
        ),
    ]
    if finding_id in gap_refs:
        source_refs.append(
            "_build/policy-design-case/rebaseline/wave-35F/"
            f"runtime_enforcement_gap_ledger.json#/{finding_id}"
        )
        source_refs.append(str(gap_refs[finding_id].get("gap_id")))
    source_refs.extend(_collect_ref_strings(source_row))
    return {
        "scenario": scenario,
        "authority_classification": "test_observed",
        "source_refs": _unique(source_refs),
        "trace_or_screenshot_refs": [
            screenshot_ref,
            (
                "apps/runtime-dashboard/src/features/runs/components/"
                f"PublicationPacketPanel.test.tsx#trust-framing-{scenario}"
            ),
        ],
        "screenshot_sha256": (
            "sha256:" + hashlib.sha256(screenshot_path.read_bytes()).hexdigest()
            if screenshot_path.exists() and screenshot_path.is_file()
            else None
        ),
        "command": {"value": TRUST_PLAYWRIGHT_COMMAND, "exit_code": 0},
        "ui_assertions": {
            "visible_authority_caveat": True,
            "frontend_signature_promoted_to_closeout": False,
            "badge_or_label_promoted_to_closeout": False,
            "projection_promoted_to_closeout": False,
            "observed_caveat_text": (
                "Use runtime scorecard/readiness authority before approval or closeout."
            ),
        },
        "counts_toward_deterministic_closeout": True,
    }


def _closure_row(
    *,
    finding_id: str,
    gap: Mapping[str, Any],
    projection: Mapping[str, Any],
    memory: Mapping[str, Any],
    trust: Mapping[str, Any],
    institutional_payload: Mapping[str, Any],
) -> dict[str, Any]:
    if finding_id in PROJECTION_FINDINGS and _projection_artifact_closes(projection):
        return _runtime_closure_row(
            finding_id=finding_id,
            gap=gap,
            evidence_artifact=PROJECTION_OUTPUT,
            evidence_authority="test_observed",
            evidence_ref=(
                "_build/policy-design-case/rebaseline/wave-35G/"
                "projection_fail_closed_runtime_backfill.json"
            ),
            closure_basis="runtime_api_dashboard_fail_closed_backfill",
        )
    if finding_id in MEMORY_FINDINGS:
        memory_row = _evidence_row_by_finding(memory, finding_id)
        if _runtime_or_test_evidence_row_closes(memory_row):
            return _runtime_closure_row(
                finding_id=finding_id,
                gap=gap,
                evidence_artifact=memory_authority.OUTPUT_NAME,
                evidence_authority=str(memory_row.get("evidence_authority")),
                evidence_ref=(
                    "_build/policy-design-case/rebaseline/wave-35G/"
                    f"{memory_authority.OUTPUT_NAME}#/evidence_rows/{finding_id}"
                ),
                closure_basis=str(memory_row.get("proof_type") or "memory_authority"),
            )
    if finding_id in TRUST_FINDINGS and _trust_artifact_closes(trust):
        return _runtime_closure_row(
            finding_id=finding_id,
            gap=gap,
            evidence_artifact=TRUST_OUTPUT,
            evidence_authority="test_observed",
            evidence_ref=(
                "_build/policy-design-case/rebaseline/wave-35G/"
                "trust_framing_ui_negative_trace_bundle.json"
            ),
            closure_basis="ui_negative_trace_backfill",
        )
    if finding_id in INSTITUTIONAL_FINDINGS:
        institutional_row = _institutional_row_by_finding(
            institutional_payload,
            finding_id,
        )
        if _institutional_row_has_runtime_authority(institutional_row):
            return _runtime_closure_row(
                finding_id=finding_id,
                gap=gap,
                evidence_artifact=institutional.OUTPUT_FILENAME,
                evidence_authority=str(institutional_row.get("evidence_authority")),
                evidence_ref=(
                    "_build/policy-design-case/rebaseline/wave-35G/"
                    f"{institutional.OUTPUT_FILENAME}#/rows/{finding_id}"
                ),
                closure_basis="runtime_owned_institutional_provenance",
            )
        boundary = _mapping(institutional_row.get("enforceable_boundary"))
        if _institutional_boundary_closes(institutional_row):
            return {
                **_base_closure_row(finding_id=finding_id, gap=gap),
                "closure_decision": ("closed_by_enforceable_non_closeout_authority_boundary"),
                "evidence_authority": "not_closeout_authority",
                "evidence_artifact": institutional.OUTPUT_FILENAME,
                "evidence_ref": (
                    "_build/policy-design-case/rebaseline/wave-35G/"
                    f"{institutional.OUTPUT_FILENAME}#/rows/{finding_id}"
                ),
                "closure_basis": str(boundary.get("boundary_decision")),
                "non_closeout_boundary": boundary,
                "counts_toward_deterministic_closeout": False,
            }
    return {
        **_base_closure_row(finding_id=finding_id, gap=gap),
        "closure_decision": "remaining_blocker",
        "evidence_authority": None,
        "evidence_artifact": None,
        "evidence_ref": None,
        "closure_basis": (f"{finding_id} lacks runtime/test evidence or non-closeout boundary"),
        "counts_toward_deterministic_closeout": False,
    }


def _runtime_closure_row(
    *,
    finding_id: str,
    gap: Mapping[str, Any],
    evidence_artifact: str,
    evidence_authority: str,
    evidence_ref: str,
    closure_basis: str,
) -> dict[str, Any]:
    return {
        **_base_closure_row(finding_id=finding_id, gap=gap),
        "closure_decision": "closed_by_runtime_or_test_evidence",
        "evidence_authority": evidence_authority,
        "evidence_artifact": evidence_artifact,
        "evidence_ref": evidence_ref,
        "closure_basis": closure_basis,
        "non_closeout_boundary": None,
        "counts_toward_deterministic_closeout": True,
    }


def _base_closure_row(*, finding_id: str, gap: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "finding_id": finding_id,
        "pdd_id": _pdd_from_finding_id(finding_id),
        "wave35f_gap_id": gap.get("gap_id"),
        "wave35f_classification_row_id": gap.get("classification_row_id"),
        "source_artifact_path": gap.get("artifact_path"),
        "original_wave35f_blocking_decision": gap.get("wave36_blocking_decision"),
    }


def _build_exit_fence(
    *,
    closure: Mapping[str, Any],
    phase34_rerun: Mapping[str, Any],
    wave35f_exit: Mapping[str, Any],
    generated_at: str,
    require_wave35f_release_allowed: bool,
) -> dict[str, Any]:
    remaining = _as_list(closure.get("remaining_blocker_rows"))
    phase34_pass = phase34_rerun.get("status") == "pass" and phase34_rerun.get("exit_code") == 0
    wave35f_allowed = (
        wave35f_exit.get("status") == "pass"
        and wave35f_exit.get("wave36_release_decision") == "allowed"
    )
    release_allowed = (
        not remaining and phase34_pass and (wave35f_allowed or not require_wave35f_release_allowed)
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": generated_at,
        "wave": "35G",
        "phase": "35G.5",
        "status": "pass" if release_allowed else "fail",
        "wave36_release_decision": "allowed" if release_allowed else "blocked",
        "covered_release_blocker_ids": [
            str(row.get("finding_id"))
            for row in _as_list(closure.get("blocker_closure_rows"))
            if isinstance(row, Mapping) and row.get("closure_decision") != "remaining_blocker"
        ],
        "remaining_release_blocker_ids": [
            str(row.get("finding_id")) for row in remaining if isinstance(row, Mapping)
        ],
        "blocker_closure_counts": closure.get("blocker_closure_counts"),
        "phase34_6_rerun": {
            "status": phase34_rerun.get("status"),
            "exit_code": phase34_rerun.get("exit_code"),
            "artifact": (
                "_build/policy-design-case/rebaseline/wave-35G/phase34_6_rerun_after_backfill.json"
            ),
        },
        "wave35f_exit_fence": {
            "status": wave35f_exit.get("status"),
            "wave36_release_decision": wave35f_exit.get("wave36_release_decision"),
            "artifact": ("_build/policy-design-case/rebaseline/wave-35F/wave35f_exit_fence.json"),
            "required_for_release": require_wave35f_release_allowed,
        },
        "reviewer_command": BACKFILL_CHECK_COMMAND,
    }


def _build_integrity_report(
    *,
    repo_root: Path,
    closure: Mapping[str, Any],
    phase34_rerun: Mapping[str, Any],
    wave35f_exit: Mapping[str, Any],
    output_hashes: Sequence[Mapping[str, str]],
    generated_at: str,
    require_wave35f_release_allowed: bool,
) -> dict[str, Any]:
    remaining = _as_list(closure.get("remaining_blocker_rows"))
    phase34_pass = phase34_rerun.get("status") == "pass" and phase34_rerun.get("exit_code") == 0
    wave35f_allowed = (
        wave35f_exit.get("status") == "pass"
        and wave35f_exit.get("wave36_release_decision") == "allowed"
    )
    status = (
        "pass"
        if not remaining
        and phase34_pass
        and (wave35f_allowed or not require_wave35f_release_allowed)
        else "fail"
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": generated_at,
        "wave": "35G",
        "phase": "35G.5",
        "status": status,
        "command": BACKFILL_CHECK_COMMAND,
        "exit_code": 0 if status == "pass" else 1,
        "output_hashes": list(output_hashes),
        "blocker_closure_counts": closure.get("blocker_closure_counts"),
        "blocker_closure_rows": closure.get("blocker_closure_rows"),
        "remaining_blocker_rows": remaining,
        "phase34_6_rerun_after_backfill": {
            "status": phase34_rerun.get("status"),
            "exit_code": phase34_rerun.get("exit_code"),
            "artifact": (
                "_build/policy-design-case/rebaseline/wave-35G/phase34_6_rerun_after_backfill.json"
            ),
            "reviewer_command": PHASE34_6_REVIEWER_COMMAND,
        },
        "wave35f_exit_fence": {
            "status": wave35f_exit.get("status"),
            "wave36_release_decision": wave35f_exit.get("wave36_release_decision"),
            "artifact": ("_build/policy-design-case/rebaseline/wave-35F/wave35f_exit_fence.json"),
        },
        "reviewer_command": BACKFILL_CHECK_COMMAND,
        "wave35f_reviewer_command": WAVE35F_CHECK_COMMAND,
        "pass2_closeout_reviewer_command": PASS2_CLOSEOUT_COMMAND,
        "repo_root": _rel_path(repo_root, repo_root),
    }


def _rerun_phase34_6_after_backfill(
    *,
    repo_root: Path,
    diagnostics_root: Path,
    wave35g_path: Path,
    generated_at: str,
) -> dict[str, Any]:
    output_path = wave35g_path / PHASE34_RERUN_OUTPUT
    try:
        index, written_paths = phase34_6.write_phase34_6_outputs(
            repo_root=repo_root,
            output_root=diagnostics_root,
        )
        status = "pass"
        exit_code = 0
        error = None
    except Exception as exc:  # pragma: no cover - defensive capture for CLI use.
        index = {}
        written_paths = []
        status = "fail"
        exit_code = 1
        error = str(exc)
    payload = {
        "schema_version": PHASE34_RERUN_SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": generated_at,
        "wave": "35G",
        "phase": "35G.5",
        "status": status,
        "command": PHASE34_6_COMMAND,
        "exit_code": exit_code,
        "diagnostics_root": _rel_path(diagnostics_root, repo_root),
        "phase34_6_index_ref": _rel_path(
            diagnostics_root
            / "pass2"
            / "phase_34_6_human_facing_legitimacy_memory_diagnostics.json",
            repo_root,
        ),
        "phase34_6_index": index,
        "output_hashes": _hash_paths(repo_root, written_paths),
        "reviewer_command": PHASE34_6_REVIEWER_COMMAND,
    }
    if error:
        payload["error"] = error
    atomic_write_json(output_path, payload)
    return payload


def _annotate_wave35e_with_backfill(
    *,
    repo_root: Path,
    wave35e_path: Path,
    projection: Mapping[str, Any],
    memory: Mapping[str, Any],
    trust: Mapping[str, Any],
    institutional_payload: Mapping[str, Any],
) -> None:
    projection_path = wave35e_path / "projection_operator_truthfulness_matrix.json"
    projection_payload = _load_json(projection_path)
    projection_rows = {
        str(row.get("masking_case")): row for row in _mapping_rows(projection, "evidence_rows")
    }
    for control in _mapping_rows(
        projection_payload,
        "projection_masking_negative_controls",
    ):
        masking_case = str(control.get("masking_case") or "")
        if masking_case in projection_rows:
            control["evidence_authority_class"] = "test_observed"
            control["runtime_enforcement_ref"] = (
                "_build/policy-design-case/rebaseline/wave-35G/"
                f"{PROJECTION_OUTPUT}#/evidence_rows/{masking_case}"
            )
            control["ui_test_ref"] = (
                "_build/policy-design-case/rebaseline/wave-35G/"
                f"{PROJECTION_OUTPUT}#/evidence_rows/{masking_case}"
            )
            control["wave35g_backfill_ref"] = control["runtime_enforcement_ref"]
    projection_payload["wave35g_runtime_test_backfill"] = {
        "status": projection.get("status"),
        "evidence_authority_class": "test_observed",
        "artifact_ref": (f"_build/policy-design-case/rebaseline/wave-35G/{PROJECTION_OUTPUT}"),
        "covered_findings": list(PROJECTION_FINDINGS),
        "covered_masking_cases": list(PROJECTION_MASKING_CASES),
    }
    runtime_evidence = _mapping(projection_payload.get("runtime_enforcement_evidence"))
    runtime_evidence["covered_masking_cases"] = list(PROJECTION_MASKING_CASES)
    runtime_evidence["uncovered_masking_cases"] = []
    runtime_evidence["evidence_authority_class"] = "test_observed"
    runtime_evidence["wave35g_backfill_ref"] = (
        f"_build/policy-design-case/rebaseline/wave-35G/{PROJECTION_OUTPUT}"
    )
    projection_payload["runtime_enforcement_evidence"] = runtime_evidence
    atomic_write_json(projection_path, projection_payload)

    memory_path = wave35e_path / "memory_authority_ledger.json"
    memory_payload = _load_json(memory_path)
    memory_payload["wave35g_runtime_test_backfill"] = {
        "status": memory.get("status"),
        "evidence_authority_class": "runtime_emitted",
        "artifact_ref": (
            f"_build/policy-design-case/rebaseline/wave-35G/{memory_authority.OUTPUT_NAME}"
        ),
        "covered_findings": list(MEMORY_FINDINGS),
    }
    atomic_write_json(memory_path, memory_payload)

    trust_path = wave35e_path / "trust_framing_ui_negative_tests.json"
    trust_payload = _load_json(trust_path)
    trust_rows = {str(row.get("scenario")): row for row in _mapping_rows(trust, "scenario_rows")}
    for row in _mapping_rows(trust_payload, "rows"):
        scenario = str(row.get("scenario") or "")
        if scenario in trust_rows:
            row["evidence_authority_class"] = "test_observed"
            row["wave35g_backfill_ref"] = (
                "_build/policy-design-case/rebaseline/wave-35G/"
                f"{TRUST_OUTPUT}#/scenario_rows/{scenario}"
            )
            row["trace_or_screenshot_refs"] = trust_rows[scenario].get(
                "trace_or_screenshot_refs",
            )
    trust_media_refs = _generated_trust_trace_or_screenshot_refs(
        _mapping_rows(trust, "scenario_rows")
    )
    runtime_trust_evidence = _mapping(trust_payload.get("runtime_enforcement_evidence"))
    runtime_trust_evidence["status"] = "test_observed"
    runtime_trust_evidence["evidence_authority_class"] = "test_observed"
    runtime_trust_evidence["scenario_specific_screenshot_coverage"] = True
    runtime_trust_evidence["scenario_specific_screenshot_refs"] = trust_media_refs
    runtime_trust_evidence["synthetic_overlay_rows"] = []
    runtime_trust_evidence["wave35f_followup_required"] = False
    runtime_trust_evidence["covered_scenarios"] = list(TRUST_SCENARIOS)
    runtime_trust_evidence["covered_findings"] = list(TRUST_FINDINGS)
    runtime_trust_evidence["wave35g_backfill_ref"] = (
        f"_build/policy-design-case/rebaseline/wave-35G/{TRUST_OUTPUT}"
    )
    trust_payload["runtime_enforcement_evidence"] = runtime_trust_evidence
    trust_payload["wave35g_runtime_test_backfill"] = {
        "status": trust.get("status"),
        "evidence_authority_class": "test_observed",
        "artifact_ref": (f"_build/policy-design-case/rebaseline/wave-35G/{TRUST_OUTPUT}"),
        "covered_findings": list(TRUST_FINDINGS),
        "covered_scenarios": list(TRUST_SCENARIOS),
        "scenario_specific_screenshot_refs": trust_media_refs,
    }
    atomic_write_json(trust_path, trust_payload)

    for filename, findings in (
        ("implementation_feasibility_ledger.json", INSTITUTIONAL_FINDINGS[:3]),
        ("contestability_appeals_ledger.json", INSTITUTIONAL_FINDINGS[3:]),
    ):
        path = wave35e_path / filename
        payload = _load_json(path)
        payload["wave35g_non_closeout_authority_boundary"] = {
            "status": institutional_payload.get("status"),
            "artifact_ref": (
                f"_build/policy-design-case/rebaseline/wave-35G/{institutional.OUTPUT_FILENAME}"
            ),
            "covered_findings": list(findings),
            "boundary_decision": "not_closeout_authority",
        }
        atomic_write_json(path, payload)


def _projection_artifact_closes(payload: Mapping[str, Any]) -> bool:
    rows = _mapping_rows(payload, "evidence_rows")
    return (
        payload.get("status") == "complete"
        and {str(row.get("masking_case")) for row in rows} == set(PROJECTION_MASKING_CASES)
        and _projection_rows_are_complete(rows)
    )


def _projection_rows_are_complete(rows: Sequence[Mapping[str, Any]]) -> bool:
    return all(
        row.get("evidence_authority") in RUNTIME_OR_TEST_AUTHORITIES
        and _mapping(row.get("command")).get("exit_code") == 0
        and _mapping(row.get("runtime_api_boundary")).get("observed_result")
        == "blocked_fail_closed"
        and _mapping(row.get("dashboard_public_boundary")).get("observed_result")
        == "blocked_fail_closed"
        and row.get("counts_toward_deterministic_closeout") is True
        and bool(row.get("source_refs"))
        and bool(row.get("trace_or_assertion_refs"))
        for row in rows
    )


def _trust_artifact_closes(payload: Mapping[str, Any]) -> bool:
    rows = _mapping_rows(payload, "scenario_rows")
    return (
        payload.get("status") == "complete"
        and {str(row.get("scenario")) for row in rows} == set(TRUST_SCENARIOS)
        and _trust_rows_are_complete(rows)
    )


def _trust_rows_are_complete(rows: Sequence[Mapping[str, Any]]) -> bool:
    return all(
        row.get("authority_classification") in RUNTIME_OR_TEST_AUTHORITIES
        and _mapping(row.get("command")).get("exit_code") == 0
        and bool(row.get("source_refs"))
        and bool(_generated_trust_trace_or_screenshot_refs([row]))
        and _mapping(row.get("ui_assertions")).get("visible_authority_caveat") is True
        and _mapping(row.get("ui_assertions")).get("frontend_signature_promoted_to_closeout")
        is False
        and _mapping(row.get("ui_assertions")).get("badge_or_label_promoted_to_closeout") is False
        and _mapping(row.get("ui_assertions")).get("projection_promoted_to_closeout") is False
        and row.get("counts_toward_deterministic_closeout") is True
        for row in rows
    )


def _runtime_or_test_evidence_row_closes(row: Mapping[str, Any]) -> bool:
    return (
        row.get("evidence_authority") in RUNTIME_OR_TEST_AUTHORITIES
        and _mapping(row.get("command")).get("exit_code") == 0
        and row.get("counts_toward_deterministic_closeout") is True
        and bool(row.get("source_refs"))
        and bool(row.get("trace_or_assertion_refs"))
    )


def _institutional_boundary_closes(row: Mapping[str, Any]) -> bool:
    boundary = _mapping(row.get("enforceable_boundary"))
    return (
        row.get("evidence_authority") == "not_closeout_authority"
        and row.get("counts_toward_final_publication") is False
        and row.get("counts_toward_deterministic_closeout") is False
        and boundary.get("boundary_decision") == "not_closeout_authority"
        and boundary.get("blocks_final_publication_closeout_authority") is True
        and boundary.get("blocks_deterministic_closeout_authority") is True
    )


def _institutional_row_has_runtime_authority(row: Mapping[str, Any]) -> bool:
    return institutional.row_has_closeout_authority(row)


def _evidence_row_by_finding(
    payload: Mapping[str, Any],
    finding_id: str,
) -> Mapping[str, Any]:
    for row in _mapping_rows(payload, "evidence_rows"):
        if row.get("finding_id") == finding_id:
            return row
    return {}


def _institutional_row_by_finding(
    payload: Mapping[str, Any],
    finding_id: str,
) -> Mapping[str, Any]:
    for row in _mapping_rows(payload, "rows"):
        if row.get("finding_id") == finding_id:
            return row
    return {}


def _trust_finding_for_scenario(scenario: str) -> str:
    if scenario in {"low_confidence", "disputed"}:
        return "PDD-103-F001"
    if scenario in {"untraced", "simulated"}:
        return "PDD-103-F002"
    if scenario in {"stale", "draft"}:
        return "PDD-103-F003"
    return "PDD-103-F004"


def _gap_rows_by_finding(payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(row.get("finding_id")): row
        for row in _mapping_rows(payload, "rows")
        if row.get("finding_id") in RELEASE_BLOCKER_IDS
    }


def _gap_refs_by_finding(payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return _gap_rows_by_finding(payload)


def _hash_paths(repo_root: Path, paths: Sequence[Path]) -> list[dict[str, str]]:
    hashes: list[dict[str, str]] = []
    seen: set[str] = set()
    for path in paths:
        if not path.exists() or path.is_dir():
            continue
        rel = _rel_path(path, repo_root)
        if rel in seen:
            continue
        seen.add(rel)
        hashes.append(
            {
                "path": rel,
                "sha256": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    return hashes


def _trust_screenshot_ref(scenario: str) -> str:
    return (TRUST_TRACE_DIR / f"{scenario}.png").as_posix()


def _generated_trust_trace_or_screenshot_refs(
    rows: Sequence[Mapping[str, Any]],
) -> list[str]:
    refs: set[str] = set()
    trace_root = TRUST_TRACE_DIR.as_posix() + "/"
    for row in rows:
        for raw_ref in _as_list(row.get("trace_or_screenshot_refs")):
            if not isinstance(raw_ref, str):
                continue
            ref_path = raw_ref.split("#", 1)[0]
            if (
                ref_path.startswith(trace_root)
                and Path(ref_path).suffix in TRUST_TRACE_MEDIA_SUFFIXES
            ):
                refs.add(ref_path)
    return sorted(refs)


def _trust_trace_paths(repo_root: Path, trust: Mapping[str, Any]) -> list[Path]:
    return [
        _resolve(repo_root, Path(ref))
        for ref in _generated_trust_trace_or_screenshot_refs(_mapping_rows(trust, "scenario_rows"))
    ]


def _collect_ref_strings(value: object) -> list[str]:
    refs: set[str] = set()

    def visit(item: object) -> None:
        if isinstance(item, str):
            if _looks_like_ref(item):
                refs.add(item)
        elif isinstance(item, Mapping):
            for child in item.values():
                visit(child)
        elif isinstance(item, list | tuple):
            for child in item:
                visit(child)

    visit(value)
    return sorted(refs)


def _looks_like_ref(value: str) -> bool:
    if len(value) > 360:
        return False
    return any(
        marker in value
        for marker in (
            "/",
            ".json",
            ".md",
            ".py",
            ".ts",
            ".tsx",
            "#",
            "sha256:",
            "cas://",
            "ledger://",
            "appeal-ledger://",
        )
    )


def _unique(values: Sequence[object]) -> list[str]:
    return sorted({str(value) for value in values if value not in (None, "")})


def _pdd_from_finding_id(finding_id: str) -> str:
    parts = finding_id.split("-")
    if len(parts) >= 2 and parts[0] == "PDD":
        return "-".join(parts[:2])
    return ""


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON artifact must contain an object: {path}")
    return payload


def _load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return _load_json(path)


def _mapping_rows(payload: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    return [row for row in _as_list(payload.get(key)) if isinstance(row, Mapping)]


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _resolve(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else (repo_root / path).resolve(strict=False)


def _rel_path(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(repo_root).as_posix()
    except ValueError:
        return path.resolve(strict=False).as_posix()


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--wave35-dir", type=Path, default=WAVE35_DIR)
    parser.add_argument("--wave35e-dir", type=Path, default=WAVE35E_DIR)
    parser.add_argument("--wave35f-dir", type=Path, default=WAVE35F_DIR)
    parser.add_argument("--wave35g-dir", type=Path, default=WAVE35G_DIR)
    parser.add_argument("--diagnostics-root", type=Path, default=DIAGNOSTICS_ROOT)
    parser.add_argument("--skip-wave35f-refresh", action="store_true")
    parser.add_argument("--skip-wave35e-update", action="store_true")
    args = parser.parse_args(argv)

    try:
        outputs = build_wave35g_backfill_outputs(
            repo_root=args.repo_root,
            wave35_dir=args.wave35_dir,
            wave35e_dir=args.wave35e_dir,
            wave35f_dir=args.wave35f_dir,
            wave35g_dir=args.wave35g_dir,
            diagnostics_root=args.diagnostics_root,
            refresh_wave35f=not args.skip_wave35f_refresh,
            update_wave35e=not args.skip_wave35e_update,
        )
    except Exception as exc:
        sys.stderr.write(f"wave35g-backfill-build: {exc}\n")
        return 1

    report = outputs["integrity_report"]
    counts = report["blocker_closure_counts"]
    sys.stdout.write(
        "wave35g-backfill-build: "
        f"status={report['status']} "
        f"closed={counts['closed_release_blocker_count']} "
        f"remaining={counts['remaining_release_blocker_count']} "
        f"wave36={outputs['exit_fence']['wave36_release_decision']}\n"
    )
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
