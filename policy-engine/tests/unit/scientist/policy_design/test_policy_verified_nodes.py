from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

import pytest

from polisyos.core.artifacts import load_core_json_artifact
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.fabric import (
    DataSnapshot,
    DataSnapshotOwnerBound,
    DataSnapshotRef,
    DataViewRequestRef,
)
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.connectors import DataVersion, FetchResult, QualityTier, VersionStrategy
from polisyos.ir.model_layer.queries import DataViewRequest
from polisyos.lex.knowledge.types import (
    LegalFactResult,
    LegalSourceAnchor,
    LegalSourceBundle,
)
from polisyos.scientist.adapters.fabric_bridge import DefaultFabricPort
from polisyos.scientist.evidence.claims.head_index import build_default_claim_ledger_owner
from polisyos.scientist.governance.report import load_governance_report_artifact
from polisyos.scientist.nodes.builtins.decide.build_decision_packet import BuildDecisionPacketNode
from polisyos.scientist.nodes.builtins.governance.run_governance import RunGovernanceNode
from polisyos.scientist.nodes.builtins.planning.run_source_gap_review import RunSourceGapReviewNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF,
    ARTIFACT_DECISION_PACKET_REF,
    ARTIFACT_LEGAL_CANDIDATE_PACK_REF,
    ARTIFACT_LEGAL_SOURCE_PACK_REF,
    ARTIFACT_POLICY_REQUEST_FRAME_REF,
    ARTIFACT_SOURCE_VERIFICATION_REPORT_REF,
    ARTIFACT_VERIFIED_POLICY_REPORT_REF,
    INPUT_DATA_SNAPSHOT_REF,
    INPUT_REGISTRY_BUNDLE_REF,
    INPUT_TRINITY_BUNDLE_REF,
    REPORT_GOVERNANCE_REPORT_REF,
)
from polisyos.scientist.orchestration.engine.context import (
    ClaimCapableExecutionContext,
    ExecutionContext,
)
from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec
from polisyos.scientist.validation.policy_verified import (
    LegalCandidatePack,
    LegalRetrievalStatus,
    LegalSourcePack,
    PolicyRequestFrame,
    SourceCoverageGap,
    SourceVerificationReport,
    VerifiedLegalClaim,
    VerifiedPolicyReport,
    load_legal_candidate_pack,
    load_source_verification_report,
    load_verified_policy_report,
    persist_legal_candidate_pack,
    persist_legal_source_pack,
    persist_policy_request_frame,
    persist_source_verification_report,
    persist_verified_policy_report,
)
from polisyos.scientist.validation.policy_verified.service import (
    _build_legal_toolkit,
    _load_cross_graph_profile,
    _load_research_intent,
    _maybe_verify_with_llm,
    _parse_json_object,
    assemble_legal_candidate_pack,
)


def _make_ctx(tmp_path, run_id: str) -> tuple[FileSystemCAS, ExecutionContext, object]:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store, return_selected_profile=True).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id=run_id)
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger(run_id))
    return store, ctx, registry_bundle


