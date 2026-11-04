"""Exercise an authored candidate compound through the actual NCM and CAS reader."""

from __future__ import annotations

import math
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

import polisyos.runtime.quality.recursive_generation_cycle as recursive_cycle
from polisyos.core.artifacts import ArtifactRef, FileSystemCAS, read_core_json_artifact
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.pdc import gy_artifact_self_identity_projection, gy_content_hash
from polisyos.runtime.quality.generation_cycle import (
    GenerationCycleError,
    load_joint_simulation_result,
)
from polisyos.runtime.quality.joint_simulation_horizon import JointSimulationHorizonController
from tests.unit.remediation import test_cyc05_authored_relation as authored_witness

controlled_candidate_gateway = authored_witness.controlled_candidate_gateway


def _declared_joint_polynomial_profile(**kwargs: Any) -> dict[str, Any]:
    """Construct a selected candidate model using the existing artifact owners.

    The polynomial is y=baseline+u+0.4*d+1.6*d², d=a+1.25*b. For binary
    interventions it has the SIM-03 single/joint effects 2, 3 and 9. It also
    has a 4*a*b cross-term for the actual source-selected scalar values.
    """
    from polisyos.core.artifacts import ArtifactRef, ensure_ir_artifact_store
    from polisyos.ir.analytics.ncm import (
        ExogenousSpec,
        NCMSpec,
        StructuralEquation,
        persist_ncm_spec,
    )
    from polisyos.runtime.quality.generic_simulation_admission import GenericCycleN5RequestProfileV3
    from polisyos.runtime.quality.world_model_record import world_model_artifact_views
    from tests._helpers.controlled_candidate_profile import (
        _controlled_direct_ncm_outcome_state_paths,
        _materialize_controlled_world_model_build,
    )

    profiles = kwargs["child_profiles"]
    assert len(profiles) == 2
    first = profiles[0]
    rules = tuple(rule for profile in profiles for rule in profile.n5.component_rules)
    targets = tuple(rule.target_world_slot for rule in rules)
    assert len(targets) == len(set(targets)) == 2
    outcomes = set.intersection(*(set(profile.n5.baseline_state) for profile in profiles)) - set(
        targets
    )
    assert len(outcomes) == 1
    outcome = next(iter(outcomes))
    baseline = dict.fromkeys(targets, 0.0)
    baseline[outcome] = float(first.n5.baseline_state[outcome])
    expression = (
        f"u + {baseline[outcome]!r} + 0.4*(deterministic - {baseline[outcome]!r}) "
        f"+ 1.6*(deterministic - {baseline[outcome]!r})**2"
    )
    spec = NCMSpec(
        endogenous_vars=[*targets, outcome],
        exogenous_specs=[
            ExogenousSpec(
                variable=f"U_{variable}",
                associated_endogenous=variable,
                distribution_params={"mean": 0.0, "std": 0.01 if variable == outcome else 0.0},
            )
            for variable in (*targets, outcome)
        ],
        structural_equations=[
            StructuralEquation(
                variable=target,
                exogenous=f"U_{target}",
                equation_type="linear",
                equation_params={"intercept": 0.0, "coefficients": {}},
            )
            for target in targets
        ]
        + [
            StructuralEquation(
                variable=outcome,
                parents=list(targets),
                exogenous=f"U_{outcome}",
                equation_type="nonlinear",
                equation_params={
                    "intercept": baseline[outcome],
                    "coefficients": {targets[0]: 1.0, targets[1]: 1.25},
                    "noise_expression": expression,
                },
            )
        ],
        is_acyclic=True,
        fit_method="declared_joint_polynomial_candidate_fixture_not_empirical",
    )
    with tenant_scope(None, tenant_id=kwargs["tenant_id"], cell_id=kwargs["cell_id"]):
        ncm_ref = ArtifactRef.model_validate(
            persist_ncm_spec(ensure_ir_artifact_store(kwargs["store"]), spec).model_dump(
                mode="python"
            )
        )
    source_model = first.context_inputs.world_model_record
    views = world_model_artifact_views(source_model)
    units = {slot.slot_id: slot.unit for slot in source_model.policy_slot_map}
    declared_units = {rule.target_world_slot: rule.unit_id for rule in rules}
    declared_units[outcome] = units[outcome]
    built = _materialize_controlled_world_model_build(
        source_world_model_record=source_model,
        artifact_store=kwargs["store"],
        tmp_path=kwargs["tmp_path"] / "declared-polynomial-joint-model",
        source_root=kwargs["source_root"],
        substrate_registry=first.context_inputs.substrate_registry,
        selected_registry_entry_hashes=first.context_inputs.selected_registry_entry_hashes,
        substrate_registry_ref=views.substrate_registry_ref,
        policy_slot_ids=tuple(
            dict.fromkeys(
                [*(slot.slot_id for slot in source_model.policy_slot_map), *targets, outcome]
            )
        ),
        selected_skg_source=kwargs["selected_skg_source"],
        tenant_id=kwargs["tenant_id"],
        cell_id=kwargs["cell_id"],
        ncm_view_refs=(ncm_ref,),
        candidate_baseline_state=baseline,
        candidate_outcome_state_paths=_controlled_direct_ncm_outcome_state_paths(outcome),
        candidate_model_unit_ids=declared_units,
    )
    n5_fields = first.n5.model_dump(
        mode="python", exclude={"schema_version", "component_rules", "ncm_plan_refs"}
    )
    n5_fields["baseline_state"] = baseline
    return {
        **kwargs["root_fields"],
        "world_model_record_ref": built.record_ref,
        "selected_ncm_ref": ncm_ref,
        "context_inputs": first.context_inputs.model_copy(
            update={"world_model_record": built.record}
        ),
        "n5": GenericCycleN5RequestProfileV3(
            **n5_fields, ncm_plan_refs=(ncm_ref,), component_rules=rules
        ),
    }


