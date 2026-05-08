#!/usr/bin/env python3
"""Validate the Scientist best-in-class Phase 2.0 operating contract."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from tools.lib.fs import atomic_write_text
from tools.lib.output import ToolMessage, ToolResult, format_tool_result

ASSESSMENT_ID = "scientist_best_in_class_phase2_0"
TOOL_NAME = "ci.check-scientist-best-in-class-phase2-0"

ACTIVE_PLAN_DOC = Path("docs/plans/active/SCIENTIST_BEST_IN_CLASS_PLAN.md")
READINESS_DOC = Path("docs/reference/scientist/best-in-class-readiness.md")
INVENTORY_DOC = Path("docs/reference/scientist/scientist-capability-inventory.md")
SCIENTIST_INDEX_DOC = Path("docs/reference/scientist/index.md")
REFERENCE_DOC = Path("docs/reference/scientist/wave2-runtime-contracts.md")
ADR_INDEX_DOC = Path("docs/adr/index.md")
MKDOCS_CONFIG = Path("architecture/tooling/mkdocs/generated.yml")

ADR_FILES: tuple[Path, ...] = (
    Path("docs/adr/0129-scientist-claim-ledger.md"),
    Path("docs/adr/0130-scientist-research-dag.md"),
    Path("docs/adr/0131-scientist-readiness-ladder.md"),
    Path("docs/adr/0132-scientist-voi-compute-law.md"),
)
REQUIRED_FILES: tuple[Path, ...] = (
    *ADR_FILES,
    REFERENCE_DOC,
    Path("tools/ci/check_scientist_best_in_class_phase2_0.py"),
    Path("tests/unit/scientist/orchestrator_v2/test_compatibility_contracts.py"),
    Path("tests/repo_quality/tools/test_scientist_best_in_class_phase2_0.py"),
)

ADR_REQUIRED_TOKENS: tuple[str, ...] = (
    "## Status",
    "Accepted",
    "## Compatibility",
    "## Rollout",
    "## Rollback",
    "## Related Decisions",
)
REFERENCE_TOKENS: tuple[str, ...] = (
    "Scientist Wave 2 Runtime Contracts",
    "API Migration Notes",
    "claim_ledger_v2_ref",
    "research_dag_replay_ref",
    "voi_report_ref",
    "reissue_packet_ref",
    "legacy_missing",
    "additive/deprecated",
    "DecisionReadinessContract",
)
WAVE2_PHASE_TOKENS: tuple[str, ...] = (
    "Phase 2.0 - Scientist OS foundation",
    "Phase 2.1 - Claim Ledger",
    "Phase 2.2 - Research DAG replay and comparison",
    "Phase 2.3 - VOI scheduler",
    "Phase 2.4 - Reflexive memory and failure intelligence",
    "Phase 2.5 - Adversarial challenge factory",
    "Phase 2.6 - Continuous governance and reissue loop",
    "Phase 2.7 - Decision-grade research compiler",
    "Phase 2.8 - System closeout",
)
PLAN_TOKENS: tuple[str, ...] = (
    "Фаза 2.0 - Scientist OS foundation",
    "closed",
    "0129-scientist-claim-ledger.md",
    "0130-scientist-research-dag.md",
    "0131-scientist-readiness-ladder.md",
    "0132-scientist-voi-compute-law.md",
    "check_scientist_best_in_class_phase2_0.py",
)
READINESS_TOKENS: tuple[str, ...] = (
    "Phase 2.0 - Scientist OS foundation",
    "wave2-runtime-contracts.md",
    "check_scientist_best_in_class_phase2_0.py",
    "closed",
)
INDEX_TOKENS: tuple[str, ...] = (
    "wave2-runtime-contracts.md",
    "Wave 2 runtime contracts",
)
MKDOCS_TOKENS: tuple[str, ...] = ("reference/scientist/wave2-runtime-contracts.md",)

LEGACY_PUBLIC_PACKET_FIELDS: frozenset[str] = frozenset(
    {
        "schema_version",
        "run_id",
        "generated_at",
        "policy_ir",
        "simulation_results",
        "governance",
        "feedback",
        "artifacts",
        "claims_ref",
        "claim_ledger_status",
        "research_dag_ref",
        "research_dag_status",
        "human_review",
        "human_review_validation",
    }
)
WAVE2_ADDITIVE_PACKET_FIELDS: frozenset[str] = LEGACY_PUBLIC_PACKET_FIELDS | frozenset(
    {
        "claim_ledger_v2_ref",
        "claim_ledger_diff_ref",
        "claim_export_ref",
        "blocked_claim_summary_ref",
        "research_dag_replay_ref",
        "research_dag_diff_ref",
        "research_source_invalidation_ref",
        "benchmark_authority_ref",
        "benchmark_scope_ref",
        "hidden_eval_redaction_ref",
        "challenge_pack_rotation_ref",
        "review_assignment_ref",
        "two_person_review_ref",
        "explanation_sufficiency_ref",
        "voi_report_ref",
        "source_voi_ref",
        "human_review_voi_ref",
        "compute_budget_decision_ref",
        "reissue_packet_ref",
        "withdrawal_notice_ref",
        "incident_report_ref",
        "monitor_event_ref",
        "decision_grade_export_ref",
        "public_summary_ref",
        "reviewer_packet_ref",
        "expert_appendix_ref",
        "machine_export_ref",
        "frontend_trust_view",
    }
)
WAVE2_FEATURE_FLAG_DEFAULTS: Mapping[str, str] = {
    "scientist.best_in_class.wave2.phase2_1.claim_ledger_v2": "off",
    "scientist.best_in_class.wave2.phase2_2.research_dag_replay": "off",
    "scientist.best_in_class.wave2.phase2_3.voi_scheduler": "shadow",
    "scientist.best_in_class.wave2.phase2_4.reflexive_memory": "shadow",
    "scientist.best_in_class.wave2.phase2_5.challenge_factory": "shadow",
    "scientist.best_in_class.wave2.phase2_6.continuous_governance_reissue": "off",
    "scientist.best_in_class.wave2.phase2_7.decision_grade_compiler": "off",
    "scientist.best_in_class.wave2.phase2_7.compiler_backed_decision_card": "off",
    "scientist.best_in_class.wave2.phase2_8.wave2_acceptance_gate": "off",
}
ARTIFACT_SCHEMA_VERSION_BASELINES: Mapping[str, str] = {
    "ClaimLedger": "1.0",
    "ResearchDAGArtifact": "1.0",
    "AgentCapabilityPromotionReport": "1.0",
    "BenchmarkAuthorityVerdict": "1.0",
    "HumanReviewPacket": "1.0",
    "DecisionGradeExport": "1.0",
}


def validate_additive_packet_fields(proposed_fields: set[str]) -> list[str]:
    """Return removed legacy fields from a proposed Wave 2 packet shape."""

    return sorted(LEGACY_PUBLIC_PACKET_FIELDS - proposed_fields)


def validate_wave2_flag_defaults(defaults: Mapping[str, object]) -> list[str]:
    """Return feature flags that are unsafe for Phase 2.0 production defaults."""

    unsafe: list[str] = []
    for flag, value in defaults.items():
        token = str(value).strip().lower()
        if token not in {"off", "shadow"}:
            unsafe.append(f"wave2_flag_default_not_safe:{flag}:{token}")
    return unsafe


def validate_schema_versions(proposed_versions: Mapping[str, str]) -> list[str]:
    """Return schema versions that regress below the accepted Phase 2.0 baseline."""

    notes: list[str] = []
    for artifact_name, baseline in ARTIFACT_SCHEMA_VERSION_BASELINES.items():
        proposed = proposed_versions.get(artifact_name)
        if proposed is None:
            notes.append(f"missing_schema_version:{artifact_name}")
            continue
        if _version_tuple(proposed) < _version_tuple(baseline):
            notes.append(f"schema_version_regression:{artifact_name}:{proposed}<{baseline}")
    return notes


def validate_adr_compatibility_text(
    adr_text: str,
    *,
    adr_label: str = "proposed_adr",
) -> list[str]:
    """Return compatibility issues from a proposed Scientist Wave 2 ADR."""

    notes: list[str] = []
    if "## Compatibility" not in adr_text:
        notes.append(f"adr_missing_compatibility_section:{adr_label}")
    if "## Rollout" not in adr_text:
        notes.append(f"adr_missing_rollout_section:{adr_label}")
    if "## Rollback" not in adr_text:
        notes.append(f"adr_missing_rollback_section:{adr_label}")
    if "additive" not in adr_text.lower():
        notes.append(f"adr_missing_additive_posture:{adr_label}")

    for field in LEGACY_PUBLIC_PACKET_FIELDS:
        pattern = re.compile(
            rf"\b(remove|rename|delete)\b[^\n.]*`?{re.escape(field)}`?",
            re.IGNORECASE,
        )
        if pattern.search(adr_text):
            notes.append(f"adr_removes_legacy_public_field:{adr_label}:{field}")
    return notes


def _version_tuple(value: str) -> tuple[int, ...]:
    parts: list[int] = []
    for part in value.split("."):
        if not part.isdigit():
            return (-1,)
        parts.append(int(part))
    return tuple(parts)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _contains(path: Path, token: str) -> bool:
    return path.is_file() and token in _read_text(path)


def _run_wave1_gate(repo_root: Path) -> tuple[bool, dict[str, Any], list[str]]:
    try:
        module = importlib.import_module("tools.ci.check_scientist_best_in_class_wave1")
    except Exception as exc:  # pragma: no cover - surfaced in gate payload.
        return (
            False,
            {"passes_all": False},
            [f"wave1_gate_import_failed:{exc.__class__.__name__}:{exc}"],
        )

    with TemporaryDirectory() as tmp:
        output_path = Path(tmp) / "wave1.json"
        try:
            exit_code = module.main(
                [
                    "--repo-root",
                    str(repo_root),
                    "--output",
                    str(output_path),
                    "--output-format",
                    "json",
                    "--require-passing",
                ]
            )
            payload = json.loads(output_path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - surfaced in gate payload.
            return (
                False,
                {"passes_all": False},
                [f"wave1_gate_run_failed:{exc.__class__.__name__}:{exc}"],
            )
    notes: list[str] = []
    if exit_code != 0 or payload.get("passes_all") is not True:
        notes.append("wave1_gate_failed")
        notes.extend(f"wave1:{note}" for note in payload.get("notes", []))
    return not notes, payload, notes


def _import_and_validate(repo_root: Path) -> tuple[bool, list[str]]:
    src_path = str(repo_root / "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    notes: list[str] = []
    try:
        from polisyos.core.artifacts.ids import ArtifactID
        from polisyos.core.artifacts.manifest import ArtifactRef
        from polisyos.scientist.claims.validators import legacy_claim_ledger_status
        from polisyos.scientist.orchestration.orchestrator.decision_card import DecisionCard
        from polisyos.scientist.methods.research_dag.replay import legacy_research_dag_status
    except Exception as exc:  # pragma: no cover - surfaced in gate payload.
        return False, [f"phase2_0_import_failed:{exc.__class__.__name__}:{exc}"]

    legacy_packet = {
        "schema_version": "3.4",
        "run_id": "legacy_phase2_0_packet",
        "generated_at": "2026-04-28T00:00:00+00:00",
        "policy_ir": {"policy_spec": {"interventions": [{"kind": "legacy"}]}},
        "simulation_results": {"jobs_delta": 10.0},
        "governance": {"verdict": "APPROVE", "issues": []},
        "artifacts": {},
    }
    try:
        card = DecisionCard.from_packet(legacy_packet)
    except Exception as exc:  # pragma: no cover - surfaced in gate payload.
        notes.append(f"legacy_packet_load_failed:{exc.__class__.__name__}:{exc}")
    else:
        if card.run_id != "legacy_phase2_0_packet":
            notes.append("legacy_packet_run_id_not_preserved")

    if legacy_claim_ledger_status(None) != "legacy_missing":
        notes.append("legacy_claim_ledger_status_not_legacy_missing")
    if legacy_research_dag_status(None) != "legacy_missing":
        notes.append("legacy_research_dag_status_not_legacy_missing")

    artifact_id = ArtifactID.model_validate("sha256:" + hashlib.sha256(b"phase2_0").hexdigest())
    ref = ArtifactRef(
        artifact_id=artifact_id,
        kind="scientist.phase2_0.fixture",
        media_type="application/json",
    )
    if str(ref.artifact_id) != str(artifact_id):
        notes.append("artifact_ref_fixture_failed")

    removed = validate_additive_packet_fields(set(WAVE2_ADDITIVE_PACKET_FIELDS))
    notes.extend(f"unexpected_removed_public_field:{field}" for field in removed)

    unsafe_defaults = validate_wave2_flag_defaults(WAVE2_FEATURE_FLAG_DEFAULTS)
    notes.extend(unsafe_defaults)

    schema_notes = validate_schema_versions(dict(ARTIFACT_SCHEMA_VERSION_BASELINES))
    notes.extend(schema_notes)

    return not notes, notes


def _doc_tokens_missing(
    repo_root: Path, path: Path, tokens: tuple[str, ...], prefix: str
) -> list[str]:
    absolute = repo_root / path
    return [f"{prefix}:{token}" for token in tokens if not _contains(absolute, token)]


def _build_payload(repo_root: Path) -> dict[str, Any]:
    notes: list[str] = []
    missing_files = [str(path) for path in REQUIRED_FILES if not (repo_root / path).is_file()]
    notes.extend(f"missing_file:{path}" for path in missing_files)

    wave1_ok, wave1_payload, wave1_notes = _run_wave1_gate(repo_root)
    notes.extend(wave1_notes)

    import_ok, import_notes = _import_and_validate(repo_root)
    notes.extend(import_notes)

    missing_adr_tokens: list[str] = []
    adr_compatibility_notes: list[str] = []
    for adr_path in ADR_FILES:
        missing_adr_tokens.extend(
            _doc_tokens_missing(
                repo_root,
                adr_path,
                ADR_REQUIRED_TOKENS,
                f"missing_adr_token:{adr_path}",
            )
        )
        absolute = repo_root / adr_path
        if absolute.is_file():
            adr_compatibility_notes.extend(
                validate_adr_compatibility_text(
                    _read_text(absolute),
                    adr_label=str(adr_path),
                )
            )
    notes.extend(missing_adr_tokens)
    notes.extend(adr_compatibility_notes)

    missing_reference_tokens = _doc_tokens_missing(
        repo_root,
        REFERENCE_DOC,
        REFERENCE_TOKENS,
        "missing_reference_token",
    )
    notes.extend(missing_reference_tokens)

    missing_reference_phase_tokens = _doc_tokens_missing(
        repo_root,
        REFERENCE_DOC,
        WAVE2_PHASE_TOKENS,
        "missing_reference_phase_token",
    )
    notes.extend(missing_reference_phase_tokens)

    missing_plan_tokens = _doc_tokens_missing(
        repo_root,
        ACTIVE_PLAN_DOC,
        PLAN_TOKENS,
        "missing_active_plan_token",
    )
    notes.extend(missing_plan_tokens)

    missing_readiness_tokens = _doc_tokens_missing(
        repo_root,
        READINESS_DOC,
        (*READINESS_TOKENS, *WAVE2_PHASE_TOKENS),
        "missing_readiness_token",
    )
    notes.extend(missing_readiness_tokens)

    missing_inventory_tokens = _doc_tokens_missing(
        repo_root,
        INVENTORY_DOC,
        ("wave2-runtime-contracts.md", "check_scientist_best_in_class_phase2_0.py"),
        "missing_inventory_token",
    )
    notes.extend(missing_inventory_tokens)

    missing_scientist_index_tokens = _doc_tokens_missing(
        repo_root,
        SCIENTIST_INDEX_DOC,
        INDEX_TOKENS,
        "missing_scientist_index_token",
    )
    notes.extend(missing_scientist_index_tokens)

    missing_adr_index_tokens = _doc_tokens_missing(
        repo_root,
        ADR_INDEX_DOC,
        (
            "0129-scientist-claim-ledger.md",
            "0130-scientist-research-dag.md",
            "0131-scientist-readiness-ladder.md",
            "0132-scientist-voi-compute-law.md",
        ),
        "missing_adr_index_token",
    )
    notes.extend(missing_adr_index_tokens)

    missing_mkdocs_tokens = _doc_tokens_missing(
        repo_root,
        MKDOCS_CONFIG,
        MKDOCS_TOKENS,
        "missing_mkdocs_token",
    )
    notes.extend(missing_mkdocs_tokens)

    category_results = {
        "deliverables_exist": not missing_files,
        "wave1_gate_green": wave1_ok,
        "compatibility_contracts_validate": import_ok,
        "adrs_complete": not missing_adr_tokens and not adr_compatibility_notes,
        "reference_contract_complete": not missing_reference_tokens
        and not missing_reference_phase_tokens,
        "active_plan_updated": not missing_plan_tokens,
        "readiness_doc_updated": not missing_readiness_tokens,
        "inventory_doc_updated": not missing_inventory_tokens,
        "scientist_index_updated": not missing_scientist_index_tokens,
        "adr_index_updated": not missing_adr_index_tokens,
        "mkdocs_nav_updated": not missing_mkdocs_tokens,
    }
    return {
        "assessment_id": ASSESSMENT_ID,
        "passes_all": all(category_results.values()),
        "category_results": category_results,
        "wave1_gate_report": wave1_payload,
        "wave2_feature_flag_defaults": dict(WAVE2_FEATURE_FLAG_DEFAULTS),
        "schema_version_baselines": dict(ARTIFACT_SCHEMA_VERSION_BASELINES),
        "notes": notes,
    }


def _result(payload: dict[str, Any]) -> ToolResult:
    status = "ok" if payload.get("passes_all") else "failed"
    notes = payload.get("notes")
    note_list = list(notes) if isinstance(notes, list) else []
    return ToolResult(
        tool=TOOL_NAME,
        status=status,
        summary=(
            "Scientist best-in-class Phase 2.0 is accepted"
            if status == "ok"
            else "Scientist best-in-class Phase 2.0 is incomplete"
        ),
        exit_code=0 if status == "ok" else 1,
        messages=tuple(
            ToolMessage(
                level="error" if status == "failed" else "info",
                message=str(note),
                rule_id="SCIENTIST_BEST_IN_CLASS_PHASE2_0",
            )
            for note in note_list
        ),
        data=payload,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    parser.add_argument("--output-format", choices=("json", "text"), default="text")
    parser.add_argument("--require-passing", action="store_true")
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    payload = _build_payload(repo_root)
    result = _result(payload)
    rendered = (
        json.dumps(payload, indent=2, sort_keys=True)
        if args.output_format == "json"
        else format_tool_result(result)
    )
    if args.output is not None:
        atomic_write_text(args.output, rendered + "\n")
    else:
        print(rendered)
    return 0 if result.exit_code == 0 or not args.require_passing else result.exit_code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
