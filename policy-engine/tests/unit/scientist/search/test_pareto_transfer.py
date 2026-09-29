from __future__ import annotations

import json
import math
from decimal import Decimal

import pytest

from polisyos.ir.governance.policy_spec import InterventionSpec, ParameterSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ObjectiveSpec, ProblemDomain, ProblemFrame
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.model_layer.types import OptimizationDirection, SelectorOperator
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.methods.search.contracts import (
    ParetoBasisScope,
    ParetoViewAssessment,
)
from polisyos.scientist.methods.search.pareto_registry import ParetoRegistry, ParetoView
from polisyos.scientist.methods.search.transfer_context import TransferContext
from polisyos.scientist.policy_design.objectives import (
    ConstraintStatus,
    ObjectiveChannelValue,
    ObjectiveDirection,
    ObjectiveKind,
    PolicyEvaluationVector,
)
from polisyos.scientist.policy_design.schema import PolicyCandidateSchema, TargetPopulationSpec


def _candidate() -> PolicyCandidateSchema:
    return PolicyCandidateSchema(
        candidate_id="candidate_policy",
        trinity_bundle=TrinityBundle(
            problem_frame=ProblemFrame(
                problem_id="problem_policy",
                domain=ProblemDomain.FISCAL,
                objectives=[
                    ObjectiveSpec(
                        objective_id="welfare",
                        metric_id="welfare_metric",
                        direction=OptimizationDirection.MAXIMIZE,
                    )
                ],
            ),
            policy_spec=PolicySpec(
                policy_id="policy_policy",
                interventions=[
                    InterventionSpec(
                        intervention_id="tax_cut",
                        kind="tax_policy",
                        target={
                            "kind": "predicate",
                            "field": "id",
                            "operator": SelectorOperator.EQUALS,
                            "value": "all",
                        },
                        schedule={"start_step": 0, "duration_steps": 2},
                        params={"rate": Decimal("0.1")},
                    )
                ],
                parameters=[
                    ParameterSpec(
                        param_id="tax_rate",
                        intervention_id="tax_cut",
                        param_path="rate",
                        default_value=Decimal("0.1"),
                    )
                ],
            ),
            model_spec=ModelSpec(
                model_id="model_policy",
                data_snapshot_ref="sha256:" + "1" * 64,
            ),
        ),
        target_population=TargetPopulationSpec(
            population_id="population_policy",
            description="General population",
            geography="national",
        ),
        metadata={"policy_family": "core_family"},
    )


def _evaluation_vector(candidate: PolicyCandidateSchema) -> PolicyEvaluationVector:
    return PolicyEvaluationVector(
        candidate_id=candidate.candidate_id,
        primary={
            "policy_value": ObjectiveChannelValue(
                name="policy_value",
                kind=ObjectiveKind.PRIMARY,
                value=1.2,
                direction=ObjectiveDirection.MAXIMIZE,
            ),
            "welfare": ObjectiveChannelValue(
                name="welfare",
                kind=ObjectiveKind.PRIMARY,
                value=1.0,
                direction=ObjectiveDirection.MAXIMIZE,
            ),
            "employment": ObjectiveChannelValue(
                name="employment",
                kind=ObjectiveKind.PRIMARY,
                value=0.5,
                direction=ObjectiveDirection.MAXIMIZE,
            ),
        },
        hard_constraints={
            "policy_budget_constraint": ObjectiveChannelValue(
                name="policy_budget_constraint",
                kind=ObjectiveKind.HARD_CONSTRAINT,
                value=0.95,
                direction=ObjectiveDirection.MINIMIZE,
                threshold=1.0,
                status=ConstraintStatus.NEAR_BINDING,
            )
        },
        secondary={},
        penalties={},
        feasible=True,
        blocking_reasons=[],
        metadata={"policy_family": "core_family", "candidate_hash": candidate.candidate_hash()},
    )


