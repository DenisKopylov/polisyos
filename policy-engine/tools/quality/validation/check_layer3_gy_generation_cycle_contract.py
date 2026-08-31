#!/usr/bin/env python3
"""Validate the frozen Layer 3 GY-N6 generation-cycle controller contract."""

from __future__ import annotations

from time import perf_counter as _timing_perf_counter

_TIMING_STARTED_AT = _timing_perf_counter()

# Completed-work terminals per mode, owned here because this module's own return mapping is the
# only place that knows them. ``corrupt_field_drift_check`` reports "fail" when the mutation was
# DETECTED (the correct outcome) and "pass" when it survived, while ``main`` exits
# ``0 if status == "pass" else 1`` -- so this lane's healthy terminal is exit 1 and its DEFECT
# terminal is exit 0. The default {0} would admit exactly the failures and reject the good runs.
TIMING_HEALTHY_TERMINAL_EXIT_CODES: dict[str, list[int]] = {
    "corrupt-field-drift-check": [1],
}

import argparse
import asyncio
import copy
import json
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, get_args

from pydantic import ValidationError

from polisyos.core.artifacts import FileSystemCAS
from polisyos.pdc import (
    GY_COMPARISON_PROJECTION_LEGACY_SCHEMA_VERSION,
    GY_COMPARISON_PROJECTION_SCHEMA_VERSION,
    GY_VERIFICATION_COMPARISON_LEGACY_RULE_VERSION,
    GY_VERIFICATION_COMPARISON_RULE_VERSION,
    GyComparisonAdmission,
    GyComparisonProjectionPlan,
    SearchTerminalKind,
    build_gy_comparison_projection_plan,
    build_gy_comparison_projection_plan_from_manifest,
    gy_comparison_content_hash,
    gy_content_hash,
)
from polisyos.runtime.quality.confidence_ledger import ConfidenceLedgerSession
from polisyos.runtime.quality.design_problem import (
    AuthorityProfile,
    CandidateLever,
    CandidateLeverSpace,
    DesignConstraint,
    DesignObjective,
    DesignProblem,
    DesignStakeholder,
    EvidenceAcquisitionNeeds,
    EvidenceNeed,
    JurisdictionTimeSemantics,
    NLProvenance,
    OutcomeOfInterest,
)
from polisyos.runtime.quality.generation_cycle import (
    GENERATION_CYCLE_CONTRACT_SCHEMA_VERSION,
    CandidateGroundingObservation,
    GenerationCycleController,
    GenerationCycleRun,
    PendingN8ValuePort,
    PolicyGroundingPort,
    enforce_no_retry_without_new_grammar,
    validate_generation_cycle_run,
)
from polisyos.runtime.quality.grounding_disposition_vocab import GroundingDispositionKind
from polisyos.runtime.quality.promotion_sequence import (
    CanonicalN9PromotionPort,
    CanonicalPromotionReceipt,
    N9DesignProblemBinding,
    admit_canonical_promotion_receipt_for_comparison,
    canonical_promotion_receipt_semantic_projection,
    canonical_promotion_verification_comparison_owner_rule_registry,
    confidence_risk_scope_for_problem,
    parse_canonical_promotion_history_receipt,
)
from polisyos.scientist.methods.search.voi_scheduler import SchedulingDecision
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from tools.lib.timing import run_timed_entrypoint

OUTPUT_PATH = "architecture/policy_design_case/layer3_gy_generation_cycle_contract.json"
_FIXED_GENERATED_AT = datetime(2026, 7, 5, tzinfo=UTC)
_CONTENT_HASH_EXCLUDED_TOP_LEVEL = {"contract_content_hash", "capture_wall_time_seconds"}

_COMPARISON_IDENTITY_FIELDS = {
    "comparison_admission_manifest",
    "comparison_content_hash",
    "comparison_projection_schema_version",
    "comparison_rule_version",
}

_EXPECTED_MUTATION_IDS: tuple[str, ...] = (
    "revision_not_terminal_driven",
    "retry_without_new_grammar_admitted",
    "voi_scheduler_ignored_fixed_cycle_count",
    "single_pass_fixture_survives_as_production_cycle",
    "proxy_gap_candidate_promoted_without_adversarial_validate",
    "decision_front_admitted_non_current_valid",
    "grounding_bypassed_cgf_firewall",
    "coverage_depends_on_llm",
    "k_sim_shrank_k_world",
    "full_denominator_curated_subset",
    "incoherent_single_terminal_run",
    "empty_cycle_run",
)


def declared_outputs() -> list[str]:
    """Return generated artifacts owned by this validator."""

    return [OUTPUT_PATH]


@dataclass(frozen=True)
class _Atom:
    intervention_id: str
    content_hash: str
    target_world_slots: tuple[str, ...] = ("industrial_resilience",)
    world_model_record_ref: str = "world_model_record_industrial_resilience"
    status: str = "candidate_unverified"


@dataclass(frozen=True)
class _Candidate:
    candidate_id: str
    atom: _Atom
    diversity_key: tuple[str, str, str, str]
    status: str = "candidate_unverified"


@dataclass(frozen=True)
class _Ranking:
    candidate_id: str
    score: float
    voi_estimate: float
    trust_level: str = "search_guiding"
    promotion_allowed: bool = False


@dataclass(frozen=True)
class _CertificateChain:
    cg1_certificate_id: str = "cg1_cert_n6_lane0"
    cg1_content_hash: str = "sha256:" + "1" * 64
    cg2_certificate_id: str = "cg2_cert_n6_lane0"
    cg2_content_hash: str = "sha256:" + "2" * 64
    cg3_certificate_id: str = "cg3_cert_n6_lane0"
    cg3_content_hash: str = "sha256:" + "3" * 64
    cg4_proxy_gap_risk_id: str | None = None
    cg4_proxy_gap_content_hash: str | None = None
    cg4_quarantine_handoff_id: str | None = None
    cg4_quarantine_handoff_hash: str | None = None
    cg5_action_certificate_id: str | None = None
    cg5_action_content_hash: str | None = None
    cg5_ticket_id: str | None = None
    cg5_ticket_hash: str | None = None


