from __future__ import annotations

import pytest

from polisyos.foundry.methods.selection.requirements import (
    select_method_candidates_for_requirements,
)

# ruff: noqa: S101
from polisyos.ir.observation import IdentificationMode
from polisyos.method_requirement import (
    MethodValidityRequirementSpec,
    compile_method_validity_requirements,
)
from polisyos.scientist.policy_design.claim_decomposition import (
    ClaimDecompositionCompiler,
    ClaimDecompositionFacet,
    ClaimDecompositionInput,
    ClaimDecompositionObligation,
)


def _requirement() -> MethodValidityRequirementSpec:
    return MethodValidityRequirementSpec(
        requirement_id="method-req-claim-effect",
        run_id="run_w7c",
        claim_id="claim_effect",
        identification_class="point",
        method_expectations=["causal_effect_estimation"],
        required_method_families=["causal_effect_estimation"],
        transportability_requirement="target_population_limits",
        uncertainty_class="interval",
        assumption_validation_needs=[
            {"assumption_id": "parallel_trends"},
            {"assumption_id": "overlap_or_support"},
        ],
        facet_refs=["facet_outcome"],
        obligation_refs=["obl_method"],
    )


def test_requirement_selection_rejects_generic_and_offline_only_candidates() -> None:
    report = select_method_candidates_for_requirements(
        candidate_methods=[
            {
                "method_id": "foundry.execute",
                "method_family": "simulation",
                "method_expectations": ["causal_effect_estimation"],
                "result_refs": {"simulation_result_ref": "sha256:" + "8" * 64},
            },
            {
                "method_id": "causal.offline.validity_report",
                "method_family": "causal_effect_estimation",
                "method_expectations": ["causal_effect_estimation"],
                "truthfulness_status": "catalog_only",
                "result_refs": {"offline_report_ref": "sha256:" + "7" * 64},
            },
            {
                "method_id": "causal.did.runtime",
                "method_family": "causal_effect_estimation",
                "method_expectations": ["causal_effect_estimation"],
                "truthfulness_status": "runtime_consistent",
                "runtime_assumption_gates": [
                    {
                        "gate_ref": "gate://parallel-trends",
                        "assumption": "parallel_trends",
                        "status": "pass",
                    },
                    {
                        "gate_ref": "gate://overlap",
                        "assumption": "overlap_or_support",
                        "status": "pass",
                    },
                ],
                "uncertainty_refs": {"uncertainty_envelope_ref": "sha256:" + "6" * 64},
                "limitation_refs": {"method_limitation_ref": "sha256:" + "5" * 64},
                "method_result_refs": {"method_result_ref": "sha256:" + "4" * 64},
            },
        ],
        method_requirements=[_requirement()],
    )

    assert report["status"] == "pass"
    assert [method["method_id"] for method in report["selected_methods"]] == ["causal.did.runtime"]
    assert report["selected_methods"][0]["method_requirement_refs"] == ["method-req-claim-effect"]
    assert {rejected["reason_code"] for rejected in report["rejected_methods"]} == {
        "generic_method_not_admissible",
        "offline_only_validity_not_admissible",
    }


