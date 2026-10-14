from __future__ import annotations

import logging
from pathlib import Path

import pytest

from polisyos.core.artifacts import artifact_manifest_profile_sha256, load_core_json_artifact
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
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
from polisyos.scientist.evidence.sources import EvidenceSourcesConfig
from polisyos.scientist.methods.autotune.models import (
    BenchmarkEvaluation,
    BenchmarkSplit,
    persist_benchmark_evaluation,
)
from polisyos.scientist.methods.search.benchmark_registry import BenchmarkRegistry
from polisyos.scientist.methods.search.transfer_context import (
    TransferContext,
    TransferScopeRefusalReason,
    TransferScopeRefusedError,
    TransferTenantScopeStatus,
    anonymize_tenant_id,
    resolve_transfer_context,
)
from polisyos.scientist.nodes.builtins.decide.policy_blueprint_runtime_benchmarks import (
    _maybe_register_benchmark_evaluation,
    _resolve_policy_runtime_source_statuses,
    _resolve_runtime_transfer_context,
)
from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
    ensure_policy_candidate_ref,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
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
