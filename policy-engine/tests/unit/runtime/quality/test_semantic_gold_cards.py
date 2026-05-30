from __future__ import annotations

# ruff: noqa: S101
from copy import deepcopy

from polisyos.runtime.quality.semantic_fixtures import (
    SEMANTIC_EVALUATION_PACK_SCHEMA_VERSION,
    SEMANTIC_GOLD_CARD_SCHEMA_VERSION,
    evaluate_semantic_evaluation_pack,
    evaluate_semantic_gold_card_fixture,
    semantic_evaluation_pack_json_schema,
    semantic_gold_card_json_schema,
)


def _base_gold_card() -> dict[str, object]:
    return {
        "schema_version": SEMANTIC_GOLD_CARD_SCHEMA_VERSION,
        "fixture_id": "projection_laundering_semantic_fail",
        "title": "Projection summary cannot satisfy closeout authority",
        "expected_status": "semantic_fail",
        "failure_mode": "projection_laundering",
        "research_refs": ["E1", "C30", "C12"],
        "pattern_ids": ["P10", "P15", "P05"],
        "structural_pass_claimed": True,
        "structural_verdict": {
            "status": "pass",
            "validator_refs": ["structural-pdc-v1"],
            "completeness_claims": ["required_fields_present"],
        },
        "semantic_adjudication": {
            "status": "fail",
            "adjudicator": "policyos.semantic_gold_card.w1b",
            "failure_mode": "projection_laundering",
            "failure_code": "semantic_projection_laundering",
            "rationale": (
                "A public projection marks the case publishable without closeout authority."
            ),
            "authority_effect": "block_closeout",
            "required_remediation": (
                "Bind the claim to closeout evidence rather than projection output."
            ),
        },
        "semantic_probes": [
            {
                "probe_id": "projection-closeout-authority",
                "semantic_axis": "authority",
                "pattern_ids": ["P10", "P15", "P05"],
                "observed_signal": "Public export claims publishable status.",
                "expected_signal": "Closeout remains blocked until authority evidence exists.",
                "verdict": "fail",
                "failure_code": "semantic_projection_laundering",
                "evidence_refs": ["public://pdc/projection"],
            }
        ],
        "payload": {
            "case_id": "pdc-w1b-projection",
            "claim_ids": ["claim-projection"],
            "authority_chain": {
                "closeout_evidence_ref": None,
                "authoritative_for": ["public_summary"],
                "may_not_use_for": ["closeout", "producer_evidence"],
            },
            "projection": {
                "source_surface": "public_export",
                "claims_publishable": True,
                "public_status": "publishable",
            },
        },
    }


def test_semantic_gold_card_schema_is_strict_and_named() -> None:
    schema = semantic_gold_card_json_schema()

    assert schema["title"] == "PolicyDesignCaseSemanticGoldCardFixture"
    assert schema["properties"]["schema_version"]["const"] == SEMANTIC_GOLD_CARD_SCHEMA_VERSION
    assert schema["additionalProperties"] is False


def test_projection_false_pass_structural_pass_still_semantic_fails() -> None:
    result = evaluate_semantic_gold_card_fixture(_base_gold_card())

    assert result["fixture_status"] == "valid"
    assert result["structural_status"] == "pass"
    assert result["semantic_status"] == "fail"
    assert result["detected_failure_codes"] == ["semantic_projection_laundering"]
    assert result["expected_failure_code"] == "semantic_projection_laundering"


def test_gold_card_rejects_structural_only_fixture_without_semantic_probe() -> None:
    card = deepcopy(_base_gold_card())
    card["semantic_probes"] = []

    result = evaluate_semantic_gold_card_fixture(card)

    assert result["fixture_status"] == "invalid"
    assert "semantic_gold_card_probe_missing" in _issue_codes(result)


def test_gold_card_rejects_expected_failure_not_detected_from_payload() -> None:
    card = deepcopy(_base_gold_card())
    payload = deepcopy(card["payload"])
    assert isinstance(payload, dict)
    payload["authority_chain"] = {
        "closeout_evidence_ref": "cas://sha256/11111111111111111111111111111111"
    }
    payload["projection"] = {"claims_publishable": False, "public_status": "limited"}
    card["payload"] = payload

    result = evaluate_semantic_gold_card_fixture(card)

    assert result["fixture_status"] == "invalid"
    assert "semantic_gold_card_expected_failure_not_detected" in _issue_codes(result)


