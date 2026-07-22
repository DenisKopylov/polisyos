"""RT6 grounding benchmark over the real CGF pipeline.

The benchmark measures CG1 relation, CG2 bind, CG3 admission, and CG4 phrasing
defense behavior over a CG0 ``CredalReference``. It deliberately treats labels
as owner-derived obligation sets, not authored gold answers: cases whose labels
cannot be re-derived from their construction proof are dropped and counted.
"""

from __future__ import annotations

import json
import math
import time
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.credal_reference import (
    CREDAL_REFERENCE_SCHEMA_VERSION,
    AdmissibleCompletion,
    CredalReference,
    CredalReferenceEdge,
    replace_reference_edge,
)
from polisyos.runtime.quality.grounding_admission import GroundingAdmissionEngine
from polisyos.runtime.quality.grounding_bind import (
    CalibrationStratumRecord,
    GroundingBindGate,
    GroundingCalibrationLedger,
)
from polisyos.runtime.quality.grounding_phrasing_defense import (
    GroundingPhrasingDefenseEngine,
)
from polisyos.runtime.quality.grounding_relation import (
    GroundingCandidateAtom,
    GroundingEnginePolicy,
    GroundingRelationCertificate,
    GroundingRelationEngine,
    grounding_candidate_semantic_sort_key,
    parse_n4_proposal,
)

GROUNDING_BENCHMARK_SCHEMA_VERSION = "policyos.runtime.grounding_benchmark_scoreboard.v1"
GROUNDING_BENCHMARK_VALIDATOR_VERSION = "policyos.runtime.grounding_benchmark.rt6.v1"
DEFAULT_BENCHMARK_SEED = "cg6_rt6_grounding_benchmark_seed_v1"
BENCHMARK_OUTPUT_PATH = "architecture/policy_design_case/grounding_benchmark_scoreboard.json"

type ObligationLabel = Literal[
    "must+",
    "may+",
    "must-",
    "unknown",
    "novel+",
    "hallucination-",
]
type BaselineId = Literal[
    "full_cgf_stack",
    "exact_match_alias_table",
    "lexical_similarity_duckdb_fts_top1",
    "entity_linker_recorded_replay",
    "greedy_per_axis",
    "llm_judge_recorded_replay",
    "passive_abstain",
]
type BenchmarkStream = Literal[
    "seed_anchors",
    "calibration",
    "stress",
    "growth",
    "private",
    "retroactive_denominator",
]

_IDENTIFYING_RELATIONS = frozenset({"exact", "certified-specialization"})
_BIND_RELATIONS = frozenset({"bind"})
_CGF_BASELINE: BaselineId = "full_cgf_stack"
_ALIAS_TABLE = {
    "budget": "budget_allocation_multiplier",
    "budget_allocation": "budget_allocation_multiplier",
    "budget_multiplier": "budget_allocation_multiplier",
    "corporate_tax_credit": "tax_relief_rate",
    "income_tax_credit": "tax_relief_rate",
    "payroll_tax_credit": "tax_relief_rate",
    "procurement": "procurement_shock_intensity",
    "procurement_shock": "procurement_shock_intensity",
    "tax_credit": "tax_relief_rate",
    "tax_credit_rate": "tax_relief_rate",
    "tax_relief": "tax_relief_rate",
    "tax_subsidy": "income_tax",
}


class _StrictModel(BaseModel):
    """Strict immutable base for benchmark DTOs."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class LabelDerivation(_StrictModel):
    """Owner-derived proof for a benchmark obligation set."""

    derivation_kind: str = Field(..., min_length=1)
    owner_refs: tuple[str, ...]
    proof_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    derivation_notes: str = ""


class GroundingBenchmarkCase(_StrictModel):
    """One RT6 benchmark case and its owner-derived obligation set."""

    case_id: str = Field(..., min_length=1)
    case_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    stream: BenchmarkStream
    family: str = Field(..., min_length=1)
    epoch_id: str = Field(..., min_length=1)
    proposal: Mapping[str, Any]
    obligation_labels: tuple[ObligationLabel, ...]
    expected_atom_id: str | None = None
    expected_operator: str | None = None
    expected_target: str | None = None
    construction_family: str = Field(..., min_length=1)
    label_derivation: LabelDerivation
    held_out_key: str = Field(..., min_length=1)
    source_atom_id: str | None = None
    decisive_mechanism_expected: str = Field(..., min_length=1)


class DroppedBenchmarkCase(_StrictModel):
    """Dropped case record; dropped cases remain in denominators."""

    case_id: str = Field(..., min_length=1)
    stream: BenchmarkStream
    family: str = Field(..., min_length=1)
    epoch_id: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1)


class BaselineConfig(_StrictModel):
    """Replayable baseline configuration."""

    baseline_id: BaselineId
    implementation: str = Field(..., min_length=1)
    provenance: str = Field(..., min_length=1)
    decision_boundary: str = Field(..., min_length=1)
    alias_table_hash: str | None = Field(None, pattern=r"^sha256:[0-9a-f]{64}$")
    dense_embeddings_status: str = "not_used"
    entity_linker_status: str = "not_used"
    llm_status: str = "not_used"
    config_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    expected_config_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")


class CertificateReplayRef(_StrictModel):
    """Certificate ids and hashes needed for replay completeness scoring."""

    certificate_id: str = Field(..., min_length=1)
    content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    component: str = Field(..., min_length=1)


class GroundingBenchmarkDecision(_StrictModel):
    """One baseline decision for one benchmark case."""

    case_id: str = Field(..., min_length=1)
    case_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    baseline_id: BaselineId
    epoch_id: str = Field(..., min_length=1)
    stream: BenchmarkStream
    family: str = Field(..., min_length=1)
    relation: str = Field(..., min_length=1)
    selected_atom_id: str | None = None
    bind_decision: str = "abstain"
    admission_decision: str = "not_applicable"
    admission_reason: str | None = None
    quarantined: bool = False
    certificate_chain: tuple[CertificateReplayRef, ...] = ()
    replay_complete: bool
    latency_ms: float = Field(..., ge=0.0)
    decision_notes: tuple[str, ...] = ()


class IntervalEstimate(_StrictModel):
    """Binomial rate with explicit denominator and interval."""

    numerator: int = Field(..., ge=0)
    denominator: int = Field(..., ge=0)
    rate: float = Field(..., ge=0.0, le=1.0)
    interval_method: Literal["clopper_pearson_scipy_beta"] = "clopper_pearson_scipy_beta"
    lower: float = Field(..., ge=0.0, le=1.0)
    upper: float = Field(..., ge=0.0, le=1.0)


class ScoreSlice(_StrictModel):
    """Score row for one baseline x epoch x stream x family denominator."""

    baseline_id: BaselineId
    epoch_id: str = Field(..., min_length=1)
    stream: BenchmarkStream
    family: str = Field(..., min_length=1)
    total_cases: int = Field(..., ge=0)
    evaluated_cases: int = Field(..., ge=0)
    dropped_cases: int = Field(..., ge=0)
    false_bind: IntervalEstimate
    hallucination_admit: IntervalEstimate
    confident_wrong: IntervalEstimate
    useful_recall: IntervalEstimate
    novel_admission_precision: IntervalEstimate
    correct_abstention: IntervalEstimate
    quarantine_capture: IntervalEstimate
    certificate_replay_completeness: IntervalEstimate
    latency_ms_p50: float = Field(..., ge=0.0)
    latency_ms_max: float = Field(..., ge=0.0)


class BenchmarkHeadline(_StrictModel):
    """Mandatory growth headline."""

    metric_id: Literal["false_bind_rate_under_growth"] = "false_bind_rate_under_growth"
    baseline_id: Literal["full_cgf_stack"] = "full_cgf_stack"
    stream: Literal["growth"] = "growth"
    growth_epoch_count: int = Field(..., ge=0)
    false_bind: IntervalEstimate
    hallucination_admit: IntervalEstimate
    confident_wrong: IntervalEstimate
    denominator_note: str = Field(..., min_length=1)


class CalibrationAnchorSet(_StrictModel):
    """Held-out future CG2 calibration source; not wired into CG2."""

    anchor_set_id: str = Field(..., min_length=1)
    content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    provenance: Literal["cg6_benchmark_calibration_v1"] = "cg6_benchmark_calibration_v1"
    epoch_id: str = Field(..., min_length=1)
    wired_into_cg2: Literal[False] = False
    unfreeze_pathway: str = Field(..., min_length=1)
    strata: Mapping[str, int]


class DetectorLivenessRecord(_StrictModel):
    """Broken-stack benchmark replay used to prove detector liveness."""

    variant_id: str = Field(..., min_length=1)
    contract_testing_scope: bool
    mutation_switches: tuple[str, ...]
    false_bind_count: int = Field(..., ge=0)
    hallucination_admit_count: int = Field(..., ge=0)
    confident_wrong_count: int = Field(..., ge=0)
    denominator: int = Field(..., ge=0)
    working_confident_wrong_count: int = Field(..., ge=0)
    confident_wrong_interval: IntervalEstimate
    working_confident_wrong_interval: IntervalEstimate
    materiality_rule: str = Field(..., min_length=1)
    materially_degraded: bool
    detection_floor: Literal[
        "not_applicable",
        "detectable_single",
        "detectable_stacked_only",
        "undetectable",
    ]


class GrowthEpochRecord(_StrictModel):
    """Growth epoch reference and loop-closure record."""

    epoch_id: str = Field(..., min_length=1)
    reference_epoch: str = Field(..., min_length=1)
    reference_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    admitted_operator: str | None = None
    admitted_patch_id: str | None = None
    admitted_lever_groundable: bool = False
    fresh_mimicry_caught: bool = False


class GroundingBenchmarkScoreboard(_StrictModel):
    """Content-addressed RT6 benchmark scoreboard."""

    schema_version: Literal["policyos.runtime.grounding_benchmark_scoreboard.v1"] = (
        GROUNDING_BENCHMARK_SCHEMA_VERSION
    )
    benchmark_id: str = Field(..., pattern=r"^cg6_benchmark_[a-f0-9]{16}$")
    content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    validator_version: str = GROUNDING_BENCHMARK_VALIDATOR_VERSION
    seed: str = Field(..., min_length=1)
    reference_epoch: str = Field(..., min_length=1)
    reference_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    generation_scope: Mapping[str, Any]
    baseline_configs: Mapping[str, BaselineConfig]
    cases: tuple[GroundingBenchmarkCase, ...]
    dropped_cases: tuple[DroppedBenchmarkCase, ...]
    decisions: tuple[GroundingBenchmarkDecision, ...]
    score_slices: tuple[ScoreSlice, ...]
    headline: BenchmarkHeadline
    growth_epochs: tuple[GrowthEpochRecord, ...]
    calibration_anchor_set: CalibrationAnchorSet
    detector_liveness: tuple[DetectorLivenessRecord, ...]
    findings: tuple[str, ...]
    private_streams: Mapping[str, str]
    summary: Mapping[str, Any]
    latency_bound_ms: float = Field(..., gt=0.0)
    latency_bound_asserted: bool
    pattern_pass: Mapping[str, Any]

    @model_validator(mode="after")
    def _content_hash_matches_payload(self) -> GroundingBenchmarkScoreboard:
        expected = recompute_grounding_benchmark_scoreboard_hash(self)
        if self.content_hash != expected:
            raise ValueError("grounding_benchmark_content_hash_mismatch")
        expected_id = f"cg6_benchmark_{expected.removeprefix('sha256:')[:16]}"
        if self.benchmark_id != expected_id:
            raise ValueError("grounding_benchmark_id_mismatch")
        if self.headline.growth_epoch_count < 2:
            raise ValueError("grounding_benchmark_headline_growth_missing")
        if any(not row.epoch_id for row in self.score_slices):
            raise ValueError("grounding_benchmark_slice_epoch_missing")
        return self


def build_grounding_benchmark_scoreboard(
    reference: CredalReference,
) -> GroundingBenchmarkScoreboard:
    """Run the safe public benchmark over a caller-supplied CG0 reference.

    The public entrypoint exposes no case exclusion, reweighting, threshold, or
    mutation knobs. Validators that need mutation probes must use the explicit
    ``run_grounding_benchmark_for_contract_testing`` entrypoint.
    """

    return _run_benchmark(reference, cases=None, include_detector_liveness=True)


def run_grounding_benchmark_for_contract_testing(
    reference: CredalReference,
    *,
    cases: Sequence[GroundingBenchmarkCase] | None = None,
) -> GroundingBenchmarkScoreboard:
    """Run CG6 with validator-scoped case injection and broken-stack probes."""

    return _run_benchmark(reference, cases=cases, include_detector_liveness=True)


def build_grounding_benchmark_live_slice_for_contract_testing(
    *,
    representative_reference: CredalReference,
    live_reference: CredalReference,
) -> dict[str, Any]:
    """Run the fixed CG6 reality-anchor slice over representative and live CG0."""

    start = time.perf_counter()
    representative = _run_live_slice_world(
        "representative_world",
        representative_reference,
    )
    live = _run_live_slice_world("live_cg0_world", live_reference)
    divergences = _slice_divergences(
        representative["score_slices"],
        live["score_slices"],
    )
    fields = {
        "composition": {
            "representative_cases": representative["case_count"],
            "live_cases": live["case_count"],
            "headline_world": "representative_world",
            "live_slice_role": "reality_anchor_not_headline_denominator",
        },
        "divergences": divergences,
        "live": live,
        "representative": representative,
        "scope": (
            "fixed one-case-per-decisive-class slice over the live CG0 reference; "
            "it anchors substrate divergence but does not replace the representative "
            "headline denominator"
        ),
    }
    content_hash = gy_content_hash(_without_volatile_latency(fields))
    return {
        "content_hash": content_hash,
        "latency_ms": _elapsed_ms(start),
        **fields,
    }


def build_grounding_benchmark_reference_for_contract_testing() -> CredalReference:
    """Return an owner-shaped synthetic CG0 reference for unit/contract tests."""

    edges = [
        _operator_edge("tax_relief_rate", minimum=0.0, maximum=0.5, unit="ratio"),
        _target_edge("tax_relief_rate", "global.tax_rate"),
        _lex_edge("tax_relief_statute", "tax_relief_rate"),
        _operator_edge("budget_allocation_multiplier", minimum=0.0, maximum=2.0, unit="ratio"),
        _target_edge("budget_allocation_multiplier", "government.balance"),
        _lex_edge("budget_law", "budget_allocation_multiplier"),
        _operator_edge("procurement_shock_intensity", minimum=0.0, maximum=1.0, unit="ratio"),
        _target_edge("procurement_shock_intensity", "cells.distress_score"),
        _lex_edge("procurement_decree", "procurement_shock_intensity"),
        _operator_edge("household_transfer", minimum=0.0, maximum=1.0, unit="ratio"),
        _target_edge("household_transfer", "household_cells.transfer_intensity"),
        _world_slot("global.tax_rate", unit="ratio", slot_role="policy_input"),
        _world_slot("government.balance", unit="usd", slot_role="policy_input"),
        _world_slot("cells.distress_score", unit="ratio", slot_role="policy_input"),
        _world_slot("cells.output", unit="usd", slot_role="outcome"),
        _world_slot("cells.employment", unit="count", slot_role="outcome"),
        _world_slot("household_cells.disposable_income", unit="usd", slot_role="outcome"),
        _world_slot("household_cells.transfer_intensity", unit="ratio", slot_role="policy_input"),
        _world_slot("community.resilience_index", unit="ratio", slot_role="policy_input"),
        _world_slot(
            "household_cells.energy_security",
            unit="security_index",
            slot_role="policy_input",
        ),
        _world_slot(
            "household_cells.food_security",
            unit="food_security_index",
            slot_role="policy_input",
        ),
        _policy_slot("tax_policy_slot", "global.tax_rate"),
        _policy_slot("budget_policy_slot", "government.balance"),
        _policy_slot("distress_policy_slot", "cells.distress_score"),
        _policy_slot("transfer_policy_slot", "household_cells.transfer_intensity"),
        _policy_slot("resilience_policy_slot", "community.resilience_index"),
        _policy_slot("energy_policy_slot", "household_cells.energy_security"),
        _policy_slot("food_policy_slot", "household_cells.food_security"),
        _causal_edge("global_tax_balance", "global.tax_rate", "government.balance"),
        _causal_edge("budget_income", "government.balance", "household_cells.disposable_income"),
        _causal_edge("distress_output", "cells.distress_score", "cells.output"),
        _causal_edge(
            "transfer_income",
            "household_cells.transfer_intensity",
            "household_cells.disposable_income",
        ),
        _causal_edge("resilience_output", "community.resilience_index", "cells.output"),
        _causal_edge(
            "energy_income",
            "household_cells.energy_security",
            "household_cells.disposable_income",
        ),
        _causal_edge(
            "food_income",
            "household_cells.food_security",
            "household_cells.disposable_income",
        ),
        _text_only_mechanism_edge(
            "fabricated_tax_output_text",
            mentioned_source="global.tax_rate",
            mentioned_outcome="cells.output",
        ),
    ]
    return _reference_from_edges(edges, versions_suffix="contract")


def validate_grounding_benchmark_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a scoreboard payload and return stable issue codes."""

    issues: list[str] = []
    try:
        scoreboard = GroundingBenchmarkScoreboard.model_validate(payload)
    except Exception as exc:
        message = str(exc)
        for code in (
            "grounding_benchmark_content_hash_mismatch",
            "grounding_benchmark_id_mismatch",
            "grounding_benchmark_headline_growth_missing",
            "grounding_benchmark_slice_epoch_missing",
        ):
            if code in message:
                issues.append(code)
        scoreboard = None
    raw_headline = payload.get("headline") if isinstance(payload, Mapping) else None
    if isinstance(raw_headline, Mapping) and int(raw_headline.get("growth_epoch_count") or 0) < 2:
        issues.append("grounding_benchmark_headline_growth_missing")
    raw_scores = payload.get("score_slices") if isinstance(payload, Mapping) else None
    if isinstance(raw_scores, Sequence) and any(
        isinstance(row, Mapping) and not row.get("epoch_id") for row in raw_scores
    ):
        issues.append("grounding_benchmark_slice_epoch_missing")
    for baseline_id, raw_config in _mapping(payload.get("baseline_configs")).items():
        if not isinstance(raw_config, Mapping):
            issues.append("grounding_benchmark_baseline_config_invalid")
            continue
        expected_hash = _baseline_config_hash(raw_config)
        if raw_config.get("config_hash") != expected_hash:
            issues.append("grounding_benchmark_baseline_config_hash_mismatch")
        if raw_config.get("expected_config_hash") != expected_hash:
            issues.append("grounding_benchmark_baseline_expected_hash_mismatch")
        if (
            baseline_id == "exact_match_alias_table"
            and raw_config.get("alias_table_hash") != _alias_table_hash()
        ):
            issues.append("grounding_benchmark_baseline_config_hash_mismatch")
    if scoreboard is not None:
        if not scoreboard.detector_liveness:
            issues.append("grounding_benchmark_detector_liveness_missing")
        if any(
            row.variant_id != "working_stack" and row.detection_floor == "not_applicable"
            for row in scoreboard.detector_liveness
        ):
            issues.append("grounding_benchmark_detector_liveness_floor_missing")
        if (
            not scoreboard.calibration_anchor_set
            or scoreboard.calibration_anchor_set.wired_into_cg2
        ):
            issues.append("grounding_benchmark_calibration_wired")
        if not scoreboard.latency_bound_asserted:
            issues.append("grounding_benchmark_latency_bound_not_asserted")
    return {
        "status": "pass" if not issues else "fail",
        "issue_codes": sorted(set(issues)),
    }