def test_publish_transfer_surface_produces_seed_only_bundle(tmp_path) -> None:
    registry = ParetoRegistry(tmp_path / "registry")
    candidate = _candidate()
    evaluation = _evaluation_vector(candidate)
    source = TransferContext(
        task_family="policy",
        domain="fiscal",
        run_id="loop-source",
        tenant_hash="tenant-a",
    )
    target = TransferContext(
        task_family="policy",
        domain="labor",
        run_id="loop-target",
        tenant_hash="tenant-a",
    )

    registry.update(
        "loop-source",
        candidate_hash=candidate.candidate_hash(),
        evaluation=evaluation,
        candidate_id=candidate.candidate_id,
        policy_family="core_family",
        seed_payload=candidate.model_dump(mode="json"),
        transfer_context=source,
    )

    bundle = registry.get_seed_bundle(target, max_seeds=3)
    warm_start = registry.build_warm_start_evaluations(target, max_seeds=3)

    assert bundle.entries
    assert all(entry.seed_only for entry in bundle.entries)
    assert bundle.cross_domain_seed_count == 1
    assert warm_start
    assert warm_start[0]["metadata"]["seed_only"] is True
    assert registry.get_snapshot("loop-target").entries == {}


def test_same_domain_seed_sorting_precedes_cross_domain(tmp_path) -> None:
    registry = ParetoRegistry(tmp_path / "registry")
    candidate = _candidate()
    evaluation = _evaluation_vector(candidate)
    registry.update(
        "loop-fiscal",
        candidate_hash=f"{candidate.candidate_hash()}::fiscal",
        evaluation=evaluation.model_copy(update={"candidate_id": "candidate_fiscal"}),
        candidate_id="candidate_fiscal",
        policy_family="core_family",
        seed_payload=candidate.model_dump(mode="json"),
        transfer_context=TransferContext(
            task_family="policy",
            domain="fiscal",
            run_id="loop-fiscal",
            tenant_hash="tenant-a",
        ),
    )
    registry.update(
        "loop-labor",
        candidate_hash=f"{candidate.candidate_hash()}::labor",
        evaluation=evaluation.model_copy(update={"candidate_id": "candidate_labor"}),
        candidate_id="candidate_labor",
        policy_family="core_family",
        seed_payload=candidate.model_dump(mode="json"),
        transfer_context=TransferContext(
            task_family="policy",
            domain="labor",
            run_id="loop-labor",
            tenant_hash="tenant-a",
        ),
    )

    bundle = registry.get_seed_bundle(
        TransferContext(
            task_family="policy",
            domain="labor",
            run_id="loop-target",
            tenant_hash="tenant-a",
        ),
        max_seeds=5,
    )

    assert len(bundle.entries) >= 2
    assert bundle.entries[0].domain == "labor"


