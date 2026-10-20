from __future__ import annotations

import logging
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.common.canonical_profile import CanonicalProfileRefusalError
from polisyos.core.artifacts import (
    ArtifactStore,
    CoreJSONArtifactStore,
    VerificationReport,
    artifact_manifest_profile_sha256,
    ensure_ir_artifact_store,
    load_core_json_artifact,
)
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactManifest, ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.security import (
    AccessScope,
    reset_current_access_scope,
    set_current_access_scope,
)
from polisyos.ir.analytics.cross_graph import (
    CrossGraphEvidenceProfile,
    CrossGraphEvidenceSummary,
    EvidenceSourceKind,
    EvidenceSourceState,
    EvidenceSourceStatus,
)
from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.trinity import TrinityBundle
from polisyos.runtime.http.resilience import guard_runtime_cas
from polisyos.scientist.evidence.sources import EvidenceSourcesConfig
from polisyos.scientist.methods.autotune.models import (
    BenchmarkEvaluation,
    BenchmarkSplit,
    persist_benchmark_evaluation,
)
from polisyos.scientist.methods.backtesting.adversarial import (
    build_challenge_suite_result,
)
from polisyos.scientist.methods.doe.stress_report import (
    StressOutcomeBasis,
    VulnerabilityType,
)
from polisyos.scientist.methods.search.benchmark_registry import BenchmarkRegistry
from polisyos.scientist.methods.search.funnel.level6_promotion import Level6PromotionStage
from polisyos.scientist.methods.search.objective import ObjectiveScoreStatus
from polisyos.scientist.methods.search.promotion_evidence import (
    PromotionEvidenceBundle,
    persist_promotion_evidence_bundle,
)
from polisyos.scientist.methods.search.transfer_context import (
    TransferContext,
    TransferScopeRefusalReason,
    TransferScopeRefusedError,
    TransferTenantScopeStatus,
    anonymize_tenant_id,
    resolve_transfer_context,
)
from polisyos.scientist.nodes.builtins.decide import (
    policy_blueprint_runtime_benchmarks,
    run_policy_blueprint_runtime,
)
from polisyos.scientist.nodes.builtins.decide.policy_blueprint_runtime_benchmarks import (
    _maybe_register_benchmark_evaluation,
    _register_runtime_benchmark_inputs,
    _resolve_benchmark_scope,
    _resolve_policy_runtime_source_statuses,
    _resolve_runtime_transfer_context,
    _run_and_register_phase_d4_challenge_suites,
    build_runtime_funnel_context,
    prepare_runtime_benchmark_evidence,
)
from polisyos.scientist.nodes.builtins.decide.policy_blueprint_runtime_engine import (
    _RuntimeSession,
    prepare_runtime_session,
)
from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
    ensure_policy_candidate_ref,
    persist_policy_evaluation_vector_to_store,
    run_promotion_with_evidence,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.policy_design.objectives import (
    ObjectiveChannelValue,
    ObjectiveDirection,
    ObjectiveKind,
    PolicyEvaluationVector,
)
from polisyos.scientist.policy_design.schema import (
    PolicyCandidateSchema,
    persist_policy_candidate_schema,
)


def _candidate() -> PolicyCandidateSchema:
    return PolicyCandidateSchema.from_trinity_bundle(
        TrinityBundle(
            problem_frame=ProblemFrame(
                problem_id="problem_benchmark_scope",
                domain=ProblemDomain.FISCAL,
            ),
            policy_spec=PolicySpec(policy_id="policy_benchmark_scope"),
            model_spec=ModelSpec(
                model_id="model_benchmark_scope",
                data_snapshot_ref="sha256:" + "3" * 64,
            ),
        ),
        candidate_id="candidate_benchmark_scope",
    )


def _context(tmp_path: Path, run_id: str) -> ExecutionContext:
    store = FileSystemCAS(tmp_path / run_id)
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.core.run.context import RunContext

    registry_ref = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_ref, run_id=run_id)
    return ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger(f"test.{run_id}"),
    )


def test_runtime_transfer_context_resolves_absence_for_search_consumer() -> None:
    run_id = "run_benchmark_transfer_scope"
    candidate = _candidate()
    emitted = _resolve_runtime_transfer_context(ExperimentState(run_id=run_id), candidate)

    assert emitted["task_family"] == "policy"
    assert emitted["domain"] == "fiscal"
    assert emitted["run_id"] == run_id
    assert emitted["tenant_hash"] is None
    assert emitted["tenant_scope_status"] == "unknown"

    consumed = resolve_transfer_context(
        candidate=candidate,
        context={"transfer_context": emitted},
    )
    assert consumed.domain == "fiscal"
    assert consumed.run_id == run_id
    assert consumed.tenant_hash is None
    assert consumed.tenant_scope_status.value == "unknown"


