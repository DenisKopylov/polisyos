from __future__ import annotations

from copy import deepcopy

from polisyos.runtime.quality.semantic_binding import (
    PRODUCER_SPINE_CONSUMER_COMPONENTS,
    PRODUCER_SPINE_CONTEXT_SCHEMA_VERSION,
    SEMANTIC_BINDING_SCHEMA_VERSION,
    ProducerSpineReadContext,
    SemanticBindingLedger,
    build_producer_spine_read_context,
    close_semantic_binding_ledger,
    build_semantic_binding_ledger,
    evaluate_semantic_binding_ledger,
    producer_spine_read_context_for,
)
from tests._helpers.hds_quality import (
    blocking_codes,
    complete_job_payload,
    complete_quality_evidence,
    scorecard_for,
    sha,
)


def _complete_ledger() -> dict[str, object]:
    return {
        "schema_version": SEMANTIC_BINDING_SCHEMA_VERSION,
        "semantic_binding_ref": sha("b"),
        "status": "pass",
        "policy_intent_ref": sha("a"),
        "spine_context": {
            "schema_version": PRODUCER_SPINE_CONTEXT_SCHEMA_VERSION,
            "context_id": "producer-spine-context-run-10-2",
            "concept_spine_ref": sha("2"),
            "jurisdiction_spine_ref": sha("6"),
            "canonical_concept_refs": ["concept.msme_survival_rate"],
            "jurisdiction_refs": ["UA"],
            "consumer_components": list(PRODUCER_SPINE_CONSUMER_COMPONENTS),
        },
        "intent": {
            "policy_intent_ref": sha("a"),
            "canonical_concept_refs": ["concept.msme_survival_rate"],
            "jurisdiction": "UA",
            "time_context": "2026-05-15",
            "population": "wartime MSMEs",
            "intervention": "wartime credit support",
            "treatment": "credit eligibility",
            "outcome": "msme survival",
            "legal_domain": "wartime_msme_support",
            "data_source_family": "production_msme_panel",
            "dataset": "production-msme-panel",
            "columns": ["firm_id", "survival", "credit_amount"],
            "method_family": "causal_effect_estimation",
            "final_claim": "rec_1",
            "monitoring_signal": "msme_survival_rate",
            "public_artifact_section": "recommendations",
        },
        "lex": [
            {
                "binding_id": "lex-binding-1",
                "legal_query_terms": ["credit support", "wartime MSME eligibility"],
                "legal_query_refs": ["lex-query:welfare-msme"],
                "concept_refs": ["concept.msme_survival_rate"],
                "candidate_norm_refs": [
                    "norm.ua.credit_eligibility",
                    "norm.ua.procurement_fixture",
                ],
                "selected_norm_refs": ["norm.ua.credit_eligibility"],
                "rejected_norm_refs": ["norm.ua.procurement_fixture"],
                "legal_snapshot_refs": [sha("d")],
                "jurisdiction_filters": ["UA"],
                "effective_date_filters": ["2026-05-15"],
                "hierarchy_conflict_refs": ["conflict:resolved-credit-eligibility"],
                "competence_refs": ["competence:norm.ua.credit_eligibility"],
                "no_norm_blocker_refs": [],
                "retrieval_error_blocker_refs": [],
                **_spine_binding_fields("lex"),
            }
        ],
        "fabric": [
            {
                "binding_id": "fabric-binding-1",
                "candidate_dataset_source_refs": [
                    "production-msme-panel",
                    "fixture-source",
                ],
                "selected_dataset_source_refs": ["production-msme-panel"],
                "rejected_dataset_source_refs": ["fixture-source"],
                "metric_bindings": [
                    {
                        "metric_id": "msme_survival_rate",
                        "claim_ids": ["rec_1"],
                        "source_refs": ["production-msme-panel"],
                    }
                ],
                "column_bindings": [
                    {
                        "claim_id": "rec_1",
                        "source_ref": "production-msme-panel",
                        "column_refs": ["firm_id", "survival", "credit_amount"],
                    }
                ],
                "unit_bindings": [{"metric_id": "credit_amount", "unit": "UAH"}],
                "geography_bindings": [{"source_ref": "production-msme-panel", "geo": "UA"}],
                "calendar_time_bindings": [
                    {"source_ref": "production-msme-panel", "time_window": "2024-2026"}
                ],
                "source_freshness": [{"source_ref": "production-msme-panel", "status": "pass"}],
                "data_coverage": [
                    {
                        "source_ref": "production-msme-panel",
                        "claim_ids": [
                            "rec_1",
                            "legal_1",
                            "budget_1",
                            "dist_1",
                            "risk_1",
                            "monitor_survival",
                            "uncertainty_1",
                        ],
                        "status": "covers",
                    }
                ],
                "dictionary_refs": ["dictionary:production-msme-panel:v1"],
                "lineage_refs": ["lineage:production-msme-panel:v1"],
                **_wave13_fabric_lineage_fields(),
                "data_gap_blocker_refs": [],
                "ambiguity_blocker_refs": [],
                **_spine_binding_fields("fabric"),
            }
        ],
        "scholar": [
            {
                "binding_id": "scholar-binding-1",
                "candidate_literature_refs": [
                    "literature:msme-survival-review",
                    "literature:procurement-fixture",
                ],
                "selected_literature_refs": ["literature:msme-survival-review"],
                "rejected_literature_refs": ["literature:procurement-fixture"],
                "support_link_refs": ["support:msme-survival-review:rec_1"],
                "conflict_link_refs": ["conflict:literature:resolved"],
                "retrieval_blocker_refs": [],
                **_spine_binding_fields("scholar"),
            }
        ],
        "foundry": [
            {
                "binding_id": "foundry-binding-1",
                "selected_method_refs": ["causal.difference_in_differences"],
                "rejected_method_refs": ["descriptive.summary"],
                "scenario_method_expectation_refs": ["causal_effect_estimation"],
                "assumptions": ["parallel_trends"],
                "input_coverage": [{"source_ref": "production-msme-panel", "status": "pass"}],
                "sample_power_adequacy": [{"method_ref": "causal.difference_in_differences"}],
                "placebo_negative_control_refs": ["placebo:pre_period"],
                "sensitivity_refs": ["sensitivity:survival-v1"],
                "uncertainty_refs": ["uncertainty:survival-v1"],
                "method_incompatibility_blocker_refs": [],
                **_spine_binding_fields("foundry"),
            }
        ],
        "scientist": [
            {
                "binding_id": "scientist-binding-1",
                "major_claim_ids": ["rec_1"],
                "recommendation_ids": ["rec_1"],
                "legal_assertion_ids": ["legal_1"],
                "budget_feasibility_ids": ["budget_1"],
                "distributional_impact_ids": ["dist_1"],
                "implementation_risk_ids": ["risk_1"],
                "monitoring_ids": ["monitor_survival"],
                "residual_uncertainty_ids": ["uncertainty_1"],
                "required_data_refs": ["production-msme-panel"],
                "required_method_refs": ["causal.difference_in_differences"],
                "required_norm_refs": ["norm.ua.credit_eligibility"],
                "required_literature_refs": ["literature:msme-survival-review"],
                "required_uncertainty_refs": ["uncertainty:survival-v1"],
                "required_blocker_refs": [],
                "claim_evidence_paths": _complete_claim_evidence_paths(),
                **_spine_binding_fields("scientist"),
            }
        ],
        "final_compiler": [
            {
                "binding_id": "final-binding-1",
                "major_claim_ids": ["rec_1"],
                "recommendation_ids": ["rec_1"],
                "legal_assertion_ids": ["legal_1"],
                "budget_feasibility_ids": ["budget_1"],
                "distributional_impact_ids": ["dist_1"],
                "implementation_risk_ids": ["risk_1"],
                "monitoring_ids": ["monitor_survival"],
                "residual_uncertainty_ids": ["uncertainty_1"],
                "required_data_refs": ["production-msme-panel"],
                "required_method_refs": ["causal.difference_in_differences"],
                "required_norm_refs": ["norm.ua.credit_eligibility"],
                "required_literature_refs": ["literature:msme-survival-review"],
                "required_uncertainty_refs": ["uncertainty:survival-v1"],
                "required_blocker_refs": [],
                "public_artifact_section_refs": ["section:recommendations"],
                "claim_evidence_paths": _complete_claim_evidence_paths(),
                **_spine_binding_fields("final_compiler"),
            }
        ],
    }


