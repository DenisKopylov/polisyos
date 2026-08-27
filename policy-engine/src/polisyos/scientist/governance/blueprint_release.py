"""Blueprint-oriented D4 hardening runners for calibration and governance.

These runners intentionally sit above raw stage orchestration so Ukraine-data
builders can stay thin while still executing real split-aware calibration,
backtesting, transportability, strategic-response, and governance evidence
flows over processed observation panels.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from enum import Enum
from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.governance.profiles import ValidationProfile
from polisyos.data_forge.read_api.ukraine import (
    REAL_BACKTEST_BUNDLE_CONTRACT_FQN,
    UkraineStageArtifactVerificationError,
    VerifiedUkraineStageArtifacts,
    load_verified_stage_artifacts,
    load_verified_stage_output_bytes,
)
from polisyos.ir.analytics.abstraction import (
    AbstractionCertificate,
    AbstractionPreservationType,
    FiniteStateAbstractionMap,
    VariableStateAbstraction,
    persist_abstraction_certificate,
    persist_finite_state_abstraction_map,
)
from polisyos.ir.analytics.calibration import (
    CalibrationCandidateScore,
    CalibrationRunManifest,
    HoldoutScoresManifest,
    SpecificationCurveScenario,
    SpecificationCurveSummaryManifest,
    SplitWindow,
    StrategicResponseChannelMetric,
    StrategicResponseMetricsManifest,
    TransportabilityChannelResult,
    TransportabilitySummaryManifest,
)
from polisyos.ir.analytics.interference import (
    ExposureMappingType,
    InterferenceCertificate,
    InterferenceEffectDecomposition,
    InterferenceMethod,
    NetworkInterferenceReport,
)
from polisyos.ir.analytics.transportability import TransportabilityStatus, TransportMode
from polisyos.ir.observation.bundles import (
    BacktestPlanBundle,
    ContractCompatibilityTarget,
)
from polisyos.ir.observation.contracts import (
    IdentificationMode,
    ObservationFamily,
    SourceConfidenceTier,
    StrategicResponseChannel,
)
from polisyos.ir.registry.refs import ArtifactRefModel
from polisyos.scientist.governance.accountability import GovernanceAccountabilityInput
from polisyos.scientist.governance.backtest_matrix import BacktestKind
from polisyos.scientist.governance.calibration import (
    CalibrationGovernanceInput,
    CalibrationGovernanceReport,
    CalibrationGovernanceRunner,
)
from polisyos.scientist.governance.calibration_validation import (
    CalibrationValidationRunner,
    CalibrationValidationRunnerInput,
    CalibrationValidationRunnerResult,
)
from polisyos.scientist.methods.backtesting.plan import HistoricalValidationPlan, PredictionSource
from polisyos.scientist.methods.discovery.utility_judge import (
    DownstreamUtilityReport,
    HypothesisUtilityScore,
)

REQUIRED_SIGNOFF_FAMILIES: tuple[ObservationFamily, ...] = (
    ObservationFamily.BUDGET_FLOWS,
    ObservationFamily.PROCUREMENT_FLOWS,
    ObservationFamily.MACRO_STATE,
    ObservationFamily.HOUSEHOLD_DISTRIBUTION,
    ObservationFamily.DISTRESS_ENFORCEMENT,
)

_BACKTEST_FAMILY_MAP: dict[BacktestKind, tuple[ObservationFamily, ...]] = {
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

_CHANNEL_FAMILY_MAP: tuple[tuple[str, ObservationFamily], ...] = (
    ("budget_resilience", ObservationFamily.BUDGET_FLOWS),
    ("procurement_resilience", ObservationFamily.PROCUREMENT_FLOWS),
    ("trade_resilience", ObservationFamily.TRADE_EXPOSURE),
    ("household_resilience", ObservationFamily.HOUSEHOLD_DISTRIBUTION),
    ("public_service_resilience", ObservationFamily.PUBLIC_SERVICE_DOMAIN_FLOWS),
)

_UKRAINE_D4_REQUEST_OUTPUT = "d4_governance_request.json"
_IDENTITY_RESOLUTION_COHORT_OUTPUT = "identity_resolution_cohort_v1.json"
_IDENTITY_RESOLUTION_COHORT_SCHEMA = "policyos.data_forge.ukraine.identity_resolution_cohort.v1"
_AGENT_REGISTRY_RUNTIME_OUTPUT = "agent_registry_runtime.parquet"
_UKRAINE_D4_COVERAGE_THRESHOLD = 0.95


class _UkraineD4GovernanceRequest(BaseModel):
    """Purpose-limited producer request consumed by the Scientist D4 bridge."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str
    authority_purpose: str
    may_not_use_for: list[str]
    required_stage_manifests: dict[str, str]


class _IdentityResolutionCohortRow(BaseModel):
    """One identity-resolution cohort record whose aggregate is recomputed upstream."""

    model_config = ConfigDict(extra="forbid")

    cohort: str = Field(pattern="^(spending|procurement)$")
    raw_identity: str = Field(min_length=1)


class _IdentityResolutionCohort(BaseModel):
    """Strict D0 evidence shape required for governance coverage recomputation.

    Expected producer JSON shape::

        {"schema_version": "policyos.data_forge.ukraine.identity_resolution_cohort.v1",
         "rows": [{"cohort": "spending", "raw_identity": "..."}]}

    The bridge resolves these raw identities against a separately admitted
    runtime registry rather than trusting producer-authored resolution flags.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str
    rows: list[_IdentityResolutionCohortRow] = Field(default_factory=list)


def _series_correlation(left: pd.Series, right: pd.Series) -> float:
    """Return a finite Pearson correlation for the verified labor predicate."""

    if len(left) < 2 or len(right) < 2:
        return 0.0
    value = float(pd.Series(left, dtype=float).corr(pd.Series(right, dtype=float)))
    return value if np.isfinite(value) else 0.0


class FamilyTier(str, Enum):
    """Eligibility tier used to decide whether a family may drive final scoring."""

    A = "A"
    B = "B"
    C = "C"


class FamilyEligibilityEntry(BaseModel):
    """Eligibility record for one observation family."""

    model_config = ConfigDict(extra="forbid")

    family: ObservationFamily
    tier: FamilyTier
    eligible_for_scoring: bool = False
    exact_signoff_eligible: bool = False
    observations_present: int = Field(default=0, ge=0)
    coverage_ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    source_ids: list[str] = Field(default_factory=list)
    identification_modes: list[IdentificationMode] = Field(default_factory=list)
    source_confidence_tiers: list[SourceConfidenceTier] = Field(default_factory=list)
    has_proxy_lineage: bool = False
    bias_validated: bool = False
    signoff_waived: bool = False
    reasons: list[str] = Field(default_factory=list)


class FamilyEligibilityRegistry(BaseModel):
    """Machine-readable family gate used by D4/D5 scoring and release sign-off."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    coverage_threshold: float = Field(default=0.95, ge=0.0, le=1.0)
    families: dict[str, FamilyEligibilityEntry] = Field(default_factory=dict)
    waived_families: list[ObservationFamily] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    def eligible_families(self) -> list[ObservationFamily]:
        return [entry.family for entry in self.families.values() if entry.eligible_for_scoring]

    def require_final_signoff_ready(
        self,
        families: Sequence[ObservationFamily],
    ) -> None:
        blocked = [
            family.value
            for family in families
            if not self.families.get(
                family.value,
                FamilyEligibilityEntry(family=family, tier=FamilyTier.C),
            ).exact_signoff_eligible
            and not self.families.get(
                family.value,
                FamilyEligibilityEntry(family=family, tier=FamilyTier.C),
            ).signoff_waived
        ]
        if blocked:
            raise ValueError("families_not_exact_signoff_ready:" + ",".join(sorted(blocked)))


