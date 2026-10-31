from __future__ import annotations

import hashlib
import json

import pandas as pd
import pytest

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.data_forge.read_api.ukraine import (
    UKRAINE_D4_SOURCE_JSON_SNAPSHOT_ROLE_BY_CONTRACT,
    UkraineD4GovernanceRequest,
    UkraineIdentityResolutionCohort,
    UkraineIdentityResolutionCohortRow,
)
from polisyos.ir.analytics.distributional import (
    TailRiskDeltaEntry,
    TailRiskDeltaSummary,
)
from polisyos.ir.analytics.fairness import CausalFairnessReport, FairnessDecomposition
from polisyos.ir.analytics.interference import (
    ExposureMappingType,
    InterferenceCertificate,
    InterferenceEffectDecomposition,
    InterferenceMethod,
    NetworkInterferenceReport,
)
from polisyos.ir.observation.bundles import (
    BacktestPlanBundle,
    ContractCompatibilityTarget,
)
from polisyos.ir.observation.contract_compilers import SpecificationCurveInput
from polisyos.scientist.governance.accountability import GovernanceAccountabilityInput
from polisyos.scientist.governance.backtest_matrix import BacktestKind
from polisyos.scientist.governance.blueprint_release import (
    REQUIRED_SIGNOFF_FAMILIES,
    CalibrationRunRunner,
    FamilyEligibilityEntry,
    FamilyEligibilityRegistry,
    FamilyTier,
)
from polisyos.scientist.governance.calibration import (
    CalibrationAdversarialResult,
    CalibrationGovernanceReport,
)
from polisyos.scientist.governance.calibration_validation import (
    CalibrationValidationRunner,
    CalibrationValidationRunnerInput,
    load_calibration_validation_bundle,
)
from polisyos.scientist.methods.backtesting.plan import (
    HistoricalValidationPlan,
    PredictionSource,
)
from polisyos.scientist.methods.discovery.utility_judge import (
    DownstreamUtilityReport,
    HypothesisUtilityScore,
)
from polisyos.scientist.methods.search.lessons import (
    LessonCard,
    LessonKind,
    LessonQuery,
    LessonRegistry,
    load_lesson_card,
)
from polisyos.scientist.methods.search.transfer_context import (
    TransferContext,
    TransferScopeRefusedError,
)


class _CountingLessonRegistry:
    def __init__(self, registry: LessonRegistry) -> None:
        self.registry = registry
        self.resolutions = 0
        self.calls = 0
        self.context: TransferContext | None = None

    @property
    def record_local(self) -> object:
        self.resolutions += 1
        if self.resolutions > 1:
            raise AssertionError("selected lesson writer was resolved more than once")

        def record(
            card: LessonCard,
            *,
            context: TransferContext,
        ) -> ArtifactRef:
            self.calls += 1
            self.context = context
            return self.registry.record_local(card, context=context)

        return record


class _MissingLessonRegistry:
    pass


class _NonCallableLessonRegistry:
    record_local = 7


class _WrongResultLessonRegistry:
    def __init__(self, result: object) -> None:
        self.result = result
        self.calls = 0

    def record_local(
        self,
        card: LessonCard,
        *,
        context: TransferContext,
    ) -> object:
        del card, context
        self.calls += 1
        return self.result