def _spine_binding_fields(component: str) -> dict[str, object]:
    return {
        "consumed_concept_spine_ref": sha("2"),
        "consumed_jurisdiction_spine_ref": sha("6"),
        "candidate_spine_binding_refs": [
            f"spine-binding:{component}:concept.msme_survival_rate:UA"
        ],
        "spine_blocker_refs": [],
        "local_labels": [],
    }


def _wave13_fabric_lineage_fields() -> dict[str, object]:
    return {
        "data_forge_snapshot_refs": [sha("4")],
        "source_facets": [
            {
                "source_ref": "production-msme-panel",
                "source_family": "production_msme_panel",
                "source_rights": "government_open_data",
                "dataset_ref": "dataset:production-msme-panel",
                "dictionary_ref": "dictionary:production-msme-panel:v1",
                "schema_ref": "schema:production-msme-panel:v1",
                "field_refs": [
                    "field:production-msme-panel.firm_id",
                    "field:production-msme-panel.survival",
                    "field:production-msme-panel.credit_amount",
                ],
                "unit_refs": ["unit:percent", "unit:UAH"],
                "geography_refs": ["UA"],
                "time_coverage_refs": ["2024-2026"],
                "quality_refs": ["quality:production-msme-panel:v1"],
                "missingness_refs": ["missingness:production-msme-panel:v1"],
                "freshness_refs": ["freshness:production-msme-panel:2026-05-15"],
                "lineage_refs": ["lineage:production-msme-panel:v1"],
                "transformation_refs": ["transform:survival-rate:v1"],
                "data_forge_snapshot_refs": [sha("4")],
                "selected_candidate_ref": "production-msme-panel",
                "rejected_candidate_refs": ["fixture-source"],
            }
        ],
        "derived_features": [
            {
                "feature_ref": "feature:msme_survival_rate",
                "source_ref": "production-msme-panel",
                "source_facet_refs": ["field:production-msme-panel.survival"],
                "claim_ids": ["rec_1"],
                "claim_support_feature_refs": ["claim-feature:rec_1:msme_survival_rate"],
                "lineage_refs": ["lineage:production-msme-panel:v1"],
                "transformation_refs": ["transform:survival-rate:v1"],
            }
        ],
        "claim_support_feature_refs": ["claim-feature:rec_1:msme_survival_rate"],
    }


