"""Replay historical validation plans and aggregate trust calibration/audit outputs."""

from __future__ import annotations

import hashlib
import inspect
import json
import math
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from importlib import import_module
from pathlib import Path
from sys import float_info
from typing import TYPE_CHECKING, Any, Literal, cast

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts import (
    ArtifactRef as CoreArtifactRef,
)
from polisyos.core.artifacts import (
    artifact_ref_identity_key,
    input_ref_from_artifact_ref,
    read_core_manifest_profile,
    resolve_manifest_by_profile,
    validate_core_model_json_artifact,
)
from polisyos.core.artifacts import (
    ensure_ir_artifact_store as _ensure_ir_artifact_store,
)
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.ir_adapter import (
    CoreToIRArtifactStoreAdapter,
    build_ir_artifact_store,
    ensure_ir_artifact_store,
)
from polisyos.core.contracts import (
    CompileRequest,
    CompileResult,
    DataSnapshot,
    DataSnapshotRef,
    ExecuteRequest,
    ExecuteResult,
    FoundryExecConfig,
    FoundryInputBindingRule,
    FoundryInputBindings,
    MetricsRef,
    SimulationResult,
    SimulationResultRef,
)
from polisyos.ir import (
    BacktestReportRef,
    IntervalSemantics,
    UncertaintyEnvelope,
    UncertaintySource,
    combine_envelopes,
)
from polisyos.ir import CanonSpec as IRCanonSpec
from polisyos.ir import to_canonical_bytes as to_ir_canonical_bytes
from polisyos.ir.analytics.backtest import (
    BacktestReport,
    BacktestScenario,
    BiasDirection,
    MetricBiasDiagnostic,
    SystematicBias,
    backtest_mean,
    backtest_measurements_need_policy,
    backtest_sample_spread,
    persist_backtest_report,
    summarize_backtest_errors,
    summarize_unpooled_backtest,
    unpooled_backtest_scenarios,
)
from polisyos.ir.artifacts import (
    InputRef,
    InputRefLike,
    normalize_artifact_ref,
    normalize_input_refs,
    put_json_artifact,
)
from polisyos.scientist import run_experiment
from polisyos.scientist.adapters.foundry_bridge import DefaultFoundryPort
from polisyos.scientist.methods.backtesting.evaluator import PredictionEvaluator
from polisyos.scientist.methods.backtesting.masking import MaskingValidationError, OutcomeMasker
from polisyos.scientist.methods.backtesting.plan import (
    ForecastProfileContract,
    HistoricalReplaySourceSelection,
    HistoricalValidationPlan,
    PredictionSource,
)
from polisyos.scientist.methods.backtesting.trust_scorer import TrustScorer
from polisyos.scientist.nodes.builtins.simulate.uncertainty_source_projection import (
    load_science_simulation_result_uncertainty_admission,
)
from polisyos.scientist.nodes.builtins.state_keys import INPUT_INPUT_BINDINGS_REF
from polisyos.scientist.orchestration.engine.context import FoundryPort


def _trust_scorer_profile(scorer: TrustScorer) -> dict[str, Any] | None:
    """Bind the report to the concrete TrustScorer compute source and settings."""
    scorer_type = type(scorer)
    try:
        source = inspect.getsource(scorer_type.compute)
    except (OSError, TypeError, AttributeError):
        return None
    weights = getattr(getattr(scorer, "_scorer", None), "weights", None)
    mapper = getattr(scorer, "_grade_mapper", None)
    bands = getattr(mapper, "_bands", None)
    default = getattr(mapper, "_default", None)
    nominal = getattr(scorer, "_DEFAULT_NOMINAL_CONFIDENCE_LEVEL", None)
    if (
        not isinstance(weights, dict)
        or not isinstance(bands, (list, tuple))
        or not isinstance(default, str)
    ):
        return None
    try:
        grade_bands = [
            {"min_score": float(row.min_score), "value": str(row.value)} for row in bands
        ]
    except (AttributeError, TypeError, ValueError, OverflowError):
        return None
    if not isinstance(nominal, (float, int)):
        return None
    return {
        "profile_schema": "trust-scorer-profile-v1",
        "implementation": f"{scorer_type.__module__}.{scorer_type.__qualname__}",
        "compute_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "weights": {str(k): float(v) for k, v in sorted(weights.items())},
        "grade_bands": grade_bands,
        "grade_default": default,
        "nominal_confidence_default": float(nominal),
        "numpy_version": np.__version__,
    }


if TYPE_CHECKING:
    from polisyos.core.artifacts import ArtifactTenantContextInfo
    from polisyos.core.artifacts.protocol import ArtifactStore as CoreArtifactStore
    from polisyos.core.run.context import RunContext
    from polisyos.scientist.methods.backtesting.replica_budget import (
        BacktestFoundryInvocationBudget,
        BacktestFoundryInvocationScopeV1,
    )
    from polisyos.ir.analytics.backtest_pooling import (
        BacktestPoolingPolicyRef,
        BacktestPoolingProjection,
    )
    from polisyos.ir.artifacts import ArtifactStore as IRArtifactStore

    type BacktestStore = IRArtifactStore | CoreArtifactStore
else:
    BacktestStore = Any


class _BacktestReplicaRecord(BaseModel):
    """Persist one requested Scientist execution and its actual Foundry result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    index: int = Field(ge=1)
    run_id: str
    seed: int
    workflow_started: bool
    status: Literal["completed", "failed"]
    physical_request: dict[str, Any] | None = None
    workflow_report_ref: CoreArtifactRef | None = None
    run_manifest_ref: CoreArtifactRef | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    workflow_status: str | None = None
    workflow_failures: list[dict[str, Any]] = Field(default_factory=list)
    simulation_result_ref: SimulationResultRef | None = None
    metrics_ref: MetricsRef | None = None
    seed_source: str | None = None
    environment_fingerprint: str | None = None
    failure: str | None = None


class _BacktestReplicaCohort(BaseModel):
    """Durable denominator and CAS lineage for one backtest's Scientist replicas.

    ``foundry_execute_count`` counts replicas reaching Foundry, not step calls.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["polisyos.scientist.backtesting.replica_cohort.v1"] = (
        "polisyos.scientist.backtesting.replica_cohort.v1"
    )
    plan_id: str
    masked_data_snapshot_ref: DataSnapshotRef
    requested_count: int = Field(ge=1)
    started_count: int = Field(ge=0)
    foundry_execute_count: int = Field(ge=0)
    completed_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    replicas: list[_BacktestReplicaRecord]

    @model_validator(mode="after")
    def _validate_denominator(self) -> _BacktestReplicaCohort:
        if len(self.replicas) != self.requested_count:
            raise ValueError("replicas must retain the complete requested denominator")
        if self.started_count > self.requested_count:
            raise ValueError("started_count cannot exceed requested_count")
        if self.foundry_execute_count > self.started_count:
            raise ValueError("Foundry execution count cannot exceed started workflows")
        if self.completed_count + self.failed_count != self.requested_count:
            raise ValueError("every requested replica must have a terminal status")
        if self.completed_count != sum(item.status == "completed" for item in self.replicas):
            raise ValueError("completed_count must match replica statuses")
        if self.failed_count != sum(item.status == "failed" for item in self.replicas):
            raise ValueError("failed_count must match replica statuses")
        return self


