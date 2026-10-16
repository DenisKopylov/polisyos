from __future__ import annotations

from typing import Any

from polisyos.core.artifacts import (
    ArtifactRef,
    InputRef,
    PutOptions,
    SchemaInfo,
    input_ref_from_artifact_ref,
)
from polisyos.core.canon import CanonSpec
from polisyos.foundry.validation import normalize_phase2_artifact_family
from polisyos.ir import CrossGraphEvidenceProfile, EvidenceSourceKind
from polisyos.scientist.evidence.sources import (
    EvidenceSourcesConfig,
    build_path_source_status,
)
from polisyos.scientist.methods.autotune.models import (
    BenchmarkEvaluation,
    BenchmarkSplit,
    persist_benchmark_evaluation,
)
from polisyos.scientist.methods.backtesting.adversarial import (
    ABSTRACTION_LEAKAGE_SUITE_ID,
    MULTIPLICITY_DISCLOSURE_SUITE_ID,
    PHASE_D4_ROTATION_GROUP,
    STRATEGIC_GAMING_SUITE_ID,
    run_phase_d4_challenge_suites,
)
from polisyos.scientist.methods.doe.stress_report import (
    _STRESS_OUTCOME_BASIS_ARTIFACT_KIND,
    _STRESS_OUTCOME_BASIS_SCHEMA_NAME,
    _STRESS_OUTCOME_BASIS_SCHEMA_VERSION,
    _STRESS_TEST_REPORT_ARTIFACT_KIND,
    _STRESS_TEST_REPORT_SCHEMA_NAME,
    StressScoreComponent,
    StressTestReport,
    resolve_stress_score_components,
)
from polisyos.scientist.methods.search.benchmark_registry import BenchmarkRegistry
from polisyos.scientist.methods.search.promotion_evidence import PromotionEvidenceBundle
from polisyos.scientist.methods.search.transfer_context import resolve_transfer_context
from polisyos.scientist.nodes.builtins.decide.policy_blueprint_runtime_engine import (
    _RuntimeSession,
)
from polisyos.scientist.nodes.builtins.decide.policy_runtime_state import (
    maybe_artifact_ref,
)
from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
    _parse_policy_claim_mode,
    _require_policy_runtime_registry_root,
    load_benchmark_evaluation,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_PROMOTION_EVIDENCE_BUNDLE_REF,
    ARTIFACT_WELFARE_BUNDLE_REF,
    INPUT_PROMOTION_EVIDENCE_BUNDLE_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.policy_design.objectives import PolicyEvaluationVector
from polisyos.scientist.policy_design.schema import PolicyCandidateSchema


def _resolve_policy_runtime_source_statuses(
    *,
    cross_graph_profile: CrossGraphEvidenceProfile | None,
    evidence_sources: EvidenceSourcesConfig,
) -> dict[str, str]:
    statuses: dict[str, str] = {}
    if cross_graph_profile is not None:
        statuses.update(
            {key: value.status.value for key, value in cross_graph_profile.source_statuses.items()}
        )

    inferred = {
        EvidenceSourceKind.ACADEMIC.value: build_path_source_status(
            EvidenceSourceKind.ACADEMIC,
            evidence_sources.academic_db_path,
            detail="policy_runtime_evidence_sources",
        ).status.value,
        EvidenceSourceKind.DATASETS.value: build_path_source_status(
            EvidenceSourceKind.DATASETS,
            evidence_sources.datasets_db_path,
            detail="policy_runtime_evidence_sources",
        ).status.value,
        EvidenceSourceKind.LEGAL.value: build_path_source_status(
            EvidenceSourceKind.LEGAL,
            evidence_sources.legal_db_path,
            detail="policy_runtime_evidence_sources",
        ).status.value,
    }
    benchmark_path = (
        str(evidence_sources.benchmark_report_path or "").strip()
        or str(evidence_sources.benchmark_suite_path or "").strip()
        or None
    )
    inferred[EvidenceSourceKind.BENCHMARK.value] = build_path_source_status(
        EvidenceSourceKind.BENCHMARK,
        benchmark_path,
        detail="policy_runtime_evidence_sources",
    ).status.value
    for key, value in inferred.items():
        statuses.setdefault(key, value)
    return statuses


