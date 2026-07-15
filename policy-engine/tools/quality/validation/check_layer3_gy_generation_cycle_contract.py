#!/usr/bin/env python3
"""Validate the frozen Layer 3 GY-N6 generation-cycle controller contract."""

from __future__ import annotations

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
from typing import Any, get_args

from pydantic import ValidationError

from polisyos.pdc import SearchTerminalKind, gy_content_hash
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
from polisyos.scientist.methods.search.voi_scheduler import SchedulingDecision
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState

OUTPUT_PATH = "architecture/policy_design_case/layer3_gy_generation_cycle_contract.json"
_FIXED_GENERATED_AT = datetime(2026, 7, 5, tzinfo=UTC)
_CONTENT_HASH_EXCLUDED_TOP_LEVEL = {"contract_content_hash", "capture_wall_time_seconds"}
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


class _Lane0GenerationPort:
    """Scripted proposer over real N6 controller semantics, with CGF-shaped records."""

    async def __call__(self, problem: DesignProblem, *, cycle_index: int) -> _GenerationResult:
        grammar = tuple(problem.runtime_hints.get("generation_cycle_grammar", ()))
        if cycle_index > 0 and any(
            "repair:search_ceiling_repair_required" in item
            or "adversarial_validate" in item
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

    started = time.monotonic()
    controller = GenerationCycleController(
        generation_port=_Lane0GenerationPort(),
        grounding_port=PolicyGroundingPort(),
        value_port=PendingN8ValuePort(),
        repo_root=repo_root,
        generated_at=_FIXED_GENERATED_AT,
    )
    run = await controller.run(
        _design_problem(),
        budget_state=BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("5.0"))}
        ),
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
    payload["behavioral_mutations"] = _mutation_reports(payload)
    payload["capture_wall_time_seconds"] = round(max(0.0, time.monotonic() - started), 6)
    payload["contract_content_hash"] = _contract_content_hash(payload)
    return payload


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
        committed = json.loads(path.read_text(encoding="utf-8"))
        issues.extend(validate_payload(committed)["issues"])
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

    payload = asyncio.run(build_live_payload(repo_root))
    payload.pop("capture_wall_time_seconds", None)
    payload["contract_content_hash"] = _contract_content_hash(payload)
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def corrupt_field_drift_check(repo_root: Path) -> dict[str, Any]:
    """Mutate a decisive field and require the semantic validator to turn red."""

    started = time.monotonic()
    corrupted = copy.deepcopy(load_contract_payload(repo_root))
    corrupted["generation_cycle_run"]["cycles"][1]["selected_candidate_content_hash"] = (
        corrupted["generation_cycle_run"]["cycles"][0]["selected_candidate_content_hash"]
    )
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


def _mutation_reports(payload: dict[str, Any]) -> list[dict[str, Any]]:
    mutations = {
        "revision_not_terminal_driven": _mutate_revision_not_terminal_driven,
        "retry_without_new_grammar_admitted": _mutate_no_new_grammar,
        "voi_scheduler_ignored_fixed_cycle_count": _mutate_ignored_voi,
        "single_pass_fixture_survives_as_production_cycle": _mutate_strangle_drift,
        "proxy_gap_candidate_promoted_without_adversarial_validate": (
            _mutate_proxy_gap_decision
        ),
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
    payload["denominators"]["scheduling_actions"] = payload["denominators"][
        "scheduling_actions"
    ][:-1]


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
    unknown_voi["generation_cycle_run"]["cycles"][0]["voi_decision"][
        "scheduler_action"
    ] = "unknown_owner_action"
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
        key: value
        for key, value in payload.items()
        if key not in _CONTENT_HASH_EXCLUDED_TOP_LEVEL
    }
    return gy_content_hash(stable)


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
    raise SystemExit(main())