def _persist_test_data_snapshot(store: FileSystemCAS, request_id: str) -> DataSnapshotRef:
    """Use the real Fabric producer with an explicit deterministic fixture source."""
    now = datetime(2026, 10, 15, tzinfo=UTC)

    def fetch_data(
        *,
        dataset_id: str,
        connector_id: str | None = None,
        constraints: dict[str, object] | None = None,
        registry: object | None = None,
    ) -> FetchResult[object]:
        del connector_id, constraints, registry
        return FetchResult(
            data=[{"dataset_id": dataset_id, "value": 0.5}],
            row_count=1,
            schema_id="e02.policy_verified.fixture",
            schema_version="1.0",
            version=DataVersion(
                strategy=VersionStrategy.TIMESTAMP,
                value=now.isoformat(),
                timestamp=now,
            ),
            fetched_at=now,
            source_updated_at=now,
            completeness=1.0,
            quality_tier=QualityTier.GOLD,
            quality_flags=frozenset(),
            bytes_transferred=64,
        )

    request_ref = store.put_json(
        DataViewRequest(
            schema_version="1.0",
            request_id=request_id,
            view_type="table",
            metrics=["policy_verified_fixture"],
        ),
        ArtifactWriteOptions(
            kind="ir.data_view_request",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.DataViewRequest", version="1.0"),
        ),
    )
    snapshot_ref = DefaultFabricPort(fetch_data=fetch_data).snapshot(
        store,
        DataViewRequestRef(artifact_id=request_ref.artifact_id),
    )
    manifest = store.get_manifest(snapshot_ref)
    assert manifest.artifact_schema == SchemaInfo(
        name=DataSnapshot.ARTIFACT_SCHEMA_NAME,
        version=DataSnapshotOwnerBound.ARTIFACT_SCHEMA_VERSION,
    )
    assert (
        DataSnapshotOwnerBound.model_validate(
            load_core_json_artifact(store, snapshot_ref)
        ).source_lineage
        is not None
    )
    assert snapshot_ref.manifest_profile_sha256 is not None
    assert any(
        edge.role == "data_ref" and edge.manifest_profile_sha256 is not None
        for edge in manifest.inputs
    )
    return snapshot_ref


def _run_engine_governance_and_packet(
    store: FileSystemCAS, ctx: ExecutionContext, state: ExperimentState
) -> dict[str, object]:
    """Run the actual governance producer before its packet consumer."""
    governed_ctx = ClaimCapableExecutionContext(
        store=ctx.store,
        run=ctx.run,
        logger=ctx.logger,
        claim_ledger_owner=build_default_claim_ledger_owner(store=store),
    )
    governance = RunGovernanceNode()
    packet = BuildDecisionPacketNode()
    registry = NodeRegistry()
    registry.register(governance)
    registry.register(packet)
    workflow = WorkflowSpec(
        workflow_id="synthetic_policy_packet",
        nodes=[
            NodeInvocation(alias="governance", node_id=governance.spec.metadata.component_id),
            NodeInvocation(
                alias="packet", node_id=packet.spec.metadata.component_id, depends_on=["governance"]
            ),
        ],
    )
    result = WorkflowExecutor(governed_ctx, registry).execute(workflow, state)
    nodes = {item.alias: item for item in result.report.nodes}
    assert nodes["governance"].status == "ok", nodes["governance"].error
    assert nodes["packet"].status == "ok", nodes["packet"].error
    report_ref = result.state.reports_index[REPORT_GOVERNANCE_REPORT_REF]
    report = load_governance_report_artifact(store, report_ref)
    assert report.schema_version == "2.0" and report.invocation_binding is not None
    assert report.links.claims_ref is not None
    packet_ref = result.state.artifacts_index[ARTIFACT_DECISION_PACKET_REF]
    assert packet_ref.manifest_profile_sha256 is not None
    payload = from_canonical_bytes(store.get_bytes(packet_ref))
    assert isinstance(payload, dict)
    return payload