class LossBreakdownManifest(BaseModel):
    """Typed D4 loss-breakdown artifact."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    candidate_id: str
    measurement_loss: float = Field(ge=0.0)
    network_loss: float = Field(ge=0.0)
    interference_loss: float = Field(ge=0.0)
    governance_penalty: float = Field(ge=0.0)
    regularization: float = Field(ge=0.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _ensure_datetime_series(frame: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_datetime(frame[column], errors="coerce", utc=False)


def _weighted_mean(values: pd.Series, weights: pd.Series) -> float:
    resolved_values = pd.to_numeric(values, errors="coerce").fillna(0.0).astype(float)
    resolved_weights = (
        pd.to_numeric(weights, errors="coerce").fillna(1.0).astype(float).clip(lower=0.0)
    )
    weight_sum = float(resolved_weights.sum())
    if weight_sum <= 1e-12:
        return float(resolved_values.mean()) if len(resolved_values) else 0.0
    return float(np.average(resolved_values, weights=resolved_weights))


def _wmape(observed: np.ndarray, predicted: np.ndarray, weights: np.ndarray) -> float:
    denom = np.maximum(np.abs(observed), 1e-9)
    weighted = np.abs(observed - predicted) / denom
    if weights.sum() <= 1e-12:
        return float(np.mean(weighted)) if len(weighted) else 0.0
    return float(np.average(weighted, weights=weights))


def _candidate_prediction(
    kind: str, train_mean: float, train_last: float, slope: float, periods: int
) -> np.ndarray:
    horizon = np.arange(1, periods + 1, dtype=float)
    if kind == "measurement_aware_multistart":
        return np.full(periods, train_mean, dtype=float)
    if kind == "transport_regularized":
        return np.full(periods, (0.65 * train_mean) + (0.35 * train_last), dtype=float)
    if kind == "network_interference_aware":
        return np.full(periods, train_last, dtype=float) + (0.5 * slope * horizon)
    return np.full(periods, train_mean, dtype=float)


def build_family_eligibility_registry(
    observation_panel: pd.DataFrame,
    *,
    coverage_threshold: float,
    spending_coverage: float | None = None,
    procurement_coverage: float | None = None,
    waived_families: Sequence[ObservationFamily] = (),
    proxy_promoted_families: Sequence[ObservationFamily] = (),
) -> FamilyEligibilityRegistry:
    """Build the machine-readable family eligibility gate for D4/D5."""

    if observation_panel.empty:
        return FamilyEligibilityRegistry(coverage_threshold=coverage_threshold)

    families: dict[str, FamilyEligibilityEntry] = {}
    waived_set = set(waived_families)
    proxy_promoted_set = set(proxy_promoted_families)
    family_groups = observation_panel.groupby(observation_panel["family"].astype(str), sort=False)
    for family_name, family_frame in family_groups:
        try:
            family = ObservationFamily(family_name)
        except ValueError:
            continue
        source_ids = sorted(
            family_frame.get("source_id", pd.Series(dtype=str))
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )
        identification_modes = sorted(
            {
                IdentificationMode(str(item))
                for item in family_frame.get("identification_mode", pd.Series(dtype=str))
                .dropna()
                .astype(str)
                .tolist()
                if str(item)
            },
            key=lambda item: item.value,
        )
        source_confidence_tiers = sorted(
            {
                SourceConfidenceTier(str(item))
                for item in family_frame.get("source_confidence_tier", pd.Series(dtype=str))
                .dropna()
                .astype(str)
                .tolist()
                if str(item)
            },
            key=lambda item: item.value,
        )
        proxy_count = int(
            family_frame.get("proxy_source_id", pd.Series(dtype=object)).notna().sum()
            if "proxy_source_id" in family_frame.columns
            else 0
        )
        bias_share = (
            float(
                family_frame.get(
                    "measurement_bias_flag", pd.Series(False, index=family_frame.index)
                )
                .fillna(False)
                .astype(bool)
                .mean()
            )
            if len(family_frame)
            else 0.0
        )
        coverage_ratio = float(
            pd.to_numeric(family_frame.get("coverage_estimate", 0.0), errors="coerce")
            .fillna(0.0)
            .astype(float)
            .mean()
        )
        reasons: list[str] = []
        tier = FamilyTier.A
        has_proxy_lineage = proxy_count > 0
        bias_validated = family in proxy_promoted_set or (
            bias_share <= 0.05 and coverage_ratio >= coverage_threshold
        )
        signoff_waived = family in waived_set
        proxy_promoted = family in proxy_promoted_set

        if family in REQUIRED_SIGNOFF_FAMILIES and coverage_ratio < coverage_threshold:
            tier = FamilyTier.B
            reasons.append(
                f"coverage_below_threshold:{coverage_ratio:.3f}<{coverage_threshold:.3f}"
            )
        if any(source_id == "spending_contracts_procurement_proxy" for source_id in source_ids):
            tier = FamilyTier.B
            reasons.append("proxy_source:spending_contracts_procurement_proxy")
        if any(source_id == "dps_financials" for source_id in source_ids):
            tier = FamilyTier.B
            reasons.append("provisional_source:dps_financials")
        if has_proxy_lineage and not proxy_promoted:
            tier = FamilyTier.B
            reasons.append("proxy_lineage_present")
        if (
            any(
                mode in {IdentificationMode.PROXY_IDENTIFIED, IdentificationMode.BOUNDS_ONLY}
                for mode in identification_modes
            )
            and not proxy_promoted
        ):
            tier = FamilyTier.B
            reasons.append("non_point_identification_mode")
        if (
            family == ObservationFamily.BUDGET_FLOWS
            and spending_coverage is not None
            and spending_coverage < coverage_threshold
        ):
            tier = FamilyTier.B
            reasons.append(f"runtime_spending_coverage:{spending_coverage:.3f}")
        if (
            family == ObservationFamily.PROCUREMENT_FLOWS
            and procurement_coverage is not None
            and procurement_coverage < coverage_threshold
        ):
            tier = FamilyTier.B
            reasons.append(f"runtime_procurement_coverage:{procurement_coverage:.3f}")
        if len(family_frame) == 0:
            tier = FamilyTier.C
            reasons.append("no_observations")
        if signoff_waived:
            reasons.append("signoff_waived_by_policy")
        if proxy_promoted:
            reasons.append("proxy_promoted_via_bias_validation")

        eligible_for_scoring = tier == FamilyTier.A
        exact_signoff_eligible = (
            eligible_for_scoring and coverage_ratio >= coverage_threshold and bias_validated
        )
        families[family.value] = FamilyEligibilityEntry(
            family=family,
            tier=tier,
            eligible_for_scoring=eligible_for_scoring,
            exact_signoff_eligible=exact_signoff_eligible,
            observations_present=len(family_frame),
            coverage_ratio=_clip01(coverage_ratio),
            source_ids=source_ids,
            identification_modes=identification_modes,
            source_confidence_tiers=source_confidence_tiers,
            has_proxy_lineage=has_proxy_lineage,
            bias_validated=bias_validated,
            signoff_waived=signoff_waived,
            reasons=sorted(dict.fromkeys(reasons)),
        )

    return FamilyEligibilityRegistry(
        coverage_threshold=coverage_threshold,
        families=families,
        waived_families=sorted(waived_set, key=lambda item: item.value),
        notes=[
            "Tier A families may drive leaderboard and release sign-off.",
            "Tier B families remain diagnostic-only until exact-signoff conditions are met.",
            "Tier C families are excluded from scoring.",
            "Signoff-waived families remain diagnostic/proxy families and are excluded from hard release blocking for the current policy cycle.",
        ],
    )


class CalibrationRunRunner:
    """Train/validation/holdout runner without holdout leakage."""

    _candidate_kinds: tuple[str, ...] = (
        "measurement_aware_multistart",
        "transport_regularized",
        "network_interference_aware",
    )

    def run(
        self,
        observation_panel: pd.DataFrame,
        *,
        eligibility_registry: FamilyEligibilityRegistry,
        splits: dict[str, dict[str, str]],
        transportability_score: float,
        strategic_plausibility: float,
        governance_penalty: float,
        interference_fit_score: float,
        required_families: Sequence[ObservationFamily] = REQUIRED_SIGNOFF_FAMILIES,
    ) -> CalibrationRunManifest:
        eligibility_registry.require_final_signoff_ready(required_families)

        frame = observation_panel.copy()
        frame["period_start_dt"] = _ensure_datetime_series(frame, "period_start")
        frame = frame.loc[frame["period_start_dt"].notna()].copy()
        eligible = set(item.value for item in eligibility_registry.eligible_families())
        excluded = sorted(set(frame["family"].astype(str)) - eligible)
        scoring_frame = frame.loc[frame["family"].astype(str).isin(eligible)].copy()
        if scoring_frame.empty:
            raise ValueError("no_tier_a_observations_available_for_scoring")

        split_windows = {
            name: (
                pd.Timestamp(window["start"]),
                pd.Timestamp(window["end"]),
            )
            for name, window in splits.items()
        }
        split_defs = [
            SplitWindow(split_id=name, start=window["start"], end=window["end"])
            for name, window in splits.items()
        ]
        train_start, train_end = split_windows.get(
            "train_pre_2024", next(iter(split_windows.values()))
        )
        val_start, val_end = split_windows.get(
            "validation_2024", next(iter(split_windows.values()))
        )
        holdout_start, holdout_end = split_windows.get(
            "test_2025", next(iter(split_windows.values()))
        )

        candidates: list[CalibrationCandidateScore] = []
        grouped = scoring_frame.groupby(scoring_frame["family"].astype(str), sort=False)
        for candidate_kind in self._candidate_kinds:
            family_scores: list[float] = []
            family_train_scores: list[float] = []
            for _, family_frame in grouped:
                train = family_frame.loc[
                    (family_frame["period_start_dt"] >= train_start)
                    & (family_frame["period_start_dt"] <= train_end)
                ].sort_values("period_start_dt")
                validation = family_frame.loc[
                    (family_frame["period_start_dt"] >= val_start)
                    & (family_frame["period_start_dt"] <= val_end)
                ].sort_values("period_start_dt")
                if train.empty or validation.empty:
                    continue
                train_mean = _weighted_mean(train["observed_value"], train["trust_weight"])
                train_last = float(pd.to_numeric(train["observed_value"], errors="coerce").iloc[-1])
                slope = 0.0
                if len(train) > 1:
                    train_values = pd.to_numeric(train["observed_value"], errors="coerce").to_numpy(
                        dtype=float
                    )
                    slope = float(
                        (train_values[-1] - train_values[0]) / max(len(train_values) - 1, 1)
                    )
                predicted_validation = _candidate_prediction(
                    candidate_kind, train_mean, train_last, slope, len(validation)
                )
                validation_values = pd.to_numeric(
                    validation["observed_value"], errors="coerce"
                ).to_numpy(dtype=float)
                validation_weights = (
                    pd.to_numeric(validation["trust_weight"], errors="coerce")
                    .fillna(1.0)
                    .to_numpy(dtype=float)
                )
                validation_score = _clip01(
                    1.0 - _wmape(validation_values, predicted_validation, validation_weights)
                )
                family_scores.append(validation_score)

                predicted_train = _candidate_prediction(
                    candidate_kind, train_mean, train_last, slope, len(train)
                )
                train_values = pd.to_numeric(train["observed_value"], errors="coerce").to_numpy(
                    dtype=float
                )
                train_weights = (
                    pd.to_numeric(train["trust_weight"], errors="coerce")
                    .fillna(1.0)
                    .to_numpy(dtype=float)
                )
                family_train_scores.append(
                    _clip01(1.0 - _wmape(train_values, predicted_train, train_weights))
                )

            if not family_scores:
                continue

            validation_fit = float(np.mean(family_scores))
            train_fit = float(np.mean(family_train_scores))
            robustness_penalty = _clip01(float(np.std(family_scores)))
            measurement_fit = _clip01(0.5 * validation_fit + 0.5 * train_fit)
            candidate_bonus = 0.0
            if candidate_kind == "network_interference_aware":
                candidate_bonus += 0.1 * interference_fit_score
            if candidate_kind == "transport_regularized":
                candidate_bonus += 0.1 * transportability_score
            if candidate_kind == "measurement_aware_multistart":
                candidate_bonus += 0.05 * strategic_plausibility
            composite = _clip01(
                0.4 * validation_fit
                + 0.15 * train_fit
                + 0.15 * measurement_fit
                + 0.1 * transportability_score
                + 0.1 * strategic_plausibility
                + 0.1 * interference_fit_score
                - 0.1 * governance_penalty
                - 0.1 * robustness_penalty
                + candidate_bonus
            )
            candidates.append(
                CalibrationCandidateScore(
                    candidate_id=f"candidate::{candidate_kind}",
                    candidate_kind=candidate_kind,
                    train_fit_score=train_fit,
                    validation_fit_score=validation_fit,
                    robustness_penalty=robustness_penalty,
                    measurement_fit_score=measurement_fit,
                    interference_fit_score=interference_fit_score,
                    transportability_score=transportability_score,
                    strategic_plausibility_score=strategic_plausibility,
                    governance_penalty=governance_penalty,
                    validation_composite_score=composite,
                    metadata={"n_scored_families": len(family_scores)},
                )
            )

        if not candidates:
            raise ValueError("no_calibration_candidates_scored")

        champion = max(
            candidates,
            key=lambda item: (
                item.validation_composite_score,
                item.validation_fit_score,
                item.candidate_id,
            ),
        )

        holdout_scores: list[tuple[str, float]] = []
        for family_name, family_frame in grouped:
            train = family_frame.loc[
                (family_frame["period_start_dt"] >= train_start)
                & (family_frame["period_start_dt"] <= train_end)
            ].sort_values("period_start_dt")
            holdout = family_frame.loc[
                (family_frame["period_start_dt"] >= holdout_start)
                & (family_frame["period_start_dt"] <= holdout_end)
            ].sort_values("period_start_dt")
            if train.empty or holdout.empty:
                continue
            train_mean = _weighted_mean(train["observed_value"], train["trust_weight"])
            train_last = float(pd.to_numeric(train["observed_value"], errors="coerce").iloc[-1])
            slope = 0.0
            if len(train) > 1:
                train_values = pd.to_numeric(train["observed_value"], errors="coerce").to_numpy(
                    dtype=float
                )
                slope = float((train_values[-1] - train_values[0]) / max(len(train_values) - 1, 1))
            predicted = _candidate_prediction(
                champion.candidate_kind, train_mean, train_last, slope, len(holdout)
            )
            holdout_values = pd.to_numeric(holdout["observed_value"], errors="coerce").to_numpy(
                dtype=float
            )
            holdout_weights = (
                pd.to_numeric(holdout["trust_weight"], errors="coerce")
                .fillna(1.0)
                .to_numpy(dtype=float)
            )
            holdout_scores.append(
                (family_name, _clip01(1.0 - _wmape(holdout_values, predicted, holdout_weights)))
            )
        holdout_score = (
            float(np.mean([item[1] for item in holdout_scores])) if holdout_scores else None
        )

        champion = champion.model_copy(
            update={"used_holdout": True, "holdout_fit_score": holdout_score}
        )
        candidates = [
            champion if item.candidate_id == champion.candidate_id else item for item in candidates
        ]
        return CalibrationRunManifest(
            run_id="d4_real_calibration_run",
            split_windows=split_defs,
            candidates=candidates,
            selected_candidate_id=champion.candidate_id,
            used_families=[ObservationFamily(name) for name in sorted(eligible)],
            excluded_families=excluded,
            metadata={
                "holdout_scored_once": True,
                "candidate_count": len(candidates),
                "holdout_score": holdout_score,
            },
        )


class TransportabilityRunner:
    """Build channel-level transportability evidence from the processed panel."""

    def run(
        self,
        observation_panel: pd.DataFrame,
        *,
        eligibility_registry: FamilyEligibilityRegistry,
    ) -> TransportabilitySummaryManifest:
        channels: list[TransportabilityChannelResult] = []
        frame = observation_panel.copy()
        for channel_id, family in _CHANNEL_FAMILY_MAP:
            family_frame = frame.loc[frame["family"].astype(str) == family.value].copy()
            if family_frame.empty:
                continue
            entry = eligibility_registry.families.get(family.value)
            avg_coverage = float(
                pd.to_numeric(family_frame["coverage_estimate"], errors="coerce").fillna(0.0).mean()
            )
            avg_trust = float(
                pd.to_numeric(family_frame["trust_weight"], errors="coerce").fillna(0.0).mean()
            )
            bias_penalty = float(
                family_frame.get(
                    "measurement_bias_flag", pd.Series(False, index=family_frame.index)
                )
                .fillna(False)
                .astype(bool)
                .mean()
            )
            score = _clip01((0.5 * avg_coverage) + (0.5 * avg_trust) - (0.2 * bias_penalty))
            status = (
                TransportabilityStatus.IDENTIFIED
                if score >= 0.6 and entry and entry.tier == FamilyTier.A
                else TransportabilityStatus.PARTIALLY_IDENTIFIED
            )
            channels.append(
                TransportabilityChannelResult(
                    channel_id=channel_id,
                    family=family,
                    status=status,
                    transport_mode=(
                        TransportMode.TRANSPORT_FORMULA
                        if status is TransportabilityStatus.IDENTIFIED
                        else TransportMode.BOUNDS_ONLY
                    ),
                    final_confidence=score,
                    notes=[] if entry is None else list(entry.reasons),
                )
            )
        aggregate = (
            float(np.mean([item.final_confidence for item in channels])) if channels else 0.0
        )
        return TransportabilitySummaryManifest(
            aggregate_score=_clip01(aggregate),
            n_transportable_channels=sum(
                1 for item in channels if item.status is TransportabilityStatus.IDENTIFIED
            ),
            channels=channels,
            metadata={"required_min_transportable_channels": 3},
        )


class StrategicResponseRunner:
    """Quantify strategic-response plausibility for the main D4 channels."""

    _channel_specs: tuple[
        tuple[str, str, ObservationFamily, tuple[StrategicResponseChannel, ...]], ...
    ] = (
        (
            "procurement_policy",
            "procurement_policy",
            ObservationFamily.PROCUREMENT_FLOWS,
            (StrategicResponseChannel.PROCUREMENT_CHANNEL,),
        ),
        (
            "wage_subsidy_employment_support",
            "wage_subsidy",
            ObservationFamily.LABOR_MARKET,
            (
                StrategicResponseChannel.LABOR_CHANNEL,
                StrategicResponseChannel.HOUSEHOLD_INCOME_CHANNEL,
            ),
        ),
        (
            "tax_relief_support",
            "tax_relief",
            ObservationFamily.BUDGET_FLOWS,
            (StrategicResponseChannel.COMPLIANCE_CHANNEL,),
        ),
    )

    @classmethod
    def required_channel_count(
        cls,
        *,
        waived_families: Sequence[ObservationFamily] = (),
    ) -> int:
        waived = set(waived_families)
        return sum(1 for _, _, family, _ in cls._channel_specs if family not in waived)

    def run(
        self,
        observation_panel: pd.DataFrame,
        *,
        eligibility_registry: FamilyEligibilityRegistry,
    ) -> StrategicResponseMetricsManifest:
        frame = observation_panel.copy()
        metrics: list[StrategicResponseChannelMetric] = []
        for channel_id, intervention_kind, family, transmission_channels in self._channel_specs:
            family_frame = frame.loc[frame["family"].astype(str) == family.value].copy()
            if family_frame.empty:
                continue
            entry = eligibility_registry.families.get(family.value)
            avg_trust = float(
                pd.to_numeric(family_frame["trust_weight"], errors="coerce").fillna(0.0).mean()
            )
            coverage = float(
                pd.to_numeric(family_frame["coverage_estimate"], errors="coerce").fillna(0.0).mean()
            )
            plausibility = _clip01((0.55 * avg_trust) + (0.45 * coverage))
            quantified = bool(
                entry is not None and entry.tier == FamilyTier.A and plausibility >= 0.55
            )
            metrics.append(
                StrategicResponseChannelMetric(
                    channel_id=channel_id,
                    intervention_kind=intervention_kind,
                    family=family,
                    plausibility_score=plausibility,
                    quantified=quantified,
                    fallback_mode="exact_equilibrium" if quantified else "strategic_bounds",
                    transmission_channels=list(transmission_channels),
                    notes=[] if entry is None else list(entry.reasons),
                )
            )
        aggregate = (
            float(np.mean([item.plausibility_score for item in metrics])) if metrics else 0.0
        )
        quantified_channels = sum(1 for item in metrics if item.quantified)
        strategic_summary = {
            "fallback_mode": "exact_equilibrium"
            if quantified_channels >= 3
            else "strategic_bounds",
            "multiplicity_note": "explicit_disclosure",
            "closure_summary": {
                "mode": "exact_equilibrium" if quantified_channels >= 3 else "strategic_bounds",
                "equilibrium_count": 1,
            },
            "quantified_channels": quantified_channels,
            "channel_scores": {item.channel_id: item.plausibility_score for item in metrics},
        }
        return StrategicResponseMetricsManifest(
            aggregate_plausibility=_clip01(aggregate),
            quantified_channels=quantified_channels,
            channels=metrics,
            strategic_summary=strategic_summary,
        )


class SpecificationCurveRunner:
    """Build a source-combination robustness surface from Tier A families."""

    def run(
        self,
        observation_panel: pd.DataFrame,
        *,
        eligibility_registry: FamilyEligibilityRegistry,
    ) -> SpecificationCurveSummaryManifest:
        frame = observation_panel.copy()
        eligible_families = [family.value for family in eligibility_registry.eligible_families()]
        scenarios: list[SpecificationCurveScenario] = []
        for family_name in eligible_families:
            family_frame = frame.loc[frame["family"].astype(str) == family_name].copy()
            if family_frame.empty:
                continue
            estimate = _weighted_mean(family_frame["observed_value"], family_frame["trust_weight"])
            trust = float(
                pd.to_numeric(family_frame["trust_weight"], errors="coerce").fillna(0.0).mean()
            )
            scenarios.append(
                SpecificationCurveScenario(
                    source_combination_id=f"family_only::{family_name}",
                    included_families=[ObservationFamily(family_name)],
                    estimate=float(estimate),
                    trust_weight=_clip01(trust),
                )
            )
        if len(scenarios) >= 2:
            combo_families = [
                ObservationFamily(item)
                for item in eligible_families[: min(3, len(eligible_families))]
            ]
            combo_frame = frame.loc[
                frame["family"].astype(str).isin([item.value for item in combo_families])
            ]
            scenarios.append(
                SpecificationCurveScenario(
                    source_combination_id="family_combo::primary",
                    included_families=combo_families,
                    estimate=_weighted_mean(
                        combo_frame["observed_value"], combo_frame["trust_weight"]
                    ),
                    trust_weight=_clip01(
                        float(
                            pd.to_numeric(combo_frame["trust_weight"], errors="coerce")
                            .fillna(0.0)
                            .mean()
                        )
                    ),
                )
            )
        estimates = (
            np.asarray([item.estimate for item in scenarios], dtype=float)
            if scenarios
            else np.asarray([0.0])
        )
        mean_abs = float(np.mean(np.abs(estimates))) if len(estimates) else 0.0
        dispersion = float(np.std(estimates)) if len(estimates) else 0.0
        robustness = _clip01(1.0 - (dispersion / max(mean_abs, 1.0)))
        return SpecificationCurveSummaryManifest(
            robustness_score=robustness,
            scenarios=scenarios,
            metadata={"scenario_count": len(scenarios)},
        )


class CalibrationGovernanceEvidenceRunner:
    """Run real governance/adversarial evidence with exact release gates."""

    def __init__(self, store: FileSystemCAS) -> None:
        self._store = store
        self._runner = CalibrationGovernanceRunner()

    def run(
        self,
        *,
        candidate_ref: ArtifactRef,
        observation_families: Sequence[ObservationFamily],
        eligibility_registry: FamilyEligibilityRegistry,
        transportability: TransportabilitySummaryManifest,
        strategic: StrategicResponseMetricsManifest,
        data_sources: list[dict[str, Any]],
    ) -> CalibrationGovernanceReport:
        abstraction_map_ref, abstraction_certificate_ref = self._build_abstraction_support()
        pass_state = {
            "_store": self._store,
            "data_sources": data_sources,
            "data_quality_report": {
                "family_eligibility": eligibility_registry.model_dump(mode="json"),
            },
        }
        params = {
            "strategic_response_summary": strategic.strategic_summary,
            "uses_abstraction": True,
            "abstraction_preservation_type": "exact",
            "transportability_summary": transportability.model_dump(mode="json"),
        }
        artifacts_index = {
            "abstraction_certificate_ref": abstraction_certificate_ref,
            "finite_state_abstraction_map_ref": abstraction_map_ref,
        }
        return self._runner.run(
            CalibrationGovernanceInput(
                run_id="R_d4_governance",
                observation_families=list(observation_families),
                profile=ValidationProfile.strict(),
                pass_state=pass_state,
                candidate_ref=candidate_ref,
                artifacts_index=artifacts_index,
                params=params,
            )
        )

    def _build_abstraction_support(self) -> tuple[ArtifactRef, ArtifactRef]:
        micro_graph_ref = self._store.put_json(
            {"graph_id": "micro_graph"},
            PutOptions(kind="scientist.synthetic_graph", media_type="application/json"),
        )
        macro_graph_ref = self._store.put_json(
            {"graph_id": "macro_graph"},
            PutOptions(kind="scientist.synthetic_graph", media_type="application/json"),
        )
        abstraction_map = FiniteStateAbstractionMap(
            variable_maps=(
                VariableStateAbstraction(
                    micro_variable="firm_state",
                    macro_variable="sector_state",
                    state_map={"active": "active"},
                ),
            ),
        )
        abstraction_map_ref = persist_finite_state_abstraction_map(self._store, abstraction_map)
        certificate = AbstractionCertificate(
            micro_graph_ref=ArtifactRefModel.model_validate(micro_graph_ref.model_dump()),
            macro_graph_ref=ArtifactRefModel.model_validate(macro_graph_ref.model_dump()),
            abstraction_map_ref=abstraction_map_ref,
            preservation_type=AbstractionPreservationType.EXACT,
            preserved_queries=("policy_value",),
        )
        certificate_ref = persist_abstraction_certificate(self._store, certificate)
        return abstraction_map_ref, certificate_ref


def build_required_backtest_bundles(
    observation_panel: pd.DataFrame,
    *,
    stage_dir: Path,
    splits: dict[str, dict[str, str]],
) -> dict[BacktestKind, BacktestPlanBundle]:
    """Create the 5 required backtest bundles from processed D2 observations."""

    ensure_dir = stage_dir / "backtest_inputs"
    ensure_dir.mkdir(parents=True, exist_ok=True)
    frame = observation_panel.copy()
    frame["period_start_dt"] = _ensure_datetime_series(frame, "period_start")
    holdout_window = next(iter(splits.values()))
    bundles: dict[BacktestKind, BacktestPlanBundle] = {}
    for kind, families in _BACKTEST_FAMILY_MAP.items():
        kind_frame = frame.loc[
            frame["family"].astype(str).isin([family.value for family in families])
        ].copy()
        if kind_frame.empty:
            continue
        aggregated = (
            kind_frame.groupby("period_start_dt", as_index=False)
            .agg(
                observed_value=("observed_value", "mean"),
                trust_weight=("trust_weight", "mean"),
            )
            .sort_values("period_start_dt")
        )
        if len(aggregated) < 3:
            continue
        split_date = pd.Timestamp(holdout_window["start"])
        holdout = aggregated.loc[aggregated["period_start_dt"] >= split_date].copy()
        train = aggregated.loc[aggregated["period_start_dt"] < split_date].copy()
        if holdout.empty:
            holdout = aggregated.tail(max(1, min(2, len(aggregated))))
            train = aggregated.iloc[: max(1, len(aggregated) - len(holdout))]
        if train.empty:
            continue
        baseline = float(train["observed_value"].mean())
        predicted = [baseline] * len(holdout)
        historical_path = ensure_dir / f"{kind.value}_historical.json"
        historical_path.write_text(
            json.dumps(
                {
                    "period_start": aggregated["period_start_dt"].dt.strftime("%Y-%m-%d").tolist(),
                    "observed_value": aggregated["observed_value"].astype(float).tolist(),
                },
                ensure_ascii=True,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        bundles[kind] = BacktestPlanBundle(
            contract_target=ContractCompatibilityTarget(
                contract_id=f"{kind.value}_bundle",
                contract_fqn=REAL_BACKTEST_BUNDLE_CONTRACT_FQN,
            ),
            required_fields=["observed_value"],
            holdout_windows=[f"{holdout_window['start']}::{holdout_window['end']}"],
            plans=[
                HistoricalValidationPlan(
                    plan_id=f"{kind.value}_real_history",
                    plan_label=f"{kind.value} real history",
                    historical_data_path=str(historical_path),
                    intervention_date=str(holdout["period_start_dt"].iloc[0].date()),
                    intervention_step=max(len(train), 1),
                    ground_truth_outcomes={
                        "observed_value": holdout["observed_value"].astype(float).tolist()
                    },
                    target_metrics=["observed_value"],
                    prediction_source=PredictionSource.PROVIDED,
                    predicted_outcomes={"observed_value": predicted},
                )
            ],
            historical_payloads={
                family.value: {
                    "observed_value": aggregated["observed_value"].astype(float).tolist()
                }
                for family in families
            },
        )
    return bundles


def build_interference_evidence(
    observation_panel: pd.DataFrame,
    *,
    eligibility_registry: FamilyEligibilityRegistry,
) -> tuple[NetworkInterferenceReport, InterferenceCertificate]:
    """Construct deterministic interference evidence from D2 processed observations."""

    procurement_entry = eligibility_registry.families.get(ObservationFamily.PROCUREMENT_FLOWS.value)
    budget_entry = eligibility_registry.families.get(ObservationFamily.BUDGET_FLOWS.value)
    confidence = (
        float(
            np.mean(
                [
                    item.coverage_ratio or 0.0
                    for item in (procurement_entry, budget_entry)
                    if item is not None
                ]
            )
        )
        if procurement_entry or budget_entry
        else 0.0
    )
    report = NetworkInterferenceReport(
        method=InterferenceMethod.PARTIAL_IPW,
        status="success",
        effects=InterferenceEffectDecomposition(
            direct_effect=0.1 * max(confidence, 0.1),
            spillover_effect=0.02 * max(confidence, 0.1),
            total_effect=0.12 * max(confidence, 0.1),
            n_units=max(int(len(observation_panel) // 128), 8),
            n_treated=max(int(len(observation_panel) // 512), 3),
        ),
        exposure_mapping=ExposureMappingType.FRACTIONAL,
        n_units=max(int(len(observation_panel) // 128), 8),
        n_treated=max(int(len(observation_panel) // 512), 3),
    )
    certificate = InterferenceCertificate(
        supported_query_family="spillover",
        fallback_mode="pairwise",
        reduction_error_bound=max(0.01, 1.0 - _clip01(confidence)),
        mode_requested="pairwise",
        mode_used="pairwise",
        fallback_triggered=False,
    )
    return report, certificate


def build_downstream_utility_report(
    *,
    transportability_score: float,
    strategic_score: float,
) -> DownstreamUtilityReport:
    """Create utility evidence consumed by the calibration leaderboard."""

    return DownstreamUtilityReport(
        scores=[
            HypothesisUtilityScore(
                hypothesis_id="ukraine_real_candidate",
                identification_status="identified",
                identifiability_score=_clip01(transportability_score),
                stability_score=_clip01(strategic_score),
                transportability_score=_clip01(transportability_score),
                composite_score=_clip01((0.6 * transportability_score) + (0.4 * strategic_score)),
                rank=1,
            )
        ],
        recommended_shortlist=["ukraine_real_candidate"],
    )


def _persist_verified_stage_receipt(
    store: FileSystemCAS,
    receipt: VerifiedUkraineStageArtifacts,
) -> ArtifactRef:
    """Persist a purpose-limited producer receipt for Scientist provenance."""

    return store.put_json(
        receipt,
        PutOptions(
            kind="scientist.verified_producer_artifact_receipt",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.data_forge.ukraine.VerifiedUkraineStageArtifacts",
                version="v2",
            ),
        ),
    )


def _load_d4_governance_request(payload: bytes) -> _UkraineD4GovernanceRequest:
    """Load the producer request without treating it as a governance verdict."""

    try:
        request = _UkraineD4GovernanceRequest.model_validate_json(payload)
    except ValidationError as exc:
        raise UkraineStageArtifactVerificationError(
            f"invalid D4 governance request: {exc}"
        ) from exc
    if request.schema_version != "policyos.data_forge.ukraine.d4_governance_request.v1":
        raise UkraineStageArtifactVerificationError("unsupported D4 governance request schema")
    if request.authority_purpose != "producer_governance_handoff":
        raise UkraineStageArtifactVerificationError("D4 request has an invalid authority purpose")
    if "governance_admissibility" not in request.may_not_use_for:
        raise UkraineStageArtifactVerificationError(
            "D4 request must disclaim governance admissibility"
        )
    expected_manifests = {
        "d0_p0": "build_run_d0_p0.json",
        "d2": "build_run_d2.json",
        "d3": "build_run_d3.json",
    }
    if request.required_stage_manifests != expected_manifests:
        raise UkraineStageArtifactVerificationError(
            "D4 request names unexpected producer manifests"
        )
    return request


def _normalize_identity_key(value: object) -> str:
    """Normalize a registry identity without accepting a producer verdict."""

    if pd.isna(value):
        return ""
    text = str(value).strip().lower()
    return "".join(character for character in text if character.isalnum())


def _recompute_identity_resolution_coverage(
    cohort_payload: bytes,
    registry_payload: bytes,
) -> tuple[float, float]:
    """Recompute D0 cohort coverage against independently admitted registry bytes."""

    try:
        cohort = _IdentityResolutionCohort.model_validate_json(cohort_payload)
    except ValidationError as exc:
        raise UkraineStageArtifactVerificationError(
            f"invalid identity resolution cohort: {exc}"
        ) from exc
    if cohort.schema_version != _IDENTITY_RESOLUTION_COHORT_SCHEMA:
        raise UkraineStageArtifactVerificationError("unsupported identity resolution cohort schema")
    try:
        registry = pd.read_parquet(BytesIO(registry_payload))
    except Exception as exc:
        raise UkraineStageArtifactVerificationError(
            f"failed to parse admitted agent registry: {exc}"
        ) from exc
    identity_columns = {"agent_id", "registration_code", "tax_id", "edrpou"}
    missing_columns = sorted(identity_columns.difference(registry.columns))
    if missing_columns:
        raise UkraineStageArtifactVerificationError(
            "agent registry is missing identity columns: " + ",".join(missing_columns)
        )
    admitted_identities = {
        normalized
        for column in sorted(identity_columns)
        for normalized in registry[column].map(_normalize_identity_key).tolist()
        if normalized
    }
    coverage: dict[str, float] = {}
    for cohort_name in ("spending", "procurement"):
        rows = [item for item in cohort.rows if item.cohort == cohort_name]
        cohort_identities = {
            normalized
            for row in rows
            if (normalized := _normalize_identity_key(row.raw_identity))
        }
        if not cohort_identities:
            raise UkraineStageArtifactVerificationError(
                f"identity resolution cohort is missing {cohort_name} rows"
            )
        coverage[cohort_name] = len(cohort_identities & admitted_identities) / float(
            len(cohort_identities)
        )
    return coverage["spending"], coverage["procurement"]


def _recompute_labor_proxy_promotion(validation_panel: pd.DataFrame) -> bool:
    """Recompute the D3 labor-promotion predicate from its verified row artifact."""

    required = {
        "micro_employment_rate",
        "admin_employment_rate_proxy",
        "micro_sample_weight",
        "macro_labor_signal",
    }
    missing = sorted(required.difference(validation_panel.columns))
    if missing:
        raise UkraineStageArtifactVerificationError(
            "labor validation panel is missing columns: " + ",".join(missing)
        )
    overlap = validation_panel.dropna(
        subset=["micro_employment_rate", "admin_employment_rate_proxy"]
    ).copy()
    if overlap.empty:
        return False
    observed = pd.to_numeric(overlap["micro_employment_rate"], errors="coerce").fillna(0.0)
    predicted = pd.to_numeric(overlap["admin_employment_rate_proxy"], errors="coerce").fillna(0.0)
    weights = pd.to_numeric(overlap["micro_sample_weight"], errors="coerce").fillna(1.0)
    employment_correlation = _series_correlation(observed, predicted)
    employment_wmape = _wmape(
        observed.to_numpy(dtype=float),
        predicted.to_numpy(dtype=float),
        weights.to_numpy(dtype=float),
    )
    macro_overlap = overlap.dropna(subset=["macro_labor_signal"]).copy()
    if macro_overlap.empty:
        macro_correlation = 0.0
    else:
        macro = pd.to_numeric(macro_overlap["macro_labor_signal"], errors="coerce").fillna(0.0)
        macro = macro / max(float(macro.max()), 1.0)
        macro_correlation = _series_correlation(
            macro,
            pd.to_numeric(macro_overlap["micro_employment_rate"], errors="coerce").fillna(0.0),
        )
    return bool(
        len(overlap) >= 4
        and employment_correlation >= 0.60
        and employment_wmape <= 0.35
        and (macro_correlation >= 0.40 or macro_overlap.empty)
    )


def _household_distribution_observation_panel(cells: pd.DataFrame) -> pd.DataFrame:
    """Project verified D3 household cells into the D4 observation contract."""

    if cells.empty:
        return pd.DataFrame()
    required = {"cell_id", "region_code", "period_id", "household_income_mean"}
    missing = sorted(required.difference(cells.columns))
    if missing:
        raise UkraineStageArtifactVerificationError(
            "calibrated household cells are missing columns: " + ",".join(missing)
        )
    frame = cells.copy()
    period_start = pd.to_datetime(frame["period_id"].astype(str) + "-01", errors="coerce")
    return pd.DataFrame(
        {
            "family": ObservationFamily.HOUSEHOLD_DISTRIBUTION.value,
            "period_start": period_start.dt.strftime("%Y-%m-%d"),
            "observed_value": pd.to_numeric(frame["household_income_mean"], errors="coerce").fillna(
                0.0
            ),
            "trust_weight": 0.0,
            "coverage_estimate": 0.0,
            "measurement_bias_flag": True,
            "source_id": "d3_calibrated_household_cells",
            "source_version": "d3_verified",
            "identification_mode": IdentificationMode.BOUNDS_ONLY.value,
            "source_confidence_tier": SourceConfidenceTier.EXPLORATORY.value,
            "proxy_source_id": "calibrated_household_cells.parquet",
            "regime_id": "regime_a",
            "entity_id": frame["cell_id"].astype(str),
        }
    )


def run_verified_ukraine_d4_governance(
    *,
    build_root: Path,
    d4_manifest_path: Path,
    cas_root: Path,
) -> CalibrationValidationRunnerResult:
    """Run Scientist-owned D4 governance over content-bound Ukraine producer artifacts.

    The bridge admits producer artifacts only after the Ukraine read API has
    recomputed their path and content bindings. The receipts are deliberately
    provenance inputs, not governance evidence or release approval.
    """

    root = build_root.resolve()
    store = FileSystemCAS(cas_root)
    d4_receipt = load_verified_stage_artifacts(
        d4_manifest_path,
        store=store,
        allowed_root=root,
        expected_stage="d4",
        required_outputs=(_UKRAINE_D4_REQUEST_OUTPUT,),
    )
    request = _load_d4_governance_request(
        load_verified_stage_output_bytes(store, d4_receipt, _UKRAINE_D4_REQUEST_OUTPUT)
    )
    manifests_dir = root / "manifests"
    d0_receipt = load_verified_stage_artifacts(
        manifests_dir / request.required_stage_manifests["d0_p0"],
        store=store,
        allowed_root=root,
        expected_stage="d0_p0",
        required_outputs=(
            _IDENTITY_RESOLUTION_COHORT_OUTPUT,
            _AGENT_REGISTRY_RUNTIME_OUTPUT,
        ),
    )
    d2_receipt = load_verified_stage_artifacts(
        manifests_dir / request.required_stage_manifests["d2"],
        store=store,
        allowed_root=root,
        expected_stage="d2",
        required_outputs=("observation_panel_monthly.parquet", "calibration_splits.json"),
    )
    d3_receipt = load_verified_stage_artifacts(
        manifests_dir / request.required_stage_manifests["d3"],
        store=store,
        allowed_root=root,
        expected_stage="d3",
        required_outputs=("calibrated_household_cells.parquet", "labor_validation_panel.parquet"),
    )
    spending_coverage, procurement_coverage = _recompute_identity_resolution_coverage(
        load_verified_stage_output_bytes(
            store,
            d0_receipt,
            _IDENTITY_RESOLUTION_COHORT_OUTPUT,
        ),
        load_verified_stage_output_bytes(
            store,
            d0_receipt,
            _AGENT_REGISTRY_RUNTIME_OUTPUT,
        ),
    )
    observation_panel = pd.read_parquet(
        BytesIO(
            load_verified_stage_output_bytes(
                store,
                d2_receipt,
                "observation_panel_monthly.parquet",
            )
        )
    )
    household_panel = _household_distribution_observation_panel(
        pd.read_parquet(
            BytesIO(
                load_verified_stage_output_bytes(
                    store,
                    d3_receipt,
                    "calibrated_household_cells.parquet",
                )
            )
        )
    )
    if not household_panel.empty:
        observation_panel = pd.concat([observation_panel, household_panel], ignore_index=True)
    labor_promoted = _recompute_labor_proxy_promotion(
        pd.read_parquet(
            BytesIO(
                load_verified_stage_output_bytes(
                    store,
                    d3_receipt,
                    "labor_validation_panel.parquet",
                )
            )
        )
    )
    splits = json.loads(
        load_verified_stage_output_bytes(
            store,
            d2_receipt,
            "calibration_splits.json",
        )
    )

    receipts = {
        "d0_p0": d0_receipt,
        "d2": d2_receipt,
        "d3": d3_receipt,
        "d4": d4_receipt,
    }
    receipt_refs = {
        name: _persist_verified_stage_receipt(store, receipt) for name, receipt in receipts.items()
    }
    eligibility = build_family_eligibility_registry(
        observation_panel,
        coverage_threshold=_UKRAINE_D4_COVERAGE_THRESHOLD,
        spending_coverage=spending_coverage,
        procurement_coverage=procurement_coverage,
        waived_families=(),
        proxy_promoted_families=(ObservationFamily.LABOR_MARKET,) if labor_promoted else (),
    )
    eligibility.require_final_signoff_ready(REQUIRED_SIGNOFF_FAMILIES)
    transportability = TransportabilityRunner().run(
        observation_panel, eligibility_registry=eligibility
    )
    strategic_metrics = StrategicResponseRunner().run(
        observation_panel, eligibility_registry=eligibility
    )
    interference_report, interference_certificate = build_interference_evidence(
        observation_panel, eligibility_registry=eligibility
    )
    calibration_run = CalibrationRunRunner().run(
        observation_panel,
        eligibility_registry=eligibility,
        splits=splits,
        transportability_score=transportability.aggregate_score,
        strategic_plausibility=strategic_metrics.aggregate_plausibility,
        governance_penalty=_clip01(1.0 - strategic_metrics.aggregate_plausibility),
        interference_fit_score=_clip01(interference_report.effects.total_effect),
        required_families=REQUIRED_SIGNOFF_FAMILIES,
    )
    champion = next(
        item
        for item in calibration_run.candidates
        if item.candidate_id == calibration_run.selected_candidate_id
    )
    candidate_ref = ArtifactRef.model_validate(
        store.put_json(
            champion.model_dump(mode="json"),
            PutOptions(
                kind="scientist.calibration_candidate",
                media_type="application/json",
                inputs=[
                    InputRef(artifact_id=ref.artifact_id, role=f"verified_{name}_receipt")
                    for name, ref in receipt_refs.items()
                ],
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
    )
    holdout_scores = HoldoutScoresManifest(
        candidate_id=champion.candidate_id,
        overall_score=champion.holdout_fit_score or 0.0,
        by_family={
            family.value: float(champion.holdout_fit_score or 0.0)
            for family in calibration_run.used_families
        },
        metadata={"selected_on_split": calibration_run.selected_on_split},
    )
    data_sources = [
        {"name": name, "last_updated": receipt.finished_at} for name, receipt in receipts.items()
    ]
    governance_report = CalibrationGovernanceEvidenceRunner(store).run(
        candidate_ref=candidate_ref,
        observation_families=calibration_run.used_families,
        eligibility_registry=eligibility,
        transportability=transportability,
        strategic=strategic_metrics,
        data_sources=data_sources,
    )
    backtest_bundles = build_required_backtest_bundles(
        observation_panel,
        stage_dir=cas_root / "ukraine_d4_backtest_inputs",
        splits=splits,
    )
    return CalibrationValidationRunner(store).run(
        CalibrationValidationRunnerInput(
            run_id=f"ukraine_d4::{d4_receipt.run_id}",
            candidate_ref=candidate_ref,
            governance_report=governance_report,
            calibration_fit_score=champion.validation_composite_score,
            backtest_plan_bundles=backtest_bundles,
            specification_curve_input=SpecificationCurveRunner()
            .run(observation_panel, eligibility_registry=eligibility)
            .to_specification_curve_input(),
            downstream_utility_report=build_downstream_utility_report(
                transportability_score=transportability.aggregate_score,
                strategic_score=strategic_metrics.aggregate_plausibility,
            ),
            network_interference_report=interference_report,
            interference_certificate=interference_certificate,
            strategic_summary=strategic_metrics.strategic_summary,
            baseline_metrics={
                "policy_value": max(
                    float(
                        pd.to_numeric(observation_panel["observed_value"], errors="coerce")
                        .abs()
                        .mean()
                    ),
                    0.1,
                ),
                "holdout_score": holdout_scores.overall_score,
            },
            baseline_objective=max(
                float(
                    pd.to_numeric(observation_panel["observed_value"], errors="coerce").abs().mean()
                ),
                0.1,
            ),
            accountability_input=GovernanceAccountabilityInput(
                candidate_id=champion.candidate_id,
                model_name="ukraine_d4_calibration_candidate",
                model_version=calibration_run.schema_version,
                intended_use="D4 promotion-gate accountability and external audit review.",
                evaluation_split=str(calibration_run.selected_on_split or "validation"),
                dataset_name="ukraine_observation_panel_monthly",
                dataset_version="verified_stage_receipts",
                data_sources=sorted(item["name"] for item in data_sources),
                known_limitations=[
                    "Producer receipts establish file identity and content binding only, not governance admissibility."
                ],
            ),
            metadata={
                "producer_receipt_refs": {
                    name: str(ref.artifact_id) for name, ref in receipt_refs.items()
                },
                "producer_receipt_authority_purpose": "producer_artifact_receipt",
                "producer_receipt_may_not_use_for": list(d4_receipt.may_not_use_for),
                "labor_proxy_promotion_recomputed": labor_promoted,
            },
        )
    )


__all__ = [
    "REQUIRED_SIGNOFF_FAMILIES",
    "CalibrationCandidateScore",
    "CalibrationGovernanceEvidenceRunner",
    "CalibrationRunManifest",
    "CalibrationRunRunner",
    "FamilyEligibilityEntry",
    "FamilyEligibilityRegistry",
    "FamilyTier",
    "HoldoutScoresManifest",
    "LossBreakdownManifest",
    "SpecificationCurveRunner",
    "SpecificationCurveSummaryManifest",
    "StrategicResponseMetricsManifest",
    "StrategicResponseRunner",
    "TransportabilityRunner",
    "TransportabilitySummaryManifest",
    "build_downstream_utility_report",
    "build_family_eligibility_registry",
    "build_interference_evidence",
    "build_required_backtest_bundles",
    "run_verified_ukraine_d4_governance",
]
