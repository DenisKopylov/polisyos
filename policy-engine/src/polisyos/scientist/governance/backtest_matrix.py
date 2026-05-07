"""Run and summarize required historical backtest slices for promotion review.

The matrix runner groups `BacktestPlanBundle` inputs by `BacktestKind`, executes
them through the backtesting orchestrator, and persists a single
`BacktestReportRef` plus per-kind coverage diagnostics. Calibration governance
uses the resulting gap flags and worst-kind summary to block promotions when a
required observational regime is missing or weak.
"""

from __future__ import annotations

from collections import defaultdict
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts.manifest import InputRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.backtest import BacktestReportRef
from polisyos.ir.analytics.backtest import BacktestScenario, persist_backtest_report
from polisyos.ir.observation.bundles import BacktestPlanBundle
from polisyos.ir.observation.contracts import ObservationFamily
from polisyos.scientist.methods.backtesting.orchestrator import BacktestOrchestrator, _collapse_modes
from polisyos.scientist.methods.backtesting.plan import HistoricalValidationPlan


class BacktestKind(str, Enum):
    """Required backtest channel in calibration governance.

    The kinds partition historical validation into macro, cell,
    strategic-agent, household, and distress evidence slices so promotion
    decisions can require coverage across distinct observational regimes.
    """

    MACRO = "macro"
    CELL = "cell"
    STRATEGIC_AGENT = "strategic_agent"
    HOUSEHOLD = "household"
    DISTRESS = "distress"


_BACKTEST_KIND_FAMILIES: dict[BacktestKind, tuple[ObservationFamily, ...]] = {
    BacktestKind.MACRO: (ObservationFamily.MACRO_STATE,),
    BacktestKind.CELL: (
        ObservationFamily.BUDGET_FLOWS,
        ObservationFamily.PUBLIC_SERVICE_DOMAIN_FLOWS,
    ),
    BacktestKind.STRATEGIC_AGENT: (ObservationFamily.PROCUREMENT_FLOWS,),
    BacktestKind.HOUSEHOLD: (
        ObservationFamily.HOUSEHOLD_DISTRIBUTION,
        ObservationFamily.LABOR_MARKET,
    ),
    BacktestKind.DISTRESS: (ObservationFamily.DISTRESS_ENFORCEMENT,),
}