def test_run_source_gap_review_node_performs_second_recovery_cycle(monkeypatch, tmp_path) -> None:
    store, ctx, registry_bundle = _make_ctx(tmp_path, "R_policy_verified_gap_review")
    frame = PolicyRequestFrame(
        schema_version="1.1",
        request_id="req-1",
        policy_question="Як змінити ліцензування перевізників?",
        jurisdiction="UA",
        jurisdiction_source="policy_request_jurisdiction",
        policy_domain="transport",
    )
    frame_ref = persist_policy_request_frame(store, frame)
    candidate_pack = LegalCandidatePack(request_id="req-1", queries=["ліцензування перевізників"])
    candidate_ref = persist_legal_candidate_pack(store, candidate_pack)
    source_pack = LegalSourcePack(
        request_id="req-1",
        source_bundles=[
            LegalSourceBundle(
                bundle_id="bundle-1",
                doc_id="doc-1",
                version_id="v-1",
                doc_name="Mock approval law",
                doc_reestr_code="123",
                source_family="approval_bundle",
                primary_anchors=[
                    LegalSourceAnchor(
                        doc_id="doc-1",
                        version_id="v-1",
                        anchor="art:1",
                        citation_label="стаття 1",
                        provision_text="Порядок видачі посвідчень встановлюється Кабінетом Міністрів України.",
                        struct_kind="article",
                        section_role="normative_unit",
                        legal_unit_subtype="approval_bundle",
                        route_class="reasoning",
                        context_prefix=["Розділ I"],
                    )
                ],
            ),
            LegalSourceBundle(
                bundle_id="warning-bundle", doc_id="warning-document", source_family="general"
            ),
        ],
    )
    source_ref = persist_legal_source_pack(store, source_pack)
    initial_report = SourceVerificationReport(
        request_id="req-1",
        verified_claims=[],
        unresolved_critical_gaps=[
            SourceCoverageGap(
                gap_id="gap-1",
                category="bundle_without_claims",
                description="No verified claim extracted for approval bundle.",
                severity="critical",
                related_bundle_ids=["bundle-1"],
                suggested_queries=["порядок видачі посвідчень встановлюється"],
            )
        ],
        verification_cycles_completed=1,
        needs_expert_review=True,
    )
    report_ref = persist_source_verification_report(store, initial_report)

    class _RecoveryToolkit:
        def assemble_legal_candidate_pack(
            self, query, *, jurisdiction="UA", domain=None, as_of=None
        ):
            del jurisdiction, domain, as_of
            return LegalCandidatePack(
                request_id="req-1",
                queries=[query],
                fact_hits=[
                    LegalFactResult(
                        fact_id="lf-recovered",
                        subject_name="Кабінет Міністрів України",
                        predicate="establishes_order",
                        object_name="видача посвідчень",
                        fact_text="Порядок видачі посвідчень встановлюється Кабінетом Міністрів України.",
                        confidence=0.91,
                        norm_type="procedure",
                        norm_type_canon="procedure",
                        source_quote_uk="Порядок видачі посвідчень встановлюється Кабінетом Міністрів України.",
                        trust_tier="grounded_fact",
                        grounding_status="exact_quote",
                        canonical_status="canonicalized",
                        legal_unit_subtype="approval_bundle",
                        route_class="reasoning",
                        doc_id="doc-1",
                        version_id="v-1",
                        jurisdiction="UA",
                        top_domain="transport",
                        doc_name="Mock approval law",
                        doc_reestr_code="123",
                        provision_anchor="art:1",
                        provision_citation="стаття 1",
                        similarity=0.98,
                    )
                ],
            )

        def expand_legal_source_pack(
            self, candidate_pack, *, max_source_docs=120, max_reference_hops=2
        ):
            del max_source_docs, max_reference_hops
            return LegalSourcePack(
                request_id=candidate_pack.request_id,
                source_bundles=[
                    LegalSourceBundle(
                        bundle_id="bundle-1",
                        doc_id="doc-1",
                        version_id="v-1",
                        doc_name="Mock approval law",
                        doc_reestr_code="123",
                        source_family="approval_bundle",
                        primary_anchors=source_pack.source_bundles[0].primary_anchors,
                        candidate_fact_ids=["lf-recovered"],
                    )
                ],
            )

    monkeypatch.setattr(
        "polisyos.scientist.validation.policy_verified.service._build_legal_toolkit",
        lambda ctx_arg, state_arg: _RecoveryToolkit(),
    )

    state = ExperimentState(
        run_id="R_policy_verified_gap_review",
        inputs={INPUT_REGISTRY_BUNDLE_REF: registry_bundle},
        policy_request_ref=frame_ref,
        legal_candidate_pack_ref=candidate_ref,
        legal_source_pack_ref=source_ref,
        source_verification_report_ref=report_ref,
        artifacts_index={
            ARTIFACT_POLICY_REQUEST_FRAME_REF: frame_ref,
            ARTIFACT_LEGAL_CANDIDATE_PACK_REF: candidate_ref,
            ARTIFACT_LEGAL_SOURCE_PACK_REF: source_ref,
            ARTIFACT_SOURCE_VERIFICATION_REPORT_REF: report_ref,
        },
        params={"verification_cycles_completed": 1, "max_gap_review_calls": 10},
    )

    outcome = RunSourceGapReviewNode().execute(ctx, state)
    assert outcome.status == "ok"
    assert outcome.state.params["verification_cycles_completed"] == 2
    assert outcome.state.params["needs_expert_review"] is True

    updated_candidate_pack = load_legal_candidate_pack(
        store, outcome.state.legal_candidate_pack_ref
    )
    assert "порядок видачі посвідчень встановлюється" in updated_candidate_pack.queries
    updated_report = load_source_verification_report(
        store, outcome.state.source_verification_report_ref
    )
    assert not updated_report.verified_claims
    assert len(updated_report.legal_claim_candidates) == 1
    assert (
        updated_report.legal_claim_candidates[0].metadata["legal_source_candidate"]["claim_type"]
        == "procedure"
    )
    assert any(
        gap.category == "legal_claim_verification_not_established" and gap.severity == "critical"
        for gap in updated_report.unresolved_critical_gaps
    )
    assert any(gap.severity == "warning" for gap in updated_report.unresolved_critical_gaps)
    assert outcome.events[0].attrs["critical_gaps"] == sum(
        gap.severity == "critical" and not gap.resolved
        for gap in updated_report.unresolved_critical_gaps
    )
    assert outcome.events[0].attrs["critical_gaps"] < len(updated_report.unresolved_critical_gaps)


