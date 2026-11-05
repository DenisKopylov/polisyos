"""Candidate-only GDP fixtures for the genuine served acquisition path.

The known captured observation is a test input to existing WDI and N4 producers. Local
catalog metadata and model couplings below do not establish rights, currentness,
causal effects, or publication authority.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from tests._helpers.lane01_wdi_profiles import GDP_PROFILE

if TYPE_CHECKING:
    from polisyos.core.artifacts import ArtifactStore
    from polisyos.runtime.quality.candidate_simulation import (
        CandidateSimulationScenarioProfile,
        CandidateSimulationSyntheticModelDeclarationV1,
    )
    from polisyos.runtime.quality.design_problem import DesignProblem
    from polisyos.runtime.quality.substrate_registry import (
        CatalogServingSourcePaths,
        CatalogServingSourceSelection,
        SubstrateRegistry,
    )
    from polisyos.scientist.orchestration.engine import BudgetInvocationQuotaPolicy
    from tests._helpers.controlled_candidate_profile import SyntheticCandidateProviderProfile


ANNUAL_GDP_VALUE_USD = 29_298_013_000_000
ANNUAL_GDP_SCOPE_REQUEST = (
    "For USA in calendar year 2024, assess annual nominal GDP in current US dollars "
    "and a candidate tax_relief_rate set-to on global.tax_rate from a declared 0.5 "
    "ratio baseline to 0.0. Any USD response is a declared synthetic SCM assumption."
)
_CANDIDATE_ONLY_REQUEST = (
    "All proposals remain candidate-only until independent evidence supports any measured effect."
)
ANNUAL_GDP_REQUEST = f"{ANNUAL_GDP_SCOPE_REQUEST} {_CANDIDATE_ONLY_REQUEST}"
ANNUAL_GDP_WDI_PROFILE = replace(GDP_PROFILE, fixture_value=float(ANNUAL_GDP_VALUE_USD))

_ANNUAL_GDP_PROBLEM_STATEMENT = (
    "Assess a candidate-only USA 2024 annual nominal GDP scenario in current US dollars "
    "with a registered tax-rate set-to from 0.5 to 0.0."
)
_ANNUAL_GDP_INTERVENTION_ID = "annual_gdp_tax_relief_rate"
_ANNUAL_GDP_COEFFICIENT_USD_PER_RATIO = -500_000_000_000.0
_ANNUAL_GDP_TARGET_BASELINE = 0.5
_ANNUAL_GDP_OUTCOME_BASELINE_USD = 0.0
# A new 96-token bookkeeping budget per local fixture stage exercises the
# settlement path. These are declared test counters, not measured tokens or
# a historical/provider bill. Captured recording usage remains unattested.
_DECLARED_STAGE_USAGE = {"prompt_tokens": 64, "completion_tokens": 32, "total_tokens": 96}


@contextmanager
def annual_gdp_catalog_source(
    source_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[CatalogServingSourceSelection, CatalogServingSourcePaths, SubstrateRegistry]]:
    """Publish and readmit the GDP candidate's test-owned macro substrate.

    The existing substrate fixture producer owns all metadata files. This
    scoped wrapper adds only the low-coverage, bounds-only ``macro_state`` row
    to the exact unpublished source root. The published Catalog producer and
    existing registry reader then consume those bytes. These values describe
    candidate inventory availability only; they are not empirical coverage,
    currentness, source authority, or measurement evidence.

    Args:
        source_root: Fresh fixture-owned candidate source root.
        monkeypatch: Pytest monkeypatch scope used by the composed fixture.

    Yields:
        The Catalog selection, resolved source paths, and owner-built registry.

    Raises:
        ValueError: If the source root is not a fresh, direct fixture directory.
        AssertionError: If catalog readmission fails to retain the declared row.
    """
    from polisyos.runtime.quality import substrate_registry as registry_owner
    from tests._helpers.candidate_cycle_source_profile import (
        complete_candidate_cycle_catalog_source,
    )
    from tests.unit.runtime.quality import test_substrate_registry

    requested_root = Path(source_root)
    if requested_root.is_symlink() or not requested_root.is_dir():
        raise ValueError("annual_gdp_catalog_source_root_invalid")
    owned_root = requested_root.resolve(strict=True)
    paths = registry_owner.default_substrate_catalog_paths(owned_root)
    measurement_path = paths.measurement_registry_path
    identification_path = paths.identification_mode_registry_path
    if measurement_path is None or identification_path is None:
        raise ValueError("annual_gdp_catalog_source_metadata_path_missing")

    original_writer = test_substrate_registry._write_substrate_catalog_fixture
    written_owned_root = False

    def write_annual_gdp_fixture_metadata(
        root: Path,
        *,
        include_graphs: bool = True,
    ) -> None:
        nonlocal written_owned_root
        original_writer(root, include_graphs=include_graphs)
        candidate_root = Path(root)
        if candidate_root.is_symlink() or candidate_root.resolve(strict=True) != owned_root:
            return
        if written_owned_root:
            raise AssertionError("annual_gdp_catalog_source_metadata_repeated")
        measurement = json.loads(measurement_path.read_text(encoding="utf-8"))
        coverage_rules = measurement.get("coverage_rules")
        if not isinstance(coverage_rules, dict) or "macro_state" in coverage_rules:
            raise AssertionError("annual_gdp_catalog_source_macro_coverage_not_fresh")
        coverage_rules["macro_state"] = 0.10
        measurement_path.write_text(
            json.dumps(measurement, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        identification = json.loads(identification_path.read_text(encoding="utf-8"))
        if "macro_state" in identification:
            raise AssertionError("annual_gdp_catalog_source_macro_identification_not_fresh")
        identification["macro_state"] = {"selected_mode": "bounds_only"}
        identification_path.write_text(
            json.dumps(identification, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        written_owned_root = True

    with monkeypatch.context() as scoped:
        scoped.setattr(
            test_substrate_registry,
            "_write_substrate_catalog_fixture",
            write_annual_gdp_fixture_metadata,
        )
        with complete_candidate_cycle_catalog_source(owned_root, monkeypatch) as prepared:
            macro_entries = prepared[2].resolve(family_id="macro_state")
            if not written_owned_root or not macro_entries:
                raise AssertionError("annual_gdp_catalog_source_macro_row_not_readmitted")
            if any(
                entry.coverage.coverage_score != 0.10 or entry.identification_mode != "bounds_only"
                for entry in macro_entries
            ):
                raise AssertionError("annual_gdp_catalog_source_macro_row_mismatch")
            yield prepared


def annual_gdp_candidate_problem() -> DesignProblem:
    """Build the exact USA 2024 GDP request as a typed candidate-only problem.

    The captured served WDI recording supplies only the existing controlled
    compiler parent. Scope and source-span text below are new fixture inputs;
    no observation or authority claim is attached to the problem.

    Returns:
        A strict current-schema DesignProblem with a candidate tax-rate set-to.
    """
    from polisyos.runtime.quality.design_problem import DesignProblem
    from tests._helpers import acquisition_chain, controlled_candidate_profile
    from tests._helpers.lane01_candidate_source import GDP_COMPILER_INPUT

    if acquisition_chain.SERVED_WDI_CANDIDATE_ONLY_SOURCE != _CANDIDATE_ONLY_REQUEST:
        raise ValueError("annual_gdp_candidate_only_request_source_changed")
    source_recording = acquisition_chain.load_served_wdi_generation_recording()
    current_parent = controlled_candidate_profile._current_compiler_problem(source_recording)
    baseline_problem = acquisition_chain.controlled_served_wdi_problem(
        current_parent,
        raw_request=acquisition_chain.SERVED_WDI_FISCAL_REQUEST,
    )
    payload = baseline_problem.model_dump(mode="json")
    payload["domain"] = "economic"
    payload["problem_statement"] = _ANNUAL_GDP_PROBLEM_STATEMENT
    payload["nl_provenance"]["raw_request"] = ANNUAL_GDP_REQUEST
    payload["jurisdiction_time"].update(
        {
            "region": "USA",
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
            "objective_id": "annual_gdp",
            "description": "Improve annual nominal GDP in current US dollars.",
            "metric_id": "annual_gdp",
            "direction": "maximize",
        }
    ]
    payload["candidate_lever_space"] = {
        "allowed_operator_kinds": ["tax_relief_rate"],
        "candidate_levers": [
            {
                "lever_id": _ANNUAL_GDP_INTERVENTION_ID,
                "operator_kind": "tax_relief_rate",
                "instrument": "Registered candidate tax relief rate",
                "target_slot": "global.tax_rate",
            }
        ],
    }
    payload["constraints"] = [
        {
            "constraint_id": "annual_gdp_request_scope",
            "description": "Keep the candidate within the requested USA 2024 annual GDP scope.",
            "hard": True,
            "admissibility_basis": "request_text",
            "source_text": ANNUAL_GDP_SCOPE_REQUEST,
        },
        {
            "constraint_id": "no_authority_without_a",
            "description": "Generated proposals remain candidate-only.",
            "hard": True,
            "admissibility_basis": "request_text",
            "source_text": _CANDIDATE_ONLY_REQUEST,
        },
    ]
    payload["stakeholders"] = [
        {
            "stakeholder_id": "us_economic_analysts",
            "name": "US economic analysts",
            "role": "reviewer",
        }
    ]
    payload["outcome_of_interest"].update(
        {
            "target_variable": "global.gdp",
            "metric_id": "annual_gdp",
            "estimand": "Candidate-only annual nominal GDP in current US dollars.",
            "direction": "maximize",
        }
    )
    payload["evidence_acquisition_needs"] = {
        "needs": [
            {
                "need_id": "annual_gdp_observation",
                "question": "Which annual public source supplies nominal GDP in current US dollars?",
                "required_for": "Candidate-only GDP input availability.",
            }
        ]
    }
    payload["runtime_hints"]["n7_scope_profile"] = {
        "profile_id": GDP_COMPILER_INPUT.profile_id,
        "jurisdiction": GDP_COMPILER_INPUT.jurisdiction,
        "population": GDP_COMPILER_INPUT.population,
        "entity_scope": GDP_COMPILER_INPUT.entity_scope,
        "time_window": {
            "start": GDP_COMPILER_INPUT.time_start,
            "end": GDP_COMPILER_INPUT.time_end,
        },
        "time_role": GDP_COMPILER_INPUT.time_role,
        "granularity": GDP_COMPILER_INPUT.granularity,
        "required_constructs": list(GDP_COMPILER_INPUT.required_constructs),
    }

    problem = DesignProblem.model_validate(payload)
    constraints = {item.constraint_id: item for item in problem.constraints}
    if (
        problem.nl_provenance.raw_request != ANNUAL_GDP_REQUEST
        or ANNUAL_GDP_SCOPE_REQUEST not in problem.nl_provenance.raw_request
        or _CANDIDATE_ONLY_REQUEST not in problem.nl_provenance.raw_request
        or constraints["annual_gdp_request_scope"].source_text != ANNUAL_GDP_SCOPE_REQUEST
        or constraints["no_authority_without_a"].source_text != _CANDIDATE_ONLY_REQUEST
        or problem.domain != "economic"
        or problem.jurisdiction_time.region != "USA"
        or problem.jurisdiction_time.data_time != "2024"
        or problem.jurisdiction_time.as_of != "2024-12-31"
        or problem.outcome_of_interest.target_variable != "global.gdp"
        or problem.candidate_lever_space.candidate_levers[0].target_slot != "global.tax_rate"
    ):
        raise ValueError("annual_gdp_candidate_problem_binding_mismatch")
    return problem


def build_annual_gdp_candidate_profile(
    *,
    tmp_path: Path,
    store: ArtifactStore,
    problem: DesignProblem,
    source_owner_root: Path | None = None,
    prepared_substrate_registry: SubstrateRegistry | None = None,
    invocation_quota_policy: BudgetInvocationQuotaPolicy | None = None,
) -> tuple[CandidateSimulationScenarioProfile, CandidateSimulationSyntheticModelDeclarationV1]:
    """Build a current WMR-bound annual GDP profile and its declared toy SCM.

    The served profile producer resolves the actual WMR, bindings, selected
    state, substrate registry, and model spec. Its declared 0 USD GDP fixture
    baseline and 0.5 tax-rate baseline are independently checked against the
    bound Foundry state. The coefficient is a software assumption only.

    Args:
        tmp_path: Owned fixture directory used by the served WMR producer.
        store: The caller's existing artifact store.
        problem: The typed annual GDP candidate problem.
        source_owner_root: Optional selected catalog owner root.
        prepared_substrate_registry: Optional registry already admitted from that root.
        invocation_quota_policy: Optional run-owned candidate invocation quota.

    Returns:
        The typed candidate profile and its content-bound synthetic model declaration.

    Raises:
        ValueError: If scope, physical baselines, or model time do not match the fixture.
    """
    import numpy as np

    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.foundry.execute.executor import get_state_path, load_state_snapshot
    from polisyos.ir.kernel.time_semantics import TimeSemantics
    from polisyos.ir.model_layer.model_spec import ModelSpec
    from polisyos.ir.model_layer.types import TimeFrequency
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.quality.candidate_simulation import (
        CandidateScenarioSetToRule,
        CandidateSimulationSyntheticModelDeclarationV1,
        candidate_simulation_profile_ref,
    )
    from polisyos.runtime.quality.design_problem import DesignProblem
    from polisyos.runtime.quality.world_model_record import world_model_artifact_views
    from tests._helpers import acquisition_served_history as served
    from tests._helpers.world_model_record import FABRIC_PAYLOAD

    if (
        type(problem) is not DesignProblem
        or problem.outcome_of_interest.target_variable != "global.gdp"
        or problem.jurisdiction_time.region != "USA"
        or problem.jurisdiction_time.data_time != "2024"
    ):
        raise ValueError("annual_gdp_candidate_profile_problem_scope_mismatch")
    if FABRIC_PAYLOAD.get("gdp") != _ANNUAL_GDP_OUTCOME_BASELINE_USD:
        raise ValueError("annual_gdp_candidate_fixture_world_gdp_baseline_mismatch")
    if FABRIC_PAYLOAD.get("tax_rate") != _ANNUAL_GDP_TARGET_BASELINE:
        raise ValueError("annual_gdp_candidate_fixture_world_tax_baseline_mismatch")

    rule = CandidateScenarioSetToRule(
        operator_kind="tax_relief_rate",
        parameter_id="rate",
        target_world_slot="global.tax_rate",
        unit_id="ratio",
        minimum=0,
        maximum=0,
    )
    profile, source_declaration = served._served_wdi_candidate_profile(
        tmp_path=tmp_path,
        store=store,
        problem=problem,
        source_owner_root=source_owner_root,
        prepared_substrate_registry=prepared_substrate_registry,
        country_code="USA",
        data_year=2024,
        population_scope="national_economy",
        invocation_quota_policy=invocation_quota_policy,
        candidate_rule=rule,
    )
    world = profile.context_inputs.world_model_record
    views = world_model_artifact_views(world)
    state_ref = views.bound_state_snapshot_ref
    verification = store.verify(state_ref)
    if not verification.ok:
        raise ValueError("annual_gdp_candidate_bound_state_invalid")
    state = load_state_snapshot(store, snapshot_ref=state_ref)

    def read_bound_scalar(slot_id: str) -> float:
        binding = world.slot_binding(slot_id)
        if binding is None or not binding.state_path:
            raise ValueError("annual_gdp_candidate_wmr_slot_binding_missing:" + slot_id)
        value = np.asarray(get_state_path(state, binding.state_path))
        if value.size != 1:
            raise ValueError("annual_gdp_candidate_wmr_slot_not_scalar:" + slot_id)
        return float(value.item())

    physical_baselines = {
        "global.tax_rate": read_bound_scalar("global.tax_rate"),
        "global.gdp": read_bound_scalar("global.gdp"),
    }
    if (
        physical_baselines["global.tax_rate"] != _ANNUAL_GDP_TARGET_BASELINE
        or physical_baselines["global.gdp"] != _ANNUAL_GDP_OUTCOME_BASELINE_USD
        or profile.n5.baseline_state != physical_baselines
        or profile.rule != rule
        or world.region_or_jurisdiction != "USA"
        or world.population_scope != "national_economy"
        or world.policy_domain != "economic"
        or world.valid_time_scope != "2024-01-01/2024-12-31"
    ):
        raise ValueError("annual_gdp_candidate_profile_wmr_baseline_mismatch")

    tax_binding = world.slot_binding("global.tax_rate")
    gdp_binding = world.slot_binding("global.gdp")
    if (
        tax_binding is None
        or tax_binding.unit != "ratio"
        or gdp_binding is None
        or gdp_binding.unit != "usd"
    ):
        raise ValueError("annual_gdp_candidate_profile_wmr_unit_mismatch")

    model_spec = ModelSpec.model_validate(load_core_json_artifact(store, views.model_spec_ref))
    if model_spec.time_semantics is None:
        raise ValueError("annual_gdp_candidate_model_time_missing")
    model_time = TimeSemantics.model_validate(model_spec.time_semantics.model_dump(mode="python"))
    if (
        model_time.frequency is not TimeFrequency.YEAR
        or model_time.start_date != "2024-01-01"
        or model_time.step_count != 1
        or profile.n5.horizon.start != 0
        or profile.n5.horizon.end != 0
        or profile.n5.horizon.step != 1
    ):
        raise ValueError("annual_gdp_candidate_model_time_scope_mismatch")

    declaration_fields = source_declaration.model_dump(mode="json", exclude={"content_hash"})
    if (
        declaration_fields["profile_config_ref"] != candidate_simulation_profile_ref(profile)
        or declaration_fields["profile_content_hash"] != profile.content_hash
        or declaration_fields["profile_selection_ref"] != profile.profile_selection_ref
        or declaration_fields["target_world_slot"] != "global.tax_rate"
        or declaration_fields["outcome_variable"] != "global.gdp"
        or declaration_fields["target_baseline"] != _ANNUAL_GDP_TARGET_BASELINE
        or declaration_fields["outcome_baseline"] != _ANNUAL_GDP_OUTCOME_BASELINE_USD
        or declaration_fields["target_unit_id"] != "ratio"
        or declaration_fields["outcome_unit_id"] != "usd"
    ):
        raise ValueError("annual_gdp_candidate_source_declaration_mismatch")
    declaration_fields["outcome_per_target_unit"] = _ANNUAL_GDP_COEFFICIENT_USD_PER_RATIO
    declaration_fields["outcome_noise_stddev"] = 0.0
    declaration_draft = CandidateSimulationSyntheticModelDeclarationV1.model_construct(
        **declaration_fields,
        content_hash="sha256:" + "0" * 64,
    )
    declaration = CandidateSimulationSyntheticModelDeclarationV1.model_validate(
        {
            **declaration_fields,
            "content_hash": gy_content_hash(
                declaration_draft.model_dump(mode="json", exclude={"content_hash"})
            ),
        }
    )
    return profile, declaration


def build_annual_gdp_candidate_provider(
    source_recording: dict[str, Any],
    *,
    problem: DesignProblem,
    profile: CandidateSimulationScenarioProfile,
    store: ArtifactStore,
    evidence_root: Path,
) -> tuple[dict[str, Any], SyntheticCandidateProviderProfile]:
    """Create a content-bound annual GDP N4 overlay and synthetic provider rows.

    Existing captured bytes are used only as response parents. Formalizer,
    draft, multipass, and critic outputs are new candidate-only software
    fixtures. Token values are explicit synthetic usage inputs marked as not
    provider measurements or historical bills.

    Args:
        source_recording: The retained served WDI recording used as immutable parent.
        problem: The exact annual GDP candidate problem.
        profile: The WMR-bound annual GDP N5 profile.
        store: The caller's existing artifact store for selected WMR refs.
        evidence_root: Test-owned provider evidence directory.

    Returns:
        The validated controlled recording and its typed synthetic provider profile.

    Raises:
        ValueError: If source rows, WMR refs, or fixture bindings do not match.
    """
    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.ir.model_layer.model_spec import ModelSpec
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.quality.candidate_simulation import CandidateSimulationScenarioProfile
    from polisyos.runtime.quality.cycle_substrate import cycle_job_profile_selection_ref
    from polisyos.runtime.quality.design_problem import DesignProblem
    from polisyos.runtime.quality.world_model_record import world_model_artifact_views
    from tests._helpers import acquisition_chain
    from tests._helpers.controlled_candidate_profile import SyntheticCandidateProviderProfile
    from tools.quality.validation import (
        check_layer3_gy_design_generation_contract as n4_contract,
    )

    if (
        type(problem) is not DesignProblem
        or type(profile) is not CandidateSimulationScenarioProfile
        or problem.outcome_of_interest.target_variable != "global.gdp"
        or problem.jurisdiction_time.region != "USA"
        or problem.jurisdiction_time.data_time != "2024"
        or profile.profile_selection_ref != cycle_job_profile_selection_ref(problem)
    ):
        raise ValueError("annual_gdp_candidate_provider_scope_mismatch")
    if profile.context_inputs.world_model_record.slot_binding("global.gdp") is None:
        raise ValueError("annual_gdp_candidate_provider_wmr_binding_missing")

    controlled = acquisition_chain.controlled_served_wdi_generation_recording(
        source_recording,
        outcome_variable="global.gdp",
    )
    source_responses = source_recording.get("responses")
    responses = controlled.get("responses")
    if (
        not isinstance(source_responses, list)
        or not isinstance(responses, list)
        or len(source_responses) != len(responses)
    ):
        raise ValueError("annual_gdp_candidate_recording_parent_denominator_mismatch")

    world = profile.context_inputs.world_model_record
    views = world_model_artifact_views(world)
    base_model = ModelSpec.model_validate(load_core_json_artifact(store, views.model_spec_ref))
    if base_model.time_semantics is None:
        raise ValueError("annual_gdp_candidate_provider_model_time_missing")
    data_snapshot_id = str(views.data_snapshot_ref.artifact_id)
    registry_bundle_id = str(views.registry_bundle_ref.artifact_id)
    time_semantics = base_model.time_semantics.model_dump(mode="json")

    formalizer_parent_hashes = {
        acquisition_chain._SERVED_WDI_FIRST_FORMALIZER_HASH,
        acquisition_chain._SERVED_WDI_STAGE_PARENTS["formalizer"][1],
    }
    formalizer_indexes = [
        index
        for index, (source_row, _) in enumerate(zip(source_responses, responses, strict=True))
        if source_row.get("role") == "formalizer"
        and source_row.get("raw_response_hash") in formalizer_parent_hashes
    ]
    if len(formalizer_indexes) != 2:
        raise ValueError("annual_gdp_candidate_formalizer_parent_denominator_mismatch")

    selected_formalizer_hash = acquisition_chain._SERVED_WDI_STAGE_PARENTS["formalizer"][1]
    final_formalizer: dict[str, Any] | None = None
    for index in formalizer_indexes:
        source_row = source_responses[index]
        response = responses[index]
        if (
            source_row.get("role") != "formalizer"
            or response.get("role") != "formalizer"
            or source_row.get("status") != "success"
            or response.get("status") != "success"
            or source_row.get("raw_response_hash") not in formalizer_parent_hashes
            or gy_content_hash(source_row.get("raw_response"))
            != source_row.get("raw_response_hash")
        ):
            raise ValueError("annual_gdp_candidate_formalizer_parent_identity_mismatch")
        body = json.loads(response["raw_response"])
        policy_spec = body["policy_spec"]
        interventions = policy_spec["interventions"]
        selected_actions = [
            item for item in interventions if item.get("kind") == "budget_allocation_multiplier"
        ]
        if len(selected_actions) != 1:
            raise ValueError("annual_gdp_candidate_parent_action_denominator_mismatch")
        action = selected_actions[0]
        original_intervention_id = action["intervention_id"]
        parameters = policy_spec["parameters"]
        rate_parameters = [
            item
            for item in parameters
            if item.get("intervention_id") == original_intervention_id
            and item.get("param_path") == "multiplier"
        ]
        if len(rate_parameters) != 1:
            raise ValueError("annual_gdp_candidate_parent_parameter_denominator_mismatch")
        action.update(
            {
                "kind": "tax_relief_rate",
                "intervention_id": _ANNUAL_GDP_INTERVENTION_ID,
                "schedule": {"start_step": 0, "duration_steps": 1},
                "params": {"rate": 0},
                "notes": [
                    "do.target=global.tax_rate sign=decrease outcome=global.gdp "
                    "effect_path=global.tax_rate,global.gdp; test-owned candidate set-to "
                    "from ratio baseline 0.5 to 0 under a declared synthetic SCM"
                ],
            }
        )
        rate_parameters[0].update(
            {
                "intervention_id": _ANNUAL_GDP_INTERVENTION_ID,
                "param_id": "rate",
                "param_path": "rate",
                "default_value": "0",
                "min_value": "0",
                "max_value": "0.5",
            }
        )
        policy_spec.update(
            {
                "policy_id": "annual_gdp_tax_rate_candidate_policy",
                "description": (
                    "Candidate-only software fixture: set the registered global tax-rate "
                    "ratio from 0.5 to 0.0; the declared GDP response is synthetic."
                ),
                "labels": ["synthetic", "candidate_only", "usa", "annual_gdp", "2024"],
                "interventions": [action],
                "parameters": rate_parameters,
            }
        )
        frame = body["problem_frame"]
        frame.update(
            {
                "problem_id": problem.design_problem_id,
                "domain": "economic",
                "narrative": problem.problem_statement,
                "labels": ["synthetic", "candidate_only", "usa", "annual_gdp", "2024"],
                "objectives": [
                    {
                        "objective_id": "annual_gdp",
                        "metric_id": "annual_gdp",
                        "direction": "maximize",
                        "weight": "1.0",
                    }
                ],
            }
        )
        model_spec = body["model_spec"]
        model_spec.update(
            {
                "model_id": "annual_gdp_tax_rate_candidate_model",
                "data_snapshot_ref": data_snapshot_id,
                "registry_bundle_ref": registry_bundle_id,
                "time_semantics": time_semantics,
                "labels": ["synthetic", "candidate_only", "usa", "annual_gdp", "2024"],
                "assumptions": [
                    {
                        "assumption_id": "tax_rate_to_annual_gdp_synthetic_coefficient",
                        "assumption_type": "structural",
                        "description": (
                            "Declared test-only SCM coefficient: -500,000,000,000 current "
                            "USD per unit tax-rate ratio. It is not an empirical or "
                            "policy-effect estimate."
                        ),
                        "confidence": "0.0",
                        "sensitivity_flag": True,
                    }
                ],
            }
        )
        response["raw_response"] = json.dumps(body, sort_keys=True, separators=(",", ":"))
        response["raw_response_hash"] = gy_content_hash(response["raw_response"])
        if source_row.get("raw_response_hash") == selected_formalizer_hash:
            final_formalizer = response
    if final_formalizer is None:
        raise ValueError("annual_gdp_candidate_final_formalizer_missing")

    selected_stage_parents = {
        stage: acquisition_chain._SERVED_WDI_STAGE_PARENTS[stage][1]
        for stage in ("draft", "drafter_multipass", "critic")
    }
    for source_row, response in zip(source_responses, responses, strict=True):
        role = response.get("role")
        source_hash = source_row.get("raw_response_hash")
        if role == "draft" and source_hash == selected_stage_parents["draft"]:
            body = json.loads(response["raw_response"])
            body.update(
                {
                    "draft_id": "annual-gdp-usa-2024-tax-rate",
                    "problem_frame_ref": problem.design_problem_id,
                    "narrative": problem.problem_statement,
                    "rationale": (
                        "This candidate-only software fixture sets global.tax_rate from a "
                        "physically bound 0.5 ratio baseline to 0.0. The declared synthetic "
                        "coefficient maps the change to 250 billion current USD; it makes no "
                        "empirical or causal claim."
                    ),
                    "confidence": 0.0,
                    "alternatives_considered": [
                        "No-change baseline retained for the N5 comparison."
                    ],
                    "interventions": [
                        {
                            "name": "Annual GDP tax-rate candidate set-to",
                            "description": (
                                "Set the registered global.tax_rate ratio from 0.5 to 0.0."
                            ),
                            "mechanism_type": "tax_relief_rate",
                            "parameters": {
                                "rate": 0,
                                "target_world_slot": "global.tax_rate",
                                "sign": "decrease",
                                "outcome_slots": ["global.gdp"],
                                "effect_path": ["global.tax_rate", "global.gdp"],
                            },
                            "rationale": (
                                "A declared test-only synthetic SCM provides the USD response; "
                                "this is not an empirical policy effect."
                            ),
                            "target_population": "USA national economy",
                        }
                    ],
                }
            )
            _replace_recording_response(response, body)
        elif (
            role == "drafter_multipass"
            and source_hash == selected_stage_parents["drafter_multipass"]
        ):
            body = json.loads(response["raw_response"])
            findings = body.get("findings")
            if not isinstance(findings, list) or len(findings) != 1:
                raise ValueError("annual_gdp_candidate_multipass_finding_denominator_mismatch")
            finding = dict(findings[0])
            finding.update(
                {
                    "anchor": "annual_gdp_tax_rate_synthetic_coefficient",
                    "description": (
                        "The 250 billion USD change is computed from an explicit synthetic "
                        "coefficient and a 0.5 ratio delta, not independent evidence."
                    ),
                    "affected_intervention": _ANNUAL_GDP_INTERVENTION_ID,
                    "suggested_fix": (
                        "Keep the result candidate-only until a measurement contract and "
                        "causal coupling are independently established."
                    ),
                }
            )
            body["findings"] = [finding]
            _replace_recording_response(response, body)
        elif role == "critic" and source_hash == selected_stage_parents["critic"]:
            body = json.loads(response["raw_response"])
            issues = body.get("issues")
            if not isinstance(issues, list) or len(issues) != 1:
                raise ValueError("annual_gdp_candidate_critic_issue_denominator_mismatch")
            issue = dict(issues[0])
            issue.update(
                {
                    "issue_id": "ANNUAL-GDP-SYNTHETIC-SCM-001",
                    "category": "ALIGNMENT",
                    "severity": "WARNING",
                    "message": (
                        "The tax-rate to GDP coefficient is a declared software-fixture "
                        "assumption, not measured or causally grounded evidence."
                    ),
                    "location": "model_spec.assumptions",
                    "suggestion": (
                        "Preserve limited candidate-only status and do not publish this "
                        "synthetic effect as a policy estimate."
                    ),
                }
            )
            body.update(
                {
                    "verdict": "NEEDS_REVISION",
                    "alignment_score": 0.0,
                    "completeness_score": 0.0,
                    "overall_quality": 0.0,
                    "problem_frame_ref": problem.design_problem_id,
                    "report_id": "annual_gdp_tax_rate_candidate_critic",
                    "reflexion_hint": (
                        "The recorded ratio action is unit-consistent, but its USD effect is "
                        "synthetic and remains inadmissible as a causal estimate."
                    ),
                }
            )
            body["issues"] = [issue]
            _replace_recording_response(response, body)

    final_ir_ref = gy_content_hash(json.loads(final_formalizer["raw_response"]))
    selected_critic_rows = [
        response
        for source_row, response in zip(source_responses, responses, strict=True)
        if source_row.get("role") == "critic"
        and source_row.get("raw_response_hash") == selected_stage_parents["critic"]
    ]
    if len(selected_critic_rows) != 1:
        raise ValueError("annual_gdp_candidate_critic_parent_denominator_mismatch")
    critic_body = json.loads(selected_critic_rows[0]["raw_response"])
    critic_body["ir_ref"] = final_ir_ref
    _replace_recording_response(selected_critic_rows[0], critic_body)

    identity_seed = gy_content_hash(
        {
            "parent_recording_id": controlled["derived_from_recording_id"],
            "parent_content_hash": controlled["derived_from_content_hash"],
            "problem_id": problem.design_problem_id,
            "response_hashes": [item.get("raw_response_hash") for item in responses],
            "target": "global.tax_rate",
            "outcome": "global.gdp",
        }
    ).removeprefix("sha256:")[:20]
    fixture_id = f"synthetic_annual_gdp_tax_n4_{identity_seed}"
    controlled.update(
        {
            "design_problem_id": problem.design_problem_id,
            "fixture_id": fixture_id,
            "recording_id": fixture_id,
            "recording_source": "synthetic_annual_gdp_tax_overlay_of_recorded_capture",
        }
    )
    controlled["recording_content_hash"] = gy_content_hash(
        {key: value for key, value in controlled.items() if key != "recording_content_hash"}
    )
    n4_contract._validate_recording_fixture(controlled)

    stage_parents = {
        "draft": ("draft", selected_stage_parents["draft"]),
        "drafter_multipass": ("drafter_multipass", selected_stage_parents["drafter_multipass"]),
        "drafter_consolidation": ("draft", selected_stage_parents["draft"]),
        "formalizer": (
            "formalizer",
            acquisition_chain._SERVED_WDI_STAGE_PARENTS["formalizer"][1],
        ),
        "critic": ("critic", selected_stage_parents["critic"]),
    }
    provider_rows: list[tuple[str, str]] = []
    for stage, (parent_role, parent_hash) in stage_parents.items():
        matches = [
            (source_row, response)
            for source_row, response in zip(source_responses, responses, strict=True)
            if source_row.get("role") == parent_role
            and source_row.get("raw_response_hash") == parent_hash
        ]
        if len(matches) != 1:
            raise ValueError("annual_gdp_candidate_provider_parent_identity_unresolved")
        source_row, response = matches[0]
        if (
            source_row.get("status") != "success"
            or response.get("status") != "success"
            or source_row.get("model_id") != source_recording.get("model_id")
            or response.get("model_id") != source_recording.get("model_id")
            or gy_content_hash(source_row.get("raw_response")) != parent_hash
            or gy_content_hash(response.get("raw_response")) != response.get("raw_response_hash")
        ):
            raise ValueError("annual_gdp_candidate_provider_parent_content_mismatch")
        row = {
            "status": response["status"],
            "source_model_id": source_recording["model_id"],
            "raw_response": response["raw_response"],
            "raw_response_hash": response["raw_response_hash"],
            "usage": {
                **_DECLARED_STAGE_USAGE,
                "usage_status": "known",
            },
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
    )
    if (
        provider.profile_selection_ref != profile.profile_selection_ref
        or provider.controlled_recording_content_hash != controlled["recording_content_hash"]
    ):
        raise ValueError("annual_gdp_candidate_provider_profile_binding_mismatch")
    return controlled, provider


def _replace_recording_response(
    response: dict[str, Any],
    body: dict[str, Any],
) -> None:
    """Serialize one controlled stage body and bind its new content hash."""
    from polisyos.pdc import gy_content_hash

    raw_response = json.dumps(body, sort_keys=True, separators=(",", ":"))
    response["raw_response"] = raw_response
    response["raw_response_hash"] = gy_content_hash(raw_response)
