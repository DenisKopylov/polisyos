from __future__ import annotations

# ruff: noqa: S101
from copy import deepcopy

import pytest

import polisyos.runtime.quality as runtime_quality
from polisyos.ir.analytics.falsification_report import (
    FalsificationReport,
    FalsificationTest,
    FalsificationTestKind,
)
from polisyos.runtime.quality.disconfirming_evidence import (
    DISCONFIRMING_EVIDENCE_LEDGER_SCHEMA_VERSION,
    DisconfirmingEvidenceLedgerError,
    build_disconfirming_evidence_ledger,
    validate_disconfirming_evidence_ledger_record,
)
from polisyos.runtime.quality.evidence_portfolio import (
    EVIDENCE_PORTFOLIO_DESIGN_SCHEMA_VERSION,
)
from polisyos.scientist.methods.doe.designs import (
    AdversarialPlan,
    AdversarialStrategy,
    ParameterSpec,
)
from tests._helpers.hds_quality import sha


def _portfolio_design() -> dict[str, object]:
    return {
        "schema_version": EVIDENCE_PORTFOLIO_DESIGN_SCHEMA_VERSION,
        "portfolio_id": "portfolio-rec-1",
        "claim_ids": ["rec_1"],
        "predeclared": True,
        "declared_at": "2026-05-17T08:00:00+00:00",
        "declared_before_producer_execution": True,
        "authority_level": "production",
        "strands": [
            {
                "strand_id": "data-method-literature",
                "claim_id": "rec_1",
                "authority_level": "production",
                "candidate_data_source_families": ["production_msme_panel"],
                "candidate_method_families": ["causal_effect_estimation"],
                "defensible_specification_space": {
                    "primary_estimand": "ATT",
                    "allowed_models": ["two_way_fixed_effects", "event_study"],
                },
                "inclusion_rules": ["Include production administrative sources."],
                "exclusion_rules": ["Exclude fixture sources."],
                "disconfirming_lines": [
                    {
                        "line_id": "placebo-pre-period",
                        "stance": "disconfirming",
                        "evidence_family": "negative_control",
                        "required": True,
                    }
                ],
                "synthesis_rules": {"strategy": "triangulate_independent_lines"},
                "stopping_rules": {"minimum_effective_independent_evidence_count": 2},
                "cost_proportionality": {"budget_tier": "standard"},
            }
        ],
        "candidate_data_source_families": ["production_msme_panel"],
        "candidate_method_families": ["causal_effect_estimation"],
        "inclusion_rules": ["Prefer production administrative sources."],
        "exclusion_rules": ["Reject local fixtures."],
        "disconfirming_lines": ["placebo-pre-period"],
        "synthesis_rules": {"strategy": "triangulate_independent_lines"},
        "stopping_rules": {"minimum_effective_independent_evidence_count": 2},
        "cost_proportionality": {"budget_tier": "standard"},
        "cas_ref": sha("1"),
        "runtime_event_ref": sha("2"),
    }


def _ir_falsification_report() -> FalsificationReport:
    return FalsificationReport.from_tests(
        [
            FalsificationTest(
                test_name="placebo-pre-period",
                test_kind=FalsificationTestKind.PLACEBO_TREATMENT,
                passed=True,
                p_value=0.41,
                interpretation="Placebo effect is statistically indistinguishable from zero.",
                is_critical=True,
            )
        ]
    )


def _adversarial_plan() -> AdversarialPlan:
    return AdversarialPlan(
        strategy=AdversarialStrategy.GRID_EXTREME,
        parameter_specs=[
            ParameterSpec(
                name="credit_shock",
                lower_bound=-0.35,
                upper_bound=0.35,
                baseline=0.0,
            )
        ],
        vulnerability_threshold=-0.05,
        stop_on_first_vulnerability=False,
    )


def _severe_test_record() -> dict[str, object]:
    return {
        "test_id": "severe-placebo-pre-period",
        "line_id": "placebo-pre-period",
        "claim_id": "rec_1",
        "test_kind": "negative_control",
        "severity": "severe",
        "rationale": (
            "A pre-period placebo had a high chance to expose anticipatory trends "
            "that would invalidate the recommended targeting claim."
        ),
        "expected_failure_mode": "pre_policy_trend_violation",
        "result": "passed",
        "evidence_ref": sha("3"),
        "runtime_event_ref": sha("4"),
    }


def _previous_wave_refs() -> dict[str, list[str]]:
    return {
        "portfolio_design_refs": ["portfolio-rec-1"],
        "evidence_line_refs": ["line-data"],
        "independence_map_refs": ["independence-map-rec-1"],
    }


