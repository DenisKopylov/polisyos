from __future__ import annotations

from copy import deepcopy

import pytest

from polisyos.runtime.quality.metamorphic_controls import (
    PHASE56_CROSS_DOMAIN_SCENARIO_IDS,
    PHASE56_NEGATIVE_CONTROL_IDS,
    REQUIRED_CROSS_DOMAIN_CONTROL_IDS,
    build_cross_domain_control_report,
    build_metamorphic_prompt_report,
    build_negative_control_report,
    build_scenario_semantic_binding_report,
)
from tools.ops_runners.runtime.quality_scenarios import (
    available_quality_scenario_ids,
    load_quality_scenario_contract,
)


def test_phase56_catalog_declares_required_cross_domain_scenarios() -> None:
    scenario_ids = set(available_quality_scenario_ids(include_quarantined=True))

    assert set(PHASE56_CROSS_DOMAIN_SCENARIO_IDS) <= scenario_ids
    for scenario_id in PHASE56_CROSS_DOMAIN_SCENARIO_IDS:
        contract = load_quality_scenario_contract(
            scenario_id,
            include_quarantined=True,
        )
        profile = contract["diagnostic_control_profile"]
        assert profile["phase"] == "5.6"
        assert set(profile["cross_domain_controls"]) >= set(
            REQUIRED_CROSS_DOMAIN_CONTROL_IDS
        )
        variant_ids = {
            variant["variant_id"]
            for variant in contract["metamorphic_prompt_variants"]
            if isinstance(variant, dict)
        }
        assert {
            "wrong_jurisdiction",
            "wrong_time_context",
            "wrong_data_family",
            "wrong_method_expectation",
        } <= variant_ids
        assert contract["negative_controls"]


@pytest.mark.parametrize("scenario_id", PHASE56_CROSS_DOMAIN_SCENARIO_IDS)
def test_cross_domain_controls_detect_semantic_collapse_for_each_scenario(
    scenario_id: str,
) -> None:
    contract = load_quality_scenario_contract(
        scenario_id,
        include_quarantined=True,
    )

    report = build_cross_domain_control_report(contract)
    scenario_report = build_scenario_semantic_binding_report(contract)

    assert report["status"] == "pass", report["controls"]
    assert scenario_report["status"] == "pass", scenario_report["issues"]
    assert scenario_report["selected_evidence_refs"]
    controls = {control["control_id"]: control for control in report["controls"]}
    assert set(controls) >= set(REQUIRED_CROSS_DOMAIN_CONTROL_IDS)
    assert controls["generic_metric_collapse"]["failure_codes"] == [
        "semantic_intent_collapsed_to_generic_evidence"
    ]
    assert controls["manifest_role_source_selection"]["failure_codes"] == [
        "semantic_manifest_role_source_selection_false_pass",
        "semantic_intent_collapsed_to_generic_evidence"
    ]
    assert controls["generic_method_selection"]["failure_codes"] == [
        "semantic_intent_collapsed_to_generic_evidence"
    ]
    assert controls["no_norm_false_pass"]["failure_codes"] == [
        "semantic_no_norm_false_pass"
    ]
    assert controls["data_present_but_irrelevant_pass"]["failure_codes"] == [
        "semantic_data_present_but_irrelevant"
    ]
    assert controls["unsupported_final_claim"]["failure_codes"] == [
        "major_claim_missing_grounding"
    ]


@pytest.mark.parametrize("scenario_id", PHASE56_CROSS_DOMAIN_SCENARIO_IDS)
def test_metamorphic_prompt_variants_preserve_canonical_bindings(
    scenario_id: str,
) -> None:
    contract = load_quality_scenario_contract(
        scenario_id,
        include_quarantined=True,
    )

    report = build_metamorphic_prompt_report(contract)

    assert report["status"] == "pass", report["variants"]
    assert {variant["locale"] for variant in report["variants"]} >= {"en", "uk"}
    preserved_fields = {
        "canonical_jurisdiction",
        "time_context",
        "data_source_family",
        "legal_query",
        "method_expectation",
        "final_claim_refs",
    }
    for variant in report["variants"]:
        if variant["status"] == "blocked":
            assert variant["ambiguity_blocker_codes"]
            continue
        if variant["expected"] == "fail":
            assert variant["status"] == "fail"
            assert variant["failure_codes"]
            continue
        assert variant["status"] == "pass"
        assert preserved_fields <= set(variant["preserved_fields"])