def _complete_claim_evidence_paths() -> list[dict[str, object]]:
    return [
        {
            "claim_id": "rec_1",
            "scenario_requirement_refs": ["scenario-public_golden:msme_survival"],
            "canonical_concept_refs": ["concept.msme_survival_rate"],
            "fabric_binding_refs": ["fabric-binding-1"],
            "source_refs": ["production-msme-panel"],
            "column_refs": ["firm_id", "survival", "credit_amount"],
            "lex_binding_refs": ["lex-binding-1"],
            "selected_norm_refs": ["norm.ua.credit_eligibility"],
            "foundry_binding_refs": ["foundry-binding-1"],
            "selected_method_refs": ["causal.difference_in_differences"],
            "method_output_refs": ["method-output:causal.difference_in_differences"],
            "scientist_claim_refs": ["claim:rec_1"],
            "argument_refs": ["arg-rec-1"],
            "warrant_refs": ["warrant-rec-1"],
            "rebuttal_refs": ["rebuttal-rec-1"],
            "counter_evidence_refs": ["counter-evidence-rec-1"],
            "limitation_refs": ["deficit-assessment-rec-1"],
            "blocker_refs": [],
        }
    ]


def _evidence_with_ledger(ledger: dict[str, object]) -> dict[str, object]:
    evidence = complete_quality_evidence()
    evidence["semantic_binding_ledger"] = ledger
    return evidence


def test_spine_read_context_exposes_previous_wave_refs_to_producers() -> None:
    context_payload = build_producer_spine_read_context(
        concept_spine={
            "concept_ref": sha("2"),
            "canonical_concept_ids": ["concept.msme_survival_rate"],
        },
        jurisdiction_spine={
            "jurisdiction_spine_ref": sha("6"),
            "jurisdictions": [{"jurisdiction_id": "UA"}],
        },
    )
    context = ProducerSpineReadContext.model_validate(context_payload)

    assert context.schema_version == PRODUCER_SPINE_CONTEXT_SCHEMA_VERSION
    assert context.concept_spine_ref == sha("2")
    assert context.jurisdiction_spine_ref == sha("6")
    assert context.consumer_components == PRODUCER_SPINE_CONSUMER_COMPONENTS

    for component in PRODUCER_SPINE_CONSUMER_COMPONENTS:
        producer_view = producer_spine_read_context_for(component, context)
        assert producer_view["consumer_component"] == component
        assert producer_view["concept_spine_ref"] == sha("2")
        assert producer_view["jurisdiction_spine_ref"] == sha("6")


def test_semantic_binding_ledger_preserves_required_phase_records() -> None:
    ledger = SemanticBindingLedger.model_validate(_complete_ledger())

    assert ledger.schema_version == SEMANTIC_BINDING_SCHEMA_VERSION
    assert ledger.spine_context is not None
    assert ledger.spine_context.consumer_components == PRODUCER_SPINE_CONSUMER_COMPONENTS
    assert ledger.intent.dataset == "production-msme-panel"
    assert ledger.intent.public_artifact_section == "recommendations"
    assert ledger.lex[0].candidate_norm_refs == (
        "norm.ua.credit_eligibility",
        "norm.ua.procurement_fixture",
    )
    assert ledger.lex[0].legal_query_terms == (
        "credit support",
        "wartime MSME eligibility",
    )
    assert ledger.lex[0].concept_refs == ("concept.msme_survival_rate",)
    assert ledger.lex[0].rejected_norm_refs == ("norm.ua.procurement_fixture",)
    assert ledger.lex[0].competence_refs == ("competence:norm.ua.credit_eligibility",)
    assert ledger.fabric[0].dictionary_refs == ("dictionary:production-msme-panel:v1",)
    assert ledger.fabric[0].data_forge_snapshot_refs == (sha("4"),)
    assert ledger.fabric[0].source_facets[0].field_refs == (
        "field:production-msme-panel.firm_id",
        "field:production-msme-panel.survival",
        "field:production-msme-panel.credit_amount",
    )
    assert ledger.fabric[0].derived_features[0].claim_support_feature_refs == (
        "claim-feature:rec_1:msme_survival_rate",
    )
    assert ledger.scholar[0].selected_literature_refs == ("literature:msme-survival-review",)
    assert ledger.foundry[0].placebo_negative_control_refs == ("placebo:pre_period",)
    assert ledger.scientist[0].major_claim_ids == ("rec_1",)
    assert ledger.scientist[0].claim_evidence_paths[0].claim_id == "rec_1"
    assert ledger.final_compiler[0].public_artifact_section_refs == ("section:recommendations",)