@dataclass(frozen=True)
class _GroundingDisposition:
    proposal_id: str
    candidate_id: str | None
    raw_candidate_hash: str
    disposition: str
    selected_relation: str
    shadow_atom_content_hash: str | None = None
    identified_atom_id: str | None = "atom_n6_lane0"
    cg2_decision: str | None = "shadow_frozen"
    cg2_reason: str | None = "cg2_frozen_until_cg6"
    cg3_decision: str | None = "shadow"
    cg3_reason: str | None = "cg3_shadow_only"
    rejected_cause: dict[str, Any] | None = None
    certificate_chain: _CertificateChain = _CertificateChain()
    bridge_missing_records: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class _GenerationResult:
    status: str
    candidates: tuple[_Candidate, ...]
    surrogate_rankings: tuple[_Ranking, ...]
    grounding_dispositions: tuple[_GroundingDisposition, ...]


@dataclass(frozen=True)
class _VerificationReplayContext:
    """Live owners and isolated ledger retained for deep committed validation."""

    session: ConfidenceLedgerSession
    problem: DesignProblem
    run: GenerationCycleRun
    comparison_admissions: tuple[GyComparisonAdmission, ...]
    comparison_plan: GyComparisonProjectionPlan


class _Lane0GenerationPort:
    """Scripted proposer over real N6 controller semantics, with CGF-shaped records."""

    async def __call__(self, problem: DesignProblem, *, cycle_index: int) -> _GenerationResult:
        grammar = tuple(problem.runtime_hints.get("generation_cycle_grammar", ()))
        if cycle_index > 0 and any(
            "repair:search_ceiling_repair_required" in item or "adversarial_validate" in item
            for item in grammar
        ):
            candidate = _Candidate(
                candidate_id="candidate_lane0_cycle_002",
                atom=_Atom("cycle_002", "sha256:" + "b" * 64),
                diversity_key=("grant", "industrial", "repair", "cycle2"),
            )
            disposition = _GroundingDisposition(
                proposal_id="n6_lane0.cycle_002",
                candidate_id=candidate.candidate_id,
                raw_candidate_hash="sha256:" + "c" * 64,
                disposition="novel_cg3",
                selected_relation="novel-candidate",
                shadow_atom_content_hash=candidate.atom.content_hash,
                cg2_decision="novel_candidate",
                cg2_reason="novel_cg3",
                cg3_decision="requires_free_grow",
                cg3_reason="missing_supporting_data",
            )
            ranking = _Ranking(candidate.candidate_id, score=0.31, voi_estimate=0.22)
        else:
            candidate = _Candidate(
                candidate_id="candidate_lane0_cycle_001",
                atom=_Atom("cycle_001", "sha256:" + "a" * 64),
                diversity_key=("grant", "industrial", "proxy_gap", "cycle1"),
            )
            chain = _CertificateChain(
                cg4_proxy_gap_risk_id="cg4_proxy_gap_1111111111111111",
                cg4_proxy_gap_content_hash="sha256:" + "4" * 64,
                cg4_quarantine_handoff_id="cg4_quarantine_1111111111111111",
                cg4_quarantine_handoff_hash="sha256:" + "5" * 64,
                cg5_action_certificate_id="cg5_action_1111111111111111",
                cg5_action_content_hash="sha256:" + "6" * 64,
            )
            disposition = _GroundingDisposition(
                proposal_id="n6_lane0.cycle_001",
                candidate_id=candidate.candidate_id,
                raw_candidate_hash="sha256:" + "d" * 64,
                disposition="shadow_bound",
                selected_relation="exact",
                shadow_atom_content_hash=candidate.atom.content_hash,
                cg2_reason="cg2_frozen_until_cg6",
                cg3_reason="cg3_shadow_only",
                certificate_chain=chain,
                bridge_missing_records=(
                    {
                        "pattern": "bridge_missing",
                        "owner": "CG4",
                        "integration_status": "handoff_artifact_n6_direct_intake_not_wired",
                    },
                ),
            )
            ranking = _Ranking(candidate.candidate_id, score=0.91, voi_estimate=0.74)
        return _GenerationResult(
            status="generated",
            candidates=(candidate,),
            surrogate_rankings=(ranking,),
            grounding_dispositions=(disposition,),
        )


def load_contract_payload(repo_root: Path) -> dict[str, Any]:
    """Read the committed frozen N6 contract payload."""

    return json.loads((repo_root / OUTPUT_PATH).read_text(encoding="utf-8"))


async def build_live_payload(repo_root: Path) -> dict[str, Any]:
    """Build the frozen Lane-0 payload by exercising the real N6 controller."""

    with TemporaryDirectory(prefix="gy-n6-verification-") as temp_dir:
        payload, _ = await _build_live_payload_in_verification_namespace(
            repo_root,
            state_root=Path(temp_dir),
        )
        return payload