def test_w5b_e22_gold_card_detects_participation_prevalence_negative() -> None:
    result = evaluate_semantic_gold_card_fixture(_w5b_prevalence_gold_card())

    assert result["fixture_status"] == "valid"
    assert result["structural_status"] == "pass"
    assert result["semantic_status"] == "fail"
    assert result["expected_failure_code"] == "semantic_participation_prevalence_negative"
    assert result["detected_failure_codes"] == ["semantic_participation_prevalence_negative"]


def test_w5b_detectors_cover_unreachable_recourse_and_hardcoded_thresholds() -> None:
    recourse = _w5b_recourse_gold_card()
    threshold = _w5b_threshold_gold_card()

    recourse_result = evaluate_semantic_gold_card_fixture(recourse)
    threshold_result = evaluate_semantic_gold_card_fixture(threshold)

    assert recourse_result["fixture_status"] == "valid"
    assert recourse_result["detected_failure_codes"] == ["semantic_recourse_pointer_unreachable"]
    assert threshold_result["fixture_status"] == "valid"
    assert threshold_result["detected_failure_codes"] == ["semantic_tuned_threshold_hardcoding"]


def test_w5b_pack_schema_requires_public_hidden_and_rotating_splits() -> None:
    schema = semantic_evaluation_pack_json_schema()
    manifest = _w5b_pack_manifest()
    fixtures_by_ref = {
        manifest["splits"][0]["fixtures"][0]["fixture_ref"]: _w5b_prevalence_gold_card(),
        manifest["splits"][1]["fixtures"][0]["fixture_ref"]: _w5b_recourse_gold_card(),
        manifest["splits"][2]["fixtures"][0]["fixture_ref"]: _w5b_threshold_gold_card(),
    }

    result = evaluate_semantic_evaluation_pack(manifest, fixtures_by_ref)

    assert schema["properties"]["schema_version"]["const"] == (
        SEMANTIC_EVALUATION_PACK_SCHEMA_VERSION
    )
    assert result["status"] == "pass", result["issues"]
    assert result["split_summary"] == {"public": 1, "hidden": 1, "rotating": 1}
    assert set(result["detected_failure_modes"]) == {
        "participation_prevalence_negative",
        "unreachable_recourse_pointer",
        "tuned_threshold_hardcoding",
    }


def test_w5b_pack_rejects_hidden_fixture_detail_leakage() -> None:
    manifest = _w5b_pack_manifest()
    hidden_split = manifest["splits"][1]
    hidden_split["public_export_visibility"] = "public_detail"
    fixtures_by_ref = {
        manifest["splits"][0]["fixtures"][0]["fixture_ref"]: _w5b_prevalence_gold_card(),
        manifest["splits"][1]["fixtures"][0]["fixture_ref"]: _w5b_recourse_gold_card(),
        manifest["splits"][2]["fixtures"][0]["fixture_ref"]: _w5b_threshold_gold_card(),
    }

    result = evaluate_semantic_evaluation_pack(manifest, fixtures_by_ref)

    assert result["status"] == "fail"
    assert "semantic_pack_hidden_detail_leakage" in _issue_codes(result)


def _issue_codes(result: dict[str, object]) -> set[str]:
    return {
        str(issue["code"])
        for issue in result["issues"]  # type: ignore[index]
    }