@pytest.mark.asyncio
async def test_authored_compound_runs_real_joint_ncm_and_fresh_selected_reader(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    controlled_candidate_gateway: Any,
) -> None:
    """A source-selected two-component candidate runs its declared additive SCM.

    This reuses the real NL worker, relation writer, and source/selection
    controls. The observers call the unmodified numerical owner and persistence
    path. The declared model is a toy candidate, not empirical coupling.
    """
    from fastapi.testclient import TestClient

    from polisyos.runtime.http.security import build_fixture_identity_claims
    from polisyos.runtime.http.services.control.generation_cycle import (
        CompiledRecursiveGenerationCycleRun,
    )
    from tests._helpers import generic_n4_served_replay

    authored_inputs: list[dict[str, Any]] = []
    writes: list[tuple[Any, Any, Any]] = []
    served: list[dict[str, Any]] = []
    original_authored = recursive_cycle.persist_authored_joint_components
    original_persist = recursive_cycle.persist_joint_simulation_result
    original_get = TestClient.get

    def observe_authored(**kwargs: Any) -> Any:
        result = original_authored(**kwargs)
        authored_inputs.append(kwargs)
        return result

    def observe_persist(result: Any, **kwargs: Any) -> Any:
        ref = original_persist(result, **kwargs)
        writes.append((result, ref, kwargs["store"]))
        return ref

    def observe_get(client: Any, *args: Any, **kwargs: Any) -> Any:
        response = original_get(client, *args, **kwargs)
        if args and str(args[0]).startswith("/api/v1/runs/") and response.status_code == 200:
            served.append(response.json())
        return response

    monkeypatch.setattr(recursive_cycle, "persist_authored_joint_components", observe_authored)
    monkeypatch.setattr(recursive_cycle, "persist_joint_simulation_result", observe_persist)
    monkeypatch.setattr(TestClient, "get", observe_get)
    monkeypatch.setattr(
        generic_n4_served_replay,
        "_declared_additive_joint_root_fields",
        _declared_joint_polynomial_profile,
    )
    await (
        authored_witness.test_authored_joint_relation_replays_real_source_request_and_selected_cas(
            tmp_path, monkeypatch, controlled_candidate_gateway
        )
    )

    assert len(authored_inputs) == 1
    (selected_inputs,) = authored_inputs
    request = selected_inputs["request"]
    requested_atoms = tuple(atom.intervention_id for atom in request.intervention_atoms)
    selected_writes = [
        (result, ref, store) for result, ref, store in writes if result.atom_ids == requested_atoms
    ]
    assert len(selected_writes) == 1
    produced, ref, writer = selected_writes[0]
    assert ref.manifest_profile_sha256
    assert len(served) == 1
    projection = served[0]["run"]["generic_cycle_simulation"]
    parent_rows = [
        row
        for row in projection["n5_observations"]
        if row.get("n8_selected_member_relationship") == "joint_components"
    ]
    assert len(parent_rows) == 1
    parent = parent_rows[0]
    assert parent["n8_source_candidate_relationship"] == "alternatives"
    assert parent["n8_policy_composition_status"] == "authored_candidate"
    assert parent["n8_child_to_parent_refinement_status"] == "not_established"
    assert parent["n8_policy_composition_limitation_code"] == (
        "authored_candidate_coupling_not_established"
    )

    claims = build_fixture_identity_claims()
    with tenant_scope(None, tenant_id=claims.tenant_id, cell_id=claims.cell_id):
        reader = FileSystemCAS(tmp_path / ".polisyos")
        assert reader is not writer
        reopened = load_joint_simulation_result(ref, store=reader, expected_request=request)
        compiled = CompiledRecursiveGenerationCycleRun.model_validate(
            read_core_json_artifact(
                reader, ArtifactRef.model_validate(projection["source_ref"])
            ).value
        )
    assert reopened.model_dump(mode="json") == produced.model_dump(mode="json")

    # Full-run validation rechecks the embedded node before folding: a supported
    # candidate lacking coupling cannot be relabeled as unsupported.
    run = compiled.recursive_run
    parent_node = next(node for node in run.nodes if node.joint_candidate_selection is not None)
    assert parent_node.node_ref == run.root_node_ref
    assert "observed_coupling_evidence_missing" in parent_node.terminal.blocking_obligations
    wrong_terminal = recursive_cycle._blocked_parent_terminal("unsupported_coupling_gated")
    wrong_parent = parent_node.model_copy(update={"terminal": wrong_terminal})
    assert recursive_cycle._fold_uncertified_joint_terminal(parent_node) == parent_node.terminal
    assert recursive_cycle._fold_uncertified_joint_terminal(wrong_parent) == parent_node.terminal
    wrong_nodes = tuple(wrong_parent if node is parent_node else node for node in run.nodes)
    wrong_run = run.model_copy(update={"nodes": wrong_nodes, "terminal": wrong_terminal})
    identity = gy_artifact_self_identity_projection(wrong_run)
    identity.pop("leaf_nodes", None)
    wrong_fields = {name: getattr(wrong_run, name) for name in type(wrong_run).model_fields}
    wrong_fields["content_hash"] = gy_content_hash(identity)
    with pytest.raises(
        ValueError, match="recursive_parent_joint_candidate_requires_blocked_composition"
    ):
        type(run).model_validate(wrong_fields)

    # The actual request observes both roots at zero and the outcome at its
    # baseline, so NCM abduction selects u=0. Independent rational arithmetic
    # checks the declared polynomial; it is not a statement about real causality.
    assert len(request.intervention_atoms) == 2
    materializations = selected_inputs["component_materializations"]
    assert tuple(item.derived_n5_atom for item in materializations) == request.intervention_atoms
    for materialization in materializations:
        slot = request.world_model_record.slot_binding(materialization.target_world_slot)
        assert slot is not None and slot.unit == materialization.unit_id
    (plan,) = request.engine_plan
    assert plan.engine_kind == "ncm_parallel_worlds"
    assert plan.ncm_spec is not None
    (outcome,) = request.selected_outcomes
    outcome_variable = plan.variable_map.get(outcome, outcome)
    equation = next(e for e in plan.ncm_spec.structural_equations if e.variable == outcome_variable)
    assignments: list[tuple[str, Fraction]] = []
    for atom in request.intervention_atoms:
        (assignment,) = atom.causal_do_expr.assignments
        assert assignment.value is not None
        variable = plan.variable_map.get(assignment.variable, assignment.variable)
        assignments.append((variable, Fraction(str(assignment.value))))
    assert len({variable for variable, _ in assignments}) == 2
    assert set(equation.parents) == {variable for variable, _ in assignments}
    assert equation.equation_type == "nonlinear"
    assert equation.equation_params["coefficients"] == {
        assignments[0][0]: 1.0,
        assignments[1][0]: 1.25,
    }
    baseline = float(request.baseline_state[outcome])
    assert float(equation.equation_params["intercept"]) == baseline
    assert all(float(request.baseline_state[variable]) == 0.0 for variable, _ in assignments)
    assert request.evidence_state is None  # The existing legacy baseline-evidence profile.

    atom_ids = tuple(atom.intervention_id for atom in request.intervention_atoms)
    expected_seeds = tuple(range(request.seed, request.seed + request.replications))
    a, b = (value for _, value in assignments)
    assert a != 0 and b != 0
    effect_a = Fraction(2, 5) * a + Fraction(8, 5) * a * a
    effect_b = Fraction(1, 2) * b + Fraction(5, 2) * b * b
    interaction = 4 * a * b
    # Cover this small binary64 fixture even when its declared baseline is zero.
    magnitude = max(1.0, abs(baseline), abs(baseline + float(effect_a + effect_b + interaction)))
    tolerance = 8 * math.ulp(magnitude)
    for level, ids, expected_delta in (
        ("individual", atom_ids[:1], effect_a),
        ("individual", atom_ids[1:], effect_b),
        ("joint", atom_ids, effect_a + effect_b + interaction),
    ):
        trajectory = reopened.trajectory_for(level, ids)
        (point,) = trajectory.points
        assert point.replication_sampling is not None
        assert point.replication_sampling.seeds == expected_seeds
        for sample in point.replication_sampling.samples:
            assert math.isclose(
                sample.outcomes[outcome],
                baseline + float(expected_delta),
                rel_tol=0.0,
                abs_tol=tolerance,
            )

    pair = reopened.trajectory_for("pairwise", atom_ids)
    joint = reopened.trajectory_for("joint", atom_ids)
    assert pair.diagnostics["physical_run_ref"] == joint.diagnostics["physical_run_ref"]
    (interaction_term,) = reopened.interaction_terms
    assert set(interaction_term.atom_ids) == set(atom_ids)
    assert math.isclose(
        interaction_term.by_step[request.horizon.start],
        float(interaction),
        rel_tol=0.0,
        abs_tol=tolerance,
    )
    assert reopened.feedback_classification.numeric_interaction == "unsupported"
    assert reopened.diagnostics["effect_basis_status"] == "not_established"

    # Removing one selected component must change the actual numerical case;
    # the fresh selected reader must not bind the old compound to that case.
    one_component = type(request).model_validate(
        {**request.model_dump(mode="python"), "intervention_atoms": request.intervention_atoms[:1]}
    )
    removed = JointSimulationHorizonController().run(one_component)
    (point,) = removed.trajectory_for("joint", atom_ids[:1]).points
    assert math.isclose(
        point.outcomes[outcome],
        baseline + float(effect_a),
        rel_tol=0.0,
        abs_tol=tolerance,
    )
    assert not math.isclose(
        point.outcomes[outcome],
        joint.points[0].outcomes[outcome],
        rel_tol=0.0,
        abs_tol=tolerance,
    )
    with (
        tenant_scope(None, tenant_id=claims.tenant_id, cell_id=claims.cell_id),
        pytest.raises(
            GenerationCycleError, match="joint_simulation_result_execution_binding_invalid"
        ),
    ):
        load_joint_simulation_result(ref, store=reader, expected_request=one_component)
