#!/usr/bin/env python3
"""Validate Scientist best-in-class Phase 2.5 adversarial challenge factory."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from tools.lib.fs import atomic_write_text
from tools.lib.output import ToolMessage, ToolResult, format_tool_result

ASSESSMENT_ID = "scientist_best_in_class_phase2_5"
TOOL_NAME = "ci.check-scientist-best-in-class-phase2-5"

REFERENCE_DOC = Path("docs/reference/scientist/adversarial-challenge-factory.md")
ACTIVE_PLAN_DOC = Path("docs/plans/active/SCIENTIST_BEST_IN_CLASS_PLAN.md")
READINESS_DOC = Path("docs/reference/scientist/best-in-class-readiness.md")
INVENTORY_DOC = Path("docs/reference/scientist/scientist-capability-inventory.md")
SCIENTIST_INDEX_DOC = Path("docs/reference/scientist/index.md")
WAVE2_CONTRACT_DOC = Path("docs/reference/scientist/wave2-runtime-contracts.md")
MKDOCS_CONFIG = Path("architecture/tooling/mkdocs/generated.yml")

REQUIRED_FILES: tuple[Path, ...] = (
    Path("src/polisyos/scientist/evals/challenge_factory.py"),
    Path("src/polisyos/scientist/evals/sentinels.py"),
    Path("src/polisyos/scientist/evals/red_team.py"),
    Path("src/polisyos/scientist/evals/rotation.py"),
    Path("src/polisyos/scientist/evals/challenge_packs.py"),
    Path("src/polisyos/scientist/evals/authority.py"),
    REFERENCE_DOC,
    Path("tools/ci/check_scientist_best_in_class_phase2_5.py"),
    Path("tests/unit/scientist/evals/test_challenge_factory.py"),
    Path("tests/unit/scientist/evals/test_sentinels.py"),
    Path("tests/unit/scientist/evals/test_red_team.py"),
    Path("tests/unit/scientist/evals/test_rotation.py"),
    Path("tests/repo_quality/tools/test_scientist_best_in_class_phase2_5.py"),
)
REFERENCE_TOKENS: tuple[str, ...] = (
    "GeneratedChallenge",
    "ChallengeFactoryReport",
    "ChallengeSeed",
    "near-miss",
    "policy-domain risk",
    "mutate_generated_challenge",
    "review-before-hidden",
    "Benchmark authority",
    "ChallengePackLineage",
    "fresh rotating challenge",
    "hidden answer",
    "canary",
    "source_contradiction",
    "stale_source",
    "forged_citation",
    "missing_transportability_assumption",
    "hidden_confounding_proxy_assumption_trap",
    "fairness_threshold_reversal",
    "legal_exception",
    "policy_gaming_strategic_response",
    "budget_infeasibility",
    "ambiguous_human_review_instruction",
    "scientist.best_in_class.wave2.phase2_5.challenge_factory",
    "scientist.best_in_class.wave2.phase2_5.require_fresh_rotating_challenge",
)
PLAN_TOKENS: tuple[str, ...] = (
    "Фаза 2.5 - Adversarial challenge factory",
    "closed",
    "check_scientist_best_in_class_phase2_5.py",
)
READINESS_TOKENS: tuple[str, ...] = (
    "Phase 2.5 - Adversarial challenge factory",
    "adversarial-challenge-factory.md",
    "check_scientist_best_in_class_phase2_5.py",
    "closed",
)
INDEX_TOKENS: tuple[str, ...] = (
    "adversarial-challenge-factory.md",
    "Adversarial challenge factory",
)
MKDOCS_TOKENS: tuple[str, ...] = ("reference/scientist/adversarial-challenge-factory.md",)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _contains(path: Path, token: str) -> bool:
    return path.is_file() and token in _read_text(path)


def _missing_tokens(repo_root: Path, path: Path, tokens: tuple[str, ...], prefix: str) -> list[str]:
    return [f"{prefix}:{token}" for token in tokens if not _contains(repo_root / path, token)]


def _run_phase2_4_gate(repo_root: Path) -> tuple[bool, dict[str, Any], list[str]]:
    try:
        module = importlib.import_module("tools.ci.check_scientist_best_in_class_phase2_4")
    except Exception as exc:  # pragma: no cover - surfaced in payload.
        return (
            False,
            {"passes_all": False},
            [f"phase2_4_gate_import_failed:{exc.__class__.__name__}:{exc}"],
        )
    with TemporaryDirectory() as tmp:
        output_path = Path(tmp) / "phase2_4.json"
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
                [f"phase2_4_gate_run_failed:{exc.__class__.__name__}:{exc}"],
            )
    notes: list[str] = []
    if exit_code != 0 or payload.get("passes_all") is not True:
        notes.append("phase2_4_gate_failed")
        notes.extend(f"phase2_4:{note}" for note in payload.get("notes", []))
    return not notes, payload, notes


def _import_and_validate(repo_root: Path) -> tuple[bool, list[str]]:
    src_path = str(repo_root / "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    notes: list[str] = []
    try:
        from polisyos.core.artifacts.ids import ArtifactID
        from polisyos.core.artifacts.manifest import ArtifactRef
        from polisyos.scientist.evals.authority import (
            BenchmarkAuthority,
            PromotionEvidenceRequest,
        )
        from polisyos.scientist.evals.challenge_factory import (
            ChallengeClass,
            ChallengeSeed,
            ChallengeSeedKind,
            ChallengeStatus,
            export_public_challenge_factory_report,
            generate_challenge_from_failure_card,
            generate_challenge_from_seed,
            generate_challenge_report_from_failure_cards,
            generate_challenge_report_from_seeds,
            mutate_generated_challenge,
            promote_generated_challenge,
            register_challenge_pack_with_benchmark_registry,
        )
        from polisyos.scientist.evals.challenge_packs import ChallengePack, ChallengePackKind
        from polisyos.scientist.evals.red_team import (
            default_red_team_scenario_registry,
            red_team_registry_missing_classes,
        )
        from polisyos.scientist.evals.rotation import (
            RotatingChallengePackStatus,
            build_challenge_pack_lineage,
            dedupe_challenge_lineage,
            validate_fresh_rotating_challenge_evidence,
        )
        from polisyos.scientist.evals.sentinels import SentinelChallengeCase, SentinelChallengeKind
        from polisyos.scientist.methods.search.benchmark_registry import BenchmarkRegistry
        from polisyos.scientist.methods.search.failure_cards import FailureSeverity, TypedFailureCard
    except Exception as exc:  # pragma: no cover - surfaced in payload.
        return False, [f"phase2_5_import_failed:{exc.__class__.__name__}:{exc}"]

    def _ref(seed: str, *, kind: str = "scientist.challenge_case") -> ArtifactRef:
        import hashlib

        return ArtifactRef(
            artifact_id=ArtifactID.model_validate(
                "sha256:" + hashlib.sha256(seed.encode("utf-8")).hexdigest()
            ),
            kind=kind,
            media_type="application/json",
        )

    failure_card = TypedFailureCard(
        judge_name="citation_faithfulness",
        failure_type="forged_citation",
        severity=FailureSeverity.BLOCKER,
        description="The output used a forged citation.",
        remediation_hint="Add a forged-citation adversarial challenge.",
        evidence_ref=_ref("failure", kind="scientist.failure_card"),
    )
    challenge = generate_challenge_from_failure_card(
        failure_card,
        run_id="run_phase2_5",
        prompt_or_case_ref=_ref("case"),
    )
    if challenge.status is not ChallengeStatus.REVIEW_REQUIRED:
        notes.append("generated_challenge_not_review_required")
    if challenge.challenge_class != ChallengeClass.FORGED_CITATION.value:
        notes.append("failure_card_challenge_class_mapping_failed")
    report = generate_challenge_report_from_failure_cards(
        run_id="run_phase2_5",
        failure_cards=[failure_card],
        prompt_or_case_refs=[_ref("case")],
    )
    if len(report.generated) != 1:
        notes.append("failure_card_report_generation_failed")
    near_miss_seed = ChallengeSeed(
        seed_id="near_miss_fixture",
        seed_kind=ChallengeSeedKind.NEAR_MISS,
        challenge_class=ChallengeClass.FORGED_CITATION,
        prompt_or_case_ref=_ref("near-miss-case"),
        expected_failure_mode="Near miss should become a reviewable challenge.",
        summary="Citation nearly passed but failed support.",
    )
    risk_seed = ChallengeSeed(
        seed_id="policy_risk_fixture",
        seed_kind=ChallengeSeedKind.POLICY_DOMAIN_RISK,
        challenge_class=ChallengeClass.BUDGET_INFEASIBILITY,
        prompt_or_case_ref=_ref("policy-risk-case"),
        expected_failure_mode="Budget infeasibility should be challenged.",
        summary="Policy-domain budget risk.",
    )
    seeded_report = generate_challenge_report_from_seeds(
        run_id="run_phase2_5",
        seeds=[near_miss_seed, risk_seed],
    )
    if len(seeded_report.generated) != 2:
        notes.append("near_miss_policy_risk_seed_generation_failed")
    try:
        promote_generated_challenge(challenge, status=ChallengeStatus.APPROVED_FOR_HIDDEN)
    except ValueError:
        pass
    else:
        notes.append("unreviewed_hidden_promotion_not_blocked")

    reviewer_ref = _ref("review", kind="scientist.human_review_decision")
    reviewed = promote_generated_challenge(
        challenge,
        status=ChallengeStatus.APPROVED_FOR_HIDDEN,
        reviewer_refs=[reviewer_ref],
    )
    mutated = mutate_generated_challenge(
        reviewed,
        mutation_strategy="contradict_supporting_source",
    )
    if mutated.status is not ChallengeStatus.REVIEW_REQUIRED or mutated.reviewer_refs:
        notes.append("mutated_challenge_did_not_reset_review_state")
    with TemporaryDirectory() as tmp:
        registry = BenchmarkRegistry(Path(tmp) / "benchmarks")
        try:
            register_challenge_pack_with_benchmark_registry(
                registry,
                split_type="hidden_holdout",
                pack_ref=_ref("hidden-pack", kind="scientist.benchmark_pack"),
                challenges=[challenge],
                family="policy_design",
                loop_id="loop-a",
            )
        except ValueError:
            pass
        else:
            notes.append("unreviewed_hidden_registration_not_blocked")
        registry.record("selection", _ref("selection"), family="policy_design", loop_id="loop-a")
        register_challenge_pack_with_benchmark_registry(
            registry,
            split_type="hidden_holdout",
            pack_ref=_ref("hidden-pack", kind="scientist.benchmark_pack"),
            challenges=[reviewed],
            family="policy_design",
            loop_id="loop-a",
            suite_id="hidden-v1",
        )
        private_challenge = promote_generated_challenge(
            generate_challenge_from_seed(
                risk_seed.model_copy(update={"private_data": True}),
                run_id="run_phase2_5",
                target_visibility="private",
            ),
            status=ChallengeStatus.APPROVED_FOR_PRIVATE,
            reviewer_refs=[reviewer_ref],
        )
        try:
            register_challenge_pack_with_benchmark_registry(
                registry,
                split_type="private",
                pack_ref=_ref("private-pack", kind="scientist.benchmark_pack"),
                challenges=[private_challenge],
                family="policy_design",
                loop_id="loop-a",
                suite_id="private-v1",
            )
        except ValueError:
            notes.append("reviewed_private_pack_registration_blocked")
        rotating = promote_generated_challenge(
            challenge,
            status=ChallengeStatus.APPROVED_FOR_PRIVATE,
            reviewer_refs=[reviewer_ref],
        )
        register_challenge_pack_with_benchmark_registry(
            registry,
            split_type="rotating_challenge",
            pack_ref=_ref("rotating-pack", kind="scientist.benchmark_pack"),
            challenges=[rotating],
            family="policy_design",
            loop_id="loop-a",
            suite_id="rotating-v1",
        )
        verdict = BenchmarkAuthority(registry).verdict(
            PromotionEvidenceRequest(
                family="policy_design",
                claim_mode="estimation",
                loop_id="loop-a",
                near_frontier=True,
            )
        )
        if not verdict.default_enable_allowed:
            notes.append("fresh_rotating_challenge_authority_fixture_blocked")
        if not verdict.challenge_pack_lineage:
            notes.append("authority_lineage_fixture_missing")
        public_payload = verdict.public_export()
        if not public_payload.get("challenge_pack_lineage"):
            notes.append("authority_public_export_missing_lineage")

    pack = ChallengePack(
        pack_id="rotating-v1",
        kind=ChallengePackKind.ROTATING,
        artifact_ref=_ref("rotating-pack", kind="scientist.benchmark_pack"),
        created_at=datetime.now(UTC) - timedelta(days=45),
        rotation_days=30,
    )
    lineage = build_challenge_pack_lineage(
        pack,
        [reviewed],
        status=RotatingChallengePackStatus.ACTIVE,
    )
    blockers = validate_fresh_rotating_challenge_evidence([lineage], near_frontier=True)
    if not blockers or not blockers[0].startswith("rotating_challenge_expired:"):
        notes.append("expired_rotation_fixture_not_blocked")
    if len(dedupe_challenge_lineage([lineage, lineage])) != 1:
        notes.append("duplicate_lineage_not_deduped")

    canary_report = report.model_copy(
        update={
            "generated": [
                challenge.model_copy(update={"expected_failure_mode": "contains HIDDEN_CANARY"})
            ]
        }
    )
    try:
        export_public_challenge_factory_report(
            canary_report,
            canary_tokens={"HIDDEN_CANARY"},
        )
    except ValueError:
        pass
    else:
        notes.append("challenge_public_export_canary_not_blocked")

    private_failure = failure_card.model_copy(update={"metadata": {"private_data": True}})
    public_report = generate_challenge_report_from_failure_cards(
        run_id="run_phase2_5",
        failure_cards=[private_failure],
        prompt_or_case_refs=[_ref("case")],
        target_visibility="public",
    )
    if not public_report.rejected_reasons:
        notes.append("private_failure_public_challenge_not_rejected")
    try:
        SentinelChallengeCase(
            sentinel_id="sentinel-a",
            kind=SentinelChallengeKind.CANARY,
            challenge_ref=_ref("sentinel"),
            expected_detection="Detect canary.",
            admission_status=ChallengeStatus.APPROVED_FOR_HIDDEN,
        )
    except ValueError:
        pass
    else:
        notes.append("unreviewed_hidden_sentinel_not_blocked")
    if red_team_registry_missing_classes(default_red_team_scenario_registry()):
        notes.append("red_team_registry_missing_required_classes")
    return not notes, notes


def _build_payload(repo_root: Path) -> dict[str, Any]:
    notes: list[str] = []
    missing_files = [str(path) for path in REQUIRED_FILES if not (repo_root / path).is_file()]
    notes.extend(f"missing_file:{path}" for path in missing_files)

    phase2_4_ok, phase2_4_payload, phase2_4_notes = _run_phase2_4_gate(repo_root)
    notes.extend(phase2_4_notes)
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
        ("adversarial-challenge-factory.md", "check_scientist_best_in_class_phase2_5.py"),
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
        ("Phase 2.5 - Adversarial challenge factory", "closed"),
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
        "phase2_4_gate_green": phase2_4_ok,
        "challenge_factory_contracts_validate": import_ok,
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
        "phase2_4_gate_report": phase2_4_payload,
        "notes": notes,
    }


def _result(payload: dict[str, Any]) -> ToolResult:
    status = "ok" if payload.get("passes_all") else "failed"
    note_list = list(payload.get("notes", []))
    return ToolResult(
        tool=TOOL_NAME,
        status=status,
        summary=(
            "Scientist best-in-class Phase 2.5 is accepted"
            if status == "ok"
            else "Scientist best-in-class Phase 2.5 is incomplete"
        ),
        exit_code=0 if status == "ok" else 1,
        messages=tuple(
            ToolMessage(
                level="error" if status == "failed" else "info",
                message=str(note),
                rule_id="SCIENTIST_BEST_IN_CLASS_PHASE2_5",
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
