"""Synthetic-world orchestration layer."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np

from polisyos.ir.model_layer.canon import CanonSpec, content_hash, to_canonical_bytes

from .core.truth_api import select_truth_targets
from .evaluators import build_hook_diagnostics, build_plot_specs, evaluate_prediction
from .models import (
    BenchmarkSuiteBinding,
    EvaluationRun,
    MeasurementErrorKind,
    MissingnessMechanism,
    SamplingDesignKind,
    SyntheticWorldDGP,
    SyntheticWorldSample,
    TruthManifest,
    TruthQuery,
    WorldArtifact,
    WorldFamily,
    json_safe,
)
from .templates import (
    MaterializedWorldPayload,
    materialize_cross_sectional_world,
    materialize_panel_dynamic_world,
    materialize_spatio_temporal_world,
    materialize_survey_repeated_cross_section_world,
)

_TEMPLATE_REGISTRY = {
    WorldFamily.CROSS_SECTIONAL: materialize_cross_sectional_world,
    WorldFamily.PANEL_DYNAMIC: materialize_panel_dynamic_world,
    WorldFamily.SPATIO_TEMPORAL: materialize_spatio_temporal_world,
    WorldFamily.SURVEY_REPEATED_CROSS_SECTION: materialize_survey_repeated_cross_section_world,
}

_TRUTH_PREFIX_FLAGS = {
    "bayesian": "include_bayesian",
    "ml": "include_ml",
    "forecast": "include_forecasting",
    "econometrics": "include_econometrics",
    "survey": "include_survey",
    "distributional": "include_distributional",
    "causal": "include_causal",
}


def _table_slice(table: Mapping[str, np.ndarray], rows: np.ndarray) -> dict[str, np.ndarray]:
    return {name: np.asarray(values)[rows] for name, values in table.items()}


def _hash_payload(payload: Any) -> str:
    canonical = to_canonical_bytes(
        _sanitize_non_finite(json_safe(payload)), spec=CanonSpec(forbid_floats=False)
    )
    return content_hash(canonical, prefix=True)


def _artifact_ref(kind: str, digest: str) -> str:
    return f"synthetic-world://{kind}/{digest}"


def _target_families(registry: Mapping[str, Mapping[str, Any]]) -> tuple[str, ...]:
    families = sorted({target.split(".", 1)[0] for target in registry})
    return tuple(families)


def _sanitize_non_finite(value: Any) -> Any:
    if isinstance(value, float):
        if np.isnan(value):
            return "__nan__"
        if np.isposinf(value):
            return "__inf__"
        if np.isneginf(value):
            return "__-inf__"
        return value
    if isinstance(value, Mapping):
        return {str(key): _sanitize_non_finite(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_non_finite(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_non_finite(item) for item in value]
    return value


def _filter_truth_registry(
    spec: SyntheticWorldDGP, registry: Mapping[str, Mapping[str, Any]]
) -> dict[str, dict[str, Any]]:
    truth_spec = spec.truth
    extra_targets = set(truth_spec.extra_targets)
    filtered: dict[str, dict[str, Any]] = {}
    for key, payload in registry.items():
        prefix = key.split(".", 1)[0]
        include_flag_name = _TRUTH_PREFIX_FLAGS.get(prefix)
        include_flag = (
            True if include_flag_name is None else bool(getattr(truth_spec, include_flag_name))
        )
        if include_flag or key in extra_targets:
            filtered[key] = dict(payload)
    return filtered


class SyntheticWorld:
    """Materialized synthetic world with a truth-centric API."""

    def __init__(self, spec: SyntheticWorldDGP) -> None:
        self.spec = spec
        self._materialized = self._materialize()

    @classmethod
    def from_spec(cls, spec: SyntheticWorldDGP) -> SyntheticWorld:
        return cls(spec)

    @classmethod
    def from_yaml(cls, path: str | Path, *, seed: int | None = None) -> SyntheticWorld:
        return cls(SyntheticWorldDGP.from_path(path, seed=seed))

    def _materialize(self) -> MaterializedWorldPayload:
        try:
            builder = _TEMPLATE_REGISTRY[self.spec.family]
        except KeyError as exc:
            raise ValueError(f"Unsupported world family: {self.spec.family}") from exc
        payload = builder(self.spec)
        return MaterializedWorldPayload(
            latent_table=payload.latent_table,
            observed_table=payload.observed_table,
            truth_registry=_filter_truth_registry(self.spec, payload.truth_registry),
            metadata=payload.metadata,
            splits=payload.splits,
        )

    def sample(
        self,
        *,
        split: str = "train",
        n: int | None = None,
        observed: bool = True,
        format: str = "python",
    ) -> SyntheticWorldSample | list[dict[str, Any]] | Any:
        if format not in {"python", "records", "pandas", "parquet"}:
            raise ValueError(
                "SyntheticWorld.sample supports format='python', 'records', 'pandas', or 'parquet'"
            )

        table = self._materialized.observed_table if observed else self._materialized.latent_table
        rows = self._materialized.splits.get(split)
        if rows is None:
            raise KeyError(
                f"Unknown split {split!r}; expected one of {sorted(self._materialized.splits)}"
            )
        if n is not None:
            rows = rows[: max(0, min(int(n), rows.shape[0]))]
        sliced = _table_slice(table, rows)
        metadata = {
            **self._materialized.metadata,
            "observed": bool(observed),
            "requested_format": format,
        }

        if format == "records":
            keys = list(sliced)
            records: list[dict[str, Any]] = []
            for row_idx in range(rows.shape[0]):
                records.append({key: json_safe(np.asarray(sliced[key])[row_idx]) for key in keys})
            return records
        if format == "pandas":
            import pandas as pd

            return pd.DataFrame({key: np.asarray(values) for key, values in sliced.items()})
        if format == "parquet":
            buffer = BytesIO()
            try:
                import pyarrow as pa
                import pyarrow.parquet as pq

                table_payload = pa.table(
                    {key: np.asarray(values) for key, values in sliced.items()}
                )
                pq.write_table(table_payload, buffer)
            except ModuleNotFoundError:
                fallback_payload = {
                    "columns": {key: np.asarray(values).tolist() for key, values in sliced.items()},
                    "row_count": int(rows.shape[0]),
                }
                buffer.write(
                    to_canonical_bytes(
                        _sanitize_non_finite(fallback_payload), spec=CanonSpec(forbid_floats=False)
                    )
                )
                metadata["serialization_fallback"] = "canonical_json_bytes"
            return SyntheticWorldSample(
                world_id=self.spec.world_id,
                family=self.spec.family,
                split=split,
                seed=self.spec.seed,
                config_hash=self.spec.config_hash(),
                row_count=int(rows.shape[0]),
                format=format,
                columns={"parquet_bytes": buffer.getvalue()},
                metadata=metadata,
            )
        return SyntheticWorldSample(
            world_id=self.spec.world_id,
            family=self.spec.family,
            split=split,
            seed=self.spec.seed,
            config_hash=self.spec.config_hash(),
            row_count=int(rows.shape[0]),
            format=format,
            columns=sliced,
            metadata=metadata,
        )

    def truth(
        self,
        *,
        targets: Iterable[str] | None = None,
        prefixes: Iterable[str] | None = None,
        subset: Mapping[str, Any] | None = None,
    ) -> TruthManifest:
        query = TruthQuery(
            targets=tuple(str(item) for item in (targets or ())),
            prefixes=tuple(str(item) for item in (prefixes or ())),
            subset=dict(subset or {}),
        )
        selected = select_truth_targets(self._materialized.truth_registry, query)
        return TruthManifest(
            world_id=self.spec.world_id,
            family=self.spec.family,
            world_spec_version=self.spec.world_spec_version,
            truth_schema_version=self.spec.truth_schema_version,
            seed=self.spec.seed,
            config_hash=self.spec.config_hash(),
            truth_policy=self.spec.truth.model_dump(mode="python"),
            available_targets=tuple(sorted(self._materialized.truth_registry)),
            target_families=_target_families(self._materialized.truth_registry),
            targets=selected,
        )

    def artifact(self, *, split: str = "train") -> WorldArtifact:
        rows = self._materialized.splits.get(split)
        if rows is None:
            raise KeyError(f"Unknown split {split!r}")
        latent_slice = _table_slice(self._materialized.latent_table, rows)
        observed_slice = _table_slice(self._materialized.observed_table, rows)
        truth_manifest = self.truth()
        latent_hash = _hash_payload(latent_slice)
        observed_hash = _hash_payload(observed_slice)
        truth_hash = _hash_payload(truth_manifest.targets)
        return WorldArtifact(
            world_id=self.spec.world_id,
            family=self.spec.family,
            world_spec_version=self.spec.world_spec_version,
            truth_schema_version=self.spec.truth_schema_version,
            artifact_schema_version=self.spec.artifact_schema_version,
            seed=self.spec.seed,
            config_hash=self.spec.config_hash(),
            split=split,
            row_count=int(rows.shape[0]),
            observed_columns=tuple(sorted(self._materialized.observed_table)),
            available_targets=tuple(sorted(self._materialized.truth_registry)),
            latent_hash=latent_hash,
            observed_hash=observed_hash,
            truth_hash=truth_hash,
            replay_key=f"{self.spec.world_id}:{self.spec.world_spec_version}:{self.spec.seed}:{self.spec.config_hash()}",
            latent_artifact_ref=_artifact_ref("latent", latent_hash),
            observed_artifact_ref=_artifact_ref("observed", observed_hash),
            truth_artifact_ref=_artifact_ref("truth", truth_hash),
            metadata=self._materialized.metadata,
        )

    def evaluate(
        self,
        *,
        predictions: Mapping[str, Any],
        metrics: str | Iterable[str] = "default",
        hooks: Iterable[str] | None = None,
    ) -> EvaluationRun:
        resolved_hooks = tuple(str(item) for item in (hooks or self.spec.evaluation.default_hooks))
        truth_manifest = self.truth(targets=predictions.keys())
        metric_payload: dict[str, float] = {}
        diagnostics: dict[str, Any] = {}
        plots: dict[str, Any] = {}

        if metrics == "default":
            resolved_metric_set = self.spec.evaluation.default_metric_set
            allowed_metrics: set[str] | None = None
        elif isinstance(metrics, str):
            resolved_metric_set = metrics
            allowed_metrics = {metrics}
        else:
            allowed_metrics = {str(item) for item in metrics}
            resolved_metric_set = ",".join(sorted(allowed_metrics))
        for target, prediction in predictions.items():
            truth_payload = truth_manifest.targets[target]
            resolved_prediction = prediction
            if (
                target == "ml.classification.probability"
                and isinstance(prediction, Mapping)
                and "labels" not in prediction
                and "ml.classification.label" in self._materialized.truth_registry
            ):
                resolved_prediction = {
                    **prediction,
                    "labels": self._materialized.truth_registry["ml.classification.label"][
                        "values"
                    ],
                }
            target_metrics, target_diagnostics = evaluate_prediction(
                target_name=target,
                truth_payload=truth_payload,
                prediction=resolved_prediction,
            )
            for metric_name, value in target_metrics.items():
                qualified_name = f"{target}.{metric_name}"
                if (
                    allowed_metrics is None
                    or metric_name in allowed_metrics
                    or qualified_name in allowed_metrics
                ):
                    metric_payload[qualified_name] = float(value)
            diagnostics[target] = {
                **target_diagnostics,
                **build_hook_diagnostics(
                    hooks=resolved_hooks,
                    target_name=target,
                    truth_payload=truth_payload,
                    prediction=resolved_prediction,
                    metrics=target_metrics,
                ),
            }
            plot_specs = build_plot_specs(
                target_name=target,
                truth_payload=truth_payload,
                prediction=resolved_prediction,
            )
            if plot_specs:
                plots[target] = plot_specs

        return EvaluationRun(
            world_id=self.spec.world_id,
            queried_targets=tuple(str(key) for key in predictions),
            metric_set=resolved_metric_set,
            metrics=metric_payload,
            evaluation_policy=self.spec.evaluation.model_dump(mode="python"),
            diagnostics=diagnostics,
            hooks=resolved_hooks,
            plots=plots,
        )


def phase0_seed_world_specs() -> tuple[SyntheticWorldDGP, ...]:
    """Default Phase-0 seed worlds spanning the required DGP classes."""
    return (
        SyntheticWorldDGP(
            world_id="sw.phase0.cross_sectional.calibrated.v1",
            family=WorldFamily.CROSS_SECTIONAL,
            seed=20260421,
            n_units=180,
            n_features=4,
            truth={"posterior_mode": "exact_posterior"},
            missingness={
                "mechanism": MissingnessMechanism.MAR,
                "rate": 0.07,
                "strength": 0.9,
                "targets": ("outcome", "feature_0"),
            },
            measurement={
                "kind": MeasurementErrorKind.CLASSICAL_ADDITIVE,
                "scale": 0.08,
                "targets": ("outcome", "feature_0", "feature_1"),
            },
            sampling={"kind": SamplingDesignKind.BERNOULLI, "inclusion_rate": 0.85},
            metadata={"phase": "phase0", "calibrated_world": True},
        ),
        SyntheticWorldDGP(
            world_id="sw.phase0.survey_repeated_cs.seed.v1",
            family=WorldFamily.SURVEY_REPEATED_CROSS_SECTION,
            seed=20260424,
            n_units=220,
            n_features=4,
            n_waves=4,
            n_strata=5,
            n_clusters=10,
            truth={"posterior_mode": "reference_posterior"},
            missingness={
                "mechanism": MissingnessMechanism.MAR,
                "rate": 0.05,
                "targets": ("outcome", "feature_0"),
            },
            measurement={
                "kind": MeasurementErrorKind.CLASSICAL_ADDITIVE,
                "scale": 0.06,
                "targets": ("outcome", "feature_0"),
            },
            sampling={
                "kind": SamplingDesignKind.STRATIFIED,
                "inclusion_rate": 0.7,
                "response_rate": 0.82,
                "n_strata": 5,
                "n_clusters": 10,
                "calibrate_weights": True,
            },
            intervention={"style": "survey_wave", "treatment_share": 0.5},
            metadata={"phase": "phase0"},
        ),
        SyntheticWorldDGP(
            world_id="sw.phase0.panel_dynamic.seed.v1",
            family=WorldFamily.PANEL_DYNAMIC,
            seed=20260422,
            n_units=72,
            n_features=3,
            n_periods=9,
            truth={"posterior_mode": "reference_posterior"},
            missingness={
                "mechanism": MissingnessMechanism.MCAR,
                "rate": 0.04,
                "targets": ("outcome",),
            },
            measurement={
                "kind": MeasurementErrorKind.CLASSICAL_ADDITIVE,
                "scale": 0.05,
                "targets": ("outcome",),
            },
            sampling={"kind": SamplingDesignKind.BERNOULLI, "inclusion_rate": 0.9},
            intervention={"style": "dynamic", "treatment_start_period": 4},
            metadata={"phase": "phase0"},
        ),
        SyntheticWorldDGP(
            world_id="sw.phase0.spatio_temporal.seed.v1",
            family=WorldFamily.SPATIO_TEMPORAL,
            seed=20260423,
            n_regions=10,
            n_periods=8,
            truth={"posterior_mode": "reference_posterior"},
            missingness={
                "mechanism": MissingnessMechanism.MCAR,
                "rate": 0.03,
                "targets": ("outcome",),
            },
            measurement={"kind": MeasurementErrorKind.NONE},
            sampling={"kind": SamplingDesignKind.BERNOULLI, "inclusion_rate": 0.95},
            intervention={"style": "spatial", "treatment_start_period": 4},
            metadata={"phase": "phase0"},
        ),
    )


def phase0_seed_benchmark_binding() -> BenchmarkSuiteBinding:
    """Benchmark-harness binding for the synthetic-world seed suite."""
    specs = phase0_seed_world_specs()
    return BenchmarkSuiteBinding(
        suite_id="synthetic_world_seed",
        benchmark_family="synthetic_world",
        case_ids=(
            "synthetic_world::cross_sectional_seed",
            "synthetic_world::survey_repeated_cs_seed",
            "synthetic_world::panel_dynamic_seed",
            "synthetic_world::spatio_temporal_seed",
        ),
        world_ids=tuple(spec.world_id for spec in specs),
    )


__all__ = [
    "SyntheticWorld",
    "phase0_seed_benchmark_binding",
    "phase0_seed_world_specs",
]