def test_live_ledger_runtime_report_status_blocked_is_reader_compatible() -> None:
    payload = _complete_ledger()
    payload["runtime_report_status"] = "blocked"
    payload["status"] = "blocked"

    ledger = SemanticBindingLedger.model_validate(payload)
    evaluation = evaluate_semantic_binding_ledger(payload)

    assert ledger.runtime_report_status == "blocked"
    assert evaluation.status == "blocked"
    assert evaluation.reason_family == "complete"


def test_material_claim_fails_when_binding_axes_are_empty() -> None:
    ledger = _complete_ledger()
    for phase in ("scientist", "final_compiler"):
        binding = deepcopy(ledger[phase][0])  # type: ignore[index]
        assert isinstance(binding, dict)
        binding["claim_evidence_paths"] = [
            {
                "claim_id": "rec_1",
                "scenario_requirement_refs": ["scenario-public_golden:msme_survival"],
                "scientist_claim_refs": ["claim:rec_1"],
                "canonical_concept_refs": [],
                "selected_norm_refs": [],
                "column_refs": [],
                "method_output_refs": [],
                "argument_refs": ["arg-rec-1"],
                "warrant_refs": ["warrant-rec-1"],
                "rebuttal_refs": ["rebuttal-rec-1"],
                "counter_evidence_refs": ["counter-evidence-rec-1"],
                "limitation_refs": ["deficit-assessment-rec-1"],
            }
        ]
        ledger[phase] = [binding]  # type: ignore[index]

    evaluation = evaluate_semantic_binding_ledger(ledger)

    assert evaluation.status == "fail"
    assert {
        "semantic_major_claim_canonical_concept_refs_missing",
        "semantic_major_claim_selected_norm_refs_missing",
        "semantic_major_claim_column_refs_missing",
        "semantic_major_claim_method_output_refs_missing",
    } <= {issue.code for issue in evaluation.issues}


def test_cloud_pass_shape_is_closed_by_producer_semantic_evaluation() -> None:
    ledger = _complete_ledger()
    ledger["status"] = "pass"
    ledger["runtime_report_status"] = None
    for phase in ("scientist", "final_compiler"):
        binding = deepcopy(ledger[phase][0])  # type: ignore[index]
        assert isinstance(binding, dict)
        binding["claim_evidence_paths"] = [
            {
                "claim_id": "rec_1",
                "source_refs": ["production-msme-panel"],
                "selected_norm_refs": ["norm.ua.credit_eligibility"],
                "selected_method_refs": ["causal.difference_in_differences"],
                "method_output_refs": ["method-output:causal.difference_in_differences"],
                "scientist_claim_refs": ["claim:rec_1"],
            }
        ]
        ledger[phase] = [binding]  # type: ignore[index]

    closed = close_semantic_binding_ledger(ledger)

    issue_codes = {issue["code"] for issue in closed["issues"]}
    assert closed["status"] == "fail"
    assert closed["runtime_report_status"] == "fail"
    assert {
        "semantic_major_claim_scenario_requirement_refs_missing",
        "semantic_major_claim_canonical_concept_refs_missing",
        "semantic_major_claim_column_refs_missing",
        "semantic_major_claim_argument_refs_missing",
        "semantic_major_claim_warrant_refs_missing",
        "semantic_major_claim_rebuttal_refs_missing",
        "semantic_major_claim_counter_evidence_refs_missing",
        "semantic_major_claim_limitation_refs_missing",
    } <= issue_codes
    assert closed["semantic_closure"]["issue_codes"] == sorted(issue_codes)


def test_complete_claim_evidence_path_closes_data_legal_method_and_argument_axes() -> None:
    ledger = SemanticBindingLedger.model_validate(_complete_ledger())
    path = ledger.final_compiler[0].claim_evidence_paths[0]

    evaluation = evaluate_semantic_binding_ledger(ledger)

    assert evaluation.status == "pass"
    assert path.claim_id == "rec_1"
    assert path.scenario_requirement_refs == ("scenario-public_golden:msme_survival",)
    assert path.fabric_binding_refs == ("fabric-binding-1",)
    assert path.lex_binding_refs == ("lex-binding-1",)
    assert path.foundry_binding_refs == ("foundry-binding-1",)
    assert path.scientist_claim_refs == ("claim:rec_1",)
    assert path.selected_norm_refs == ("norm.ua.credit_eligibility",)
    assert path.column_refs == ("firm_id", "survival", "credit_amount")
    assert path.method_output_refs == ("method-output:causal.difference_in_differences",)
    assert path.argument_refs == ("arg-rec-1",)
    assert path.warrant_refs == ("warrant-rec-1",)
    assert path.counter_evidence_refs == ("counter-evidence-rec-1",)
    assert path.limitation_refs == ("deficit-assessment-rec-1",)