def test_linked_bounds_mode_is_enforced_by_real_method_requirement_selector() -> None:
    ledger = ClaimDecompositionCompiler().compile(
        ClaimDecompositionInput(
            run_id="run_w6d_selector_bounds",
            intent="Assess a causal effect with a bounds-only identification mode.",
            facets=[
                ClaimDecompositionFacet(
                    facet_id="facet_effect",
                    facet_type="outcome_channel",
                    value="causal effect",
                ),
                ClaimDecompositionFacet(
                    facet_id="facet_method",
                    facet_type="method_need",
                    value=IdentificationMode.BOUNDS_ONLY.value,
                ),
            ],
            obligations=[
                ClaimDecompositionObligation(
                    obligation_id="obligation_effect",
                    family="causal_effect",
                    description="Assess the causal effect.",
                    facet_refs=["facet_effect", "facet_method"],
                )
            ],
        )
    )
    artifact = compile_method_validity_requirements(
        run_id=ledger.run_id,
        claims=ledger.claims,
    )
    requirements = artifact.requirements
    assert len(requirements) == 2
    assert all(row.identification_class.value == "bounds" for row in requirements)
    assert all(
        row.metadata["explicit_identification_mode_facets"][0]["facet_ref"] == "facet_method"
        for row in requirements
    )
    candidate = {
        "method_id": "causal.did.runtime",
        "method_family": "causal_effect_estimation",
        "method_expectations": ["causal_effect_estimation", "bounds_only"],
        "truthfulness_status": "runtime_consistent",
        "runtime_assumption_gates": [
            {"assumption": "identification_assumptions", "status": "pass"},
            {"assumption": "overlap_or_support", "status": "pass"},
            {"assumption": "missingness_process", "status": "pass"},
        ],
        "uncertainty_refs": {"uncertainty_envelope_ref": "sha256:" + "6" * 64},
        "limitation_refs": {"method_limitation_ref": "sha256:" + "5" * 64},
        "method_result_refs": {"method_result_ref": "sha256:" + "4" * 64},
    }

    report = select_method_candidates_for_requirements(
        candidate_methods=[candidate],
        method_requirements=requirements,
    )

    assert report["status"] == "pass"
    assert set(report["method_requirement_statuses"]) == {
        row.requirement_id for row in requirements
    }
    assert set(report["method_requirement_statuses"].values()) == {"satisfied"}
    assert all(row["method_id"] == "causal.did.runtime" for row in report["selected_methods"])
    assert {
        requirement_ref
        for row in report["selected_methods"]
        for requirement_ref in row["method_requirement_refs"]
    } == {row.requirement_id for row in requirements}


def test_method_selector_refuses_absent_or_wrong_explicit_identification_mode() -> None:
    ledger = ClaimDecompositionCompiler().compile(
        ClaimDecompositionInput(
            run_id="run_w6d_selector_mode_control",
            intent="Assess a causal effect with bounds-only identification.",
            facets=[
                ClaimDecompositionFacet(
                    facet_id="facet_effect",
                    facet_type="outcome_channel",
                    value="causal effect",
                ),
                ClaimDecompositionFacet(
                    facet_id="facet_method",
                    facet_type="method_need",
                    value=IdentificationMode.BOUNDS_ONLY.value,
                ),
            ],
            obligations=[
                ClaimDecompositionObligation(
                    obligation_id="obligation_effect",
                    family="causal_effect",
                    description="Assess the causal effect.",
                    facet_refs=["facet_effect", "facet_method"],
                )
            ],
        )
    )
    requirement_artifact = compile_method_validity_requirements(
        run_id=ledger.run_id,
        claims=ledger.claims,
    )
    requirements = requirement_artifact.requirements
    assert len(requirements) == 2
    candidate = {
        "method_id": "causal.did.runtime",
        "method_family": "causal_effect_estimation",
        "method_expectations": ["causal_effect_estimation"],
        "tags": ["bounds_only"],
        "truthfulness_status": "runtime_consistent",
        "runtime_assumption_gates": [
            {"assumption": "identification_assumptions", "status": "pass"},
            {"assumption": "overlap_or_support", "status": "pass"},
            {"assumption": "missingness_process", "status": "pass"},
        ],
        "uncertainty_refs": {"uncertainty_envelope_ref": "sha256:" + "6" * 64},
        "limitation_refs": {"method_limitation_ref": "sha256:" + "5" * 64},
        "method_result_refs": {"method_result_ref": "sha256:" + "4" * 64},
    }

    absent = select_method_candidates_for_requirements(
        candidate_methods=[candidate],
        method_requirements=requirements,
    )
    wrong_mode = select_method_candidates_for_requirements(
        candidate_methods=[
            {
                **candidate,
                "method_expectations": ["causal_effect_estimation", "point_identified"],
            }
        ],
        method_requirements=requirements,
    )

    for report in (absent, wrong_mode):
        assert report["status"] == "fail"
        assert report["selected_methods"] == []
        assert set(report["method_requirement_statuses"]) == {
            row.requirement_id for row in requirements
        }
        assert set(report["method_requirement_statuses"].values()) == {"missing"}
        assert all(
            row["reason_code"] == "identification_mode_unsupported"
            for row in report["rejected_methods"]
        )


