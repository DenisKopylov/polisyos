"""Replay historical validation plans and aggregate trust calibration/audit outputs."""

from __future__ import annotations

import json
import math
import uuid
from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from enum import Enum
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import numpy as np

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.ir_adapter import (
    CoreToIRArtifactStoreAdapter,
    build_ir_artifact_store,
    ensure_ir_artifact_store,
)
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.ir.analytics.backtest import (
    BacktestReport,
    BacktestScenario,
    BiasDirection,
    SystematicBias,
    persist_backtest_report,
)
from polisyos.ir.analytics.uncertainty import (
    IntervalSemantics,
    UncertaintyEnvelope,
    UncertaintySource,
    combine_envelopes,
)
from polisyos.ir.artifacts import InputRef, normalize_input_refs, put_json_artifact
from polisyos.ir.model_layer.canon import CanonSpec as IRCanonSpec
from polisyos.scientist import run_experiment
from polisyos.scientist.methods.backtesting.evaluator import PredictionEvaluator
from polisyos.scientist.methods.backtesting.masking import OutcomeMasker
from polisyos.scientist.methods.backtesting.plan import (
    ForecastProfileContract,
    HistoricalValidationPlan,
    PredictionSource,
)
from polisyos.scientist.methods.backtesting.trust_scorer import TrustScorer

if TYPE_CHECKING:
    from polisyos.core.artifacts.protocol import ArtifactStore as CoreArtifactStore
    from polisyos.ir.artifacts import ArtifactStore as IRArtifactStore

    type BacktestStore = IRArtifactStore | CoreArtifactStore
else:
    BacktestStore = Any


BacktestStoreFactory = Callable[[Path], BacktestStore]


class TrustScreeningMode(str, Enum):
    """Typed, downward-only trust limitation applied to a backtest report."""

    DEFAULT = "default"
    PREDICTIVE_ONLY_BRIDGE_PENDING = "predictive_only_bridge_pending"


@dataclass(frozen=True)
class _TTestResult:
    """Keep descriptive diagnostics separate from statistical test status."""

    p_value: float | None
    test_name: str | None
    status: str
    reason: str | None = None


def _default_backtest_store_factory(root: Path) -> BacktestStore:
    return build_ir_artifact_store(root)


def _consistent_plan_refs(
    plans: Sequence[HistoricalValidationPlan],
) -> tuple[str | None, str | None, str | None]:
    """Resolve one model/policy pair without mixing aggregate inputs."""
    pairs = {(plan.model_spec_ref, plan.policy_spec_ref) for plan in plans}
    if not pairs or pairs == {(None, None)}:
        return None, None, None

    if len(pairs) == 1:
        model_spec_ref, policy_spec_ref = next(iter(pairs))
        if model_spec_ref is None or policy_spec_ref is None:
            return (
                None,
                None,
                "model_spec_ref/policy_spec_ref is incomplete across aggregated plans",
            )
        return model_spec_ref, policy_spec_ref, None

    return (
        None,
        None,
        "model_spec_ref/policy_spec_ref is inconsistent across aggregated plans",
    )


def _validate_report_id(report_id: object, *, field: str = "report_id") -> str:
    """Validate an externally allocated report identity without rewriting it."""
    if not isinstance(report_id, str) or not report_id:
        raise ValueError(f"{field} must be a non-empty string")
    if report_id != report_id.strip():
        raise ValueError(f"{field} must not have leading or trailing whitespace")
    if any(ord(char) < 0x20 or ord(char) == 0x7F for char in report_id):
        raise ValueError(f"{field} must not contain control characters")
    return report_id


def _resolve_report_id(
    report_id: str | None,
    *,
    generated_prefix: str,
    metadata: Mapping[str, Any] | None = None,
) -> str:
    """Resolve one report identity and reject a second conflicting declaration."""
    metadata_report_id: str | None = None
    if metadata is not None and "report_id" in metadata:
        metadata_report_id = _validate_report_id(
            metadata["report_id"],
            field="metadata.report_id",
        )
    if report_id is None:
        return metadata_report_id or f"{generated_prefix}{uuid.uuid4().hex[:12]}"
    resolved = _validate_report_id(report_id)
    if metadata_report_id is not None and metadata_report_id != resolved:
        raise ValueError(
            "conflicting report_id declarations between the explicit report_id "
            "and metadata.report_id"
        )
    return resolved


def _normalize_manifest_inputs(inputs: Sequence[Any] | None) -> list[InputRef] | None:
    """Validate explicit report lineage edges before executing a backtest."""
    if inputs is None:
        return None
    for item in inputs:
        if isinstance(item, Mapping):
            has_artifact_id = "artifact_id" in item
            has_role = "role" in item
        else:
            has_artifact_id = getattr(item, "artifact_id", None) is not None
            has_role = getattr(item, "role", None) is not None
        if not has_artifact_id or not has_role:
            raise ValueError("manifest inputs must provide both artifact_id and role")
    try:
        normalized = normalize_input_refs(inputs)
    except (TypeError, ValueError) as exc:
        raise ValueError("manifest inputs must contain typed artifact references") from exc

    seen_pairs: set[tuple[str, str]] = set()
    for item in normalized:
        role = item.role
        if (
            not role
            or role != role.strip()
            or any(ord(char) < 0x20 or ord(char) == 0x7F for char in role)
        ):
            raise ValueError("manifest input role must be a non-empty clean string")
        pair = (str(item.artifact_id), role)
        if pair in seen_pairs:
            raise ValueError("duplicate manifest input role/artifact pair is not allowed")
        seen_pairs.add(pair)
    return normalized


