"""Public simulate run metric validation module API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.contracts.foundry import (
    MetricObservationBundle,
    MetricObservationBundleRef,
    Metrics,
    MetricsRef,
    SimulationResult,
    SimulationResultRef,
)
from polisyos.core.contracts.scientist import (
    MetricValidationReportRef as CoreMetricValidationReportRef,
)
from polisyos.ir.analytics.metric_validation_report import persist_metric_validation_report
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.protocol import NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.engine.state_branching import branch_state
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_METRIC_OBSERVATION_BUNDLE_REF,
    ARTIFACT_METRIC_VALIDATION_REPORT_REF,
    ARTIFACT_METRICS_REF,
    ARTIFACT_SIMULATION_RESULT_REF,
)
from polisyos.scientist.validation.metrics import (
    CorrectionMethod,
    FamilyScope,
    MetricId,
    TestConfig,
    compare_metric_family,
    load_metric_observation_bundle,
    persist_metric_observation_bundle,
)

_SUPPORTED_METRIC_IDS: tuple[MetricId, ...] = (
    "roc_auc",
    "accuracy",
    "precision",
    "recall",
    "f1",
    "log_loss",
    "brier",
    "mse",
    "rmse",
    "mae",
    "average_precision",
)
_METRIC_LOAD_ERRORS = (OSError, RuntimeError, TypeError, ValueError, ValidationError)

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_run_metric_validation@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Run Metric Validation",
    description="Run formal statistical validation over metric comparison families.",
    tags=["builtin", "simulate", "validation", "metrics"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=[
        f"artifacts_index.{ARTIFACT_SIMULATION_RESULT_REF}",
        f"artifacts_index.{ARTIFACT_METRICS_REF}",
        f"artifacts_index.{ARTIFACT_METRIC_OBSERVATION_BUNDLE_REF}",
        "params.metric_validation",
    ],
    state_writes=[
        f"artifacts_index.{ARTIFACT_SIMULATION_RESULT_REF}",
        f"artifacts_index.{ARTIFACT_METRIC_OBSERVATION_BUNDLE_REF}",
        f"artifacts_index.{ARTIFACT_METRIC_VALIDATION_REPORT_REF}",
    ],
    produces=[
        ARTIFACT_SIMULATION_RESULT_REF,
        ARTIFACT_METRIC_OBSERVATION_BUNDLE_REF,
        ARTIFACT_METRIC_VALIDATION_REPORT_REF,
    ],
)


class MetricValidationNodeConfig(BaseModel):
    """Runtime configuration surface for the metric-validation node."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    observation_bundle_ref: str | dict[str, Any] | None = None
    observation_bundle: MetricObservationBundle | dict[str, Any] | None = None
    baseline_model_id: str | None = None
    candidate_model_ids: list[str] | None = None
    metric_ids: list[MetricId] | None = None
    family_scope: FamilyScope = "all_pairs_all_metrics"
    alpha: float = Field(default=0.05, gt=0.0, lt=1.0)
    alternative: Literal["two-sided", "greater", "less"] = "two-sided"
    n_resamples: int = Field(default=20_000, ge=100)
    confidence_level: float = Field(default=0.95, gt=0.0, lt=1.0)
    correction: CorrectionMethod = "holm"
    random_seed: int | None = None
    exact_if_feasible: bool = True


