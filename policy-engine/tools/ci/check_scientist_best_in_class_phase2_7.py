#!/usr/bin/env python3
"""Validate Scientist best-in-class Phase 2.7 decision-grade compiler."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from tools.lib.fs import atomic_write_text
from tools.lib.output import ToolMessage, ToolResult, format_tool_result

ASSESSMENT_ID = "scientist_best_in_class_phase2_7"
TOOL_NAME = "ci.check-scientist-best-in-class-phase2-7"

REFERENCE_DOC = Path("docs/reference/scientist/decision-grade-compiler.md")
ACTIVE_PLAN_DOC = Path("docs/plans/active/SCIENTIST_BEST_IN_CLASS_PLAN.md")
READINESS_DOC = Path("docs/reference/scientist/best-in-class-readiness.md")
INVENTORY_DOC = Path("docs/reference/scientist/scientist-capability-inventory.md")
SCIENTIST_INDEX_DOC = Path("docs/reference/scientist/index.md")
WAVE2_CONTRACT_DOC = Path("docs/reference/scientist/wave2-runtime-contracts.md")
MKDOCS_CONFIG = Path("architecture/tooling/mkdocs/generated.yml")

REQUIRED_FILES: tuple[Path, ...] = (
    Path("src/polisyos/scientist/publishing/publisher.py"),
    Path("src/polisyos/scientist/orchestration/orchestrator/decision_card.py"),
    Path("src/polisyos/scientist/evidence/claims/export.py"),
    REFERENCE_DOC,
    Path("tools/ci/check_scientist_best_in_class_phase2_7.py"),
    Path("tests/unit/scientist/orchestration/orchestrator/test_decision_grade_compiler.py"),
    Path("tests/repo_quality/tools/test_scientist_best_in_class_phase2_7.py"),
)
REFERENCE_TOKENS: tuple[str, ...] = (
    "DecisionGradeExport",
    "OutputAudience",
    "OutputOmissionRecord",
    "persist_decision_grade_export",
    "load_decision_grade_export",
    "scientist.decision_grade_export",
    "public summary",
    "reviewer packet",
    "expert appendix",
    "machine export",
    "omissions",
    "trust_provenance",
    "claims_ref",
    "research_dag_ref",
    "hidden benchmark",
    "scientist.best_in_class.wave2.phase2_7.decision_grade_compiler",
    "scientist.best_in_class.wave2.phase2_7.compiler_backed_decision_card",
)
PLAN_TOKENS: tuple[str, ...] = (
    "Фаза 2.7 - Decision-grade research compiler",
    "closed",
    "check_scientist_best_in_class_phase2_7.py",
)
READINESS_TOKENS: tuple[str, ...] = (
    "Phase 2.7 - Decision-grade research compiler",
    "decision-grade-compiler.md",
    "decision_grade_compiler",
    "check_scientist_best_in_class_phase2_7.py",
    "closed",
)
INDEX_TOKENS: tuple[str, ...] = (
    "decision-grade-compiler.md",
    "Decision-grade research compiler",
)
WAVE2_TOKENS: tuple[str, ...] = (
    "Phase 2.7 - Decision-grade research compiler",
    "closed",
    "decision_grade_compiler",
    "check_scientist_best_in_class_phase2_7.py",
)
MKDOCS_TOKENS: tuple[str, ...] = ("reference/scientist/decision-grade-compiler.md",)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _contains(path: Path, token: str) -> bool:
    return path.is_file() and token in _read_text(path)


def _missing_tokens(repo_root: Path, path: Path, tokens: tuple[str, ...], prefix: str) -> list[str]:
    return [f"{prefix}:{token}" for token in tokens if not _contains(repo_root / path, token)]


def _run_phase2_6_gate(repo_root: Path) -> tuple[bool, dict[str, Any], list[str]]:
    try:
        module = importlib.import_module("tools.ci.check_scientist_best_in_class_phase2_6")
    except Exception as exc:  # pragma: no cover - surfaced in payload.
        return (
            False,
            {"passes_all": False},
            [f"phase2_6_gate_import_failed:{exc.__class__.__name__}:{exc}"],
        )
    with TemporaryDirectory() as tmp:
        output_path = Path(tmp) / "phase2_6.json"
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
        except Exception as exc:  # pragma: no cover - surfaced in payload.
            return (
                False,
                {"passes_all": False},
                [f"phase2_6_gate_run_failed:{exc.__class__.__name__}:{exc}"],
            )
    notes: list[str] = []
    if exit_code != 0 or payload.get("passes_all") is not True:
        notes.append("phase2_6_gate_failed")
        notes.extend(f"phase2_6:{note}" for note in payload.get("notes", []))
    return not notes, payload, notes


def _import_and_validate(repo_root: Path) -> tuple[bool, list[str]]:
    src_path = str(repo_root / "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    notes: list[str] = []
    try:
        from pydantic import ValidationError

        from polisyos.core.artifacts.ids import ArtifactID
        from polisyos.core.artifacts.manifest import ArtifactRef
        from polisyos.core.artifacts.store import FileSystemCAS
        from polisyos.core.contracts.c4_persisted_profiles import c4_semantic_digest
        from polisyos.scientist.evidence.claims.export import (
            ClaimExportAudience,
            _format_resolved_claim_ledger,
        )
        from polisyos.scientist.evidence.claims.head_index import (
            CLAIM_LEDGER_AUTHORITY_PURPOSE,
            ClaimBridgePendingProjection,
            ClaimLedgerHeadStatement,
            ClaimLedgerOwnerKey,
            ClaimLedgerOwnerKeyDerivationInput,
            PersistedClaimLedgerHead,
            derive_claim_ledger_owner_scope_ref,
        )
        from polisyos.scientist.evidence.claims.lifecycle import AppendOnlyClaimLedger
        from polisyos.scientist.evidence.claims.models import (
            ClaimPublishability,
            ClaimRecord,
            ClaimSupportStatus,
            ClaimType,
        )
        from polisyos.scientist.methods.research_dag.models import (
            ResearchDAGArtifact,
            ResearchDAGEdge,
            ResearchDAGNode,
            ResearchEdgeType,
            ResearchNodeType,
        )
        from polisyos.scientist.methods.search.readiness import DecisionReadiness
        from polisyos.scientist.orchestration.orchestrator.decision_card import DecisionCard
        from polisyos.scientist.publishing.publisher import (
            DecisionGradeExport,
            OutputAudience,
            OutputOmissionRecord,
            assert_decision_grade_exports_consistent,
            compile_decision_grade_export,
            compile_decision_grade_exports,
            decision_grade_export_inputs,
            load_decision_grade_export,
            persist_decision_grade_export,
        )
    except Exception as exc:  # pragma: no cover - surfaced in payload.
        return False, [f"phase2_7_import_failed:{exc.__class__.__name__}:{exc}"]

    def _ref(seed: str, *, kind: str = "scientist.test") -> ArtifactRef:
        return ArtifactRef(
            artifact_id=ArtifactID.model_validate(
                "sha256:" + hashlib.sha256(seed.encode("utf-8")).hexdigest()
            ),
            kind=kind,
            media_type="application/json",
        )

    claim_public = ClaimRecord(
        claim_id="claim_public",
        run_id="run_phase2_7",
        claim_type=ClaimType.FACTUAL,
        text="Public claim.",
        support_status=ClaimSupportStatus.SUPPORTED,
        publishability=ClaimPublishability.PUBLISHABLE,
        readiness_level=DecisionReadiness.ANALYST_ADVISORY,
        evidence_refs=[_ref("evidence")],
    )
    claim_blocked = ClaimRecord(
        claim_id="claim_blocked",
        run_id="run_phase2_7",
        claim_type=ClaimType.FACTUAL,
        text="Blocked claim.",
        support_status=ClaimSupportStatus.CONTESTED,
        publishability=ClaimPublishability.BLOCKED,
        readiness_level=DecisionReadiness.RESEARCH_ARTIFACT,
        evidence_refs=[_ref("evidence")],
        counterevidence_refs=[_ref("counter")],
        blocked_reasons=["counterevidence unresolved"],
    )
    ledger = AppendOnlyClaimLedger(
        run_id="run_phase2_7",
        current_claims=[claim_public, claim_blocked],
    )
    dag = ResearchDAGArtifact(
        run_id="run_phase2_7",
        workflow_id="scientist_policy_design",
        created_at=datetime(2026, 4, 28, tzinfo=UTC),
        nodes=[
            ResearchDAGNode(
                node_id="question",
                node_type=ResearchNodeType.QUESTION,
                run_id="run_phase2_7",
                workflow_id="scientist_policy_design",
                producer="planner",
                summary="Normalize question.",
            ),
            ResearchDAGNode(
                node_id="synthesis",
                node_type=ResearchNodeType.SYNTHESIS,
                run_id="run_phase2_7",
                workflow_id="scientist_policy_design",
                producer="compiler",
                summary="Compile claims.",
                claim_ids=["claim_public", "claim_blocked"],
            ),
        ],
        edges=[
            ResearchDAGEdge(
                source_node_id="question",
                target_node_id="synthesis",
                edge_type=ResearchEdgeType.DERIVES,
                claim_ids=["claim_public"],
            )
        ],
    )
    claims_ref = _ref("claims", kind="scientist.claim_ledger_v2")
    dag_ref = _ref("dag", kind="scientist.research_dag")

    derivation = ClaimLedgerOwnerKeyDerivationInput(
        base_claims_ref=claims_ref,
        base_claims_content_hash=str(claims_ref.artifact_id),
        requested_authority_purpose=CLAIM_LEDGER_AUTHORITY_PURPOSE,
    )
    claim_owner_key = ClaimLedgerOwnerKey(
        scope_ref=derive_claim_ledger_owner_scope_ref(derivation),
        claim_owner_ref="phase2-7-fixture-owner",
        authority_purpose=CLAIM_LEDGER_AUTHORITY_PURPOSE,
        derivation_input=derivation,
    )
    head_statement = ClaimLedgerHeadStatement(
        root_identity=str(_ref("root-identity").artifact_id),
        root_receipt_ref=_ref("root", kind="scientist.claims.ledger_root"),
        root_receipt_content_hash=str(_ref("root-content").artifact_id),
        owner_key=claim_owner_key,
        ledger_artifact_ref=claims_ref,
        ledger_raw_cas_hash=str(claims_ref.artifact_id),
        generation=0,
        predecessor_head_ref=None,
        bridge_result_refs=(),
        issuance_verifier_receipt_ref=_ref(
            "issuance-verifier",
            kind="scientist.claims.ledger_root_verification",
        ),
        issuance_verifier_receipt_content_hash=str(_ref("issuance-verifier-content").artifact_id),
    )

    class _FixtureClaimOwner:
        def __init__(self) -> None:
            self.head = PersistedClaimLedgerHead(
                head_ref=_ref("head", kind="scientist.claims.ledger_head"),
                head_content_hash=c4_semantic_digest("claim_ledger_head", head_statement),
                statement=head_statement,
            )

        def resolve_current(self, *, owner_key: object) -> object:
            del owner_key
            return self.head

        def export_current(
            self,
            *,
            owner_key: object,
            audience: ClaimExportAudience,
        ) -> object:
            del owner_key
            return _format_resolved_claim_ledger(
                ledger,
                audience=audience,
                pending_projection=ClaimBridgePendingProjection(
                    completed_batch_denominator_established=True,
                ),
            )

    claim_owner = _FixtureClaimOwner()
    exports = compile_decision_grade_exports(
        run_id="run_phase2_7",
        research_dag_ref=dag_ref,
        claim_owner=claim_owner,
        claim_owner_key=claim_owner_key,
        research_dag=dag,
        decision_payload={"policy_summary": "Public claim."},
    )
    if set(exports) != set(OutputAudience):
        notes.append("four_audience_fixtures_missing")
    try:
        assert_decision_grade_exports_consistent(exports.values())
    except ValueError as exc:
        notes.append(f"export_refs_not_consistent:{exc}")
    public_payload = json.dumps(exports[OutputAudience.PUBLIC].model_dump(mode="json"))
    if "hidden_holdout" in public_payload or "private_eval" in public_payload:
        notes.append("public_fixture_contains_hidden_ref")
    if not exports[OutputAudience.PUBLIC].omissions:
        notes.append("public_blocker_omission_reason_missing")
    if not exports[OutputAudience.REVIEWER].payload["blocked_claim_summary"]["blocked_claims"]:
        notes.append("reviewer_fixture_missing_blocked_claims")
    machine_card = DecisionCard.from_decision_grade_export(exports[OutputAudience.MACHINE])
    if machine_card.trust_provenance is None:
        notes.append("decision_card_bridge_missing_trust_fields")
    with TemporaryDirectory() as tmp:
        store = FileSystemCAS(Path(tmp))
        machine_export = exports[OutputAudience.MACHINE]
        inputs = decision_grade_export_inputs(machine_export)
        if [item.role for item in inputs] != ["claims", "research_dag"]:
            notes.append("decision_grade_export_lineage_inputs_missing")
        export_ref = persist_decision_grade_export(
            store,
            machine_export,
            claim_owner=claim_owner,
            claim_owner_key=claim_owner_key,
        )
        if load_decision_grade_export(store, export_ref) != machine_export:
            notes.append("decision_grade_export_cas_roundtrip_failed")

    try:
        compile_decision_grade_export(
            run_id="wrong_run",
            audience=OutputAudience.MACHINE,
            research_dag_ref=dag_ref,
            claim_owner=claim_owner,
            claim_owner_key=claim_owner_key,
            research_dag=dag,
        )
    except ValueError:
        pass
    else:
        notes.append("mismatched_compiler_source_run_not_blocked")

    try:
        OutputOmissionRecord(
            field_path="blocked_claim_summary.blocked_claims",
            audience=OutputAudience.PUBLIC,
            reason=" ",
        )
    except ValidationError:
        pass
    else:
        notes.append("blank_omission_reason_not_blocked")

    silent_blocker = exports[OutputAudience.PUBLIC].model_dump(mode="json")
    silent_blocker["omissions"] = []
    try:
        DecisionGradeExport.model_validate(silent_blocker)
    except ValidationError:
        pass
    else:
        notes.append("silent_blocker_omission_not_blocked")
    unrelated_omission = {
        **silent_blocker,
        "omissions": [
            OutputOmissionRecord(
                field_path="claim_ledger_export.claims[claim_draft]",
                audience=OutputAudience.PUBLIC,
                reason="draft claim hidden from public audience",
            ).model_dump(mode="json")
        ],
    }
    try:
        DecisionGradeExport.model_validate(unrelated_omission)
    except ValidationError:
        pass
    else:
        notes.append("non_blocker_omission_satisfied_blocker_rule")
    return not notes, notes


def _build_payload(repo_root: Path) -> dict[str, Any]:
    notes: list[str] = []
    missing_files = [str(path) for path in REQUIRED_FILES if not (repo_root / path).is_file()]
    notes.extend(f"missing_file:{path}" for path in missing_files)

    phase2_6_ok, phase2_6_payload, phase2_6_notes = _run_phase2_6_gate(repo_root)
    notes.extend(phase2_6_notes)
    import_ok, import_notes = _import_and_validate(repo_root)
    notes.extend(import_notes)

    missing_reference_tokens = _missing_tokens(
        repo_root,
        REFERENCE_DOC,
        REFERENCE_TOKENS,
        "missing_reference_token",
    )
    notes.extend(missing_reference_tokens)
    missing_plan_tokens = _missing_tokens(
        repo_root,
        ACTIVE_PLAN_DOC,
        PLAN_TOKENS,
        "missing_active_plan_token",
    )
    notes.extend(missing_plan_tokens)
    missing_readiness_tokens = _missing_tokens(
        repo_root,
        READINESS_DOC,
        READINESS_TOKENS,
        "missing_readiness_token",
    )
    notes.extend(missing_readiness_tokens)
    missing_inventory_tokens = _missing_tokens(
        repo_root,
        INVENTORY_DOC,
        ("decision-grade-compiler.md", "check_scientist_best_in_class_phase2_7.py"),
        "missing_inventory_token",
    )
    notes.extend(missing_inventory_tokens)
    missing_index_tokens = _missing_tokens(
        repo_root,
        SCIENTIST_INDEX_DOC,
        INDEX_TOKENS,
        "missing_scientist_index_token",
    )
    notes.extend(missing_index_tokens)
    missing_wave2_tokens = _missing_tokens(
        repo_root,
        WAVE2_CONTRACT_DOC,
        WAVE2_TOKENS,
        "missing_wave2_contract_token",
    )
    notes.extend(missing_wave2_tokens)
    missing_mkdocs_tokens = _missing_tokens(
        repo_root,
        MKDOCS_CONFIG,
        MKDOCS_TOKENS,
        "missing_mkdocs_token",
    )
    notes.extend(missing_mkdocs_tokens)

    category_results = {
        "deliverables_exist": not missing_files,
        "phase2_6_gate_green": phase2_6_ok,
        "decision_grade_compiler_contracts_validate": import_ok,
        "reference_doc_complete": not missing_reference_tokens,
        "active_plan_updated": not missing_plan_tokens,
        "readiness_doc_updated": not missing_readiness_tokens,
        "inventory_doc_updated": not missing_inventory_tokens,
        "scientist_index_updated": not missing_index_tokens,
        "wave2_contract_updated": not missing_wave2_tokens,
        "mkdocs_nav_updated": not missing_mkdocs_tokens,
    }
    return {
        "assessment_id": ASSESSMENT_ID,
        "passes_all": all(category_results.values()),
        "category_results": category_results,
        "phase2_6_gate_report": phase2_6_payload,
        "notes": notes,
    }


def _result(payload: dict[str, Any]) -> ToolResult:
    status = "ok" if payload.get("passes_all") else "failed"
    note_list = list(payload.get("notes", []))
    return ToolResult(
        tool=TOOL_NAME,
        status=status,
        summary=(
            "Scientist best-in-class Phase 2.7 is accepted"
            if status == "ok"
            else "Scientist best-in-class Phase 2.7 is incomplete"
        ),
        exit_code=0 if status == "ok" else 1,
        messages=tuple(
            ToolMessage(
                level="error" if status == "failed" else "info",
                message=str(note),
                rule_id="SCIENTIST_BEST_IN_CLASS_PHASE2_7",
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