def test_semantic_binding_builder_preserves_runtime_report_refs() -> None:
    evidence = complete_quality_evidence()
    normative = deepcopy(evidence["normative_evidence"])  # type: ignore[index]
    assert isinstance(normative, dict)
    normative.update(
        {
            "legal_corpus_snapshot": {"snapshot_ref": sha("d")},
            "query_terms": ["credit support", "wartime MSME eligibility"],
            "concept_refs": ["concept.msme_survival_rate"],
            "conflicts": [{"conflict_id": "conflict:resolved-credit-eligibility"}],
            "competence": [
                {
                    "competence_ref": "competence:norm.ua.credit_eligibility",
                    "norm_id": "norm.ua.credit_eligibility",
                }
            ],
        }
    )

    ledger = build_semantic_binding_ledger(
        runtime_refs={"policy_intent_ref": sha("a")},
        normative_evidence=normative,
        fabric_retrieval_trace=evidence["fabric_retrieval_trace"],  # type: ignore[index]
        foundry_method_report=evidence["foundry_method_report"],  # type: ignore[index]
        policy_grounding_matrix=evidence["policy_grounding_matrix"],  # type: ignore[index]
        decision_artifact_contract={
            "statements": [{"statement_scope": "recommendations", "evidence_refs": [sha("1")]}]
        },
    )

    validated = SemanticBindingLedger.model_validate(ledger)
    assert validated.semantic_binding_ref.startswith("sha256:")
    assert validated.lex[0].selected_norm_refs == ("norm.ua.credit_eligibility",)
    assert validated.lex[0].legal_query_terms == (
        "credit support",
        "wartime MSME eligibility",
    )
    assert validated.lex[0].concept_refs == ("concept.msme_survival_rate",)
    assert validated.lex[0].legal_snapshot_refs == (sha("d"),)
    assert validated.lex[0].hierarchy_conflict_refs == (
        "conflict:resolved-credit-eligibility",
    )
    assert validated.lex[0].competence_refs == ("competence:norm.ua.credit_eligibility",)
    assert validated.fabric[0].candidate_dataset_source_refs == ("production-msme-panel",)
    assert validated.fabric[0].selected_dataset_source_refs == ("production-msme-panel",)
    assert validated.fabric[0].data_forge_snapshot_refs
    assert validated.fabric[0].source_facets[0].source_ref == "production-msme-panel"
    assert validated.fabric[0].derived_features[0].claim_support_feature_refs == (
        "claim-feature:rec_1:msme_survival_rate",
    )
    assert validated.foundry[0].selected_method_refs == ("causal.difference_in_differences",)
    assert validated.final_compiler[0].public_artifact_section_refs == ("section:recommendations",)


def test_semantic_binding_builder_fails_status_when_claim_closure_is_missing() -> None:
    evidence = complete_quality_evidence()
    ledger = build_semantic_binding_ledger(
        runtime_refs={
            "policy_intent_ref": sha("a"),
            "concept_spine_ref": "unbound",
            "jurisdiction_spine_ref": "unbound",
        },
        normative_evidence=evidence["normative_evidence"],  # type: ignore[index]
        fabric_retrieval_trace={
            "selected_sources": [
                {
                    "source_id": "production-msme-panel",
                    "source_family": "production_msme_panel",
                }
            ]
        },
        foundry_method_report=evidence["foundry_method_report"],  # type: ignore[index]
        policy_grounding_matrix={
            "claims": [
                {
                    "claim_id": "rec_1",
                    "claim_type": "recommendation",
                    "major": True,
                    "text": "Target wartime credit support to eligible MSMEs.",
                    "data_refs": ["production-msme-panel"],
                    "method_refs": ["causal.difference_in_differences"],
                    "norm_refs": ["norm.ua.credit_eligibility"],
                }
            ]
        },
        decision_artifact_contract={"statements": []},
    )

    issue_codes = {issue["code"] for issue in ledger["issues"]}
    assert ledger["status"] == "fail"
    assert ledger["runtime_report_status"] == "fail"
    assert {
        "semantic_major_claim_scenario_requirement_refs_missing",
        "semantic_major_claim_canonical_concept_refs_missing",
        "semantic_major_claim_column_refs_missing",
        "semantic_major_claim_argument_refs_missing",
        "semantic_major_claim_warrant_refs_missing",
        "semantic_major_claim_rebuttal_refs_missing",
        "semantic_major_claim_counter_evidence_refs_missing",
        "semantic_major_claim_limitation_refs_missing",
    } <= issue_codes