@pytest.mark.parametrize(
    ("params", "candidate_metadata"),
    [
        (
            {
                "transfer_context": {
                    "task_family": "policy",
                    "domain": "fiscal",
                    "run_id": "run_benchmark_transfer_scope",
                    "tenant_hash": "",
                }
            },
            {},
        ),
        ({"transfer_context": {}}, {}),
        (
            {
                "policy_request_domain": "fiscal",
                "transfer_context": {
                    "task_family": "policy",
                    "domain": "labor",
                    "run_id": "run_benchmark_transfer_scope",
                },
            },
            {},
        ),
        ({}, {"tenant_hash": ""}),
        ({"source_run_id": "origin_run"}, {}),
        (
            {
                "transfer_context": {
                    "task_family": "policy",
                    "domain": "fiscal",
                    "run_id": "other_runtime_run",
                }
            },
            {},
        ),
    ],
)
def test_runtime_transfer_context_refuses_present_empty_or_conflicting_scope(
    params: dict[str, object],
    candidate_metadata: dict[str, object],
) -> None:
    run_id = "run_benchmark_transfer_scope"
    candidate = _candidate().model_copy(update={"metadata": candidate_metadata})

    with pytest.raises(TransferScopeRefusedError) as captured:
        _resolve_runtime_transfer_context(
            ExperimentState(run_id=run_id, params=params),
            candidate,
        )

    assert captured.value.refusals[0].reason is TransferScopeRefusalReason.INVALID_REQUEST_SCOPE


def test_runtime_transfer_context_refuses_sibling_scope_from_another_run() -> None:
    sibling_context = TransferContext(
        task_family="policy",
        domain="fiscal",
        run_id="sibling_producer_run",
        tenant_scope_status=TransferTenantScopeStatus.UNKNOWN,
    )

    with pytest.raises(TransferScopeRefusedError):
        _resolve_runtime_transfer_context(
            ExperimentState(
                run_id="runtime_run",
                params={"transfer_context": sibling_context},
            ),
            _candidate(),
        )


def test_runtime_transfer_context_uses_live_access_scope_and_rejects_candidate_mismatch() -> None:
    access = AccessScope.for_service(
        tenant_id="benchmark-tenant-a",
        cell_id=None,
        spiffe_id="spiffe://test/policy-runtime",
    )
    token = set_current_access_scope(access)
    try:
        run_id = "run_benchmark_transfer_scope"
        emitted = _resolve_runtime_transfer_context(
            ExperimentState(run_id=run_id),
            _candidate(),
        )
        assert emitted["tenant_hash"] == anonymize_tenant_id("benchmark-tenant-a")
        assert emitted["tenant_scope_status"] == "authenticated"

        mismatched = _candidate().model_copy(
            update={"metadata": {"tenant_hash": anonymize_tenant_id("benchmark-tenant-b")}}
        )
        with pytest.raises(TransferScopeRefusedError) as captured:
            _resolve_runtime_transfer_context(ExperimentState(run_id=run_id), mismatched)
        assert (
            captured.value.refusals[0].reason
            is TransferScopeRefusalReason.AUTHENTICATED_SCOPE_MISMATCH
        )
    finally:
        reset_current_access_scope(token)


def test_runtime_transfer_context_preserves_explicit_declared_unscoped_status() -> None:
    run_id = "run_benchmark_transfer_scope"
    emitted = _resolve_runtime_transfer_context(
        ExperimentState(
            run_id=run_id,
            params={
                "transfer_context": {
                    "task_family": "policy",
                    "domain": "fiscal",
                    "run_id": run_id,
                    "tenant_scope_status": "declared_unscoped",
                }
            },
        ),
        _candidate(),
    )

    assert emitted["tenant_hash"] is None
    assert emitted["tenant_scope_status"] == "declared_unscoped"


def test_runtime_candidate_bridge_writes_selected_owner_schema_and_body(tmp_path: Path) -> None:
    ctx = _context(tmp_path, "candidate_bridge")
    candidate = _candidate()
    state = ExperimentState(run_id="candidate_bridge")

    ref = ensure_policy_candidate_ref(ctx, state, candidate, None)

    assert ref.kind == PolicyCandidateSchema.ARTIFACT_KIND
    assert ref.media_type == PolicyCandidateSchema.ARTIFACT_MEDIA_TYPE
    assert ref.manifest_profile_sha256 is not None
    manifest = ctx.store.get_manifest(ref)
    assert artifact_manifest_profile_sha256(manifest) == ref.manifest_profile_sha256
    assert manifest.artifact_schema is not None
    assert manifest.artifact_schema.name == PolicyCandidateSchema.ARTIFACT_SCHEMA_NAME
    assert manifest.artifact_schema.version == PolicyCandidateSchema.ARTIFACT_SCHEMA_VERSION
    persisted = PolicyCandidateSchema.model_validate(
        load_core_json_artifact(ctx.store, ref, manifest_profile_sha256=ref.manifest_profile_sha256)
    )
    assert persisted == candidate