def _w5b_prevalence_gold_card() -> dict[str, object]:
    card = deepcopy(_base_gold_card())
    card.update(
        {
            "fixture_id": "w5b_participation_prevalence_negative_semantic_fail",
            "title": "Thin consultation cannot satisfy affected-population prevalence",
            "failure_mode": "participation_prevalence_negative",
            "research_refs": ["E22", "C30", "C19", "C34"],
            "pattern_ids": ["P10", "P15", "P05"],
            "semantic_adjudication": {
                "status": "fail",
                "adjudicator": "policyos.semantic_gold_card.w5b",
                "failure_mode": "participation_prevalence_negative",
                "failure_code": "semantic_participation_prevalence_negative",
                "rationale": (
                    "The case projects affected-population prevalence from a "
                    "nonrepresentative consultation despite a lower allowed claim use."
                ),
                "authority_effect": "block_closeout",
                "required_remediation": (
                    "Downgrade the participation claim use or add representative "
                    "population participation evidence."
                ),
            },
            "semantic_probes": [
                {
                    "probe_id": "participation-prevalence-negative",
                    "semantic_axis": "participation",
                    "pattern_ids": ["P10", "P15", "P05"],
                    "observed_signal": "Projection claims affected-population prevalence.",
                    "expected_signal": "Allowed use remains qualitative or context-only.",
                    "verdict": "fail",
                    "failure_code": "semantic_participation_prevalence_negative",
                    "evidence_refs": ["event://policy-design-case/w5b/thin-consultation"],
                }
            ],
            "payload": {
                "case_id": "pdc-w5b-participation-prevalence",
                "claim_ids": ["claim-participation-prevalence"],
                "participation": {
                    "claim_use_requested": "prevalence",
                    "claim_use_allowed": "qualitative",
                    "authority_level": "production",
                    "population_scope": "affected_population",
                    "source_kind": "consultation",
                    "provenance_class": "C_attributable_nonrepresentative",
                    "representativeness_class": "nonrepresentative",
                    "downgrade_ref": None,
                    "blocker_ref": None,
                },
                "projection": {
                    "participation_claim_use": "prevalence",
                    "prevalence_supported": True,
                    "population_scope": "affected_population",
                },
            },
        }
    )
    return card


def _w5b_recourse_gold_card() -> dict[str, object]:
    card = deepcopy(_base_gold_card())
    card.update(
        {
            "fixture_id": "w5b_unreachable_recourse_pointer_semantic_fail",
            "title": "Contested public case cannot publish with unreachable recourse",
            "failure_mode": "unreachable_recourse_pointer",
            "research_refs": ["E22", "C30", "C17", "C39b"],
            "pattern_ids": ["P10", "P05"],
            "semantic_adjudication": {
                "status": "fail",
                "adjudicator": "policyos.semantic_gold_card.w5b",
                "failure_mode": "unreachable_recourse_pointer",
                "failure_code": "semantic_recourse_pointer_unreachable",
                "rationale": (
                    "A high-stakes contested production publication carries an "
                    "unreachable recourse pointer."
                ),
                "authority_effect": "block_closeout",
                "required_remediation": (
                    "Publish only after a verified-reachable recourse pointer exists."
                ),
            },
            "semantic_probes": [
                {
                    "probe_id": "recourse-pointer-reachability",
                    "semantic_axis": "recourse",
                    "pattern_ids": ["P10", "P05"],
                    "observed_signal": (
                        "Publication status is publishable with an unreachable pointer."
                    ),
                    "expected_signal": (
                        "Publication fails with public_export_recourse_pointer_unreachable."
                    ),
                    "verdict": "fail",
                    "failure_code": "semantic_recourse_pointer_unreachable",
                    "evidence_refs": ["runtime-event://recourse-pointer/unreachable"],
                }
            ],
            "payload": {
                "case_id": "pdc-w5b-recourse",
                "claim_ids": ["claim-contested-publication"],
                "contestability": {
                    "contestability_status": "contested",
                    "authority_level": "production",
                    "stakes": "high_stakes",
                    "publication_status": "publishable",
                    "recourse_pointer": {
                        "uri": "https://appeals.example.test/pdc/w5b",
                        "verification_status": "unreachable",
                        "verified_at": "2026-05-23T00:00:00Z",
                        "verification_ref": "runtime-event://recourse-pointer/unreachable",
                    },
                },
            },
        }
    )
    return card