def recompute_grounding_benchmark_scoreboard_hash(
    scoreboard_or_payload: GroundingBenchmarkScoreboard | Mapping[str, Any],
) -> str:
    """Recompute scoreboard content hash."""

    payload = (
        scoreboard_or_payload.model_dump(mode="json")
        if isinstance(scoreboard_or_payload, BaseModel)
        else _json_ready(scoreboard_or_payload)
    )
    body = dict(_mapping(payload))
    body.pop("benchmark_id", None)
    body.pop("content_hash", None)
    return gy_content_hash(_without_volatile_latency(body))


def _run_benchmark(
    reference: CredalReference,
    *,
    cases: Sequence[GroundingBenchmarkCase] | None,
    include_detector_liveness: bool,
) -> GroundingBenchmarkScoreboard:
    epoch_records, references = _growth_references(reference)
    generated_cases = tuple(cases) if cases is not None else _assemble_cases(references)
    valid_cases, dropped_cases = _partition_derivable_cases(generated_cases, references)
    baseline_configs = _baseline_configs()
    decisions = _run_decisions(valid_cases, references, baseline_configs)
    score_slices = _score_decisions(generated_cases, dropped_cases, decisions)
    headline = _headline(score_slices)
    calibration = _calibration_anchor_set(reference, generated_cases)
    detector = (
        _detector_liveness(valid_cases, references)
        if include_detector_liveness
        else ()
    )
    findings = _findings(score_slices, generated_cases, decisions, detector)
    summary = {
        "case_count": len(generated_cases),
        "decision_count": len(decisions),
        "dropped_underivable_cases": len(dropped_cases),
        "score_slice_count": len(score_slices),
        "committed_composition": {
            "representative_cases": len(generated_cases),
            "live_cases": 0,
            "headline_world": "representative_world",
            "live_slice": "validator_payload_distinct_reality_anchor",
        },
        "scope_note": (
            "Deterministic representative full-reference slice. The selector is "
            "content-hash based and not caller configurable."
        ),
    }
    latency_bound_ms = 30_000.0
    latency_bound_asserted = all(decision.latency_ms <= latency_bound_ms for decision in decisions)
    raw_payload = {
        "baseline_configs": {
            key: value.model_dump(mode="json") for key, value in baseline_configs.items()
        },
        "calibration_anchor_set": calibration.model_dump(mode="json"),
        "cases": [case.model_dump(mode="json") for case in generated_cases],
        "decisions": [decision.model_dump(mode="json") for decision in decisions],
        "detector_liveness": [row.model_dump(mode="json") for row in detector],
        "dropped_cases": [case.model_dump(mode="json") for case in dropped_cases],
        "findings": list(findings),
        "generation_scope": {
            "case_selector": "seeded_content_hash_representative_slice",
            "contract_fixture_disjointness": "asserted_by_validator",
            "dense_embeddings": "missing_documented_duckdb_fts_proxy",
            "llm_judge": "honestly_unavailable_without_recorded_judgments",
            "public_knobs": [],
            "seed": DEFAULT_BENCHMARK_SEED,
        },
        "growth_epochs": [row.model_dump(mode="json") for row in epoch_records],
        "headline": headline.model_dump(mode="json"),
        "latency_bound_asserted": latency_bound_asserted,
        "latency_bound_ms": latency_bound_ms,
        "pattern_pass": {
            "relevant_ids": ["P01", "P03", "P05", "P10", "P15", "P27", "P29", "P32", "P33"],
            "target_correct_pattern": (
                "real CGF replay over owner-derived cases; no hand-authored labels; "
                "growth headline mandatory"
            ),
            "missing_capability_labels": [],
            "acceptance_signal": (
                "scoreboard recomputes, corrupt-field drift goes red, and broken-stack "
                "variants degrade the headline"
            ),
        },
        "private_streams": {
            "private": "deferred_no_private_denominator_owner_declared",
            "retroactive_denominator": "deferred_until_retroactive_denominator_owner_exists",
        },
        "reference_epoch": reference.reference_epoch,
        "reference_hash": reference.reference_hash,
        "schema_version": GROUNDING_BENCHMARK_SCHEMA_VERSION,
        "score_slices": [row.model_dump(mode="json") for row in score_slices],
        "seed": DEFAULT_BENCHMARK_SEED,
        "summary": summary,
        "validator_version": GROUNDING_BENCHMARK_VALIDATOR_VERSION,
    }
    content_hash = gy_content_hash(_without_volatile_latency(raw_payload))
    return GroundingBenchmarkScoreboard(
        benchmark_id=f"cg6_benchmark_{content_hash.removeprefix('sha256:')[:16]}",
        content_hash=content_hash,
        **raw_payload,
    )


def _assemble_cases(
    references: Mapping[str, CredalReference],
) -> tuple[GroundingBenchmarkCase, ...]:
    cases: list[GroundingBenchmarkCase] = []
    base = references["epoch_0"]
    base_atoms = _selected_atoms(base, limit=5)
    if not base_atoms:
        return ()
    for index, atom in enumerate(base_atoms):
        cases.append(
            _case_from_atom(atom, "seed_anchors", "registered_alias_anchor", "epoch_0", index)
        )
    for index, atom in enumerate(reversed(base_atoms)):
        cases.append(_case_from_atom(atom, "calibration", "held_out_anchor", "epoch_0", index))
    for index, atom in enumerate(base_atoms):
        cases.extend(
            [
                _false_analog_case(atom, "epoch_0", index),
                _name_collision_false_analog_case(atom, "epoch_0", index),
                _high_lexical_similarity_false_analog_case(atom, "epoch_0", index),
                _compositional_case(atom, "epoch_0", index),
                _cross_modal_inconsistent_case(atom, "epoch_0", index),
                _joint_type_inconsistent_case(atom, "epoch_0", index),
                _adversarial_mimic_case(atom, "epoch_0", index),
            ]
        )
    cases.append(_unknown_case(base_atoms[0], "epoch_0"))
    cases.append(_fabricated_mechanism_hallucination_case(base_atoms[0], "epoch_0"))
    cases.extend(
        [
            _novel_case(
                "energy_security_transfer",
                "household_cells.energy_security",
                "household_cells.disposable_income",
                "epoch_0",
                unit="security_index",
                owner_refs=(
                    "WMR_WORLD_SLOT::household_cells.energy_security",
                    "L2_CAUSAL_CLAIM::energy_income",
                ),
                index=0,
            ),
            _novel_case(
                "food_security_transfer",
                "household_cells.food_security",
                "household_cells.disposable_income",
                "epoch_0",
                unit="food_security_index",
                owner_refs=(
                    "WMR_WORLD_SLOT::household_cells.food_security",
                    "L2_CAUSAL_CLAIM::food_income",
                ),
                index=1,
            ),
            _novel_case(
                "community_resilience_grant",
                "community.resilience_index",
                "cells.output",
                "epoch_0",
                unit="ratio",
                owner_refs=(
                    "WMR_WORLD_SLOT::community.resilience_index",
                    "L2_CAUSAL_CLAIM::resilience_output",
                ),
                index=2,
            ),
            _novel_case(
                "transfer_income_bonus",
                "household_cells.transfer_intensity",
                "household_cells.disposable_income",
                "epoch_0",
                unit="bonus_index",
                owner_refs=(
                    "WMR_WORLD_SLOT::household_cells.transfer_intensity",
                    "L2_CAUSAL_CLAIM::transfer_income",
                ),
                index=3,
            ),
            _novel_case(
                "distress_reduction_program",
                "cells.distress_score",
                "cells.output",
                "epoch_0",
                unit="program_intensity",
                owner_refs=(
                    "WMR_WORLD_SLOT::cells.distress_score",
                    "L2_CAUSAL_CLAIM::distress_output",
                ),
                index=4,
            ),
        ]
    )
    for epoch_id in ("epoch_1", "epoch_2"):
        atoms = _selected_atoms(references[epoch_id], limit=5)
        new_atoms = [
            atom
            for atom in atoms
            if str(atom.signature.op or "").startswith(("energy_", "food_"))
        ]
        selected = new_atoms[0] if new_atoms else atoms[0]
        cases.append(_case_from_atom(selected, "growth", "new_lever_loop_closure", epoch_id, 0))
        cases.append(_adversarial_mimic_case(selected, epoch_id, 0, stream="growth"))
        cases.append(_false_analog_case(selected, epoch_id, 1, stream="growth"))
    unique = {case.case_hash: case for case in cases}
    return tuple(sorted(unique.values(), key=lambda case: case.case_id))


