"""Calibration and governance evidence builders for Ukraine."""

from __future__ import annotations

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.ir.observation.contracts import ObservationFamily
from polisyos.scientist.governance import (
    REQUIRED_SIGNOFF_FAMILIES,
    BacktestKind,
    CalibrationGovernanceEvidenceRunner,
    CalibrationRunManifest,
    CalibrationRunRunner,
    CalibrationValidationRunner,
    CalibrationValidationRunnerInput,
    GovernanceAccountabilityInput,
    HoldoutScoresManifest,
    LossBreakdownManifest,
    SpecificationCurveRunner,
    StrategicResponseMetricsManifest,
    StrategicResponseRunner,
    TransportabilityRunner,
    TransportabilitySummaryManifest,
    build_downstream_utility_report,
    build_family_eligibility_registry,
    build_interference_evidence,
    build_required_backtest_bundles,
    load_governance_accountability_artifact,
)

from .common import *
from .demography import _build_household_distribution_observation_panel


def _build_d4_governance_accountability_input(
    *,
    observation_panel: pd.DataFrame,
    calibration_run: CalibrationRunManifest,
    champion: Any,
    holdout_scores: HoldoutScoresManifest,
    transportability: TransportabilitySummaryManifest,
    strategic_metrics: StrategicResponseMetricsManifest,
    data_sources: Sequence[dict[str, Any]],
) -> GovernanceAccountabilityInput:
    """Build the default D4 accountability payload without fabricating probabilistic evidence.

    The production D4 path has rich governance metadata, but not every deployment
    slice exposes calibrated probability vectors. We therefore publish dataset,
    grouping, and limitation metadata explicitly while allowing the accountability
    artifact to mark missing probabilistic surfaces as audit-visible gaps instead
    of silently inventing calibration inputs.
    """

    protected_axes = [
        axis
        for axis in ("region_code", "family", "entity_scope", "source_id")
        if axis in observation_panel.columns and observation_panel[axis].notna().any()
    ]
    source_versions = sorted(
        {
            str(value).strip()
            for value in observation_panel.get("source_version", pd.Series(dtype=str))
            .dropna()
            .astype(str)
            .tolist()
            if str(value).strip()
        }
    )
    known_limitations: list[str] = [
        "Default D4 accountability currently exposes provenance, grouping, and threshold rationale even when calibrated per-row probability outputs are unavailable on the production path.",
        "Fairness-aware calibration slices on the default D4 path rely on deployment metadata axes and should be upgraded to direct protected-group labels before external publication.",
    ]
    if holdout_scores.overall_score < 0.8:
        known_limitations.append(
            "Holdout score remains below the default external-audit comfort band for calibration claims."
        )
    if transportability.aggregate_score < 0.75:
        known_limitations.append(
            "Transportability remains below the preferred D4 accountability band and should be reviewed before promotion."
        )
    if transportability.n_transportable_channels < 3:
        known_limitations.append(
            "Fewer than three transportable channels were established on the default path."
        )
    if strategic_metrics.aggregate_plausibility < 0.75:
        known_limitations.append(
            "Strategic-response plausibility remains below the preferred governance band."
        )
    if str(calibration_run.selected_on_split or "").strip().lower() != "holdout":
        known_limitations.append(
            "Champion was selected on a non-holdout split and then scored on holdout; recalibration evidence should be refreshed after policy changes."
        )

    return GovernanceAccountabilityInput(
        candidate_id=str(
            getattr(champion, "candidate_id", "") or calibration_run.selected_candidate_id
        ),
        model_name="ukraine_d4_calibration_candidate",
        model_version=str(calibration_run.schema_version),
        intended_use="D4 promotion-gate accountability and external audit review.",
        evaluation_split=str(calibration_run.selected_on_split or "validation"),
        dataset_name="ukraine_observation_panel_monthly",
        dataset_version=(
            None
            if not source_versions
            else source_versions[0]
            if len(source_versions) == 1
            else "mixed"
        ),
        data_sources=sorted(
            {
                str(item.get("name") or "").strip()
                for item in data_sources
                if str(item.get("name") or "").strip()
            }
        ),
        known_limitations=sorted(set(known_limitations)),
        protected_attributes={axis: [] for axis in protected_axes},
        metadata={
            "n_observations": len(observation_panel),
            "used_families": sorted(family.value for family in calibration_run.used_families),
            "selected_on_split": calibration_run.selected_on_split,
            "holdout_score": holdout_scores.overall_score,
            "transportability_score": transportability.aggregate_score,
            "transportable_channels": transportability.n_transportable_channels,
            "strategic_plausibility": strategic_metrics.aggregate_plausibility,
        },
    )