def _register_runtime_benchmark_inputs(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    benchmark_registry: BenchmarkRegistry,
    evidence_bundle: PromotionEvidenceBundle | None,
    family: str | None,
    claim_mode: str | None = None,
    query_type: str | None,
    estimator_name: str | None,
    readiness_target: str | None,
) -> None:
    expected_loop_id = _expected_policy_loop_id(state)
    rotating_refs: list[ArtifactRef] = []
    if "rotating_challenge_evaluation_refs" in state.params:
        supplied_refs = state.params["rotating_challenge_evaluation_refs"]
        if not isinstance(supplied_refs, list):
            raise ValueError("rotating_challenge_evaluation_refs_invalid")
        for supplied_ref in supplied_refs:
            parsed_ref = maybe_artifact_ref(supplied_ref)
            if parsed_ref is None:
                raise ValueError("rotating_challenge_evaluation_refs_invalid")
            rotating_refs.append(parsed_ref)
    if evidence_bundle is not None and evidence_bundle.rotating_challenge_evaluation_refs:
        rotating_refs = list(evidence_bundle.rotating_challenge_evaluation_refs)
    hidden_holdout_ref = (
        evidence_bundle.hidden_holdout_evaluation_ref
        if evidence_bundle is not None
        else maybe_artifact_ref(state.params.get("hidden_holdout_evaluation_ref"))
    )
    _maybe_register_benchmark_evaluation(
        ctx,
        benchmark_registry=benchmark_registry,
        ref=hidden_holdout_ref,
        split_type=BenchmarkSplit.HIDDEN_HOLDOUT,
        run_id=state.run_id,
        expected_loop_id=expected_loop_id,
        family=family,
        claim_mode=claim_mode,
        query_type=query_type,
        estimator_name=estimator_name,
        readiness_target=readiness_target,
    )
    for ref in rotating_refs:
        _maybe_register_benchmark_evaluation(
            ctx,
            benchmark_registry=benchmark_registry,
            ref=ref,
            split_type=BenchmarkSplit.ROTATING_CHALLENGE,
            run_id=state.run_id,
            expected_loop_id=expected_loop_id,
            family=family,
            claim_mode=claim_mode,
            query_type=query_type,
            estimator_name=estimator_name,
            readiness_target=readiness_target,
        )