def _run_live_slice_world(label: str, reference: CredalReference) -> dict[str, Any]:
    cases = _live_slice_cases(reference)
    refs = {"epoch_0": reference}
    valid, dropped = _partition_derivable_cases(cases, refs)
    baseline_configs = _baseline_configs()
    decisions = _run_decisions(valid, refs, baseline_configs)
    score_slices = _score_decisions(cases, dropped, decisions)
    atoms = _selected_atoms(reference, limit=50)
    alias_hash = _alias_table_hash()
    return {
        "alias_table_hash": alias_hash,
        "atom_universe_size_sampled": len(atoms),
        "case_count": len(cases),
        "decision_count": len(decisions),
        "dropped_cases": [row.model_dump(mode="json") for row in dropped],
        "edge_count": len(reference.essential_edges),
        "fts_behavior": (
            "GroundingRelationEngine DuckDB FTS-backed retrieval reused per run context"
        ),
        "label": label,
        "reference_epoch": reference.reference_epoch,
        "reference_hash": reference.reference_hash,
        "score_slices": [row.model_dump(mode="json") for row in score_slices],
        "selected_case_families": [case.family for case in cases],
        "summary_by_baseline": _summarize_score_slices(score_slices),
    }


def _live_slice_cases(reference: CredalReference) -> tuple[GroundingBenchmarkCase, ...]:
    atoms = _selected_atoms(reference, limit=1)
    if not atoms:
        return ()
    atom = atoms[0]
    cases = [
        _case_from_atom(atom, "seed_anchors", "live_seed_anchor", "epoch_0", 0),
        _false_analog_case(atom, "epoch_0", 0),
        _name_collision_false_analog_case(atom, "epoch_0", 0),
        _adversarial_mimic_case(atom, "epoch_0", 0),
    ]
    novel = _owner_backed_novel_from_reference(reference)
    if novel is not None:
        cases.append(novel)
    unique = {case.case_hash: case for case in cases}
    return tuple(sorted(unique.values(), key=lambda case: case.case_id))


def _owner_backed_novel_from_reference(
    reference: CredalReference,
) -> GroundingBenchmarkCase | None:
    first_l2_edge: CredalReferenceEdge | None = None
    for edge in sorted(reference.essential_edges.values(), key=lambda item: item.key):
        if edge.modality != "L2_CAUSAL_CLAIM":
            continue
        first_l2_edge = first_l2_edge or edge
        endpoints = _causal_edge_endpoints(edge)
        source = endpoints.get("source") or endpoints.get("src")
        outcome = endpoints.get("outcome") or endpoints.get("dst") or endpoints.get("target")
        if not source or not outcome:
            continue
        slot = reference.essential_edges.get(("WMR_WORLD_SLOT", source))
        if slot is None:
            continue
        unit = slot.unit or "ratio"
        suffix = gy_content_hash(
            {
                "edge": edge.key,
                "reference": reference.reference_hash,
                "seed": DEFAULT_BENCHMARK_SEED,
            }
        ).removeprefix("sha256:")[:8]
        return _novel_case(
            f"cg6_live_owner_backed_novel_{suffix}",
            source,
            outcome,
            "epoch_0",
            unit=unit,
            owner_refs=(f"WMR_WORLD_SLOT::{source}", f"L2_CAUSAL_CLAIM::{edge.edge_id}"),
            index=0,
        )
    if first_l2_edge is None:
        return None
    slots = [
        edge
        for edge in sorted(reference.essential_edges.values(), key=lambda item: item.key)
        if edge.modality == "WMR_WORLD_SLOT"
    ]
    if len(slots) < 2:
        return None
    target_slot = next(
        (edge for edge in slots if edge.edge_id in {"global.tax_rate", "cells.distress_score"}),
        slots[0],
    )
    outcome_slot = next(
        (edge for edge in slots if edge.edge_id != target_slot.edge_id),
        slots[-1],
    )
    suffix = gy_content_hash(
        {
            "edge": first_l2_edge.key,
            "fallback": "resolvable_live_owner_refs_no_l2_endpoints",
            "reference": reference.reference_hash,
            "slot": target_slot.key,
            "seed": DEFAULT_BENCHMARK_SEED,
        }
    ).removeprefix("sha256:")[:8]
    return _novel_case(
        f"cg6_live_owner_ref_novel_{suffix}",
        target_slot.edge_id,
        outcome_slot.edge_id,
        "epoch_0",
        unit=target_slot.unit or "ratio",
        owner_refs=(
            f"WMR_WORLD_SLOT::{target_slot.edge_id}",
            f"L2_CAUSAL_CLAIM::{first_l2_edge.edge_id}",
        ),
        index=1,
    )
    return None


def _causal_edge_endpoints(edge: CredalReferenceEdge) -> dict[str, str]:
    for completion in edge.admissible_completions:
        value = _mapping(completion.value)
        if value:
            return {str(key): str(item) for key, item in value.items() if item is not None}
    return {}


def _summarize_score_slices(score_slices: Sequence[ScoreSlice]) -> dict[str, Any]:
    by_baseline: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "false_bind": 0,
            "hallucination_admit": 0,
            "confident_wrong": 0,
            "useful_recall_num": 0,
            "useful_recall_den": 0,
            "denominator": 0,
        }
    )
    for row in score_slices:
        summary = by_baseline[row.baseline_id]
        summary["false_bind"] += row.false_bind.numerator
        summary["hallucination_admit"] += row.hallucination_admit.numerator
        summary["confident_wrong"] += row.confident_wrong.numerator
        summary["denominator"] += row.confident_wrong.denominator
        summary["useful_recall_num"] += row.useful_recall.numerator
        summary["useful_recall_den"] += row.useful_recall.denominator
    return {
        baseline: {
            **values,
            "confident_wrong_rate": round(
                values["confident_wrong"] / values["denominator"],
                12,
            )
            if values["denominator"]
            else 0.0,
            "useful_recall_rate": round(
                values["useful_recall_num"] / values["useful_recall_den"],
                12,
            )
            if values["useful_recall_den"]
            else 0.0,
        }
        for baseline, values in sorted(by_baseline.items())
    }