def test_metamorphic_ambiguous_prompt_blocks_instead_of_rebinding_context() -> None:
    contract = deepcopy(
        load_quality_scenario_contract(
            PHASE56_CROSS_DOMAIN_SCENARIO_IDS[0],
            include_quarantined=True,
        )
    )
    contract["metamorphic_prompt_variants"].append(
        {
            "variant_id": "ambiguous_jurisdiction_and_time",
            "locale": "en",
            "prompt": "Assess the same policy for the region sometime next year.",
            "expected": "blocked",
            "ambiguity_blocker_codes": [
                "ambiguous_jurisdiction",
                "ambiguous_time_context",
            ],
        }
    )

    report = build_metamorphic_prompt_report(contract)

    blocked = {
        variant["variant_id"]: variant
        for variant in report["variants"]
        if variant["status"] == "blocked"
    }
    assert blocked["ambiguous_jurisdiction_and_time"][
        "ambiguity_blocker_codes"
    ] == [
        "ambiguous_jurisdiction",
        "ambiguous_time_context",
    ]


def test_metamorphic_prompt_text_is_observed_not_copied_from_canonical() -> None:
    contract = deepcopy(
        load_quality_scenario_contract(
            PHASE56_CROSS_DOMAIN_SCENARIO_IDS[0],
            include_quarantined=True,
        )
    )
    contract["metamorphic_prompt_variants"] = [
        {
            "variant_id": "wrong_jurisdiction_without_canonical_override",
            "locale": "en",
            "prompt": "Assess Poland household benefits and tax relief as of 2026-05-15.",
            "expected": "pass",
            "canonical_ref": "diagnostic_control_profile.canonical",
        }
    ]

    report = build_metamorphic_prompt_report(contract)

    variant = report["variants"][0]
    assert variant["status"] == "fail"
    assert variant["observed_canonical"]["canonical_jurisdiction"] == "PL"
    assert "metamorphic_canonical_jurisdiction_drift" in variant["failure_codes"]


def test_metamorphic_ambiguous_prompt_blocks_without_declared_blocker_hint() -> None:
    contract = deepcopy(
        load_quality_scenario_contract(
            PHASE56_CROSS_DOMAIN_SCENARIO_IDS[0],
            include_quarantined=True,
        )
    )
    contract["metamorphic_prompt_variants"] = [
        {
            "variant_id": "ambiguous_without_declared_hint",
            "locale": "en",
            "prompt": "Assess the same policy for the region sometime next year.",
            "expected": "pass",
            "canonical_ref": "diagnostic_control_profile.canonical",
        }
    ]

    report = build_metamorphic_prompt_report(contract)

    variant = report["variants"][0]
    assert variant["status"] == "blocked"
    assert {
        "ambiguous_jurisdiction",
        "ambiguous_time_context",
    } <= set(variant["ambiguity_blocker_codes"])


@pytest.mark.parametrize("scenario_id", PHASE56_CROSS_DOMAIN_SCENARIO_IDS)
def test_negative_controls_block_outputs_with_typed_failure_codes_and_operator_envelopes(
    scenario_id: str,
) -> None:
    contract = load_quality_scenario_contract(
        scenario_id,
        include_quarantined=True,
    )

    report = build_negative_control_report(contract)

    assert report["status"] == "pass", report["controls"]
    controls = {control["control_id"]: control for control in report["controls"]}
    assert set(controls) >= set(PHASE56_NEGATIVE_CONTROL_IDS)
    for control_id in PHASE56_NEGATIVE_CONTROL_IDS:
        control = controls[control_id]
        assert control["observed_status"] == "blocked"
        assert control["failure_codes"], control_id
        assert {
            "owner",
            "phase",
            "cause",
            "missing_input",
            "downstream_impact",
            "refs",
            "next_command",
        } <= set(control["failure_envelope"])