def test_engine_packet_keeps_historical_policy_sections_unbound(tmp_path) -> None:
    store, ctx, registry_bundle = _make_ctx(tmp_path, "R_policy_verified_packet")
    trinity_ref = store.put_json(
        {"trinity": {"interventions": []}},
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version="1.0"),
        ),
    )
    data_snapshot_ref = _persist_test_data_snapshot(store, "req_policy_verified_packet")
    verification_ref = persist_source_verification_report(
        store,
        SourceVerificationReport(
            request_id="req-2",
            verified_claims=[
                VerifiedLegalClaim(
                    claim_id="claim-1",
                    bundle_id="bundle-1",
                    doc_id="doc-1",
                    version_id="v-1",
                    anchor="art:1",
                    citation_label="стаття 1",
                    claim_type="obligation",
                    claim_text="Ліцензія є обов'язковою.",
                    quote="Ліцензія є обов'язковою.",
                    confidence=0.94,
                )
            ],
            verified_claim_citation_coverage_pct=100.0,
            verification_cycles_completed=2,
        ),
    )
    verified_policy_ref = persist_verified_policy_report(
        store,
        VerifiedPolicyReport(
            request_id="req-2",
            executive_summary="Verified policy summary",
            verified_findings=["Ліцензія є обов'язковою. [стаття 1]"],
            hypotheses=["Можливе пом'якшення вимог для пілотного режиму."],
            missing_evidence=["Потрібно окремо перевірити додаток 2."],
            intervention_legal_basis_map={"verified_option_1": ["стаття 1"]},
        ),
    )

    historical_source = load_source_verification_report(store, verification_ref)
    historical_policy = load_verified_policy_report(store, verified_policy_ref)
    assert historical_source.verified_claims[0].claim_text == "Ліцензія є обов'язковою."
    assert historical_policy.executive_summary == "Verified policy summary"
    assert historical_policy.verified_findings == ["Ліцензія є обов'язковою. [стаття 1]"]

    state = ExperimentState(
        run_id="R_policy_verified_packet",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
        artifacts_index={
            ARTIFACT_SOURCE_VERIFICATION_REPORT_REF: verification_ref,
            ARTIFACT_VERIFIED_POLICY_REPORT_REF: verified_policy_ref,
        },
    )

    payload = _run_engine_governance_and_packet(store, ctx, state)

    assert payload["legal_verification"]["verification_status"] == "not_established"
    assert payload["legal_verification"]["verified_claim_count"] is None
    assert payload["legal_verification"]["reported_unbound_claim_count"] == 1
    assert payload["legal_verification"]["verification_cycles_completed"] == 2
    assert any(
        gap["category"] == "legal_claim_verification_not_established"
        for gap in payload["source_coverage"]["unresolved_critical_gaps"]
    )
    assert payload["policy_answer"] is None
    assert payload["verified_findings"] == []
    assert payload["hypotheses"] == []
    assert payload["intervention_legal_basis_map"] == {}
    assert any(
        item["reason"] == "verified_policy_report_currentness_not_established"
        for item in payload["degraded_paths"]
    )
    outline = {entry["section_id"]: entry for entry in payload["document_outline"]}
    assert outline["governance"]["section_type"] == "governance"