def test_unassessed_nonfinite_vector_is_retained_locally_but_not_transferred(tmp_path) -> None:
    registry = ParetoRegistry(tmp_path / "registry")
    candidate = _candidate()
    baseline = _evaluation_vector(candidate)
    evaluation = baseline.model_copy(
        update={
            "primary": {
                **baseline.primary,
                "policy_value": baseline.primary["policy_value"].model_copy(
                    update={"value": float("nan")}
                ),
            },
            "secondary": {
                **baseline.secondary,
                "unstated_quality": ObjectiveChannelValue(
                    name="unstated_quality",
                    kind=ObjectiveKind.SECONDARY,
                    value=float("inf"),
                    direction=ObjectiveDirection.MAXIMIZE,
                )
            },
            "penalties": {
                "negative_infinity": ObjectiveChannelValue(
                    name="negative_infinity",
                    kind=ObjectiveKind.PENALTY,
                    value=float("-inf"),
                    direction=ObjectiveDirection.MINIMIZE,
                )
            },
        }
    )
    source = TransferContext(
        task_family="policy",
        domain="fiscal",
        run_id="loop-nonfinite-source",
        tenant_hash="tenant-a",
    )
    target = TransferContext(
        task_family="policy",
        domain="labor",
        run_id="loop-nonfinite-target",
        tenant_hash="tenant-a",
    )
    candidate_hash = candidate.candidate_hash()

    registry.update(
        source.run_id,
        candidate_hash=candidate_hash,
        evaluation=evaluation,
        candidate_id=candidate.candidate_id,
        policy_family="core_family",
        seed_payload=candidate.model_dump(mode="json"),
        transfer_context=source,
    )

    local = registry.get_snapshot(source.run_id)
    snapshot_path = registry._snapshot_path(source.run_id)
    wire = json.loads(
        snapshot_path.read_text(encoding="utf-8"),
        parse_constant=lambda token: (_ for _ in ()).throw(
            ValueError(f"non-standard JSON numeric token: {token}")
        ),
    )
    wire_evaluation = wire["entries"][candidate_hash]["evaluation"]
    assert wire["schema_version"] == "2.1"
    assert wire_evaluation["primary"]["policy_value"]["value"] == {
        "$type": "raw_non_finite_objective_value",
        "kind": "nan",
    }
    assert wire_evaluation["secondary"]["unstated_quality"]["value"] == {
        "$type": "raw_non_finite_objective_value",
        "kind": "positive_infinity",
    }
    assert wire_evaluation["penalties"]["negative_infinity"]["value"] == {
        "$type": "raw_non_finite_objective_value",
        "kind": "negative_infinity",
    }
    assert candidate_hash in local.entries
    restored = local.entries[candidate_hash].evaluation
    assert math.isnan(restored.primary["policy_value"].value)
    assert restored.secondary["unstated_quality"].value == float("inf")
    assert restored.penalties["negative_infinity"].value == float("-inf")
    assert local.frontiers["global_feasible"] == []
    assert registry.get_seed_bundle(target, max_seeds=3).entries == []

    malformed_wire = json.loads(snapshot_path.read_text(encoding="utf-8"))
    malformed_wire["entries"][candidate_hash]["evaluation"]["secondary"][
        "unstated_quality"
    ]["value"]["kind"] = "not-a-supported-kind"
    snapshot_path.write_text(json.dumps(malformed_wire), encoding="utf-8")
    with pytest.raises(ValueError, match="raw non-finite objective value"):
        registry.get_snapshot(source.run_id)

    malformed_wire["entries"][candidate_hash]["evaluation"]["secondary"][
        "unstated_quality"
    ]["value"] = float("nan")
    snapshot_path.write_text(json.dumps(malformed_wire, allow_nan=True), encoding="utf-8")
    with pytest.raises(ValueError, match="non-standard JSON numeric token"):
        registry.get_snapshot(source.run_id)