class BacktestKindResult(BaseModel):
    """Per-kind summary for one required backtest slice."""

    model_config = ConfigDict(extra="forbid")

    kind: BacktestKind
    status: str = Field(pattern="^(ok|gap|error)$")
    score: float | None = Field(default=None, ge=0.0, le=1.0)
    n_plans: int = Field(default=0, ge=0)
    n_scenarios: int = Field(default=0, ge=0)
    scenario_ids: list[str] = Field(default_factory=list)
    observation_families: list[ObservationFamily] = Field(default_factory=list)
    gap_flag: str | None = None
    notes: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BacktestMatrixResult(BaseModel):
    """Aggregate calibration-governance view over all required backtest kinds.

    `gap_flags` enumerates missing evidence channels, `composite_score` provides
    the promotion score, and `backtest_report_ref` links to the persisted replay
    artifact for audit and downstream leaderboard scoring.
    """

    model_config = ConfigDict(extra="forbid")

    report_id: str = Field(min_length=1)
    backtest_report_ref: BacktestReportRef | None = None
    kind_results: list[BacktestKindResult] = Field(default_factory=list)
    composite_score: float | None = Field(default=None, ge=0.0, le=1.0)
    worst_kind: BacktestKind | None = None
    gap_flags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BacktestMatrixRunner:
    """Runner that executes the required backtest matrix for promotion review.

    It fans out historical validation plans by `BacktestKind`, aggregates the
    resulting `BacktestReport`, and computes a composite score plus gap flags
    for any missing evidence channel.
    """

    def __init__(
        self,
        store: FileSystemCAS,
        *,
        orchestrator: BacktestOrchestrator | None = None,
    ) -> None:
        self._store = store
        self._orchestrator = orchestrator or BacktestOrchestrator(cas=store)

    def run(
        self,
        bundles: dict[BacktestKind, BacktestPlanBundle],
        *,
        inputs: list[InputRef] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> BacktestMatrixResult:
        """Execute all required backtest kinds and persist the aggregate report.

        Args:
            bundles: Backtest plans keyed by the required matrix slice.
            inputs: Optional provenance refs to attach to the persisted report.
            metadata: Additional report metadata propagated into the aggregate
                `BacktestReport`.

        Returns:
            `BacktestMatrixResult` with one `kind_results` item per required
            backtest kind, plus a persisted report ref and composite summary.
        """

        scenario_groups: dict[BacktestKind, list[BacktestScenario]] = defaultdict(list)
        kind_results: list[BacktestKindResult] = []
        report_scenarios: list[BacktestScenario] = []
        gap_flags: list[str] = []
        requested_modes: list[str] = []
        effective_modes: list[str] = []
        degraded_reasons: list[str] = []

        for kind in BacktestKind:
            bundle = bundles.get(kind)
            if bundle is None or not bundle.plans:
                gap_flag = f"missing_backtest_bundle:{kind.value}"
                gap_flags.append(gap_flag)
                kind_results.append(
                    BacktestKindResult(
                        kind=kind,
                        status="gap",
                        gap_flag=gap_flag,
                        observation_families=list(_BACKTEST_KIND_FAMILIES[kind]),
                        notes=[
                            "No BacktestPlanBundle was supplied for this required backtest kind."
                        ],
                    )
                )
                continue

            notes: list[str] = []
            for plan in bundle.plans:
                scenario_plan = self._decorate_plan(kind, bundle, plan)
                (
                    scenario,
                    scenario_warnings,
                    requested_mode,
                    effective_mode,
                    scenario_degraded_reasons,
                ) = self._orchestrator._run_single_scenario(scenario_plan)
                scenario.metadata = {
                    **dict(scenario.metadata),
                    "backtest_kind": kind.value,
                    "observation_families": [
                        family.value for family in _BACKTEST_KIND_FAMILIES[kind]
                    ],
                    "source_contract_id": bundle.contract_target.contract_id,
                    "source_contract_fqn": bundle.contract_target.contract_fqn,
                    "holdout_windows": list(bundle.holdout_windows),
                }
                scenario_groups[kind].append(scenario)
                report_scenarios.append(scenario)
                requested_modes.append(requested_mode)
                effective_modes.append(effective_mode)
                degraded_reasons.extend(str(item) for item in scenario_degraded_reasons)
                notes.extend(str(item) for item in scenario_warnings)

            scenarios_for_kind = scenario_groups[kind]
            kind_results.append(
                BacktestKindResult(
                    kind=kind,
                    status="ok",
                    score=_score_backtest_scenarios(scenarios_for_kind),
                    n_plans=len(bundle.plans),
                    n_scenarios=len(scenarios_for_kind),
                    scenario_ids=[scenario.scenario_id for scenario in scenarios_for_kind],
                    observation_families=list(_BACKTEST_KIND_FAMILIES[kind]),
                    notes=notes,
                    metadata={
                        "holdout_windows": list(bundle.holdout_windows),
                        "historical_payload_keys": sorted(bundle.historical_payloads.keys()),
                    },
                )
            )

        report_id = f"BTM_{uuid4().hex[:12]}"
        report = self._orchestrator._aggregate(
            report_id=report_id,
            scenarios=report_scenarios,
            metadata={
                "backtest_kinds": {
                    result.kind.value: {
                        "status": result.status,
                        "score": result.score,
                        "gap_flag": result.gap_flag,
                    }
                    for result in kind_results
                },
                "required_backtest_kinds": [kind.value for kind in BacktestKind],
                **dict(metadata or {}),
            },
            prediction_mode_requested=_collapse_modes(requested_modes),
            prediction_mode_effective=_collapse_modes(effective_modes),
            degraded_reasons=degraded_reasons,
        )
        report_ref = persist_backtest_report(self._store, report, inputs=inputs)
        report.cas_artifact_id = str(report_ref.artifact_id)
        composite_score = _mean_defined(result.score for result in kind_results)
        scored_results = [result for result in kind_results if result.score is not None]
        worst_kind = (
            min(
                scored_results,
                key=lambda item: (item.score if item.score is not None else 1.0, item.kind.value),
            ).kind
            if scored_results
            else None
        )
        return BacktestMatrixResult(
            report_id=report.report_id,
            backtest_report_ref=report_ref,
            kind_results=kind_results,
            composite_score=composite_score,
            worst_kind=worst_kind,
            gap_flags=gap_flags,
            metadata={
                "n_present_kinds": sum(1 for result in kind_results if result.status == "ok"),
                "report_degraded": report.degraded,
                "report_trust_eligible": report.trust_eligible,
            },
        )

    def _decorate_plan(
        self,
        kind: BacktestKind,
        bundle: BacktestPlanBundle,
        plan: HistoricalValidationPlan,
    ) -> HistoricalValidationPlan:
        decorated_metadata = {
            **dict(plan.metadata),
            "backtest_kind": kind.value,
            "observation_families": [family.value for family in _BACKTEST_KIND_FAMILIES[kind]],
            "source_contract_id": bundle.contract_target.contract_id,
        }
        return plan.model_copy(
            update={
                "plan_id": f"{kind.value}:{plan.plan_id}",
                "plan_label": f"{kind.value}:{plan.plan_label or plan.plan_id}",
                "metadata": decorated_metadata,
            }
        )


def _score_backtest_scenarios(scenarios: list[BacktestScenario]) -> float | None:
    if not scenarios:
        return None
    scenario_scores: list[float] = []
    for scenario in scenarios:
        components: list[float] = []
        if scenario.rmse is not None:
            components.append(1.0 / (1.0 + float(scenario.rmse)))
        if scenario.mae is not None:
            components.append(1.0 / (1.0 + float(scenario.mae)))
        if scenario.mape is not None:
            components.append(1.0 / (1.0 + (float(scenario.mape) / 100.0)))
        if scenario.coverage_probability is not None:
            components.append(float(scenario.coverage_probability))
        if not components:
            continue
        scenario_scores.append(sum(components) / len(components))
    return _clamp(_mean_defined(scenario_scores))


def _mean_defined(values) -> float | None:
    finite = [float(value) for value in values if value is not None]
    if not finite:
        return None
    return sum(finite) / len(finite)


def _clamp(value: float | None) -> float | None:
    if value is None:
        return None
    return max(0.0, min(1.0, float(value)))


__all__ = [
    "BacktestKind",
    "BacktestKindResult",
    "BacktestMatrixResult",
    "BacktestMatrixRunner",
]