@pytest.mark.parametrize("mode", tuple(IdentificationMode))
def test_selector_requires_exact_support_for_each_declared_identification_mode(
    mode: IdentificationMode,
) -> None:
    ledger = ClaimDecompositionCompiler().compile(
        ClaimDecompositionInput(
            run_id=f"run_w6d_selector_explicit_{mode.value}",
            intent="Assess a causal policy effect under the declared mode.",
            facets=[
                ClaimDecompositionFacet(
                    facet_id="facet_effect",
                    facet_type="outcome_channel",
                    value="causal effect",
                ),
                ClaimDecompositionFacet(
                    facet_id="facet_method",
                    facet_type="method_need",
                    value=mode.value,
                ),
            ],
            obligations=[
                ClaimDecompositionObligation(
                    obligation_id="obligation_effect",
                    family="causal_effect",
                    description="Assess the policy effect.",
                    facet_refs=["facet_effect", "facet_method"],
                )
            ],
        )
    )
    requirements = compile_method_validity_requirements(
        run_id=ledger.run_id,
        claims=ledger.claims,
    ).requirements
    assert requirements
    assert all(
        requirement.metadata["explicit_identification_mode_facets"][0]["identification_mode"]
        == mode.value
        for requirement in requirements
    )

    report = select_method_candidates_for_requirements(
        candidate_methods=[
            {
                "method_id": "causal.did.runtime",
                "method_family": "causal_effect_estimation",
                "method_expectations": ["causal_effect_estimation"],
            }
        ],
        method_requirements=requirements,
    )

    assert report["status"] == "fail"
    assert report["selected_methods"] == []
    assert report["rejected_methods"]
    assert all(
        row["reason_code"] == "identification_mode_unsupported"
        and row["missing_identification_modes"] == [mode.value]
        for row in report["rejected_methods"]
    )