def _run_and_register_phase_d4_challenge_suites(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    benchmark_registry: BenchmarkRegistry,
    candidate_ref: ArtifactRef,
    selection_evaluation: BenchmarkEvaluation,
    benchmark_scope: dict[str, str | None],
    artifacts_index: dict[str, ArtifactRef],
) -> tuple[list[ArtifactRef], list[ArtifactRef], tuple[str, ...]]:
    suite_results, warnings = run_phase_d4_challenge_suites(
        store=ctx.store,
        run_id=state.run_id,
        loop_id=selection_evaluation.loop_id,
        candidate_ref=candidate_ref,
        params=state.params,
        artifacts_index=artifacts_index,
        selection_metadata=selection_evaluation.metadata,
    )
    benchmark_refs: list[ArtifactRef] = []
    stress_refs: list[ArtifactRef] = []
    retained_warnings = list(warnings)

    for suite_result in suite_results:
        benchmark_ref = persist_benchmark_evaluation(
            ctx.store,
            suite_result.benchmark_evaluation,
            return_selected_profile=True,
        )
        benchmark_refs.append(benchmark_ref)
        benchmark_registry.record_evaluation(
            suite_result.benchmark_evaluation,
            benchmark_ref,
            run_id=state.run_id,
            family=benchmark_scope["artifact_family"],
            query_type=benchmark_scope["query_type"],
            estimator_name=benchmark_scope["estimator_name"],
            readiness_target=benchmark_scope["readiness_target"],
            rotation_group=PHASE_D4_ROTATION_GROUP,
            produced_by_run_id=state.run_id,
            metadata={
                "artifact_family": benchmark_scope["artifact_family"],
                "claim_mode": benchmark_scope["claim_mode"],
                "rotation_group": PHASE_D4_ROTATION_GROUP,
                **dict(suite_result.benchmark_evaluation.metadata),
            },
        )
        basis = suite_result.stress_outcome_basis.model_copy(
            update={"benchmark_evaluation_ref": benchmark_ref}
        )
        basis_ref = ctx.store.put_json(
            basis,
            PutOptions(
                kind=_STRESS_OUTCOME_BASIS_ARTIFACT_KIND,
                media_type="application/json",
                schema=SchemaInfo(
                    name=_STRESS_OUTCOME_BASIS_SCHEMA_NAME,
                    version=_STRESS_OUTCOME_BASIS_SCHEMA_VERSION,
                ),
                inputs=[
                    InputRef(
                        artifact_id=benchmark_ref.artifact_id,
                        role="benchmark_evaluation",
                        manifest_profile_sha256=benchmark_ref.manifest_profile_sha256,
                    ),
                    InputRef(
                        artifact_id=candidate_ref.artifact_id,
                        role="candidate",
                        manifest_profile_sha256=candidate_ref.manifest_profile_sha256,
                    ),
                ],
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        component = StressScoreComponent(
            component_id=basis.source_id,
            score_profile="finite_binary_scenario_v1",
            outcome_basis_ref=basis_ref,
        )
        resolution = resolve_stress_score_components(
            ctx.store, [component], expected_candidate_ref=candidate_ref
        )
        source_stress_report = suite_result.stress_test_report
        if source_stress_report is None:
            retained_warnings.append(f"phase_d4_stress_report_absent:{suite_result.suite_id}")
            continue
        stress_report = source_stress_report.model_copy(
            update={
                "score_components": [component],
                "score_profile": resolution.score_profile or "finite_binary_scenario_v1",
                "score_status": resolution.status,
                "score_reason": resolution.reason_code,
                "score_predicate_status": resolution.predicate_status,
                "robustness_score": resolution.robustness_score,
                "total_scenarios_evaluated": resolution.total_scenarios_evaluated,
                "critical_count": resolution.critical_count,
                "high_count": resolution.high_count,
                "medium_count": resolution.medium_count,
            }
        )
        stress_ref = ctx.store.put_json(
            stress_report,
            PutOptions(
                kind=_STRESS_TEST_REPORT_ARTIFACT_KIND,
                media_type="application/json",
                schema=SchemaInfo(name=_STRESS_TEST_REPORT_SCHEMA_NAME, version="1.1"),
                inputs=[
                    InputRef(
                        artifact_id=candidate_ref.artifact_id,
                        role="candidate",
                        manifest_profile_sha256=candidate_ref.manifest_profile_sha256,
                    ),
                    InputRef(
                        artifact_id=benchmark_ref.artifact_id,
                        role="benchmark_evaluation",
                        manifest_profile_sha256=benchmark_ref.manifest_profile_sha256,
                    ),
                    InputRef(
                        artifact_id=basis_ref.artifact_id,
                        role="stress_outcome_basis",
                        manifest_profile_sha256=basis_ref.manifest_profile_sha256,
                    ),
                ],
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        stress_refs.append(stress_ref)
        benchmark_registry.record(
            BenchmarkSplit.ADVERSARIAL.value,
            stress_ref,
            run_id=state.run_id,
            loop_id=selection_evaluation.loop_id,
            suite_id=suite_result.suite_id,
            suite_version=suite_result.suite_version,
            family=benchmark_scope["artifact_family"],
            query_type=benchmark_scope["query_type"],
            estimator_name=benchmark_scope["estimator_name"],
            readiness_target=benchmark_scope["readiness_target"],
            rotation_group=PHASE_D4_ROTATION_GROUP,
            produced_by_run_id=state.run_id,
            artifact_kind="scientist.stress_test_report",
            metadata={
                "artifact_type": "stress_test_report",
                "artifact_family": benchmark_scope["artifact_family"],
                "claim_mode": benchmark_scope["claim_mode"],
                "rotation_group": PHASE_D4_ROTATION_GROUP,
                **dict(source_stress_report.metadata),
            },
        )
    return benchmark_refs, stress_refs, tuple(retained_warnings)


def _dedupe_phase_d4_rotating_refs(
    ctx: ExecutionContext,
    refs: list[ArtifactRef],
) -> list[ArtifactRef]:
    latest_by_suite: dict[str, ArtifactRef] = {}
    ordered: list[tuple[str | None, ArtifactRef]] = []
    d4_suite_ids = {
        STRATEGIC_GAMING_SUITE_ID,
        MULTIPLICITY_DISCLOSURE_SUITE_ID,
        ABSTRACTION_LEAKAGE_SUITE_ID,
    }
    for ref in refs:
        evaluation = _load_benchmark_if_present(ctx, ref)
        suite_id = None
        if evaluation is not None:
            suite_id = str(
                evaluation.metadata.get("challenge_suite_id") or evaluation.suite_id or ""
            ).strip()
            if suite_id not in d4_suite_ids:
                suite_id = None
        ordered.append((suite_id, ref))
        if suite_id is not None:
            latest_by_suite[suite_id] = ref

    deduped: list[ArtifactRef] = []
    emitted_d4_suite_ids: set[str] = set()
    for suite_id, ref in reversed(ordered):
        if suite_id is None:
            deduped.append(ref)
            continue
        if suite_id in emitted_d4_suite_ids:
            continue
        emitted_d4_suite_ids.add(suite_id)
        deduped.append(latest_by_suite[suite_id])
    deduped.reverse()
    return deduped


def _maybe_register_benchmark_evaluation(
    ctx: ExecutionContext,
    *,
    benchmark_registry: BenchmarkRegistry,
    ref: ArtifactRef | None,
    split_type: BenchmarkSplit,
    run_id: str,
    expected_loop_id: str,
    family: str | None,
    claim_mode: str | None,
    query_type: str | None,
    estimator_name: str | None,
    readiness_target: str | None,
) -> None:
    if ref is None:
        return
    evaluation = _load_benchmark_if_present(ctx, ref)
    if evaluation is None:
        return
    if evaluation.loop_id != expected_loop_id:
        return
    if evaluation.resolved_runtime_split_type() is not split_type:
        return
    benchmark_registry.record_evaluation(
        evaluation,
        ref,
        run_id=run_id,
        family=family,
        query_type=query_type,
        estimator_name=estimator_name,
        readiness_target=readiness_target,
        produced_by_run_id=run_id,
        metadata={
            "loop_id": evaluation.loop_id,
            "artifact_family": family,
            "claim_mode": claim_mode,
        },
    )


def _optional_scope_text(
    name: str,
    sources: tuple[dict[str, Any], ...],
    *,
    lowercase: bool = False,
) -> str | None:
    """Read optional declared scope without coercing malformed supplied values."""
    for source in sources:
        if name not in source:
            continue
        value = source[name]
        if value is None:
            continue
        if not isinstance(value, str):
            raise ValueError(f"{name}_invalid")
        text = value.strip()
        if text:
            return text.lower() if lowercase else text
    return None


def _resolve_benchmark_scope(
    *,
    state: ExperimentState,
    candidate: PolicyCandidateSchema,
    selection_vector: PolicyEvaluationVector,
) -> dict[str, str | None]:
    metadata = dict(selection_vector.metadata or {})
    candidate_metadata = dict(candidate.metadata or {})
    query_type = (
        str(
            state.params.get("query_type")
            or candidate_metadata.get("query_type")
            or metadata.get("query_type")
            or "policy"
        ).strip()
        or None
    )
    estimator_name = (
        str(
            state.params.get("estimator_name")
            or metadata.get("estimator_name")
            or candidate_metadata.get("estimator_name")
            or ""
        ).strip()
        or None
    )
    raw_artifact_family = _optional_scope_text(
        "artifact_family", (state.params, candidate_metadata, metadata)
    )
    artifact_family = (
        None
        if raw_artifact_family is None
        else normalize_phase2_artifact_family(
            raw_artifact_family,
            estimator_name=estimator_name,
            query_type=query_type,
        )
    )
    raw_claim_mode = _optional_scope_text(
        "claim_mode", (state.params, candidate_metadata, metadata), lowercase=True
    )
    claim_mode = None if raw_claim_mode is None else _parse_policy_claim_mode(raw_claim_mode)
    readiness_target = (
        str(
            state.params.get("readiness_target")
            or candidate_metadata.get("readiness_target")
            or metadata.get("readiness_target")
            or ""
        ).strip()
        or None
    )
    return {
        "artifact_family": artifact_family,
        "claim_mode": claim_mode,
        "query_type": query_type,
        "estimator_name": estimator_name,
        "readiness_target": readiness_target,
    }


def _expected_policy_loop_id(state: ExperimentState) -> str:
    return str(state.params.get("policy_loop_id") or state.run_id)


def _load_benchmark_if_present(
    ctx: ExecutionContext,
    ref: ArtifactRef | None,
) -> BenchmarkEvaluation | None:
    if ref is None:
        return None
    return load_benchmark_evaluation(ctx, ref)


def prepare_runtime_benchmark_evidence(session: _RuntimeSession) -> None:
    """Register supporting benchmark evidence and persist the promotion bundle."""
    owner = session.owner
    ctx = session.ctx
    state = session.state
    registry_root = _require_policy_runtime_registry_root(ctx.store)
    benchmark_registry = session.benchmark_registry
    benchmark_scope = session.benchmark_scope
    selection_evaluation = session.selection_evaluation
    selection_ref = session.selection_ref
    candidate_ref = session.candidate_ref
    selection_vector_ref = session.selection_vector_ref
    assert benchmark_registry is not None
    assert selection_evaluation is not None
    assert selection_ref is not None
    assert selection_vector_ref is not None

    existing_evidence = owner._load_existing_promotion_evidence(ctx, state)
    session.existing_evidence = existing_evidence
    owner._register_runtime_benchmark_inputs(
        ctx,
        state,
        benchmark_registry=benchmark_registry,
        evidence_bundle=existing_evidence,
        family=benchmark_scope["artifact_family"],
        claim_mode=benchmark_scope["claim_mode"],
        query_type=benchmark_scope["query_type"],
        estimator_name=benchmark_scope["estimator_name"],
        readiness_target=benchmark_scope["readiness_target"],
    )
    phase_d4_rotating_refs, phase_d4_stress_refs, phase_d4_warnings = (
        owner._run_and_register_phase_d4_challenge_suites(
            ctx,
            state,
            benchmark_registry=benchmark_registry,
            candidate_ref=candidate_ref,
            selection_evaluation=selection_evaluation,
            benchmark_scope=benchmark_scope,
            artifacts_index=session.runtime_artifacts_index,
        )
    )
    session.phase_d4_rotating_refs = phase_d4_rotating_refs
    session.phase_d4_stress_refs = phase_d4_stress_refs
    session.phase_d4_warnings = phase_d4_warnings
    if phase_d4_rotating_refs:
        session.phase_d4_suite_ids = [
            evaluation.suite_id
            for evaluation in (
                owner._load_benchmark_if_present(ctx, ref) for ref in phase_d4_rotating_refs
            )
            if evaluation is not None
        ]
    artifact_family = benchmark_scope["artifact_family"]
    claim_mode = benchmark_scope["claim_mode"]
    if artifact_family is not None and claim_mode is not None:
        frontier_benchmark_bundle = benchmark_registry.resolve_family_bundle(
            family=artifact_family,
            claim_mode=claim_mode,
            run_id=state.run_id,
            loop_id=owner._expected_policy_loop_id(state),
            query_type=benchmark_scope["query_type"],
            estimator_name=benchmark_scope["estimator_name"],
            readiness_target=benchmark_scope["readiness_target"],
        )
        hidden_holdout_ref = frontier_benchmark_bundle.hidden_holdout_evaluation_ref
        rotating_refs = owner._dedupe_phase_d4_rotating_refs(
            ctx,
            list(frontier_benchmark_bundle.rotating_challenge_evaluation_refs),
        )
    else:
        hidden_holdout_ref = None
        rotating_refs = []
    hidden_holdout = owner._load_benchmark_if_present(ctx, hidden_holdout_ref)
    rotating_holdouts = [
        item
        for item in (owner._load_benchmark_if_present(ctx, ref) for ref in rotating_refs)
        if item is not None
    ]
    calibration_ref = owner._ensure_calibration_report(ctx, state)
    platform_meta_ref = owner._ensure_platform_meta_report(
        ctx,
        state,
        selection_ref=selection_ref,
        selection_evaluation=selection_evaluation,
        hidden_holdout=hidden_holdout,
        rotating_holdouts=rotating_holdouts,
        existing_evidence=existing_evidence,
    )
    if platform_meta_ref is not None:
        benchmark_registry.record(
            BenchmarkSplit.ADVERSARIAL.value,
            platform_meta_ref,
            run_id=state.run_id,
            family=benchmark_scope["artifact_family"],
            query_type=benchmark_scope["query_type"],
            estimator_name=benchmark_scope["estimator_name"],
            readiness_target=benchmark_scope["readiness_target"],
            produced_by_run_id=state.run_id,
            artifact_kind="scientist.platform_meta_evaluation_report",
            metadata={
                "artifact_type": "platform_meta_evaluation",
                "artifact_family": benchmark_scope["artifact_family"],
                "claim_mode": benchmark_scope["claim_mode"],
            },
        )
    supplemental_stress_report_refs: list[ArtifactRef] = []
    supplemental_stress_reports: list[StressTestReport] = []
    for stress_ref in phase_d4_stress_refs:
        stress_report = owner._load_stress_test_report(ctx, stress_ref)
        if stress_report is not None:
            supplemental_stress_report_refs.append(stress_ref)
            supplemental_stress_reports.append(stress_report)
    stress_report_ref = owner._ensure_stress_test_report(
        ctx,
        state,
        evaluation_vector=session.selection_vector,
        supplemental_reports=supplemental_stress_reports,
        supplemental_report_refs=supplemental_stress_report_refs,
        phase_d4_suite_ids=session.phase_d4_suite_ids,
        expected_candidate_ref=session.candidate_ref,
    )
    if stress_report_ref is not None:
        benchmark_registry.record(
            BenchmarkSplit.ADVERSARIAL.value,
            stress_report_ref,
            run_id=state.run_id,
            family=benchmark_scope["artifact_family"],
            query_type=benchmark_scope["query_type"],
            estimator_name=benchmark_scope["estimator_name"],
            readiness_target=benchmark_scope["readiness_target"],
            produced_by_run_id=state.run_id,
            artifact_kind="scientist.stress_test_report",
            metadata={
                "artifact_type": "stress_test_report",
                "artifact_family": benchmark_scope["artifact_family"],
                "claim_mode": benchmark_scope["claim_mode"],
            },
        )
    replay_bundle_ref = owner._resolve_replay_bundle_ref(state, existing_evidence)
    replay_verification_ref = (
        existing_evidence.replay_verification_ref if existing_evidence is not None else None
    )
    if replay_verification_ref is None and replay_bundle_ref is not None:
        replay_verification_ref = owner.verify_and_persist_replay_bundle(
            ctx.store,
            run_id=state.run_id,
            replay_bundle_ref=replay_bundle_ref,
            candidate_ref=candidate_ref,
            evaluation_ref=selection_vector_ref,
            registry=owner.ReplayRegistry(registry_root / "search_registry" / "replay_registry"),
        )
    governance_ref = (
        existing_evidence.governance_report_ref
        if existing_evidence is not None and existing_evidence.governance_report_ref is not None
        else state.reports_index.get("governance_report_ref")
    )
    calibration_report = owner.load_funnel_calibration_report(ctx.store, calibration_ref)
    degradation_mode = owner._resolve_degradation_mode(
        state,
        hidden_holdout_ref=hidden_holdout_ref,
        replay_bundle_ref=replay_bundle_ref,
        governance_ref=governance_ref,
        calibration_report=calibration_report,
    )
    if artifact_family is not None and claim_mode is not None:
        missing_benchmark_requirements = benchmark_registry.require_promotion_evidence(
            family=artifact_family,
            claim_mode=claim_mode,
            run_id=state.run_id,
            loop_id=owner._expected_policy_loop_id(state),
            query_type=benchmark_scope["query_type"],
            estimator_name=benchmark_scope["estimator_name"],
            readiness_target=benchmark_scope["readiness_target"],
        )
    else:
        missing_benchmark_requirements = [
            name
            for name, value in (
                ("artifact_family", artifact_family),
                ("claim_mode", claim_mode),
            )
            if value is None
        ]
    if missing_benchmark_requirements and degradation_mode == "normal":
        degradation_mode = "no_promotion"
    evidence_bundle = PromotionEvidenceBundle(
        run_id=state.run_id,
        produced_by_run_id=state.run_id,
        candidate_ref=candidate_ref,
        evaluation_ref=None,
        selection_evaluation_ref=selection_ref,
        hidden_holdout_evaluation_ref=hidden_holdout_ref,
        rotating_challenge_evaluation_refs=rotating_refs,
        adversarial_meta_evaluation_ref=platform_meta_ref,
        replay_bundle_ref=replay_bundle_ref,
        replay_verification_ref=replay_verification_ref,
        calibration_report_ref=calibration_ref,
        governance_report_ref=governance_ref,
        stress_test_report_ref=stress_report_ref,
        metadata={
            "workflow_id": str(state.params.get("workflow_id") or ""),
            "cutover_mode": "hard_cutover",
            "scheduler_mode": "predictive",
            "degradation_mode": degradation_mode,
            "artifact_family": benchmark_scope["artifact_family"],
            "claim_mode": benchmark_scope["claim_mode"],
            "query_type": benchmark_scope["query_type"],
            "estimator_name": benchmark_scope["estimator_name"],
            "readiness_target": benchmark_scope["readiness_target"],
            "missing_benchmark_requirements": list(missing_benchmark_requirements),
            "evidence_source_statuses": dict(session.runtime_source_statuses),
            "phase_d4_suite_ids": list(session.phase_d4_suite_ids),
            "phase_d4_warnings": list(session.phase_d4_warnings),
        },
    )
    source_evidence_ref = state.inputs.get(INPUT_PROMOTION_EVIDENCE_BUNDLE_REF)
    if source_evidence_ref is None:
        source_evidence_ref = state.artifacts_index.get(ARTIFACT_PROMOTION_EVIDENCE_BUNDLE_REF)
    evidence_ref = owner.persist_promotion_evidence_bundle(
        ctx.store,
        evidence_bundle,
        inputs=[
            input_ref_from_artifact_ref(candidate_ref, role="candidate"),
            input_ref_from_artifact_ref(selection_vector_ref, role="policy_evaluation"),
            input_ref_from_artifact_ref(selection_ref, role="selection_evaluation"),
            *(
                [
                    input_ref_from_artifact_ref(
                        source_evidence_ref, role="source_promotion_evidence_bundle"
                    )
                ]
                if source_evidence_ref is not None
                else []
            ),
        ],
    )
    session.hidden_holdout_ref = hidden_holdout_ref
    session.rotating_refs = rotating_refs
    session.hidden_holdout = hidden_holdout
    session.calibration_ref = calibration_ref
    session.calibration_report = calibration_report
    session.platform_meta_ref = platform_meta_ref
    session.stress_report_ref = stress_report_ref
    session.replay_bundle_ref = replay_bundle_ref
    session.replay_verification_ref = replay_verification_ref
    session.governance_ref = governance_ref
    session.degradation_mode = degradation_mode
    session.evidence_bundle = evidence_bundle
    session.evidence_ref = evidence_ref


def _resolve_runtime_transfer_context(
    state: ExperimentState,
    candidate: PolicyCandidateSchema,
) -> dict[str, Any]:
    """Resolve producer declarations against the runtime run and live access scope.

    Candidate metadata can carry a tenant declaration for compatibility, but it
    never authenticates that identity. Only pass it as a declaration when the
    key is present: an absent label is not an empty tenant identity, and a
    present malformed label must remain a refusal.
    """
    metadata = candidate.metadata
    resolved = resolve_transfer_context(
        candidate=candidate,
        context=state.params,
        run_id=state.run_id,
        tenant_hash=metadata.get("tenant_hash"),
        tenant_hash_is_explicit="tenant_hash" in metadata,
    )
    return resolved.model_dump(mode="json", exclude_none=False)


def build_runtime_funnel_context(session: _RuntimeSession) -> None:
    """Build the existing promotion context and attach the scheduler's current projection."""
    owner = session.owner
    ctx = session.ctx
    state = session.state
    registry_root = _require_policy_runtime_registry_root(ctx.store)
    candidate = session.candidate
    evidence_bundle = session.evidence_bundle
    evidence_ref = session.evidence_ref
    selection_vector_ref = session.selection_vector_ref
    selection_ref = session.selection_ref
    calibration_report = session.calibration_report
    assert selection_vector_ref is not None
    assert selection_ref is not None
    assert evidence_bundle is not None
    assert evidence_ref is not None
    transfer_context = _resolve_runtime_transfer_context(state, candidate)
    funnel_context = {
        "store": owner.resolve_actionable_store(store=ctx.store),
        "transfer_context": transfer_context,
        "policy_candidate_schema": candidate,
        "policy_candidate_ref": session.candidate_ref,
        "welfare_bundle_ref": owner.maybe_artifact_ref(
            state.artifacts_index.get(ARTIFACT_WELFARE_BUNDLE_REF)
        ),
        "simulation_metrics": session.simulation_metrics,
        "uncertainty_envelope": session.uncertainty_envelope,
        "uncertainty_basis_ref": owner.maybe_artifact_ref(
            state.params.get("uncertainty_basis_ref")
        ),
        "selection_evaluation": session.selection_evaluation,
        "hidden_holdout_evaluation": session.hidden_holdout,
        "benchmark_registry": session.benchmark_registry,
        "platform_meta_evaluation_report": (
            None
            if session.platform_meta_ref is None
            else owner.load_platform_meta_evaluation_report(ctx.store, session.platform_meta_ref)
        ),
        "governance_report": session.governance_report,
        "stress_test_report": owner._load_stress_test_report(ctx, session.stress_report_ref),
        "stress_test_report_ref": session.stress_report_ref,
        "causal_effect_report": session.causal_report,
        "distributional_report": session.distributional_report,
        "cross_graph_profile": session.cross_graph_profile,
        "correlation_metrics": owner._resolve_runtime_correlation_metrics(
            state,
            calibration_report,
        ),
        "funnel_degradation_mode": session.degradation_mode,
        # Ephemeral runtime permission; the owner callback rechecks the
        # evidence/candidate/run binding immediately before the write path.
        "promotion_write_allowed": session.degradation_mode == "normal",
        "promotion_evidence_bundle_ref": evidence_ref,
        "calibration_report_ref": session.calibration_ref,
        "calibration_report": calibration_report,
        "pinned_input_signature": session.input_signature,
        "lesson_registry": owner.LessonRegistry(
            root=registry_root / "search_registry" / "lessons",
            store=ctx.store,
        ),
    }
    predictive_voi = owner.load_predictive_voi_scheduler(
        ctx,
        transfer_context=transfer_context,
    )
    predictive_voi.update_calibration_state(
        {
            **owner._resolve_runtime_correlation_metrics(state, calibration_report),
            "routing_mode": session.degradation_mode,
        }
    )
    evidence_bundle = evidence_bundle.model_copy(
        update={
            "metadata": {
                **evidence_bundle.metadata,
                "voi_model_status": [
                    status.model_dump(mode="json") for status in predictive_voi.model_status()
                ],
            }
        }
    )
    evidence_ref = owner.persist_promotion_evidence_bundle(
        ctx.store,
        evidence_bundle,
        inputs=[
            input_ref_from_artifact_ref(session.candidate_ref, role="candidate"),
            input_ref_from_artifact_ref(
                selection_vector_ref,
                role="policy_evaluation",
            ),
            input_ref_from_artifact_ref(
                selection_ref,
                role="selection_evaluation",
            ),
            input_ref_from_artifact_ref(
                evidence_ref,
                role="source_promotion_evidence_bundle",
            ),
        ],
    )
    funnel_context["promotion_evidence_bundle_ref"] = evidence_ref
    session.transfer_context = transfer_context
    session.funnel_context = funnel_context
    session.predictive_voi = predictive_voi
    session.evidence_bundle = evidence_bundle
    session.evidence_ref = evidence_ref