def test_dataset_exists_but_not_covering_claim_blocks_serious_scorecard() -> None:
    ledger = _complete_ledger()
    fabric_binding = deepcopy(ledger["fabric"][0])  # type: ignore[index]
    assert isinstance(fabric_binding, dict)
    fabric_binding["data_coverage"] = [
        {"source_ref": "production-msme-panel", "claim_ids": ["other_claim"], "status": "covers"}
    ]
    ledger["fabric"] = [fabric_binding]

    scorecard = scorecard_for(
        job_payload=complete_job_payload(),
        quality_evidence=_evidence_with_ledger(ledger),
    )

    assert scorecard["quality_status"] == "fail"
    assert "semantic_data_claim_uncovered" in blocking_codes(scorecard)


def test_data_present_but_irrelevant_has_specific_wave13_failure_code() -> None:
    ledger = _complete_ledger()
    fabric_binding = deepcopy(ledger["fabric"][0])  # type: ignore[index]
    assert isinstance(fabric_binding, dict)
    fabric_binding["data_coverage"] = [
        {
            "source_ref": "production-msme-panel",
            "claim_ids": ["rec_1"],
            "status": "irrelevant",
        }
    ]
    fabric_binding["column_bindings"] = []
    ledger["fabric"] = [fabric_binding]

    evaluation = evaluate_semantic_binding_ledger(ledger)

    assert evaluation.status == "fail"
    assert "semantic_data_present_but_irrelevant" in {
        issue.code for issue in evaluation.issues
    }


def test_manifest_role_source_selection_has_specific_wave13_failure_code() -> None:
    ledger = _complete_ledger()
    fabric_binding = deepcopy(ledger["fabric"][0])  # type: ignore[index]
    assert isinstance(fabric_binding, dict)
    fabric_binding["candidate_dataset_source_refs"] = [
        "source_manifest",
        "production-msme-panel",
    ]
    fabric_binding["selected_dataset_source_refs"] = ["source_manifest"]
    fabric_binding["rejected_dataset_source_refs"] = ["production-msme-panel"]
    fabric_binding["column_bindings"] = [
        {
            "claim_id": "rec_1",
            "source_ref": "source_manifest",
            "column_refs": ["manifest_role"],
        }
    ]
    fabric_binding["data_coverage"] = [
        {"source_ref": "source_manifest", "claim_ids": ["rec_1"], "status": "covers"}
    ]
    ledger["fabric"] = [fabric_binding]
    for phase in ("scientist", "final_compiler"):
        binding = deepcopy(ledger[phase][0])  # type: ignore[index]
        assert isinstance(binding, dict)
        binding["required_data_refs"] = ["source_manifest"]
        ledger[phase] = [binding]  # type: ignore[index]

    evaluation = evaluate_semantic_binding_ledger(ledger)

    assert evaluation.status == "fail"
    assert "semantic_manifest_role_source_selection_false_pass" in {
        issue.code for issue in evaluation.issues
    }


def test_missing_field_lineage_blocks_claim_bindable_fabric_evidence() -> None:
    ledger = _complete_ledger()
    fabric_binding = deepcopy(ledger["fabric"][0])  # type: ignore[index]
    assert isinstance(fabric_binding, dict)
    fabric_binding["source_facets"] = []
    fabric_binding["derived_features"] = []
    fabric_binding["data_forge_snapshot_refs"] = []
    ledger["fabric"] = [fabric_binding]

    evaluation = evaluate_semantic_binding_ledger(ledger)

    assert evaluation.status == "fail"
    assert {
        "semantic_fabric_data_forge_snapshot_ref_missing",
        "semantic_fabric_source_facet_missing",
        "semantic_fabric_derived_feature_binding_missing",
    } <= {issue.code for issue in evaluation.issues}


def test_derived_feature_without_source_facet_or_claim_support_blocks() -> None:
    ledger = _complete_ledger()
    fabric_binding = deepcopy(ledger["fabric"][0])  # type: ignore[index]
    assert isinstance(fabric_binding, dict)
    fabric_binding["derived_features"] = [
        {
            "feature_ref": "feature:msme_survival_rate",
            "source_ref": "production-msme-panel",
            "source_facet_refs": [],
            "claim_ids": ["rec_1"],
            "claim_support_feature_refs": [],
        }
    ]
    ledger["fabric"] = [fabric_binding]

    evaluation = evaluate_semantic_binding_ledger(ledger)

    assert evaluation.status == "fail"
    assert {
        "semantic_derived_feature_source_facet_ref_missing",
        "semantic_derived_feature_claim_support_ref_missing",
    } <= {issue.code for issue in evaluation.issues}


def test_multiple_candidate_datasets_require_selection_or_typed_ambiguity_blocker() -> None:
    ledger = _complete_ledger()
    fabric_binding = deepcopy(ledger["fabric"][0])  # type: ignore[index]
    assert isinstance(fabric_binding, dict)
    fabric_binding["candidate_dataset_source_refs"] = [
        "production-msme-panel",
        "tax-msme-panel",
    ]
    fabric_binding["selected_dataset_source_refs"] = []
    fabric_binding["rejected_dataset_source_refs"] = []
    fabric_binding["ambiguity_blocker_refs"] = []
    ledger["fabric"] = [fabric_binding]

    scorecard = scorecard_for(
        job_payload=complete_job_payload(),
        quality_evidence=_evidence_with_ledger(ledger),
    )

    assert scorecard["quality_status"] == "fail"
    assert "semantic_dataset_selection_ambiguous" in blocking_codes(scorecard)