def test_method_selector_keeps_component_modes_on_every_causal_claim() -> None:
    ledger = ClaimDecompositionCompiler().compile(
        ClaimDecompositionInput(
            run_id="run_w6d_selector_component_modes",
            intent="Assess employment and inflation effects in separate intervention components.",
            facets=[
                ClaimDecompositionFacet(
                    facet_id="facet_employment",
                    facet_type="outcome_channel",
                    value="employment causal effect",
                    metadata={"component_id": "employment"},
                ),
                ClaimDecompositionFacet(
                    facet_id="facet_employment_mode",
                    facet_type="method_need",
                    value=IdentificationMode.POINT_IDENTIFIED.value,
                    metadata={"component_id": "employment"},
                ),
                ClaimDecompositionFacet(
                    facet_id="facet_inflation",
                    facet_type="outcome_channel",
                    value="inflation causal effect",
                    metadata={"component_id": "inflation"},
                ),
                ClaimDecompositionFacet(
                    facet_id="facet_inflation_mode",
                    facet_type="method_need",
                    value=IdentificationMode.SEQUENTIAL.value,
                    metadata={"component_id": "inflation"},
                ),
            ],
            obligations=[
                ClaimDecompositionObligation(
                    obligation_id="obligation_employment",
                    family="causal_effect",
                    description="Assess employment effects.",
                    facet_refs=["facet_employment", "facet_employment_mode"],
                ),
                ClaimDecompositionObligation(
                    obligation_id="obligation_inflation",
                    family="causal_effect",
                    description="Assess inflation effects.",
                    facet_refs=["facet_inflation", "facet_inflation_mode"],
                ),
            ],
        )
    )
    requirements = compile_method_validity_requirements(
        run_id=ledger.run_id,
        claims=ledger.claims,
    ).requirements
    assert len(requirements) == 4
    candidates = [
        {
            "method_id": "causal.point.runtime",
            "method_family": "causal_effect_estimation",
            "method_expectations": [
                "causal_effect_estimation",
                IdentificationMode.POINT_IDENTIFIED.value,
            ],
            "truthfulness_status": "runtime_consistent",
            "runtime_assumption_gates": [
                {"assumption": "identification_assumptions", "status": "pass"},
                {"assumption": "overlap_or_support", "status": "pass"},
                {"assumption": "missingness_process", "status": "pass"},
            ],
            "uncertainty_refs": {"uncertainty_envelope_ref": "sha256:" + "6" * 64},
            "limitation_refs": {"method_limitation_ref": "sha256:" + "5" * 64},
            "method_result_refs": {"method_result_ref": "sha256:" + "4" * 64},
        },
        {
            "method_id": "causal.sequential.runtime",
            "method_family": "causal_effect_estimation",
            "method_expectations": [
                "causal_effect_estimation",
                IdentificationMode.SEQUENTIAL.value,
            ],
            "truthfulness_status": "runtime_consistent",
            "runtime_assumption_gates": [
                {"assumption": "identification_assumptions", "status": "pass"},
                {"assumption": "overlap_or_support", "status": "pass"},
                {"assumption": "missingness_process", "status": "pass"},
            ],
            "uncertainty_refs": {"uncertainty_envelope_ref": "sha256:" + "7" * 64},
            "limitation_refs": {"method_limitation_ref": "sha256:" + "8" * 64},
            "method_result_refs": {"method_result_ref": "sha256:" + "9" * 64},
        },
    ]

    report = select_method_candidates_for_requirements(
        candidate_methods=candidates,
        method_requirements=requirements,
    )

    assert report["status"] == "pass"
    assert set(report["method_requirement_statuses"]) == {
        row.requirement_id for row in requirements
    }
    assert set(report["method_requirement_statuses"].values()) == {"satisfied"}
    selected_by_requirement = {
        requirement_ref: row["method_id"]
        for row in report["selected_methods"]
        for requirement_ref in row["method_requirement_refs"]
    }
    assert set(selected_by_requirement) == {row.requirement_id for row in requirements}
    for requirement in requirements:
        expected = (
            "causal.point.runtime"
            if "facet_employment_mode" in requirement.facet_refs
            else "causal.sequential.runtime"
        )
        assert selected_by_requirement[requirement.requirement_id] == expected


def test_requirement_selection_rejects_method_without_runtime_assumption_gate() -> None:
    report = select_method_candidates_for_requirements(
        candidate_methods=[
            {
                "method_id": "causal.did.runtime",
                "method_family": "causal_effect_estimation",
                "method_expectations": ["causal_effect_estimation"],
                "truthfulness_status": "runtime_consistent",
                "runtime_assumption_gates": [
                    {
                        "gate_ref": "gate://parallel-trends",
                        "assumption": "parallel_trends",
                        "status": "pass",
                    }
                ],
                "uncertainty_refs": {"uncertainty_envelope_ref": "sha256:" + "6" * 64},
                "limitation_refs": {"method_limitation_ref": "sha256:" + "5" * 64},
                "method_result_refs": {"method_result_ref": "sha256:" + "4" * 64},
            }
        ],
        method_requirements=[_requirement()],
    )

    assert report["status"] == "fail"
    assert report["selected_methods"] == []
    assert report["rejected_methods"][0]["reason_code"] == ("runtime_assumption_validation_missing")
    assert report["issues"][0]["code"] == "method_requirement_no_selected_method"