def test_build_decision_packet_records_degraded_paths_for_invalid_policy_verification_artifacts(
    tmp_path,
) -> None:
    store, ctx, registry_bundle = _make_ctx(tmp_path, "R_policy_verified_packet_degraded")
    trinity_ref = store.put_json(
        {"trinity": {"interventions": []}},
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version="1.0"),
        ),
    )
    data_snapshot_ref = _persist_test_data_snapshot(
        store,
        "req_policy_verified_packet_degraded",
    )
    invalid_verification_ref = store.put_json(
        ["invalid"],
        PutOptions(kind="scientist.source_verification_report", media_type="application/json"),
    )
    invalid_verified_policy_ref = store.put_json(
        ["invalid"],
        PutOptions(kind="scientist.verified_policy_report", media_type="application/json"),
    )

    state = ExperimentState(
        run_id="R_policy_verified_packet_degraded",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
        artifacts_index={
            ARTIFACT_SOURCE_VERIFICATION_REPORT_REF: invalid_verification_ref,
            ARTIFACT_VERIFIED_POLICY_REPORT_REF: invalid_verified_policy_ref,
        },
    )

    payload = _run_engine_governance_and_packet(store, ctx, state)
    degraded_reasons = {item["reason"] for item in payload["degraded_paths"]}

    assert payload["legal_verification"] is None
    assert payload["source_coverage"] is None
    assert payload["policy_answer"] is None
    assert payload["verified_findings"] == []
    assert payload["hypotheses"] == []
    assert payload["intervention_legal_basis_map"] == {}
    assert {
        "source_verification_report_load_failed",
        "verified_policy_report_currentness_not_established",
    }.issubset(degraded_reasons)
    assert payload["diagnostics_summary"]["degraded_path_count"] >= 2


def test_build_legal_toolkit_uses_nested_evidence_sources(monkeypatch, tmp_path) -> None:
    _, ctx, registry_bundle = _make_ctx(tmp_path, "R_policy_verified_sources")
    legal_db_path = tmp_path / "legal.duckdb"
    legal_db_path.write_text("", encoding="utf-8")
    captured: dict[str, object] = {}

    class FakeLegalKnowledgeGraph:
        def __init__(self, *, db_path, index_dir, openai_api_key=None) -> None:
            captured["db_path"] = db_path
            captured["index_dir"] = index_dir
            captured["openai_api_key"] = openai_api_key

    monkeypatch.setattr(
        "polisyos.scientist.validation.policy_verified.service.LegalKnowledgeGraph",
        FakeLegalKnowledgeGraph,
    )

    state = ExperimentState(
        run_id="R_policy_verified_sources",
        inputs={INPUT_REGISTRY_BUNDLE_REF: registry_bundle},
        params={"evidence_sources": {"legal_db_path": str(legal_db_path)}},
    )

    toolkit = _build_legal_toolkit(ctx, state)

    assert toolkit is not None
    assert captured["db_path"] == legal_db_path
    assert captured["index_dir"] == legal_db_path.parent