@dataclass
class _BacktestReplicaFoundryPort:
    """Bind one replica's exact masked view and seed at Foundry's request boundary."""

    delegate: FoundryPort
    expected_snapshot_ref: DataSnapshotRef
    seed: int
    invocation_budget: BacktestFoundryInvocationBudget | None = None
    invocation_scope: BacktestFoundryInvocationScopeV1 | None = None
    request: ExecuteRequest | None = None
    result: ExecuteResult | None = None
    failure: str | None = None

    def compile(self, store: Any, request: CompileRequest) -> CompileResult:
        """Keep compile on the existing Foundry route without changing its contract."""
        return self.delegate.compile(store, request)

    def execute(
        self,
        store: Any,
        request: ExecuteRequest,
        *,
        derived_tenant_context: ArtifactTenantContextInfo | None = None,
    ) -> ExecuteResult:
        """Execute a copied request bound to the masked view and this replica seed."""
        from polisyos.core.artifacts import load_core_json_artifact

        try:
            bindings_payload = load_core_json_artifact(store, request.input_bindings_ref)
            bindings = FoundryInputBindings.model_validate(bindings_payload)
            actual_snapshot_ref = DataSnapshotRef.model_validate(
                bindings.data_snapshot_ref.model_dump(mode="python")
            )
            if artifact_ref_identity_key(actual_snapshot_ref) != artifact_ref_identity_key(
                self.expected_snapshot_ref
            ):
                raise ValueError(
                    "backtest_foundry_input_snapshot_mismatch:"
                    f"{artifact_ref_identity_key(actual_snapshot_ref)!r}!="
                    f"{artifact_ref_identity_key(self.expected_snapshot_ref)!r}"
                )

            exec_config = FoundryExecConfig.model_validate(
                {
                    **request.exec_config.model_dump(mode="python", exclude_unset=True),
                    "seed": self.seed,
                }
            )
            physical_request = request.model_copy(
                deep=True,
                update={"exec_config": exec_config},
            )
            if self.invocation_budget is None:
                self.request = physical_request
                if derived_tenant_context is None:
                    self.result = self.delegate.execute(store, physical_request)
                else:
                    self.result = self.delegate.execute(
                        store, physical_request, derived_tenant_context=derived_tenant_context
                    )
            else:
                if self.invocation_scope is None:
                    raise ValueError("backtest_foundry_invocation_scope_missing")

                from polisyos.scientist.methods.backtesting.replica_budget import (
                    BacktestFoundryDispatchState,
                    build_backtest_foundry_horizon_step_id,
                    execute_backtest_foundry_once,
                )
                from polisyos.foundry.execute.executor import load_state_snapshot

                bound_state = load_state_snapshot(
                    store, snapshot_ref=bindings.bound_state_snapshot_ref
                )
                raw_state_step = np.asarray(bound_state.step)
                if raw_state_step.size != 1 or not np.issubdtype(
                    raw_state_step.dtype, np.integer
                ):
                    raise ValueError("backtest_foundry_state_step_not_established")
                state_step = int(raw_state_step.item())
                horizon_step_id = build_backtest_foundry_horizon_step_id(
                    state_step=state_step,
                    exec_plan_ref=physical_request.exec_plan_ref,
                )
                del bound_state, raw_state_step
                dispatch_state = BacktestFoundryDispatchState()
                invocation_scope = self.invocation_scope.model_copy(
                    update={
                        "horizon_step_id": f"{self.invocation_scope.horizon_step_id}:"
                        f"{horizon_step_id}"
                    }
                )
                try:
                    self.result = execute_backtest_foundry_once(
                        ledger=self.invocation_budget.ledger,
                        profile=self.invocation_budget.profile,
                        scope=invocation_scope,
                        delegate=self.delegate,
                        store=store,
                        request=physical_request,
                        derived_tenant_context=derived_tenant_context,
                        dispatch_state=dispatch_state,
                    )
                finally:
                    if dispatch_state.entered:
                        self.request = physical_request
            if not self.result.ok:
                self.failure = "; ".join(self.result.notes) or "foundry_execute_not_ok"
            return self.result
        except Exception as exc:
            self.failure = f"{type(exc).__name__}: {exc}"
            raise


def _resolve_replica_failure(
    adapter_failure: str | None,
    workflow_failures: Sequence[Mapping[str, Any]],
    fallback_failure: str | None,
) -> str | None:
    """Prefer a concrete execution or persisted node cause to status fallback."""
    if adapter_failure:
        return adapter_failure
    for workflow_failure in workflow_failures:
        error = workflow_failure.get("error")
        if not isinstance(error, Mapping):
            continue
        code = error.get("code")
        message = error.get("message")
        clean_code = code if isinstance(code, str) and code.strip() else None
        clean_message = message if isinstance(message, str) and message.strip() else None
        if clean_code is not None and clean_message is not None:
            return f"{clean_code}: {clean_message}"
        if clean_message is not None:
            return clean_message
        if clean_code is not None:
            return clean_code
    return fallback_failure


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
    method_id: str | None = None
    backend_id: str | None = None
    backend_version: str | None = None
    statistic: float | None = None


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
            if item.manifest_profile_sha256 is None:
                manifest = store.get_manifest(item.artifact_id)
                selected_ref = item.artifact_id
            else:
                manifest = resolve_manifest_by_profile(
                    store,
                    item.artifact_id,
                    item.manifest_profile_sha256,
                )
                selected_ref = CoreArtifactRef(
                    artifact_id=item.artifact_id,
                    kind=manifest.kind,
                    media_type=manifest.media_type,
                    manifest_profile_sha256=item.manifest_profile_sha256,
                )
            manifest_artifact_id = getattr(manifest, "artifact_id", None)
            if str(manifest_artifact_id) != str(item.artifact_id):
                raise ValueError("manifest identity does not match the requested artifact")
            store.get_bytes(selected_ref)
        except Exception as exc:
            raise ValueError(
                "manifest input artifact cannot be resolved in the configured CAS: "
                f"{item.artifact_id}"
            ) from exc
    return normalized


def _plan_requests_native(plan: HistoricalValidationPlan) -> bool:
    """Identify plans that need selected native cohort/report lineage."""
    return bool(
        plan.prediction_source is PredictionSource.SCIENTIST
        and isinstance(plan.scientist_state, dict)
        and isinstance(plan.scientist_state.get("params"), dict)
        and "backtest_native_forecast" in plan.scientist_state["params"]
    )


def _verify_historical_binding_sources(
    masked_data: Mapping[str, object],
    params: Mapping[str, object],
    inputs: Mapping[str, object],
) -> list[str]:
    """Require the ordinary replay to bind from the admitted historical view."""
    if inputs.get(INPUT_INPUT_BINDINGS_REF) is not None:
        raise MaskingValidationError(
            "Prebound inputs have no verified as-of derivation for this replay",
            code="scientist_historical_prebound_inputs_not_established",
        )
    raw_rules = params.get("foundry_input_binding_rules")
    if raw_rules is None:
        return []
    try:
        if not isinstance(raw_rules, list):
            raise ValueError("binding rules must be a list")
        rules = [FoundryInputBindingRule.model_validate(item) for item in raw_rules]
    except ValueError as exc:
        raise MaskingValidationError(
            "Historical input binding rule is invalid",
            code="scientist_historical_binding_rule_invalid",
        ) from exc

    warnings: list[str] = []
    for rule in rules:
        field, separator, index = rule.source_path.partition(".")
        # Admitted view values are flat series. A request can select a series
        # or one position in it, but cannot recover an omitted path via a default.
        must_refuse = not rule.source_path or field == "_backtest_metadata"
        values = None if must_refuse else masked_data.get(field)
        if isinstance(values, (list, tuple)):
            if not separator:
                continue
            if index.isdecimal():
                try:
                    position = int(index)
                except ValueError:
                    position = len(values)
                if position < len(values):
                    value = values[position]
                    if value is not None and (not isinstance(value, float) or math.isfinite(value)):
                        continue
                    # Mask placeholders still resolve under Foundry's path reader.
                    must_refuse = True
        message = f"Historical binding source {rule.source_path!r} has no admitted as-of value"
        if must_refuse or rule.required or rule.default_value is not None:
            raise MaskingValidationError(
                message,
                code="scientist_historical_feature_not_admitted",
                details={"binding_id": rule.binding_id, "source_path": rule.source_path},
            )
        warnings.append(message)
    return warnings