def test_legacy_v2_frontier_is_reassessed_before_projection_and_transfer(tmp_path) -> None:
    registry = ParetoRegistry(tmp_path / "registry")
    candidate = _candidate()
    baseline = _evaluation_vector(candidate)
    evaluation = baseline.model_copy(
        update={
            "secondary": {
                **baseline.secondary,
                "legacy_nonfrontier_quality": ObjectiveChannelValue(
                    name="legacy_nonfrontier_quality",
                    kind=ObjectiveKind.SECONDARY,
                    value=0.5,
                    direction=ObjectiveDirection.MAXIMIZE,
                ),
            }
        }
    )
    source = TransferContext(
        task_family="policy",
        domain="fiscal",
        run_id="loop-legacy-v2",
        tenant_hash="tenant-a",
    )
    basis = ParetoBasisScope(
        scope="declared",
        coordinate_ids=["policy_value", "employment"],
        basis_ref="test:legacy-v2-rank-basis",
    )
    candidate_hash = candidate.candidate_hash()
    registry.update(
        source.run_id,
        candidate_hash=candidate_hash,
        evaluation=evaluation,
        candidate_id=candidate.candidate_id,
        policy_family="core_family",
        seed_payload=candidate.model_dump(mode="json"),
        transfer_context=source,
        objective_basis_by_view={"global_feasible": basis},
    )

    local_path = registry._snapshot_path(source.run_id)
    catalog_path = registry._catalog_path(source)
    for path, key in ((local_path, candidate_hash), (catalog_path, f"{source.run_id}:{candidate_hash}")):
        legacy = json.loads(path.read_text(encoding="utf-8"))
        legacy["schema_version"] = "2.0"
        legacy["frontiers"]["global_feasible"] = [key]
        legacy["view_assessments"]["global_feasible"] = ParetoViewAssessment(
            status="complete",
            coverage_status="complete",
            basis_scope=basis,
            input_count=1,
            assessed_count=1,
        ).model_dump(mode="json")
        entry = legacy["entries"][key]
        entry.pop("policy_evaluation_status", None)
        entry.pop("policy_evaluation_error", None)
        entry["evaluation"]["secondary"]["legacy_nonfrontier_quality"]["value"] = float(
            "nan"
        )
        path.write_text(json.dumps(legacy, allow_nan=True), encoding="utf-8")

    loaded = registry.get_snapshot(source.run_id)
    historical_payload = loaded.historical_v2_0_payload()
    assert loaded.schema_version == "2.0"
    assert "policy_evaluation_status" not in historical_payload["entries"][candidate_hash]
    assert math.isnan(
        historical_payload["entries"][candidate_hash]["evaluation"]["secondary"][
            "legacy_nonfrontier_quality"
        ]["value"]
    )
    historical_path = tmp_path / "historical-v2-snapshot.json"
    ParetoRegistry._write_json(historical_path, loaded)
    repersisted = json.loads(historical_path.read_text(encoding="utf-8"))
    assert repersisted["schema_version"] == "2.0"
    assert "policy_evaluation_status" not in repersisted["entries"][candidate_hash]
    assert math.isnan(
        repersisted["entries"][candidate_hash]["evaluation"]["secondary"][
            "legacy_nonfrontier_quality"
        ]["value"]
    )
    projection = loaded.project_view(ParetoView.GLOBAL_FEASIBLE)
    assert projection.assessment.status != "complete"
    assert projection.ranked_frontier_hashes == ()
    assert projection.unassessed_candidate_hashes == (candidate_hash,)

    republished = registry.publish_transfer_surface(
        source.run_id,
        transfer_context=source,
        snapshot=loaded,
    )
    assert republished.frontiers["global_feasible"] == []
    assert registry.get_seed_bundle(source, max_seeds=3).entries == []


def test_unassessed_registry_entry_is_retained_but_never_ranked_or_transferred(tmp_path) -> None:
    registry = ParetoRegistry(tmp_path / "registry")
    candidate = _candidate()
    source = TransferContext(
        task_family="policy",
        domain="fiscal",
        run_id="loop-unassessed-status",
        tenant_hash="tenant-a",
    )
    evaluation = _evaluation_vector(candidate)
    candidate_hash = candidate.candidate_hash()

    registry.update(
        source.run_id,
        candidate_hash=candidate_hash,
        evaluation=evaluation,
        candidate_id=candidate.candidate_id,
        policy_family="core_family",
        seed_payload=candidate.model_dump(mode="json"),
        transfer_context=source,
        objective_basis_by_view={
            "global_feasible": ParetoBasisScope(
                scope="declared",
                coordinate_ids=["policy_value", "employment"],
                basis_ref="test:unassessed-status-basis",
            )
        },
        policy_evaluation_status="unassessed",
        policy_evaluation_error="secondary.registry_only_quality.value:non_finite",
    )

    local = registry.get_snapshot(source.run_id)
    entry = local.entries[candidate_hash]
    assert entry.policy_evaluation_status == "unassessed"
    assert entry.policy_evaluation_error == "secondary.registry_only_quality.value:non_finite"
    assert local.frontiers["global_feasible"] == []
    assert local.project_view(ParetoView.GLOBAL_FEASIBLE).ranked_frontier_hashes == ()
    assert registry.get_seed_bundle(source, max_seeds=3).entries == []
