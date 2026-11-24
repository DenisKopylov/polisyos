"""Candidate-grade Pareto reports based on selected MethodJob observations."""

from __future__ import annotations

from collections import Counter
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from polisyos.core.artifacts import (
    CoreJSONArtifactStore,
    read_core_manifest_profile,
    validate_core_model_json_artifact,
)
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    InputRef,
    ProducerInfo,
    SchemaInfo,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec

from .models import (
    BenchmarkEvaluation,
    BenchmarkSplit,
    BenchmarkSuite,
    PromotionPolicy,
    load_model_artifact,
)
from .pareto import (
    ParetoFront,
    ParetoHypervolumeIndicator,
    ParetoPromoter,
    _coordinate_for_policy,
)
from .registry import _methodjob_source_admission_failure

_REPORT_KIND = "scientist.autotune.method_job.pareto_front"
_REPORT_SCHEMA = SchemaInfo(
    name="polisyos.scientist.methods.autotune.MethodJobParetoReport",
    version="1.0",
)
_REPORT_PRODUCER = ProducerInfo(
    component="polisyos.scientist.methods.autotune.benchmark_pareto",
    version="1.0",
)


class MethodJobParetoCandidate(BaseModel):
    """Pair the exact candidate profile with selected evaluations by coordinate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_ref: ArtifactRef
    evaluation_refs_by_coordinate: dict[str, ArtifactRef] = Field(default_factory=dict)


class MethodJobParetoReport(BaseModel):
    """Replayable candidate geometry without ranked policy or publication authority."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    purpose: Literal["candidate_comparison"] = "candidate_comparison"
    suite_ref: ArtifactRef
    policies: tuple[PromotionPolicy, ...]
    candidates: tuple[MethodJobParetoCandidate, ...]
    declared_reference_point: dict[str, float] | None = None
    coordinate_refusals: tuple[dict[str, str], ...]
    front: ParetoFront
    hypervolume_indicator: ParetoHypervolumeIndicator | None = None


def _selected_coordinate(
    store: CoreJSONArtifactStore,
    *,
    suite_ref: ArtifactRef,
    candidate_ref: ArtifactRef,
    evaluation_ref: ArtifactRef | None,
    policy: PromotionPolicy,
) -> tuple[float | None, str | None]:
    if evaluation_ref is None:
        return None, "coordinate_source_missing"
    if evaluation_ref.manifest_profile_sha256 is None:
        return None, "coordinate_selected_profile_required"
    try:
        manifest, _ = read_core_manifest_profile(store, evaluation_ref)
        if (
            manifest.kind != f"scientist.autotune.{policy.loop_id}.evaluation"
            or manifest.artifact_schema is None
            or manifest.artifact_schema.name
            != "polisyos.scientist.methods.autotune.BenchmarkEvaluation"
        ):
            return None, "coordinate_evaluation_schema_mismatch"
        evaluation = load_model_artifact(store, evaluation_ref, BenchmarkEvaluation)
        if manifest.artifact_schema.version != evaluation.suite_version:
            return None, "coordinate_evaluation_schema_mismatch"
        if evaluation.runtime_split_type is not policy.compare_split:
            return None, "coordinate_runtime_split_mismatch"
        if policy.compare_split not in {BenchmarkSplit.SELECTION, BenchmarkSplit.HOLDOUT}:
            return None, "coordinate_method_job_split_unsupported"
        if evaluation.metadata.get("metric_unit") != policy.unit:
            return None, "coordinate_unit_mismatch"
        refusal = _methodjob_source_admission_failure(
            store=store,
            candidate_ref=candidate_ref,
            evaluation_ref=evaluation_ref,
            evaluation=evaluation,
            suite_ref=suite_ref,
            policy=policy,
        )
        if refusal is not None:
            return None, refusal
        value = evaluation.primary_value(split=policy.compare_split, metric=policy.primary_metric)
        if value is None:
            return None, "coordinate_source_metric_missing"
        return value, None
    except (KeyError, OSError, OverflowError, RuntimeError, TypeError, ValueError, ValidationError):
        return None, "coordinate_source_unavailable"