def build_d4_stage(config: PipelineConfig) -> StageBuildResult:
    """Build D4 calibration, backtesting, and governance evidence artifacts."""

    build_root = config.build_root
    stage_dir = _stage_dir(build_root, StageId.D4)
    ensure_dirs(stage_dir)
    outputs: dict[str, ArtifactRecord] = {}
    d0_manifest_path = _manifest_path(build_root, "build_run_d0_p0.json")
    d2_stage_dir = _stage_dir(build_root, StageId.D2)
    d3_stage_dir = _stage_dir(build_root, StageId.D3)
    observation_panel_path = d2_stage_dir / "observation_panel_monthly.parquet"
    observation_panel = _read_parquet_frame(
        observation_panel_path,
        columns=[
            "family",
            "period_start",
            "observed_value",
            "trust_weight",
            "coverage_estimate",
            "measurement_bias_flag",
            "censoring_mask",
            "source_id",
            "identification_mode",
            "source_confidence_tier",
            "proxy_source_id",
            "regime_id",
            "entity_id",
        ],
    )
    calibrated_household_cells_path = d3_stage_dir / "calibrated_household_cells.parquet"
    if calibrated_household_cells_path.exists():
        calibrated_household_cells = _read_parquet_frame(
            calibrated_household_cells_path,
            columns=[
                "cell_id",
                "region_code",
                "period_id",
                "household_income_mean",
                "measurement_bias_flag",
                "trust_weight",
            ],
        )
        household_observation_panel = _build_household_distribution_observation_panel(
            calibrated_household_cells,
        )
        if not household_observation_panel.empty:
            observation_panel = pd.concat(
                [observation_panel, household_observation_panel],
                ignore_index=True,
            )
    observed_abs_mean, observed_head = _stream_parquet_numeric_column_stats(
        observation_panel_path,
        "observed_value",
        head_limit=256,
    )
    splits = json.loads((d2_stage_dir / "calibration_splits.json").read_text(encoding="utf-8"))
    d0_metrics = {}
    if d0_manifest_path.exists():
        d0_metrics = json.loads(d0_manifest_path.read_text(encoding="utf-8")).get("metrics", {})
    spending_coverage = d0_metrics.get("runtime_cohort_coverage_spending")
    procurement_coverage = d0_metrics.get("runtime_cohort_coverage_procurement")
    d4_stage_config = config.stages[StageId.D4.value]
    waived_signoff_families = tuple(d4_stage_config.final_signoff_waived_families)
    labor_bias_validation_path = d3_stage_dir / "labor_bias_validation.json"
    proxy_promoted_families: tuple[ObservationFamily, ...] = ()
    if labor_bias_validation_path.exists():
        labor_bias_validation = json.loads(labor_bias_validation_path.read_text(encoding="utf-8"))
        if labor_bias_validation.get("promotion_allowed"):
            proxy_promoted_families = (ObservationFamily.LABOR_MARKET,)
    blueprint_coverage_threshold = max(
        0.95,
        float(config.stages[StageId.D0_P0.value].coverage_threshold),
    )
    family_eligibility = build_family_eligibility_registry(
        observation_panel,
        coverage_threshold=blueprint_coverage_threshold,
        spending_coverage=spending_coverage,
        procurement_coverage=procurement_coverage,
        waived_families=waived_signoff_families,
        proxy_promoted_families=proxy_promoted_families,
    )
    family_eligibility_path = _write_json(
        stage_dir / "family_eligibility_registry.json", family_eligibility
    )
    outputs["family_eligibility_registry.json"] = ArtifactRecord.from_path(family_eligibility_path)
    try:
        family_eligibility.require_final_signoff_ready(REQUIRED_SIGNOFF_FAMILIES)
    except ValueError as exc:
        return StageBuildResult(
            outputs=outputs,
            findings=[
                ValidationFinding(
                    severity="error",
                    code="families_not_exact_signoff_ready",
                    message=str(exc),
                )
            ],
            metrics={
                "blueprint_coverage_threshold": blueprint_coverage_threshold,
                "runtime_cohort_coverage_spending": spending_coverage,
                "runtime_cohort_coverage_procurement": procurement_coverage,
                "tier_a_family_count": len(family_eligibility.eligible_families()),
                "waived_signoff_families": [family.value for family in waived_signoff_families],
                "proxy_promoted_families": [family.value for family in proxy_promoted_families],
            },
            manifest_paths=[family_eligibility_path],
        )

    transportability_runner = TransportabilityRunner()
    transportability = transportability_runner.run(
        observation_panel,
        eligibility_registry=family_eligibility,
    )
    strategic_runner = StrategicResponseRunner()
    strategic_metrics = strategic_runner.run(
        observation_panel,
        eligibility_registry=family_eligibility,
    )
    governance_penalty = _clip_value(
        1.0 - strategic_metrics.aggregate_plausibility, lower=0.0, upper=1.0
    )
    interference_report, interference_certificate = build_interference_evidence(
        observation_panel,
        eligibility_registry=family_eligibility,
    )
    calibration_runner = CalibrationRunRunner()
    calibration_run = calibration_runner.run(
        observation_panel,
        eligibility_registry=family_eligibility,
        splits=splits,
        transportability_score=transportability.aggregate_score,
        strategic_plausibility=strategic_metrics.aggregate_plausibility,
        governance_penalty=governance_penalty,
        interference_fit_score=_clip_value(
            interference_report.effects.total_effect, lower=0.0, upper=1.0
        ),
        required_families=tuple(
            family
            for family in REQUIRED_SIGNOFF_FAMILIES
            if family not in set(waived_signoff_families)
        ),
    )
    champion = next(
        item
        for item in calibration_run.candidates
        if item.candidate_id == calibration_run.selected_candidate_id
    )
    holdout_scores = HoldoutScoresManifest(
        candidate_id=champion.candidate_id,
        overall_score=champion.holdout_fit_score or 0.0,
        by_family={
            str(family.value): float(champion.holdout_fit_score or 0.0)
            for family in calibration_run.used_families
        },
        metadata={"selected_on_split": calibration_run.selected_on_split},
    )
    loss_breakdown = LossBreakdownManifest(
        candidate_id=champion.candidate_id,
        measurement_loss=max(0.0, 1.0 - champion.measurement_fit_score),
        network_loss=max(0.0, 1.0 - champion.validation_fit_score),
        interference_loss=max(0.0, 1.0 - champion.interference_fit_score),
        governance_penalty=champion.governance_penalty,
        regularization=champion.robustness_penalty,
    )
    specification_curve = SpecificationCurveRunner().run(
        observation_panel,
        eligibility_registry=family_eligibility,
    )
    cas_store = FileSystemCAS(stage_dir / ".d4_cas")
    candidate_ref = cas_store.put_json(
        champion.model_dump(mode="json"),
        PutOptions(kind="scientist.calibration_candidate", media_type="application/json"),
    )
    candidate_artifact_ref = ArtifactRef.model_validate(candidate_ref)
    observed_sources = sorted(
        observation_panel.get("source_id", pd.Series(dtype=str))
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )
    data_sources: list[dict[str, Any]] = []
    for source_id in observed_sources:
        source = config.sources.get(source_id)
        if source is None:
            continue
        source_path = build_root.normalized_dir / source_id / source.normalized_artifact
        last_updated = (
            datetime.utcfromtimestamp(source_path.stat().st_mtime).isoformat()
            if source_path.exists()
            else datetime.utcnow().isoformat()
        )
        data_sources.append({"name": source_id, "last_updated": last_updated})
    governance_report = CalibrationGovernanceEvidenceRunner(cas_store).run(
        candidate_ref=candidate_artifact_ref,
        observation_families=calibration_run.used_families,
        eligibility_registry=family_eligibility,
        transportability=transportability,
        strategic=strategic_metrics,
        data_sources=data_sources,
    )
    backtest_bundles = build_required_backtest_bundles(
        observation_panel,
        stage_dir=stage_dir,
        splits=splits,
    )
    validation_runner = CalibrationValidationRunner(cas_store)
    validation_result = validation_runner.run(
        CalibrationValidationRunnerInput(
            run_id="R_d4_real_validation",
            candidate_ref=candidate_artifact_ref,
            governance_report=governance_report,
            calibration_fit_score=champion.validation_composite_score,
            backtest_plan_bundles=backtest_bundles,
            specification_curve_input=specification_curve.to_specification_curve_input(),
            downstream_utility_report=build_downstream_utility_report(
                transportability_score=transportability.aggregate_score,
                strategic_score=strategic_metrics.aggregate_plausibility,
            ),
            transportability_result=transportability.to_transportability_result(),
            network_interference_report=interference_report,
            interference_certificate=interference_certificate,
            strategic_summary=strategic_metrics.strategic_summary,
            baseline_metrics={
                "policy_value": max(observed_abs_mean, 0.1),
                "holdout_score": holdout_scores.overall_score,
            },
            baseline_objective=max(observed_abs_mean, 0.1),
            accountability_input=_build_d4_governance_accountability_input(
                observation_panel=observation_panel,
                calibration_run=calibration_run,
                champion=champion,
                holdout_scores=holdout_scores,
                transportability=transportability,
                strategic_metrics=strategic_metrics,
                data_sources=data_sources,
            ),
        )
    )

    calibration_manifest_path = _write_json(
        stage_dir / "calibration_run_manifest.json", calibration_run
    )
    outputs["calibration_run_manifest.json"] = ArtifactRecord.from_path(calibration_manifest_path)
    loss_breakdown_path = _write_json(stage_dir / "loss_breakdown.json", loss_breakdown)
    outputs["loss_breakdown.json"] = ArtifactRecord.from_path(loss_breakdown_path)
    holdout_scores_path = _write_json(stage_dir / "holdout_scores.json", holdout_scores)
    outputs["holdout_scores.json"] = ArtifactRecord.from_path(holdout_scores_path)
    shock_scores_path = _write_json(
        stage_dir / "shock_scenario_scores.json", validation_result.bundle.stress_scenarios
    )
    outputs["shock_scenario_scores.json"] = ArtifactRecord.from_path(shock_scores_path)
    if validation_result.bundle.governance_accountability_ref is not None:
        accountability_artifact = load_governance_accountability_artifact(
            cas_store,
            validation_result.bundle.governance_accountability_ref,
        )
        accountability_path = _write_json(
            stage_dir / "governance_accountability.json",
            accountability_artifact,
        )
        outputs["governance_accountability.json"] = ArtifactRecord.from_path(accountability_path)
    leaderboard_path = _write_json(
        stage_dir / "calibration_leaderboard.json",
        {
            "selected_candidate_id": calibration_run.selected_candidate_id,
            "candidates": [item.model_dump(mode="json") for item in calibration_run.candidates],
            "leaderboard_entry": (
                None
                if validation_result.bundle.leaderboard_entry is None
                else validation_result.bundle.leaderboard_entry.model_dump(mode="json")
            ),
            "governance_verdict": governance_report.resolved_verdict(),
        },
    )
    outputs["calibration_leaderboard.json"] = ArtifactRecord.from_path(leaderboard_path)
    transportability_path = _write_json(
        stage_dir / "transportability_results.json", transportability
    )
    outputs["transportability_results.json"] = ArtifactRecord.from_path(transportability_path)
    strategic_metrics_path = _write_json(
        stage_dir / "strategic_response_metrics.json", strategic_metrics
    )
    outputs["strategic_response_metrics.json"] = ArtifactRecord.from_path(strategic_metrics_path)
    specification_curve_path = _write_json(
        stage_dir / "specification_curve_summary.json", specification_curve
    )
    outputs["specification_curve_summary.json"] = ArtifactRecord.from_path(specification_curve_path)
    outputs["foundry_seed_state_v1.npz"] = _write_npz(
        stage_dir / "foundry_seed_state_v1.npz", values=observed_head
    )
    replay_artifacts_path = _write_json(
        stage_dir / "replay_artifacts.json",
        {
            "schema_version": "1.0",
            "calibration_validation_bundle_ref": str(validation_result.bundle_ref.artifact_id),
            "backtest_report_ref": (
                None
                if validation_result.bundle.backtest_report_ref is None
                else str(validation_result.bundle.backtest_report_ref.artifact_id)
            ),
            "stress_test_report_ref": (
                None
                if validation_result.bundle.stress_test_report_ref is None
                else str(validation_result.bundle.stress_test_report_ref.artifact_id)
            ),
        },
    )
    outputs["replay_artifacts.json"] = ArtifactRecord.from_path(replay_artifacts_path)
    governance_report_path = _write_json(stage_dir / "governance_report_v1.json", governance_report)
    outputs["governance_report_v1.json"] = ArtifactRecord.from_path(governance_report_path)
    lesson_registry_path = _write_json(
        stage_dir / "lesson_registry_d4.json",
        {
            "schema_version": "1.0",
            "lessons": [
                {
                    "lesson_id": "d4::leaderboard",
                    "status": "success",
                    "message": f"Champion {calibration_run.selected_candidate_id} selected on validation split and scored once on holdout.",
                },
                {
                    "lesson_id": "d4::governance",
                    "status": governance_report.resolved_verdict(),
                    "message": f"Calibration governance verdict: {governance_report.resolved_verdict()}",
                },
            ],
        },
    )
    outputs["lesson_registry_d4.json"] = ArtifactRecord.from_path(lesson_registry_path)

    findings: list[ValidationFinding] = []
    if len(backtest_bundles) != len(BacktestKind):
        findings.append(
            ValidationFinding(
                severity="error",
                code="missing_required_backtests",
                message="D4 requires all 5 backtest kinds to be materialized from D2 outputs",
            )
        )
    if (
        validation_result.bundle.stress_scenarios is None
        or len(validation_result.bundle.stress_scenarios.comparisons) != 6
    ):
        findings.append(
            ValidationFinding(
                severity="error",
                code="missing_required_stress_scenarios",
                message="D4 requires all 6 canonical stress scenarios",
            )
        )
    if transportability.n_transportable_channels < 3:
        findings.append(
            ValidationFinding(
                severity="error",
                code="insufficient_transportable_channels",
                message="D4 requires at least 3 transportable channels for exact sign-off",
            )
        )
    required_strategic_channels = StrategicResponseRunner.required_channel_count(
        waived_families=waived_signoff_families,
    )
    if strategic_metrics.quantified_channels < required_strategic_channels:
        findings.append(
            ValidationFinding(
                severity="error",
                code="insufficient_strategic_channels",
                message=(
                    "D4 requires at least "
                    f"{required_strategic_channels} quantified strategic-response channels "
                    "after applying current signoff waivers"
                ),
            )
        )
    if specification_curve.robustness_score < 0.6:
        findings.append(
            ValidationFinding(
                severity="error",
                code="specification_curve_below_threshold",
                message="D4 specification-curve robustness is below the blueprint threshold",
            )
        )
    if governance_report.resolved_verdict() != "approve":
        findings.append(
            ValidationFinding(
                severity="error",
                code="governance_not_approved",
                message="D4 governance evidence did not resolve to approve",
            )
        )

    return StageBuildResult(
        outputs=outputs,
        findings=findings,
        metrics={
            "blueprint_coverage_threshold": blueprint_coverage_threshold,
            "tier_a_family_count": len(family_eligibility.eligible_families()),
            "transportable_channels": transportability.n_transportable_channels,
            "quantified_strategic_channels": strategic_metrics.quantified_channels,
            "required_strategic_channels": required_strategic_channels,
            "waived_signoff_families": [family.value for family in waived_signoff_families],
            "proxy_promoted_families": [family.value for family in proxy_promoted_families],
            "governance_verdict": governance_report.resolved_verdict(),
            "holdout_score": holdout_scores.overall_score,
        },
        manifest_paths=[calibration_manifest_path],
    )


__all__ = tuple(name for name in globals() if not name.startswith("__"))