def test_runtime_candidate_bridge_preserves_legacy_candidate_only_ref(tmp_path: Path) -> None:
    ctx = _context(tmp_path, "candidate_bridge_legacy")
    candidate = _candidate()
    state = ExperimentState(run_id="candidate_bridge_legacy")
    legacy_ref = ctx.store.put_json(
        candidate,
        PutOptions(
            kind="scientist.policy_candidate_schema",
            media_type="application/json",
            schema=SchemaInfo(name="candidate", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )

    result = ensure_policy_candidate_ref(ctx, state, candidate, legacy_ref)

    assert result == legacy_ref
    assert result.kind == "scientist.policy_candidate_schema"


def test_runtime_candidate_bridge_binds_canonical_candidate_to_selected_trinity_source(
    tmp_path: Path,
) -> None:
    ctx = _context(tmp_path, "candidate_bridge_trinity")
    source = _candidate().trinity_bundle
    source_ref = ctx.store.put_json(
        source,
        PutOptions(
            kind=source.ARTIFACT_KIND,
            media_type=source.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=source.ARTIFACT_SCHEMA_NAME, version=source.ARTIFACT_SCHEMA_VERSION
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    candidate = PolicyCandidateSchema.from_trinity_bundle(
        source, candidate_id="candidate_trinity_bridge"
    )
    state = ExperimentState(
        run_id="candidate_bridge_trinity",
        inputs={"trinity_bundle_ref": source_ref},
    )

    ref = ensure_policy_candidate_ref(ctx, state, candidate, source_ref)

    assert ref.kind == PolicyCandidateSchema.ARTIFACT_KIND
    assert ref.manifest_profile_sha256 is not None
    manifest = ctx.store.get_manifest(ref)
    assert any(
        item.role == "candidate_source"
        and item.artifact_id == source_ref.artifact_id
        and item.manifest_profile_sha256 == source_ref.manifest_profile_sha256
        for item in manifest.inputs
    )


def _register(
    *,
    ctx: ExecutionContext,
    registry: BenchmarkRegistry,
    ref,
    run_id: str,
    expected_loop_id: str,
) -> None:
    _maybe_register_benchmark_evaluation(
        ctx,
        benchmark_registry=registry,
        ref=ref,
        split_type=BenchmarkSplit.HIDDEN_HOLDOUT,
        run_id=run_id,
        expected_loop_id=expected_loop_id,
        family="causal_core",
        claim_mode="estimation",
        query_type="policy",
        estimator_name="matching",
        readiness_target="release",
    )


def test_source_statuses_are_per_source_and_choose_the_configured_benchmark_report(
    tmp_path: Path,
) -> None:
    benchmark_report = tmp_path / "benchmark-report.json"
    benchmark_report.write_text('{"suite":"native"}', encoding="utf-8")
    missing_suite = tmp_path / "missing-suite.json"
    missing_legal_db = tmp_path / "missing-legal.sqlite"
    supplied_legal_status = EvidenceSourceStatus(
        source=EvidenceSourceKind.LEGAL,
        configured=True,
        status=EvidenceSourceState.QUERY_FAILED,
        path=str(missing_legal_db),
        detail="profile query failed",
    )
    profile = CrossGraphEvidenceProfile(
        summary=CrossGraphEvidenceSummary(),
        source_statuses={EvidenceSourceKind.LEGAL.value: supplied_legal_status},
    )
    sources = EvidenceSourcesConfig(
        legal_db_path=str(missing_legal_db),
        benchmark_suite_path=str(missing_suite),
        benchmark_report_path=str(benchmark_report),
    )

    statuses = _resolve_policy_runtime_source_statuses(
        cross_graph_profile=profile,
        evidence_sources=sources,
    )

    assert statuses[EvidenceSourceKind.LEGAL.value] == EvidenceSourceState.QUERY_FAILED.value
    assert statuses[EvidenceSourceKind.BENCHMARK.value] == EvidenceSourceState.AVAILABLE.value
    assert statuses[EvidenceSourceKind.ACADEMIC.value] == EvidenceSourceState.MISSING_CONFIG.value
    assert supplied_legal_status.status is EvidenceSourceState.QUERY_FAILED
    assert str(benchmark_report) == sources.benchmark_report_path


def test_benchmark_admission_requires_exact_loop_and_split_and_keeps_scope_filters(
    tmp_path: Path,
) -> None:
    ctx = _context(tmp_path, "run_benchmark_admission")
    candidate_ref = persist_policy_candidate_schema(ctx.store, _candidate())
    registry = BenchmarkRegistry(tmp_path / "search_registry" / "benchmarks")
    current_run = "run_current_scope"
    expected_loop = "loop_current_scope"
    accepted = BenchmarkEvaluation(
        loop_id=expected_loop,
        suite_id="native_hidden_holdout",
        candidate_ref=candidate_ref,
        runtime_split_type=BenchmarkSplit.HIDDEN_HOLDOUT,
        holdout_metrics={"policy_value": 0.25},
        sample_counts={BenchmarkSplit.HIDDEN_HOLDOUT.value: 12},
    )
    accepted_ref = persist_benchmark_evaluation(ctx.store, accepted)

    _register(
        ctx=ctx,
        registry=registry,
        ref=accepted_ref,
        run_id=current_run,
        expected_loop_id=expected_loop,
    )

    assert (
        registry.latest(
            BenchmarkSplit.HIDDEN_HOLDOUT.value,
            run_id=current_run,
            loop_id=expected_loop,
            family="causal_core",
            query_type="policy",
            estimator_name="matching",
            readiness_target="release",
        )
        == accepted_ref
    )
    assert (
        registry.latest(
            BenchmarkSplit.HIDDEN_HOLDOUT.value,
            run_id=current_run,
            loop_id=expected_loop,
            family="other_family",
            query_type="policy",
            estimator_name="matching",
            readiness_target="release",
        )
        is None
    )

    wrong_loop = accepted.model_copy(update={"loop_id": "loop_other"})
    wrong_loop_ref = persist_benchmark_evaluation(ctx.store, wrong_loop)
    _register(
        ctx=ctx,
        registry=registry,
        ref=wrong_loop_ref,
        run_id="run_wrong_loop",
        expected_loop_id=expected_loop,
    )
    assert (
        registry.latest(
            BenchmarkSplit.HIDDEN_HOLDOUT.value,
            run_id="run_wrong_loop",
        )
        is None
    )

    wrong_split = accepted.model_copy(
        update={
            "suite_id": "native_selection",
            "runtime_split_type": BenchmarkSplit.SELECTION,
        }
    )
    wrong_split_ref = persist_benchmark_evaluation(ctx.store, wrong_split)
    _register(
        ctx=ctx,
        registry=registry,
        ref=wrong_split_ref,
        run_id="run_wrong_split",
        expected_loop_id=expected_loop,
    )
    assert (
        registry.latest(
            BenchmarkSplit.HIDDEN_HOLDOUT.value,
            run_id="run_wrong_split",
        )
        is None
    )


def test_runtime_benchmark_refs_refuse_present_malformed_values(tmp_path: Path) -> None:
    ctx = _context(tmp_path, "run_malformed_rotating_refs")
    registry = BenchmarkRegistry(tmp_path / "search_registry" / "benchmarks")

    with pytest.raises(ValueError, match="rotating_challenge_evaluation_refs"):
        _register_runtime_benchmark_inputs(
            ctx,
            ExperimentState(
                run_id="run_malformed_rotating_refs",
                params={"rotating_challenge_evaluation_refs": 17},
            ),
            benchmark_registry=registry,
            evidence_bundle=None,
            family="causal_core",
            query_type="policy",
            estimator_name=None,
            readiness_target=None,
        )

    assert registry._load_snapshot().entries == []


@pytest.mark.parametrize(
    "supplied_value",
    [None, "not-a-list", {}, [{}]],
    ids=["explicit-null", "scalar", "object", "malformed-ref-member"],
)
def test_runtime_benchmark_refs_reject_present_non_list_or_invalid_members(
    tmp_path: Path,
    supplied_value: object,
) -> None:
    ctx = _context(tmp_path, f"run_bad_rotating_refs_{type(supplied_value).__name__}")
    registry = BenchmarkRegistry(tmp_path / "search_registry" / "benchmarks")

    with pytest.raises(ValueError, match="rotating_challenge_evaluation_refs"):
        _register_runtime_benchmark_inputs(
            ctx,
            ExperimentState(
                run_id="run_bad_rotating_refs",
                params={"rotating_challenge_evaluation_refs": supplied_value},
            ),
            benchmark_registry=registry,
            evidence_bundle=None,
            family="causal_core",
            query_type="policy",
            estimator_name=None,
            readiness_target=None,
        )

    assert registry._load_snapshot().entries == []


def test_runtime_benchmark_scope_keeps_unprovided_authority_intent_unresolved() -> None:
    scope = _resolve_benchmark_scope(
        state=ExperimentState(run_id="run_without_benchmark_intent"),
        candidate=_candidate(),
        selection_vector=PolicyEvaluationVector(candidate_id="candidate_without_benchmark_intent"),
    )

    assert scope["artifact_family"] is None
    assert scope["claim_mode"] is None


def test_runtime_benchmark_scope_refuses_malformed_present_family_or_claim_mode() -> None:
    with pytest.raises(ValueError, match="artifact_family"):
        _resolve_benchmark_scope(
            state=ExperimentState(
                run_id="run_bad_benchmark_intent",
                params={"artifact_family": 4},
            ),
            candidate=_candidate(),
            selection_vector=PolicyEvaluationVector(candidate_id="candidate_bad_family"),
        )

    with pytest.raises(ValueError, match="claim_mode"):
        _resolve_benchmark_scope(
            state=ExperimentState(
                run_id="run_bad_benchmark_intent",
                params={"claim_mode": False},
            ),
            candidate=_candidate(),
            selection_vector=PolicyEvaluationVector(candidate_id="candidate_bad_claim_mode"),
        )


def test_phase_d4_missing_optional_stress_report_stays_visible_and_does_not_block_benchmark(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx = _context(tmp_path, "run_phase_d4_without_stress_report")
    candidate = _candidate()
    candidate_ref = ctx.store.put_json(
        candidate,
        PutOptions(
            kind=PolicyCandidateSchema.ARTIFACT_KIND,
            media_type=PolicyCandidateSchema.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=PolicyCandidateSchema.ARTIFACT_SCHEMA_NAME,
                version=PolicyCandidateSchema.ARTIFACT_SCHEMA_VERSION,
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    selection = build_challenge_suite_result(
        suite_id="strategic_gaming_v1",
        suite_version="1.0",
        candidate_ref=candidate_ref,
        loop_id="loop_phase_d4_without_stress_report",
        challenge_family="strategic_gaming",
        case_results=[],
        planned_case_ids=[],
        primary_failure_rate_name="silent_static_fallback_rate",
        vulnerability_type=VulnerabilityType.COMBINATORIAL,
    )
    suite = replace(selection, stress_test_report=None)
    resolved_components = []
    score_resolutions = []
    resolve_components = policy_blueprint_runtime_benchmarks.resolve_stress_score_components

    def _resolve_and_capture(store, components, *, expected_candidate_ref):
        resolved_components.extend(components)
        resolution = resolve_components(
            store,
            components,
            expected_candidate_ref=expected_candidate_ref,
        )
        score_resolutions.append(resolution)
        return resolution

    monkeypatch.setattr(
        policy_blueprint_runtime_benchmarks,
        "run_phase_d4_challenge_suites",
        lambda **_kwargs: ([suite], ()),
    )
    monkeypatch.setattr(
        policy_blueprint_runtime_benchmarks,
        "resolve_stress_score_components",
        _resolve_and_capture,
    )
    registry = BenchmarkRegistry(tmp_path / "search_registry" / "benchmarks")

    benchmark_refs, stress_refs, warnings = _run_and_register_phase_d4_challenge_suites(
        ctx,
        ExperimentState(run_id="run_phase_d4_without_stress_report"),
        benchmark_registry=registry,
        candidate_ref=candidate_ref,
        selection_evaluation=selection.benchmark_evaluation,
        benchmark_scope={
            "artifact_family": "causal_core",
            "claim_mode": "estimation",
            "query_type": "policy",
            "estimator_name": None,
            "readiness_target": None,
        },
        artifacts_index={},
    )

    assert len(benchmark_refs) == 1
    assert stress_refs == []
    assert warnings == ("phase_d4_stress_report_absent:strategic_gaming_v1",)
    assert len(resolved_components) == 1
    assert len(score_resolutions) == 1
    assert score_resolutions[0].status == "not_evaluated"
    assert score_resolutions[0].reason_code == "zero_expected_denominator"
    basis_ref = resolved_components[0].outcome_basis_ref
    assert basis_ref.manifest_profile_sha256 is not None
    basis = StressOutcomeBasis.model_validate(from_canonical_bytes(ctx.store.get_bytes(basis_ref)))
    assert basis.source_id == ("phase_d4:strategic_gaming_v1:loop_phase_d4_without_stress_report")
    assert basis.candidate_ref == candidate_ref
    assert basis.benchmark_evaluation_ref == benchmark_refs[0]
    assert (
        registry.latest(
            BenchmarkSplit.ROTATING_CHALLENGE.value,
            run_id="run_phase_d4_without_stress_report",
            loop_id="loop_phase_d4_without_stress_report",
            family="causal_core",
            query_type="policy",
        )
        == benchmark_refs[0]
    )


def test_runtime_funnel_refuses_sidecar_registry_without_root_capability(tmp_path: Path) -> None:
    original_ctx = _context(tmp_path, "run_rootless_registry")
    candidate = _candidate()
    candidate_ref = persist_policy_candidate_schema(original_ctx.store, candidate)
    rootless_store = ensure_ir_artifact_store(original_ctx.store)
    assert not hasattr(rootless_store, "root")
    ctx = ExecutionContext(
        store=rootless_store,
        run=original_ctx.run,
        logger=original_ctx.logger,
    )
    owner = SimpleNamespace(
        resolve_actionable_store=lambda *, store: store,
        maybe_artifact_ref=lambda _value: None,
        _load_stress_test_report=lambda _ctx, _ref: None,
        _resolve_runtime_correlation_metrics=lambda _state, _report: {},
        LessonRegistry=object,
    )
    session = _RuntimeSession(
        ctx=ctx,
        state=ExperimentState(run_id="run_rootless_registry"),
        owner=owner,
        candidate=candidate,
        candidate_ref=candidate_ref,
        uncertainty_envelope=None,
        governance_report=None,
        causal_report=None,
        distributional_report=None,
        cross_graph_profile=None,
        evidence_sources=EvidenceSourcesConfig(),
        runtime_source_statuses={},
        simulation_metrics={},
        ambiguity_certificate=None,
        ambiguity_certificate_ref=None,
        runtime_backend=None,
        input_signature="",
        selection_vector_ref=candidate_ref,
        selection_ref=candidate_ref,
        evidence_bundle=PromotionEvidenceBundle(
            run_id="run_rootless_registry",
            produced_by_run_id="run_rootless_registry",
            candidate_ref=candidate_ref,
        ),
        evidence_ref=candidate_ref,
    )

    with pytest.raises(ValueError, match="policy_runtime_registry_root_unavailable"):
        build_runtime_funnel_context(session)


def test_runtime_session_refuses_rootless_store_before_resolving_inputs(tmp_path: Path) -> None:
    original_ctx = _context(tmp_path, "run_rootless_prepare_session")
    rootless_ctx = replace(
        original_ctx,
        store=ensure_ir_artifact_store(original_ctx.store),
    )

    with pytest.raises(ValueError, match="policy_runtime_registry_root_unavailable"):
        prepare_runtime_session(
            rootless_ctx,
            ExperimentState(run_id="run_rootless_prepare_session"),
            runtime_request=object(),
            owner=SimpleNamespace(),
        )


def test_runtime_node_refuses_rootless_store_before_resolving_policy_inputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_ctx = _context(tmp_path, "run_rootless_node_entry")
    rootless_ctx = replace(
        original_ctx,
        store=ensure_ir_artifact_store(original_ctx.store),
    )
    monkeypatch.setattr(
        run_policy_blueprint_runtime,
        "resolve_policy_runtime_request",
        lambda *_args: pytest.fail("rootless registry must refuse before input resolution"),
    )

    with pytest.raises(ValueError, match="policy_runtime_registry_root_unavailable"):
        run_policy_blueprint_runtime.RunPolicyBlueprintRuntimeNode().execute(
            rootless_ctx,
            ExperimentState(
                run_id="run_rootless_node_entry",
                params={"policy_mode": True},
            ),
        )


def test_missing_benchmark_intent_caps_runtime_before_level6_promotion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx = _context(tmp_path, "run_missing_benchmark_intent")
    state = ExperimentState(run_id="run_missing_benchmark_intent")
    candidate = _candidate()
    candidate_ref = persist_policy_candidate_schema(ctx.store, candidate)
    selection_vector = PolicyEvaluationVector(candidate_id=candidate.candidate_id)
    selection_vector_ref = persist_policy_evaluation_vector_to_store(
        ctx.store,
        candidate_ref=candidate_ref,
        evaluation_vector=selection_vector,
    )
    selection_evaluation = BenchmarkEvaluation(
        loop_id=state.run_id,
        suite_id="policy_runtime_selection",
        candidate_ref=candidate_ref,
        runtime_split_type=BenchmarkSplit.SELECTION,
        selection_metrics={"policy_value": 0.5},
    )
    selection_ref = persist_benchmark_evaluation(
        ctx.store,
        selection_evaluation,
        return_selected_profile=True,
    )
    registry = BenchmarkRegistry(tmp_path / "search_registry" / "benchmarks")
    monkeypatch.setattr(
        registry,
        "resolve_family_bundle",
        lambda **_kwargs: pytest.fail("unknown benchmark scope must not query a family bundle"),
    )
    monkeypatch.setattr(
        registry,
        "require_promotion_evidence",
        lambda **_kwargs: pytest.fail("unknown benchmark scope must not query promotion evidence"),
    )
    owner = SimpleNamespace(
        _load_existing_promotion_evidence=lambda *_args: None,
        _load_benchmark_if_present=lambda *_args: None,
        _register_runtime_benchmark_inputs=_register_runtime_benchmark_inputs,
        _run_and_register_phase_d4_challenge_suites=lambda *_args, **_kwargs: ([], [], ()),
        _expected_policy_loop_id=lambda current_state: current_state.run_id,
        _ensure_calibration_report=lambda *_args, **_kwargs: None,
        _ensure_platform_meta_report=lambda *_args, **_kwargs: None,
        _ensure_stress_test_report=lambda *_args, **_kwargs: None,
        _resolve_replay_bundle_ref=lambda *_args: None,
        _resolve_degradation_mode=lambda *_args, **_kwargs: "normal",
        load_funnel_calibration_report=lambda *_args: None,
        persist_promotion_evidence_bundle=persist_promotion_evidence_bundle,
    )
    session = _RuntimeSession(
        ctx=ctx,
        state=state,
        owner=owner,
        candidate=candidate,
        candidate_ref=candidate_ref,
        uncertainty_envelope=None,
        governance_report=None,
        causal_report=None,
        distributional_report=None,
        cross_graph_profile=None,
        evidence_sources=EvidenceSourcesConfig(),
        runtime_source_statuses={},
        simulation_metrics={},
        ambiguity_certificate=None,
        ambiguity_certificate_ref=None,
        runtime_backend=None,
        input_signature="",
        selection_vector=selection_vector,
        selection_vector_ref=selection_vector_ref,
        selection_evaluation=selection_evaluation,
        selection_ref=selection_ref,
        benchmark_scope=_resolve_benchmark_scope(
            state=state,
            candidate=candidate,
            selection_vector=selection_vector,
        ),
        benchmark_registry=registry,
    )

    prepare_runtime_benchmark_evidence(session)

    assert session.degradation_mode == "no_promotion"
    assert session.evidence_bundle is not None
    assert session.evidence_bundle.metadata["artifact_family"] is None
    assert session.evidence_bundle.metadata["claim_mode"] is None
    assert "artifact_family" in session.evidence_bundle.metadata["missing_benchmark_requirements"]
    assert "claim_mode" in session.evidence_bundle.metadata["missing_benchmark_requirements"]

    promotion_calls: list[object] = []
    stage = Level6PromotionStage(
        promotion_runner=lambda candidate_payload, context: promotion_calls.append(
            (candidate_payload, context)
        )
    )
    result = stage.evaluate(
        {"candidate_id": candidate.candidate_id},
        {"funnel_degradation_mode": session.degradation_mode},
    )
    assert result.terminal_action == "defer_to_human"
    assert promotion_calls == []


def test_promotion_consumer_refuses_missing_benchmark_scope(tmp_path: Path) -> None:
    ctx = _context(tmp_path, "run_missing_promotion_scope")
    candidate = _candidate()
    candidate_ref = persist_policy_candidate_schema(ctx.store, candidate)
    evidence = PromotionEvidenceBundle(
        run_id="run_missing_promotion_scope",
        produced_by_run_id="run_missing_promotion_scope",
        candidate_ref=candidate_ref,
        metadata={"artifact_family": None, "claim_mode": None},
    )

    with pytest.raises(ValueError, match="promotion_benchmark_scope_unavailable"):
        run_promotion_with_evidence(
            ctx=ctx,
            state=ExperimentState(run_id="run_missing_promotion_scope"),
            candidate=candidate,
            candidate_ref=candidate_ref,
            evaluation_vector=PolicyEvaluationVector(candidate_id=candidate.candidate_id),
            evidence_bundle=evidence,
        )


def test_policy_runtime_selection_returns_selected_view_to_fresh_promotion_consumer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Carry a source-bound selection result through CAS to fresh PBE readback."""
    from polisyos.core.artifacts import input_ref_from_artifact_ref
    from polisyos.scientist.methods.search.promotion_evidence import (
        _PolicyRuntimeSelectionSourceBasis,
        load_promotion_evidence_bundle,
    )
    from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
        PolicyRuntimeEvaluationArtifact,
        PolicyRuntimeProvenance,
        ensure_policy_candidate_ref,
    )

    run_id = "run_policy_runtime_selected_selection"
    ctx = _context(tmp_path, run_id)
    candidate = _candidate()
    state = ExperimentState(run_id=run_id)
    candidate_ref = ensure_policy_candidate_ref(ctx, state, candidate, None)
    assert candidate_ref.manifest_profile_sha256 is not None

    runtime_invocation = {
        "evaluation_attempt_id": "attempt:source-bound-selection-fixture",
        "requested_draw_count": 0,
        "requested_draw_source": "test_fixture",
        "effective_estimation_config_sha256": None,
    }
    source_results = {
        "objective_channels": {"policy_value": 0.2},
        "metric_units": {"channel:primary:policy_value": "fixture-score-unit"},
        "feasible": True,
        "blocking_reasons": [],
        "bootstrap": dict(runtime_invocation),
    }
    selection_vector = PolicyEvaluationVector(
        candidate_id=candidate.candidate_id,
        primary={
            "policy_value": ObjectiveChannelValue(
                name="policy_value",
                kind=ObjectiveKind.PRIMARY,
                value=0.2,
                direction=ObjectiveDirection.MAXIMIZE,
                expected_unit="fixture-score-unit",
            )
        },
        metadata={"policy_runtime_invocation": runtime_invocation},
    ).with_runtime_score_assessment(runtime_invocation)
    selection_vector = selection_vector.with_score_source_results(source_results)
    assert selection_vector.score_assessment is not None
    assert selection_vector.score_assessment.status is ObjectiveScoreStatus.AVAILABLE
    synthetic_artifact = PolicyRuntimeEvaluationArtifact(
        simulation_metrics={"policy_value": 0.2},
        simulation_results=source_results,
        evaluation_vector=selection_vector,
        fidelity="selection",
        provenance=PolicyRuntimeProvenance(
            backend_kind="synthetic_transport_fixture",
            fidelity_mode="selection",
            promotable_source=False,
        ),
    )
    monkeypatch.setattr(
        run_policy_blueprint_runtime,
        "ProductionPolicyEvaluationBackend",
        lambda **_kwargs: SimpleNamespace(),
    )
    monkeypatch.setattr(
        run_policy_blueprint_runtime,
        "_world_model_record_from_state",
        lambda _state: None,
    )
    monkeypatch.setattr(
        run_policy_blueprint_runtime,
        "policy_runtime_input_signature",
        lambda **_kwargs: "synthetic-input-signature",
    )
    monkeypatch.setattr(
        run_policy_blueprint_runtime,
        "build_policy_runtime_evaluation",
        lambda _candidate, **_kwargs: synthetic_artifact,
    )
    monkeypatch.setattr(
        run_policy_blueprint_runtime,
        "_resolve_existing_strategic_output",
        lambda _state: SimpleNamespace(
            strategic_scm_ref=None,
            strategic_response_bundle_ref=None,
            strategic_response_summary=None,
        ),
    )
    monkeypatch.setattr(
        run_policy_blueprint_runtime,
        "_build_runtime_abstraction_metadata",
        lambda _ctx, *, artifacts_index: {},
    )

    session = prepare_runtime_session(
        ctx,
        state,
        runtime_request=SimpleNamespace(
            candidate=candidate,
            candidate_ref=candidate_ref,
            cross_graph_profile=None,
            evidence_sources=EvidenceSourcesConfig(),
            simulation_metrics={},
            uncertainty_envelope=None,
            distributional_report=None,
            causal_report=None,
            governance_report=None,
            ambiguity_certificate=None,
            ambiguity_certificate_ref=None,
        ),
        owner=run_policy_blueprint_runtime,
    )
    assert session.selection_ref is not None
    assert session.selection_evaluation is not None
    assert session.selection_ref.manifest_profile_sha256 is not None

    selection_manifest = ctx.store.get_manifest(session.selection_ref)
    candidate_edge = next(item for item in selection_manifest.inputs if item.role == "candidate")
    assert candidate_edge == input_ref_from_artifact_ref(candidate_ref, role="candidate")
    assert candidate_edge.manifest_profile_sha256 == candidate_ref.manifest_profile_sha256

    bundle = PromotionEvidenceBundle(
        run_id=run_id,
        produced_by_run_id=run_id,
        candidate_ref=candidate_ref,
        selection_evaluation_ref=session.selection_ref,
    )
    bundle_ref = persist_promotion_evidence_bundle(ctx.store, bundle)
    fresh_bundle = load_promotion_evidence_bundle(ctx.store, bundle_ref)
    source_basis = _PolicyRuntimeSelectionSourceBasis(
        expected_evaluation=session.selection_evaluation,
    )
    fresh_bundle.assert_runtime_compatible(
        run_id=run_id,
        store=ctx.store,
        expected_loop_id=run_id,
        source_basis_by_role={"selection_evaluation_ref": source_basis},
    )
    bundle_manifest = ctx.store.get_manifest(bundle_ref)
    selection_bundle_edge = next(
        item for item in bundle_manifest.inputs if item.role == "selection_evaluation"
    )
    assert selection_bundle_edge == input_ref_from_artifact_ref(
        session.selection_ref,
        role="selection_evaluation",
    )

    # The generic helper retains its default: a policy-runtime evaluation requested without
    # selected return remains profileless even though its candidate edge is selected.
    profileless_evaluation = session.selection_evaluation.model_copy(
        update={"metadata": {**session.selection_evaluation.metadata, "profileless_control": True}}
    )
    profileless_ref = persist_benchmark_evaluation(
        ctx.store,
        profileless_evaluation,
        inputs=[input_ref_from_artifact_ref(candidate_ref, role="candidate")],
    )
    assert profileless_ref.manifest_profile_sha256 is None
    profileless_manifest = ctx.store.get_manifest(profileless_ref)
    profileless_candidate_edge = next(
        item for item in profileless_manifest.inputs if item.role == "candidate"
    )
    assert profileless_candidate_edge == input_ref_from_artifact_ref(
        candidate_ref,
        role="candidate",
    )
    profileless_bundle = bundle.model_copy(update={"selection_evaluation_ref": profileless_ref})
    with pytest.raises(ValueError, match="requires a selected manifest profile"):
        profileless_bundle.assert_runtime_compatible(
            run_id=run_id,
            store=ctx.store,
            expected_loop_id=run_id,
            source_basis_by_role={"selection_evaluation_ref": source_basis},
        )


class _OpaqueArtifactStoreWithoutRawManifestReader:
    """Base ArtifactStore facade that deliberately lacks the Core raw sidecar reader."""

    def __init__(self, delegate: ArtifactStore) -> None:
        self._delegate = delegate
        self.calls: list[str] = []

    def has(self, artifact_id: ArtifactID | ArtifactRef) -> bool:
        self.calls.append("has")
        return self._delegate.has(artifact_id)

    def get_bytes(self, artifact_id: ArtifactID | ArtifactRef) -> bytes:
        self.calls.append("get_bytes")
        return self._delegate.get_bytes(artifact_id)

    def get_manifest(self, artifact_id: ArtifactID | ArtifactRef) -> ArtifactManifest:
        self.calls.append("get_manifest")
        return self._delegate.get_manifest(artifact_id)

    def put_bytes(
        self,
        data: bytes,
        opts: ArtifactWriteOptions,
        *,
        return_selected_profile: bool = False,
    ) -> ArtifactRef:
        self.calls.append("put_bytes")
        return self._delegate.put_bytes(data, opts, return_selected_profile=return_selected_profile)

    def put_json(
        self,
        obj: object,
        opts: ArtifactWriteOptions,
        canon_spec: CanonSpec | None = None,
        *,
        return_selected_profile: bool = False,
    ) -> ArtifactRef:
        self.calls.append("put_json")
        return self._delegate.put_json(
            obj,
            opts,
            canon_spec,
            return_selected_profile=return_selected_profile,
        )

    def verify(self, artifact_id: ArtifactID | ArtifactRef) -> VerificationReport:
        self.calls.append("verify")
        return self._delegate.verify(artifact_id)

    def iter_artifact_ids(self) -> list[ArtifactID]:
        self.calls.append("iter_artifact_ids")
        return self._delegate.iter_artifact_ids()


def test_promotion_evidence_loader_accepts_rootless_core_json_adapter(tmp_path: Path) -> None:
    run_id = "run_promotion_rootless_core_reader"
    ctx = _context(tmp_path, run_id)
    state = ExperimentState(run_id=run_id)
    candidate_ref = ensure_policy_candidate_ref(ctx, state, _candidate(), None)
    bundle = PromotionEvidenceBundle(
        run_id=run_id,
        produced_by_run_id=run_id,
        candidate_ref=candidate_ref,
    )
    bundle_ref = persist_promotion_evidence_bundle(ctx.store, bundle)
    rootless_store = ensure_ir_artifact_store(ctx.store)
    assert not hasattr(rootless_store, "root")
    assert isinstance(rootless_store, CoreJSONArtifactStore)
    guarded_store = guard_runtime_cas(rootless_store)
    rootless_ctx = replace(ctx, store=guarded_store)
    rootless_state = ExperimentState(
        run_id=run_id,
        inputs={run_policy_blueprint_runtime.INPUT_PROMOTION_EVIDENCE_BUNDLE_REF: bundle_ref},
    )
    try:
        loaded = run_policy_blueprint_runtime._load_existing_promotion_evidence(
            rootless_ctx,
            rootless_state,
        )
    finally:
        guarded_store.close()

    assert loaded is not None
    assert loaded.candidate_ref == candidate_ref
    assert guarded_store._target is rootless_store


def test_promotion_evidence_reader_refuses_minimal_store_before_cas_reads(tmp_path: Path) -> None:
    run_id = "run_promotion_minimal_store_refusal"
    ctx = _context(tmp_path, run_id)
    state = ExperimentState(run_id=run_id)
    candidate_ref = ensure_policy_candidate_ref(ctx, state, _candidate(), None)
    bundle_ref = persist_promotion_evidence_bundle(
        ctx.store,
        PromotionEvidenceBundle(
            run_id=run_id,
            produced_by_run_id=run_id,
            candidate_ref=candidate_ref,
        ),
    )
    minimal_store: ArtifactStore = _OpaqueArtifactStoreWithoutRawManifestReader(ctx.store)
    assert not isinstance(minimal_store, CoreJSONArtifactStore)
    rootless_minimal_store = ensure_ir_artifact_store(minimal_store)
    assert not hasattr(rootless_minimal_store, "root")
    minimal_ctx = replace(ctx, store=rootless_minimal_store)
    minimum_state = ExperimentState(
        run_id=run_id,
        inputs={run_policy_blueprint_runtime.INPUT_PROMOTION_EVIDENCE_BUNDLE_REF: bundle_ref},
    )

    with pytest.raises(CanonicalProfileRefusalError) as exc_info:
        run_policy_blueprint_runtime._load_existing_promotion_evidence(minimal_ctx, minimum_state)

    assert exc_info.value.code == "canon_profile_raw_manifest_unavailable"
    assert minimal_store.calls == []