def _reconcile_report(
    store: CoreJSONArtifactStore,
    *,
    suite_ref: ArtifactRef,
    policies: tuple[PromotionPolicy, ...],
    candidates: tuple[MethodJobParetoCandidate, ...],
    declared_reference_point: dict[str, float] | None,
) -> MethodJobParetoReport:
    if (
        suite_ref.manifest_profile_sha256 is None
        or suite_ref.kind != "scientist.autotune.method_job.suite"
    ):
        raise ValueError("Pareto comparison requires a selected MethodJob suite")
    suite_manifest, _ = read_core_manifest_profile(store, suite_ref)
    suite = load_model_artifact(store, suite_ref, BenchmarkSuite)
    if (
        suite.kind != "method_job"
        or suite_manifest.kind != suite_ref.kind
        or suite_manifest.media_type != "application/json"
        or suite_manifest.artifact_schema
        != SchemaInfo(
            name="polisyos.scientist.methods.autotune.BenchmarkSuite",
            version=suite.suite_version,
        )
    ):
        raise ValueError("Pareto comparison suite manifest does not match the MethodJob suite")
    if not policies or len({policy.loop_id for policy in policies}) != 1:
        raise ValueError("Pareto comparison requires policies from one benchmark loop")
    if len({str(candidate.candidate_ref.artifact_id) for candidate in candidates}) != len(
        candidates
    ):
        raise ValueError("Pareto comparison repeats a candidate")
    promoter = ParetoPromoter(list(policies))
    policy_by_axis = {_coordinate_for_policy(policy).coordinate_id: policy for policy in policies}
    metric_counts = Counter((policy.compare_split, policy.primary_metric) for policy in policies)

    evaluations: list[BenchmarkEvaluation] = []
    coordinate_values: list[dict[str, float]] = []
    coordinate_refusals: list[dict[str, str]] = []
    for candidate in candidates:
        if candidate.candidate_ref.manifest_profile_sha256 is None:
            raise ValueError("Pareto comparison requires selected candidate profiles")
        if not candidate.evaluation_refs_by_coordinate.keys() <= policy_by_axis.keys():
            raise ValueError("Pareto comparison source names an undeclared coordinate")
        values: dict[str, float] = {}
        refusals: dict[str, str] = {}
        selection: dict[str, float] = {}
        holdout: dict[str, float] = {}
        for axis, policy in policy_by_axis.items():
            value, refusal = _selected_coordinate(
                store,
                suite_ref=suite_ref,
                candidate_ref=candidate.candidate_ref,
                evaluation_ref=candidate.evaluation_refs_by_coordinate.get(axis),
                policy=policy,
            )
            if value is None:
                assert refusal is not None
                refusals[axis] = refusal
                continue
            values[axis] = value
            # The legacy split maps can represent only one value for a metric.
            # Canonical rows retain each unit/direction even if that label repeats.
            if metric_counts[policy.compare_split, policy.primary_metric] == 1:
                metrics = selection if policy.compare_split is BenchmarkSplit.SELECTION else holdout
                metrics[policy.primary_metric] = value
        evaluations.append(
            BenchmarkEvaluation(
                loop_id=policies[0].loop_id,
                suite_id=suite.suite_id,
                suite_version=suite.suite_version,
                candidate_ref=candidate.candidate_ref,
                selection_metrics=selection,
                holdout_metrics=holdout,
                status="candidate_comparison",
            )
        )
        coordinate_values.append(values)
        coordinate_refusals.append(refusals)
    front, indicator = promoter._compute_front_with_indicator(
        evaluations,
        declared_reference_point=declared_reference_point,
        coordinate_values=coordinate_values,
    )
    return MethodJobParetoReport(
        suite_ref=suite_ref,
        policies=policies,
        candidates=candidates,
        declared_reference_point=declared_reference_point,
        coordinate_refusals=tuple(coordinate_refusals),
        front=front,
        hypervolume_indicator=indicator,
    )


def _comparison_inputs(report: MethodJobParetoReport) -> list[InputRef]:
    inputs = [input_ref_from_artifact_ref(report.suite_ref, role="benchmark_suite")]
    for index, candidate in enumerate(report.candidates):
        inputs.append(
            input_ref_from_artifact_ref(candidate.candidate_ref, role=f"candidate:{index}")
        )
        inputs.extend(
            input_ref_from_artifact_ref(ref, role=f"coordinate:{index}:{axis}")
            for axis, ref in sorted(candidate.evaluation_refs_by_coordinate.items())
        )
    return inputs


def persist_method_job_front(
    store: CoreJSONArtifactStore,
    *,
    suite_ref: ArtifactRef,
    policies: tuple[PromotionPolicy, ...],
    candidates: tuple[MethodJobParetoCandidate, ...],
    declared_reference_point: dict[str, float] | None = None,
) -> ArtifactRef:
    """Reconcile the selected evaluations and persist their candidate comparison."""
    report = _reconcile_report(
        store,
        suite_ref=suite_ref,
        policies=tuple(policy.model_copy(deep=True) for policy in policies),
        candidates=tuple(candidate.model_copy(deep=True) for candidate in candidates),
        declared_reference_point=(
            dict(declared_reference_point) if declared_reference_point is not None else None
        ),
    )
    return store.put_json(
        report,
        ArtifactWriteOptions(
            kind=_REPORT_KIND,
            media_type="application/json",
            schema=_REPORT_SCHEMA,
            producer=_REPORT_PRODUCER,
            inputs=_comparison_inputs(report),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )


def load_method_job_front(
    store: CoreJSONArtifactStore,
    ref: ArtifactRef,
) -> MethodJobParetoReport:
    """Reopen the exact report and recompute it from the selected source graph."""
    if ref.kind != _REPORT_KIND or ref.manifest_profile_sha256 is None:
        raise ValueError("Pareto comparison report requires its selected manifest profile")
    manifest, _ = read_core_manifest_profile(store, ref)
    if (
        manifest.kind != _REPORT_KIND
        or manifest.artifact_schema != _REPORT_SCHEMA
        or manifest.producer != _REPORT_PRODUCER
    ):
        raise ValueError("Pareto comparison report manifest mismatch")
    report = validate_core_model_json_artifact(MethodJobParetoReport, store, ref)
    if manifest.inputs != _comparison_inputs(report):
        raise ValueError("Pareto comparison report source edges mismatch")
    expected = _reconcile_report(
        store,
        suite_ref=report.suite_ref,
        policies=report.policies,
        candidates=report.candidates,
        declared_reference_point=report.declared_reference_point,
    )
    if report != expected:
        raise ValueError("Pareto comparison report no longer matches the selected source")
    return report