@dataclass(frozen=True)
class RunMetricValidationNode:
    """Simulation-stage node that materializes a formal metric-validation report."""

    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        config = _load_config(state.params.get("metric_validation"))
        if not config.enabled:
            return NodeOutcome(
                status="skip",
                state=state,
                events=[
                    NodeEvent(
                        level="info",
                        message="Metric validation disabled in params.metric_validation",
                    )
                ],
            )

        simulation_result_ref = state.artifacts_index.get(ARTIFACT_SIMULATION_RESULT_REF)
        if simulation_result_ref is None:
            return NodeOutcome(
                status="skip",
                state=state,
                events=[
                    NodeEvent(
                        level="info", message="No simulation_result_ref; skip metric validation"
                    )
                ],
            )

        simulation_result = _load_model(ctx, simulation_result_ref, SimulationResult)
        bundle_ref, persisted_bundle_artifact = _resolve_observation_bundle_ref(
            ctx,
            state,
            simulation_result,
            config,
        )
        if bundle_ref is None:
            return NodeOutcome(
                status="skip",
                state=state,
                events=[
                    NodeEvent(
                        level="info",
                        message="No metric observation bundle available; skip metric validation",
                    )
                ],
            )

        bundle = load_metric_observation_bundle(ctx.store, bundle_ref)
        baseline_model_id = _resolve_baseline_model_id(bundle, config)
        if baseline_model_id is None:
            return NodeOutcome(
                status="skip",
                state=state,
                events=[
                    NodeEvent(
                        level="warn",
                        message="Metric validation requires baseline_model_id when multiple models are present",
                    )
                ],
            )

        candidate_model_ids = _resolve_candidate_model_ids(bundle, baseline_model_id, config)
        if not candidate_model_ids:
            return NodeOutcome(
                status="skip",
                state=state,
                events=[
                    NodeEvent(
                        level="warn",
                        message="Metric validation found no candidate models beyond the baseline",
                    )
                ],
            )

        metric_ids = _resolve_metric_ids(
            ctx, state, simulation_result, bundle, baseline_model_id, candidate_model_ids, config
        )
        if not metric_ids:
            return NodeOutcome(
                status="skip",
                state=state,
                events=[
                    NodeEvent(
                        level="warn",
                        message="Metric validation found no supported metric families to compare",
                    )
                ],
            )

        report = compare_metric_family(
            bundle=bundle,
            baseline_model_id=baseline_model_id,
            candidate_model_ids=candidate_model_ids,
            metric_ids=metric_ids,
            config=TestConfig(
                alpha=config.alpha,
                alternative=config.alternative,
                n_resamples=config.n_resamples,
                confidence_level=config.confidence_level,
                correction=config.correction,
                random_seed=config.random_seed,
                exact_if_feasible=config.exact_if_feasible,
            ),
            family_scope=config.family_scope,
        )
        persisted_report_ref = persist_metric_validation_report(
            ctx.store,
            report,
            inputs=[
                InputRef(artifact_id=str(bundle_ref.artifact_id), role="metric_observation_bundle"),
                InputRef(
                    artifact_id=str(simulation_result_ref.artifact_id), role="simulation_result"
                ),
                InputRef(
                    artifact_id=str(simulation_result.metrics_ref.artifact_id), role="metrics"
                ),
            ],
        )
        report_ref = CoreMetricValidationReportRef.model_validate(
            persisted_report_ref.model_dump(mode="json")
        )

        updated_simulation_result = simulation_result.model_copy(
            update={
                "metric_observation_bundle_ref": bundle_ref,
                "metric_validation_report_ref": report_ref,
            }
        )
        updated_simulation_result_payload = ctx.store.put_json(
            updated_simulation_result,
            PutOptions(
                kind="foundry.simulation_result",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.core.SimulationResult", version="1.1"),
                inputs=[
                    InputRef(
                        artifact_id=str(simulation_result_ref.artifact_id),
                        role="base_simulation_result",
                    ),
                    InputRef(
                        artifact_id=str(bundle_ref.artifact_id), role="metric_observation_bundle"
                    ),
                    InputRef(
                        artifact_id=str(report_ref.artifact_id), role="metric_validation_report"
                    ),
                ],
            ),
        )
        updated_simulation_result_ref = SimulationResultRef(
            artifact_id=updated_simulation_result_payload.artifact_id
        )

        new_state = branch_state(state, write_paths=("artifacts_index",)).state
        new_state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF] = updated_simulation_result_ref
        new_state.artifacts_index[ARTIFACT_METRIC_OBSERVATION_BUNDLE_REF] = bundle_ref
        new_state.artifacts_index[ARTIFACT_METRIC_VALIDATION_REPORT_REF] = report_ref

        artifacts: list[ArtifactRef] = [updated_simulation_result_ref, report_ref]
        if persisted_bundle_artifact is not None:
            artifacts.append(persisted_bundle_artifact)

        return NodeOutcome(
            status="ok",
            state=new_state,
            artifacts=artifacts,
            events=[
                NodeEvent(
                    level="info",
                    message=(
                        "Metric validation completed "
                        f"(baseline={baseline_model_id}, candidates={len(candidate_model_ids)}, metrics={len(metric_ids)})"
                    ),
                    attrs={
                        "comparison_count": len(report.comparisons),
                        "warning_count": len(report.warnings),
                        "error_count": len(report.errors),
                    },
                )
            ],
        )


def _load_config(payload: Any) -> MetricValidationNodeConfig:
    if payload is None:
        return MetricValidationNodeConfig()
    if isinstance(payload, MetricValidationNodeConfig):
        return payload
    if isinstance(payload, dict):
        return MetricValidationNodeConfig.model_validate(payload)
    raise ValueError("params.metric_validation must be an object when provided")


def _load_model(ctx: ExecutionContext, ref: ArtifactRef, model_cls: type[Any]) -> Any:
    payload = ctx.store.get_bytes(ref.artifact_id)
    return model_cls.model_validate_json(payload)


