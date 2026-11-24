"""Exercise source-selected Pareto comparison with registered MethodJob results."""

from __future__ import annotations

from dataclasses import replace
from itertools import product
from pathlib import Path
from typing import Any, ClassVar

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef, input_ref_from_artifact_ref
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec
from polisyos.foundry.methods import MethodRegistry, MethodSignature
from polisyos.scientist.methods.autotune.benchmark_pareto import MethodJobParetoCandidate
from polisyos.scientist.methods.autotune.models import (
    BenchmarkEvaluation,
    BenchmarkSplit,
    BenchmarkSuite,
    PromotionPolicy,
    load_model_artifact,
    persist_benchmark_evaluation,
    persist_benchmark_suite,
    persist_mutation_artifact,
)
from polisyos.scientist.methods.autotune.pareto import _coordinate_for_policy
from polisyos.scientist.methods.autotune.runtime import MethodJobBenchmarkEvaluator
from polisyos.scientist.methods.search.pareto_registry import ParetoRegistry
from tests.unit.scientist.methods.autotune.test_v5_search_pipeline import (
    _V5Mutation,
    _V5ScoreMethod,
)

_UNIT = "USD per resident"
_DELIMITER_METRIC = "score::holdout::unit=USD per resident::direction=maximize"


class _ParetoMutation(_V5Mutation):
    holdout_value: float
    third_value: float


class _ParetoScoreMethod(_V5ScoreMethod):
    signature: ClassVar[MethodSignature] = replace(
        _V5ScoreMethod.signature, name="pareto_selected_score"
    )
    calls: ClassVar[int] = 0

    @staticmethod
    def pure_step(state: Any, params: dict[str, Any]) -> dict[str, Any]:
        _ParetoScoreMethod.calls += 1
        value = float(state["value"]) + float(params.get("offset", 0.0))
        return {
            "score": value,
            _DELIMITER_METRIC: value,
            "metric_units": {"score": _UNIT},
            "sample_counts": {"selection": 3, "holdout": 3},
        }


def _selected_case(
    store: FileSystemCAS,
    suite_ref: ArtifactRef,
    rows: tuple[tuple[float, float, float], ...],
    policies: tuple[PromotionPolicy, ...],
) -> tuple[MethodJobParetoCandidate, ...]:
    candidates = []
    for value, holdout_value, third_value in rows:
        candidate_ref = persist_mutation_artifact(
            store,
            _ParetoMutation(
                value=value, holdout_value=holdout_value - 1.0, third_value=third_value - 2.0
            ),
            inputs=[input_ref_from_artifact_ref(suite_ref, role="benchmark_suite")],
            return_selected_profile=True,
        )
        refs = {}
        for index, (policy, value_field) in enumerate(
            zip(policies, ("value", "holdout_value", "third_value"), strict=True)
        ):
            evaluation = MethodJobBenchmarkEvaluator(
                method_fqn=_ParetoScoreMethod.signature.fqn,
                candidate_input_bindings={"value": value_field},
                method_params={"offset": float(index)},
                split=policy.compare_split,
            ).evaluate(
                candidate_ref,
                suite_ref,
                {"store": store, "loop_id": policy.loop_id, "policy": policy},
            )
            assert evaluation.status == "measured_candidate"
            assert not evaluation.promotable
            assert evaluation.runtime_split_type is policy.compare_split
            assert evaluation.metadata["metric_unit"] == policy.unit
            axis = _coordinate_for_policy(policy).coordinate_id
            refs[axis] = persist_benchmark_evaluation(
                store,
                evaluation,
                inputs=[input_ref_from_artifact_ref(suite_ref, role="benchmark_suite")],
                return_selected_profile=True,
            )
        candidates.append(
            MethodJobParetoCandidate(
                candidate_ref=candidate_ref, evaluation_refs_by_coordinate=refs
            )
        )
    return tuple(candidates)