def _w5b_threshold_gold_card() -> dict[str, object]:
    card = deepcopy(_base_gold_card())
    card.update(
        {
            "fixture_id": "w5b_tuned_threshold_hardcoding_semantic_fail",
            "title": "Tuned threshold cannot be projected as final structural truth",
            "failure_mode": "tuned_threshold_hardcoding",
            "research_refs": ["E22", "C30", "C35"],
            "pattern_ids": ["P10", "P13"],
            "semantic_adjudication": {
                "status": "fail",
                "adjudicator": "policyos.semantic_gold_card.w5b",
                "failure_mode": "tuned_threshold_hardcoding",
                "failure_code": "semantic_tuned_threshold_hardcoding",
                "rationale": (
                    "A provisional participation threshold is hardcoded and projected "
                    "as final without governed config or ADR evidence."
                ),
                "authority_effect": "review_required",
                "required_remediation": (
                    "Move the threshold to governed config with owner and version."
                ),
            },
            "semantic_probes": [
                {
                    "probe_id": "tuned-threshold-hardcoding",
                    "semantic_axis": "tuned_config",
                    "pattern_ids": ["P10", "P13"],
                    "observed_signal": "Output presents a hardcoded threshold as final.",
                    "expected_signal": (
                        "Threshold remains governed config until evidence promotes it."
                    ),
                    "verdict": "fail",
                    "failure_code": "semantic_tuned_threshold_hardcoding",
                    "evidence_refs": ["repo://docs/adr/0167-participation-legitimacy-matrix.md"],
                }
            ],
            "payload": {
                "case_id": "pdc-w5b-threshold",
                "claim_ids": ["claim-threshold"],
                "tuned_parameters": {
                    "parameters": [
                        {
                            "parameter_id": "participation.prevalence.minimum_response_rate",
                            "value": 0.73,
                            "status": "hardcoded_final",
                            "owner": None,
                            "config_ref": None,
                            "adr_ref": None,
                        }
                    ],
                    "public_output": {
                        "threshold_status": "final",
                        "claims_structural_truth": True,
                    },
                },
            },
        }
    )
    return card


def _w5b_pack_manifest() -> dict[str, object]:
    return {
        "schema_version": SEMANTIC_EVALUATION_PACK_SCHEMA_VERSION,
        "pack_id": "w5b_false_pass_semantic_evaluation_pack",
        "phase_id": "W5.B",
        "title": "W5.B Semantic false-pass evaluation pack",
        "research_refs": ["E22", "C30", "P10", "P14", "P15"],
        "pattern_ids": ["P10", "P14", "P15"],
        "adjudication_labels": ["false_pass", "unsupported", "limitation_required"],
        "required_failure_modes": [
            "participation_prevalence_negative",
            "unreachable_recourse_pointer",
            "tuned_threshold_hardcoding",
        ],
        "reviewer_protocol_ref": (
            "repo://docs/plans/active/"
            "POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_RESEARCH_PLAN.md"
            "#C30---Semantic-Benchmark-Rubric"
        ),
        "splits": [
            {
                "split": "public",
                "purpose": "Stable public examples for semantic adequacy review.",
                "public_export_visibility": "public_detail",
                "fixtures": [
                    {
                        "fixture_id": "w5b_participation_prevalence_negative_semantic_fail",
                        "fixture_ref": (
                            "repo://tests/fixtures/policy_design_case/semantic_evaluation_packs/"
                            "public/w5b_participation_prevalence_negative_semantic_fail.json"
                        ),
                        "failure_mode": "participation_prevalence_negative",
                    }
                ],
            },
            {
                "split": "hidden",
                "purpose": "Internal holdout fixtures for anti-overfitting checks.",
                "public_export_visibility": "aggregate_only",
                "fixtures": [
                    {
                        "fixture_id": "w5b_unreachable_recourse_pointer_semantic_fail",
                        "fixture_ref": (
                            "repo://tests/fixtures/policy_design_case/semantic_evaluation_packs/"
                            "hidden/w5b_unreachable_recourse_pointer_semantic_fail.json"
                        ),
                        "failure_mode": "unreachable_recourse_pointer",
                    }
                ],
            },
            {
                "split": "rotating",
                "purpose": "Time-limited rotating challenge fixtures.",
                "public_export_visibility": "aggregate_only",
                "rotation_policy": {
                    "rotation_interval_days": 30,
                    "next_rotation_due": "2026-06-22",
                    "owner": "team-evaluation",
                },
                "fixtures": [
                    {
                        "fixture_id": "w5b_tuned_threshold_hardcoding_semantic_fail",
                        "fixture_ref": (
                            "repo://tests/fixtures/policy_design_case/semantic_evaluation_packs/"
                            "rotating/w5b_tuned_threshold_hardcoding_semantic_fail.json"
                        ),
                        "failure_mode": "tuned_threshold_hardcoding",
                    }
                ],
            },
        ],
        "benchmark_metadata": {
            "leakage_policy": "hidden_and_rotating_fixture_ids_are_internal_only",
            "fixture_rotation_ref": "repo://docs/reference/policy-design-case-failure-patterns.md#Register",
            "validation_command": (
                "uv run pytest tests/repo_quality/tools/"
                "test_policy_design_case_w5b_semantic_evaluation_packs.py -q"
            ),
        },
    }