def _slice_divergences(
    representative_slices: Sequence[Mapping[str, Any]],
    live_slices: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    rep = {
        (row["baseline_id"], row["stream"], row["family"]): row
        for row in representative_slices
    }
    live = {
        (row["baseline_id"], row["stream"], row["family"]): row
        for row in live_slices
    }
    out: list[dict[str, Any]] = []
    for key in sorted(set(rep) & set(live)):
        rep_row = rep[key]
        live_row = live[key]
        fields = ("false_bind", "hallucination_admit", "confident_wrong", "useful_recall")
        if any(
            rep_row[field]["numerator"] != live_row[field]["numerator"]
            or rep_row[field]["denominator"] != live_row[field]["denominator"]
            for field in fields
        ):
            out.append(
                {
                    "baseline_id": key[0],
                    "stream": key[1],
                    "family": key[2],
                    "representative": {field: rep_row[field] for field in fields},
                    "live": {field: live_row[field] for field in fields},
                }
            )
    return tuple(out)


@dataclass(slots=True)
class _BenchmarkRunContext:
    """Per-run engine cache; avoids rebuilding FTS and CGF engines per decision."""

    relation_engines: dict[tuple[str, str], GroundingRelationEngine] = field(
        default_factory=dict
    )
    bind_gates: dict[str, GroundingBindGate] = field(default_factory=dict)
    admission_engines: dict[str, GroundingAdmissionEngine] = field(default_factory=dict)
    phrasing_engines: dict[str, GroundingPhrasingDefenseEngine] = field(
        default_factory=dict
    )

    def relation_engine(
        self,
        reference: CredalReference,
        policy: GroundingEnginePolicy | None = None,
    ) -> GroundingRelationEngine:
        key = (reference.reference_hash, _relation_policy_key(policy))
        engine = self.relation_engines.get(key)
        if engine is None:
            engine = GroundingRelationEngine(reference, policy=policy)
            self.relation_engines[key] = engine
        return engine

    def bind_gate(self, reference: CredalReference) -> GroundingBindGate:
        gate = self.bind_gates.get(reference.reference_hash)
        if gate is None:
            gate = GroundingBindGate(reference)
            self.bind_gates[reference.reference_hash] = gate
        return gate

    def admission_engine(self, reference: CredalReference) -> GroundingAdmissionEngine:
        engine = self.admission_engines.get(reference.reference_hash)
        if engine is None:
            engine = GroundingAdmissionEngine(reference)
            self.admission_engines[reference.reference_hash] = engine
        return engine

    def phrasing_engine(self, reference: CredalReference) -> GroundingPhrasingDefenseEngine:
        engine = self.phrasing_engines.get(reference.reference_hash)
        if engine is None:
            engine = GroundingPhrasingDefenseEngine(reference)
            self.phrasing_engines[reference.reference_hash] = engine
        return engine


def _relation_policy_key(policy: GroundingEnginePolicy | None) -> str:
    if policy is None:
        return "production"
    return gy_content_hash(policy.model_dump(mode="json"))


def _run_decisions(
    cases: Sequence[GroundingBenchmarkCase],
    references: Mapping[str, CredalReference],
    baseline_configs: Mapping[str, BaselineConfig],
) -> tuple[GroundingBenchmarkDecision, ...]:
    decisions: list[GroundingBenchmarkDecision] = []
    context = _BenchmarkRunContext()
    for case in cases:
        reference = references.get(case.epoch_id) or references["epoch_0"]
        for baseline_id in sorted(baseline_configs):
            decisions.append(
                _run_one_decision(case, reference, baseline_id, context=context)  # type: ignore[arg-type]
            )
    return tuple(decisions)


def _run_one_decision(
    case: GroundingBenchmarkCase,
    reference: CredalReference,
    baseline_id: BaselineId,
    *,
    context: _BenchmarkRunContext | None = None,
) -> GroundingBenchmarkDecision:
    start = time.perf_counter()
    if baseline_id == "passive_abstain":
        return _decision(
            case,
            baseline_id,
            relation="abstain",
            latency_ms=_elapsed_ms(start),
            notes=("always_abstain_floor",),
        )
    if baseline_id == "llm_judge_recorded_replay":
        return _decision(
            case,
            baseline_id,
            relation="unavailable",
            latency_ms=_elapsed_ms(start),
            notes=("honestly_unavailable_no_recorded_judgments_for_case_family",),
        )
    if baseline_id == "entity_linker_recorded_replay":
        return _decision(
            case,
            baseline_id,
            relation="unavailable",
            latency_ms=_elapsed_ms(start),
            notes=("honestly_unavailable_no_entity_linker_recordings_or_service",),
        )
    if baseline_id == "exact_match_alias_table":
        return _exact_match_decision(case, reference, start, context=context)
    if baseline_id == "lexical_similarity_duckdb_fts_top1":
        return _lexical_decision(case, reference, start, context=context)
    if baseline_id == "greedy_per_axis":
        return _greedy_decision(
            case,
            reference,
            start,
            context=context,
        )
    return _cgf_decision(
        case,
        reference,
        start,
        baseline_id="full_cgf_stack",
        context=context,
    )


def _cgf_decision(
    case: GroundingBenchmarkCase,
    reference: CredalReference,
    start: float,
    *,
    baseline_id: BaselineId,
    context: _BenchmarkRunContext | None = None,
    relation_policy: GroundingEnginePolicy | None = None,
    bind_gate: GroundingBindGate | None = None,
    admission_engine: GroundingAdmissionEngine | None = None,
    calibration_ledger: GroundingCalibrationLedger | None = None,
) -> GroundingBenchmarkDecision:
    context = context or _BenchmarkRunContext()
    relation_engine = context.relation_engine(reference, relation_policy)
    cg1 = relation_engine.certificate_for(case.proposal, proposal_id=case.case_id)
    cg2_gate = bind_gate or context.bind_gate(reference)
    cg2 = cg2_gate.certificate_for(cg1, calibration_ledger=calibration_ledger)
    cg3_engine = admission_engine or context.admission_engine(reference)
    cg3 = cg3_engine.decide(cg2, cg1_certificate=cg1)
    cg4 = context.phrasing_engine(reference)
    pipeline_run = cg4.run_pipeline(case.proposal, proposal_id=f"{case.case_id}.cg4")
    risk = cg4.detect_proxy_gap(pipeline_run)
    chain = (
        CertificateReplayRef(
            certificate_id=cg1.certificate_id,
            content_hash=cg1.content_hash,
            component="CG1",
        ),
        CertificateReplayRef(
            certificate_id=cg2.certificate_id,
            content_hash=cg2.content_hash,
            component="CG2",
        ),
        CertificateReplayRef(
            certificate_id=cg3.certificate_id,
            content_hash=cg3.content_hash,
            component="CG3",
        ),
    )
    return _decision(
        case,
        baseline_id,
        relation=cg1.selected_relation,
        selected_atom_id=_selected_atom_id(cg1),
        bind_decision=cg2.decision,
        admission_decision=cg3.decision,
        admission_reason=cg3.decisive_reason,
        quarantined=risk is not None,
        certificate_chain=chain,
        replay_complete=True,
        latency_ms=_elapsed_ms(start),
        notes=(
            "cg2_production_freeze_applies_to_bind; useful_recall_counts_relation_level",
        )
        if baseline_id == "full_cgf_stack"
        else (),
    )


def _greedy_decision(
    case: GroundingBenchmarkCase,
    reference: CredalReference,
    start: float,
    *,
    context: _BenchmarkRunContext | None = None,
) -> GroundingBenchmarkDecision:
    context = context or _BenchmarkRunContext()
    policy = GroundingEnginePolicy(use_greedy_solver=True)
    cg1 = context.relation_engine(reference, policy).certificate_for(
        case.proposal,
        proposal_id=f"{case.case_id}.greedy",
    )
    chain = (
        CertificateReplayRef(
            certificate_id=cg1.certificate_id,
            content_hash=cg1.content_hash,
            component="CG1.greedy_per_axis",
        ),
    )
    return _decision(
        case,
        "greedy_per_axis",
        relation=cg1.selected_relation,
        selected_atom_id=_selected_atom_id(cg1),
        certificate_chain=chain,
        replay_complete=True,
        latency_ms=_elapsed_ms(start),
        notes=("greedy_identification_only_no_cg2_cg3_safety",),
    )


def _exact_match_decision(
    case: GroundingBenchmarkCase,
    reference: CredalReference,
    start: float,
    *,
    context: _BenchmarkRunContext | None = None,
) -> GroundingBenchmarkDecision:
    parsed = parse_n4_proposal(case.proposal, proposal_id=case.case_id, reference=reference)
    signature = parsed.hypotheses[0].signature
    proposal_op = _canonical_operator(signature.op)
    proposal_target = signature.X_do[0] if signature.X_do else ""
    selected_atom_id = None
    relation = "abstain"
    context = context or _BenchmarkRunContext()
    for atom in context.relation_engine(reference).reference_atoms:
        if (
            _canonical_operator(atom.signature.op) == proposal_op
            and proposal_target in atom.signature.X_do
        ):
            selected_atom_id = atom.atom_id
            relation = "exact"
            break
    return _decision(
        case,
        "exact_match_alias_table",
        relation=relation,
        selected_atom_id=selected_atom_id,
        latency_ms=_elapsed_ms(start),
        notes=("historical_name_equality_plus_registered_alias_table",),
    )


def _lexical_decision(
    case: GroundingBenchmarkCase,
    reference: CredalReference,
    start: float,
    *,
    context: _BenchmarkRunContext | None = None,
) -> GroundingBenchmarkDecision:
    context = context or _BenchmarkRunContext()
    engine = context.relation_engine(reference)
    parsed = parse_n4_proposal(case.proposal, proposal_id=case.case_id, reference=reference)
    candidates = engine.retrieve_candidates(parsed, include_adversarial_countercandidates=False)
    if not candidates:
        return _decision(
            case,
            "lexical_similarity_duckdb_fts_top1",
            relation="abstain",
            latency_ms=_elapsed_ms(start),
            notes=("duckdb_fts_no_hit",),
        )
    selected = sorted(
        candidates,
        key=lambda item: (
            -item.retrieval_score,
            grounding_candidate_semantic_sort_key(item),
        ),
    )[0]
    return _decision(
        case,
        "lexical_similarity_duckdb_fts_top1",
        relation="exact",
        selected_atom_id=selected.atom_id,
        latency_ms=_elapsed_ms(start),
        notes=("duckdb_fts_top1_proxy_for_missing_dense_embeddings",),
    )


def _decision(
    case: GroundingBenchmarkCase,
    baseline_id: BaselineId,
    *,
    relation: str,
    latency_ms: float,
    selected_atom_id: str | None = None,
    bind_decision: str = "abstain",
    admission_decision: str = "not_applicable",
    admission_reason: str | None = None,
    quarantined: bool = False,
    certificate_chain: tuple[CertificateReplayRef, ...] = (),
    replay_complete: bool | None = None,
    notes: tuple[str, ...] = (),
) -> GroundingBenchmarkDecision:
    return GroundingBenchmarkDecision(
        case_id=case.case_id,
        case_hash=case.case_hash,
        baseline_id=baseline_id,
        epoch_id=case.epoch_id,
        stream=case.stream,
        family=case.family,
        relation=relation,
        selected_atom_id=selected_atom_id,
        bind_decision=bind_decision,
        admission_decision=admission_decision,
        admission_reason=admission_reason,
        quarantined=quarantined,
        certificate_chain=certificate_chain,
        replay_complete=bool(certificate_chain) if replay_complete is None else replay_complete,
        latency_ms=latency_ms,
        decision_notes=notes,
    )


def _score_decisions(
    all_cases: Sequence[GroundingBenchmarkCase],
    dropped_cases: Sequence[DroppedBenchmarkCase],
    decisions: Sequence[GroundingBenchmarkDecision],
) -> tuple[ScoreSlice, ...]:
    cases_by_id = {case.case_id: case for case in all_cases}
    dropped_counts: dict[tuple[str, str, str], int] = defaultdict(int)
    total_counts: dict[tuple[str, str, str], int] = defaultdict(int)
    for case in all_cases:
        key = (case.epoch_id, case.stream, case.family)
        total_counts[key] += 1
    for dropped in dropped_cases:
        dropped_counts[(dropped.epoch_id, dropped.stream, dropped.family)] += 1

    by_slice: dict[tuple[str, str, str, str], list[GroundingBenchmarkDecision]] = (
        defaultdict(list)
    )
    for decision in decisions:
        slice_key = (
            decision.baseline_id,
            decision.epoch_id,
            decision.stream,
            decision.family,
        )
        by_slice[slice_key].append(decision)
    rows: list[ScoreSlice] = []
    baselines = sorted({decision.baseline_id for decision in decisions} | set(_baseline_configs()))
    groups = sorted(total_counts)
    for baseline in baselines:
        for epoch_id, stream, family in groups:
            slice_decisions = by_slice.get((baseline, epoch_id, stream, family), [])
            slice_cases = [
                cases_by_id[decision.case_id]
                for decision in slice_decisions
                if decision.case_id in cases_by_id
            ]
            false_bind = sum(
                _is_false_bind(case, decision)
                for case, decision in zip(slice_cases, slice_decisions, strict=True)
            )
            hallucination = sum(
                _is_hallucination_admit(case, decision)
                for case, decision in zip(slice_cases, slice_decisions, strict=True)
            )
            useful_num, useful_den = _useful_recall_counts(slice_cases, slice_decisions)
            novel_num, novel_den = _novel_precision_counts(slice_cases, slice_decisions)
            abstain_num, abstain_den = _abstention_counts(slice_cases, slice_decisions)
            quarantine_num, quarantine_den = _quarantine_counts(slice_cases, slice_decisions)
            replay_num = sum(1 for decision in slice_decisions if decision.replay_complete)
            latencies = sorted(decision.latency_ms for decision in slice_decisions)
            total = total_counts[(epoch_id, stream, family)]
            dropped = dropped_counts[(epoch_id, stream, family)]
            evaluated = len(slice_decisions)
            rows.append(
                ScoreSlice(
                    baseline_id=baseline,  # type: ignore[arg-type]
                    epoch_id=epoch_id,
                    stream=stream,  # type: ignore[arg-type]
                    family=family,
                    total_cases=total,
                    evaluated_cases=evaluated,
                    dropped_cases=dropped,
                    false_bind=_interval(false_bind, evaluated + dropped),
                    hallucination_admit=_interval(hallucination, evaluated + dropped),
                    confident_wrong=_interval(false_bind + hallucination, evaluated + dropped),
                    useful_recall=_interval(useful_num, useful_den),
                    novel_admission_precision=_interval(novel_num, novel_den),
                    correct_abstention=_interval(abstain_num, abstain_den),
                    quarantine_capture=_interval(quarantine_num, quarantine_den),
                    certificate_replay_completeness=_interval(replay_num, evaluated + dropped),
                    latency_ms_p50=_percentile(latencies, 50.0),
                    latency_ms_max=max(latencies) if latencies else 0.0,
                )
            )
    return tuple(rows)


def _headline(score_slices: Sequence[ScoreSlice]) -> BenchmarkHeadline:
    growth = [
        row
        for row in score_slices
        if row.baseline_id == _CGF_BASELINE and row.stream == "growth"
    ]
    false_num = sum(row.false_bind.numerator for row in growth)
    false_den = sum(row.false_bind.denominator for row in growth)
    hall_num = sum(row.hallucination_admit.numerator for row in growth)
    hall_den = sum(row.hallucination_admit.denominator for row in growth)
    return BenchmarkHeadline(
        growth_epoch_count=len({row.epoch_id for row in growth}),
        false_bind=_interval(false_num, false_den),
        hallucination_admit=_interval(hall_num, hall_den),
        confident_wrong=_interval(false_num + hall_num, max(false_den, hall_den)),
        denominator_note=(
            "Growth headline denominator is every full-CGF growth-stream case across "
            "growth epochs, including dropped/underivable cases."
        ),
    )


def _detector_liveness(
    cases: Sequence[GroundingBenchmarkCase],
    references: Mapping[str, CredalReference],
) -> tuple[DetectorLivenessRecord, ...]:
    probe_cases = tuple(
        case
        for case in cases
        if case.stream in {"stress", "growth"}
        and ("must-" in case.obligation_labels or "hallucination-" in case.obligation_labels)
    )
    working = _variant_counts("working_stack", probe_cases, references)
    records = [working]
    records.append(
        _variant_counts(
            "cg1_critical_veto_disabled_only",
            probe_cases,
            references,
            relation_policy=GroundingEnginePolicy(disable_critical_veto=True),
            mutation_switches=("GroundingEnginePolicy.disable_critical_veto",),
            working=working,
        )
    )
    records.append(
        _variant_counts(
            "cg1_critical_veto_disabled_stacked_similarity",
            probe_cases,
            references,
            relation_policy=GroundingEnginePolicy(
                disable_critical_veto=True,
                allow_surface_similarity_exact=True,
            ),
            mutation_switches=(
                "GroundingEnginePolicy.disable_critical_veto",
                "GroundingEnginePolicy.allow_surface_similarity_exact",
            ),
            working=working,
        )
    )
    records.append(
        _variant_counts(
            "cg3_disable_do_path_resolution_only",
            probe_cases,
            references,
            admission_engine_factory=lambda ref: GroundingAdmissionEngine.for_contract_testing(
                ref,
                disable_do_path_resolution=True,
            ),
            mutation_switches=("GroundingAdmissionEngine.disable_do_path_resolution",),
            working=working,
        )
    )
    records.append(
        _variant_counts(
            "cg3_disable_mechanism_witness_resolution_only",
            probe_cases,
            references,
            admission_engine_factory=lambda ref: GroundingAdmissionEngine.for_contract_testing(
                ref,
                substrate_registry=_unsafe_causal_substrate_registry(),
                disable_mechanism_witness_resolution=True,
            ),
            mutation_switches=(
                "GroundingAdmissionEngine.disable_mechanism_witness_resolution",
            ),
            working=working,
        )
    )
    records.append(
        _variant_counts(
            "cg3_disable_denotation_novelty_only",
            probe_cases,
            references,
            admission_engine_factory=lambda ref: GroundingAdmissionEngine.for_contract_testing(
                ref,
                disable_denotation_novelty=True,
            ),
            mutation_switches=("GroundingAdmissionEngine.disable_denotation_novelty",),
            working=working,
        )
    )
    records.append(
        _variant_counts(
            "cg3_disable_stable_unique_only",
            probe_cases,
            references,
            admission_engine_factory=lambda ref: GroundingAdmissionEngine.for_contract_testing(
                ref,
                disable_stable_unique=True,
            ),
            mutation_switches=("GroundingAdmissionEngine.disable_stable_unique",),
            working=working,
        )
    )
    records.append(
        _variant_counts(
            "cg3_allow_substrate_registry_authority_only",
            probe_cases,
            references,
            admission_engine_factory=lambda ref: GroundingAdmissionEngine.for_contract_testing(
                ref,
                substrate_registry=_unsafe_causal_substrate_registry(),
                allow_substrate_registry_authority=True,
            ),
            mutation_switches=(
                "GroundingAdmissionEngine.allow_substrate_registry_authority",
            ),
            working=working,
        )
    )
    records.append(
        _variant_counts(
            "cg3_mechanism_witness_trust_restored_stacked",
            probe_cases,
            references,
            admission_engine_factory=lambda ref: GroundingAdmissionEngine.for_contract_testing(
                ref,
                substrate_registry=_unsafe_causal_substrate_registry(),
                disable_do_path_resolution=True,
                disable_mechanism_witness_resolution=True,
                disable_denotation_novelty=True,
                disable_stable_unique=True,
                allow_substrate_registry_authority=True,
                allow_policy_map_mention_actuatability=True,
                use_best_edge_trust=True,
            ),
            mutation_switches=(
                "GroundingAdmissionEngine.disable_do_path_resolution",
                "GroundingAdmissionEngine.disable_mechanism_witness_resolution",
                "GroundingAdmissionEngine.disable_denotation_novelty",
                "GroundingAdmissionEngine.allow_substrate_registry_authority",
            ),
            working=working,
        )
    )
    records.append(
        _variant_counts(
            "cg2_calibration_owner_validation_bypassed_only",
            (*probe_cases, *_cg2_liveness_attack_cases(references["epoch_0"])),
            references,
            bind_gate_factory=lambda ref: GroundingBindGate.for_contract_testing(
                ref,
                calibration_seed_anchor=True,
                disable_calibration_owner_validation=True,
            ),
            calibration_ledger_factory=_fabricated_calibration_ledger,
            mutation_switches=(
                "GroundingBindGate.disable_calibration_owner_validation",
            ),
            working=working,
        )
    )
    records.append(
        _variant_counts(
            "cg2_calibration_owner_validation_bypassed_stacked_freeze",
            (*probe_cases, *_cg2_liveness_attack_cases(references["epoch_0"])),
            references,
            bind_gate_factory=lambda ref: GroundingBindGate.for_contract_testing(
                ref,
                calibration_seed_anchor=True,
                disable_calibration_owner_validation=True,
                disable_calibration_freeze=True,
            ),
            mutation_switches=(
                "GroundingBindGate.disable_calibration_owner_validation",
                "GroundingBindGate.disable_calibration_freeze",
            ),
            working=working,
        )
    )
    return tuple(records)


def _variant_counts(
    variant_id: str,
    cases: Sequence[GroundingBenchmarkCase],
    references: Mapping[str, CredalReference],
    *,
    relation_policy: GroundingEnginePolicy | None = None,
    bind_gate_factory: Callable[[CredalReference], GroundingBindGate] | None = None,
    admission_engine_factory: Callable[[CredalReference], GroundingAdmissionEngine]
    | None = None,
    calibration_ledger_factory: Callable[
        [GroundingBenchmarkCase, CredalReference],
        GroundingCalibrationLedger,
    ]
    | None = None,
    mutation_switches: tuple[str, ...] = (),
    working: DetectorLivenessRecord | None = None,
) -> DetectorLivenessRecord:
    false_bind = 0
    hallucination = 0
    context = _BenchmarkRunContext()
    for case in cases:
        reference = references.get(case.epoch_id) or references["epoch_0"]
        start = time.perf_counter()
        bind_gate = bind_gate_factory(reference) if bind_gate_factory else None
        admission = admission_engine_factory(reference) if admission_engine_factory else None
        calibration_ledger = (
            calibration_ledger_factory(case, reference)
            if calibration_ledger_factory is not None
            else None
        )
        decision = _cgf_decision(
            case,
            reference,
            start,
            baseline_id="full_cgf_stack",
            relation_policy=relation_policy,
            bind_gate=bind_gate,
            admission_engine=admission,
            calibration_ledger=calibration_ledger,
            context=context,
        )
        false_bind += _is_false_bind(case, decision)
        hallucination += _is_hallucination_admit(case, decision)
    working_count = (
        working.confident_wrong_count if working is not None else false_bind + hallucination
    )
    confident = false_bind + hallucination
    current_interval = _interval(confident, len(cases))
    working_interval = (
        working.confident_wrong_interval
        if working is not None
        else current_interval
    )
    materially_degraded = (
        current_interval.rate > working_interval.rate
        and current_interval.lower > working_interval.upper
    )
    return DetectorLivenessRecord(
        variant_id=variant_id,
        contract_testing_scope=variant_id != "working_stack",
        mutation_switches=mutation_switches,
        false_bind_count=false_bind,
        hallucination_admit_count=hallucination,
        confident_wrong_count=confident,
        denominator=len(cases),
        working_confident_wrong_count=working_count,
        confident_wrong_interval=current_interval,
        working_confident_wrong_interval=working_interval,
        materiality_rule=(
            "materially_detected iff variant confident-wrong rate is strictly above "
            "working and the variant lower Clopper-Pearson bound exceeds the working "
            "upper bound"
        ),
        materially_degraded=materially_degraded if working is not None else False,
        detection_floor=_detection_floor(
            variant_id,
            mutation_switches,
            current_interval,
            working_interval,
            materially_degraded if working is not None else False,
        ),
    )


def _detection_floor(
    variant_id: str,
    mutation_switches: Sequence[str],
    current: IntervalEstimate,
    working: IntervalEstimate,
    materially_degraded: bool,
) -> Literal[
    "not_applicable",
    "detectable_single",
    "detectable_stacked_only",
    "undetectable",
]:
    if variant_id == "working_stack":
        return "not_applicable"
    if materially_degraded and len(mutation_switches) <= 1:
        return "detectable_single"
    if materially_degraded:
        return "detectable_stacked_only"
    if current.rate > working.rate:
        return "undetectable"
    return "undetectable"


def _cg2_liveness_attack_cases(
    reference: CredalReference,
) -> tuple[GroundingBenchmarkCase, ...]:
    atoms = _selected_atoms(reference, limit=1)
    if not atoms:
        return ()
    attack = _name_collision_false_analog_case(atoms[0], "epoch_0", 919)
    return (
        attack.model_copy(
            update={
                "case_id": f"{attack.case_id}.cg2_owner_validation_attack",
                "family": "cg2_fabricated_caller_calibration_attack",
                "decisive_mechanism_expected": (
                    "cg2_owner_validation_bypass_must_not_accept_caller_calibration"
                ),
            }
        ),
    )


def _is_false_bind(case: GroundingBenchmarkCase, decision: GroundingBenchmarkDecision) -> int:
    if "must-" not in case.obligation_labels:
        return 0
    identified = (
        decision.relation in _IDENTIFYING_RELATIONS
        or decision.bind_decision in _BIND_RELATIONS
    )
    if not identified:
        return 0
    return 1


def _is_hallucination_admit(
    case: GroundingBenchmarkCase,
    decision: GroundingBenchmarkDecision,
) -> int:
    return int(
        "hallucination-" in case.obligation_labels
        and decision.admission_decision == "admit_new_lever"
    )


def _useful_recall_counts(
    cases: Sequence[GroundingBenchmarkCase],
    decisions: Sequence[GroundingBenchmarkDecision],
) -> tuple[int, int]:
    numerator = 0
    denominator = 0
    for case, decision in zip(cases, decisions, strict=True):
        if "must+" in case.obligation_labels:
            denominator += 1
            if decision.relation in _IDENTIFYING_RELATIONS and (
                not case.expected_atom_id or decision.selected_atom_id == case.expected_atom_id
            ):
                numerator += 1
        elif "novel+" in case.obligation_labels:
            denominator += 1
            if decision.admission_decision in {"admit_new_lever", "acquire_then_decide"}:
                numerator += 1
    return numerator, denominator


def _novel_precision_counts(
    cases: Sequence[GroundingBenchmarkCase],
    decisions: Sequence[GroundingBenchmarkDecision],
) -> tuple[int, int]:
    admitted = [
        (case, decision)
        for case, decision in zip(cases, decisions, strict=True)
        if decision.admission_decision == "admit_new_lever"
    ]
    return (
        sum(1 for case, _decision_item in admitted if "novel+" in case.obligation_labels),
        len(admitted),
    )


def _abstention_counts(
    cases: Sequence[GroundingBenchmarkCase],
    decisions: Sequence[GroundingBenchmarkDecision],
) -> tuple[int, int]:
    unknowns = [
        (case, decision)
        for case, decision in zip(cases, decisions, strict=True)
        if "unknown" in case.obligation_labels
    ]
    return (
        sum(
            1
            for _case, decision in unknowns
            if decision.relation not in _IDENTIFYING_RELATIONS
            and decision.bind_decision != "bind"
            and decision.admission_decision != "admit_new_lever"
        ),
        len(unknowns),
    )


def _quarantine_counts(
    cases: Sequence[GroundingBenchmarkCase],
    decisions: Sequence[GroundingBenchmarkDecision],
) -> tuple[int, int]:
    mimics = [
        (case, decision)
        for case, decision in zip(cases, decisions, strict=True)
        if case.family in {"adversarial_mimicry", "registered_lever_mimicry"}
    ]
    return (sum(1 for _case, decision in mimics if decision.quarantined), len(mimics))


def _partition_derivable_cases(
    cases: Sequence[GroundingBenchmarkCase],
    references: Mapping[str, CredalReference],
) -> tuple[tuple[GroundingBenchmarkCase, ...], tuple[DroppedBenchmarkCase, ...]]:
    valid: list[GroundingBenchmarkCase] = []
    dropped: list[DroppedBenchmarkCase] = []
    for case in cases:
        reference = references.get(case.epoch_id) or references["epoch_0"]
        reason = _label_derivation_issue(case, reference)
        if reason:
            dropped.append(
                DroppedBenchmarkCase(
                    case_id=case.case_id,
                    stream=case.stream,
                    family=case.family,
                    epoch_id=case.epoch_id,
                    reason=reason,
                )
            )
        else:
            valid.append(case)
    return tuple(valid), tuple(dropped)


def _label_derivation_issue(
    case: GroundingBenchmarkCase,
    reference: CredalReference,
) -> str | None:
    if case.label_derivation.derivation_kind == "hand_asserted":
        return "label_derivation_hand_asserted"
    if not case.label_derivation.owner_refs:
        return "label_derivation_owner_refs_missing"
    if any(
        not _owner_ref_resolves(owner_ref, reference)
        for owner_ref in case.label_derivation.owner_refs
    ):
        return "label_derivation_owner_ref_unresolved"
    expected = _label_proof_hash(
        derivation_kind=case.label_derivation.derivation_kind,
        owner_refs=case.label_derivation.owner_refs,
        labels=case.obligation_labels,
        expected_atom_id=case.expected_atom_id,
        construction_family=case.construction_family,
    )
    if expected != case.label_derivation.proof_hash:
        return "label_derivation_proof_hash_mismatch"
    return None


def _owner_ref_resolves(owner_ref: str, reference: CredalReference) -> bool:
    if "::" in owner_ref:
        modality, edge_id = owner_ref.split("::", 1)
        return (modality, edge_id) in reference.essential_edges
    if ":" in owner_ref:
        modality, edge_id = owner_ref.split(":", 1)
        return (modality, edge_id) in reference.essential_edges
    return any(edge.content_hash == owner_ref for edge in reference.essential_edges.values())


def _growth_references(
    reference: CredalReference,
) -> tuple[tuple[GrowthEpochRecord, ...], dict[str, CredalReference]]:
    records = [
        GrowthEpochRecord(
            epoch_id="epoch_0",
            reference_epoch=reference.reference_epoch,
            reference_hash=reference.reference_hash,
        )
    ]
    refs = {"epoch_0": reference}
    epoch_1 = _reference_with_growth_lever(
        reference,
        operator="energy_security_transfer",
        target="household_cells.energy_security",
        unit="security_index",
    )
    groundable_1, mimic_1, patch_1 = _growth_loop_closure(
        reference,
        epoch_1,
        operator="energy_security_transfer",
        target="household_cells.energy_security",
        outcome="household_cells.disposable_income",
        unit="security_index",
    )
    refs["epoch_1"] = epoch_1
    records.append(
        GrowthEpochRecord(
            epoch_id="epoch_1",
            reference_epoch=epoch_1.reference_epoch,
            reference_hash=epoch_1.reference_hash,
            admitted_operator="energy_security_transfer",
            admitted_patch_id=patch_1,
            admitted_lever_groundable=groundable_1,
            fresh_mimicry_caught=mimic_1,
        )
    )
    epoch_2 = _reference_with_growth_lever(
        epoch_1,
        operator="food_security_transfer",
        target="household_cells.food_security",
        unit="food_security_index",
    )
    groundable_2, mimic_2, patch_2 = _growth_loop_closure(
        epoch_1,
        epoch_2,
        operator="food_security_transfer",
        target="household_cells.food_security",
        outcome="household_cells.disposable_income",
        unit="food_security_index",
    )
    refs["epoch_2"] = epoch_2
    records.append(
        GrowthEpochRecord(
            epoch_id="epoch_2",
            reference_epoch=epoch_2.reference_epoch,
            reference_hash=epoch_2.reference_hash,
            admitted_operator="food_security_transfer",
            admitted_patch_id=patch_2,
            admitted_lever_groundable=groundable_2,
            fresh_mimicry_caught=mimic_2,
        )
    )
    return tuple(records), refs


def _growth_loop_closure(
    before: CredalReference,
    after: CredalReference,
    *,
    operator: str,
    target: str,
    outcome: str,
    unit: str,
) -> tuple[bool, bool, str | None]:
    proposal = _proposal(
        operator=operator,
        target=target,
        outcome=outcome,
        raw_text=f"{operator} grows owner-backed lever for {target} to affect {outcome}",
        admissibility="passed",
        unit=unit,
        evidence=("owner mechanism witness",),
    )
    cg1 = GroundingRelationEngine(before).certificate_for(
        proposal,
        proposal_id=f"cg6.growth.admit.{operator}",
    )
    cg2 = GroundingBindGate(before).certificate_for(cg1)
    cg3 = GroundingAdmissionEngine(before).decide(cg2, cg1_certificate=cg1)
    patch_id = cg3.registry_patch.patch_id if cg3.registry_patch else None
    after_cg1 = GroundingRelationEngine(after).certificate_for(
        proposal,
        proposal_id=f"cg6.growth.after.{operator}",
    )
    groundable = after_cg1.selected_relation in _IDENTIFYING_RELATIONS
    mimic = _proposal(
        operator=f"{operator}_mimic",
        target=target,
        outcome=outcome,
        raw_text=f"{operator} adjustment mimic surface with no owner lever",
        admissibility="candidate_unverified",
        unit=unit,
    )
    mimic_run = GroundingPhrasingDefenseEngine(after).run_pipeline(
        mimic,
        proposal_id=f"cg6.growth.mimic.{operator}",
    )
    risk = GroundingPhrasingDefenseEngine(after).detect_proxy_gap(mimic_run)
    mimic_caught = risk is not None or mimic_run.decisions.cg2_decision != "bind"
    return groundable, mimic_caught, patch_id


def _reference_with_growth_lever(
    reference: CredalReference,
    *,
    operator: str,
    target: str,
    unit: str,
) -> CredalReference:
    updated = replace_reference_edge(
        reference,
        _operator_edge(operator, minimum=0.0, maximum=1.0, unit=unit),
    )
    updated = replace_reference_edge(updated, _target_edge(operator, target))
    return replace_reference_edge(updated, _lex_edge(f"{operator}_statute", operator))


def _case_from_atom(
    atom: GroundingCandidateAtom,
    stream: BenchmarkStream,
    family: str,
    epoch_id: str,
    index: int,
) -> GroundingBenchmarkCase:
    signature = atom.signature.model_dump(mode="json")
    if signature.get("op") == "tax_relief_rate":
        signature["op"] = "tax_credit_rate"
        signature["effect_path"] = [
            "tax_credit_rate",
            *list(atom.signature.X_do),
            *list(atom.signature.outcome),
        ]
    proposal = {
        "raw_text": f"held out {family} {signature.get('op')} {signature.get('target')}",
        "signature": signature,
    }
    return _make_case(
        stream=stream,
        family=family,
        epoch_id=epoch_id,
        proposal=proposal,
        labels=("must+",),
        expected_atom_id=atom.atom_id,
        expected_operator=str(atom.signature.op or ""),
        expected_target=atom.signature.X_do[0] if atom.signature.X_do else None,
        construction_family="registered_alias_or_denotation_identity",
        derivation_kind="registered_alias_or_denotation_identity",
        owner_refs=tuple(atom.edge_scope),
        source_atom_id=atom.atom_id,
        index=index,
        decisive="bind_eligible_relation_for_must_plus_under_cg2_freeze",
    )


def _false_analog_case(
    atom: GroundingCandidateAtom,
    epoch_id: str,
    index: int,
    *,
    stream: BenchmarkStream = "stress",
) -> GroundingBenchmarkCase:
    target = _sibling_target(atom.signature.X_do[0] if atom.signature.X_do else "")
    proposal = _proposal(
        operator=str(atom.signature.op or ""),
        target=target,
        outcome=atom.signature.outcome[0] if atom.signature.outcome else target,
        raw_text=f"{atom.signature.op} near analog surface but critical target swap {target}",
        admissibility="passed",
    )
    return _make_case(
        stream=stream,
        family="false_analog_minimal_axis_swap",
        epoch_id=epoch_id,
        proposal=proposal,
        labels=("must-",),
        expected_atom_id=atom.atom_id,
        expected_operator=str(atom.signature.op or ""),
        expected_target=atom.signature.X_do[0] if atom.signature.X_do else None,
        construction_family="minimal_critical_axis_swap",
        derivation_kind="owner_atom_minimal_critical_axis_swap",
        owner_refs=tuple(atom.edge_scope),
        source_atom_id=atom.atom_id,
        index=index,
        decisive="critical_axis_veto_or_abstain",
    )


def _name_collision_false_analog_case(
    atom: GroundingCandidateAtom,
    epoch_id: str,
    index: int,
) -> GroundingBenchmarkCase:
    target = atom.signature.X_do[0] if atom.signature.X_do else "global.tax_rate"
    outcome = atom.signature.outcome[0] if atom.signature.outcome else target
    proposal = _proposal(
        operator=str(atom.signature.op or ""),
        target=target,
        outcome=outcome,
        raw_text=(
            f"{atom.signature.op} registered name collision with opposite causal "
            f"semantics for {target}"
        ),
        sign="decrease",
        admissibility="passed",
    )
    return _make_case(
        stream="stress",
        family="name_collision_false_analog",
        epoch_id=epoch_id,
        proposal=proposal,
        labels=("must-",),
        expected_atom_id=atom.atom_id,
        expected_operator=str(atom.signature.op or ""),
        expected_target=target,
        construction_family="registered_name_collision_critical_semantic_swap",
        derivation_kind="owner_atom_registered_name_collision_sign_contradiction",
        owner_refs=tuple(atom.edge_scope),
        source_atom_id=atom.atom_id,
        index=index,
        decisive="exact_and_lexical_name_match_false_bind_unless_firewall_vetoes",
    )


def _high_lexical_similarity_false_analog_case(
    atom: GroundingCandidateAtom,
    epoch_id: str,
    index: int,
) -> GroundingBenchmarkCase:
    target = atom.signature.X_do[0] if atom.signature.X_do else "global.tax_rate"
    outcome = atom.signature.outcome[0] if atom.signature.outcome else target
    operator = str(atom.signature.op or "")
    proposal = _proposal(
        operator=f"{operator}_proxy_surface",
        target=target,
        outcome=outcome,
        raw_text=(
            f"{operator} {target} {outcome} {operator} policy lever proxy surface "
            "with no owner denotation"
        ),
        admissibility="passed",
        evidence=("lexical surface only",),
    )
    return _make_case(
        stream="stress",
        family="high_lexical_similarity_false_analog",
        epoch_id=epoch_id,
        proposal=proposal,
        labels=("must-", "hallucination-"),
        expected_atom_id=atom.atom_id,
        expected_operator=operator,
        expected_target=target,
        construction_family="high_lexical_similarity_without_owner_denotation",
        derivation_kind="owner_atom_lexical_surface_mimic_no_denotation",
        owner_refs=tuple(atom.edge_scope),
        source_atom_id=atom.atom_id,
        index=index,
        decisive="fts_top1_false_bind_unless_firewall_abstains_or_quarantines",
    )


def _compositional_case(
    atom: GroundingCandidateAtom,
    epoch_id: str,
    index: int,
) -> GroundingBenchmarkCase:
    target = atom.signature.X_do[0] if atom.signature.X_do else "global.tax_rate"
    proposal = _proposal(
        operator=str(atom.signature.op or ""),
        target=[target, "government.balance"],
        outcome=atom.signature.outcome[0] if atom.signature.outcome else "government.balance",
        raw_text=f"bundle {atom.signature.op} with budget_allocation_multiplier",
        admissibility="candidate_unverified",
    )
    return _make_case(
        stream="stress",
        family="compositional_multi_atom_bundle",
        epoch_id=epoch_id,
        proposal=proposal,
        labels=("may+",),
        expected_atom_id=atom.atom_id,
        expected_operator=str(atom.signature.op or ""),
        expected_target=target,
        construction_family="underspecified_compatible_bundle",
        derivation_kind="owner_atom_underspecified_compatible_bundle",
        owner_refs=tuple(atom.edge_scope),
        source_atom_id=atom.atom_id,
        index=index,
        decisive="may_bind_or_abstain",
    )


def _cross_modal_inconsistent_case(
    atom: GroundingCandidateAtom,
    epoch_id: str,
    index: int,
) -> GroundingBenchmarkCase:
    target = (
        "government.balance"
        if "government.balance" not in atom.signature.X_do
        else "global.tax_rate"
    )
    proposal = _proposal(
        operator=str(atom.signature.op or "tax_relief_rate"),
        target=target,
        outcome=target,
        raw_text=f"{atom.signature.op} with budget_law cross modal contradiction",
        law_token="budget_law",  # noqa: S106 - domain law token, not a secret.
        knob=str(atom.signature.op or ""),
        admissibility="passed",
    )
    return _make_case(
        stream="stress",
        family="cross_modal_inconsistent",
        epoch_id=epoch_id,
        proposal=proposal,
        labels=("must-",),
        expected_atom_id=atom.atom_id,
        expected_operator=str(atom.signature.op or ""),
        expected_target=atom.signature.X_do[0] if atom.signature.X_do else None,
        construction_family="modal_claims_disagree",
        derivation_kind="owner_l3_l6_modal_contradiction",
        owner_refs=tuple(atom.edge_scope),
        source_atom_id=atom.atom_id,
        index=index,
        decisive="joint_cross_modal_block_or_abstain",
    )


def _joint_type_inconsistent_case(
    atom: GroundingCandidateAtom,
    epoch_id: str,
    index: int,
) -> GroundingBenchmarkCase:
    proposal = _proposal(
        operator=str(atom.signature.op or "tax_relief_rate"),
        target="government.balance",
        outcome="government.balance",
        raw_text=f"{atom.signature.op} valid operator and valid slot but invalid joint mapping",
        law_token="tax_relief_statute",  # noqa: S106 - domain law token, not a secret.
        knob=str(atom.signature.op or ""),
        unit="usd",
        admissibility="passed",
    )
    return _make_case(
        stream="stress",
        family="joint_type_inconsistent",
        epoch_id=epoch_id,
        proposal=proposal,
        labels=("must-",),
        expected_atom_id=atom.atom_id,
        expected_operator=str(atom.signature.op or ""),
        expected_target=atom.signature.X_do[0] if atom.signature.X_do else None,
        construction_family="joint_invalid_axis_combination",
        derivation_kind="owner_joint_type_axis_contradiction",
        owner_refs=tuple(atom.edge_scope),
        source_atom_id=atom.atom_id,
        index=index,
        decisive="joint_type_constraint_blocks",
    )


def _adversarial_mimic_case(
    atom: GroundingCandidateAtom,
    epoch_id: str,
    index: int,
    *,
    stream: BenchmarkStream = "stress",
) -> GroundingBenchmarkCase:
    op = str(atom.signature.op or "tax_relief_rate")
    target = atom.signature.X_do[0] if atom.signature.X_do else "global.tax_rate"
    outcome = atom.signature.outcome[0] if atom.signature.outcome else target
    mimic = f"{op}_adjustment"
    proposal = _proposal(
        operator=mimic,
        target=target,
        outcome=outcome,
        raw_text=f"{op.replace('_', ' ')} adjustment mimics registered lever without owner proof",
        admissibility="candidate_unverified",
        evidence=("surface mimic only",),
    )
    return _make_case(
        stream=stream,
        family="adversarial_mimicry",
        epoch_id=epoch_id,
        proposal=proposal,
        labels=("must-", "hallucination-"),
        expected_atom_id=atom.atom_id,
        expected_operator=op,
        expected_target=target,
        construction_family="registered_lever_mimicry_surface",
        derivation_kind="owner_atom_mimicry_surface_no_denotation",
        owner_refs=tuple(atom.edge_scope),
        source_atom_id=atom.atom_id,
        index=index,
        decisive="cg4_quarantine_or_cg2_abstain",
    )


def _unknown_case(atom: GroundingCandidateAtom, epoch_id: str) -> GroundingBenchmarkCase:
    proposal = {
        "raw_text": "unresolved policy handle with insufficient owner evidence",
        "signature": {
            "op": None,
            "target": [],
            "params": {},
            "x_do": {},
            "outcome": [],
            "effect_path": [],
            "admissibility": "candidate_unverified",
            "modal_claims": {"NL": {"op": "", "target": "", "outcome": ""}},
        },
    }
    return _make_case(
        stream="stress",
        family="unknown_insufficient_owner_evidence",
        epoch_id=epoch_id,
        proposal=proposal,
        labels=("unknown",),
        expected_atom_id=None,
        expected_operator=None,
        expected_target=None,
        construction_family="insufficient_owner_evidence",
        derivation_kind="owner_evidence_intentionally_insufficient",
        owner_refs=tuple(atom.edge_scope),
        source_atom_id=atom.atom_id,
        index=0,
        decisive="correct_abstention_or_acquire",
    )


def _fabricated_mechanism_hallucination_case(
    atom: GroundingCandidateAtom,
    epoch_id: str,
) -> GroundingBenchmarkCase:
    proposal = _proposal(
        operator="fabricated_tax_output_lever",
        target="global.tax_rate",
        outcome="cells.output",
        raw_text="fabricated tax output mechanism with confident owner-sounding text",
        admissibility="passed",
        evidence=("caller mechanism witness",),
    )
    return _make_case(
        stream="stress",
        family="hallucination_fabricated_mechanism",
        epoch_id=epoch_id,
        proposal=proposal,
        labels=("hallucination-",),
        expected_atom_id=atom.atom_id,
        expected_operator="fabricated_tax_output_lever",
        expected_target="global.tax_rate",
        construction_family="caller_claimed_mechanism_not_structural_owner_path",
        derivation_kind="owner_structural_path_absent_text_only_mimic_present",
        owner_refs=tuple(atom.edge_scope),
        source_atom_id=atom.atom_id,
        index=0,
        decisive="cg3_must_not_admit_text_only_mechanism",
    )


def _novel_case(
    operator: str,
    target: str,
    outcome: str,
    epoch_id: str,
    *,
    unit: str = "ratio",
    owner_refs: tuple[str, ...] | None = None,
    index: int = 0,
) -> GroundingBenchmarkCase:
    proposal = _proposal(
        operator=operator,
        target=target,
        outcome=outcome,
        raw_text=f"{operator} owner-backed new lever for {target}",
        admissibility="passed",
        unit=unit,
        evidence=("owner mechanism witness",),
    )
    return _make_case(
        stream="stress",
        family="novel_lever_owner_backed",
        epoch_id=epoch_id,
        proposal=proposal,
        labels=("novel+",),
        expected_atom_id=None,
        expected_operator=operator,
        expected_target=target,
        construction_family="new_lever_with_owner_evidence",
        derivation_kind="owner_backed_new_lever_shape",
        owner_refs=owner_refs
        or (f"WMR_WORLD_SLOT::{target}", f"L2_CAUSAL_CLAIM::{target}->{outcome}"),
        source_atom_id=None,
        index=index,
        decisive="cg3_admit_or_acquire_never_reject",
    )


def _make_case(
    *,
    stream: BenchmarkStream,
    family: str,
    epoch_id: str,
    proposal: Mapping[str, Any],
    labels: tuple[ObligationLabel, ...],
    expected_atom_id: str | None,
    expected_operator: str | None,
    expected_target: str | None,
    construction_family: str,
    derivation_kind: str,
    owner_refs: tuple[str, ...],
    source_atom_id: str | None,
    index: int,
    decisive: str,
) -> GroundingBenchmarkCase:
    proof_hash = _label_proof_hash(
        derivation_kind=derivation_kind,
        owner_refs=owner_refs,
        labels=labels,
        expected_atom_id=expected_atom_id,
        construction_family=construction_family,
    )
    held_out_key = gy_content_hash(
        {
            "construction_family": construction_family,
            "epoch_id": epoch_id,
            "family": family,
            "index": index,
            "seed": DEFAULT_BENCHMARK_SEED,
            "stream": stream,
        }
    )
    fields = {
        "construction_family": construction_family,
        "decisive_mechanism_expected": decisive,
        "epoch_id": epoch_id,
        "expected_atom_id": expected_atom_id,
        "expected_operator": expected_operator,
        "expected_target": expected_target,
        "family": family,
        "held_out_key": held_out_key,
        "label_derivation": {
            "derivation_kind": derivation_kind,
            "derivation_notes": "derived from owner-shaped construction data",
            "owner_refs": list(owner_refs),
            "proof_hash": proof_hash,
        },
        "obligation_labels": list(labels),
        "proposal": _json_ready(proposal),
        "source_atom_id": source_atom_id,
        "stream": stream,
    }
    case_hash = gy_content_hash(fields)
    return GroundingBenchmarkCase(
        case_id=f"cg6.{epoch_id}.{stream}.{family}.{case_hash.removeprefix('sha256:')[:12]}",
        case_hash=case_hash,
        **fields,
    )


def _proposal(
    *,
    operator: str,
    target: str | Sequence[str],
    outcome: str,
    raw_text: str,
    sign: str = "increase",
    unit: str = "ratio",
    admissibility: str = "candidate_unverified",
    law_token: str | None = None,
    knob: str | None = None,
    evidence: tuple[str, ...] = (),
) -> dict[str, Any]:
    targets = [target] if isinstance(target, str) else list(target)
    first_target = targets[0] if targets else ""
    modal_claims: dict[str, dict[str, Any]] = {
        "NL": {
            "op": operator,
            "target": first_target,
            "outcome": outcome,
            "estimand": "average_treatment_effect",
        },
        "do_AST": {"op": operator, "target": first_target, "do_value": {"rate": 0.1}},
        "method": {
            "treatment_op": operator,
            "treatment_target": first_target,
            "outcome": outcome,
            "estimand": "average_treatment_effect",
        },
    }
    if law_token:
        modal_claims["L3"] = {"law_token": law_token}
    if knob:
        modal_claims["L6"] = {"knob": knob}
    if evidence:
        modal_claims["claim"] = {"mechanism_witness": list(evidence)}
    return {
        "raw_text": raw_text,
        "signature": {
            "op": operator,
            "target": targets,
            "sign": sign,
            "params": {"rate": 0.1},
            "x_do": {"rate": 0.1},
            "scope": "global" if not first_target.startswith("household") else "households",
            "population": "all" if not first_target.startswith("household") else "households",
            "unit": unit,
            "outcome": [outcome] if outcome else [],
            "effect_path": [operator, *targets, outcome] if outcome else [operator, *targets],
            "estimand": "average_treatment_effect",
            "admissibility": admissibility,
            "evidence": list(evidence),
            "modal_claims": modal_claims,
        },
    }


def _selected_atoms(reference: CredalReference, *, limit: int) -> tuple[Any, ...]:
    atoms = GroundingRelationEngine(reference).reference_atoms
    return tuple(
        sorted(
            atoms,
            key=lambda atom: gy_content_hash(
                {
                    "atom_id": atom.atom_id,
                    "reference_hash": reference.reference_hash,
                    "seed": DEFAULT_BENCHMARK_SEED,
                }
            ),
        )[:limit]
    )


def _calibration_anchor_set(
    reference: CredalReference,
    cases: Sequence[GroundingBenchmarkCase],
) -> CalibrationAnchorSet:
    strata: dict[str, int] = defaultdict(int)
    for case in cases:
        if case.stream not in {"seed_anchors", "calibration"}:
            continue
        if not {"must+", "may+"}.intersection(case.obligation_labels):
            continue
        key = "|".join(
            [
                case.expected_operator or "unknown_operator",
                case.expected_target or "unknown_region",
                "exact_or_specialization",
            ]
        )
        strata[key] += 1
    fields = {
        "epoch_id": reference.reference_epoch,
        "provenance": "cg6_benchmark_calibration_v1",
        "strata": dict(sorted(strata.items())),
        "unfreeze_pathway": (
            "Future CG2 unfreeze must populate an owned calibration store from this "
            "content-addressed held-out set only after the bind-path re-audit; CG6 "
            "does not write grounding_bind.py or production CG2 state."
        ),
        "wired_into_cg2": False,
    }
    content_hash = gy_content_hash(fields)
    return CalibrationAnchorSet(
        anchor_set_id=f"cg6_calibration_{content_hash.removeprefix('sha256:')[:16]}",
        content_hash=content_hash,
        **fields,
    )


def _baseline_configs() -> dict[str, BaselineConfig]:
    configs = {
        "full_cgf_stack": {
            "baseline_id": "full_cgf_stack",
            "implementation": (
                "GroundingRelationEngine -> GroundingBindGate -> "
                "GroundingAdmissionEngine -> GroundingPhrasingDefenseEngine"
            ),
            "provenance": "real_cgf_stack_production_policy",
            "decision_boundary": (
                "identifies via CG1 exact/certified-specialization or CG2 bind; "
                "admits novel only through CG3; CG4 quarantine recorded separately"
            ),
        },
        "exact_match_alias_table": {
            "baseline_id": "exact_match_alias_table",
            "implementation": "name equality plus registered alias table",
            "provenance": "historical_trinity_linker_behavior_honest_alias_enabled",
            "decision_boundary": (
                "bind-equivalent exact identification when canonical operator and target "
                "match a registered atom; no CGF safety machinery"
            ),
            "alias_table_hash": _alias_table_hash(),
        },
        "lexical_similarity_duckdb_fts_top1": {
            "baseline_id": "lexical_similarity_duckdb_fts_top1",
            "implementation": "CG1 DuckDB FTS retrieval top-1",
            "provenance": "honest_proxy_for_dense_embeddings_missing_in_environment",
            "decision_boundary": (
                "bind-equivalent exact identification of top retrieval-score atom; "
                "dense embeddings missing, no CG2/CG3/CG4 safety"
            ),
            "dense_embeddings_status": "missing_documented_duckdb_fts_proxy",
        },
        "entity_linker_recorded_replay": {
            "baseline_id": "entity_linker_recorded_replay",
            "implementation": "deterministic entity-linker judgment replay",
            "provenance": "honestly_unavailable_no_entity_linker_recordings_or_service",
            "decision_boundary": (
                "unavailable in this environment because no recorded entity-linker "
                "judgments or local entity-linker service exist for these case families"
            ),
            "entity_linker_status": (
                "honestly_unavailable_no_recorded_entity_linker_judgments_or_service"
            ),
        },
        "greedy_per_axis": {
            "baseline_id": "greedy_per_axis",
            "implementation": (
                "GroundingEnginePolicy.use_greedy_solver CG1 identification only"
            ),
            "provenance": "contract_testing_mutation_switch_existing_cg1",
            "decision_boundary": (
                "bind-equivalent identification when greedy per-axis CG1 relation is "
                "exact or certified-specialization; no CG2 calibration, CG3 admission, "
                "or CG4 quarantine borrowed from CGF"
            ),
        },
        "llm_judge_recorded_replay": {
            "baseline_id": "llm_judge_recorded_replay",
            "implementation": "deterministic recorded judgment replay",
            "provenance": "honestly_unavailable_no_recorded_judgments",
            "decision_boundary": (
                "unavailable in this environment because no recorded LLM judgments "
                "exist for these case families"
            ),
            "llm_status": "honestly_unavailable_no_recorded_judgments",
        },
        "passive_abstain": {
            "baseline_id": "passive_abstain",
            "implementation": "always abstain",
            "provenance": "floor_zero_false_bind_zero_recall",
            "decision_boundary": "never identifies, binds, admits, or quarantines",
        },
    }
    out: dict[str, BaselineConfig] = {}
    for key, fields in configs.items():
        config_hash = _baseline_config_hash(fields)
        out[key] = BaselineConfig(
            config_hash=config_hash,
            expected_config_hash=config_hash,
            **fields,
        )
    return out


def _baseline_config_hash(fields: Mapping[str, Any]) -> str:
    payload = dict(_mapping(fields))
    payload.pop("config_hash", None)
    payload.pop("expected_config_hash", None)
    payload.setdefault("alias_table_hash", None)
    payload.setdefault("dense_embeddings_status", "not_used")
    payload.setdefault("entity_linker_status", "not_used")
    payload.setdefault("llm_status", "not_used")
    return gy_content_hash(payload)


def _alias_table_hash() -> str:
    return gy_content_hash(dict(sorted(_ALIAS_TABLE.items())))


def _canonical_operator(value: object) -> str:
    text = str(value or "").strip().casefold().replace("-", "_").replace(" ", "_")
    return _ALIAS_TABLE.get(text, text)


def _selected_atom_id(cg1_certificate: GroundingRelationCertificate) -> str | None:
    selected = _mapping(_mapping(cg1_certificate.cross_modal_witnesses).get("selected_pair"))
    atom_id = str(selected.get("atom_id") or "")
    if atom_id:
        return atom_id
    for row in _sequence(_mapping(cg1_certificate.relation_set).get("candidate_results")):
        payload = _mapping(row)
        if payload.get("selected_relation") == cg1_certificate.selected_relation:
            return str(payload.get("atom_id") or "") or None
    return None


def _fabricated_calibration_ledger(
    case: GroundingBenchmarkCase,
    reference: CredalReference,
) -> GroundingCalibrationLedger:
    operator = _canonical_operator(case.expected_operator or "tax_relief_rate")
    region = "global"
    relation_type = "exact"
    anchor = CalibrationStratumRecord(
        operator_family=operator,
        reference_region=region,
        relation_type=relation_type,
        status="calibrated",
        reference_epoch=reference.reference_epoch,
        sample_count=999,
        provenance="cg6_benchmark_fabricated_caller_calibration",
        owner_anchor_id=f"fabricated:{case.case_id}",
        evidence_hash=gy_content_hash(
            {
                "owner_anchor_id": f"fabricated:{case.case_id}",
                "operator_family": operator,
                "reference_epoch": reference.reference_epoch,
                "reference_region": region,
                "relation_type": relation_type,
                "sample_count": 999,
            }
        ),
    ).with_content_hash()
    return GroundingCalibrationLedger(records=(anchor,), source_id="cg6_fabricated")


class _UnsafeTrustTier:
    """Tiny contract-testing object matching CG3's trust-cap protocol."""

    trust_cap = 0.99


class _UnsafeRegistryEntry:
    """Tiny contract-testing registry entry for broken-CG3 liveness."""

    layer = "L2"
    family_id = "causal_claim_contract_testing_unsafe"
    trust_tier = _UnsafeTrustTier()
    authority_refs = ("cg6://unsafe-contract-testing-causal-trust",)
    entry_content_hash = "sha256:" + "1" * 64


class _UnsafeCausalSubstrateRegistry:
    """Tiny contract-testing registry for the existing CG3 mutation hook."""

    entries = (_UnsafeRegistryEntry(),)


def _unsafe_causal_substrate_registry() -> _UnsafeCausalSubstrateRegistry:
    return _UnsafeCausalSubstrateRegistry()


def _findings(
    score_slices: Sequence[ScoreSlice],
    cases: Sequence[GroundingBenchmarkCase],
    decisions: Sequence[GroundingBenchmarkDecision],
    detector_liveness: Sequence[DetectorLivenessRecord],
) -> tuple[str, ...]:
    findings: list[str] = []
    findings.extend(_baseline_verdict_findings(score_slices))
    findings.extend(_full_cgf_confident_wrong_findings(cases, decisions))
    findings.extend(_detection_floor_findings(detector_liveness))
    cgf = [
        row
        for row in score_slices
        if row.baseline_id == "full_cgf_stack"
        and row.stream in {"stress", "growth", "seed_anchors", "calibration"}
    ]
    by_key = {(row.epoch_id, row.stream, row.family): row for row in cgf}
    non_dominance_found = False
    for row in score_slices:
        if row.baseline_id == "full_cgf_stack":
            continue
        peer = by_key.get((row.epoch_id, row.stream, row.family))
        if peer is None:
            continue
        pair_worse = (
            peer.confident_wrong.rate > row.confident_wrong.rate
            and peer.useful_recall.rate <= row.useful_recall.rate
        )
        recall_worse = (
            peer.useful_recall.denominator > 0
            and peer.useful_recall.rate < row.useful_recall.rate
            and peer.confident_wrong.rate >= row.confident_wrong.rate
        )
        if pair_worse or recall_worse:
            non_dominance_found = True
            findings.append(
                "CGF did not dominate "
                f"{row.baseline_id} on {row.epoch_id}/{row.stream}/{row.family}: "
                f"cgf_confident_wrong={peer.confident_wrong.rate:.4f}, "
                f"baseline_confident_wrong={row.confident_wrong.rate:.4f}, "
                f"cgf_recall={peer.useful_recall.rate:.4f}, "
                f"baseline_recall={row.useful_recall.rate:.4f}"
            )
    if not non_dominance_found:
        findings.append(
            "No CGF non-dominance finding on measured representative slices; this is "
            "not a claim about unmeasured private/retroactive streams."
        )
    return tuple(findings)


def _baseline_verdict_findings(score_slices: Sequence[ScoreSlice]) -> tuple[str, ...]:
    baseline_ids: tuple[BaselineId, ...] = (
        "full_cgf_stack",
        "exact_match_alias_table",
        "lexical_similarity_duckdb_fts_top1",
        "greedy_per_axis",
        "passive_abstain",
    )
    summaries: list[str] = []
    for baseline_id in baseline_ids:
        rows = [
            row
            for row in score_slices
            if row.baseline_id == baseline_id
            and row.epoch_id == "epoch_0"
            and row.stream == "stress"
        ]
        if not rows:
            continue
        false_bind = sum(row.false_bind.numerator for row in rows)
        hallucination = sum(row.hallucination_admit.numerator for row in rows)
        confident = sum(row.confident_wrong.numerator for row in rows)
        denominator = sum(row.confident_wrong.denominator for row in rows)
        recall_num = sum(row.useful_recall.numerator for row in rows)
        recall_den = sum(row.useful_recall.denominator for row in rows)
        summaries.append(
            f"{baseline_id}:false_bind={false_bind}/{denominator},"
            f"hallucination_admit={hallucination}/{denominator},"
            f"confident_wrong={confident}/{denominator},"
            f"useful_recall={recall_num}/{recall_den}"
        )
    if not summaries:
        return ()
    return (
        "CG6_CORRECTED_BASELINE_VERDICT epoch_0/stress representative-world: "
        + "; ".join(summaries),
    )


def _full_cgf_confident_wrong_findings(
    cases: Sequence[GroundingBenchmarkCase],
    decisions: Sequence[GroundingBenchmarkDecision],
) -> tuple[str, ...]:
    cases_by_id = {case.case_id: case for case in cases}
    findings: list[str] = []
    for decision in sorted(
        (
            row
            for row in decisions
            if row.baseline_id == "full_cgf_stack"
            and row.stream == "stress"
            and row.epoch_id == "epoch_0"
        ),
        key=lambda row: row.case_id,
    ):
        case = cases_by_id.get(decision.case_id)
        if case is None:
            continue
        false_bind = _is_false_bind(case, decision)
        hallucination = _is_hallucination_admit(case, decision)
        if not false_bind and not hallucination:
            continue
        if false_bind and decision.relation in _IDENTIFYING_RELATIONS:
            violation = (
                "must-_false_bind_via_cg1_relation "
                f"relation={decision.relation} selected_atom={decision.selected_atom_id}"
            )
            gap = "CG1 emitted an identifying relation for a must-negative construction"
        elif false_bind and decision.bind_decision in _BIND_RELATIONS:
            violation = (
                "must-_false_bind_via_cg2_bind "
                f"bind_decision={decision.bind_decision} selected_atom={decision.selected_atom_id}"
            )
            gap = "CG2 emitted a bind for a must-negative construction"
        elif hallucination:
            violation = (
                "hallucination_admit_via_cg3 "
                f"admission_decision={decision.admission_decision} "
                f"reason={decision.admission_reason}"
            )
            gap = "CG3 admitted a hallucination-negative proposal as a new lever"
        else:
            violation = "confident_wrong_unclassified"
            gap = "Confident-wrong channel requires follow-up classification"
        chain = ",".join(
            f"{ref.component}:{ref.certificate_id}:{ref.content_hash}"
            for ref in decision.certificate_chain
        )
        findings.append(
            "CG6_REAL_FIREWALL_GAP "
            f"case={case.case_id} family={case.family} labels={case.obligation_labels} "
            f"expected_atom={case.expected_atom_id} source_atom={case.source_atom_id} "
            f"{violation}; cg2={decision.bind_decision}; "
            f"cg3={decision.admission_decision}/{decision.admission_reason}; "
            "signature_only_overcount=false; "
            f"gap={gap}; replay_chain={chain}"
        )
    return tuple(findings)


def _detection_floor_findings(
    detector_liveness: Sequence[DetectorLivenessRecord],
) -> tuple[str, ...]:
    if not detector_liveness:
        return ()
    working = next(
        (row for row in detector_liveness if row.variant_id == "working_stack"),
        None,
    )
    detectable_single = [
        row.variant_id
        for row in detector_liveness
        if row.detection_floor == "detectable_single"
    ]
    detectable_stacked = [
        row.variant_id
        for row in detector_liveness
        if row.detection_floor == "detectable_stacked_only"
    ]
    undetectable_single = [
        row.variant_id
        for row in detector_liveness
        if row.contract_testing_scope
        and row.detection_floor == "undetectable"
        and len(row.mutation_switches) <= 1
    ]
    working_text = (
        f"{working.confident_wrong_count}/{working.denominator}"
        if working is not None
        else "missing"
    )
    return (
        "CG6_DETECTION_FLOOR "
        f"working_confident_wrong={working_text}; "
        "materiality_rule=variant confident-wrong interval lower bound must exceed "
        "working interval upper bound; "
        f"detectable_single={detectable_single}; "
        f"detectable_stacked_only={detectable_stacked}; "
        f"undetectable_single={undetectable_single}",
    )


def _interval(numerator: int, denominator: int) -> IntervalEstimate:
    if denominator <= 0:
        return IntervalEstimate(numerator=0, denominator=0, rate=0.0, lower=0.0, upper=1.0)
    alpha = 0.05
    try:
        from scipy.stats import beta

        lower = (
            0.0
            if numerator == 0
            else float(beta.ppf(alpha / 2, numerator, denominator - numerator + 1))
        )
        upper = (
            1.0
            if numerator == denominator
            else float(beta.ppf(1 - alpha / 2, numerator + 1, denominator - numerator))
        )
    except Exception:
        radius = 1.0 / math.sqrt(denominator)
        rate = numerator / denominator
        lower = max(0.0, rate - radius)
        upper = min(1.0, rate + radius)
    return IntervalEstimate(
        numerator=numerator,
        denominator=denominator,
        rate=round(numerator / denominator, 12),
        lower=round(lower, 12),
        upper=round(upper, 12),
    )


def _percentile(values: Sequence[float], percentile: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return round(values[0], 6)
    rank = (len(values) - 1) * percentile / 100.0
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return round(values[int(rank)], 6)
    return round(values[lower] + (values[upper] - values[lower]) * (rank - lower), 6)


def _label_proof_hash(
    *,
    derivation_kind: str,
    owner_refs: Sequence[str],
    labels: Sequence[str],
    expected_atom_id: str | None,
    construction_family: str,
) -> str:
    return gy_content_hash(
        {
            "construction_family": construction_family,
            "derivation_kind": derivation_kind,
            "expected_atom_id": expected_atom_id,
            "obligation_labels": sorted(labels),
            "owner_refs": sorted(owner_refs),
        }
    )


def _operator_edge(
    op: str,
    *,
    minimum: float,
    maximum: float,
    unit: str,
) -> CredalReferenceEdge:
    return CredalReferenceEdge(
        modality="L6_KNOB_OPERATOR",
        edge_id=op,
        status="confirmed",
        admissible_completions=(
            AdmissibleCompletion(
                "fixed",
                {
                    "operator_kind": op,
                    "parameter_domain": {
                        "kind": "range",
                        "max_value": maximum,
                        "min_value": minimum,
                        "unit": unit,
                        "value_type": "float",
                    },
                },
                "cg6_owner_operator",
            ),
        ),
        provenance={"owner": "L6", "source": "cg6_owner_shaped_reference"},
        unit=unit,
    ).with_content_hash()


def _target_edge(op: str, target: str) -> CredalReferenceEdge:
    return CredalReferenceEdge(
        modality="L6_KNOB_WORLD_SLOT",
        edge_id=op,
        status="confirmed",
        admissible_completions=(
            AdmissibleCompletion(
                "fixed",
                {
                    "operator_kind": op,
                    "target_world_slots": [target],
                    "world_model_record_id": "cg6-wmr",
                },
                "cg6_owner_target",
            ),
        ),
        provenance={"owner": "L6", "source": "cg6_owner_shaped_reference"},
    ).with_content_hash()


def _lex_edge(law_token: str, op: str) -> CredalReferenceEdge:
    return CredalReferenceEdge(
        modality="L6_LEX_INTERVENTION_MAP",
        edge_id=law_token,
        status="confirmed",
        admissible_completions=(
            AdmissibleCompletion(
                "fixed",
                {"law_token": law_token, "knob_id": op},
                "cg6_owner_lex_map",
            ),
        ),
        provenance={"owner": "L6", "source": "cg6_owner_shaped_reference"},
    ).with_content_hash()


def _world_slot(slot: str, *, unit: str, slot_role: str) -> CredalReferenceEdge:
    return CredalReferenceEdge(
        modality="WMR_WORLD_SLOT",
        edge_id=slot,
        status="confirmed",
        admissible_completions=(
            AdmissibleCompletion(
                "fixed",
                {
                    "slot_id": slot,
                    "state_path": slot,
                    "unit": unit,
                    "slot_role": slot_role,
                    "is_policy_input": slot_role == "policy_input",
                },
                "cg6_owner_wmr_slot",
            ),
        ),
        provenance={
            "owner": "WMR",
            "source": "cg6_owner_shaped_reference",
            "signals": {
                "entity_scope": slot.split(".", 1)[0],
                "slot_role": slot_role,
                "is_policy_input": slot_role == "policy_input",
            },
        },
        unit=unit,
    ).with_content_hash()


def _policy_slot(policy_slot: str, world_slot: str) -> CredalReferenceEdge:
    return CredalReferenceEdge(
        modality="WMR_POLICY_SLOT_MAP",
        edge_id=f"{policy_slot}:{world_slot}",
        status="confirmed",
        admissible_completions=(
            AdmissibleCompletion(
                "fixed",
                {
                    "policy_slot": policy_slot,
                    "slot_id": world_slot,
                    "world_slot": world_slot,
                    "is_policy_input": True,
                },
                "cg6_owner_policy_slot",
            ),
        ),
        provenance={"owner": "WMR", "source": "cg6_owner_shaped_reference"},
    ).with_content_hash()


def _causal_edge(edge_id: str, source: str, outcome: str) -> CredalReferenceEdge:
    return CredalReferenceEdge(
        modality="L2_CAUSAL_CLAIM",
        edge_id=edge_id,
        status="confirmed",
        admissible_completions=(
            AdmissibleCompletion(
                "fixed",
                {
                    "direction": "positive",
                    "dst": outcome,
                    "source": source,
                    "src": source,
                    "target": outcome,
                },
                "cg6_owner_causal_path",
            ),
        ),
        provenance={
            "owner": "L2",
            "source": "cg6_owner_shaped_reference",
            "signals": {"confidence": 0.99, "trust_score": 0.99},
        },
    ).with_content_hash()


def _text_only_mechanism_edge(
    edge_id: str,
    *,
    mentioned_source: str,
    mentioned_outcome: str,
) -> CredalReferenceEdge:
    return CredalReferenceEdge(
        modality="L2_CAUSAL_CLAIM",
        edge_id=edge_id,
        status="confirmed",
        admissible_completions=(
            AdmissibleCompletion(
                "fixed",
                {
                    "direction": "positive",
                    "dst": "unrelated.outcome",
                    "source": "unrelated.source",
                    "src": "unrelated.source",
                    "target": "unrelated.outcome",
                    "text": f"mentions {mentioned_source} and {mentioned_outcome} only",
                },
                "cg6_text_only_not_structural_path",
            ),
        ),
        provenance={
            "owner": "L2",
            "source": "cg6_owner_shaped_reference",
            "signals": {"confidence": 0.99, "trust_score": 0.99},
        },
    ).with_content_hash()


def _reference_from_edges(
    edges: Sequence[CredalReferenceEdge],
    *,
    versions_suffix: str,
) -> CredalReference:
    edge_index = {edge.key: edge for edge in edges}
    component_versions = {
        "L2": f"cg6-l2-{versions_suffix}",
        "L3": f"cg6-l3-{versions_suffix}",
        "L6": f"cg6-l6-{versions_suffix}",
        "WMR": f"cg6-wmr-{versions_suffix}",
    }
    reference_hash = gy_content_hash(
        {
            "component_versions": component_versions,
            "edges": [edge.to_payload() for edge in sorted(edges, key=lambda item: item.key)],
        }
    )
    return CredalReference(
        schema_version=CREDAL_REFERENCE_SCHEMA_VERSION,
        reference_epoch=f"kref:{reference_hash.removeprefix('sha256:')[:16]}",
        reference_hash=reference_hash,
        as_of="2026-06-29",
        component_versions=component_versions,
        essential_edges=edge_index,
    )


def _sibling_target(current: str) -> str:
    candidates = (
        "global.tax_rate",
        "government.balance",
        "cells.distress_score",
        "household_cells.transfer_intensity",
        "community.resilience_index",
    )
    for candidate in candidates:
        if candidate != current:
            return candidate
    return "government.balance"


def _elapsed_ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000.0, 6)


def _json_ready(value: object) -> object:
    return json.loads(json.dumps(value, sort_keys=True, default=str))


def _without_volatile_latency(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            str(key): _without_volatile_latency(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if str(key) not in {"latency_ms", "latency_ms_p50", "latency_ms_max"}
        }
    if isinstance(value, Sequence) and not isinstance(value, str):
        return [_without_volatile_latency(item) for item in value]
    return value


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: object) -> Sequence[Any]:
    if isinstance(value, Sequence) and not isinstance(value, str):
        return value
    return ()


__all__ = [
    "BENCHMARK_OUTPUT_PATH",
    "GROUNDING_BENCHMARK_SCHEMA_VERSION",
    "GroundingBenchmarkCase",
    "GroundingBenchmarkScoreboard",
    "build_grounding_benchmark_live_slice_for_contract_testing",
    "build_grounding_benchmark_reference_for_contract_testing",
    "build_grounding_benchmark_scoreboard",
    "recompute_grounding_benchmark_scoreboard_hash",
    "run_grounding_benchmark_for_contract_testing",
    "validate_grounding_benchmark_payload",
]