def test_foundry_selects_survival_contract_from_capability_graph_manifest() -> None:
    requirement = MethodValidityRequirementSpec(
        requirement_id="method-req-firm-survival",
        run_id="run_w7c",
        claim_id="claim_firm_survival",
        identification_class="point",
        method_expectations=["survival_data"],
        required_method_families=["survival_data"],
        transportability_requirement="target_population_limits",
        uncertainty_class="interval",
        assumption_validation_needs=[
            {"assumption_id": "right_censoring"},
            {"assumption_id": "support_overlap"},
        ],
        concept_spine_refs=["concept:firm_survival"],
        obligation_refs=["obl_method"],
    )

    report = select_method_candidates_for_requirements(
        candidate_methods=[],
        method_requirements=[requirement],
        observation_to_contract_manifest={
            "contracts": [
                {
                    "construct_ref": "construct:firm_survival",
                    "contract_target": "foundry.ml.survival_data.v1",
                    "required_assumption_gates": ["right_censoring", "support_overlap"],
                },
                {
                    "construct_ref": "construct:regional_displacement_pressure",
                    "contract_target": "foundry.ml.panel_observational_data.v1",
                },
            ]
        },
        capability_bindings=[
            {
                "requirement_id": "method-req-firm-survival",
                "status": "selected_exact",
                "selected_capability_ref": "capability:firm_survival_method_contract",
                "construct_ref": "construct:firm_survival",
                "capability_index_ref": "capability-index:phase5",
                "construct_registry_ref": "construct-registry:v1",
                "authority_composition_rule_ref": "capability-authority-v1.0",
                "method_contract_targets": ["foundry.ml.survival_data.v1"],
                "source_assets": [
                    {
                        "ref": "observation_to_contract_manifest.json",
                        "fields": ["duration", "event", "risk_signal"],
                    }
                ],
            }
        ],
    )

    selected = report["selected_methods"][0]

    assert report["status"] == "pass"
    assert selected["method_id"] == "foundry.ml.survival_data.v1"
    assert selected["method_requirement_refs"] == ["method-req-firm-survival"]
    assert selected["capability_ref"] == "capability:firm_survival_method_contract"
    assert selected["construct_ref"] == "construct:firm_survival"
    assert selected["capability_index_ref"] == "capability-index:phase5"
    assert selected["construct_registry_ref"] == "construct-registry:v1"
    assert selected["authority_composition_rule_ref"] == "capability-authority-v1.0"
    assert selected["observation_contract_manifest_ref"] == (
        "observation_to_contract_manifest.json"
    )