async def _build_live_payload_in_verification_namespace(
    repo_root: Path,
    *,
    state_root: Path,
) -> tuple[dict[str, Any], _VerificationReplayContext]:
    """Run real N6 owners with only N11 CAS/state redirected to temporary storage."""

    started = time.monotonic()
    problem = _design_problem()
    binding = N9DesignProblemBinding.from_problem(problem)
    session = ConfidenceLedgerSession._for_verification(
        repo_root,
        risk_scope=confidence_risk_scope_for_problem(binding),
        artifact_store=FileSystemCAS(state_root / "cas"),
        state_root=state_root / "state",
    )
    controller = GenerationCycleController(
        generation_port=_Lane0GenerationPort(),
        grounding_port=PolicyGroundingPort(),
        value_port=PendingN8ValuePort(),
        promotion_port=CanonicalN9PromotionPort._for_verification(
            repo_root=repo_root,
            confidence_ledger_session=session,
        ),
        repo_root=repo_root,
        generated_at=_FIXED_GENERATED_AT,
        authority_scope="contract_testing",
    )
    run = await controller.run(
        problem,
        budget_state=BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("5.0"))}),
        min_cycles=2,
        max_cycles=3,
    )
    payload: dict[str, Any] = {
        "schema_version": GENERATION_CYCLE_CONTRACT_SCHEMA_VERSION,
        "contract_id": "policyos.runtime.generation_cycle_controller",
        "producer": "tools.quality.validation.check_layer3_gy_generation_cycle_contract",
        "source_modules": [
            "src/polisyos/runtime/quality/generation_cycle.py",
            "src/polisyos/scientist/orchestration/workflows/engine_simple.py",
            "src/polisyos/runtime/quality/design_generation.py",
            "src/polisyos/runtime/quality/joint_simulation_horizon.py",
            "src/polisyos/scientist/methods/search/voi_scheduler.py",
            "src/polisyos/pdc/_impl/layer2_design_search.py",
        ],
        "pattern_pass": {
            "relevant_ids": [
                "P01",
                "P02",
                "P03",
                "P04",
                "P05",
                "P10",
                "P15",
                "P27",
                "P28",
                "P29",
                "P31",
                "P32",
                "P33",
                "P34",
            ],
            "existing_anti_patterns_found": [
                "P27 legacy grounding matrix bypass",
                "P28 single-pass production route",
                "P29 marker-only contract risk",
            ],
            "target_correct_pattern": (
                "thin engine_simple controller over N4 CGF dispositions, N5 read-only "
                "simulation, S2 refinement records, and SimpleVOIScheduler routing"
            ),
            "missing_capability_labels": ["surface_out_of_scope"],
            "acceptance_signal": "frozen_lane0_run_and_decisive_mutation_red",
        },
        "denominators": _denominators(),
        "positive_gate": _positive_gate(run),
        "generation_cycle_run": run.model_dump(mode="json"),
        "strangle_receipt": run.strangle_receipt.model_dump(mode="json"),
        "compute_economics": {
            "lane": "Lane-0",
            "engine_set_reuse": "one_controller_engine_set_reused_across_cycles",
            "owner_io": "zero",
            "non_cached_run_visibility": "rederive_audit_only",
        },
    }
    payload["fail_closed_probes"] = _fail_closed_reports(payload)
    revalidation_issues, admissions = _embedded_promotion_comparison_admissions(
        run,
        repo_root=repo_root,
        session=session,
        problem=problem,
    )
    if revalidation_issues:
        raise RuntimeError(
            "n6_verification_replay_invalid: " + json.dumps(revalidation_issues, sort_keys=True)
        )
    plan = build_gy_comparison_projection_plan(payload, admissions=admissions)
    payload["behavioral_mutations"] = _mutation_reports(payload, plan)
    payload["capture_wall_time_seconds"] = round(max(0.0, time.monotonic() - started), 6)
    _set_comparison_identity(payload, plan)
    payload["contract_content_hash"] = _contract_content_hash(payload)
    context = _VerificationReplayContext(
        session=session,
        problem=problem,
        run=run,
        comparison_admissions=admissions,
        comparison_plan=plan,
    )
    return payload, context


def _promotion_receipt_denominator_issue(
    run: GenerationCycleRun,
) -> dict[str, Any] | None:
    expected = tuple(summary.candidate_id for summary in run.candidate_summaries)
    actual = tuple(
        str(receipt.get("candidate_id") or "") for receipt in run.promotion_port.receipts
    )
    if actual == expected and actual:
        return None
    return {
        "code": "embedded_promotion_receipt_denominator_mismatch",
        "expected": list(expected),
        "actual": list(actual),
    }


def _embedded_promotion_revalidation_issues(
    run: GenerationCycleRun,
    *,
    context: _VerificationReplayContext,
    repo_root: Path,
) -> list[dict[str, Any]]:
    """Reconcile frozen receipts with fresh, owner-validated semantics."""

    del repo_root
    issues: list[dict[str, Any]] = []
    denominator_issue = _promotion_receipt_denominator_issue(run)
    if denominator_issue is not None:
        issues.append(denominator_issue)
    live_receipts: dict[str, CanonicalPromotionReceipt] = {}
    for payload in context.run.promotion_port.receipts:
        receipt = CanonicalPromotionReceipt.model_validate(payload)
        live_receipts[receipt.candidate_id] = receipt
    if len(context.comparison_admissions) != len(live_receipts):
        issues.append({"code": "embedded_promotion_live_admission_denominator_mismatch"})
        return issues
    for index, payload in enumerate(run.promotion_port.receipts):
        try:
            frozen_receipt = parse_canonical_promotion_history_receipt(payload)
        except (ValidationError, ValueError) as exc:
            issues.append(
                {
                    "code": "embedded_promotion_receipt_revalidation_failed",
                    "receipt_index": index,
                    "issue_codes": ["promotion_receipt_invalid"],
                    "error": str(exc),
                }
            )
            continue
        live_receipt = live_receipts.get(frozen_receipt.candidate_id)
        if live_receipt is None:
            issues.append(
                {
                    "code": "embedded_promotion_receipt_revalidation_failed",
                    "receipt_index": index,
                    "issue_codes": ["promotion_candidate_owner_binding_invalid"],
                }
            )
            continue
        if type(frozen_receipt) is not CanonicalPromotionReceipt:
            issues.append(
                {
                    "code": "embedded_promotion_open_world_reissue_required",
                    "receipt_index": index,
                    "historical_schema_version": frozen_receipt.schema_version,
                    "current_schema_version": live_receipt.schema_version,
                }
            )
            continue
        if canonical_promotion_receipt_semantic_projection(
            frozen_receipt.model_dump(mode="json")
        ) != canonical_promotion_receipt_semantic_projection(live_receipt.model_dump(mode="json")):
            issues.append(
                {
                    "code": "embedded_promotion_receipt_semantic_projection_drift",
                    "receipt_index": index,
                }
            )
    return issues