def _resolve_manifest_inputs(
    store: BacktestStore,
    inputs: Sequence[Any] | None,
) -> list[InputRef] | None:
    """Resolve explicit lineage edges in the configured CAS before execution."""
    normalized = _normalize_manifest_inputs(inputs)
    if normalized is None:
        return None
    for item in normalized:
        try:
            manifest = store.get_manifest(item.artifact_id)
            manifest_artifact_id = getattr(manifest, "artifact_id", None)
            if str(manifest_artifact_id) != str(item.artifact_id):
                raise ValueError("manifest identity does not match the requested artifact")
            store.get_bytes(item.artifact_id)
        except Exception as exc:
            raise ValueError(
                "manifest input artifact cannot be resolved in the configured CAS: "
                f"{item.artifact_id}"
            ) from exc
    return normalized


class BacktestOrchestrator:
    """Run scenario replay, score prediction quality, and persist a `BacktestReport`.

    The orchestrator separates masking/evaluation from the prediction source:
    plans may provide forecasts directly, ask Scientist to replay a workflow, or
    fall back to a naive baseline. Degraded Scientist predictions are surfaced in
    report metadata so trust scoring and calibration governance can audit replay
    quality.
    """

    def __init__(
        self,
        *,
        cas: BacktestStore | None = None,
        cas_root: str = ".polisyos/cas",
        store_factory: BacktestStoreFactory | None = None,
    ) -> None:
        if cas is not None:
            self._store = ensure_ir_artifact_store(cas)
        else:
            factory = store_factory or _default_backtest_store_factory
            self._store = ensure_ir_artifact_store(factory(Path(cas_root)))
        self._scientist_store = (
            self._store.store
            if isinstance(self._store, CoreToIRArtifactStoreAdapter)
            else self._store
        )
        self._masker = OutcomeMasker()
        self._evaluator = PredictionEvaluator()
        self._trust_scorer = TrustScorer()

    def run(
        self,
        plans: list[HistoricalValidationPlan],
        *,
        report_id: str | None = None,
        inputs: Sequence[InputRef] | None = None,
        metadata: dict[str, Any] | None = None,
        trust_screening: TrustScreeningMode = TrustScreeningMode.DEFAULT,
    ) -> BacktestReport:
        """Execute every historical plan and persist the aggregated report in CAS.

        ``report_id`` and ``inputs`` are caller-owned handoff values.  When they
        are absent, the historical generated-ID and empty-lineage behavior is
        retained; plan fields are never promoted into manifest inputs.  Input
        roles and content/schema semantics remain the caller's explicit
        contract; this owner resolves only the exact refs in its configured CAS.
        """
        resolved_report_id = _resolve_report_id(
            report_id,
            generated_prefix="BT_",
            metadata=metadata,
        )
        try:
            resolved_trust_screening = TrustScreeningMode(trust_screening)
        except (TypeError, ValueError) as exc:
            raise ValueError("trust_screening must be a supported typed mode") from exc
        manifest_inputs = _resolve_manifest_inputs(self._store, inputs)
        scenarios: list[BacktestScenario] = []
        warnings: list[str] = []
        requested_modes: list[str] = []
        effective_modes: list[str] = []
        degraded_reasons: list[str] = []

        replay_plans: list[HistoricalValidationPlan] = []
        for plan in plans:
            expanded = self._expand_replay_plans(plan)
            replay_plans.extend(expanded)

        for plan in replay_plans:
            (
                scenario,
                scenario_warnings,
                prediction_mode_requested,
                prediction_mode_effective,
                scenario_degraded_reasons,
            ) = self._run_single_scenario(plan)
            scenarios.append(scenario)
            warnings.extend([f"{plan.plan_id}: {item}" for item in scenario_warnings])
            requested_modes.append(prediction_mode_requested)
            effective_modes.append(prediction_mode_effective)
            degraded_reasons.extend(
                [f"{plan.plan_id}: {item}" for item in scenario_degraded_reasons]
            )

        report = self._aggregate(
            report_id=resolved_report_id,
            scenarios=scenarios,
            plans=replay_plans,
            metadata={
                **(metadata or {}),
                "warnings": warnings,
            },
            prediction_mode_requested=_collapse_modes(requested_modes),
            prediction_mode_effective=_collapse_modes(effective_modes),
            degraded_reasons=degraded_reasons,
            trust_screening=resolved_trust_screening,
        )
        ref = persist_backtest_report(self._store, report, inputs=manifest_inputs)
        report.cas_artifact_id = str(ref.artifact_id)
        return report

    @staticmethod
    def _expand_replay_plans(
        plan: HistoricalValidationPlan,
    ) -> list[HistoricalValidationPlan]:
        """Resolve requested Scientist replays into scalar, separately seeded plans."""
        count = (
            plan.n_simulation_runs if plan.prediction_source is PredictionSource.SCIENTIST else 1
        )
        streams = np.random.SeedSequence(plan.random_seed).spawn(count) if count > 1 else []
        return [
            plan.model_copy(
                deep=True,
                update={
                    "plan_id": f"{plan.plan_id}:replica:{index}" if count > 1 else plan.plan_id,
                    "n_simulation_runs": 1,
                    "random_seed": (
                        int(streams[index].generate_state(1)[0]) if streams else plan.random_seed
                    ),
                    "scientist_state": (
                        deepcopy(
                            {
                                **plan.scientist_state,
                                "run_id": f"{plan.scientist_state['run_id']}:replica:{index}",
                            }
                        )
                        if count > 1 and plan.scientist_state and plan.scientist_state.get("run_id")
                        else deepcopy(plan.scientist_state)
                    ),
                    "metadata": {
                        **plan.metadata,
                        "source_plan_id": plan.plan_id,
                        "replica_index": index,
                        "replica_count": count,
                        "declared_n_simulation_runs": plan.n_simulation_runs,
                    },
                },
            )
            for index in range(count)
        ]

    def _run_single_scenario(
        self,
        plan: HistoricalValidationPlan,
    ) -> tuple[BacktestScenario, list[str], str, str, list[str]]:
        warnings: list[str] = []
        historical_data = self._load_historical_data(plan)
        masked_data = self._masker.mask(historical_data, plan)

        prediction_payload = self._predict(plan, masked_data)
        if prediction_payload.get("warnings"):
            warnings.extend(prediction_payload["warnings"])
        degraded_reasons = [
            str(item)
            for item in prediction_payload.get("degraded_reasons", [])
            if isinstance(item, str)
        ]
        y_pred = prediction_payload["predictions"]
        intervals = prediction_payload.get("intervals")
        scenario_metadata = {
            **plan.metadata,
            "prediction_source_requested": plan.prediction_source.value,
            "prediction_source_effective": prediction_payload.get(
                "prediction_mode_effective",
                plan.prediction_source.value,
            ),
            "degraded": bool(prediction_payload.get("degraded", False)),
            "requested_replay_seed": plan.random_seed,
            "source_plan_id": plan.metadata.get("source_plan_id", plan.plan_id),
            "backend_attempted": bool(prediction_payload.get("backend_attempted", False)),
            "backend_run_id": prediction_payload.get("backend_run_id"),
        }
        if "historical_snapshot_ref" in prediction_payload:
            scenario_metadata["historical_snapshot_ref"] = prediction_payload[
                "historical_snapshot_ref"
            ]
        if "interval_type" in prediction_payload:
            scenario_metadata["interval_type"] = prediction_payload["interval_type"]
        if "interval_metadata_source" in prediction_payload:
            scenario_metadata["interval_metadata_source"] = prediction_payload[
                "interval_metadata_source"
            ]
        confidence_level = prediction_payload.get("confidence_level", plan.confidence_level)

        scenario = self._evaluator.evaluate(
            scenario_id=plan.plan_id,
            scenario_label=plan.plan_label or plan.plan_id,
            y_pred=y_pred,
            y_true=plan.ground_truth_outcomes,
            intervals=intervals,
            confidence_level=confidence_level,
            jurisdiction=plan.jurisdiction,
            intervention_date=plan.intervention_date,
            data_source=plan.historical_data_ref or plan.historical_data_path or "",
            metadata=scenario_metadata,
        )
        return (
            scenario,
            warnings,
            plan.prediction_source.value,
            str(prediction_payload.get("prediction_mode_effective", plan.prediction_source.value)),
            degraded_reasons,
        )

    def _load_historical_data(self, plan: HistoricalValidationPlan) -> dict[str, Any]:
        if plan.historical_data_ref:
            artifact_id = ArtifactID.model_validate(plan.historical_data_ref)
            payload = from_canonical_bytes(self._store.get_bytes(artifact_id))
            if not isinstance(payload, dict):
                raise ValueError(
                    f"historical_data_ref must point to a JSON object: {plan.historical_data_ref}"
                )
            return cast("dict[str, Any]", payload)
        assert plan.historical_data_path is not None
        file_payload = json.loads(Path(plan.historical_data_path).read_text(encoding="utf-8"))
        if not isinstance(file_payload, dict):
            raise ValueError(
                f"historical_data_path must contain a JSON object: {plan.historical_data_path}"
            )
        return cast("dict[str, Any]", file_payload)

    def _predict(
        self,
        plan: HistoricalValidationPlan,
        masked_data: dict[str, Any],
    ) -> dict[str, Any]:
        if plan.prediction_source is PredictionSource.PROVIDED:
            return {
                "predictions": plan.predicted_outcomes or {},
                "intervals": plan.prediction_intervals or {},
                "warnings": [],
                "prediction_mode_effective": PredictionSource.PROVIDED.value,
                "degraded": False,
                "degraded_reasons": [],
            }
        if plan.prediction_source is PredictionSource.SCIENTIST:
            return self._predict_with_scientist(plan, masked_data)
        naive = self._predict_with_naive(plan, masked_data)
        naive["prediction_mode_effective"] = PredictionSource.NAIVE.value
        naive["degraded"] = False
        naive["degraded_reasons"] = []
        return naive

    def _predict_with_scientist(
        self,
        plan: HistoricalValidationPlan,
        masked_data: dict[str, Any],
    ) -> dict[str, Any]:
        if plan.n_simulation_runs != 1:
            raise ValueError("Scientist dispatch requires one expanded scalar replay plan")
        warnings: list[str] = []
        if plan.scientist_state is None:
            reason = "scientist_state_missing"
            warnings.append("scientist_state missing; using naive predictor fallback")
            naive = self._predict_with_naive(plan, masked_data)
            naive["warnings"] = warnings + naive.get("warnings", [])
            naive["prediction_mode_effective"] = PredictionSource.NAIVE.value
            naive["degraded"] = True
            naive["degraded_reasons"] = [reason]
            return naive

        if not self._has_declared_temporal_boundary(plan):
            reason = "scientist_historical_cutoff_missing"
            warnings.append("scientist historical cutoff missing; using naive fallback")
            naive = self._predict_with_naive(plan, masked_data)
            naive["warnings"] = warnings + naive.get("warnings", [])
            naive["prediction_mode_effective"] = PredictionSource.NAIVE.value
            naive["degraded"] = True
            naive["degraded_reasons"] = [reason]
            return naive

        state_payload = dict(plan.scientist_state)
        params = dict(state_payload.get("params", {}))
        if plan.random_seed is not None:
            params["random_seed"] = plan.random_seed
        params["n_simulation_runs"] = plan.n_simulation_runs
        state_payload["params"] = params
        inputs = state_payload.get("inputs", {})
        if not isinstance(inputs, dict):
            raise ValueError("scientist_state.inputs must be an object when provided")
        inputs = dict(inputs)
        inputs["data_snapshot_ref"] = self._persist_masked_view(plan, masked_data)
        state_payload["inputs"] = inputs

        try:
            result = run_experiment(state_payload, store=self._scientist_store)
        except Exception as exc:
            reason = f"scientist_execution_failed:{type(exc).__name__}"
            naive = self._predict_with_naive(plan, masked_data)
            naive.update(
                warnings=[reason, *naive.get("warnings", [])],
                prediction_mode_effective=PredictionSource.NAIVE.value,
                degraded=True,
                degraded_reasons=[reason],
                historical_snapshot_ref=inputs["data_snapshot_ref"],
                backend_attempted=True,
                backend_run_id=state_payload.get("run_id"),
            )
            return naive
        backend_run_id = (
            result.get("run_id", state_payload.get("run_id"))
            if isinstance(result, dict)
            else state_payload.get("run_id")
        )
        artifacts = result.get("artifacts_index", {}) if isinstance(result, dict) else {}
        if not isinstance(artifacts, dict):
            reason = "scientist_artifacts_index_missing"
            warnings.append("scientist result has no artifacts_index; using naive fallback")
            naive = self._predict_with_naive(plan, masked_data)
            naive["warnings"] = warnings + naive.get("warnings", [])
            naive["prediction_mode_effective"] = PredictionSource.NAIVE.value
            naive["degraded"] = True
            naive["degraded_reasons"] = [reason]
            naive["historical_snapshot_ref"] = inputs["data_snapshot_ref"]
            naive["backend_attempted"] = True
            naive["backend_run_id"] = backend_run_id
            return naive

        metrics_ref_payload = artifacts.get("metrics_ref")
        predictions: dict[str, list[float]] = {}
        if isinstance(metrics_ref_payload, dict) and metrics_ref_payload.get("artifact_id"):
            try:
                artifact_id = ArtifactID.model_validate(metrics_ref_payload["artifact_id"])
                metrics_payload = from_canonical_bytes(self._store.get_bytes(artifact_id))
                values = metrics_payload.get("values", metrics_payload)
                if isinstance(values, dict):
                    for metric in plan.target_metrics:
                        raw = values.get(metric)
                        horizon = len(plan.ground_truth_outcomes.get(metric, []))
                        constant_profile = self._is_constant_forecast(
                            metrics_payload,
                            artifact_id,
                            horizon,
                        )
                        if isinstance(raw, list):
                            if len(raw) != horizon:
                                warnings.append(
                                    f"scientist trajectory for '{metric}' has length "
                                    f"{len(raw)}; expected {horizon}"
                                )
                                continue
                            try:
                                predictions[metric] = [float(item) for item in raw]
                            except (TypeError, ValueError):
                                warnings.append(
                                    f"scientist trajectory for '{metric}' is not numeric"
                                )
                        elif (
                            isinstance(raw, (int, float))
                            and not isinstance(raw, bool)
                            and constant_profile
                        ):
                            predictions[metric] = [float(raw)] * horizon
                        elif isinstance(raw, (int, float)) and not isinstance(raw, bool):
                            warnings.append(
                                f"scientist scalar for '{metric}' lacks constant_forecast profile"
                            )
            except Exception as exc:
                warnings.append(f"failed to parse scientist metrics output: {exc}")

        intervals, interval_metadata, interval_degraded_reasons = (
            self._extract_intervals_from_simulation_result(artifacts, plan)
        )
        if set(predictions) != set(plan.target_metrics):
            reason = "scientist_predictions_missing"
            warnings.append("scientist predictions missing; using naive fallback")
            naive = self._predict_with_naive(plan, masked_data)
            naive["warnings"] = warnings + naive.get("warnings", [])
            naive["prediction_mode_effective"] = PredictionSource.NAIVE.value
            naive["degraded"] = True
            naive["degraded_reasons"] = [reason]
            naive["historical_snapshot_ref"] = inputs["data_snapshot_ref"]
            naive["backend_attempted"] = True
            naive["backend_run_id"] = backend_run_id
            return naive
        result = {
            "predictions": predictions,
            "intervals": intervals,
            "warnings": warnings + list(interval_degraded_reasons),
            "prediction_mode_effective": PredictionSource.SCIENTIST.value,
            "degraded": bool(interval_degraded_reasons),
            "degraded_reasons": list(interval_degraded_reasons),
            "historical_snapshot_ref": inputs["data_snapshot_ref"],
            "backend_attempted": True,
            "backend_run_id": backend_run_id,
        }
        result.update(interval_metadata)
        return result

    def _extract_intervals_from_simulation_result(
        self,
        artifacts: dict[str, Any],
        plan: HistoricalValidationPlan,
    ) -> tuple[dict[str, list[tuple[float, float]]], dict[str, Any], tuple[str, ...]]:
        sim_ref_payload = artifacts.get("simulation_result_ref")
        if not isinstance(sim_ref_payload, dict) or not sim_ref_payload.get("artifact_id"):
            return {}, {}, ()

        try:
            sim_id = ArtifactID.model_validate(sim_ref_payload["artifact_id"])
            sim_payload = from_canonical_bytes(self._store.get_bytes(sim_id))
        except Exception:
            return {}, {}, ()
        if not isinstance(sim_payload, Mapping):
            return {}, {}, ()
        envelopes = sim_payload.get("uncertainty_envelopes")
        if not isinstance(envelopes, dict):
            return {}, {}, ()

        intervals: dict[str, list[tuple[float, float]]] = {}
        envelope_metadata: list[tuple[float | None, str | None]] = []
        envelope_contracts: list[UncertaintyEnvelope] = []
        legacy_metadata_seen = False
        metadata_errors: list[str] = []
        for metric in plan.target_metrics:
            ref_payload = envelopes.get(metric)
            if not isinstance(ref_payload, dict) or not ref_payload.get("artifact_id"):
                continue
            try:
                env_id = ArtifactID.model_validate(ref_payload["artifact_id"])
                env_payload = from_canonical_bytes(self._store.get_bytes(env_id))
                if not isinstance(env_payload, Mapping):
                    raise TypeError("uncertainty envelope payload must be an object")
                metadata_declared, confidence_level, interval_type, envelope_contract = (
                    self._resolve_persisted_interval_metadata(env_payload)
                )
                if metadata_declared:
                    envelope_metadata.append((confidence_level, interval_type))
                    assert envelope_contract is not None
                    envelope_contracts.append(envelope_contract)
                else:
                    legacy_metadata_seen = True
                horizon = len(plan.ground_truth_outcomes.get(metric, []))
                ci = env_payload.get("confidence_intervals", env_payload.get("confidence_interval"))
                if isinstance(ci, (list, tuple)) and ci and isinstance(ci[0], (list, tuple)):
                    if len(ci) != horizon:
                        continue
                    parsed = [self._parse_interval(item) for item in ci]
                    if all(item is not None for item in parsed):
                        intervals[metric] = cast(
                            "list[tuple[float, float]]",
                            parsed,
                        )
                elif isinstance(ci, (list, tuple)) and len(ci) == 2:
                    if (
                        not self._is_constant_forecast(env_payload, env_id, horizon)
                        and horizon != 1
                    ):
                        continue
                    parsed_interval = self._parse_interval(ci)
                    if parsed_interval is not None:
                        intervals[metric] = [parsed_interval] * horizon
            except (TypeError, ValueError, KeyError):
                if isinstance(ref_payload, dict) and ref_payload.get("artifact_id"):
                    metadata_errors.append("uncertainty_envelope_metadata_invalid")
                continue
        if envelope_metadata and legacy_metadata_seen:
            metadata_errors.append("uncertainty_envelope_metadata_incomplete")
        if len(envelope_contracts) > 1:
            try:
                combine_envelopes(envelope_contracts)
            except ValueError:
                metadata_errors.append("uncertainty_envelope_metadata_incompatible")
        if metadata_errors:
            intervals = {}

        interval_metadata: dict[str, Any] = {}
        if envelope_metadata and not metadata_errors:
            confidence_level, interval_type = envelope_metadata[0]
            interval_metadata = {
                "confidence_level": confidence_level,
                "interval_type": interval_type,
                "interval_metadata_source": "persisted_envelope",
            }
        elif legacy_metadata_seen and not envelope_metadata:
            # Legacy CAS envelopes predate persisted interval identity. Keep
            # the plan's configured level (the package default is 0.95), but
            # expose that the evaluator could not verify it from the envelope.
            interval_metadata["interval_metadata_source"] = "legacy_plan_default"
        return intervals, interval_metadata, tuple(dict.fromkeys(metadata_errors))

    @staticmethod
    def _resolve_persisted_interval_metadata(
        payload: Mapping[str, Any],
    ) -> tuple[bool, float | None, str | None, UncertaintyEnvelope | None]:
        """Validate persisted interval identity through the canonical IR contract."""
        metadata_keys = {"confidence_level", "interval_semantics", "interval_type"}
        if not metadata_keys.intersection(payload):
            return False, None, None, None

        canonical_fields = {"point_estimate", "confidence_interval", "source"}
        if canonical_fields.issubset(payload):
            envelope = UncertaintyEnvelope.model_validate(dict(payload))
            return (
                True,
                envelope.confidence_level,
                envelope.interval_semantics.value,
                envelope,
            )

        raw_semantics = payload.get("interval_semantics")
        raw_interval_type = payload.get("interval_type")
        if raw_semantics is not None and raw_interval_type is not None:
            try:
                if IntervalSemantics(raw_semantics) is not IntervalSemantics(raw_interval_type):
                    raise ValueError("uncertainty_envelope_semantics_mismatch")
            except (TypeError, ValueError) as exc:
                raise ValueError("uncertainty_envelope_interval_semantics_invalid") from exc
        raw_semantics = raw_semantics if raw_semantics is not None else raw_interval_type
        try:
            interval_semantics = IntervalSemantics(raw_semantics)
        except (TypeError, ValueError) as exc:
            raise ValueError("uncertainty_envelope_interval_semantics_invalid") from exc

        raw_intervals = payload.get("confidence_interval", payload.get("confidence_intervals"))
        representative_interval = raw_intervals
        if (
            isinstance(raw_intervals, (list, tuple))
            and raw_intervals
            and isinstance(raw_intervals[0], (list, tuple))
        ):
            representative_interval = raw_intervals[0]
        interval = BacktestOrchestrator._parse_interval(representative_interval)
        if interval is None:
            raise ValueError("uncertainty_envelope_interval_missing")

        envelope = UncertaintyEnvelope.model_validate(
            {
                "point_estimate": (interval[0] + interval[1]) / 2.0,
                "confidence_interval": interval,
                "confidence_level": payload.get("confidence_level"),
                "source": UncertaintySource.MANUAL,
                "interval_semantics": interval_semantics,
                "is_heuristic_ci": payload.get("is_heuristic_ci", False),
                "gate_eligible": payload.get("gate_eligible", True),
            }
        )
        return (
            True,
            envelope.confidence_level,
            envelope.interval_semantics.value,
            envelope,
        )

    def _is_constant_forecast(
        self,
        payload: Any,
        artifact_id: ArtifactID,
        horizon: int,
    ) -> bool:
        """Require a typed, producer-bound contract for constant trajectories."""
        if not isinstance(payload, dict) or payload.get("forecast_profile") != "constant_forecast":
            return False
        try:
            contract = ForecastProfileContract.model_validate(payload.get("forecast_contract"))
            manifest = self._store.get_manifest(artifact_id)
        except Exception:
            return False
        producer = manifest.producer
        if producer is None or contract.horizon != horizon:
            return False
        return (
            str(producer.component) == contract.producer.component
            and producer.version == contract.producer.version
        )

    @staticmethod
    def _has_declared_temporal_boundary(plan: HistoricalValidationPlan) -> bool:
        """Return whether a Scientist replay has an explicit bounded cutoff."""
        return (
            plan.intervention_step is not None
            or plan.pre_intervention_periods is not None
            or bool(plan.intervention_date)
        )

    @staticmethod
    def _parse_interval(value: Any) -> tuple[float, float] | None:
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            return None
        if isinstance(value[0], bool) or isinstance(value[1], bool):
            return None
        try:
            lo = float(value[0])
            hi = float(value[1])
        except (TypeError, ValueError):
            return None
        if lo > hi:
            lo, hi = hi, lo
        return lo, hi

    def _persist_masked_view(
        self,
        plan: HistoricalValidationPlan,
        masked_data: dict[str, Any],
    ) -> dict[str, str]:
        """Persist and bind the immutable masked view consumed by Scientist."""
        canon_spec = IRCanonSpec(forbid_floats=False, forbid_nan_inf=False)
        data_ref = put_json_artifact(
            self._store,
            masked_data,
            kind="scientist.backtest.masked_historical_view",
            schema_name="polisyos.scientist.backtesting.MaskedHistoricalView",
            schema_version="1.0",
            canon_spec=canon_spec,
        )
        lineage_inputs = [InputRef(artifact_id=data_ref["artifact_id"], role="masked_data")]
        if plan.historical_data_ref:
            try:
                lineage_inputs.append(
                    InputRef(artifact_id=plan.historical_data_ref, role="historical_data")
                )
            except ValueError:
                pass

        metadata = masked_data.get("_backtest_metadata", {})
        snapshot_stats: dict[str, int | str] = {}
        if isinstance(metadata, dict):
            strategy = metadata.get("masking_strategy")
            step = metadata.get("intervention_step")
            if isinstance(strategy, str):
                snapshot_stats["masking_strategy"] = strategy
            if isinstance(step, int):
                snapshot_stats["intervention_step"] = step
        snapshot = DataSnapshot(
            data_ref=data_ref,
            stats=snapshot_stats,
            notes=[
                "scientist.backtest.masked_historical_view",
                f"plan_id:{plan.plan_id}",
            ],
        )
        return put_json_artifact(
            self._store,
            snapshot.model_dump(mode="json"),
            kind="fabric.data_snapshot",
            schema_name="polisyos.core.DataSnapshot",
            schema_version="0.2.0",
            inputs=lineage_inputs,
            canon_spec=canon_spec,
        )

    def _predict_with_naive(
        self,
        plan: HistoricalValidationPlan,
        masked_data: dict[str, Any],
    ) -> dict[str, Any]:
        predictions: dict[str, list[float]] = {}
        warnings: list[str] = []
        for metric in plan.target_metrics:
            horizon = len(plan.ground_truth_outcomes.get(metric, []))
            series_raw = masked_data.get(metric)
            if not isinstance(series_raw, (list, tuple)):
                baseline = 0.0
                warnings.append(f"metric '{metric}' missing in historical data; baseline=0 used")
            else:
                series = np.asarray(series_raw, dtype=float)
                finite = series[np.isfinite(series)]
                if finite.size == 0:
                    baseline = 0.0
                    warnings.append(
                        f"metric '{metric}' has no finite pre-intervention values; baseline=0 used"
                    )
                elif finite.size == 1:
                    baseline = float(finite[-1])
                else:
                    baseline = float(np.mean(finite[-min(3, finite.size) :]))
            predictions[metric] = [baseline] * horizon
        return {"predictions": predictions, "intervals": {}, "warnings": warnings}

    def _aggregate(
        self,
        *,
        report_id: str,
        scenarios: list[BacktestScenario],
        plans: Sequence[HistoricalValidationPlan] = (),
        metadata: dict[str, Any],
        prediction_mode_requested: str | None,
        prediction_mode_effective: str | None,
        degraded_reasons: list[str],
        trust_screening: TrustScreeningMode = TrustScreeningMode.DEFAULT,
    ) -> BacktestReport:
        def sufficient_statistics(
            scenario: BacktestScenario,
        ) -> tuple[float, float, float, int, int]:
            if scenario.squared_error_sum is not None:
                squared_error_sum = float(scenario.squared_error_sum)
                absolute_error_sum = float(scenario.absolute_error_sum or 0.0)
                percentage_error_sum = float(scenario.percentage_error_sum or 0.0)
                compared_count = (
                    scenario.compared_count
                    if scenario.requested_count > 0
                    else len(scenario.outcome_comparisons)
                )
                percentage_error_count = scenario.percentage_error_count
                return (
                    squared_error_sum,
                    absolute_error_sum,
                    percentage_error_sum,
                    compared_count,
                    percentage_error_count,
                )

            squared_error_sum = sum(
                comparison.absolute_error**2 for comparison in scenario.outcome_comparisons
            )
            absolute_error_sum = sum(
                comparison.absolute_error for comparison in scenario.outcome_comparisons
            )
            percentage_errors = [
                comparison.relative_error * 100.0
                for comparison in scenario.outcome_comparisons
                if comparison.relative_error is not None
            ]
            return (
                float(squared_error_sum),
                float(absolute_error_sum),
                float(sum(percentage_errors)),
                len(scenario.outcome_comparisons),
                len(percentage_errors),
            )

        scenario_statistics = [sufficient_statistics(item) for item in scenarios]
        total_squared_error = sum(item[0] for item in scenario_statistics)
        total_absolute_error = sum(item[1] for item in scenario_statistics)
        total_percentage_error = sum(item[2] for item in scenario_statistics)
        total_compared = sum(item[3] for item in scenario_statistics)
        total_percentage_count = sum(item[4] for item in scenario_statistics)

        if total_compared > 0:
            overall_rmse = float(np.sqrt(total_squared_error / total_compared))
            overall_mae = float(total_absolute_error / total_compared)
        else:
            overall_rmse = None
            overall_mae = None
        overall_mape = (
            float(total_percentage_error / total_percentage_count)
            if total_percentage_count > 0
            else None
        )
        interval_evaluated = sum(item.interval_evaluated_count for item in scenarios)
        interval_hits = sum(item.interval_hit_count for item in scenarios)
        overall_coverage = (
            float(interval_hits / interval_evaluated) if interval_evaluated > 0 else None
        )
        macro_rmse_values = [
            item.rmse
            for item, statistics in zip(scenarios, scenario_statistics, strict=True)
            if item.rmse is not None and statistics[3] > 0
        ]
        overall_macro_rmse = float(np.mean(macro_rmse_values)) if macro_rmse_values else None
        interval_contracts = [
            {
                "scenario_id": item.scenario_id,
                "nominal_confidence_level": item.nominal_confidence_level,
                "interval_type": item.interval_type,
                "interval_requested_count": item.interval_requested_count,
                "interval_available_count": item.interval_available_count,
                "interval_evaluated_count": item.interval_evaluated_count,
                "interval_hit_count": item.interval_hit_count,
            }
            for item in scenarios
            if item.nominal_confidence_level is not None or item.interval_type is not None
        ]
        metadata_payload = dict(metadata)
        replay_groups: dict[str, list[BacktestScenario]] = {}
        planned_groups: dict[str, list[HistoricalValidationPlan]] = {}
        for plan in plans:
            source_plan_id = str(plan.metadata.get("source_plan_id", plan.plan_id))
            planned_groups.setdefault(source_plan_id, []).append(plan)
        for scenario in scenarios:
            source_plan_id = str(scenario.metadata.get("source_plan_id", scenario.scenario_id))
            replay_groups.setdefault(source_plan_id, []).append(scenario)
        metadata_payload["replay_denominators"] = [
            {
                "plan_id": source_plan_id,
                "requested": len(planned_groups.get(source_plan_id, group)),
                "declared_n_simulation_runs": (
                    planned_groups[source_plan_id][0].metadata.get("declared_n_simulation_runs", 1)
                    if source_plan_id in planned_groups
                    else None
                ),
                "attempted": sum(bool(item.metadata.get("backend_attempted")) for item in group),
                "completed": sum(
                    item.metadata.get("prediction_source_requested") != "scientist"
                    or item.metadata.get("prediction_source_effective") == "scientist"
                    for item in group
                ),
                "failed": sum(
                    item.metadata.get("prediction_source_requested") == "scientist"
                    and item.metadata.get("prediction_source_effective") != "scientist"
                    for item in group
                ),
                "unobserved": max(0, len(planned_groups.get(source_plan_id, group)) - len(group)),
                "outcomes": [item.scenario_id for item in group],
                "unit": "backend_replay"
                if len(planned_groups.get(source_plan_id, group)) > 1
                else "scenario",
                "basis": "recomputed" if source_plan_id in planned_groups else "not_established",
            }
            for source_plan_id in dict.fromkeys([*planned_groups, *replay_groups])
            for group in [replay_groups.get(source_plan_id, [])]
        ]
        metadata_payload["evaluation_status"] = (
            "evaluated" if total_compared > 0 else "not_evaluated"
        )
        metadata_payload["comparison_denominator"] = {
            "requested": (
                sum(len(rows) for plan in plans for rows in plan.ground_truth_outcomes.values())
                if plans
                else sum(item.requested_count for item in scenarios)
            ),
            "eligible": total_compared,
            "observed": sum(
                item.metadata.get("comparison_denominator", {}).get("observed", item.compared_count)
                for item in scenarios
            ),
            "unit": "metric_time_cell_per_replay",
            "basis": "recomputed" if plans else "not_established",
        }
        metadata_payload["trust_admission"] = {
            "status": "profile_missing",
            "purpose": None,
            "profile_ref": None,
            "bias_equivalence": "not_established",
            "predicate_basis": "not_established",
            "next_owner": "Scientist backtest trust-profile owner",
        }
        if interval_contracts:
            metadata_payload["interval_contracts"] = interval_contracts
        if trust_screening is not TrustScreeningMode.DEFAULT:
            metadata_payload["trust_screening"] = trust_screening.value

        biases, statistical_degraded_reasons = self._detect_systematic_biases(scenarios)
        all_degraded_reasons = [*degraded_reasons, *statistical_degraded_reasons]
        if trust_screening is not TrustScreeningMode.DEFAULT:
            all_degraded_reasons.append(f"trust_screening:{trust_screening.value}")

        model_spec_ref, policy_spec_ref, reference_issue = _consistent_plan_refs(plans)
        reference_issues = [reference_issue] if reference_issue is not None else []
        all_degraded_reasons = [*all_degraded_reasons, *reference_issues]
        degraded = bool(all_degraded_reasons)

        def has_complete_point_comparisons(scenario: BacktestScenario) -> bool:
            return bool(
                scenario.requested_count > 0
                and scenario.compared_count > 0
                and scenario.compared_count == scenario.requested_count
                and scenario.missing_count == 0
                and scenario.invalid_count == 0
                and len(scenario.outcome_comparisons) == scenario.compared_count
            )

        trust_eligible = (
            bool(scenarios)
            and not degraded
            and all(has_complete_point_comparisons(scenario) for scenario in scenarios)
        )
        trust_score, trust_grade = (None, None)
        if trust_eligible:
            trust_score, trust_grade = self._trust_scorer.compute(
                scenarios=scenarios, biases=biases
            )
        trust_eligible = trust_eligible and trust_score is not None and trust_grade is not None

        return BacktestReport(
            schema_version="1.0",
            report_id=report_id,
            scenarios=scenarios,
            model_spec_ref=model_spec_ref,
            policy_spec_ref=policy_spec_ref,
            overall_rmse=overall_rmse,
            overall_macro_rmse=overall_macro_rmse,
            overall_mae=overall_mae,
            overall_mape=overall_mape,
            overall_coverage_probability=overall_coverage,
            n_scenarios=len(scenarios),
            n_metrics_evaluated=total_compared,
            aggregation_policy=(
                "micro_rmse_with_explicit_equal_scenario_macro" if scenarios else None
            ),
            detected_biases=biases,
            overall_bias_direction=self._aggregate_bias_direction(biases),
            prediction_mode_requested=prediction_mode_requested,
            prediction_mode_effective=prediction_mode_effective,
            degraded=degraded,
            degraded_reasons=all_degraded_reasons,
            trust_eligible=trust_eligible,
            trust_score=trust_score,
            trust_grade=trust_grade,
            metadata=metadata_payload,
        )

    def _detect_systematic_biases(
        self,
        scenarios: list[BacktestScenario],
    ) -> tuple[list[SystematicBias], list[str]]:
        errors_by_metric: dict[str, list[float]] = {}
        for scenario in scenarios:
            for comp in scenario.outcome_comparisons:
                errors_by_metric.setdefault(comp.metric_name, []).append(comp.y_pred - comp.y_true)

        biases: list[SystematicBias] = []
        degraded_reasons: list[str] = []
        for metric, errors in errors_by_metric.items():
            arr = np.asarray(errors, dtype=float)
            mean = float(np.mean(arr))
            test_result = self._two_sided_ttest(arr)

            if test_result.p_value is None:
                # Exact agreement is an observed identity. A zero (or tiny)
                # mean of nonzero errors cannot establish statistical support.
                if np.all(arr == 0.0):
                    continue
                assert test_result.reason is not None
                degraded_reasons.append(
                    f"bias_statistical_test_{test_result.status}:{metric}:{test_result.reason}"
                )
                if mean == 0.0:
                    # There is no descriptive direction to assign, while the
                    # unresolved test must still withhold aggregate trust.
                    continue
                biases.append(
                    SystematicBias(
                        bias_type="directional",
                        direction=(
                            BiasDirection.OPTIMISTIC if mean > 0 else BiasDirection.PESSIMISTIC
                        ),
                        magnitude=float(abs(mean)),
                        affected_metrics=[metric],
                        description=(
                            "Model systematically "
                            f"{'overestimates' if mean > 0 else 'underestimates'} "
                            f"metric '{metric}'"
                        ),
                        statistical_test=test_result.test_name or "",
                        p_value=None,
                        metadata={
                            "diagnostic": "descriptive_residual",
                            "test_status": test_result.status,
                            **(
                                {"test_reason": test_result.reason}
                                if test_result.reason is not None
                                else {}
                            ),
                        },
                    )
                )
                continue
            if test_result.p_value >= 0.05:
                continue
            direction = BiasDirection.OPTIMISTIC if mean > 0 else BiasDirection.PESSIMISTIC
            biases.append(
                SystematicBias(
                    bias_type="directional",
                    direction=direction,
                    magnitude=float(abs(mean)),
                    affected_metrics=[metric],
                    description=(
                        "Model systematically "
                        f"{'overestimates' if mean > 0 else 'underestimates'} "
                        f"metric '{metric}'"
                    ),
                    statistical_test=test_result.test_name or "",
                    p_value=float(test_result.p_value),
                )
            )
        return biases, degraded_reasons

    @staticmethod
    def _two_sided_ttest(errors: np.ndarray) -> _TTestResult:
        n = int(errors.shape[0])
        if n < 3:
            return _TTestResult(
                p_value=None,
                test_name=None,
                status="not_computable",
                reason="insufficient_observations",
            )

        std = float(np.std(errors, ddof=1))
        if std <= 1e-12:
            return _TTestResult(
                p_value=None,
                test_name=None,
                status="not_computable",
                reason="zero_variance",
            )

        try:
            scipy_stats = import_module("scipy.stats")
            ttest_1samp = getattr(scipy_stats, "ttest_1samp", None)
            if ttest_1samp is None:
                return _TTestResult(
                    p_value=None,
                    test_name=None,
                    status="unavailable",
                    reason="scipy_ttest_1samp_missing",
                )
            result = ttest_1samp(errors, popmean=0.0, alternative="two-sided")
            p_value = float(result.pvalue)
            if not math.isfinite(p_value) or not 0.0 <= p_value <= 1.0:
                return _TTestResult(
                    p_value=None,
                    test_name=None,
                    status="unavailable",
                    reason="scipy_ttest_1samp_invalid_result",
                )
            return _TTestResult(
                p_value=p_value,
                test_name="one-sample t-test H0(mean_error=0)",
                status="available",
            )
        except Exception as exc:
            return _TTestResult(
                p_value=None,
                test_name=None,
                status="unavailable",
                reason=f"scipy_ttest_1samp_error:{type(exc).__name__}",
            )

    @staticmethod
    def _two_sided_ttest_pvalue(errors: np.ndarray) -> float | None:
        """Return a real SciPy one-sample t-test p-value when available."""
        return BacktestOrchestrator._two_sided_ttest(errors).p_value

    @staticmethod
    def _aggregate_bias_direction(biases: list[SystematicBias]) -> BiasDirection:
        if not biases:
            return BiasDirection.NEUTRAL
        directions = {item.direction for item in biases}
        if directions == {BiasDirection.OPTIMISTIC}:
            return BiasDirection.OPTIMISTIC
        if directions == {BiasDirection.PESSIMISTIC}:
            return BiasDirection.PESSIMISTIC
        if len(directions) > 1:
            return BiasDirection.MIXED
        return BiasDirection.NEUTRAL


__all__ = ["BacktestOrchestrator"]


def _collapse_modes(values: list[str]) -> str | None:
    unique = sorted({value for value in values if value})
    if not unique:
        return None
    if len(unique) == 1:
        return unique[0]
    return "mixed"