def test_foundry_selects_panel_microsim_and_dynamic_treatment_contracts() -> None:
    requirements = [
        MethodValidityRequirementSpec(
            requirement_id="method-req-displacement-panel",
            run_id="run_w7c_phase5",
            claim_id="claim_displacement_panel",
            identification_class="point",
            method_expectations=["panel_observational"],
            required_method_families=["panel_observational"],
            transportability_requirement="target_population_limits",
            uncertainty_class="interval",
            assumption_validation_needs=[
                {"assumption_id": "parallel_trends"},
                {"assumption_id": "support_overlap"},
            ],
            concept_spine_refs=["concept:regional_displacement_pressure"],
            obligation_refs=["obl_method"],
        ),
        MethodValidityRequirementSpec(
            requirement_id="method-req-benefit-microsim",
            run_id="run_w7c_phase5",
            claim_id="claim_benefit_microsim",
            identification_class="point",
            method_expectations=["microsimulation"],
            required_method_families=["microsimulation"],
            transportability_requirement="target_population_limits",
            uncertainty_class="interval",
            assumption_validation_needs=[
                {"assumption_id": "calibration"},
                {"assumption_id": "behavioral_response"},
            ],
            concept_spine_refs=["concept:benefit_incidence"],
            obligation_refs=["obl_method"],
        ),
        MethodValidityRequirementSpec(
            requirement_id="method-req-credit-dynamic-treatment",
            run_id="run_w7c_phase5",
            claim_id="claim_credit_dynamic_treatment",
            identification_class="point",
            method_expectations=["dynamic_treatment"],
            required_method_families=["dynamic_treatment"],
            transportability_requirement="target_population_limits",
            uncertainty_class="interval",
            assumption_validation_needs=[
                {"assumption_id": "sequential_exchangeability"},
                {"assumption_id": "positivity"},
            ],
            concept_spine_refs=["concept:credit_program_enrollment"],
            obligation_refs=["obl_method"],
        ),
    ]

    report = select_method_candidates_for_requirements(
        candidate_methods=[],
        method_requirements=requirements,
        observation_to_contract_manifest={
            "contracts": [
                {
                    "construct_ref": "construct:regional_displacement_pressure",
                    "contract_target": "foundry.ml.panel_observational_data.v1",
                    "required_assumption_gates": [
                        "parallel_trends",
                        "support_overlap",
                    ],
                    "manifest_ref": "observation_to_contract_manifest.json",
                },
                {
                    "construct_ref": "construct:benefit_incidence",
                    "contract_target": "foundry.sim.microsim_population_data.v1",
                    "required_assumption_gates": [
                        "calibration",
                        "behavioral_response",
                    ],
                    "manifest_ref": "observation_to_contract_manifest.json",
                },
                {
                    "construct_ref": "construct:credit_program_enrollment",
                    "contract_target": "foundry.causal.dynamic_treatment_data.v1",
                    "required_assumption_gates": [
                        "sequential_exchangeability",
                        "positivity",
                    ],
                    "manifest_ref": "observation_to_contract_manifest.json",
                },
            ]
        },
        capability_bindings=[
            {
                "requirement_id": "method-req-displacement-panel",
                "status": "selected_exact",
                "selected_capability_ref": "capability:displacement_panel_contract",
                "construct_ref": "construct:regional_displacement_pressure",
                "capability_index_ref": "capability-index:phase5",
                "construct_registry_ref": "construct-registry:v1",
                "authority_composition_rule_ref": "capability-authority-v1.0",
            },
            {
                "requirement_id": "method-req-benefit-microsim",
                "status": "selected_exact",
                "selected_capability_ref": "capability:benefit_microsim_contract",
                "construct_ref": "construct:benefit_incidence",
                "capability_index_ref": "capability-index:phase5",
                "construct_registry_ref": "construct-registry:v1",
                "authority_composition_rule_ref": "capability-authority-v1.0",
            },
            {
                "requirement_id": "method-req-credit-dynamic-treatment",
                "status": "selected_exact",
                "selected_capability_ref": "capability:credit_dynamic_treatment_contract",
                "construct_ref": "construct:credit_program_enrollment",
                "capability_index_ref": "capability-index:phase5",
                "construct_registry_ref": "construct-registry:v1",
                "authority_composition_rule_ref": "capability-authority-v1.0",
            },
        ],
    )

    selected_by_requirement = {
        method["method_requirement_refs"][0]: method for method in report["selected_methods"]
    }

    assert report["status"] == "pass"
    assert report["summary"]["capability_method_candidate_count"] == 3
    assert (
        selected_by_requirement["method-req-displacement-panel"]["method_id"]
        == "foundry.ml.panel_observational_data.v1"
    )
    assert (
        selected_by_requirement["method-req-benefit-microsim"]["method_id"]
        == "foundry.sim.microsim_population_data.v1"
    )
    assert (
        selected_by_requirement["method-req-credit-dynamic-treatment"]["method_id"]
        == "foundry.causal.dynamic_treatment_data.v1"
    )
    assert {method["capability_ref"] for method in report["selected_methods"]} == {
        "capability:displacement_panel_contract",
        "capability:benefit_microsim_contract",
        "capability:credit_dynamic_treatment_contract",
    }
    assert {
        method["observation_contract_manifest_ref"] for method in report["selected_methods"]
    } == {"observation_to_contract_manifest.json"}