def _persist_calibration_candidate(store: FileSystemCAS) -> ArtifactRef:
    """Persist the selected score emitted by the existing calibration producer."""
    panel = pd.DataFrame(
        [
            {
                "family": family.value,
                "period_start": period,
                "observed_value": value,
                "trust_weight": 1.0,
            }
            for family in REQUIRED_SIGNOFF_FAMILIES
            for period, value in (
                ("2023-03-01", 1.0),
                ("2023-09-01", 1.5),
                ("2024-06-01", 2.0),
                ("2025-06-01", 2.5),
            )
        ]
    )
    eligibility = FamilyEligibilityRegistry(
        coverage_threshold=1.0,
        families={
            family.value: FamilyEligibilityEntry(
                family=family,
                tier=FamilyTier.A,
                eligible_for_scoring=True,
                exact_signoff_eligible=True,
                observations_present=4,
                coverage_ratio=1.0,
            )
            for family in REQUIRED_SIGNOFF_FAMILIES
        },
    )
    run = CalibrationRunRunner().run(
        panel,
        eligibility_registry=eligibility,
        splits={
            "train_pre_2024": {"start": "2023-01-01", "end": "2023-12-31"},
            "validation_2024": {"start": "2024-01-01", "end": "2024-12-31"},
            "test_2025": {"start": "2025-01-01", "end": "2025-12-31"},
        },
        transportability_score=0.8,
        strategic_plausibility=0.8,
        governance_penalty=0.1,
        interference_fit_score=0.8,
        selected_training_role="train_pre_2024",
        selected_validation_role="validation_2024",
        selected_holdout_role="test_2025",
    )
    candidate = next(
        item for item in run.candidates if item.candidate_id == run.selected_candidate_id
    )
    persisted_ref = store.put_json(
        candidate.model_dump(mode="json"),
        PutOptions(kind="scientist.calibration_candidate", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    return ArtifactRef.model_validate(persisted_ref.model_dump(mode="python"))


def _governance_report() -> CalibrationGovernanceReport:
    return CalibrationGovernanceReport(
        verdict="approve",
        adversarial_results=[
            CalibrationAdversarialResult(
                alias="strategic_gaming_adversarial",
                suite_id="strategic_gaming_v1",
                required=True,
                status="passed",
            ),
            CalibrationAdversarialResult(
                alias="multiplicity_disclosure_adversarial",
                suite_id="multiplicity_disclosure_v1",
                required=True,
                status="passed",
            ),
        ],
        metadata={},
    )


def _plan_bundle(
    tmp_path,
    kind: BacktestKind,
    *,
    exact_predictions: bool = False,
) -> BacktestPlanBundle:
    path = tmp_path / f"{kind.value}.json"
    path.write_text(json.dumps({"metric": [1.0, 1.0, 1.0]}), encoding="utf-8")
    return BacktestPlanBundle(
        contract_target=ContractCompatibilityTarget(
            contract_id=f"{kind.value}_bundle",
            contract_fqn="polisyos.tests.BacktestPlanBundle",
        ),
        required_fields=["metric"],
        holdout_windows=["2024-Q4"],
        selected_training_role="fixture_training",
        selected_validation_role="fixture_validation",
        selected_holdout_role="fixture_holdout",
        plans=[
            HistoricalValidationPlan(
                plan_id=f"{kind.value}_plan",
                historical_data_path=str(path),
                ground_truth_outcomes={"metric": [1.0, 1.0]},
                target_metrics=["metric"],
                prediction_source=PredictionSource.PROVIDED,
                predicted_outcomes={"metric": [1.0, 1.0] if exact_predictions else [0.98, 1.02]},
                selected_training_role="fixture_training",
                selected_validation_role="fixture_validation",
                selected_holdout_role="fixture_holdout",
                metadata={
                    "selected_training_role": "fixture_training",
                    "selected_validation_role": "fixture_validation",
                    "selected_holdout_role": "fixture_holdout",
                },
            ).model_dump(mode="json")
        ],
        historical_payloads={"metric": {"values": [1.0, 1.0, 1.0]}},
    )


def _d4_source_json_profile_inputs(
    store: FileSystemCAS,
) -> tuple[dict[str, object], list[InputRef]]:
    """Persist and re-read the exact three typed D4 JSON source contracts."""
    from polisyos.data_forge.read_api.ukraine import read_ukraine_json_snapshot

    values_and_types = {
        "scientist.d4.governance_request": (
            UkraineD4GovernanceRequest(
                schema_version="policyos.data_forge.ukraine.d4_governance_request.v1",
                authority_purpose="producer_governance_handoff",
                may_not_use_for=["governance_admissibility"],
                required_stage_manifests={
                    "d0_p0": "build_run_d0_p0.json",
                    "d2": "build_run_d2.json",
                    "d3": "build_run_d3.json",
                },
            ),
            UkraineD4GovernanceRequest,
        ),
        "scientist.d4.identity_resolution_cohort": (
            UkraineIdentityResolutionCohort(
                schema_version="policyos.data_forge.ukraine.identity_resolution_cohort.v1",
                rows=[
                    UkraineIdentityResolutionCohortRow(
                        cohort="spending",
                        raw_identity="controlled-spending-1",
                    ),
                    UkraineIdentityResolutionCohortRow(
                        cohort="procurement",
                        raw_identity="controlled-procurement-1",
                    ),
                ],
            ),
            UkraineIdentityResolutionCohort,
        ),
        "scientist.d4.calibration_splits": (
            {
                "fixture_training": {"start": "2023-01-01", "end": "2023-12-31"},
                "fixture_validation": {"start": "2024-01-01", "end": "2024-12-31"},
                "fixture_holdout": {"start": "2025-01-01", "end": "2025-12-31"},
            },
            dict[str, dict[str, str]],
        ),
    }
    reads: dict[str, object] = {}
    input_refs: list[InputRef] = []
    for contract, (value, model_type) in values_and_types.items():
        ref = store.put_json(
            value,
            PutOptions(
                kind="data_forge.ukraine.stage_output_snapshot",
                media_type="application/json",
            ),
            canon_spec=CanonSpec(),
            return_selected_profile=True,
        )
        raw = store.get_bytes(ref)
        read = read_ukraine_json_snapshot(
            store,
            ref,
            raw_payload_bytes=raw,
            expected_sha256=hashlib.sha256(raw).hexdigest(),
            expected_size_bytes=len(raw),
            expected_kind="data_forge.ukraine.stage_output_snapshot",
            consumer_contract=contract,
            model_type=model_type,
        )
        reads[contract] = read.provenance
        input_refs.append(
            InputRef(
                artifact_id=read.provenance.artifact_ref.artifact_id,
                role=UKRAINE_D4_SOURCE_JSON_SNAPSHOT_ROLE_BY_CONTRACT[contract],
                manifest_profile_sha256=read.provenance.selected_manifest_profile_sha256,
            )
        )
    return reads, input_refs


def _utility_report() -> DownstreamUtilityReport:
    return DownstreamUtilityReport(
        scores=[
            HypothesisUtilityScore(
                hypothesis_id="h1",
                identification_status="identified",
                identifiability_score=1.0,
                stability_score=0.8,
                transportability_score=0.82,
                composite_score=0.9,
                rank=1,
            )
        ],
        recommended_shortlist=["h1"],
    )


def _interference_report() -> NetworkInterferenceReport:
    return NetworkInterferenceReport(
        method=InterferenceMethod.PARTIAL_IPW,
        status="success",
        effects=InterferenceEffectDecomposition(
            direct_effect=0.1,
            spillover_effect=0.02,
            total_effect=0.12,
            n_units=8,
            n_treated=3,
        ),
        exposure_mapping=ExposureMappingType.FRACTIONAL,
        n_units=8,
        n_treated=3,
    )


def _accountability_input() -> GovernanceAccountabilityInput:
    return GovernanceAccountabilityInput(
        candidate_id="candidate_policy",
        model_name="policy_classifier",
        model_version="2026.04",
        intended_use="promotion_gate",
        evaluation_split="holdout",
        dataset_name="policy_holdout",
        dataset_version="v1",
        data_sources=["holdout_snapshot"],
        predicted_scores=[0.95, 0.80, 0.70, 0.40, 0.65, 0.55, 0.35, 0.10],
        observed_outcomes=[1.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0],
        protected_attributes={
            "gender": ["F", "F", "F", "F", "M", "M", "M", "M"],
            "region": [
                "urban",
                "urban",
                "rural",
                "rural",
                "urban",
                "urban",
                "rural",
                "rural",
            ],
        },
        causal_fairness_report=CausalFairnessReport(
            decomposition=FairnessDecomposition(
                tv=0.16,
                direct_effect=0.08,
                indirect_effect=0.03,
                spurious_effect=0.05,
                decomposition_residual=0.0,
                n_obs=8,
                protected_attribute="gender",
                outcome="approval",
                mediators=("income_proxy",),
                estimation_method="counterfactual",
            ),
            counterfactual_fairness_satisfied=False,
            path_specific_fairness={"A->Y": False},
            direct_discrimination=0.08,
            indirect_discrimination=0.03,
            primary_unfair_pathway="A->Y",
            recommendation="Direct discrimination remains above threshold.",
        ),
        tail_risk_summary=TailRiskDeltaSummary(
            outcome_name="loss",
            entries=[
                TailRiskDeltaEntry(
                    baseline_quantile=0.95,
                    threshold_value=0.8,
                    baseline_exceedance_probability=0.05,
                    counterfactual_exceedance_probability=0.13,
                    exceedance_probability_delta=0.08,
                    baseline_expected_shortfall=0.22,
                    counterfactual_expected_shortfall=0.34,
                    expected_shortfall_delta=0.12,
                )
            ],
        ),
    )


@pytest.mark.parametrize("purpose", ["promotion", "candidate_diagnostic"])
def test_calibration_validation_refuses_native_before_any_promotion_bundle(
    tmp_path, cas_store, purpose
) -> None:
    class ForbiddenMatrix:
        def run(self, *args, **kwargs):
            pytest.fail("unsupported native calibration reached the matrix producer")

    bundle = _plan_bundle(tmp_path, BacktestKind.MACRO)
    bundle.plans[0]["prediction_source"] = "scientist"
    bundle.plans[0]["scientist_state"] = {"params": {"backtest_native_forecast": {}}}
    candidate_ref = _persist_calibration_candidate(cas_store)
    registry = LessonRegistry(root=tmp_path / "lessons", store=cas_store)
    source_inputs = []
    for role in ("household_candidate_panel", "household_source_basis", "selected_split_manifest"):
        ref = cas_store.put_json(
            {"source": role},
            PutOptions(kind="test.native_calibration_input", media_type="application/json"),
            return_selected_profile=True,
        )
        source_inputs.append(
            InputRef(
                artifact_id=ref.artifact_id,
                role=role,
                manifest_profile_sha256=ref.manifest_profile_sha256,
            )
        )
    before = list(cas_store.iter_artifact_ids())
    with pytest.raises(ValueError, match="native_calibration_validation_not_supported"):
        CalibrationValidationRunner(cas_store, backtest_runner=ForbiddenMatrix()).run(
            CalibrationValidationRunnerInput(
                run_id="R_native_not_calibration",
                candidate_ref=candidate_ref,
                governance_report=_governance_report(),
                backtest_plan_bundles={BacktestKind.MACRO: bundle},
                lesson_registry=registry,
                purpose=purpose,
                input_refs=source_inputs,
                selected_training_role="fixture_training",
                selected_validation_role="fixture_validation",
                selected_holdout_role="fixture_holdout",
            )
        )
    assert list(cas_store.iter_artifact_ids()) == before


def test_calibration_validation_runner_executes_backtest_stress_leaderboard_and_lesson(
    tmp_path,
    cas_store,
) -> None:
    lesson_root = tmp_path / "registry" / "lessons"
    registry = LessonRegistry(root=lesson_root, store=cas_store)
    selected_registry = _CountingLessonRegistry(registry)
    runner = CalibrationValidationRunner(cas_store)
    candidate_ref = _persist_calibration_candidate(cas_store)
    result = runner.run(
        CalibrationValidationRunnerInput(
            run_id="R_c5b_full",
            candidate_ref=candidate_ref,
            governance_report=_governance_report(),
            calibration_fit_score=0.91,
            backtest_plan_bundles={
                kind: _plan_bundle(tmp_path, kind, exact_predictions=True) for kind in BacktestKind
            },
            specification_curve_input=SpecificationCurveInput(
                specification_ids=["s1", "s2", "s3"],
                estimates=[0.3, 0.28, 0.32],
                standard_errors=[0.1, 0.1, 0.1],
            ),
            downstream_utility_report=_utility_report(),
            network_interference_report=_interference_report(),
            interference_certificate=InterferenceCertificate(
                supported_query_family="spillover",
                fallback_mode="pairwise",
                reduction_error_bound=0.05,
            ),
            strategic_summary={
                "fallback_mode": "exact_equilibrium",
                "closure_summary": {
                    "mode": "exact_equilibrium",
                    "equilibrium_count": 1,
                },
                "multiplicity_note": "disclosed",
            },
            baseline_metrics={"policy_value": 100.0, "coverage": 0.9},
            lesson_registry=selected_registry,
            accountability_input=_accountability_input(),
        ),
        return_selected_profile=True,
    )

    assert result.bundle_ref.kind == "scientist.calibration_validation_bundle"
    assert result.bundle_ref.manifest_profile_sha256 is not None
    assert (
        cas_store.get_manifest_by_profile(
            str(result.bundle_ref.artifact_id),
            result.bundle_ref.manifest_profile_sha256,
        ).artifact_id
        == result.bundle_ref.artifact_id
    )
    assert result.bundle.status == "completed"
    assert result.bundle.backtest_matrix is not None
    assert result.bundle.stress_scenarios is not None
    assert result.bundle.leaderboard_entry is not None
    assert result.bundle.lesson_card_ref is not None
    assert selected_registry.resolutions == 1
    assert selected_registry.calls == 1
    assert selected_registry.context is not None
    assert selected_registry.context.task_family == "policy"
    assert selected_registry.context.domain == "general"
    assert selected_registry.context.run_id == "R_c5b_full"
    assert result.bundle.governance_accountability_ref is not None
    assert result.bundle.governance_accountability_summary["risk_weighted_verdict"] == "human_gate"
    backtest_report_ref = result.bundle.backtest_report_ref
    assert backtest_report_ref is not None
    core_backtest_report_ref = ArtifactRef.model_validate(
        backtest_report_ref.model_dump(mode="python")
    )
    expected_candidate_identity = (
        str(candidate_ref.artifact_id),
        candidate_ref.manifest_profile_sha256,
    )
    assert expected_candidate_identity[1] is not None
    for selected_manifest in (
        cas_store.get_manifest(result.bundle_ref),
        cas_store.get_manifest(core_backtest_report_ref),
    ):
        candidate_edges = [item for item in selected_manifest.inputs if item.role == "candidate"]
        assert len(candidate_edges) == 1
        assert (
            str(candidate_edges[0].artifact_id),
            candidate_edges[0].manifest_profile_sha256,
        ) == expected_candidate_identity
    assert (
        cas_store.get_manifest_by_profile(*expected_candidate_identity).artifact_id
        == candidate_ref.artifact_id
    )

    stored = load_calibration_validation_bundle(cas_store, result.bundle_ref)
    readout = stored.readout_summary()
    assert stored.backtest_report_ref is not None
    assert readout["backtest_report_ref"] == str(stored.backtest_report_ref.artifact_id)
    assert readout["backtest_report_status"] == "available"
    assert readout["backtest_metric_diagnostics_status"] == "computed"
    assert readout["backtest_metric_diagnostics"]
    assert not result.bundle.leaderboard_entry.metrics.eligible_for_promotion
    assert (
        "backtest_matrix_source_not_established"
        in result.bundle.leaderboard_entry.metrics.gap_flags
    )
    assert readout["source_json_snapshot_binding_status"] == "not_established"
    assert readout["source_json_snapshot_profile_status"] == "not_established"
    assert readout["source_json_snapshot_profile_provenance"] == "not_established"
    assert readout["eligible_for_promotion"] is False
    assert readout["composite_score"] is not None
    assert stored.readout_summary()["accountability_ref"] is not None
    assert stored.readout_summary()["requires_human_review"] is True
    assert stored.readout_summary()["escalation_triggers"]
    assert stored.readout_summary()["accountability_summary"]["requires_human_review"] is True

    card = load_lesson_card(cas_store, result.bundle.lesson_card_ref)
    assert card.stage_name == "calibration_validation"
    assert card.domain == "general"
    assert card.kind == LessonKind.OPPORTUNITY
    assert card.failure_type == "calibration_validation_source_verification_missing"
    assert card.trust_level.value == "low_confidence"

    failed_governance = _governance_report()
    failed_governance.adversarial_results[0].status = "failed"
    observed_failure = CalibrationValidationRunner(cas_store).run(
        CalibrationValidationRunnerInput(
            run_id="R_c5b_observed_adversarial_failure",
            candidate_ref=candidate_ref,
            governance_report=failed_governance,
            calibration_fit_score=0.91,
            backtest_plan_bundles={
                BacktestKind.MACRO: _plan_bundle(
                    tmp_path, BacktestKind.MACRO, exact_predictions=True
                )
            },
            lesson_registry=registry,
        )
    )
    assert observed_failure.bundle.leaderboard_entry is not None
    assert observed_failure.bundle.leaderboard_entry.metrics.adversarial_passed is False
    assert observed_failure.bundle.lesson_card_ref is not None
    failure_card = load_lesson_card(cas_store, observed_failure.bundle.lesson_card_ref)
    assert failure_card.kind == LessonKind.FAILURE
    assert failure_card.failure_type == "calibration_validation_observed_failure"

    declared_target = TransferContext(task_family="policy", domain="general", run_id="R_c5b_full")
    for supplied_domain in ("finance", ""):
        malformed_declaration = card.model_copy(update={"domain": supplied_domain})
        with pytest.raises(TransferScopeRefusedError):
            registry.record_local(malformed_declaration, context=declared_target)

    fresh_registry = LessonRegistry(root=lesson_root, store=cas_store)
    hits = fresh_registry.query(LessonQuery(domain="general", source_run_id="R_c5b_full", limit=5))
    assert any(hit.lesson_id == card.lesson_id and hit.domain == "general" for hit in hits)


def test_calibration_validation_promotion_requires_recomputed_d4_profiles(
    tmp_path,
    cas_store: FileSystemCAS,
) -> None:
    """D4 profile conformance does not establish backtest forecast/holdout provenance."""
    from polisyos.data_forge.read_api.ukraine import (
        UkraineJSONSnapshotRefusalError,
        read_ukraine_json_snapshot,
    )
    from polisyos.scientist.governance.calibration_validation import (
        _source_json_snapshot_model_type,
        persist_calibration_validation_bundle,
    )

    source_reads, source_inputs = _d4_source_json_profile_inputs(cas_store)
    candidate_ref = _persist_calibration_candidate(cas_store)
    lesson_registry = _CountingLessonRegistry(
        LessonRegistry(root=tmp_path / "profile-eligible-lessons", store=cas_store)
    )
    result = CalibrationValidationRunner(cas_store).run(
        CalibrationValidationRunnerInput(
            run_id="R_c5b_profile_bound_positive",
            candidate_ref=candidate_ref,
            governance_report=_governance_report(),
            calibration_fit_score=0.91,
            backtest_plan_bundles={
                kind: _plan_bundle(tmp_path, kind, exact_predictions=True) for kind in BacktestKind
            },
            specification_curve_input=SpecificationCurveInput(
                specification_ids=["s1", "s2", "s3"],
                estimates=[0.3, 0.28, 0.32],
                standard_errors=[0.1, 0.1, 0.1],
            ),
            downstream_utility_report=_utility_report(),
            network_interference_report=_interference_report(),
            interference_certificate=InterferenceCertificate(
                supported_query_family="spillover",
                fallback_mode="pairwise",
                reduction_error_bound=0.05,
            ),
            strategic_summary={
                "fallback_mode": "exact_equilibrium",
                "closure_summary": {
                    "mode": "exact_equilibrium",
                    "equilibrium_count": 1,
                },
                "multiplicity_note": "disclosed",
            },
            baseline_metrics={"policy_value": 100.0, "coverage": 0.9},
            lesson_registry=lesson_registry,
            input_refs=source_inputs,
            source_json_snapshot_reads=source_reads,
        )
    )

    assert result.bundle.leaderboard_entry is not None
    assert not result.bundle.leaderboard_entry.metrics.eligible_for_promotion
    summary = result.bundle.readout_summary()
    assert summary["source_json_snapshot_binding_status"] == "available"
    assert summary["source_json_snapshot_profile_status"] == "declared_bytes_conformant"
    assert summary["source_json_snapshot_profile_provenance"] == "recomputed"
    assert summary["eligible_for_promotion"] is False
    assert summary["backtest_source_reconciliation_status"] == "not_established"
    assert summary["backtest_trust_status"] == "not_established"
    assert summary["backtest_trust_score"] is None
    assert lesson_registry.calls == 1 and result.bundle.lesson_card_ref is not None
    lesson = load_lesson_card(cas_store, result.bundle.lesson_card_ref)
    assert lesson.kind == LessonKind.OPPORTUNITY

    # A persisted historical or forged eligibility bit cannot restore authority
    # when the actual forecast/holdout source binding is unavailable.
    claimed_bundle = result.bundle.model_copy(deep=True)
    assert claimed_bundle.leaderboard_entry is not None
    claimed_bundle.leaderboard_entry.metrics.eligible_for_promotion = True
    claimed_bundle.leaderboard_entry.metrics.gap_flags = []
    unbound = type(claimed_bundle).model_validate(claimed_bundle.model_dump(mode="python"))
    assert unbound.readout_summary()["composite_score"] is None
    assert not unbound.readout_summary()["eligible_for_promotion"]
    claimed_ref = persist_calibration_validation_bundle(
        cas_store,
        claimed_bundle,
        inputs=[
            InputRef(
                artifact_id=candidate_ref.artifact_id,
                role="candidate",
                manifest_profile_sha256=candidate_ref.manifest_profile_sha256,
            ),
            *source_inputs,
        ],
    )
    claimed_fresh = load_calibration_validation_bundle(cas_store, claimed_ref)
    assert claimed_fresh.leaderboard_entry is not None
    assert not claimed_fresh.leaderboard_entry.metrics.eligible_for_promotion
    assert (
        "backtest_matrix_source_not_established"
        in claimed_fresh.leaderboard_entry.metrics.gap_flags
    )
    assert not claimed_fresh.readout_summary()["eligible_for_promotion"]

    # The historical 1.0 reader stays compatible while refusing an unbound
    # source-profile promotion claim over the exact same qualifying backtest.
    legacy_bundle = result.bundle.model_copy(
        update={
            "run_id": "R_c5b_profileless_legacy_history",
            "schema_version": "1.0",
            "source_json_snapshot_reads": {},
        }
    )
    legacy_ref = persist_calibration_validation_bundle(
        cas_store,
        legacy_bundle,
        inputs=[
            InputRef(
                artifact_id=candidate_ref.artifact_id,
                role="candidate",
                manifest_profile_sha256=candidate_ref.manifest_profile_sha256,
            ),
            *source_inputs,
        ],
    )
    legacy = load_calibration_validation_bundle(cas_store, legacy_ref)
    legacy_summary = legacy.readout_summary()
    assert legacy.schema_version == "1.0"
    assert legacy_summary["source_json_snapshot_binding_status"] == "not_established"
    assert legacy_summary["source_json_snapshot_binding_reason"] == (
        "source_json_snapshot_reads_absent"
    )
    assert legacy.leaderboard_entry is not None
    assert not legacy.leaderboard_entry.metrics.eligible_for_promotion
    assert legacy_summary["eligible_for_promotion"] is False

    # A sibling source ID cannot satisfy the exact profile-to-input binding.
    mismatched_inputs = list(source_inputs)
    mismatched_inputs[0] = InputRef(
        artifact_id=source_inputs[1].artifact_id,
        role=source_inputs[0].role,
        manifest_profile_sha256=source_inputs[1].manifest_profile_sha256,
    )
    with pytest.raises(ValueError, match="source JSON profile read is not bound"):
        CalibrationValidationRunnerInput(
            run_id="R_c5b_sibling_source_mismatch",
            candidate_ref=candidate_ref,
            governance_report=_governance_report(),
            input_refs=mismatched_inputs,
            source_json_snapshot_reads=source_reads,
        )

    # A present malformed manifest profile remains a refusal, never profile absence.
    contract = "scientist.d4.governance_request"
    provenance = result.bundle.source_json_snapshot_reads[contract]
    raw_payload_bytes = cas_store.get_bytes(provenance.artifact_ref)
    selected_manifest_path = cas_store._manifest_path_for_ref(
        provenance.artifact_ref.artifact_id,
        provenance.artifact_ref.manifest_profile_sha256,
    )
    selected_manifest = json.loads(selected_manifest_path.read_bytes())
    selected_manifest["canon"]["max_depth"] = "not-an-integer"
    selected_manifest_path.write_text(
        json.dumps(selected_manifest, separators=(",", ":")),
        encoding="utf-8",
    )
    with pytest.raises(UkraineJSONSnapshotRefusalError):
        read_ukraine_json_snapshot(
            cas_store,
            provenance.artifact_ref,
            raw_payload_bytes=raw_payload_bytes,
            expected_sha256=provenance.content_sha256,
            expected_size_bytes=provenance.content_size_bytes,
            expected_kind=provenance.artifact_kind,
            consumer_contract=contract,
            model_type=_source_json_snapshot_model_type(contract),
        )
    malformed = load_calibration_validation_bundle(cas_store, result.bundle_ref)
    malformed_summary = malformed.readout_summary()
    assert malformed_summary["source_json_snapshot_binding_status"] == "unavailable"
    assert malformed_summary["source_json_snapshot_profile_status"] == "unavailable"
    assert malformed_summary["eligible_for_promotion"] is False


@pytest.mark.parametrize(
    "registry",
    [_MissingLessonRegistry(), _NonCallableLessonRegistry()],
    ids=["missing-record-local", "noncallable-record-local"],
)
def test_calibration_validation_rejects_malformed_registry_before_producer_work(
    registry: object,
    cas_store: FileSystemCAS,
) -> None:
    candidate_ref = _persist_calibration_candidate(cas_store)
    before = list(cas_store.iter_artifact_ids())

    with pytest.raises(TypeError, match="lesson registry must provide a callable record_local"):
        CalibrationValidationRunner(cas_store).run(
            CalibrationValidationRunnerInput(
                run_id="R_c5b_bad_registry",
                candidate_ref=candidate_ref,
                governance_report=_governance_report(),
                lesson_registry=registry,
            )
        )

    assert cas_store.iter_artifact_ids() == before


@pytest.mark.parametrize("result_value", [None, "not-an-artifact-ref"], ids=["none", "string"])
def test_calibration_validation_rejects_malformed_lesson_publication_result(
    result_value: object,
    cas_store: FileSystemCAS,
) -> None:
    candidate_ref = _persist_calibration_candidate(cas_store)
    registry = _WrongResultLessonRegistry(result_value)

    with pytest.raises(TypeError, match="lesson registry record_local must return an ArtifactRef"):
        CalibrationValidationRunner(cas_store).run(
            CalibrationValidationRunnerInput(
                run_id="R_c5b_bad_publication",
                candidate_ref=candidate_ref,
                governance_report=_governance_report(),
                lesson_registry=registry,
            )
        )

    assert registry.calls == 1


def test_calibration_validation_runner_blocks_eligibility_on_missing_transport_and_interference(
    tmp_path,
    cas_store,
) -> None:
    runner = CalibrationValidationRunner(cas_store)
    result = runner.run(
        CalibrationValidationRunnerInput(
            run_id="R_c5b_gaps",
            candidate_ref=_persist_calibration_candidate(cas_store),
            governance_report=_governance_report(),
            calibration_fit_score=0.9,
            backtest_plan_bundles={kind: _plan_bundle(tmp_path, kind) for kind in BacktestKind},
            baseline_metrics={"policy_value": 100.0},
        )
    )

    assert result.bundle.status == "completed"
    assert result.bundle.lesson_card_ref is None
    metrics = result.bundle.leaderboard_entry.metrics
    assert "missing_metric:transportability_score" in metrics.gap_flags
    assert "missing_metric:interference_fit" in metrics.gap_flags
    assert metrics.eligible_for_promotion is False


def test_s1_candidate_diagnostic_is_never_promotable_and_binds_inputs(tmp_path, cas_store) -> None:
    import hashlib

    from polisyos.data_forge.domains.ukraine.manifests import (
        HouseholdDiagnosticPanelBasis,
    )
    from polisyos.data_forge.read_api.ukraine import read_ukraine_json_snapshot

    source_roles = (
        "panel",
        "basis",
        "split",
        "nested_report_source",
        "duplicate_source_a",
        "duplicate_source_b",
    )
    source_contract_by_role = {
        "basis": "scientist.d3.household_candidate_basis",
        "split": "scientist.d4.calibration_splits",
    }
    source_model_by_contract = {
        "scientist.d3.household_candidate_basis": HouseholdDiagnosticPanelBasis,
        "scientist.d4.calibration_splits": dict[str, dict[str, str]],
    }
    source_payload_by_contract = {
        "scientist.d3.household_candidate_basis": HouseholdDiagnosticPanelBasis(
            status="complete",
            source_row_count=1,
            panel_artifact={
                "path": "controlled-panel.parquet",
                "sha256": "a" * 64,
                "size_bytes": 1,
            },
        ).model_dump(mode="json"),
        "scientist.d4.calibration_splits": {
            "fixture_training": {"start": "2023-01-01", "end": "2023-12-31"},
            "fixture_validation": {"start": "2024-01-01", "end": "2024-12-31"},
            "fixture_holdout": {"start": "2025-01-01", "end": "2025-12-31"},
        },
    }
    payload_by_role = {
        role: json.dumps(
            source_payload_by_contract[source_contract_by_role[role]]
            if role in source_contract_by_role
            else {"source": role},
            separators=(",", ":"),
        ).encode("utf-8")
        for role in source_roles
    }
    refs_by_role = {
        role: cas_store.put_bytes(
            payload,
            PutOptions(
                kind="data_forge.ukraine.stage_output_snapshot",
                media_type="application/json",
            ),
            return_selected_profile=True,
        )
        for role, payload in payload_by_role.items()
    }
    source_input_roles = (
        ("panel", "household_candidate_panel"),
        ("basis", "household_source_basis"),
        ("split", "selected_split_manifest"),
        ("nested_report_source", "backtest_report"),
        ("duplicate_source_a", "controlled_extension_source"),
        ("duplicate_source_b", "controlled_extension_source"),
    )
    input_refs = [
        InputRef(
            artifact_id=refs_by_role[source_role].artifact_id,
            role=input_role,
            manifest_profile_sha256=refs_by_role[source_role].manifest_profile_sha256,
        )
        for source_role, input_role in source_input_roles
    ]
    source_json_snapshot_contracts = source_contract_by_role
    source_json_snapshot_reads = {}
    for source_role, contract in source_json_snapshot_contracts.items():
        payload = payload_by_role[source_role]
        read = read_ukraine_json_snapshot(
            cas_store,
            refs_by_role[source_role],
            raw_payload_bytes=payload,
            expected_sha256=hashlib.sha256(payload).hexdigest(),
            expected_size_bytes=len(payload),
            expected_kind="data_forge.ukraine.stage_output_snapshot",
            consumer_contract=contract,
            model_type=source_model_by_contract[contract],
        )
        source_json_snapshot_reads[contract] = read.provenance
    result = CalibrationValidationRunner(cas_store).run(
        CalibrationValidationRunnerInput(
            run_id="s1-candidate-diagnostic",
            candidate_ref=_persist_calibration_candidate(cas_store),
            governance_report=_governance_report(),
            backtest_plan_bundles={
                BacktestKind.HOUSEHOLD: _plan_bundle(tmp_path, BacktestKind.HOUSEHOLD)
            },
            purpose="candidate_diagnostic",
            input_refs=input_refs,
            source_json_snapshot_reads=source_json_snapshot_reads,
            selected_training_role="fixture_training",
            selected_validation_role="fixture_validation",
            selected_holdout_role="fixture_holdout",
        )
    )
    assert result.bundle.status == result.bundle.purpose == "candidate_diagnostic"
    assert result.bundle_ref.manifest_profile_sha256 is None
    assert result.bundle.leaderboard_entry is None
    assert result.bundle.stress_scenarios is None
    assert result.bundle.lesson_card_ref is None
    assert result.bundle.governance_accountability_ref is None
    assert result.bundle.readout_summary()["eligible_for_promotion"] is False
    assert result.bundle.schema_version == "1.1"
    assert set(result.bundle.source_json_snapshot_reads) == set(
        source_json_snapshot_contracts.values()
    )
    for source_role, contract in source_json_snapshot_contracts.items():
        provenance = result.bundle.source_json_snapshot_reads[contract]
        assert provenance.profile_status == "profile_absent_raw_snapshot_candidate"
        assert provenance.artifact_ref.artifact_id == refs_by_role[source_role].artifact_id
        assert (
            provenance.artifact_ref.manifest_profile_sha256
            == refs_by_role[source_role].manifest_profile_sha256
        )
        assert provenance.producer_attestation_status == "not_established"
        assert provenance.currentness_provenance == "not_established"
    fresh = load_calibration_validation_bundle(cas_store, result.bundle_ref)
    assert fresh.backtest_report_ref is not None
    fresh_summary = fresh.readout_summary()
    assert fresh_summary["source_json_snapshot_binding_status"] == "available"
    assert fresh_summary["backtest_metric_diagnostics"]
    assert fresh_summary["backtest_report_status"] == "available"
    assert fresh_summary["backtest_metric_diagnostics_status"] == "computed"
    assert (
        fresh.selected_training_role == "fixture_training"
        and fresh.selected_validation_role == "fixture_validation"
    )
    assert fresh.selected_holdout_role == "fixture_holdout"
    from collections import Counter

    persisted_inputs = cas_store.get_manifest(result.bundle_ref.artifact_id).inputs
    roles = Counter(item.role for item in persisted_inputs)
    assert {
        "candidate",
        "household_candidate_panel",
        "household_source_basis",
        "selected_split_manifest",
    } <= set(roles)
    assert roles["backtest_report"] == 2
    assert roles["controlled_extension_source"] == 2


def test_calibration_validation_runner_input_rejects_reserved_candidate_source_role(
    cas_store,
) -> None:
    candidate_ref = _persist_calibration_candidate(cas_store)
    with pytest.raises(ValueError, match="candidate role is reserved"):
        CalibrationValidationRunnerInput(
            run_id="R_c5b_candidate-role-shadow",
            candidate_ref=candidate_ref,
            governance_report=_governance_report(),
            input_refs=[
                InputRef(
                    artifact_id=candidate_ref.artifact_id,
                    role="candidate",
                    manifest_profile_sha256=candidate_ref.manifest_profile_sha256,
                )
            ],
        )


def test_promotion_fresh_reader_rejects_valid_report_with_sibling_source_edges(
    tmp_path,
    cas_store: FileSystemCAS,
) -> None:
    """Fresh C5b loading binds the nested report to the exact selected source edges."""
    from collections import Counter

    from polisyos.core.artifacts import ensure_ir_artifact_store
    from polisyos.ir import load_backtest_report
    from polisyos.ir.analytics.backtest import persist_backtest_report
    from polisyos.scientist.governance.calibration_validation import (
        CalibrationValidationLessonPublisher,
        persist_calibration_validation_bundle,
    )

    source_reads, source_inputs = _d4_source_json_profile_inputs(cas_store)
    candidate_ref = _persist_calibration_candidate(cas_store)
    lesson_registry = _CountingLessonRegistry(
        LessonRegistry(root=tmp_path / "report-edge-lessons", store=cas_store)
    )
    runner_input = CalibrationValidationRunnerInput(
        run_id="R_c5b_report_edge_binding_positive",
        candidate_ref=candidate_ref,
        governance_report=_governance_report(),
        calibration_fit_score=0.91,
        backtest_plan_bundles={
            kind: _plan_bundle(tmp_path, kind, exact_predictions=True) for kind in BacktestKind
        },
        specification_curve_input=SpecificationCurveInput(
            specification_ids=["s1", "s2", "s3"],
            estimates=[0.3, 0.28, 0.32],
            standard_errors=[0.1, 0.1, 0.1],
        ),
        downstream_utility_report=_utility_report(),
        network_interference_report=_interference_report(),
        interference_certificate=InterferenceCertificate(
            supported_query_family="spillover",
            fallback_mode="pairwise",
            reduction_error_bound=0.05,
        ),
        strategic_summary={
            "fallback_mode": "exact_equilibrium",
            "closure_summary": {
                "mode": "exact_equilibrium",
                "equilibrium_count": 1,
            },
            "multiplicity_note": "disclosed",
        },
        baseline_metrics={"policy_value": 100.0, "coverage": 0.9},
        lesson_registry=lesson_registry,
        input_refs=source_inputs,
        source_json_snapshot_reads=source_reads,
    )
    result = CalibrationValidationRunner(cas_store).run(runner_input)

    positive = result.bundle.readout_summary()
    assert positive["source_json_snapshot_binding_status"] == "available"
    assert positive["eligible_for_promotion"] is False
    assert result.bundle.backtest_report_ref is not None
    assert result.bundle.leaderboard_entry is not None
    assert not result.bundle.leaderboard_entry.metrics.eligible_for_promotion
    assert result.bundle.lesson_card_ref is not None
    assert load_lesson_card(cas_store, result.bundle.lesson_card_ref).kind is LessonKind.OPPORTUNITY

    # This is a distinct, valid profile with the same registered JSON contract.
    # The C5b bundle keeps its original typed refs and source edges.
    sibling_source_ref = cas_store.put_json(
        UkraineIdentityResolutionCohort(
            schema_version=("policyos.data_forge.ukraine.identity_resolution_cohort.v1"),
            rows=[
                UkraineIdentityResolutionCohortRow(
                    cohort="spending", raw_identity="sibling-spending-source"
                ),
                UkraineIdentityResolutionCohortRow(
                    cohort="procurement", raw_identity="sibling-procurement-source"
                ),
            ],
        ),
        PutOptions(
            kind="data_forge.ukraine.stage_output_snapshot",
            media_type="application/json",
        ),
        canon_spec=CanonSpec(),
        return_selected_profile=True,
    )
    sibling_edge = InputRef(
        artifact_id=sibling_source_ref.artifact_id,
        role="identity_resolution_cohort",
        manifest_profile_sha256=sibling_source_ref.manifest_profile_sha256,
    )

    original_report_ref = result.bundle.backtest_report_ref
    report_manifest = cas_store.get_manifest(
        ArtifactRef.model_validate(original_report_ref.model_dump(mode="python"))
    )
    report = load_backtest_report(cas_store, original_report_ref)
    report_schema = report_manifest.artifact_schema
    assert report_schema is not None
    sibling_report_inputs = [
        sibling_edge if edge.role == sibling_edge.role else edge for edge in report_manifest.inputs
    ]
    assert len([edge for edge in sibling_report_inputs if edge.role == sibling_edge.role]) == 1
    sibling_report_ref = persist_backtest_report(
        ensure_ir_artifact_store(cas_store),
        report,
        inputs=sibling_report_inputs,
        schema_name=report_schema.name,
        schema_version=report_schema.version,
    )

    bundle_with_sibling_report = result.bundle.model_copy(
        update={
            "run_id": "R_c5b_report_edge_binding_negative",
            "backtest_matrix": result.bundle.backtest_matrix.model_copy(
                update={"backtest_report_ref": sibling_report_ref}
            ),
            "lesson_card_ref": None,
        }
    )
    expected_bundle_inputs = [
        InputRef(
            artifact_id=candidate_ref.artifact_id,
            role="candidate",
            manifest_profile_sha256=candidate_ref.manifest_profile_sha256,
        ),
        *source_inputs,
    ]
    sibling_bundle_ref = persist_calibration_validation_bundle(
        cas_store,
        bundle_with_sibling_report,
        inputs=expected_bundle_inputs,
    )

    persisted_bundle_manifest = cas_store.get_manifest(sibling_bundle_ref)
    persisted_source_edges = [
        edge for edge in persisted_bundle_manifest.inputs if edge.role != "backtest_report"
    ]

    def edge_identity(edge: InputRef) -> tuple[str, str, str | None]:
        return (
            edge.role,
            str(edge.artifact_id),
            edge.manifest_profile_sha256,
        )

    assert Counter(map(edge_identity, persisted_source_edges)) == Counter(
        map(edge_identity, expected_bundle_inputs)
    )
    sibling_report_manifest = cas_store.get_manifest(
        ArtifactRef.model_validate(sibling_report_ref.model_dump(mode="python"))
    )
    assert Counter(map(edge_identity, sibling_report_manifest.inputs)) != Counter(
        map(edge_identity, expected_bundle_inputs)
    )

    fresh = load_calibration_validation_bundle(cas_store, sibling_bundle_ref)
    negative = fresh.readout_summary()
    assert negative["source_json_snapshot_binding_status"] == "unavailable"
    assert negative["eligible_for_promotion"] is False
    assert fresh.leaderboard_entry is not None
    assert not fresh.leaderboard_entry.metrics.eligible_for_promotion

    consumer_input = runner_input.model_copy(
        update={"run_id": "R_c5b_report_edge_binding_negative"}
    )
    failure_lesson_ref = CalibrationValidationLessonPublisher().publish(
        consumer_input,
        fresh,
        record_local=lesson_registry.registry.record_local,
    )
    assert failure_lesson_ref is not None
    assert load_lesson_card(cas_store, failure_lesson_ref).kind is LessonKind.OPPORTUNITY