def _scenario_report_inputs(scenarios: Sequence[BacktestScenario]) -> list[InputRef]:
    """Retain each scenario's selected cohort and native trajectory views."""
    edges: list[InputRef] = []
    for scenario in scenarios:
        cohort_payload = scenario.metadata.get("replica_cohort_ref")
        if not isinstance(cohort_payload, Mapping):
            continue
        try:
            cohort_ref = CoreArtifactRef.model_validate(dict(cohort_payload))
        except (TypeError, ValueError):
            continue
        edges.append(
            InputRef.model_validate(
                input_ref_from_artifact_ref(
                    cohort_ref, role=f"replica_cohort:{scenario.scenario_id}"
                ).model_dump(mode="json")
            )
        )
        projection_payload = scenario.metadata.get("native_replica_projection")
        if projection_payload is not None:
            from polisyos.scientist.methods.backtesting.native_replay import (
                _NativeReplicaProjection,
            )

            projection = _NativeReplicaProjection.model_validate(projection_payload)
            roles = [
                (forecast_ref, f"native_forecast:{scenario.scenario_id}:{index}")
                for index, forecast_ref in enumerate(projection.forecast_refs, start=1)
            ]
        else:
            forecast_payload = scenario.metadata.get("native_forecast_ref")
            roles = (
                [
                    (
                        CoreArtifactRef.model_validate(dict(forecast_payload)),
                        f"native_forecast:{scenario.scenario_id}",
                    )
                ]
                if isinstance(forecast_payload, Mapping)
                else []
            )
        interval_payload = scenario.metadata.get("native_prediction_interval_ref")
        if interval_payload is not None:
            roles.append(
                (
                    CoreArtifactRef.model_validate(interval_payload),
                    f"native_prediction_interval:{scenario.scenario_id}",
                )
            )
        edges.extend(
            InputRef.model_validate(
                input_ref_from_artifact_ref(ref, role=role).model_dump(mode="json")
            )
            for ref, role in roles
        )
    return edges


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
        foundry_invocation_budget: BacktestFoundryInvocationBudget | None = None,
    ) -> None:
        if cas is not None:
            self._store = ensure_ir_artifact_store(cas)
        else:
            factory = store_factory or _default_backtest_store_factory
            self._store = ensure_ir_artifact_store(factory(Path(cas_root)))
        self._masker = OutcomeMasker()
        self._evaluator = PredictionEvaluator()
        self._trust_scorer = TrustScorer()
        if foundry_invocation_budget is not None:
            from polisyos.scientist.methods.backtesting.replica_budget import (
                BacktestFoundryInvocationBudget,
            )

            if type(foundry_invocation_budget) is not BacktestFoundryInvocationBudget:
                raise TypeError("backtest_foundry_invocation_budget_untyped")
            foundry_invocation_budget.validate_current()
        self._foundry_invocation_budget = foundry_invocation_budget

    def run(
        self,
        plans: list[HistoricalValidationPlan],
        *,
        report_id: str | None = None,
        inputs: Sequence[InputRef] | None = None,
        metadata: dict[str, Any] | None = None,
        trust_screening: TrustScreeningMode = TrustScreeningMode.DEFAULT,
        pooling_policy_ref: BacktestPoolingPolicyRef | None = None,
        pooling_run_context: RunContext | None = None,
    ) -> BacktestReport:
        """Execute every historical plan and persist its report in CAS.

        This compatibility method preserves the historical ``BacktestReport``
        return shape. Call :meth:`run_with_ref` when the producer must retain
        the exact selected report manifest returned by the CAS write.
        """
        report, _report_ref = self.run_with_ref(
            plans,
            report_id=report_id,
            inputs=inputs,
            metadata=metadata,
            trust_screening=trust_screening,
            pooling_policy_ref=pooling_policy_ref,
            pooling_run_context=pooling_run_context,
        )
        return report

    def run_with_ref(
        self,
        plans: list[HistoricalValidationPlan],
        *,
        report_id: str | None = None,
        inputs: Sequence[InputRef] | None = None,
        metadata: dict[str, Any] | None = None,
        trust_screening: TrustScreeningMode = TrustScreeningMode.DEFAULT,
        pooling_policy_ref: BacktestPoolingPolicyRef | None = None,
        pooling_run_context: RunContext | None = None,
    ) -> tuple[BacktestReport, BacktestReportRef]:
        """Execute the plans and return the report plus its exact persisted CAS ref.

        ``report_id`` and ``inputs`` are caller-owned handoff values. When they
        are absent, historical generated-ID and empty-lineage behavior is
        retained; plan fields are never promoted into manifest inputs. Input
        roles and content/schema semantics remain the caller's explicit
        contract; this owner resolves only the exact refs in its configured CAS.
        The returned ref is the selected view returned by the report write; it
        is not reconstructed from the content-addressed artifact ID.
        A selected pooling policy fixes provided cases and weights before any
        scenario is evaluated.
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
        if self._foundry_invocation_budget is not None:
            self._foundry_invocation_budget.validate_current()
        if (pooling_policy_ref is None) != (pooling_run_context is None):
            raise ValueError("backtest pooling requires both policy and active run context")
        pooling = None
        pooling_edges: list[InputRef] = []
        policy = None
        measures = ()
        if pooling_policy_ref is not None and pooling_run_context is not None:
            from polisyos.ir.analytics.backtest_pooling import (
                load_backtest_pooling_policy,
                pooling_policy_edge,
                project_backtest_pooling,
                verify_pooling_policy_edge,
            )
            from polisyos.scientist.methods.backtesting.pooling import (
                prepare_backtest_pooling,
                record_backtest_pooling_policy,
            )

            policy = load_backtest_pooling_policy(self._store, pooling_policy_ref)
            record_backtest_pooling_policy(
                pooling_run_context, self._scientist_execution_store(), pooling_policy_ref
            )
        manifest_inputs = _resolve_manifest_inputs(self._store, inputs)
        if policy is not None:
            verify_pooling_policy_edge(manifest_inputs or (), None)
            measures = prepare_backtest_pooling(self._store, policy, plans)
        scenarios: list[BacktestScenario] = []
        warnings: list[str] = []
        requested_modes: list[str] = []
        effective_modes: list[str] = []
        degraded_reasons: list[str] = []
        select_cohort_profiles = any(_plan_requests_native(plan) for plan in plans)

        for plan in plans:
            (
                scenario,
                scenario_warnings,
                prediction_mode_requested,
                prediction_mode_effective,
                scenario_degraded_reasons,
            ) = self._run_single_scenario(plan, select_cohort_profiles=select_cohort_profiles)
            scenarios.append(scenario)
            warnings.extend([f"{plan.plan_id}: {item}" for item in scenario_warnings])
            requested_modes.append(prediction_mode_requested)
            effective_modes.append(prediction_mode_effective)
            degraded_reasons.extend(
                [f"{plan.plan_id}: {item}" for item in scenario_degraded_reasons]
            )

        if pooling_policy_ref is not None and policy is not None:
            pooling = project_backtest_pooling(
                pooling_policy_ref, policy, measures, scenarios, summarize_backtest_errors
            )
            pooling_edges.append(pooling_policy_edge(pooling_policy_ref))
        report = self._aggregate(
            report_id=resolved_report_id,
            scenarios=scenarios,
            plans=plans,
            metadata={"warnings": warnings, **(metadata or {})},
            prediction_mode_requested=_collapse_modes(requested_modes),
            prediction_mode_effective=_collapse_modes(effective_modes),
            degraded_reasons=degraded_reasons,
            trust_screening=resolved_trust_screening,
            pooling=pooling,
        )
        report = self._validate_trust_projection_before_persist(report)
        report._withhold_unreconciled_source_trust()
        report_inputs = [
            *(manifest_inputs or []),
            *_scenario_report_inputs(scenarios),
            *pooling_edges,
        ]
        ref = persist_backtest_report(
            _ensure_ir_artifact_store(self._store),
            report,
            inputs=report_inputs or None,
        )
        if pooling_run_context is not None:
            pooling_run_context.add_output(CoreArtifactRef.model_validate(dict(ref)))
        report.cas_artifact_id = str(ref.artifact_id)
        return report, ref

    def _run_single_scenario(
        self,
        plan: HistoricalValidationPlan,
        *,
        select_cohort_profiles: bool = False,
    ) -> tuple[BacktestScenario, list[str], str, str, list[str]]:
        warnings: list[str] = []
        historical_data = self._load_historical_data(plan)
        masked_data = self._masker.mask(historical_data, plan)

        prediction_payload = (
            self._predict(plan, masked_data, select_cohort_profiles=True)
            if select_cohort_profiles
            else self._predict(plan, masked_data)
        )
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
        }
        scenario_metadata.pop("native_prediction_interval_ref", None)
        if "interval_type" in prediction_payload:
            scenario_metadata["interval_type"] = prediction_payload["interval_type"]
        if "interval_metadata_source" in prediction_payload:
            scenario_metadata["interval_metadata_source"] = prediction_payload[
                "interval_metadata_source"
            ]
        if "replica_cohort_ref" in prediction_payload:
            scenario_metadata["replica_cohort_ref"] = prediction_payload["replica_cohort_ref"]
        for key in (
            "native_forecast_ref",
            "native_replica_projection",
            "native_request_ref",
            "native_forecast_purpose",
            "native_workflow_status",
            "native_workflow_failures",
            "native_foundry_step_count",
            "native_randomness_scope",
            "native_limitations",
            "native_prediction_interval_ref",
            "native_requested_replicas",
            "native_started_replicas",
            "native_requested_count_status",
            "native_started_count_status",
        ):
            if key in prediction_payload:
                scenario_metadata[key] = prediction_payload[key]
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
            data_source=(
                str(plan.historical_replay_source.source_data_ref.artifact_id)
                if plan.historical_replay_source is not None
                else plan.historical_data_ref or plan.historical_data_path or ""
            ),
            metadata=scenario_metadata,
        )
        return (
            scenario,
            warnings,
            plan.prediction_source.value,
            str(prediction_payload.get("prediction_mode_effective", plan.prediction_source.value)),
            degraded_reasons,
        )

    def _persist_replica_cohort(
        self,
        cohort: _BacktestReplicaCohort,
        *,
        inputs: Sequence[InputRefLike],
        select_profile: bool,
    ) -> CoreArtifactRef:
        """Normalize the IR writer's mapping before any native consumer uses it."""
        payload = put_json_artifact(
            _ensure_ir_artifact_store(self._store),
            cohort.model_dump(mode="json"),
            kind="scientist.backtest.replica_cohort",
            schema_name="polisyos.scientist.backtesting.ReplicaCohort",
            schema_version="1.0",
            inputs=inputs,
            canon_spec=IRCanonSpec(forbid_floats=False, forbid_nan_inf=False),
            return_selected_profile=select_profile,
        )
        return CoreArtifactRef.model_validate(payload)

    def _load_historical_data(self, plan: HistoricalValidationPlan) -> dict[str, Any]:
        from polisyos.core.artifacts import load_core_json_artifact

        source = plan.historical_replay_source
        if source is not None or plan.historical_data_ref:
            selector = (
                source.source_data_ref
                if source is not None
                else ArtifactID.model_validate(plan.historical_data_ref)
            )
            payload = load_core_json_artifact(self._store, selector)
            if not isinstance(payload, dict):
                raise ValueError(f"historical_data_ref must point to a JSON object: {selector}")
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
        *,
        select_cohort_profiles: bool = False,
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
            return self._predict_with_scientist(
                plan, masked_data, select_cohort_profiles=select_cohort_profiles
            )
        naive = self._predict_with_naive(plan, masked_data)
        naive["prediction_mode_effective"] = PredictionSource.NAIVE.value
        naive["degraded"] = False
        naive["degraded_reasons"] = []
        return naive

    def _predict_with_scientist(
        self,
        plan: HistoricalValidationPlan,
        masked_data: dict[str, Any],
        *,
        select_cohort_profiles: bool = False,
    ) -> dict[str, Any]:
        from polisyos.core.artifacts import load_core_json_artifact

        warnings: list[str] = []
        native = _plan_requests_native(plan)

        def native_unavailable(reason: str) -> dict[str, Any]:
            return {
                "predictions": {},
                "intervals": {},
                "warnings": [reason],
                "prediction_mode_effective": "scientist_unavailable",
                "degraded": True,
                "degraded_reasons": [
                    reason,
                    "native_requested_count_not_established",
                    "native_started_count_not_established",
                ],
                "native_requested_replicas": plan.n_simulation_runs,
                "native_started_replicas": 0,
                "native_requested_count_status": "not_established",
                "native_started_count_status": "not_established",
            }

        if not self._has_declared_temporal_boundary(plan):
            if native:
                return native_unavailable("native_forecast_unavailable:historical_cutoff_missing")
            return {
                "predictions": {},
                "intervals": {},
                "warnings": ["Scientist historical cutoff missing; no as-of prediction available"],
                "prediction_mode_effective": "scientist_unavailable",
                "degraded": True,
                "degraded_reasons": ["scientist_historical_cutoff_missing"],
            }

        def naive_before_dispatch(reason: str, warning: str) -> dict[str, Any]:
            naive = self._predict_with_naive(plan, masked_data)
            naive["warnings"] = [*warnings, warning, *naive.get("warnings", [])]
            naive["prediction_mode_effective"] = PredictionSource.NAIVE.value
            naive["degraded"] = True
            naive["degraded_reasons"] = [reason]
            return naive

        if plan.scientist_state is None:
            return naive_before_dispatch(
                "scientist_state_missing", "scientist_state missing; using naive predictor fallback"
            )
        source = plan.historical_replay_source
        if native and source is not None:
            return native_unavailable(
                "native_forecast_unavailable:historical_replay_source_unsupported"
            )
        if native and plan.known_ahead_calendar is not None:
            return native_unavailable(
                "native_forecast_unavailable:known_ahead_calendar_unsupported"
            )

        state_template = dict(plan.scientist_state)
        params_template = state_template.get("params", {})
        if not isinstance(params_template, dict):
            raise ValueError("scientist_state.params must be an object when provided")
        inputs_template = state_template.get("inputs", {})
        if not isinstance(inputs_template, dict):
            raise ValueError("scientist_state.inputs must be an object when provided")
        if not native:
            try:
                warnings.extend(
                    _verify_historical_binding_sources(
                        masked_data, params_template, inputs_template
                    )
                )
            except MaskingValidationError as exc:
                return naive_before_dispatch(
                    exc.code or "scientist_historical_input_invalid", exc.message
                )

        base_seed = plan.random_seed
        if base_seed is None:
            candidate_seed = params_template.get("random_seed", 0)
            if isinstance(candidate_seed, bool) or not isinstance(candidate_seed, int):
                raise ValueError("scientist_state.params.random_seed must be an integer")
            base_seed = candidate_seed

        execution_store = self._scientist_execution_store()
        if self._foundry_invocation_budget is None:
            cohort_nonce = uuid.uuid4().hex[:12]
        else:
            stable_scope = (
                f"{self._foundry_invocation_budget.profile.profile_digest}\0{plan.plan_id}"
            ).encode("utf-8")
            cohort_nonce = hashlib.sha256(stable_scope).hexdigest()[:12]
        native_first_state: dict[str, Any] | None = None
        native_plan_ref: CoreArtifactRef | None = None
        if native:
            from polisyos.scientist.methods.backtesting.native_replay import (
                NativeForecastProfile,
                _persist_native_plan,
                prepare_native_replay,
            )

            try:
                historical_data = self._load_historical_data(plan)
                native_first_state = prepare_native_replay(
                    execution_store,
                    plan,
                    historical_data,
                    run_id=f"BT-{plan.plan_id}-{cohort_nonce}-1",
                    seed=base_seed,
                )
                snapshot_payload = native_first_state["inputs"]["data_snapshot_ref"]
                profile = NativeForecastProfile.model_validate(
                    params_template["backtest_native_forecast"]
                )
                if plan.n_simulation_runs > 1 or profile.prediction_interval is not None:
                    native_plan_ref = _persist_native_plan(execution_store, plan)
            except Exception as exc:
                reason = f"native_forecast_unavailable:{type(exc).__name__}:{exc}"
                return native_unavailable(reason)
        elif source is not None and source.prepared_snapshot_ref is not None:
            snapshot_payload = self._verify_prepared_masked_view(source, masked_data)
        else:
            snapshot_payload = self._persist_masked_view(plan, masked_data)
        masked_snapshot_ref = DataSnapshotRef.model_validate(snapshot_payload)
        replica_records: list[_BacktestReplicaRecord] = []
        successful_artifacts: list[dict[str, Any]] = []
        native_forecast_refs: list[tuple[int, CoreArtifactRef]] = []
        foundry_execute_count = 0

        for index in range(plan.n_simulation_runs):
            replica_index = index + 1
            run_id = f"BT-{plan.plan_id}-{cohort_nonce}-{replica_index}"
            seed = base_seed + index
            replica_state = dict(state_template)
            replica_state["run_id"] = run_id
            replica_params = dict(params_template)
            replica_params["random_seed"] = seed
            replica_params["n_simulation_runs"] = 1
            replica_state["params"] = replica_params
            replica_inputs = dict(inputs_template)
            replica_inputs["data_snapshot_ref"] = snapshot_payload
            replica_state["inputs"] = replica_inputs

            invocation_scope = None
            if self._foundry_invocation_budget is not None:
                from polisyos.scientist.methods.backtesting.replica_budget import (
                    BacktestFoundryInvocationScopeV1,
                )

                invocation_scope = BacktestFoundryInvocationScopeV1(
                    backtest_run_id=self._foundry_invocation_budget.profile.run_binding.run_id,
                    replica_run_id=run_id,
                    replica_index=replica_index,
                    replica_seed=seed,
                    horizon_step_id="foundry_execute",
                )
            replica_foundry = _BacktestReplicaFoundryPort(
                delegate=DefaultFoundryPort(),
                expected_snapshot_ref=masked_snapshot_ref,
                seed=seed,
                invocation_budget=self._foundry_invocation_budget,
                invocation_scope=invocation_scope,
            )
            failure: str | None = None
            simulation_result_ref: SimulationResultRef | None = None
            metrics_ref: MetricsRef | None = None
            seed_source: str | None = None
            environment_fingerprint: str | None = None
            workflow_report_ref: CoreArtifactRef | None = None
            finalized_run_refs: list[CoreArtifactRef] = []
            workflow_status: str | None = None
            workflow_failures: list[dict[str, Any]] = []
            workflow_result: Any = None
            workflow_started = False
            try:
                if native:
                    assert native_first_state is not None
                    replica_state = (
                        native_first_state
                        if index == 0
                        else prepare_native_replay(
                            execution_store, plan, historical_data, run_id=run_id, seed=seed
                        )
                    )
                    replica_snapshot = DataSnapshotRef.model_validate(
                        replica_state["inputs"]["data_snapshot_ref"]
                    )
                    if artifact_ref_identity_key(replica_snapshot) != artifact_ref_identity_key(
                        masked_snapshot_ref
                    ):
                        raise ValueError("native_replica_masked_snapshot_mismatch")
                workflow_started = True
                workflow_result = run_experiment(
                    replica_state,
                    store=execution_store,
                    foundry=replica_foundry,
                    **({"on_run_finalized": finalized_run_refs.append} if native else {}),
                )
                if not isinstance(workflow_result, Mapping):
                    raise ValueError("scientist_workflow_result_missing")
                reports_index = workflow_result.get("reports_index")
                if not isinstance(reports_index, Mapping):
                    raise ValueError("scientist_workflow_reports_index_missing")
                raw_workflow_ref = reports_index.get("workflow_report")
                if not isinstance(raw_workflow_ref, Mapping):
                    raise ValueError("scientist_workflow_report_ref_missing")
                workflow_report_ref = CoreArtifactRef.model_validate(dict(raw_workflow_ref))
                if native:
                    from polisyos.scientist.methods.backtesting.native_replay import (
                        _load_native_workflow_report,
                    )

                    if len(finalized_run_refs) != 1:
                        raise ValueError("native workflow finalized run reference missing")
                    workflow_report = _load_native_workflow_report(
                        execution_store, workflow_report_ref, finalized_run_refs[0]
                    )
                else:
                    workflow_report = load_core_json_artifact(self._store, workflow_report_ref)
                if not isinstance(workflow_report, Mapping):
                    raise ValueError("scientist_workflow_report_payload_invalid")
                if workflow_report.get("run_id") != run_id:
                    raise ValueError("scientist_workflow_report_run_id_mismatch")
                raw_status = workflow_report.get("status")
                workflow_status = str(raw_status) if isinstance(raw_status, str) else None
                if workflow_status is None:
                    raise ValueError("scientist_workflow_report_status_missing")
                raw_nodes = workflow_report.get("nodes", [])
                if isinstance(raw_nodes, list):
                    for node in raw_nodes:
                        if not isinstance(node, Mapping) or node.get("status") != "fail":
                            continue
                        error = node.get("error")
                        workflow_failures.append(
                            {
                                "alias": node.get("alias"),
                                "status": node.get("status"),
                                "error": dict(error) if isinstance(error, Mapping) else None,
                            }
                        )
                if (
                    replica_foundry.result is not None
                    and replica_foundry.result.simulation_result_ref is not None
                ):
                    simulation_result_ref = replica_foundry.result.simulation_result_ref
                partial_native = False
                if workflow_status != "ok":
                    partial_native = (
                        native
                        and isinstance(raw_nodes, list)
                        and any(
                            isinstance(node, Mapping)
                            and node.get("alias") == "run_simulation"
                            and node.get("status") == "ok"
                            for node in raw_nodes
                        )
                    )
                    if not partial_native:
                        raise ValueError(f"scientist_workflow_status:{workflow_status}")
                if replica_foundry.request is None:
                    raise ValueError("scientist_workflow_did_not_submit_foundry_request")
                if replica_foundry.result is None or not replica_foundry.result.ok:
                    raise ValueError(replica_foundry.failure or "foundry_execution_result_not_ok")
                simulation_result_ref = replica_foundry.result.simulation_result_ref
                if simulation_result_ref is None:
                    raise ValueError("foundry_simulation_result_ref_missing")

                simulation_payload = load_core_json_artifact(self._store, simulation_result_ref)
                simulation_result = SimulationResult.model_validate(simulation_payload)
                if artifact_ref_identity_key(simulation_result.exec_plan_ref) != (
                    artifact_ref_identity_key(replica_foundry.request.exec_plan_ref)
                ):
                    raise ValueError("foundry_simulation_exec_plan_mismatch")
                seed_source_notes = [
                    note for note in simulation_result.notes if note.startswith("seed_source:")
                ]
                if seed_source_notes != ["seed_source:exec_config.seed"]:
                    raise ValueError("foundry_runtime_seed_source_not_established")
                seed_source = "exec_config.seed"
                environment_fingerprint = simulation_result.environment_fingerprint

                final_artifacts = workflow_result.get("artifacts_index")
                if not isinstance(final_artifacts, Mapping):
                    raise ValueError("scientist_artifacts_index_missing")
                raw_metrics_ref = final_artifacts.get("metrics_ref")
                if not isinstance(raw_metrics_ref, Mapping):
                    raise ValueError("scientist_metrics_ref_missing")
                metrics_ref = MetricsRef.model_validate(dict(raw_metrics_ref))
                if artifact_ref_identity_key(metrics_ref) != artifact_ref_identity_key(
                    simulation_result.metrics_ref
                ):
                    raise ValueError("scientist_metrics_simulation_result_mismatch")
                metrics_payload = load_core_json_artifact(self._store, metrics_ref)
                if not isinstance(metrics_payload, Mapping):
                    raise ValueError("scientist_metrics_payload_not_object")

                final_sim_ref = final_artifacts.get("simulation_result_ref")
                if not isinstance(final_sim_ref, Mapping):
                    raise ValueError("scientist_simulation_result_ref_missing")
                final_simulation_ref = SimulationResultRef.model_validate(dict(final_sim_ref))
                if artifact_ref_identity_key(final_simulation_ref) != artifact_ref_identity_key(
                    simulation_result_ref
                ):
                    raise ValueError("scientist_simulation_result_mismatch")
                artifacts: dict[str, Any] = {
                    "metrics_ref": metrics_ref,
                }
                if native:
                    from polisyos.scientist.methods.backtesting.native_replay import (
                        FORECAST_KEY,
                        REQUEST_KEY,
                        load_native_forecast,
                    )

                    forecast_ref = CoreArtifactRef.model_validate(final_artifacts[FORECAST_KEY])
                    request_ref = CoreArtifactRef.model_validate(
                        replica_state["params"][REQUEST_KEY]
                    )
                    forecast, native_request = load_native_forecast(
                        execution_store, forecast_ref, request_ref
                    )
                    if native_request.run_id != run_id or native_request.seed != seed:
                        raise ValueError("native forecast run/seed differs from replica")
                    if forecast.simulation_refs[-1] != simulation_result_ref:
                        raise ValueError("native forecast final simulation differs from workflow")
                    artifacts.update(
                        native_forecast_ref=forecast_ref.model_dump(mode="json"),
                        native_request_ref=request_ref.model_dump(mode="json"),
                        native_forecast_purpose=native_request.profile.purpose,
                        native_predictions=forecast.values,
                        native_workflow_status=workflow_status,
                        native_workflow_failures=workflow_failures,
                        native_foundry_step_count=len(forecast.simulation_refs),
                        native_randomness_scope=native_request.randomness_scope,
                        native_limitations=native_request.limitations,
                    )
                    native_forecast_refs.append((replica_index, forecast_ref))
                successful_artifacts.append(artifacts)
                if partial_native:
                    failure = f"scientist_workflow_status:{workflow_status}"
            except Exception as exc:
                failure = f"{type(exc).__name__}: {exc}"
            if failure is not None:
                failure = _resolve_replica_failure(
                    adapter_failure=replica_foundry.failure,
                    workflow_failures=workflow_failures,
                    fallback_failure=failure,
                )
            if replica_foundry.request is not None:
                foundry_execute_count += 1

            physical_request = (
                replica_foundry.request.model_dump(mode="json")
                if replica_foundry.request is not None
                else None
            )
            if failure is not None:
                warnings.append(f"Scientist replica {replica_index} failed: {failure}")
            replica_records.append(
                _BacktestReplicaRecord(
                    index=replica_index,
                    run_id=run_id,
                    seed=seed,
                    workflow_started=workflow_started,
                    status="completed" if failure is None else "failed",
                    physical_request=physical_request,
                    workflow_report_ref=workflow_report_ref,
                    run_manifest_ref=finalized_run_refs[0] if finalized_run_refs else None,
                    workflow_status=workflow_status,
                    workflow_failures=workflow_failures,
                    simulation_result_ref=simulation_result_ref,
                    metrics_ref=metrics_ref,
                    seed_source=seed_source,
                    environment_fingerprint=environment_fingerprint,
                    failure=failure,
                )
            )

        completed_count = sum(record.status == "completed" for record in replica_records)
        cohort = _BacktestReplicaCohort(
            plan_id=plan.plan_id,
            masked_data_snapshot_ref=masked_snapshot_ref,
            requested_count=plan.n_simulation_runs,
            started_count=sum(record.workflow_started for record in replica_records),
            foundry_execute_count=foundry_execute_count,
            completed_count=completed_count,
            failed_count=plan.n_simulation_runs - completed_count,
            replicas=replica_records,
        )
        cohort_inputs = [input_ref_from_artifact_ref(masked_snapshot_ref, role="masked_data")]
        if native_plan_ref is not None:
            cohort_inputs.append(input_ref_from_artifact_ref(native_plan_ref, role="native_plan"))
        for record in replica_records:
            if record.run_manifest_ref is not None:
                cohort_inputs.append(
                    input_ref_from_artifact_ref(
                        record.run_manifest_ref, role=f"replica_{record.index}_run_manifest"
                    )
                )
            if record.physical_request is None:
                if record.workflow_report_ref is not None:
                    cohort_inputs.append(
                        input_ref_from_artifact_ref(
                            record.workflow_report_ref,
                            role=f"replica_{record.index}_workflow_report",
                        )
                    )
                continue
            request = ExecuteRequest.model_validate(record.physical_request)
            cohort_inputs.extend(
                [
                    input_ref_from_artifact_ref(
                        request.exec_plan_ref,
                        role=f"replica_{record.index}_exec_plan",
                    ),
                    input_ref_from_artifact_ref(
                        request.input_bindings_ref,
                        role=f"replica_{record.index}_input_bindings",
                    ),
                    *(
                        [
                            input_ref_from_artifact_ref(
                                record.workflow_report_ref,
                                role=f"replica_{record.index}_workflow_report",
                            )
                        ]
                        if record.workflow_report_ref is not None
                        else []
                    ),
                ]
            )
            if record.simulation_result_ref is not None:
                cohort_inputs.append(
                    input_ref_from_artifact_ref(
                        record.simulation_result_ref,
                        role=f"replica_{record.index}_simulation_result",
                    )
                )
            if record.metrics_ref is not None:
                cohort_inputs.append(
                    input_ref_from_artifact_ref(
                        record.metrics_ref,
                        role=f"replica_{record.index}_metrics",
                    )
                )
        for index, forecast_ref in native_forecast_refs:
            cohort_inputs.append(
                input_ref_from_artifact_ref(forecast_ref, role=f"native_forecast:{index}")
            )
        cohort_ref = self._persist_replica_cohort(
            cohort,
            inputs=cohort_inputs,
            select_profile=native or select_cohort_profiles or source is not None,
        )

        def _naive_with_cohort(reason: str) -> dict[str, Any]:
            if native:
                from polisyos.scientist.methods.backtesting.native_replay import (
                    _load_selected_native_cohort,
                    _verify_unavailable_native_cohort,
                )

                selected_cohort_ref = cohort_ref
                selected_cohort = _load_selected_native_cohort(execution_store, selected_cohort_ref)
                _verify_unavailable_native_cohort(
                    execution_store,
                    selected_cohort_ref,
                    selected_cohort,
                    plan.plan_id,
                    plan.n_simulation_runs,
                    cohort.started_count,
                )
                return {
                    "predictions": {},
                    "intervals": {},
                    "warnings": warnings,
                    "prediction_mode_effective": "scientist_unavailable",
                    "degraded": True,
                    "degraded_reasons": [
                        reason,
                        "native_requested_count_not_established",
                        "native_started_count_not_established",
                    ],
                    "replica_cohort_ref": normalize_artifact_ref(cohort_ref),
                    "native_requested_replicas": plan.n_simulation_runs,
                    "native_started_replicas": cohort.started_count,
                    "native_requested_count_status": "not_established",
                    "native_started_count_status": "not_established",
                }
            naive = self._predict_with_naive(plan, masked_data)
            naive["warnings"] = warnings + naive.get("warnings", [])
            naive["prediction_mode_effective"] = PredictionSource.NAIVE.value
            naive["degraded"] = True
            naive["degraded_reasons"] = [reason]
            naive["replica_cohort_ref"] = normalize_artifact_ref(cohort_ref)
            return naive

        partial_native_result = (
            native
            and plan.n_simulation_runs == 1
            and completed_count == 0
            and len(successful_artifacts) == 1
        )
        if completed_count != plan.n_simulation_runs and not partial_native_result:
            return _naive_with_cohort("scientist_replica_cohort_incomplete")
        if native and plan.n_simulation_runs > 1:
            from polisyos.scientist.methods.backtesting.native_replay import (
                _mean_native_values,
                _NativeReplicaProjection,
                _reconcile_complete_native_cohort,
            )

            if native_plan_ref is None or [index for index, _ in native_forecast_refs] != list(
                range(1, plan.n_simulation_runs + 1)
            ):
                raise ValueError("native_replica_projection_trajectory_census_mismatch")
            projection = _NativeReplicaProjection(
                method="arithmetic_mean_complete_cohort_v1",
                plan_ref=native_plan_ref,
                forecast_refs=[ref for _, ref in native_forecast_refs],
            )
            selected_cohort_ref = cohort_ref
            _, forecasts, requests = _reconcile_complete_native_cohort(
                execution_store, selected_cohort_ref, projection
            )
            return {
                "predictions": _mean_native_values([forecast.values for forecast in forecasts]),
                "intervals": {},
                "warnings": warnings,
                "prediction_mode_effective": PredictionSource.SCIENTIST.value,
                "degraded": True,
                "degraded_reasons": [
                    "native_predictive_simulation_only",
                    *requests[0].limitations,
                ],
                "replica_cohort_ref": normalize_artifact_ref(cohort_ref),
                "native_replica_projection": projection.model_dump(mode="json"),
                "native_forecast_purpose": requests[0].profile.purpose,
                "native_foundry_step_count": sum(len(item.simulation_refs) for item in forecasts),
                "native_randomness_scope": requests[0].randomness_scope,
                "native_limitations": requests[0].limitations,
            }
        if plan.n_simulation_runs > 1:
            warnings.append(
                "Scientist replicas were retained individually; no multi-run projection is configured"
            )
            return _naive_with_cohort("scientist_replica_projection_unsupported")

        artifacts = successful_artifacts[0]

        if native:
            from polisyos.scientist.methods.backtesting.native_replay import (
                _build_native_interval_prediction,
                _load_selected_native_cohort,
                _verify_native_replica,
            )

            selected_cohort_ref = cohort_ref
            selected_cohort = _load_selected_native_cohort(execution_store, selected_cohort_ref)
            forecast_ref = CoreArtifactRef.model_validate(artifacts["native_forecast_ref"])
            request_ref = CoreArtifactRef.model_validate(artifacts["native_request_ref"])
            forecast, request, _ = _verify_native_replica(
                execution_store,
                selected_cohort_ref,
                selected_cohort,
                selected_cohort.replicas[0],
                forecast_ref,
                request_ref,
                index=1,
            )
            interval_payload, interval_reasons = _build_native_interval_prediction(
                execution_store,
                forecast_ref,
                request_ref,
                request,
                workflow_completed=not partial_native_result,
            )
            return {
                "predictions": forecast.values,
                "intervals": {},
                **interval_payload,
                "warnings": warnings,
                "prediction_mode_effective": (
                    "scientist_candidate"
                    if partial_native_result
                    else PredictionSource.SCIENTIST.value
                ),
                "degraded": True,
                "degraded_reasons": [
                    "native_predictive_simulation_only",
                    *request.limitations,
                    *interval_reasons,
                    *(["scientist_replica_cohort_incomplete"] if partial_native_result else []),
                ],
                "replica_cohort_ref": normalize_artifact_ref(cohort_ref),
                "native_forecast_ref": artifacts["native_forecast_ref"],
                "native_request_ref": artifacts["native_request_ref"],
                "native_forecast_purpose": artifacts["native_forecast_purpose"],
                "native_workflow_status": artifacts["native_workflow_status"],
                "native_workflow_failures": artifacts["native_workflow_failures"],
                "native_foundry_step_count": artifacts["native_foundry_step_count"],
                "native_randomness_scope": artifacts["native_randomness_scope"],
                "native_limitations": artifacts["native_limitations"],
            }

        metrics_ref = artifacts.get("metrics_ref")
        reason = "scientist_predictions_missing"
        if isinstance(metrics_ref, MetricsRef):
            try:
                selector = (
                    metrics_ref
                    if metrics_ref.manifest_profile_sha256 is not None
                    else metrics_ref.artifact_id
                )
                metrics_payload = load_core_json_artifact(self._store, selector)
                values = metrics_payload.get("values", metrics_payload)
                if isinstance(values, dict):
                    for metric in plan.target_metrics:
                        raw = values.get(metric)
                        horizon = len(plan.ground_truth_outcomes.get(metric, []))
                        if isinstance(raw, list):
                            if len(raw) != horizon:
                                warnings.append(
                                    f"scientist trajectory for '{metric}' has length "
                                    f"{len(raw)}; expected {horizon}"
                                )
                                continue
                        elif isinstance(raw, (int, float)) and not isinstance(raw, bool):
                            if not self._is_constant_forecast(metrics_payload, selector, horizon):
                                warnings.append(
                                    f"scientist scalar for '{metric}' lacks constant_forecast profile"
                                )
                                continue
                        else:
                            continue
                        # Shape and producer identity do not bind a point
                        # trajectory to the requested outcome coordinates.
                        reason = "scientist_forecast_scope_not_established"
                        warnings.append(
                            f"scientist metrics for '{metric}' have no verified outcome scope"
                        )
            except Exception as exc:
                warnings.append(f"failed to parse scientist metrics output: {exc}")

        warnings.append("scientist predictions unavailable; using naive fallback")
        return _naive_with_cohort(reason)

    def _scientist_execution_store(self) -> Any:
        """Return the underlying CAS so Foundry and backtest read the same bytes."""
        if isinstance(self._store, CoreToIRArtifactStoreAdapter):
            return self._store.store
        return self._store

    def _extract_intervals_from_simulation_result(
        self,
        artifacts: dict[str, Any],
        plan: HistoricalValidationPlan,
    ) -> tuple[dict[str, list[tuple[float, float]]], dict[str, Any], tuple[str, ...]]:
        from polisyos.core.artifacts import validate_core_model_json_artifact

        if "simulation_result_ref" not in artifacts:
            return {}, {}, ()
        sim_ref_payload = artifacts["simulation_result_ref"]
        if not isinstance(sim_ref_payload, Mapping):
            return {}, {}, ("simulation_result_ref_malformed",)
        try:
            normalized_sim_ref = normalize_artifact_ref(sim_ref_payload)
        except (TypeError, ValueError, KeyError):
            return {}, {}, ("simulation_result_ref_malformed",)
        if normalized_sim_ref.get("kind") != "foundry.simulation_result":
            return {}, {}, ("simulation_result_ref_kind_mismatch",)
        try:
            simulation_result_ref = SimulationResultRef.model_validate(normalized_sim_ref)
        except (TypeError, ValueError):
            return {}, {}, ("simulation_result_ref_malformed",)
        try:
            simulation_result = validate_core_model_json_artifact(
                SimulationResult, self._store, simulation_result_ref
            )
        except Exception as exc:
            return {}, {}, (f"simulation_result_unavailable:{type(exc).__name__}",)
        envelopes = simulation_result.uncertainty_envelopes
        if not isinstance(envelopes, Mapping):
            return {}, {}, ("simulation_uncertainty_map_missing",)
        intervals: dict[str, list[tuple[float, float]]] = {}
        envelope_metadata: list[tuple[float | None, str | None]] = []
        envelope_contracts: list[UncertaintyEnvelope] = []
        legacy_metadata_seen = False
        metadata_errors: list[str] = []
        for metric in plan.target_metrics:
            ref_payload = envelopes.get(metric)
            if ref_payload is None or not getattr(ref_payload, "artifact_id", None):
                metadata_errors.append(
                    f"simulation_uncertainty_metric_envelope_ref_missing:{metric}"
                )
                continue
            try:
                admission = load_science_simulation_result_uncertainty_admission(
                    self._store,
                    simulation_result_ref,
                    metric,
                )
                if not admission.admitted or admission.envelope is None:
                    limitations = (
                        ",".join(admission.limitation_codes) or "admission_not_established"
                    )
                    metadata_errors.append(
                        f"simulation_uncertainty_admission_limited:{metric}:{limitations}"
                    )
                    continue
                env_id = ArtifactID.model_validate(ref_payload.artifact_id)
                env_payload = admission.envelope.model_dump(mode="python", round_trip=True)
                (
                    metadata_declared,
                    confidence_level,
                    interval_type,
                    envelope_contract,
                ) = self._resolve_persisted_interval_metadata(env_payload)
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
                if ref_payload is not None and getattr(ref_payload, "artifact_id", None):
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
        selector: MetricsRef | ArtifactID,
        horizon: int,
    ) -> bool:
        """Require a typed, producer-bound contract for constant trajectories."""
        if not isinstance(payload, dict) or payload.get("forecast_profile") != "constant_forecast":
            return False
        try:
            contract = ForecastProfileContract.model_validate(payload.get("forecast_contract"))
            if isinstance(selector, MetricsRef):
                manifest, _ = read_core_manifest_profile(self._store, selector)
            else:
                manifest = self._store.get_manifest(selector)
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

    def _verify_prepared_masked_view(
        self,
        source: HistoricalReplaySourceSelection,
        recomputed_view: dict[str, Any],
    ) -> dict[str, str]:
        """Verify the selected prepared input against the freshly masked source."""
        from polisyos.core.artifacts import load_core_json_artifact

        ref = source.prepared_snapshot_ref
        assert ref is not None
        snapshot = validate_core_model_json_artifact(DataSnapshot, self._store, ref)
        manifest, _ = read_core_manifest_profile(self._store, ref)
        source_edge = input_ref_from_artifact_ref(source.source_data_ref, role="historical_data")
        actual_source = [edge for edge in manifest.inputs if edge.role == "historical_data"]
        if actual_source != [source_edge]:
            raise MaskingValidationError(
                "Prepared history names a different historical source profile",
                code="prepared_history_source_mismatch",
            )

        child_edges = [edge for edge in manifest.inputs if edge.role == "masked_data"]
        if (
            len(manifest.inputs) != 2
            or manifest.artifact_schema is None
            or manifest.artifact_schema.version != DataSnapshot.ARTIFACT_SCHEMA_VERSION
            or len(child_edges) != 1
            or child_edges[0].manifest_profile_sha256 is None
            or child_edges[0].artifact_id != snapshot.data_ref.artifact_id
            or snapshot.data_ref.kind != "scientist.backtest.masked_historical_view"
            or snapshot.data_ref.media_type != "application/json"
            or snapshot.data_ref.manifest_profile_sha256
            not in (None, child_edges[0].manifest_profile_sha256)
        ):
            raise MaskingValidationError(
                "Prepared history lacks the selected masked data view",
                code="prepared_history_snapshot_invalid",
            )
        expected = DataSnapshot(
            data_ref=snapshot.data_ref,
            stats=self._masked_view_stats(recomputed_view),
            notes=snapshot.notes,
        )
        if snapshot != expected:
            raise MaskingValidationError(
                "Prepared history snapshot differs from the current cutoff or masking strategy",
                code="prepared_history_snapshot_mismatch",
            )
        child_ref = snapshot.data_ref.model_copy(
            update={"manifest_profile_sha256": child_edges[0].manifest_profile_sha256}
        )
        child_manifest, _ = read_core_manifest_profile(self._store, child_ref)
        if (
            child_manifest.artifact_schema is None
            or child_manifest.artifact_schema.name
            != "polisyos.scientist.backtesting.MaskedHistoricalView"
            or child_manifest.artifact_schema.version != "1.0"
        ):
            raise MaskingValidationError(
                "Prepared history has a foreign masked data profile",
                code="prepared_history_snapshot_invalid",
            )
        actual = load_core_json_artifact(self._store, child_ref)
        canon = IRCanonSpec(forbid_floats=False, forbid_nan_inf=False)
        if to_ir_canonical_bytes(actual, canon) != to_ir_canonical_bytes(recomputed_view, canon):
            raise MaskingValidationError(
                "Prepared history data differs from the recomputed as-of view",
                code="prepared_history_projection_mismatch",
            )
        return ref.model_dump(mode="json")

    @staticmethod
    def _masked_view_stats(masked_data: dict[str, Any]) -> dict[str, int | str]:
        metadata = masked_data.get("_backtest_metadata", {})
        stats: dict[str, int | str] = {}
        if isinstance(metadata, dict):
            strategy = metadata.get("masking_strategy")
            step = metadata.get("intervention_step")
            if isinstance(strategy, str):
                stats["masking_strategy"] = strategy
            if isinstance(step, int):
                stats["intervention_step"] = step
        return stats

    def _persist_masked_view(
        self,
        plan: HistoricalValidationPlan,
        masked_data: dict[str, Any],
    ) -> dict[str, str]:
        """Persist and bind the immutable masked view consumed by Scientist."""
        canon_spec = IRCanonSpec(forbid_floats=False, forbid_nan_inf=False)
        data_ref = CoreArtifactRef.model_validate(
            put_json_artifact(
                _ensure_ir_artifact_store(self._store),
                masked_data,
                kind="scientist.backtest.masked_historical_view",
                schema_name="polisyos.scientist.backtesting.MaskedHistoricalView",
                schema_version="1.0",
                canon_spec=canon_spec,
                return_selected_profile=True,
            )
        )
        lineage_inputs: list[InputRefLike] = [
            input_ref_from_artifact_ref(data_ref, role="masked_data")
        ]
        if plan.historical_replay_source is not None:
            lineage_inputs.append(
                input_ref_from_artifact_ref(
                    plan.historical_replay_source.source_data_ref, role="historical_data"
                )
            )
        elif plan.historical_data_ref:
            try:
                lineage_inputs.append(
                    InputRef(artifact_id=plan.historical_data_ref, role="historical_data")
                )
            except ValueError:
                pass

        snapshot = DataSnapshot(
            # Preserve the v0.2.0 snapshot body used by existing ModelSpecs.
            # Foundry restores the selected child from the masked_data edge.
            data_ref=data_ref.model_copy(update={"manifest_profile_sha256": None}),
            stats=self._masked_view_stats(masked_data),
            notes=[
                "scientist.backtest.masked_historical_view",
                f"plan_id:{plan.plan_id}",
            ],
        )
        return put_json_artifact(
            _ensure_ir_artifact_store(self._store),
            snapshot.model_dump(mode="json"),
            kind="fabric.data_snapshot",
            schema_name="polisyos.core.DataSnapshot",
            schema_version="0.2.0",
            inputs=lineage_inputs,
            canon_spec=canon_spec,
            return_selected_profile=True,
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

    def _validate_trust_projection_before_persist(self, report: BacktestReport) -> BacktestReport:
        """Recompute TrustScorer output from source rows before the CAS write."""
        if not report.trust_eligible:
            return report
        profile = _trust_scorer_profile(self._trust_scorer)
        score, grade = self._trust_scorer.compute(
            scenarios=report.scenarios, biases=report.detected_biases
        )
        if (
            profile is None
            or report.metadata.get("trust_scorer_profile") != profile
            or not report.has_source_bound_exact_zero_metrics()
            or score is None
            or grade is None
            or report.trust_score is None
            or not math.isclose(report.trust_score, score, rel_tol=0.0, abs_tol=1e-12)
            or report.trust_grade != grade
        ):
            report.trust_eligible = False
            report.trust_score = None
            report.trust_grade = None
            report.degraded = True
            if "trust_score_source_reconciliation_failed" not in report.degraded_reasons:
                report.degraded_reasons.append("trust_score_source_reconciliation_failed")
        return report

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
        pooling: BacktestPoolingProjection | None = None,
    ) -> BacktestReport:
        measurement_unqualified = pooling is None and backtest_measurements_need_policy(scenarios)
        unpooled = None
        if measurement_unqualified:
            scenarios = unpooled_backtest_scenarios(scenarios)
            unpooled = summarize_unpooled_backtest(scenarios)
        comparisons = [row for scenario in scenarios for row in scenario.outcome_comparisons]
        pooled_range_limited = False
        if pooling is None and not measurement_unqualified:
            percentage_errors = [
                percentage
                for row in comparisons
                if row.relative_error is not None
                and math.isfinite(percentage := row.relative_error * 100.0)
            ]
            totals = summarize_backtest_errors(
                [row.y_pred - row.y_true for row in comparisons], percentage_errors
            )
            rmse_values = [item.rmse for item in scenarios if item.rmse is not None]
            coverage_values = [
                item.coverage_probability
                for item in scenarios
                if item.coverage_probability is not None
            ]
            overall_rmse = totals.rmse if comparisons else backtest_mean(rmse_values)
            overall_mae = (
                totals.mae
                if comparisons
                else backtest_mean([item.mae for item in scenarios if item.mae is not None])
            )
            overall_mape = (
                totals.mape
                if percentage_errors
                else backtest_mean([item.mape for item in scenarios if item.mape is not None])
            )
            interval_evaluated = sum(item.interval_evaluated_count for item in scenarios)
            interval_hits = sum(item.interval_hit_count for item in scenarios)
            overall_coverage = (
                float(interval_hits / interval_evaluated)
                if interval_evaluated > 0
                else (float(np.mean(coverage_values)) if coverage_values else None)
            )
            overall_macro_rmse = backtest_mean(rmse_values)
            pooled_range_limited = bool(totals.unavailable_error_sums)
        else:
            combined = pooling.combined_stratum if pooling is not None else None
            overall_rmse = combined.micro_rmse if combined else None
            overall_mae = combined.micro_mae if combined else None
            overall_macro_rmse = combined.weighted_macro_rmse if combined else None
            overall_mape = None
            overall_coverage = None
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
        if interval_contracts:
            metadata_payload["interval_contracts"] = interval_contracts
        if trust_screening is not TrustScreeningMode.DEFAULT:
            metadata_payload["trust_screening"] = trust_screening.value
        trust_profile = _trust_scorer_profile(self._trust_scorer)
        metadata_payload["trust_scorer_profile"] = trust_profile

        if pooling is None and not measurement_unqualified:
            biases, metric_diagnostics, statistical_degraded_reasons = (
                self._detect_systematic_biases(scenarios)
            )
        else:
            biases, metric_diagnostics = [], []
            if pooling is None:
                statistical_degraded_reasons = ["measurement_comparability_not_established"]
            else:
                statistical_degraded_reasons = ["backtest_pooling_candidate_only"]
                if len(pooling.strata) > 1:
                    statistical_degraded_reasons.append("distinct_measurement_strata")
                if pooling.unavailable:
                    statistical_degraded_reasons.append("incomplete_backtest_measure_comparability")
        all_degraded_reasons = [*degraded_reasons, *statistical_degraded_reasons]
        if pooled_range_limited or any(item.numerical_range is not None for item in scenarios):
            all_degraded_reasons.append("backtest_numerical_range")
        if trust_profile is None:
            all_degraded_reasons.append("trust_scorer_profile_unavailable")
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

        candidate_diagnostic = metadata_payload.get("purpose") == "candidate_diagnostic"
        if candidate_diagnostic:
            all_degraded_reasons.append("candidate_diagnostic_not_for_trust")
            degraded = True
        trust_eligible = (
            bool(scenarios)
            and not degraded
            and not candidate_diagnostic
            and all(has_complete_point_comparisons(scenario) for scenario in scenarios)
        )
        trust_score, trust_grade = (None, None)
        if trust_eligible:
            trust_score, trust_grade = self._trust_scorer.compute(
                scenarios=scenarios, biases=biases
            )

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
            n_metrics_evaluated=len(comparisons),
            aggregation_policy=(
                "preselected_weighted_measurement_strata"
                if pooling is not None
                else "measurement_comparability_not_established"
                if measurement_unqualified
                else "micro_rmse_with_explicit_equal_scenario_macro"
                if scenarios
                else None
            ),
            pooling=pooling,
            unpooled_strata=unpooled,
            detected_biases=biases,
            metric_diagnostics=metric_diagnostics,
            overall_bias_direction=(
                BiasDirection.UNKNOWN
                if pooling is not None or measurement_unqualified
                else self._aggregate_bias_direction(biases, metric_diagnostics)
            ),
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
    ) -> tuple[list[SystematicBias], list[MetricBiasDiagnostic], list[str]]:
        errors_by_metric: dict[str, list[float]] = {}
        for scenario in scenarios:
            for comparison in scenario.outcome_comparisons:
                errors_by_metric.setdefault(comparison.metric_name, []).append(
                    comparison.y_pred - comparison.y_true
                )

        biases: list[SystematicBias] = []
        diagnostics: list[MetricBiasDiagnostic] = []
        degraded_reasons: list[str] = []
        for metric, errors in sorted(errors_by_metric.items()):
            values = np.asarray(errors, dtype=float)
            mean = backtest_mean(errors)
            if mean is None:
                raise ValueError("metric diagnostic missing source residuals")
            exact_zero = bool(np.all(values == 0.0))
            test_result = self._two_sided_ttest(values)
            matching_scenarios = [
                scenario
                for scenario in scenarios
                if any(item.metric_name == metric for item in scenario.outcome_comparisons)
            ]
            residual_sign = "positive" if mean > 0 else "negative" if mean < 0 else "zero"
            diagnostics.append(
                MetricBiasDiagnostic(
                    metric_name=metric,
                    status="exact_zero" if exact_zero else test_result.status,
                    n=len(errors),
                    mean_residual=mean,
                    magnitude=float(abs(mean)),
                    residual_sign="zero" if exact_zero else residual_sign,
                    direction_status="not_applicable" if exact_zero else "not_established",
                    scope={
                        "scenario_ids": [scenario.scenario_id for scenario in matching_scenarios],
                        "holdout_windows": sorted(
                            {
                                str(window)
                                for scenario in matching_scenarios
                                for window in scenario.metadata.get("holdout_windows", [])
                            }
                        ),
                        "selected_training_roles": sorted(
                            {
                                str(scenario.metadata["selected_training_role"])
                                for scenario in matching_scenarios
                                if scenario.metadata.get("selected_training_role")
                            }
                        ),
                        "selected_validation_roles": sorted(
                            {
                                str(scenario.metadata["selected_validation_role"])
                                for scenario in matching_scenarios
                                if scenario.metadata.get("selected_validation_role")
                            }
                        ),
                        "selected_holdout_roles": sorted(
                            {
                                str(scenario.metadata["selected_holdout_role"])
                                for scenario in matching_scenarios
                                if scenario.metadata.get("selected_holdout_role")
                            }
                        ),
                    },
                    method_id=None if exact_zero else test_result.method_id,
                    backend_id=None if exact_zero else test_result.backend_id,
                    backend_version=None if exact_zero else test_result.backend_version,
                    statistic=None if exact_zero else test_result.statistic,
                    p_value=None if exact_zero else test_result.p_value,
                    reason=None if exact_zero else test_result.reason,
                    unresolved_assumptions=(
                        [
                            "residual_independence",
                            "multiplicity_policy",
                            "population_scope",
                        ]
                        if exact_zero
                        else [
                            "residual_independence",
                            "multiplicity_policy",
                            "population_scope",
                            "metric_direction",
                        ]
                    ),
                )
            )
            if exact_zero:
                continue

            degraded_reasons.append(f"metric_direction_not_established:{metric}")
            if test_result.p_value is None:
                degraded_reasons.append(
                    f"bias_statistical_test_{test_result.status}:{metric}:{test_result.reason}"
                )
            if mean == 0.0:
                continue
            biases.append(
                SystematicBias(
                    bias_type="descriptive_residual",
                    direction=BiasDirection.UNKNOWN,
                    magnitude=float(abs(mean)),
                    affected_metrics=[metric],
                    description=(
                        f"A signed residual was observed for metric '{metric}'; "
                        "metric orientation is not established."
                    ),
                    statistical_test=test_result.test_name or test_result.reason or "not_executed",
                    p_value=test_result.p_value,
                    metadata={
                        "diagnostic": "descriptive_residual",
                        "residual_sign": residual_sign,
                        "direction_status": "not_established",
                        "test_status": test_result.status,
                        **({"test_reason": test_result.reason} if test_result.reason else {}),
                    },
                )
            )
        return biases, diagnostics, degraded_reasons

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

        if bool(np.all(errors == errors[0])):
            return _TTestResult(
                p_value=None,
                test_name=None,
                status="not_computable",
                reason="zero_variance",
            )

        unavailable_range = _TTestResult(
            p_value=None,
            test_name=None,
            status="unavailable",
            reason="scipy_ttest_1samp_numeric_range",
        )
        if not bool(np.all(np.isfinite(errors))):
            return unavailable_range
        residuals = errors.tolist()
        average = backtest_mean(residuals)
        if average is None:
            return unavailable_range
        scale, normalized_std = backtest_sample_spread(residuals, average)
        if normalized_std == 0.0:
            return unavailable_range
        expected_statistic = (average / scale) / (normalized_std / math.sqrt(n))
        if not math.isfinite(expected_statistic) or (expected_statistic == 0.0 and average != 0.0):
            return unavailable_range

        # Positive rescaling preserves the test while keeping the backend's raw variance finite.
        source_std = scale * normalized_std
        source_variance = source_std * source_std
        backend_errors = (
            errors if float_info.min <= source_variance <= float_info.max / n else errors / scale
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
            result = ttest_1samp(backend_errors, popmean=0.0, alternative="two-sided")
            p_value = float(result.pvalue)
            if not math.isfinite(p_value) or not 0.0 <= p_value <= 1.0:
                return _TTestResult(
                    p_value=None,
                    test_name=None,
                    status="unavailable",
                    reason="scipy_ttest_1samp_invalid_result",
                )
            scipy = import_module("scipy")
            statistic = float(result.statistic)
            if not math.isfinite(statistic):
                return _TTestResult(
                    p_value=None,
                    test_name=None,
                    status="unavailable",
                    reason="scipy_ttest_1samp_invalid_statistic",
                )
            if not math.isclose(
                statistic,
                expected_statistic,
                rel_tol=1e-9,
                abs_tol=0.0 if expected_statistic != 0.0 else 1e-12,
            ):
                return unavailable_range
            return _TTestResult(
                p_value=p_value,
                test_name="one-sample t-test H0(mean_error=0)",
                status="available",
                method_id="scipy.stats.ttest_1samp",
                backend_id="scipy",
                backend_version=str(getattr(scipy, "__version__", "")) or None,
                statistic=statistic,
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
    def _aggregate_bias_direction(
        biases: list[SystematicBias],
        diagnostics: list[MetricBiasDiagnostic] | None = None,
    ) -> BiasDirection:
        if diagnostics and any(item.direction_status == "not_established" for item in diagnostics):
            return BiasDirection.UNKNOWN
        if not biases:
            return BiasDirection.NEUTRAL
        directions = {item.direction for item in biases}
        if BiasDirection.UNKNOWN in directions:
            return BiasDirection.UNKNOWN
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
