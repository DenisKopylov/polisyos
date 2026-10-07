"""Shared controlled candidate-scenario inputs for served N4→N5 tests.

The fixture remains candidate-only: the replay changes one integer parameter and
records its exact target/outcome path; the configured model is a declared synthetic
SCM and does not establish empirical grounding, source time, S8, or N9 authority.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from polisyos.ir.artifacts import ArtifactStore
from polisyos.runtime.quality.design_problem import (
    DESIGN_PROBLEM_CURRENT_SCHEMA_VERSION,
)
from tools.quality.validation import (
    check_layer3_gy_design_generation_contract as n4_contract,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _current_compiler_problem(recording: dict[str, object]):
    """Build honest current-schema compiler arguments without rewriting replay bytes."""

    historical = n4_contract._design_problem(recording)
    source_text = "all proposals remain candidate-only"
    assert source_text in historical.nl_provenance.raw_request
    constraints = [
        constraint.model_copy(
            update={
                "description": "All proposals remain candidate-only.",
                "source_text": source_text,
            }
        )
        if constraint.constraint_id == "no_authority_without_a"
        else constraint
        for constraint in historical.constraints
    ]
    return historical.model_copy(
        update={
            "schema_version": DESIGN_PROBLEM_CURRENT_SCHEMA_VERSION,
            "constraints": constraints,
        }
    )


def _controlled_procurement_recording(
    recording: dict[str, object], *, outcome_variable: str, intensity: int = 1
) -> dict[str, object]:
    """Keep the real N4 replay path while making its one direct value integer-only."""

    from polisyos.pdc import gy_content_hash

    controlled = copy.deepcopy(recording)
    responses = controlled.get("responses")
    assert isinstance(responses, list)
    for index in (4, 8):
        response = responses[index]
        assert isinstance(response, dict)
        raw = response.get("raw_response")
        assert isinstance(raw, str)
        trinity = json.loads(raw)
        interventions = trinity["policy_spec"]["interventions"]
        procurement = next(
            item
            for item in interventions
            if item.get("kind") == "procurement_shock_intensity"
        )
        procurement["params"] = {"intensity": intensity}
        procurement["notes"] = [
            "do.target=cells.distress_score sign=decrease "
            f"outcome={outcome_variable} "
            f"effect_path=cells.distress_score,{outcome_variable}"
        ]
        rewritten = json.dumps(trinity, sort_keys=True, separators=(",", ":"))
        response["raw_response"] = rewritten
        response["raw_response_hash"] = gy_content_hash(rewritten)
    return controlled


def _candidate_only_procurement_intervention_bundle():
    """Build a test-only, explicitly synthetic L6-shaped input for candidate N5.

    This fixture is deliberately not a production L6 manifest or evidence of a
    mechanism's empirical meaning. It supplies only the typed link needed for
    the synthetic candidate profile's single write slot.
    """

    from polisyos.ir.kernel.slots import DEFAULT_SLOT_REGISTRY, build_slot_family_manifest
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.quality.intervention_substrate import (
        replace_intervention_substrate_bundle,
    )
    from tests.unit.runtime.quality.test_cycle_substrate import _intervention_bundle

    fixture_identity = {
        "purpose": "candidate_only_synthetic_ncm_reentry_test",
        "operator_kind": "procurement_shock_intensity",
        "target_world_slot": "cells.distress_score",
    }
    owner_manifest_path = (
        REPO_ROOT
        / "architecture/policy_design_case/layer3_gy_l6_owner_authority_bindings.json"
    )
    owner_manifest = json.loads(owner_manifest_path.read_text(encoding="utf-8"))
    owner_mechanism = owner_manifest["world_mechanism_manifest"]["mechanisms"][
        "procurement_shock_intensity"
    ]
    candidate_slot_registry = DEFAULT_SLOT_REGISTRY.model_copy(
        update={
            "slots": {
                "cells.distress_score": DEFAULT_SLOT_REGISTRY.slots[
                    "cells.distress_score"
                ]
            }
        }
    )
    fixture_payloads = {
        "knob_dictionary": {
            "procurement_shock_intensity": {
                "type": "float",
                "default": 0.0,
                "min": -1.0,
                "max": 1.0,
                "mechanism_id": "procurement_shock_intensity",
                "param_path": "params.intensity",
            }
        },
        "world_mechanism_manifest": {
            "schema_version": owner_manifest["world_mechanism_manifest"][
                "schema_version"
            ],
            "mechanisms": {"procurement_shock_intensity": owner_mechanism},
        },
        "slot_family_manifest": build_slot_family_manifest(
            candidate_slot_registry
        ).model_dump(mode="json"),
    }
    source_names = {
        "knob_dictionary": "candidate_knob",
        "world_mechanism_manifest": "candidate_mechanism",
        "slot_family_manifest": "candidate_slot",
    }
    base_bundle = _intervention_bundle()
    return replace_intervention_substrate_bundle(
        base_bundle,
        update={
            **fixture_payloads,
            "source_refs": {
                name: f"test-fixture://{fixture_identity['purpose']}/{label}"
                for name, label in source_names.items()
            },
            "source_content_hashes": {
                source_name: gy_content_hash(
                    {**fixture_identity, "payload": fixture_payloads[field_name]}
                )
                for field_name, source_name in source_names.items()
            },
        },
    )


def _configured_procurement_profile(
    *,
    recorded_problem: object,
    artifact_store: ArtifactStore,
    tenant_id: str,
    cell_id: str,
    outcome_per_target_unit: float = 0.5,
    intervention_substrate: object | None = None,
):
    """Return a configured candidate profile and its explicit synthetic SCM."""

    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.ir.analytics.ncm import (
        ExogenousSpec,
        NCMSpec,
        StructuralEquation,
        persist_ncm_spec,
    )
    from polisyos.pdc import gy_content_hash, world_model_record_content_hash
    from polisyos.runtime.quality.candidate_simulation import (
        CandidateScenarioN5Config,
        CandidateScenarioSetToRule,
        CandidateSimulationContextInputs,
        CandidateSimulationScenarioProfile,
        CandidateSimulationSyntheticModelDeclarationV1,
        candidate_simulation_profile_ref,
    )
    from polisyos.runtime.quality.cycle_substrate import (
        cycle_job_profile_selection_ref,
    )
    from polisyos.runtime.quality.generation_cycle import (
        _build_boundary_world_model_record,
    )
    from polisyos.runtime.quality.intervention_substrate import (
        load_l6_intervention_substrate,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import HorizonSpec
    from tests.unit.runtime.quality.test_generation_cycle import (
        _cyc01_owner_bound_n5_case,
        _record_with_selected_ncm_ref,
    )

    base_problem, base_context, _candidate = _cyc01_owner_bound_n5_case(
        problem_seed=recorded_problem
    )
    outcome_variable = recorded_problem.outcome_of_interest.target_variable
    ncm = NCMSpec(
        endogenous_vars=["cells.distress_score", outcome_variable],
        exogenous_specs=[
            ExogenousSpec(
                variable="u_distress",
                associated_endogenous="cells.distress_score",
                distribution_params={"mean": 0.0, "std": 0.01},
            ),
            ExogenousSpec(
                variable="u_output",
                associated_endogenous=outcome_variable,
                distribution_params={"mean": 0.0, "std": 0.01},
            ),
        ],
        structural_equations=[
            StructuralEquation(
                variable="cells.distress_score",
                parents=[],
                exogenous="u_distress",
                equation_type="linear",
                equation_params={"intercept": 0.0, "coefficients": {}},
            ),
            StructuralEquation(
                variable=outcome_variable,
                parents=["cells.distress_score"],
                exogenous="u_output",
                equation_type="linear",
                equation_params={
                    "intercept": 0.0,
                    "coefficients": {
                        "cells.distress_score": outcome_per_target_unit
                    },
                },
            ),
        ],
        is_acyclic=True,
        markov_condition_verified=True,
        independence_model="dag_markov",
        fit_method="synthetic_candidate_profile_fixture",
    )
    with tenant_scope(
        None,
        tenant_id=tenant_id,
        cell_id=cell_id,
    ):
        ncm_ref = persist_ncm_spec(artifact_store, ncm)

    candidate_slots = tuple(
        dict.fromkeys(
            [
                lever.target_slot
                for lever in recorded_problem.candidate_lever_space.candidate_levers
            ]
            + ["global.tax_rate", "cells.distress_score", outcome_variable]
        )
    )
    world = _build_boundary_world_model_record(
        repo_root=REPO_ROOT,
        problem=base_problem,
        outcome=outcome_variable,
        policy_slot_ids=candidate_slots,
        substrate_registry=base_context.substrate_registry,
        selected_registry_entry_hashes=base_context.selected_registry_entry_hashes,
    )
    bindings = tuple(
        item.model_copy(update={"unit": "synthetic_score"})
        for item in world.policy_slot_map
    )
    foundry = world.foundry_binding_ref.model_copy(
        update={
            "state_slot_digest": gy_content_hash(
                {
                    "boundary": "state_slots",
                    "slots": [item.model_dump(mode="json") for item in bindings],
                }
            )
        }
    )
    draft = world.model_copy(update={"policy_slot_map": bindings, "foundry_binding_ref": foundry})
    world = draft.model_copy(
        update={
            "content_hash": world_model_record_content_hash(draft),
            "world_model_record_id": (
                "world_model_record_"
                + world_model_record_content_hash(draft).removeprefix("sha256:")[:16]
            ),
        }
    )
    world = _record_with_selected_ncm_ref(world, str(ncm_ref.artifact_id))
    if intervention_substrate is None:
        intervention_substrate = load_l6_intervention_substrate(REPO_ROOT)
    context_inputs = CandidateSimulationContextInputs(
        substrate_registry=base_context.substrate_registry,
        selected_registry_entry_hashes=base_context.selected_registry_entry_hashes,
        world_model_record=world,
        intervention_substrate=intervention_substrate,
        source_pack_content_hash=base_context.source_pack_content_hash,
        substrate_input_content_hash=base_context.substrate_input_content_hash,
    )
    rule = CandidateScenarioSetToRule(
        operator_kind="procurement_shock_intensity",
        parameter_id="intensity",
        target_world_slot="cells.distress_score",
        unit_id="synthetic_score",
        minimum=0,
        maximum=1,
    )
    n5 = CandidateScenarioN5Config(
        budget_ref="budget://r1/controlled-candidate-n5",
        horizon=HorizonSpec(start=0, end=0, step=1),
        baseline_state={"cells.distress_score": 0.0, outcome_variable: 0.0},
        seed=11,
        replications=2,
    )
    fields = {
        "schema_version": "policyos.runtime.candidate_simulation_profile.v2",
        "profile_id": "r1.controlled.synthetic.procurement",
        "profile_selection_ref": cycle_job_profile_selection_ref(recorded_problem),
        "context_inputs": context_inputs,
        "rule": rule,
        "n5": n5,
        "limitations": (
            "scenario_only",
            "real_profile_not_established",
            "real_time_not_established",
            "grounding_not_established",
            "s8_blocked",
            "n9_not_admitted",
        ),
    }
    draft_profile = CandidateSimulationScenarioProfile.model_construct(
        **fields,
        content_hash="sha256:" + "0" * 64,
    )
    profile = CandidateSimulationScenarioProfile.model_validate(
        {
            **fields,
            "content_hash": gy_content_hash(
                draft_profile.model_dump(mode="json", exclude={"content_hash"})
            ),
        }
    )
    declaration_fields = {
        "schema_version": (
            "policyos.runtime.candidate_simulation.synthetic_model_declaration.v1"
        ),
        "profile_config_ref": candidate_simulation_profile_ref(profile),
        "profile_content_hash": profile.content_hash,
        "profile_selection_ref": profile.profile_selection_ref,
        "target_world_slot": rule.target_world_slot,
        "outcome_variable": outcome_variable,
        "target_unit_id": rule.unit_id,
        "outcome_unit_id": rule.unit_id,
        "target_baseline": 0.0,
        "outcome_baseline": 0.0,
        "outcome_per_target_unit": outcome_per_target_unit,
        "outcome_noise_stddev": 0.01,
        "assumption": "declared_candidate_scm_not_empirically_grounded",
    }
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