def test_method_job_front_reopens_two_splits_and_the_3d_indicator(tmp_path: Path) -> None:
    MethodRegistry.get_instance().register(_ParetoScoreMethod, override=True)
    _ParetoScoreMethod.calls = 0
    store = FileSystemCAS(tmp_path / "cas")
    registry_root = tmp_path / "registry"
    writer = ParetoRegistry(registry_root, source_store=store)
    suite_ref = persist_benchmark_suite(
        store,
        BenchmarkSuite(suite_id="pareto-measured", kind="method_job"),
        return_selected_profile=True,
    )
    policies = (
        PromotionPolicy(
            loop_id="v5_search",
            primary_metric="score",
            unit=_UNIT,
            compare_split=BenchmarkSplit.SELECTION,
        ),
        PromotionPolicy(
            loop_id="v5_search",
            primary_metric="score",
            unit=_UNIT,
            compare_split=BenchmarkSplit.HOLDOUT,
        ),
        PromotionPolicy(
            loop_id="v5_search",
            primary_metric=_DELIMITER_METRIC,
            compare_split=BenchmarkSplit.HOLDOUT,
        ),
    )
    rows = ((10.0, 1.0, 1.0), (1.0, 10.0, 1.0), (1.0, 1.0, 10.0))
    candidate_refs = _selected_case(store, suite_ref, rows, policies)
    assert _ParetoScoreMethod.calls == 9
    axes = tuple(_coordinate_for_policy(policy).coordinate_id for policy in policies)
    origin = dict.fromkeys(axes, 0.0)
    selected = writer.persist_method_job_front(
        suite_ref=suite_ref,
        policies=policies,
        candidates=candidate_refs,
        declared_reference_point=origin,
    )
    fresh = ParetoRegistry(registry_root, source_store=FileSystemCAS(tmp_path / "cas"))
    report = fresh.load_method_job_front(selected)
    assert report.purpose == "candidate_comparison"
    assert report.coordinate_refusals == ({}, {}, {})
    assert report.front.input_assessment is not None
    assert report.front.input_assessment.status == "complete"
    schema = report.front.coordinate_schema
    assert schema is not None and len(schema.coordinates) == 3
    assert [
        (coordinate.metric, coordinate.split, coordinate.unit) for coordinate in schema.coordinates
    ] == [
        ("score", BenchmarkSplit.SELECTION, _UNIT),
        ("score", BenchmarkSplit.HOLDOUT, _UNIT),
        (_DELIMITER_METRIC, BenchmarkSplit.HOLDOUT, None),
    ]
    assert {coordinate.coordinate_id for coordinate in schema.coordinates} == set(axes)
    expected_by_ref = {
        str(source.candidate_ref.artifact_id): dict(zip(axes, row, strict=True))
        for source, row in zip(candidate_refs, rows, strict=True)
    }
    assert {
        item.candidate_ref_id: item.coordinate_values for item in report.front.members
    } == expected_by_ref
    assert all(set(item.objectives) == set(axes) for item in report.front.members)
    assert all(not item.evaluation.promotable for item in report.front.members)
    indicator = report.hypervolume_indicator
    assert indicator is not None and indicator.algorithm == "bounding_box_upper_bound.v1"
    assert indicator.value == 1000.0 and indicator.coordinate_reference_point == origin
    assert (
        len({cell for row in rows for cell in product(*(range(int(bound)) for bound in row))}) == 28
    )
    assert _ParetoScoreMethod.calls == 9

    # A valid artifact with a foreign split cannot meet the hidden coordinate.
    hidden = policies[1].model_copy(update={"compare_split": BenchmarkSplit.HIDDEN_HOLDOUT})
    hidden_id = _coordinate_for_policy(hidden).coordinate_id
    candidate = candidate_refs[0]
    without_hidden_basis = MethodJobParetoCandidate(
        candidate_ref=candidate.candidate_ref,
        evaluation_refs_by_coordinate={hidden_id: candidate.evaluation_refs_by_coordinate[axes[1]]},
    )
    unverified = writer.persist_method_job_front(
        suite_ref=suite_ref, policies=(hidden,), candidates=(without_hidden_basis,)
    )
    hidden_report = fresh.load_method_job_front(unverified)
    assert hidden_report.coordinate_refusals == ({hidden_id: "coordinate_runtime_split_mismatch"},)
    assert hidden_report.front.members == [] and hidden_report.hypervolume_indicator is None

    foreign_unit = policies[1].model_copy(update={"unit": "EUR per resident"})
    foreign_id = _coordinate_for_policy(foreign_unit).coordinate_id
    wrong_unit_source = MethodJobParetoCandidate(
        candidate_ref=candidate.candidate_ref,
        evaluation_refs_by_coordinate={
            foreign_id: candidate.evaluation_refs_by_coordinate[axes[1]]
        },
    )
    wrong_unit = fresh.load_method_job_front(
        writer.persist_method_job_front(
            suite_ref=suite_ref, policies=(foreign_unit,), candidates=(wrong_unit_source,)
        )
    )
    assert wrong_unit.coordinate_refusals == ({foreign_id: "coordinate_unit_mismatch"},)
    assert wrong_unit.front.members == []

    # Substituting another candidate's otherwise valid basis removes only that row.
    third = candidate_refs[2]
    foreign_evaluation = MethodJobParetoCandidate(
        candidate_ref=third.candidate_ref,
        evaluation_refs_by_coordinate={
            **third.evaluation_refs_by_coordinate,
            axes[0]: candidate.evaluation_refs_by_coordinate[axes[0]],
        },
    )
    partial = fresh.load_method_job_front(
        writer.persist_method_job_front(
            suite_ref=suite_ref,
            policies=policies,
            candidates=(*candidate_refs[:2], foreign_evaluation),
        )
    )
    assert partial.front.input_assessment is not None
    assert partial.front.input_assessment.status == "partial"
    assert partial.front.input_assessment.assessed_count == 2
    assert partial.coordinate_refusals[2][axes[0]] == "methodjob_source_request_binding_mismatch"
    assert partial.hypervolume_indicator is None

    manifest = store.get_manifest(selected)
    assert manifest.artifact_schema is not None
    forged = store.put_json(
        report,
        ArtifactWriteOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            producer=manifest.producer,
            inputs=manifest.inputs[:-1],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    assert forged.artifact_id == selected.artifact_id
    assert forged.manifest_profile_sha256 != selected.manifest_profile_sha256
    with pytest.raises(ValueError, match="source edges mismatch"):
        fresh.load_method_job_front(forged)

    original_eval = load_model_artifact(
        store, candidate.evaluation_refs_by_coordinate[axes[0]], BenchmarkEvaluation
    )
    result_ref = original_eval.method_result_ref
    assert result_ref is not None and result_ref.manifest_profile_sha256 is not None
    result_profile = store._manifest_path_for_ref(
        result_ref.artifact_id, result_ref.manifest_profile_sha256
    )
    withdrawn = result_profile.with_suffix(".withdrawn")
    result_profile.rename(withdrawn)
    try:
        with pytest.raises(ValueError, match="no longer matches the selected source"):
            fresh.load_method_job_front(selected)
        survivor = fresh.load_method_job_front(
            writer.persist_method_job_front(
                suite_ref=suite_ref, policies=policies, candidates=candidate_refs
            )
        )
        assert survivor.front.input_assessment is not None
        assert survivor.front.input_assessment.assessed_count == 2
        assert survivor.coordinate_refusals[0][axes[0]] == "coordinate_source_unavailable"
    finally:
        withdrawn.rename(result_profile)

    assert fresh.load_method_job_front(selected) == report
    assert _ParetoScoreMethod.calls == 9