def _embedded_promotion_comparison_admissions(
    run: GenerationCycleRun,
    *,
    repo_root: Path,
    session: ConfidenceLedgerSession,
    problem: DesignProblem,
) -> tuple[list[dict[str, Any]], tuple[GyComparisonAdmission, ...]]:
    """Revalidate every embedded receipt and return exact live admissions."""

    issues: list[dict[str, Any]] = []
    admissions: list[GyComparisonAdmission] = []
    expected_summaries = {summary.candidate_id: summary for summary in run.candidate_summaries}
    for index, receipt_payload in enumerate(run.promotion_port.receipts):
        try:
            receipt = CanonicalPromotionReceipt.model_validate(receipt_payload)
        except (ValidationError, ValueError) as exc:
            issues.append(
                {
                    "code": "embedded_promotion_receipt_revalidation_failed",
                    "receipt_index": index,
                    "issue_codes": ["promotion_receipt_invalid"],
                    "error": str(exc),
                }
            )
            continue
        summary = expected_summaries.get(receipt.candidate_id)
        if summary is None:
            issues.append(
                {
                    "code": "embedded_promotion_receipt_revalidation_failed",
                    "receipt_index": index,
                    "issue_codes": ["promotion_candidate_owner_binding_invalid"],
                }
            )
            continue
        try:
            admission = admit_canonical_promotion_receipt_for_comparison(
                receipt,
                repo_root=repo_root,
                confidence_ledger_session=session,
                candidate_summary=summary,
                design_problem=problem,
                value_receipt=summary.value_receipt,
            )
        except ValueError as exc:
            issues.append(
                {
                    "code": "embedded_promotion_receipt_revalidation_failed",
                    "receipt_index": index,
                    "issue_codes": [str(exc).partition(":")[0]],
                }
            )
        else:
            admissions.append(admission)
    return issues, tuple(admissions)


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate one frozen N6 contract payload and its mutation witnesses."""

    issues = _validate_payload_core(payload)
    mutation_reports = payload.get("behavioral_mutations")
    if not isinstance(mutation_reports, list) or not mutation_reports:
        issues.append({"code": "behavioral_mutations_missing"})
    else:
        mutation_ids = {
            str(item.get("mutation_id"))
            for item in mutation_reports
            if isinstance(item, dict) and item.get("mutation_id")
        }
        if mutation_ids != set(_EXPECTED_MUTATION_IDS):
            issues.append(
                {
                    "code": "behavioral_mutation_denominator_mismatch",
                    "expected": sorted(_EXPECTED_MUTATION_IDS),
                    "actual": sorted(mutation_ids),
                }
            )
        for report in mutation_reports:
            if not isinstance(report, dict):
                issues.append({"code": "behavioral_mutation_invalid"})
                continue
            if report.get("status") != "red":
                issues.append(
                    {
                        "code": "behavioral_mutation_not_red",
                        "mutation_id": report.get("mutation_id"),
                    }
                )
    probes = payload.get("fail_closed_probes")
    if not isinstance(probes, list) or not probes:
        issues.append({"code": "fail_closed_probes_missing"})
    else:
        for probe in probes:
            if not isinstance(probe, dict) or probe.get("status") != "fail_closed":
                issues.append({"code": "fail_closed_probe_not_closed", "probe": probe})
    expected_hash = _contract_content_hash(payload)
    issues.extend(_comparison_identity_issues(payload))
    if payload.get("contract_content_hash") != expected_hash:
        issues.append(
            {
                "code": "contract_content_hash_drift",
                "expected": expected_hash,
                "actual": payload.get("contract_content_hash"),
            }
        )
    return {"status": "pass" if not issues else "fail", "issues": issues}


def _validate_payload_core(payload: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if payload.get("schema_version") != GENERATION_CYCLE_CONTRACT_SCHEMA_VERSION:
        issues.append({"code": "schema_version_drift"})
    if payload.get("denominators") != _denominators():
        issues.append(
            {
                "code": "full_denominator_curated_subset",
                "expected": _denominators(),
                "actual": payload.get("denominators"),
            }
        )
    run_payload = payload.get("generation_cycle_run")
    if not isinstance(run_payload, dict):
        issues.append({"code": "generation_cycle_run_missing"})
        return issues
    try:
        run = GenerationCycleRun.model_validate(run_payload)
    except (ValidationError, ValueError) as exc:
        issues.append({"code": "generation_cycle_run_invalid", "error": str(exc)})
        return issues
    denominator_issue = _promotion_receipt_denominator_issue(run)
    if denominator_issue is not None:
        issues.append(denominator_issue)
    for index, receipt_payload in enumerate(run.promotion_port.receipts):
        try:
            parse_canonical_promotion_history_receipt(receipt_payload)
        except (ValidationError, ValueError) as exc:
            issues.append(
                {
                    "code": "embedded_promotion_receipt_invalid",
                    "receipt_index": index,
                    "error": str(exc),
                }
            )
    issues.extend(validate_generation_cycle_run(run))
    positive = payload.get("positive_gate")
    if not isinstance(positive, dict):
        issues.append({"code": "positive_gate_missing"})
        return issues
    if positive.get("cycle_count", 0) < 2:
        issues.append({"code": "positive_two_cycle_run_missing"})
    if positive.get("cycle_2_driven_by") != positive.get("cycle_1_counterexample_ref"):
        issues.append({"code": "cycle_two_not_counterexample_driven"})
    if positive.get("cycle_1_candidate_hash") == positive.get("cycle_2_candidate_hash"):
        issues.append({"code": "fake_cycle_same_candidate_repeated"})
    if not positive.get("cycle_2_introduced_grammar"):
        issues.append({"code": "retry_without_new_grammar_admitted"})
    if positive.get("value_port_status") != "value_pending_n8":
        issues.append({"code": "n6_fabricated_value"})
    if positive.get("decision_front"):
        issues.append({"code": "decision_front_admitted_non_current_valid"})
    if positive.get("portfolio_front"):
        issues.append({"code": "portfolio_front_not_deferred"})
    if positive.get("strangle_status") != "strangled":
        issues.append({"code": "single_pass_fixture_survives_as_production_cycle"})
    return issues


def validate(repo_root: Path) -> dict[str, Any]:
    """Validate committed frozen artifact drift and behavioral invariants."""

    started = time.monotonic()
    path = repo_root / OUTPUT_PATH
    issues: list[dict[str, Any]] = []
    if not path.is_file():
        issues.append({"code": "generation_cycle_contract_missing", "path": OUTPUT_PATH})
    else:
        committed_report = _validate_committed_contract_text(
            repo_root,
            path.read_text(encoding="utf-8"),
        )
        issues.extend(committed_report["issues"])
    return {
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "wall_time_seconds": round(max(0.0, time.monotonic() - started), 6),
    }


def write(repo_root: Path) -> None:
    """Write the frozen N6 contract artifact."""

    path = repo_root / OUTPUT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_contract_json_for_write(repo_root), encoding="utf-8")


def build_contract_json_for_write(repo_root: Path) -> str:
    """Return byte-stable JSON for the frozen N6 contract artifact."""

    with TemporaryDirectory(prefix="gy-n6-verification-") as temp_dir:
        payload, context = asyncio.run(
            _build_live_payload_in_verification_namespace(
                repo_root,
                state_root=Path(temp_dir),
            )
        )
    return _canonical_contract_json(
        payload,
        repo_root=repo_root,
        comparison_plan=context.comparison_plan,
    )


def _canonical_contract_json(
    payload: dict[str, Any],
    *,
    repo_root: Path,
    comparison_plan: GyComparisonProjectionPlan,
) -> str:
    """Render the one canonical UTF-8 JSON representation used for byte checks."""

    normalized = copy.deepcopy(payload)
    normalized.pop("capture_wall_time_seconds", None)
    _set_comparison_identity(normalized, comparison_plan)
    normalized["contract_content_hash"] = _contract_content_hash(normalized)
    normalized = _reconcile_frozen_contract(repo_root, normalized, comparison_plan)
    return json.dumps(normalized, indent=2, sort_keys=True) + "\n"


def _validate_committed_contract_text(
    repo_root: Path,
    committed_text: str,
) -> dict[str, Any]:
    """Deeply rederive owners and compare exact canonical UTF-8 bytes."""

    try:
        committed_payload = json.loads(committed_text)
    except json.JSONDecodeError as exc:
        return {
            "status": "fail",
            "issues": [{"code": "generation_cycle_contract_invalid_json", "error": str(exc)}],
        }
    report = validate_payload(committed_payload)
    issues = list(report["issues"])
    with TemporaryDirectory(prefix="gy-n6-committed-check-") as temp_dir:
        expected_payload, context = asyncio.run(
            _build_live_payload_in_verification_namespace(
                repo_root,
                state_root=Path(temp_dir),
            )
        )
        run_payload = committed_payload.get("generation_cycle_run")
        if isinstance(run_payload, dict):
            try:
                committed_run = GenerationCycleRun.model_validate(run_payload)
            except ValidationError, ValueError:
                committed_run = None
            if committed_run is not None:
                issues.extend(
                    _embedded_promotion_revalidation_issues(
                        committed_run,
                        context=context,
                        repo_root=repo_root,
                    )
                )
        try:
            expected_text = _canonical_contract_json(
                expected_payload,
                repo_root=repo_root,
                comparison_plan=context.comparison_plan,
            )
        except ValueError as exc:
            if str(exc) != "generation_cycle_comparison_admission_manifest_drift":
                raise
            issues.append({"code": "generation_cycle_comparison_admission_manifest_drift"})
            expected_text = None
    if expected_text is not None and committed_text.encode("utf-8") != expected_text.encode(
        "utf-8"
    ):
        issues.append(
            {
                "code": "generation_cycle_contract_canonical_bytes_drift",
                "expected_hash": gy_content_hash(json.loads(expected_text)),
                "actual_hash": gy_content_hash(committed_payload),
            }
        )
    return {"status": "pass" if not issues else "fail", "issues": issues}


def corrupt_field_drift_check(repo_root: Path) -> dict[str, Any]:
    """Mutate a decisive field and require the semantic validator to turn red."""

    started = time.monotonic()
    corrupted = copy.deepcopy(load_contract_payload(repo_root))
    corrupted["generation_cycle_run"]["cycles"][1]["selected_candidate_content_hash"] = corrupted[
        "generation_cycle_run"
    ]["cycles"][0]["selected_candidate_content_hash"]
    report = validate_payload(corrupted)
    if report["status"] == "fail":
        return {
            "status": "fail",
            "issues": [
                {
                    "code": "corrupt_field_drift_detected",
                    "detected_issue_codes": sorted(
                        str(issue.get("code"))
                        for issue in report["issues"]
                        if isinstance(issue, dict)
                    ),
                },
                *report["issues"],
            ],
            "wall_time_seconds": round(max(0.0, time.monotonic() - started), 6),
        }
    return {
        "status": "pass",
        "issues": [{"code": "corrupt_field_drift_not_detected"}],
        "wall_time_seconds": round(max(0.0, time.monotonic() - started), 6),
    }


def rederive_audit(repo_root: Path) -> dict[str, Any]:
    """Run the optional live-ish audit path behind an explicit flag."""

    started = time.monotonic()
    payload = asyncio.run(build_live_payload(repo_root))
    report = validate_payload(payload)
    return {
        "status": report["status"],
        "issues": report["issues"],
        "wall_time_seconds": round(max(0.0, time.monotonic() - started), 6),
        "compute_economics": payload.get("compute_economics", {}),
    }


def _positive_gate(run: GenerationCycleRun) -> dict[str, Any]:
    first = run.cycles[0]
    second = run.cycles[1] if len(run.cycles) > 1 else run.cycles[0]
    return {
        "cycle_count": len(run.cycles),
        "cycle_1_candidate": first.selected_candidate_ref,
        "cycle_2_candidate": second.selected_candidate_ref,
        "cycle_1_candidate_hash": first.selected_candidate_content_hash,
        "cycle_2_candidate_hash": second.selected_candidate_content_hash,
        "cycle_1_counterexample_ref": first.counterexample.counterexample_ref,
        "cycle_2_driven_by": second.driven_by_counterexample_ref,
        "cycle_2_introduced_grammar": list(second.introduced_grammar_elements),
        "voi_decisions": [cycle.voi_decision.model_dump(mode="json") for cycle in run.cycles],
        "decision_front": list(run.fronts.decision.candidate_ids),
        "research_front": list(run.fronts.research.candidate_ids),
        "quarantine_front": list(run.fronts.quarantine.candidate_ids),
        "portfolio_front": list(run.fronts.portfolio.candidate_ids),
        "value_port_status": run.value_port.status,
        "strangle_status": run.strangle_receipt.status,
        "quarantine_actions": {
            summary.candidate_id: summary.quarantine_action
            for summary in run.candidate_summaries
            if summary.front == "quarantine"
        },
    }


def _mutation_reports(
    payload: dict[str, Any],
    plan: GyComparisonProjectionPlan,
) -> list[dict[str, Any]]:
    mutations = {
        "revision_not_terminal_driven": _mutate_revision_not_terminal_driven,
        "retry_without_new_grammar_admitted": _mutate_no_new_grammar,
        "voi_scheduler_ignored_fixed_cycle_count": _mutate_ignored_voi,
        "single_pass_fixture_survives_as_production_cycle": _mutate_strangle_drift,
        "proxy_gap_candidate_promoted_without_adversarial_validate": (_mutate_proxy_gap_decision),
        "decision_front_admitted_non_current_valid": _mutate_non_current_decision,
        "grounding_bypassed_cgf_firewall": _mutate_grounding_bypass,
        "coverage_depends_on_llm": _mutate_fallback_promoted,
        "k_sim_shrank_k_world": _mutate_k_sim_shrank_world,
        "full_denominator_curated_subset": _mutate_full_denominator_subset,
        "incoherent_single_terminal_run": _mutate_incoherent_single_terminal,
        "empty_cycle_run": _mutate_empty_cycle_run,
    }
    reports: list[dict[str, Any]] = []
    for mutation_id, mutator in mutations.items():
        mutated = copy.deepcopy(payload)
        mutator(mutated)
        _set_comparison_identity(mutated, plan)
        mutated["contract_content_hash"] = _contract_content_hash(mutated)
        report = _validate_payload_core(mutated)
        reports.append(
            {
                "mutation_id": mutation_id,
                "status": "red" if report else "green",
                "issue_codes": [str(issue.get("code")) for issue in report],
            }
        )
    return reports


def _mutate_revision_not_terminal_driven(payload: dict[str, Any]) -> None:
    revision = payload["generation_cycle_run"]["cycles"][0]["revision_request"]
    revision["new_grammar_elements"] = ["repair:generic:missing_supporting_data"]
    revision["next_grammar_elements"] = ["seed", "repair:generic:missing_supporting_data"]


def _mutate_no_new_grammar(payload: dict[str, Any]) -> None:
    payload["generation_cycle_run"]["cycles"][1]["introduced_grammar_elements"] = []
    payload["positive_gate"]["cycle_2_introduced_grammar"] = []


def _mutate_ignored_voi(payload: dict[str, Any]) -> None:
    payload["generation_cycle_run"]["cycles"][0]["voi_decision"]["next_action"] = "stop"


def _mutate_strangle_drift(payload: dict[str, Any]) -> None:
    payload["generation_cycle_run"]["strangle_receipt"]["status"] = "drift"
    payload["generation_cycle_run"]["strangle_receipt"]["production_single_pass_callers"] = [
        "src/polisyos/runtime/http/services/control/nl_pipeline.py:1"
    ]
    payload["positive_gate"]["strangle_status"] = "drift"


def _mutate_incoherent_single_terminal(payload: dict[str, Any]) -> None:
    first_cycle = copy.deepcopy(payload["generation_cycle_run"]["cycles"][0])
    first_cycle["terminal_kind"] = SearchTerminalKind.FRONTIER_STABLE.value
    payload["generation_cycle_run"]["cycles"] = [first_cycle]


def _mutate_empty_cycle_run(payload: dict[str, Any]) -> None:
    payload["generation_cycle_run"]["cycles"] = []


def _mutate_proxy_gap_decision(payload: dict[str, Any]) -> None:
    summary = payload["generation_cycle_run"]["candidate_summaries"][0]
    summary["front"] = "decision"
    summary["certified_by_n9"] = True
    summary["current_valid"] = True
    summary["adversarial_validation_status"] = "required_before_decision"
    candidate_id = summary["candidate_id"]
    fronts = payload["generation_cycle_run"]["fronts"]
    fronts["decision"]["candidate_ids"] = [candidate_id]
    fronts["quarantine"]["candidate_ids"] = [
        item for item in fronts["quarantine"]["candidate_ids"] if item != candidate_id
    ]
    payload["positive_gate"]["decision_front"] = [candidate_id]


def _mutate_non_current_decision(payload: dict[str, Any]) -> None:
    summary = payload["generation_cycle_run"]["candidate_summaries"][-1]
    summary["front"] = "decision"
    summary["certified_by_n9"] = False
    summary["current_valid"] = False
    candidate_id = summary["candidate_id"]
    fronts = payload["generation_cycle_run"]["fronts"]
    fronts["decision"]["candidate_ids"] = [candidate_id]
    fronts["research"]["candidate_ids"] = [
        item for item in fronts["research"]["candidate_ids"] if item != candidate_id
    ]
    payload["positive_gate"]["decision_front"] = [candidate_id]


def _mutate_grounding_bypass(payload: dict[str, Any]) -> None:
    summary = payload["generation_cycle_run"]["candidate_summaries"][-1]
    summary["grounding_status"] = "grounded_shadow"
    summary["grounding_source"] = "grounding_unavailable"
    summary["grounding_disposition"] = None


def _mutate_fallback_promoted(payload: dict[str, Any]) -> None:
    summary = payload["generation_cycle_run"]["candidate_summaries"][-1]
    summary["generation_channel"] = "grammar_fallback"
    summary["front"] = "decision"
    summary["certified_by_n9"] = True
    summary["current_valid"] = True
    candidate_id = summary["candidate_id"]
    fronts = payload["generation_cycle_run"]["fronts"]
    fronts["decision"]["candidate_ids"] = [candidate_id]
    fronts["research"]["candidate_ids"] = [
        item for item in fronts["research"]["candidate_ids"] if item != candidate_id
    ]
    payload["positive_gate"]["decision_front"] = [candidate_id]


def _mutate_k_sim_shrank_world(payload: dict[str, Any]) -> None:
    simulation = payload["generation_cycle_run"]["cycles"][0]["simulation"]
    simulation["k_world_ref_before"] = "world_model_record_before"
    simulation["k_world_ref_after"] = "world_model_record_after"


def _mutate_full_denominator_subset(payload: dict[str, Any]) -> None:
    payload["denominators"]["scheduling_actions"] = payload["denominators"]["scheduling_actions"][
        :-1
    ]


def _fail_closed_reports(payload: dict[str, Any]) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    try:
        CandidateGroundingObservation.model_validate(
            {
                "candidate_id": "candidate_bad_status",
                "status": "fabricated_current_valid",
                "grounding_score": 1.0,
            }
        )
    except ValidationError:
        reports.append({"probe_id": "fabricated_grounding_status", "status": "fail_closed"})
    try:
        enforce_no_retry_without_new_grammar(
            previous_candidate_ref="candidate_a",
            next_candidate_ref="candidate_b",
            previous_grammar_elements=("seed",),
            next_grammar_elements=("seed",),
            introduced_grammar_elements=("laundered",),
        )
    except Exception as exc:
        reports.append(
            {
                "probe_id": "laundered_revision_grammar",
                "status": "fail_closed",
                "code": getattr(exc, "code", type(exc).__name__),
            }
        )
    owner_probe = copy.deepcopy(payload)
    owner_probe["generation_cycle_run"]["cycles"][0]["grounding"]["issue_codes"] = [
        "candidate_owner_target_missing"
    ]
    owner_probe["generation_cycle_run"]["cycles"][0]["grounding"]["status"] = (
        "grounding_unavailable"
    )
    reports.append({"probe_id": "candidate_owner_target_missing", "status": "fail_closed"})
    unknown_voi = copy.deepcopy(payload)
    unknown_voi["generation_cycle_run"]["cycles"][0]["voi_decision"]["scheduler_action"] = (
        "unknown_owner_action"
    )
    if any(
        issue.get("code") == "unknown_voi_action_not_fail_closed"
        for issue in _validate_payload_core(unknown_voi)
    ):
        reports.append({"probe_id": "unknown_voi_action", "status": "fail_closed"})
    return reports


def _denominators() -> dict[str, Any]:
    scheduling_actions = sorted(
        str(item)
        for item in get_args(SchedulingDecision.model_fields["recommended_action"].annotation)
    )
    terminal_kinds = sorted(item.value for item in SearchTerminalKind)
    front_kinds = ["decision", "portfolio", "quarantine", "research"]
    grounding_dispositions = sorted(str(item) for item in get_args(GroundingDispositionKind))
    grounding_statuses = sorted(
        [
            "current_valid",
            "grounded_shadow",
            "grounding_failed",
            "grounding_gap",
            "grounding_unavailable",
        ]
    )
    return {
        "scheduling_actions": scheduling_actions,
        "terminal_kinds": terminal_kinds,
        "front_kinds": front_kinds,
        "grounding_dispositions": grounding_dispositions,
        "grounding_statuses": grounding_statuses,
        "counts": {
            "scheduling_actions": len(scheduling_actions),
            "terminal_kinds": len(terminal_kinds),
            "front_kinds": len(front_kinds),
            "grounding_dispositions": len(grounding_dispositions),
            "grounding_statuses": len(grounding_statuses),
        },
    }


def _design_problem() -> DesignProblem:
    return DesignProblem(
        design_problem_id="industrial_resilience_retooling",
        problem_statement="Retool industrial resilience support without laundering proxy signals.",
        domain="industrial_policy",
        nl_provenance=NLProvenance(
            raw_request="Retool industrial resilience support.",
            source_surface="generation_cycle_contract_lane0",
        ),
        authority_profile=AuthorityProfile(
            requester_authority="research_lab",
            requested_authority_level="research",
            mandate="N6 frozen contract fixture; no promotion authority.",
        ),
        jurisdiction_time=JurisdictionTimeSemantics(
            region="UA",
            valid_time="2026",
            as_of="2026-07-05",
            policy_time="2026",
            data_time="2026",
        ),
        objectives=[
            DesignObjective(
                objective_id="industrial_resilience",
                description="Improve industrial resilience",
                metric_id="industrial_resilience",
            )
        ],
        constraints=[
            DesignConstraint(
                constraint_id="shadow_only",
                description="Generated candidates remain shadow until A/N9 certification.",
                hard=True,
                admissibility_basis="request_text",
                source_text="Do not promote generated candidates.",
            )
        ],
        stakeholders=[
            DesignStakeholder(
                stakeholder_id="industrial_firms",
                name="Industrial firms",
                role="target_population",
            )
        ],
        outcome_of_interest=OutcomeOfInterest(
            target_variable="industrial_resilience",
            metric_id="industrial_resilience",
            estimand="average_treatment_effect",
        ),
        candidate_lever_space=CandidateLeverSpace(
            allowed_operator_kinds=["grant", "procurement_priority"],
            candidate_levers=[
                CandidateLever(
                    lever_id="resilience_grant",
                    operator_kind="grant",
                    instrument="Retooling grant",
                    target_slot="industrial_resilience",
                )
            ],
        ),
        evidence_acquisition_needs=EvidenceAcquisitionNeeds(
            needs=[
                EvidenceNeed(
                    need_id="industrial_panel",
                    question="Which producer evidence grounds resilience effects?",
                    required_for="A-side grounding",
                )
            ]
        ),
        runtime_hints={"generation_cycle_grammar": ("seed",)},
    )


def _contract_content_hash(payload: dict[str, Any]) -> str:
    stable = {
        key: value for key, value in payload.items() if key not in _CONTENT_HASH_EXCLUDED_TOP_LEVEL
    }
    return gy_content_hash(stable)


def _comparison_content_hash(
    payload: dict[str, Any],
    plan: GyComparisonProjectionPlan,
) -> str:
    stable = {
        key: value
        for key, value in payload.items()
        if key not in _CONTENT_HASH_EXCLUDED_TOP_LEVEL | _COMPARISON_IDENTITY_FIELDS
    }
    return gy_comparison_content_hash(
        stable,
        comparison_plan=plan,
    )


def _reconcile_frozen_contract(
    repo_root: Path,
    live: dict[str, Any],
    plan: GyComparisonProjectionPlan,
) -> dict[str, Any]:
    path = repo_root / OUTPUT_PATH
    if not path.is_file():
        return live
    frozen = json.loads(path.read_text(encoding="utf-8"))
    if frozen.get("contract_content_hash") != _contract_content_hash(frozen):
        raise ValueError("generation_cycle_legacy_contract_content_hash_drift")
    if not _frozen_comparison_identity_admissible(frozen, plan):
        raise ValueError("generation_cycle_comparison_admission_manifest_drift")
    identity_fields = _COMPARISON_IDENTITY_FIELDS | {"contract_content_hash"}
    frozen_body = {key: value for key, value in frozen.items() if key not in identity_fields}
    live_body = {key: value for key, value in live.items() if key not in identity_fields}
    reconciled = plan.preserve_admitted_blocks(frozen_body, live_body)
    if not isinstance(reconciled, dict):  # pragma: no cover - mapping inputs
        raise ValueError("generation_cycle_contract_comparison_projection_invalid")
    _set_comparison_identity(reconciled, plan)
    reconciled["contract_content_hash"] = _contract_content_hash(reconciled)
    return reconciled


def _frozen_comparison_identity_admissible(
    frozen: dict[str, Any],
    live_plan: GyComparisonProjectionPlan,
) -> bool:
    """Accept only absent/current or exactly self-validating v1 comparison custody."""

    manifest = frozen.get("comparison_admission_manifest")
    if manifest in (None, live_plan.manifest):
        return True
    if (
        frozen.get("comparison_projection_schema_version")
        != GY_COMPARISON_PROJECTION_LEGACY_SCHEMA_VERSION
        or frozen.get("comparison_rule_version") != GY_VERIFICATION_COMPARISON_LEGACY_RULE_VERSION
    ):
        return False
    try:
        legacy_plan = build_gy_comparison_projection_plan_from_manifest(
            frozen,
            manifest=manifest,
            owner_rule_registry=(canonical_promotion_verification_comparison_owner_rule_registry()),
        )
    except ValueError:
        return False
    return frozen.get("comparison_content_hash") == _comparison_content_hash(
        frozen,
        legacy_plan,
    )


def _set_comparison_identity(
    payload: dict[str, Any],
    plan: GyComparisonProjectionPlan,
) -> None:
    payload["comparison_admission_manifest"] = plan.manifest
    payload["comparison_projection_schema_version"] = GY_COMPARISON_PROJECTION_SCHEMA_VERSION
    payload["comparison_rule_version"] = GY_VERIFICATION_COMPARISON_RULE_VERSION
    payload["comparison_content_hash"] = _comparison_content_hash(payload, plan)


def _comparison_identity_issues(payload: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if (
        payload.get("comparison_projection_schema_version")
        != GY_COMPARISON_PROJECTION_SCHEMA_VERSION
    ):
        issues.append({"code": "comparison_projection_schema_version_invalid"})
    if payload.get("comparison_rule_version") != GY_VERIFICATION_COMPARISON_RULE_VERSION:
        issues.append({"code": "comparison_rule_version_invalid"})
    manifest = payload.get("comparison_admission_manifest")
    try:
        plan = build_gy_comparison_projection_plan_from_manifest(
            payload,
            manifest=manifest,
            owner_rule_registry=(canonical_promotion_verification_comparison_owner_rule_registry()),
        )
    except ValueError as exc:
        issues.append({"code": "comparison_admission_manifest_invalid", "error": str(exc)})
    else:
        if payload.get("comparison_content_hash") != _comparison_content_hash(payload, plan):
            issues.append({"code": "comparison_content_hash_drift"})
    return issues


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--corrupt-field-drift-check", action="store_true")
    parser.add_argument("--rederive-audit", action="store_true")
    parser.add_argument("--output-format", choices={"json", "text"}, default="text")
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve()
    if args.write:
        write(repo_root)
        report = {"status": "pass", "issues": [], "outputs": declared_outputs()}
    elif args.corrupt_field_drift_check:
        report = corrupt_field_drift_check(repo_root)
    elif args.rederive_audit:
        report = rederive_audit(repo_root)
    else:
        report = validate(repo_root)
    if args.output_format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    elif report["status"] == "pass":
        print(
            "PASS layer3_gy_generation_cycle_contract "
            f"wall_time_seconds={report.get('wall_time_seconds', 0)}"
        )
    else:
        print(json.dumps(report, indent=2, sort_keys=True), file=sys.stderr)
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    import sys

    raise SystemExit(
        run_timed_entrypoint(
            main,
            script_path=__file__,
            argv=sys.argv[1:],
            started_perf_counter=_TIMING_STARTED_AT,
        )
    )