def test_producers_must_return_spine_candidate_bindings_or_blockers() -> None:
    ledger = _complete_ledger()
    lex_binding = deepcopy(ledger["lex"][0])  # type: ignore[index]
    assert isinstance(lex_binding, dict)
    lex_binding["candidate_spine_binding_refs"] = []
    lex_binding["spine_blocker_refs"] = []
    lex_binding["local_labels"] = ["MSME credit support"]
    ledger["lex"] = [lex_binding]

    evaluation = evaluate_semantic_binding_ledger(ledger)

    assert evaluation.status == "fail"
    assert "semantic_spine_candidate_binding_or_blocker_missing" in {
        issue.code for issue in evaluation.issues
    }


def test_scorecard_blocks_spine_dimension_mismatches_with_operator_diagnostics() -> None:
    ledger = _complete_ledger()
    spine_context = deepcopy(ledger["spine_context"])
    assert isinstance(spine_context, dict)
    spine_context.update(
        {
            "unit_refs": ["percent"],
            "period_refs": ["2024-2026"],
            "geography_refs": ["UA"],
        }
    )
    ledger["spine_context"] = spine_context
    fabric_binding = deepcopy(ledger["fabric"][0])  # type: ignore[index]
    assert isinstance(fabric_binding, dict)
    fabric_binding.update(
        {
            "canonical_concept_refs": ["concept.credit_volume"],
            "jurisdiction_refs": ["PL"],
            "unit_refs": ["uah"],
            "period_refs": ["2020-2021"],
            "geography_refs": ["EU"],
            "local_labels": ["local-only survival concept"],
        }
    )
    ledger["fabric"] = [fabric_binding]

    scorecard = scorecard_for(
        job_payload=complete_job_payload(),
        quality_evidence=_evidence_with_ledger(ledger),
    )

    failures = {
        str(failure["code"]): failure
        for failure in scorecard["blocking_quality_failures"]
        if isinstance(failure, dict)
    }
    expected_codes = {
        "semantic_producer_concept_mismatch",
        "semantic_producer_jurisdiction_mismatch",
        "semantic_producer_unit_mismatch",
        "semantic_producer_period_mismatch",
        "semantic_producer_geography_mismatch",
        "semantic_local_concept_leakage",
    }
    assert scorecard["quality_status"] == "fail"
    assert expected_codes <= set(failures)
    for code in expected_codes:
        failure = failures[code]
        assert failure["missing_input"]
        assert failure["conflicting_producer"] == "fabric"
        assert failure["affected_claim"] == "rec_1"
        assert failure["next_command"].startswith("uv run ")


def test_final_claims_reject_evidence_with_mismatched_spine_ref() -> None:
    ledger = _complete_ledger()
    fabric_binding = deepcopy(ledger["fabric"][0])  # type: ignore[index]
    assert isinstance(fabric_binding, dict)
    fabric_binding["consumed_concept_spine_ref"] = sha("9")
    ledger["fabric"] = [fabric_binding]

    scorecard = scorecard_for(
        job_payload=complete_job_payload(),
        quality_evidence=_evidence_with_ledger(ledger),
    )

    assert scorecard["quality_status"] == "fail"
    assert "semantic_final_claim_spine_ref_mismatch" in blocking_codes(scorecard)


def test_domain_specific_intent_cannot_collapse_to_generic_evidence() -> None:
    ledger = _complete_ledger()
    intent = deepcopy(ledger["intent"])
    assert isinstance(intent, dict)
    intent.update(
        {
            "legal_domain": "wartime_msme_support",
            "data_source_family": "production_msme_panel",
            "dataset": "generic_dataset",
            "outcome": "msme_survival_rate",
            "method_family": "causal_effect_estimation",
        }
    )
    ledger["intent"] = intent
    fabric_binding = deepcopy(ledger["fabric"][0])  # type: ignore[index]
    foundry_binding = deepcopy(ledger["foundry"][0])  # type: ignore[index]
    lex_binding = deepcopy(ledger["lex"][0])  # type: ignore[index]
    assert isinstance(fabric_binding, dict)
    assert isinstance(foundry_binding, dict)
    assert isinstance(lex_binding, dict)
    fabric_binding["metric_bindings"] = [
        {"metric_id": "generic_metric", "claim_ids": ["rec_1"], "source_refs": ["generic"]}
    ]
    fabric_binding["selected_dataset_source_refs"] = ["generic_dataset"]
    foundry_binding["selected_method_refs"] = ["generic_descriptive_summary"]
    lex_binding["selected_norm_refs"] = []
    lex_binding["no_norm_blocker_refs"] = ["blocker:no-law-generic"]
    ledger["fabric"] = [fabric_binding]
    ledger["foundry"] = [foundry_binding]
    ledger["lex"] = [lex_binding]

    scorecard = scorecard_for(
        job_payload=complete_job_payload(),
        quality_evidence=_evidence_with_ledger(ledger),
    )

    assert scorecard["quality_status"] == "fail"
    assert "semantic_intent_collapsed_to_generic_evidence" in blocking_codes(scorecard)