def _resolve_observation_bundle_ref(
    ctx: ExecutionContext,
    state: ExperimentState,
    simulation_result: SimulationResult,
    config: MetricValidationNodeConfig,
) -> tuple[MetricObservationBundleRef | None, ArtifactRef | None]:
    existing_ref = state.artifacts_index.get(ARTIFACT_METRIC_OBSERVATION_BUNDLE_REF)
    if existing_ref is not None:
        return MetricObservationBundleRef.model_validate(existing_ref.model_dump(mode="json")), None
    if simulation_result.metric_observation_bundle_ref is not None:
        return simulation_result.metric_observation_bundle_ref, None
    if config.observation_bundle_ref is not None:
        return _coerce_observation_bundle_ref(config.observation_bundle_ref), None
    if config.observation_bundle is not None:
        bundle = (
            config.observation_bundle
            if isinstance(config.observation_bundle, MetricObservationBundle)
            else MetricObservationBundle.model_validate(config.observation_bundle)
        )
        ref = persist_metric_observation_bundle(
            ctx.store,
            bundle,
            inputs=[
                InputRef(
                    artifact_id=str(simulation_result.metrics_ref.artifact_id),
                    role="metrics",
                )
            ],
        )
        return ref, ref
    return None, None


def _coerce_observation_bundle_ref(value: str | dict[str, Any]) -> MetricObservationBundleRef:
    if isinstance(value, str):
        artifact_id = value if value.startswith("sha256:") else f"sha256:{value}"
        return MetricObservationBundleRef(
            artifact_id=artifact_id,
            kind="foundry.metric_observation_bundle",
            media_type="application/json",
        )
    return MetricObservationBundleRef.model_validate(value)


def _resolve_baseline_model_id(
    bundle: MetricObservationBundle,
    config: MetricValidationNodeConfig,
) -> str | None:
    if config.baseline_model_id:
        return config.baseline_model_id
    metadata_baseline = bundle.metadata.get("baseline_model_id")
    if isinstance(metadata_baseline, str) and metadata_baseline in bundle.models:
        return metadata_baseline
    model_ids = list(bundle.models)
    if len(model_ids) == 2:
        return model_ids[0]
    if len(model_ids) == 1:
        return model_ids[0]
    return None


def _resolve_candidate_model_ids(
    bundle: MetricObservationBundle,
    baseline_model_id: str,
    config: MetricValidationNodeConfig,
) -> list[str]:
    requested = config.candidate_model_ids
    if requested:
        return [
            model_id
            for model_id in requested
            if model_id in bundle.models and model_id != baseline_model_id
        ]
    return [model_id for model_id in bundle.models if model_id != baseline_model_id]


def _resolve_metric_ids(
    ctx: ExecutionContext,
    state: ExperimentState,
    simulation_result: SimulationResult,
    bundle: MetricObservationBundle,
    baseline_model_id: str,
    candidate_model_ids: list[str],
    config: MetricValidationNodeConfig,
) -> list[MetricId]:
    if config.metric_ids:
        return list(dict.fromkeys(config.metric_ids))

    metrics_ref = state.artifacts_index.get(ARTIFACT_METRICS_REF) or simulation_result.metrics_ref
    metric_ids_from_summary = _metric_ids_from_metrics_ref(ctx, metrics_ref)
    if metric_ids_from_summary:
        return metric_ids_from_summary

    selected_model_ids = [baseline_model_id, *candidate_model_ids]
    selected_models = [
        bundle.models[model_id] for model_id in selected_model_ids if model_id in bundle.models
    ]
    if not selected_models:
        return []
    has_scores = all(model.y_score is not None for model in selected_models)
    has_preds = all(model.y_pred is not None for model in selected_models)
    inferred: list[MetricId] = []
    if bundle.task == "regression":
        if has_preds:
            inferred.extend(["mse", "rmse", "mae"])
        return inferred
    if has_preds:
        inferred.extend(["accuracy", "precision", "recall", "f1"])
    if has_scores:
        inferred.extend(["roc_auc", "average_precision", "log_loss"])
        if bundle.task == "binary":
            inferred.append("brier")
    return list(dict.fromkeys(inferred))


def _metric_ids_from_metrics_ref(
    ctx: ExecutionContext,
    ref: ArtifactRef | MetricsRef | None,
) -> list[MetricId]:
    if ref is None:
        return []
    try:
        metrics = _load_model(ctx, ref, Metrics)
    except _METRIC_LOAD_ERRORS:
        return []
    out: list[MetricId] = []
    for metric_id in metrics.values:
        if metric_id in _SUPPORTED_METRIC_IDS:
            out.append(metric_id)
    return out


__all__ = ["MetricValidationNodeConfig", "RunMetricValidationNode"]