def test_load_research_intent_assertion_is_not_swallowed(monkeypatch, tmp_path) -> None:
    store, _, _ = _make_ctx(tmp_path, "R_policy_verified_intent_assert")

    def _boom(*args, **kwargs):
        del args, kwargs
        raise AssertionError("intent-ref-broken")

    monkeypatch.setattr(
        "polisyos.scientist.validation.policy_verified.service.ResearchIntentRef.model_validate",
        _boom,
    )

    with pytest.raises(AssertionError, match="intent-ref-broken"):
        _load_research_intent(store, {})


def test_build_legal_toolkit_assertion_is_not_swallowed(monkeypatch, tmp_path) -> None:
    _, ctx, registry_bundle = _make_ctx(tmp_path, "R_policy_verified_toolkit_assert")
    legal_db_path = tmp_path / "legal.duckdb"
    legal_db_path.write_text("", encoding="utf-8")

    def _boom(*args, **kwargs):
        del args, kwargs
        raise AssertionError("legal-toolkit-broken")

    monkeypatch.setattr(
        "polisyos.scientist.validation.policy_verified.service.LegalKnowledgeGraph",
        _boom,
    )

    state = ExperimentState(
        run_id="R_policy_verified_toolkit_assert",
        inputs={INPUT_REGISTRY_BUNDLE_REF: registry_bundle},
        params={"evidence_sources": {"legal_db_path": str(legal_db_path)}},
    )

    with pytest.raises(AssertionError, match="legal-toolkit-broken"):
        _build_legal_toolkit(ctx, state)


def test_load_cross_graph_profile_assertion_is_not_swallowed(monkeypatch, tmp_path) -> None:
    store, _, _ = _make_ctx(tmp_path, "R_policy_verified_profile_assert")
    profile_ref = store.put_json(
        {"broken": True},
        PutOptions(kind="scientist.cross_graph_evidence_profile", media_type="application/json"),
    )
    state = ExperimentState(
        run_id="R_policy_verified_profile_assert",
        artifacts_index={ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF: profile_ref},
    )

    def _boom(*args, **kwargs):
        del args, kwargs
        raise AssertionError("cross-graph-profile-broken")

    monkeypatch.setattr(
        "polisyos.scientist.validation.policy_verified.service.CrossGraphEvidenceProfile.model_validate",
        _boom,
    )

    with pytest.raises(AssertionError, match="cross-graph-profile-broken"):
        _load_cross_graph_profile(store, state)


def test_parse_json_object_assertion_is_not_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*args, **kwargs):
        del args, kwargs
        raise AssertionError("json-parse-broken")

    monkeypatch.setattr(
        "polisyos.scientist.validation.policy_verified.service.extract_llm_json_object",
        _boom,
    )

    with pytest.raises(AssertionError, match="json-parse-broken"):
        _parse_json_object(json.dumps({"ok": True}))


def test_parse_json_object_accepts_think_prefixed_json() -> None:
    assert _parse_json_object('<think>legal reasoning</think>{"ok":true}') == {"ok": True}


def test_parse_json_object_returns_none_when_no_object_exists() -> None:
    assert _parse_json_object("no legal-verifier object exists") is None


def test_maybe_verify_with_llm_assertion_is_not_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FailingClient:
        async def generate(self, **kwargs):
            del kwargs
            raise AssertionError("llm-verifier-broken")

    monkeypatch.setattr(
        "polisyos.scientist.validation.policy_verified.service.create_traced_gateway_client",
        lambda **kwargs: _FailingClient(),
    )

    source_pack = LegalSourcePack(
        request_id="req-assert",
        source_bundles=[
            LegalSourceBundle(
                bundle_id="bundle-assert",
                doc_id="doc-assert",
                version_id="v-1",
                doc_name="Mock law",
                source_family="approval_bundle",
            )
        ],
    )

    with pytest.raises(AssertionError, match="llm-verifier-broken"):
        _maybe_verify_with_llm(
            state=ExperimentState(run_id="R_policy_verified_llm_assert"),
            frame=PolicyRequestFrame(
                request_id="req-assert",
                policy_question="Чи потрібна ліцензія?",
                jurisdiction="UA",
            ),
            source_pack=source_pack,
            baseline_claims=[],
        )


