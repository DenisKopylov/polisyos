"""Scoped CPI candidate-only scenario inputs for the served LANE-01 X03 test."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from polisyos.core.artifacts import ArtifactStore
from polisyos.runtime.quality.design_problem import DesignProblem

CPI_OUTCOME_SLOT = "global.consumer_price_index"
CPI_STATE_PATH = "market.avg_price"
CPI_UNIT_ID = "index"
CPI_BASE_YEAR = 2010
CPI_PRE_ACQUISITION_BASELINE = 0.0
CPI_SCENARIO_PROFILE_ID = "e02.lane01.x03.cpi.fp-cpi-totl.level.base-2010-100.candidate-only"
CPI_SCENARIO_SCOPE_SOURCE = (
    "For Ukraine in calendar year 2024, use the annual World Bank FP.CPI.TOTL consumer "
    "price index level with base year 2010=100. This candidate-only fixture exercises "
    "a direct tax_relief_rate set-to on global.tax_rate from a declared 1.0 ratio baseline "
    "to 0.0, with a declared synthetic CPI response; it does not establish authority or a law."
)


def build_x03_cpi_design_problem() -> DesignProblem:
    """Adapt the existing served WDI candidate problem to the CPI level construct."""
    from tests._helpers import acquisition_chain, controlled_candidate_profile

    recording = acquisition_chain.load_served_wdi_generation_recording()
    parent = controlled_candidate_profile._current_compiler_problem(recording)
    base = acquisition_chain.controlled_served_wdi_problem(
        parent,
        raw_request=acquisition_chain.SERVED_WDI_FISCAL_REQUEST,
    )
    payload = base.model_dump(mode="json")
    candidate_only_source = acquisition_chain.SERVED_WDI_CANDIDATE_ONLY_SOURCE
    raw_request = f"{CPI_SCENARIO_SCOPE_SOURCE} {candidate_only_source}"
    payload["schema_version"] = "policyos.runtime.design_problem.v3"
    payload["domain"] = "economic"
    payload["problem_statement"] = CPI_SCENARIO_SCOPE_SOURCE
    payload["nl_provenance"].update(
        {"raw_request": raw_request, "source_surface": "runtime.control.nl_request"}
    )
    payload["jurisdiction_time"].update(
        {
            "region": "UKR",
            "valid_time": "2024",
            "as_of": "2024-12-31",
            "policy_time": "2024",
            "data_time": "2024",
            "time_semantics": {
                "frequency": "Y",
                "start_date": "2024-01-01",
                "step_count": 1,
            },
        }
    )
    payload["objectives"] = [
        {
            "objective_id": "consumer_price_index_level",
            "description": (
                "Assess the annual consumer price index level for Ukraine in 2024, "
                "with 2010=100 units, under the candidate scenario."
            ),
            "metric_id": "consumer_price_index",
            "direction": "minimize",
        }
    ]
    payload["outcome_of_interest"].update(
        {
            "target_variable": CPI_OUTCOME_SLOT,
            "metric_id": "consumer_price_index",
            "estimand": (
                "Candidate-only 2024 annual FP.CPI.TOTL index level; 2010=100; "
                "synthetic NCM response is not an empirical effect."
            ),
            "direction": "minimize",
        }
    )
    payload["candidate_lever_space"] = {
        "allowed_operator_kinds": ["tax_relief_rate"],
        "candidate_levers": [
            {
                "lever_id": "lane01_x03_cpi_tax_relief_rate",
                "operator_kind": "tax_relief_rate",
                "instrument": "Registered candidate tax relief rate",
                "target_slot": "global.tax_rate",
            }
        ],
    }
    payload["evidence_acquisition_needs"] = {
        "needs": [
            {
                "need_id": "ukr_cpi_index_level_2024",
                "question": (
                    "Which source supplies Ukraine's 2024 FP.CPI.TOTL index level "
                    "with 2010=100, distinct from annual CPI percentage growth?"
                ),
                "required_for": "Candidate-only CPI input availability.",
            }
        ]
    }
    payload["runtime_hints"]["n7_scope_profile"] = {
        "profile_id": "scope:lane01-cpi-ukr-2024:v1",
        "jurisdiction": "UKR",
        "population": "national_economy",
        "entity_scope": "country",
        "time_window": {"start": "2024-01-01", "end": "2024-12-31"},
        "time_role": "observation_time",
        "granularity": "annual",
        "required_constructs": ["economic.consumer_price_index"],
    }
    for constraint in payload["constraints"]:
        if constraint.get("constraint_id") == "fiscal_request_scope":
            constraint.update(
                {
                    "description": (
                        "Keep the candidate within Ukraine's 2024 CPI level scope, "
                        "with the World Bank 2010=100 base."
                    ),
                    "source_text": CPI_SCENARIO_SCOPE_SOURCE,
                }
            )
        elif constraint.get("constraint_id") == "no_authority_without_a":
            constraint["source_text"] = candidate_only_source
    return DesignProblem.model_validate(payload)


def build_x03_cpi_candidate_profile(
    *,
    tmp_path: Path,
    store: ArtifactStore,
    problem: DesignProblem,
    source_owner_root: Path | None = None,
    prepared_substrate_registry: Any | None = None,
    invocation_quota_policy: Any | None = None,
    tenant_id: str | None = None,
    cell_id: str | None = None,
) -> tuple[Any, Any]:
    """Build the X03-only WMR/N5 profile with a custom CPI slot binding.

    The initial CPI value is deliberately zero and means "not acquired". The
    real served source action must replace it with the captured 2024 level.
    The only CPI slot mapping is inside this candidate WMR: CPI level →
    ``market.avg_price`` with a declared ``index`` unit. The intervention
    reuses the GDP fixture's direct tax-rate set-to on a ratio-valued slot.
    """
    import numpy as np

    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.data_requirement import DataRequirementScope
    from polisyos.foundry.execute.executor import get_state_path, load_state_snapshot
    from polisyos.ir.kernel.time_semantics import TimeSemantics
    from polisyos.ir.model_layer.model_spec import ModelSpec
    from polisyos.ir.model_layer.types import TimeFrequency
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.quality.candidate_simulation import (
        CandidateSimulationScenarioProfile,
        CandidateSimulationSyntheticModelDeclarationV1,
        candidate_simulation_profile_ref,
    )
    from polisyos.runtime.quality.substrate_registry import (
        current_catalog_serving_source,
        require_catalog_source_registry_binding,
    )
    from polisyos.runtime.quality.world_model_record import world_model_artifact_views
    from tests._helpers import acquisition_served_history, controlled_candidate_profile

    tenant_id = tenant_id or acquisition_served_history.TENANT
    cell_id = cell_id or acquisition_served_history.CELL

    raw_scope_profile = problem.runtime_hints.get("n7_scope_profile")
    if not isinstance(raw_scope_profile, dict):
        raise ValueError("x03_cpi_n7_scope_profile_missing")
    raw_time_window = raw_scope_profile.get("time_window")
    if not isinstance(raw_time_window, dict):
        raise ValueError("x03_cpi_n7_time_window_missing")
    declared_scope = DataRequirementScope.model_validate(
        {
            "population": raw_scope_profile.get("population"),
            "geography": raw_scope_profile.get("entity_scope"),
            "time": f"{raw_time_window.get('start')}/{raw_time_window.get('end')}",
            "time_role": raw_scope_profile.get("time_role"),
            "jurisdiction": raw_scope_profile.get("jurisdiction"),
        }
    )
    if (
        declared_scope.population != "national_economy"
        or declared_scope.geography != "country"
        or declared_scope.jurisdiction != problem.jurisdiction_time.region
        or declared_scope.jurisdiction != "UKR"
        or declared_scope.time != "2024-01-01/2024-12-31"
        or declared_scope.time_role != "observation_time"
        or raw_scope_profile.get("granularity") != "annual"
    ):
        raise ValueError("x03_cpi_n7_scope_profile_mismatch")
    candidate_resolution = "country_year"

    if (
        problem.outcome_of_interest.target_variable != CPI_OUTCOME_SLOT
        or problem.jurisdiction_time.region != "UKR"
        or problem.jurisdiction_time.data_time != "2024"
        or f"{CPI_BASE_YEAR}=100" not in problem.problem_statement
    ):
        raise ValueError("x03_cpi_problem_scope_mismatch")
    if prepared_substrate_registry is None or source_owner_root is None:
        raise ValueError("x03_cpi_selected_catalog_source_missing")
    selected_catalog_source = current_catalog_serving_source()
    source_root = Path(source_owner_root).resolve(strict=True)
    if (
        selected_catalog_source is None
        or selected_catalog_source.repo_root != source_root
        or selected_catalog_source.source_owner_root != source_root
    ):
        raise ValueError("x03_cpi_selected_catalog_source_owner_mismatch")
    require_catalog_source_registry_binding(
        source_root,
        prepared_substrate_registry,
        selected_catalog_source,
    )
    prepared_entry_hashes = {
        entry.entry_content_hash for entry in prepared_substrate_registry.entries
    }

    profile, declaration, _world_build = (
        controlled_candidate_profile._build_configured_procurement_profile(
            recorded_problem=problem,
            artifact_store=store,
            tenant_id=tenant_id,
            cell_id=cell_id,
            tmp_path=tmp_path,
            source_root=source_root / "controlled-candidate-source",
            repo_root=controlled_candidate_profile.REPO_ROOT,
            basis_repo_root=controlled_candidate_profile.REPO_ROOT,
            l6_source_owner_root=source_owner_root,
            invocation_quota_policy=invocation_quota_policy,
            prepared_substrate_registry=prepared_substrate_registry,
            use_prepared_substrate_registry_as_is=True,
            candidate_model_time_semantics=TimeSemantics(
                frequency=TimeFrequency.YEAR,
                start_date="2024-01-01",
                step_count=1,
            ),
            candidate_population_scope=declared_scope.population,
            candidate_resolution=candidate_resolution,
            rule_operator_kind="tax_relief_rate",
            rule_parameter_id="rate",
            rule_target_world_slot="global.tax_rate",
            rule_unit_id="ratio",
            rule_minimum=0,
            rule_maximum=0,
            target_baseline=1.0,
            outcome_baseline=CPI_PRE_ACQUISITION_BASELINE,
            candidate_outcome_state_path=CPI_STATE_PATH,
            candidate_outcome_unit_id=CPI_UNIT_ID,
            candidate_outcome_noise_stddev=0.0,
        )
    )
    if profile.context_inputs.substrate_registry != prepared_substrate_registry:
        raise ValueError("x03_cpi_prepared_catalog_registry_not_reused")
    if any(
        reference.startswith("lane0://")
        for reference in profile.context_inputs.substrate_registry.source_catalog_refs
    ):
        raise ValueError("x03_cpi_context_registry_has_unbound_lane0_source")

    profile_payload = profile.model_dump(mode="json", exclude={"content_hash"})
    profile_payload["profile_id"] = CPI_SCENARIO_PROFILE_ID
    profile = CandidateSimulationScenarioProfile.model_validate(
        {
            **profile_payload,
            "content_hash": gy_content_hash(profile_payload),
        }
    )
    declaration_payload = declaration.model_dump(mode="json", exclude={"content_hash"})
    declaration_payload.update(
        {
            "profile_config_ref": candidate_simulation_profile_ref(profile),
            "profile_content_hash": profile.content_hash,
        }
    )
    declaration = CandidateSimulationSyntheticModelDeclarationV1.model_validate(
        {
            **declaration_payload,
            "content_hash": gy_content_hash(declaration_payload),
        }
    )
    world = profile.context_inputs.world_model_record
    binding = world.slot_binding(CPI_OUTCOME_SLOT)
    target_binding = world.slot_binding("global.tax_rate")
    views = world_model_artifact_views(world)
    model_spec = ModelSpec.model_validate(load_core_json_artifact(store, views.model_spec_ref))
    resolved_entry_hashes = {
        entry.entry_content_hash for entry in world.substrate_registry_ref.resolved_entries
    }
    if views.bound_state_snapshot_ref is None:
        raise ValueError("x03_cpi_candidate_profile_bound_state_missing")
    if target_binding is None or not target_binding.state_path:
        raise ValueError("x03_cpi_candidate_profile_tax_rate_binding_missing")
    bound_state = load_state_snapshot(store, snapshot_ref=views.bound_state_snapshot_ref)
    physical_cpi = np.asarray(get_state_path(bound_state, CPI_STATE_PATH))
    physical_tax_rate = np.asarray(get_state_path(bound_state, target_binding.state_path))
    if (
        binding is None
        or world.region_or_jurisdiction != declared_scope.jurisdiction
        or world.population_scope != declared_scope.population
        or world.resolution != candidate_resolution
        or world.policy_domain != problem.domain
        or world.valid_time_scope != problem.jurisdiction_time.valid_time
        or binding.state_path != CPI_STATE_PATH
        or binding.unit != CPI_UNIT_ID
        or target_binding is None
        or target_binding.unit != "ratio"
        or profile.rule.operator_kind != "tax_relief_rate"
        or profile.rule.parameter_id != "rate"
        or profile.rule.target_world_slot != "global.tax_rate"
        or profile.rule.unit_id != "ratio"
        or profile.n5.baseline_state.get(CPI_OUTCOME_SLOT) != CPI_PRE_ACQUISITION_BASELINE
        or profile.n5.baseline_state.get("global.tax_rate") != 1.0
        or physical_cpi.size != 1
        or float(physical_cpi.item()) != CPI_PRE_ACQUISITION_BASELINE
        or physical_tax_rate.size != 1
        or float(physical_tax_rate.item()) != 1.0
        or declaration.outcome_variable != CPI_OUTCOME_SLOT
        or declaration.outcome_unit_id != CPI_UNIT_ID
        or declaration.outcome_noise_stddev != 0.0
        or not prepared_entry_hashes.issubset(resolved_entry_hashes)
        or model_spec.time_semantics is None
        or model_spec.time_semantics.frequency is not TimeFrequency.YEAR
        or model_spec.time_semantics.start_date != "2024-01-01"
        or model_spec.time_semantics.step_count != 1
    ):
        raise ValueError("x03_cpi_candidate_profile_binding_mismatch")
    return profile, declaration


def build_x03_cpi_candidate_provider(
    source_recording: dict[str, Any],
    *,
    problem: DesignProblem,
    profile: Any,
    store: ArtifactStore,
    evidence_root: Path,
) -> tuple[dict[str, Any], Any]:
    """Build a source-bound, synthetic one-action CPI N4 overlay.

    Recorded WDI N4 bytes are immutable parents only. The delivered candidate
    stages, their declared usage counters, and the NCM coefficient are new
    software-fixture inputs. They establish neither empirical causality nor
    authority.
    """
    import json

    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.ir.governance.problem_frame import ProblemDomain
    from polisyos.ir.model_layer.model_spec import ModelSpec
    from polisyos.ir.trinity import TrinityBundle
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.quality.candidate_simulation import CandidateSimulationScenarioProfile
    from polisyos.runtime.quality.cycle_substrate import cycle_job_profile_selection_ref
    from polisyos.runtime.quality.world_model_record import world_model_artifact_views
    from tests._helpers import acquisition_chain
    from tests._helpers.controlled_candidate_profile import (
        FIXED_FIXTURE_USAGE_BASIS,
        SyntheticCandidateProviderProfile,
    )
    from tools.quality.validation import (
        check_layer3_gy_design_generation_contract as n4_contract,
    )

    if (
        type(problem) is not DesignProblem
        or type(profile) is not CandidateSimulationScenarioProfile
        or problem.outcome_of_interest.target_variable != CPI_OUTCOME_SLOT
        or problem.jurisdiction_time.region != "UKR"
        or problem.jurisdiction_time.data_time != "2024"
        or profile.context_inputs.world_model_record.policy_domain != problem.domain
        or profile.profile_selection_ref != cycle_job_profile_selection_ref(problem)
        or profile.context_inputs.world_model_record.slot_binding(CPI_OUTCOME_SLOT) is None
    ):
        raise ValueError("x03_cpi_provider_scope_mismatch")

    controlled = acquisition_chain.controlled_served_wdi_generation_recording(
        source_recording,
        outcome_variable=CPI_OUTCOME_SLOT,
    )
    source_rows = source_recording.get("responses")
    responses = controlled.get("responses")
    if (
        not isinstance(source_rows, list)
        or not isinstance(responses, list)
        or len(source_rows) != len(responses)
    ):
        raise ValueError("x03_cpi_provider_recording_parent_denominator_mismatch")

    world = profile.context_inputs.world_model_record
    views = world_model_artifact_views(world)
    base_model = ModelSpec.model_validate(load_core_json_artifact(store, views.model_spec_ref))
    if base_model.time_semantics is None or base_model.calibrated or base_model.calibration_ref:
        raise ValueError("x03_cpi_provider_model_scope_or_authority_mismatch")
    model = base_model.model_dump(mode="json")
    model.update(
        {
            "model_id": "x03_cpi_2010_base_synthetic_candidate_model",
            "data_snapshot_ref": str(views.data_snapshot_ref.artifact_id),
            "registry_bundle_ref": str(views.registry_bundle_ref.artifact_id),
            "labels": ["synthetic", "candidate_only", "ukr", "cpi_level", "2024"],
            "assumptions": [
                {
                    "assumption_id": "x03_cpi_index_change_per_tax_rate_ratio",
                    "assumption_type": "structural",
                    "description": (
                        "Declared scenario-only NCM coefficient: +0.5 CPI index points "
                        "on a 2010=100 scale per unit increase in the toy global.tax_rate "
                        "ratio. The scenario sets the ratio from 1.0 to 0.0, so its declared "
                        "response is -0.5 index points. This is not an estimated causal effect."
                    ),
                    "confidence": "0.0",
                    "sensitivity_flag": True,
                }
            ],
        }
    )

    formalizer_parent_hashes = {
        acquisition_chain._SERVED_WDI_FIRST_FORMALIZER_HASH,
        acquisition_chain._SERVED_WDI_STAGE_PARENTS["formalizer"][1],
    }
    formalizer_indexes = [
        index
        for index, row in enumerate(source_rows)
        if row.get("role") == "formalizer"
        and row.get("raw_response_hash") in formalizer_parent_hashes
    ]
    if len(formalizer_indexes) != 2:
        raise ValueError("x03_cpi_provider_formalizer_parent_denominator_mismatch")

    def set_response(response: dict[str, Any], payload: dict[str, Any]) -> None:
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        response["raw_response"] = raw
        response["raw_response_hash"] = gy_content_hash(raw)

    final_formalizer: dict[str, Any] | None = None
    final_parent_hash = acquisition_chain._SERVED_WDI_STAGE_PARENTS["formalizer"][1]
    for index in formalizer_indexes:
        source_row = source_rows[index]
        response = responses[index]
        if (
            source_row.get("status") != "success"
            or response.get("status") != "success"
            or source_row.get("role") != "formalizer"
            or gy_content_hash(source_row.get("raw_response"))
            != source_row.get("raw_response_hash")
        ):
            raise ValueError("x03_cpi_provider_formalizer_parent_identity_mismatch")
        body = json.loads(response["raw_response"])
        policy = body["policy_spec"]
        actions = [
            item
            for item in policy["interventions"]
            if item.get("kind") == "budget_allocation_multiplier"
        ]
        if len(actions) != 1:
            raise ValueError("x03_cpi_provider_budget_action_denominator_mismatch")
        action = actions[0]
        old_id = action["intervention_id"]
        old_parameters = [
            item for item in policy["parameters"] if item.get("intervention_id") == old_id
        ]
        if len(old_parameters) != 1:
            raise ValueError("x03_cpi_provider_budget_parameter_denominator_mismatch")
        action_id = "lane01_x03_cpi_tax_relief_rate"
        action.update(
            {
                "kind": "tax_relief_rate",
                "intervention_id": action_id,
                "schedule": {"start_step": 0, "duration_steps": 1},
                "params": {"rate": 0},
                "notes": [
                    "do.target=global.tax_rate sign=decrease "
                    f"outcome={CPI_OUTCOME_SLOT} "
                    f"effect_path=global.tax_rate,{CPI_OUTCOME_SLOT}; "
                    "direct set-to from ratio baseline 1.0 to 0.0 under a declared "
                    "candidate-only synthetic NCM, not empirical causality"
                ],
            }
        )
        parameter = old_parameters[0]
        parameter.update(
            {
                "intervention_id": action_id,
                "param_id": "rate",
                "param_path": "rate",
                "default_value": "0",
                "min_value": "0",
                "max_value": "0.5",
            }
        )
        policy.update(
            {
                "policy_id": "lane01_x03_cpi_candidate_policy",
                "description": (
                    "Candidate-only UKR 2024 consumer price index level scenario on the "
                    "World Bank 2010=100 scale; the response is a declared synthetic model."
                ),
                "labels": ["synthetic", "candidate_only", "ukr", "cpi_level", "2024"],
                "interventions": [action],
                "parameters": [parameter],
            }
        )
        frame = body["problem_frame"]
        frame.update(
            {
                "problem_id": problem.design_problem_id,
                "domain": ProblemDomain.FISCAL.value,
                "narrative": problem.problem_statement,
                "labels": ["synthetic", "candidate_only", "ukr", "cpi_level", "2024"],
                "objectives": [
                    {
                        "objective_id": "consumer_price_index_level",
                        "metric_id": "consumer_price_index",
                        "direction": "minimize",
                        "weight": "1.0",
                    }
                ],
            }
        )
        body["model_spec"] = model
        TrinityBundle.model_validate(body)
        set_response(response, body)
        if source_row.get("raw_response_hash") == final_parent_hash:
            final_formalizer = response
    if final_formalizer is None:
        raise ValueError("x03_cpi_provider_final_formalizer_missing")

    selected_parents = {
        stage: acquisition_chain._SERVED_WDI_STAGE_PARENTS[stage][1]
        for stage in ("draft", "drafter_multipass", "critic")
    }
    selected_draft_name = "UKR 2024 CPI level tax-rate set-to candidate"
    limitation = (
        "The 2010=100 CPI level is source-bound input, while its response to the direct "
        "tax-rate set-to is a declared synthetic NCM assumption, not an empirical effect."
    )
    for source_row, response in zip(source_rows, responses, strict=True):
        parent_hash = source_row.get("raw_response_hash")
        role = source_row.get("role")
        if role == "draft" and parent_hash == selected_parents["draft"]:
            set_response(
                response,
                {
                    "draft_id": "lane01-x03-cpi-ukr-2024",
                    "problem_frame_ref": problem.design_problem_id,
                    "narrative": problem.problem_statement,
                    "rationale": limitation,
                    "confidence": 0.0,
                    "alternatives_considered": ["Keep the source-bound CPI baseline unchanged."],
                    "interventions": [
                        {
                            "name": selected_draft_name,
                            "description": (
                                "Set the registered global.tax_rate ratio from 1.0 to 0.0 "
                                "in the candidate-only UKR CPI-level scenario."
                            ),
                            "mechanism_type": "tax_relief_rate",
                            "target_population": "Ukraine national economy",
                            "parameters": {
                                "rate": 0,
                                "target_world_slot": "global.tax_rate",
                                "outcome_slots": [CPI_OUTCOME_SLOT],
                                "effect_path": ["global.tax_rate", CPI_OUTCOME_SLOT],
                                "sign": "decrease",
                                "estimand": "candidate_scenario_comparison",
                            },
                            "rationale": limitation,
                        }
                    ],
                },
            )
        elif role == "drafter_multipass" and parent_hash == selected_parents["drafter_multipass"]:
            set_response(
                response,
                {
                    "confidence_adjustment": 0.0,
                    "findings": [
                        {
                            "category": "side_effect",
                            "severity": "medium",
                            "description": limitation,
                            "suggested_fix": "Establish independent causal and measurement evidence.",
                            "affected_intervention": selected_draft_name,
                            "anchor": "intervention:0",
                        }
                    ],
                },
            )
        elif role == "critic" and parent_hash == selected_parents["critic"]:
            set_response(
                response,
                {
                    "verdict": "NEEDS_REVISION",
                    "alignment_score": 0.0,
                    "completeness_score": 0.0,
                    "overall_quality": 0.0,
                    "problem_frame_ref": problem.design_problem_id,
                    "report_id": "lane01_x03_cpi_candidate_critic",
                    "reflexion_hint": limitation,
                    "issues": [
                        {
                            "issue_id": "LANE01-X03-SYNTHETIC-CPI-001",
                            "category": "ALIGNMENT",
                            "severity": "WARNING",
                            "message": limitation,
                            "location": "model_spec.assumptions",
                            "suggestion": (
                                "Keep the effect candidate-only until an independently "
                                "grounded causal relationship exists."
                            ),
                        }
                    ],
                },
            )
    critic_matches = [
        response
        for source_row, response in zip(source_rows, responses, strict=True)
        if source_row.get("role") == "critic"
        and source_row.get("raw_response_hash") == selected_parents["critic"]
    ]
    if len(critic_matches) != 1:
        raise ValueError("x03_cpi_provider_critic_denominator_mismatch")
    critic_payload = json.loads(critic_matches[0]["raw_response"])
    critic_payload["ir_ref"] = gy_content_hash(json.loads(final_formalizer["raw_response"]))
    set_response(critic_matches[0], critic_payload)

    identity = gy_content_hash(
        {
            "parent_recording_id": controlled["derived_from_recording_id"],
            "parent_content_hash": controlled["derived_from_content_hash"],
            "problem_id": problem.design_problem_id,
            "responses": [row.get("raw_response_hash") for row in responses],
            "outcome": CPI_OUTCOME_SLOT,
            "base_year": CPI_BASE_YEAR,
        }
    ).removeprefix("sha256:")[:20]
    fixture_id = f"synthetic_lane01_x03_cpi_n4_{identity}"
    controlled.update(
        {
            "design_problem_id": problem.design_problem_id,
            "fixture_id": fixture_id,
            "recording_id": fixture_id,
            "recording_source": "synthetic_ukr_cpi_overlay_of_recorded_capture",
        }
    )
    controlled["recording_content_hash"] = gy_content_hash(
        {key: value for key, value in controlled.items() if key != "recording_content_hash"}
    )
    n4_contract._validate_recording_fixture(controlled)

    stage_parents = {
        "draft": ("draft", selected_parents["draft"]),
        "drafter_multipass": ("drafter_multipass", selected_parents["drafter_multipass"]),
        "drafter_consolidation": ("draft", selected_parents["draft"]),
        "formalizer": ("formalizer", final_parent_hash),
        "critic": ("critic", selected_parents["critic"]),
    }
    usage = {"prompt_tokens": 64, "completion_tokens": 32, "total_tokens": 96}
    provider_rows: list[tuple[str, str]] = []
    for stage, (parent_role, parent_hash) in stage_parents.items():
        matches = [
            (source_row, response)
            for source_row, response in zip(source_rows, responses, strict=True)
            if source_row.get("role") == parent_role
            and source_row.get("raw_response_hash") == parent_hash
        ]
        if len(matches) != 1:
            raise ValueError("x03_cpi_provider_stage_parent_unresolved")
        source_row, response = matches[0]
        if (
            source_row.get("status") != "success"
            or response.get("status") != "success"
            or source_row.get("model_id") != source_recording.get("model_id")
            or gy_content_hash(source_row.get("raw_response")) != parent_hash
            or gy_content_hash(response.get("raw_response")) != response.get("raw_response_hash")
        ):
            raise ValueError("x03_cpi_provider_stage_parent_content_mismatch")
        row = {
            "status": "success",
            "source_model_id": source_recording["model_id"],
            "raw_response": response["raw_response"],
            "raw_response_hash": response["raw_response_hash"],
            "usage": {**usage, "usage_status": "known"},
            "legacy_counter_availability": "not_established",
            "usage_declaration": "new_synthetic_test_input_not_provider_measurement",
            "parent_role": parent_role,
            "parent_response_hash": parent_hash,
        }
        provider_rows.append((stage, json.dumps(row, sort_keys=True, separators=(",", ":"))))

    provider = SyntheticCandidateProviderProfile(
        model_id=str(source_recording["model_id"]),
        profile_selection_ref=cycle_job_profile_selection_ref(problem),
        source_recording_id=str(source_recording["recording_id"]),
        source_recording_content_hash=str(source_recording["recording_content_hash"]),
        controlled_recording_content_hash=str(controlled["recording_content_hash"]),
        response_rows=tuple(provider_rows),
        evidence_root=evidence_root,
        usage_basis=FIXED_FIXTURE_USAGE_BASIS,
    )
    return controlled, provider
