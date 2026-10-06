"""Ordinary registry update and persisted report keep quantity availability.

The caller supplies a complete two-axis conditional fixture basis. This probes
its actual producer/projection/readback chain, not an external candidate universe
or an institutional metric-source authorization.
"""

import math
from fractions import Fraction

import pytest

from polisyos.core.artifacts import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.methods.search.pareto_registry import ParetoBasisScope, ParetoRegistry
from polisyos.scientist.policy_design.objectives import (
    ObjectiveChannelValue,
    ObjectiveDirection,
    ObjectiveKind,
    PolicyEvaluationVector,
)
from polisyos.scientist.policy_design.output import (
    PolicyArtifactBuilder,
    PolicyArtifactBuildInput,
    load_policy_frontier_report,
    persist_policy_frontier_report,
)
from polisyos.scientist.policy_design.schema import (
    PolicyCandidateSchema,
    TargetPopulationSpec,
    persist_policy_candidate_schema,
)

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("quantity", ["underflow", "genuine_zero"])
def test_ordinary_registry_update_and_fresh_report_preserve_quantity_assessment(tmp_path, quantity):
    cas_root = tmp_path / "cas"
    store = FileSystemCAS(cas_root)
    data_ref = store.put_json(
        {"fixture": "conditional-two-axis-quantity"},
        ArtifactWriteOptions(kind="synthetic.data", media_type="application/json"),
    )
    bundle = TrinityBundle(
        problem_frame=ProblemFrame(problem_id="quantity_problem", domain=ProblemDomain.FISCAL),
        policy_spec=PolicySpec(policy_id="quantity_policy"),
        model_spec=ModelSpec(
            model_id="quantity_model", data_snapshot_ref=str(data_ref.artifact_id)
        ),
    )
    registry_root = tmp_path / "registry"
    registry = ParetoRegistry(root=registry_root)
    basis = ParetoBasisScope(
        scope="declared",
        coordinate_ids=["policy_value", "employment"],
        basis_ref="test:conditional-two-axis-quantity.v1",
    )
    candidates = []
    for index, value in enumerate((1e-200, 2e-200) if quantity == "underflow" else (1e-200,) * 2):
        candidate = PolicyCandidateSchema(
            candidate_id=f"quantity_candidate_{index}",
            trinity_bundle=bundle,
            target_population=TargetPopulationSpec(
                population_id="quantity_population", description="Conditional numeric fixture"
            ),
        )
        candidate_ref = persist_policy_candidate_schema(store, candidate)
        candidate_hash = str(candidate_ref.artifact_id)
        vector = PolicyEvaluationVector(
            candidate_id=candidate.candidate_id,
            primary={
                name: ObjectiveChannelValue(
                    name=name,
                    kind=ObjectiveKind.PRIMARY,
                    value=value,
                    direction=ObjectiveDirection.MINIMIZE,
                )
                for name in ("policy_value", "employment")
            },
        )
        registry.update(
            "ordinary-quantity",
            candidate_hash=candidate_hash,
            candidate_id=candidate.candidate_id,
            candidate_ref=candidate_ref,
            evaluation=vector,
            objective_basis_by_view={"global_feasible": basis},
        )
        candidates.append((candidate, candidate_ref, vector))
    snapshot = ParetoRegistry(root=registry_root).get_snapshot("ordinary-quantity")
    assessment = snapshot.hypervolume_assessments["global_feasible"]
    projection = snapshot.project_view("global_feasible")
    assert projection.assessment.status == "complete"
    assert projection.assessment.input_count == projection.assessment.assessed_count == 2
    expected_hashes = (
        [str(candidates[0][1].artifact_id)]
        if quantity == "underflow"
        else sorted(str(ref.artifact_id) for _, ref, _ in candidates)
    )
    assert sorted(projection.ranked_frontier_hashes) == sorted(expected_hashes)
    if quantity == "underflow":
        exact = math.prod([Fraction.from_float(2e-200) - Fraction.from_float(1e-200)] * 2)
        assert exact > 0 and float(exact) == 0.0
        assert snapshot.hypervolume_by_view["global_feasible"] is None
        assert assessment.status == "unavailable"
        assert assessment.reason == "nonzero_derived_hypervolume_underflow"
    else:
        assert snapshot.hypervolume_by_view["global_feasible"] == 0.0
        assert assessment.status == "available" and assessment.reason is None
    candidate, candidate_ref, vector = candidates[0]
    source = PolicyArtifactBuildInput(
        loop_id="ordinary-quantity",
        run_id="conditional-quantity-run",
        candidate=candidate,
        candidate_hash=str(candidate_ref.artifact_id),
        candidate_ref=candidate_ref,
        evaluation_vector=vector,
        pareto_snapshot=snapshot,
    )
    report = PolicyArtifactBuilder()._build_frontier_report(source)
    report_ref = persist_policy_frontier_report(store, report)
    reopened = load_policy_frontier_report(FileSystemCAS(cas_root), report_ref)
    assert sorted(entry.candidate_hash for entry in reopened.global_frontier) == sorted(
        expected_hashes
    )
    assert reopened.candidate_frontier == []
    assert (
        reopened.metadata["hypervolume_by_view"]["global_feasible"]
        == (snapshot.hypervolume_by_view["global_feasible"])
    )
    assert reopened.metadata["hypervolume_assessments"]["global_feasible"] == (
        assessment.model_dump(mode="json")
    )
    assert reopened.view_projections["global_feasible"] == projection
    print(
        "ordinary_quantity_consumer",
        {
            "quantity": quantity,
            "candidate_refs": [ref.model_dump(mode="json") for _, ref, _ in candidates],
            "input_count": projection.assessment.input_count,
            "registry_value": snapshot.hypervolume_by_view["global_feasible"],
            "registry_assessment": assessment.model_dump(mode="json"),
            "report_ref": report_ref.model_dump(mode="json"),
            "reopened_metadata": reopened.metadata,
            "ranked_hashes": expected_hashes,
        },
    )