def test_serious_claims_require_semantic_binding_even_without_production_candidate() -> None:
    evidence = complete_quality_evidence()
    evidence.pop("semantic_binding_ledger", None)
    fabric = evidence["fabric_retrieval_trace"]
    assert isinstance(fabric, dict)
    fabric["candidate_sources"] = []
    fabric["selected_source_ids"] = []

    scorecard = scorecard_for(
        job_payload=complete_job_payload(),
        quality_evidence=evidence,
    )

    assert scorecard["quality_status"] == "fail"
    assert "hds_semantic_binding_missing" in blocking_codes(scorecard)


def test_evidence_envelopes_must_point_at_semantic_binding_ledger_ref() -> None:
    evidence = _evidence_with_ledger(_complete_ledger())
    envelope = evidence["policy_grounding_matrix"]["authority_envelope"]  # type: ignore[index]
    assert isinstance(envelope, dict)
    envelope["semantic_binding_ref"] = sha("c")

    scorecard = scorecard_for(
        job_payload=complete_job_payload(),
        quality_evidence=evidence,
    )

    assert scorecard["quality_status"] == "fail"
    assert "semantic_binding_ref_mismatch" in blocking_codes(scorecard)


def test_rejected_candidates_distinguish_no_relevant_from_retrieval_or_binding_failure() -> None:
    no_relevant = _complete_ledger()
    no_relevant_fabric = deepcopy(no_relevant["fabric"][0])  # type: ignore[index]
    assert isinstance(no_relevant_fabric, dict)
    no_relevant_fabric["selected_dataset_source_refs"] = []
    no_relevant_fabric["rejected_dataset_source_refs"] = [
        "fixture-source",
        "production-msme-panel",
        "tax-msme-panel",
    ]
    no_relevant_fabric["data_gap_blocker_refs"] = ["blocker:no_relevant_data"]
    no_relevant["fabric"] = [no_relevant_fabric]

    no_relevant_eval = evaluate_semantic_binding_ledger(no_relevant)

    assert no_relevant_eval.status == "blocked"
    assert no_relevant_eval.reason_family == "no_relevant_evidence"
    assert [issue.code for issue in no_relevant_eval.issues] == []
    assert set(no_relevant_eval.rejected_candidate_refs) == {
        "descriptive.summary",
        "fixture-source",
        "literature:procurement-fixture",
        "norm.ua.procurement_fixture",
        "production-msme-panel",
        "tax-msme-panel",
    }
    no_relevant_scorecard = scorecard_for(
        job_payload=complete_job_payload(),
        quality_evidence=_evidence_with_ledger(no_relevant),
    )
    assert "semantic_no_relevant_evidence_blocker" in blocking_codes(no_relevant_scorecard)

    retrieval_failure = _complete_ledger()
    retrieval_lex = deepcopy(retrieval_failure["lex"][0])  # type: ignore[index]
    assert isinstance(retrieval_lex, dict)
    retrieval_lex["selected_norm_refs"] = []
    retrieval_lex["rejected_norm_refs"] = []
    retrieval_lex["retrieval_error_blocker_refs"] = ["blocker:lex_retrieval_timeout"]
    retrieval_failure["lex"] = [retrieval_lex]

    retrieval_eval = evaluate_semantic_binding_ledger(retrieval_failure)

    assert retrieval_eval.status == "blocked"
    assert retrieval_eval.reason_family == "retrieval_failure"
    assert [issue.code for issue in retrieval_eval.issues] == []
    retrieval_scorecard = scorecard_for(
        job_payload=complete_job_payload(),
        quality_evidence=_evidence_with_ledger(retrieval_failure),
    )
    assert "semantic_retrieval_failure_blocker" in blocking_codes(retrieval_scorecard)

    binding_failure = _complete_ledger()
    binding_fabric = deepcopy(binding_failure["fabric"][0])  # type: ignore[index]
    assert isinstance(binding_fabric, dict)
    binding_fabric["selected_dataset_source_refs"] = []
    binding_fabric["rejected_dataset_source_refs"] = []
    binding_fabric["data_gap_blocker_refs"] = []
    binding_failure["fabric"] = [binding_fabric]

    binding_eval = evaluate_semantic_binding_ledger(binding_failure)

    assert binding_eval.status == "fail"
    assert binding_eval.reason_family == "binding_failure"
    assert [issue.code for issue in binding_eval.issues] == [
        "semantic_dataset_selection_ambiguous",
        "semantic_selected_dataset_missing",
    ]
    binding_scorecard = scorecard_for(
        job_payload=complete_job_payload(),
        quality_evidence=_evidence_with_ledger(binding_failure),
    )
    assert "semantic_dataset_selection_ambiguous" in blocking_codes(binding_scorecard)