def test_disconfirming_ledger_wires_ir_falsification_adversarial_plan_and_severe_tests() -> None:
    ledger = build_disconfirming_evidence_ledger(
        ledger_id="disconfirming-ledger-rec-1",
        portfolio_id="portfolio-rec-1",
        claim_ids=["rec_1"],
        disconfirming_lines=["placebo-pre-period"],
        ir_falsification_reports=[_ir_falsification_report()],
        adversarial_plans=[_adversarial_plan()],
        severe_test_records=[_severe_test_record()],
        evidence_ref=sha("5"),
        runtime_event_ref=sha("6"),
        previous_wave_refs=_previous_wave_refs(),
    )

    validated = validate_disconfirming_evidence_ledger_record(
        ledger,
        portfolio_designs=[_portfolio_design()],
        effective_authority_profile="production",
    )

    assert validated["schema_version"] == DISCONFIRMING_EVIDENCE_LEDGER_SCHEMA_VERSION
    assert validated["claim_ids"] == ["rec_1"]
    assert validated["ir_falsification_reports"][0]["n_passed"] == 1
    assert validated["adversarial_plans"][0]["strategy"] == "grid_extreme"
    assert validated["severe_tests"][0]["rationale"].startswith("A pre-period placebo")
    assert validated["previous_wave_refs"] == _previous_wave_refs()


def test_disconfirming_ledger_rejects_missing_severe_test_rationale() -> None:
    ledger = build_disconfirming_evidence_ledger(
        ledger_id="disconfirming-ledger-rec-1",
        portfolio_id="portfolio-rec-1",
        claim_ids=["rec_1"],
        disconfirming_lines=["placebo-pre-period"],
        ir_falsification_reports=[_ir_falsification_report()],
        adversarial_plans=[_adversarial_plan()],
        severe_test_records=[_severe_test_record()],
        evidence_ref=sha("5"),
        runtime_event_ref=sha("6"),
        previous_wave_refs=_previous_wave_refs(),
    )
    broken = deepcopy(ledger)
    broken["severe_tests"][0].pop("rationale")  # type: ignore[index]

    with pytest.raises(
        DisconfirmingEvidenceLedgerError,
        match="policy_design_severe_test_rationale_missing",
    ):
        validate_disconfirming_evidence_ledger_record(
            broken,
            portfolio_designs=[_portfolio_design()],
            effective_authority_profile="production",
        )


def test_disconfirming_ledger_rejects_friendly_only_portfolio_without_profile_deficit() -> None:
    friendly_portfolio = _portfolio_design()
    friendly_line = {
        "line_id": "positive-estimate-only",
        "stance": "supporting",
        "evidence_family": "confirmatory_estimate",
    }
    friendly_portfolio["disconfirming_lines"] = [friendly_line]
    strand = dict(friendly_portfolio["strands"][0])  # type: ignore[index]
    strand["disconfirming_lines"] = [friendly_line]
    friendly_portfolio["strands"] = [strand]
    ledger = build_disconfirming_evidence_ledger(
        ledger_id="disconfirming-ledger-rec-1",
        portfolio_id="portfolio-rec-1",
        claim_ids=["rec_1"],
        disconfirming_lines=["positive-estimate-only"],
        ir_falsification_reports=[_ir_falsification_report()],
        adversarial_plans=[_adversarial_plan()],
        severe_test_records=[_severe_test_record()],
        evidence_ref=sha("5"),
        runtime_event_ref=sha("6"),
        previous_wave_refs=_previous_wave_refs(),
    )

    with pytest.raises(
        DisconfirmingEvidenceLedgerError,
        match="policy_design_disconfirming_lines_missing",
    ):
        validate_disconfirming_evidence_ledger_record(
            ledger,
            portfolio_designs=[friendly_portfolio],
            accepted_deficits=[],
            effective_authority_profile="production",
        )


def test_disconfirming_ledger_requires_previous_wave_refs() -> None:
    ledger = build_disconfirming_evidence_ledger(
        ledger_id="disconfirming-ledger-rec-1",
        portfolio_id="portfolio-rec-1",
        claim_ids=["rec_1"],
        disconfirming_lines=["placebo-pre-period"],
        ir_falsification_reports=[_ir_falsification_report()],
        adversarial_plans=[_adversarial_plan()],
        severe_test_records=[_severe_test_record()],
        evidence_ref=sha("5"),
        runtime_event_ref=sha("6"),
        previous_wave_refs=_previous_wave_refs(),
    )
    ledger.pop("previous_wave_refs")

    with pytest.raises(
        DisconfirmingEvidenceLedgerError,
        match="policy_design_disconfirming_previous_wave_refs_missing",
    ):
        validate_disconfirming_evidence_ledger_record(
            ledger,
            portfolio_designs=[_portfolio_design()],
            effective_authority_profile="production",
        )


def test_disconfirming_ledger_is_public_runtime_quality_api() -> None:
    assert (
        runtime_quality.build_disconfirming_evidence_ledger
        is build_disconfirming_evidence_ledger
    )
    assert (
        runtime_quality.validate_disconfirming_evidence_ledger_record
        is validate_disconfirming_evidence_ledger_record
    )