def test_assemble_legal_candidate_pack_surfaces_typed_degraded_legal_status(tmp_path) -> None:
    _, ctx, registry_bundle = _make_ctx(tmp_path, "R_policy_verified_degraded")
    frame = PolicyRequestFrame(
        schema_version="1.1",
        request_id="req-degraded",
        policy_question="Як змінити ліцензування перевізників?",
        jurisdiction="UA",
        jurisdiction_source="policy_request_jurisdiction",
        policy_domain="transport",
    )
    state = ExperimentState(
        run_id="R_policy_verified_degraded",
        inputs={INPUT_REGISTRY_BUNDLE_REF: registry_bundle},
        params={},
    )

    pack = assemble_legal_candidate_pack(ctx, state, frame)

    assert pack.fact_hits == []
    assert pack.source_statuses["legal"].status.value == "missing_config"
    assert pack.legal_retrieval_status[0].search_mode is None
    assert pack.legal_retrieval_status[0].limitation_code == (
        "legal_graph_unavailable:missing_config"
    )
    assert "legal_graph_unavailable:missing_config" in pack.notes


def test_assemble_legal_candidate_pack_preserves_mixed_query_statuses(
    monkeypatch, tmp_path
) -> None:
    _, ctx, _ = _make_ctx(tmp_path, "R_policy_verified_mixed_retrieval")
    frame = PolicyRequestFrame(
        schema_version="1.1",
        request_id="req-mixed-retrieval",
        policy_question="first retrieval query",
        jurisdiction="UA",
        jurisdiction_source="policy_request_jurisdiction",
        goals=["second retrieval query"],
    )
    state = ExperimentState(
        run_id="R_policy_verified_mixed_retrieval",
        params={"max_candidate_queries": 2},
    )

    class _MixedStatusToolkit:
        def assemble_legal_candidate_pack(
            self, query, *, jurisdiction="UA", domain=None, as_of=None
        ):
            del jurisdiction, domain, as_of
            if query == "first retrieval query":
                status = LegalRetrievalStatus(
                    query=query,
                    route="hybrid_facts",
                    search_mode="text",
                    vector_refusal_code="query_encoder_runtime_material_not_established",
                )
            else:
                status = LegalRetrievalStatus(
                    query=query,
                    route="provisions",
                    limitation_code="query_encoder_assets_unavailable",
                )
            return LegalCandidatePack(
                request_id="toolkit",
                queries=[query],
                legal_retrieval_status=[status],
            )

    monkeypatch.setattr(
        "polisyos.scientist.validation.policy_verified.service._build_legal_toolkit",
        lambda ctx, state: _MixedStatusToolkit(),
    )
    pack = assemble_legal_candidate_pack(ctx, state, frame)

    assert [status.query for status in pack.legal_retrieval_status] == [
        "first retrieval query",
        "second retrieval query",
    ]
    assert pack.legal_retrieval_status[0].search_mode == "text"
    assert pack.legal_retrieval_status[0].vector_refusal_code == (
        "query_encoder_runtime_material_not_established"
    )
    assert pack.legal_retrieval_status[1].search_mode is None
    assert pack.legal_retrieval_status[1].limitation_code == "query_encoder_assets_unavailable"

    legacy_pack = LegalCandidatePack.model_validate(
        {"schema_version": "1.0", "request_id": "req-legacy"}
    )
    assert legacy_pack.schema_version == "1.0"
    assert legacy_pack.legal_retrieval_status == []
