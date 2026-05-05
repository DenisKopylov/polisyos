from __future__ import annotations

from types import SimpleNamespace

import duckdb
import pytest
from polisyos.core.governance.passes.base import PassContext
from polisyos.core.governance.profiles import ValidationProfile
from polisyos.data_forge.domains.academic.knowledge.skg_query import SKGQuery
from polisyos.data_forge.domains.academic.knowledge.skg_store import (
    ensure_skg_schema,
    next_skg_version,
)
from polisyos.ir.analytics.context import ContextProfile
from polisyos.ir.analytics.cross_graph import (
    CanonicalConcept,
    CrossGraphDiagnostic,
    CrossGraphEvidenceProfile,
    CrossGraphEvidenceSummary,
    EvidenceNeed,
    EvidenceNeedAssessment,
    EvidenceNeedType,
    EvidenceStatus,
    LegalStatus,
    ObservabilityStatus,
    TransportStatus,
)
from polisyos.ir.analytics.literature import (
    EnvironmentAuditReport,
    LiteratureCausalPrior,
    LiteratureEdgePrior,
)
from polisyos.ir.analytics.transportability import TransportMode
from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.governance.problem_frame import ConstraintSpec, ProblemFrame
from polisyos.ir.model_spec import ModelSpec
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.cross_graph.compiler import (
    CrossGraphEvidenceCompiler,
    CrossGraphEvidenceConfig,
    _assess_academic_need,
    _build_academic_query,
    _candidate_distance,
    build_fragment_alignment_ontology_warnings,
    extract_evidence_needs,
)
from polisyos.scientist.cross_graph.gatherers.academic import AcademicGatherer
from polisyos.scientist.cross_graph.protocols import GathererResult
from polisyos.scientist.governance.passes.cross_graph_evidence_pass import CrossGraphEvidencePass


def _bundle() -> TrinityBundle:
    return TrinityBundle(
        problem_frame=ProblemFrame(
            problem_id="problem1",
            domain="social",
            hard_constraints=[
                ConstraintSpec(
                    constraint_id="budget_cap",
                    value=1,
                    slot_id="budget",
                )
            ],
        ),
        policy_spec=PolicySpec(policy_id="policy1"),
        model_spec=ModelSpec(
            model_id="model1",
            data_snapshot_ref="sha256:" + ("0" * 64),
        ),
    )


def test_cross_graph_need_ids_are_deterministic_and_compiler_falls_back() -> None:
    bundle = _bundle()

    first = extract_evidence_needs(
        bundle,
        jurisdiction="UA",
        policy_domain="social",
        country_code="UA",
    )
    second = extract_evidence_needs(
        bundle,
        jurisdiction="UA",
        policy_domain="social",
        country_code="UA",
    )

    assert [item.need_id for item in first] == [item.need_id for item in second]
    assert first[0].need_type is EvidenceNeedType.CONSTRAINT_METRIC_OR_SLOT

    profile = CrossGraphEvidenceCompiler(CrossGraphEvidenceConfig()).compile(bundle)
    assert profile.summary.total_needs == len(first)
    assert any(
        diagnostic.code == "cross_graph.ontology.unknown_concept"
        for diagnostic in profile.diagnostics
    )


def test_cross_graph_compiler_routes_literature_prior_context_through_academic_gatherer(
    monkeypatch,
) -> None:
    bundle = _bundle()
    literature_prior = LiteratureCausalPrior(
        environment_audit=EnvironmentAuditReport(
            status="warning",
            n_environments=2,
            ks_passed=False,
            ks_rejected_variables=[0],
            warnings=["feature_drift_detected"],
        ),
        metadata={"build_status": "ok"},
    )
    captured_contexts: list[dict[str, object]] = []

    def _fake_assess(self, need, *, concepts, context):
        del self, need, concepts
        captured_contexts.append(dict(context))
        return GathererResult(
            status=EvidenceStatus.SUPPORTED.value,
            confidence=0.9,
            diagnostics=[],
            provenance_refs=["study:1"],
            metadata={"transport_reasons": []},
        )

    monkeypatch.setattr(AcademicGatherer, "assess", _fake_assess)

    profile = CrossGraphEvidenceCompiler(CrossGraphEvidenceConfig()).compile(
        bundle,
        literature_prior=literature_prior,
        literature_prior_ref="ir:literature_prior:test",
    )

    assert captured_contexts
    assert any(
        context.get("literature_prior_ref") == "ir:literature_prior:test"
        for context in captured_contexts
    )
    assert any(
        (context.get("environment_audit_summary") or {}).get("status") == "warning"
        for context in captured_contexts
    )
    assert any(
        diagnostic.code == "cross_graph.academic.literature_prior_context"
        for diagnostic in profile.diagnostics
    )
    assert "environment_audit_status:warning" in profile.notes


def test_cross_graph_compiler_legal_assertion_is_not_swallowed(
    monkeypatch,
    tmp_path,
) -> None:
    bundle = _bundle()

    def _boom(**kwargs):
        del kwargs
        raise AssertionError("legal bridge contract broken")

    monkeypatch.setattr(
        "polisyos.scientist.cross_graph.compiler.evaluate_transport_constraints",
        _boom,
    )

    compiler = CrossGraphEvidenceCompiler(
        CrossGraphEvidenceConfig(
            legal_db_path=str(tmp_path / "legal.duckdb"),
            jurisdiction="UA",
            policy_domain="social",
        )
    )

    with pytest.raises(AssertionError, match="legal bridge contract broken"):
        compiler.compile(bundle)


def test_build_academic_query_assertion_is_not_swallowed(
    monkeypatch,
    tmp_path,
) -> None:
    academic_db_path = tmp_path / "academic.duckdb"
    academic_db_path.write_text("", encoding="utf-8")

    class _BrokenQuery:
        def __init__(self, db_path, index_dir) -> None:
            del db_path, index_dir
            raise AssertionError("academic init exploded")

    monkeypatch.setattr(
        "polisyos.scientist.cross_graph.compiler.SKGQuery",
        _BrokenQuery,
    )

    with pytest.raises(AssertionError, match="academic init exploded"):
        _build_academic_query(CrossGraphEvidenceConfig(academic_db_path=str(academic_db_path)))


def test_candidate_distance_assertion_is_not_swallowed() -> None:
    class _BrokenContext:
        def distance_to(self, other) -> float:
            del other
            raise AssertionError("distance invariant failed")

    candidate = SimpleNamespace(source_context=_BrokenContext())

    with pytest.raises(AssertionError, match="distance invariant failed"):
        _candidate_distance(candidate, ContextProfile(context_id="UA", context_label="Ukraine"))


def test_fragment_alignment_ontology_assertion_is_not_swallowed(monkeypatch) -> None:
    def _boom(cls, payload):
        del cls, payload
        raise AssertionError("ontology validation invariant failed")

    monkeypatch.setattr(CanonicalConcept, "model_validate", classmethod(_boom))

    with pytest.raises(AssertionError, match="ontology validation invariant failed"):
        build_fragment_alignment_ontology_warnings(
            fragment_a={},
            fragment_b={},
            certificates=[],
            ontology=[{"concept_id": "x"}],
        )


def test_academic_gatherer_uses_literature_prior_baseline_without_backend() -> None:
    need = EvidenceNeed(
        need_id="edge_need:baseline",
        need_type=EvidenceNeedType.CAUSAL_EDGE_NEED,
        source_path="causal_graph.edges[0]",
        cause="tax.audit_rate",
        effect="tax.compliance",
    )
    literature_prior = LiteratureCausalPrior(
        edges=[
            LiteratureEdgePrior(
                src="tax.audit_rate",
                dst="tax.compliance",
                confidence=0.72,
                n_articles=3,
                article_refs=["oa:1", "oa:2"],
            )
        ]
    )

    result = AcademicGatherer().assess(
        need,
        concepts=[],
        context={"academic_query": None, "literature_prior": literature_prior},
    )

    assert result.status == EvidenceStatus.MIXED.value
    assert result.metadata["baseline_support_source"] == "literature_prior"
    assert result.metadata["literature_prior_confidence"] == 0.72
    assert result.metadata["literature_prior_article_refs"] == ["oa:1", "oa:2"]
    assert result.provenance_refs == ["oa:1", "oa:2"]


def test_academic_gatherer_does_not_use_edge_prior_for_parameter_needs() -> None:
    need = EvidenceNeed(
        need_id="parameter_need:baseline",
        need_type=EvidenceNeedType.PARAMETER_NEED,
        source_path="policy_spec.parameters[0]",
        parameter_name="fiscal_multiplier",
    )
    literature_prior = LiteratureCausalPrior(
        edges=[
            LiteratureEdgePrior(
                src="tax.audit_rate",
                dst="tax.compliance",
                confidence=0.8,
                n_articles=4,
                article_refs=["oa:1"],
            )
        ]
    )

    result = AcademicGatherer().assess(
        need,
        concepts=[],
        context={"academic_query": None, "literature_prior": literature_prior},
    )

    assert result.status == EvidenceStatus.INSUFFICIENT.value
    assert result.metadata.get("baseline_support_source") is None


def test_academic_gatherer_prior_baseline_only_lifts_insufficient_backend_to_mixed() -> None:
    class _AcademicResult:
        def __init__(self) -> None:
            self.evidence_status = EvidenceStatus.INSUFFICIENT
            self.transport_confidence = 0.25
            self.diagnostics = []
            self.provenance_refs = ["study:legacy"]
            self.transport_reasons = ["backend_insufficient"]

    need = EvidenceNeed(
        need_id="edge_need:merge",
        need_type=EvidenceNeedType.CAUSAL_EDGE_NEED,
        source_path="causal_graph.edges[0]",
        cause="tax.audit_rate",
        effect="tax.compliance",
    )
    literature_prior = LiteratureCausalPrior(
        edges=[
            LiteratureEdgePrior(
                src="tax.audit_rate",
                dst="tax.compliance",
                confidence=0.7,
                n_articles=3,
                article_refs=["oa:1", "oa:2"],
            )
        ]
    )

    result = AcademicGatherer().assess(
        need,
        concepts=[],
        context={
            "academic_query": object(),
            "literature_prior": literature_prior,
            "_assess_academic_need": lambda *args, **kwargs: _AcademicResult(),
        },
    )

    assert result.status == EvidenceStatus.MIXED.value
    assert result.metadata["baseline_support_source"] == "literature_prior"
    assert "study:legacy" in result.provenance_refs
    assert "oa:1" in result.provenance_refs


def test_environment_audit_warning_adds_advisory_without_changing_prior_backed_status() -> None:
    need = EvidenceNeed(
        need_id="edge_need:audit",
        need_type=EvidenceNeedType.CAUSAL_EDGE_NEED,
        source_path="causal_graph.edges[0]",
        cause="tax.audit_rate",
        effect="tax.compliance",
    )
    literature_prior = LiteratureCausalPrior(
        edges=[
            LiteratureEdgePrior(
                src="tax.audit_rate",
                dst="tax.compliance",
                confidence=0.72,
                n_articles=3,
                article_refs=["oa:1", "oa:2"],
            )
        ],
        environment_audit=EnvironmentAuditReport(
            status="warning",
            n_environments=2,
            ks_passed=False,
            ks_rejected_variables=[0],
            warnings=["feature_drift_detected"],
        ),
    )

    result = AcademicGatherer().assess(
        need,
        concepts=[],
        context={
            "academic_query": None,
            "literature_prior": literature_prior,
            "environment_audit": literature_prior.environment_audit,
        },
    )

    assert result.status == EvidenceStatus.MIXED.value
    assert any(
        diagnostic.code == "cross_graph.academic.environment_audit_advisory"
        for diagnostic in result.diagnostics
    )


def test_cross_graph_governance_pass_blocks_strict_blockers() -> None:
    need = EvidenceNeed(
        need_id="causal_edge_need:test",
        need_type=EvidenceNeedType.CAUSAL_EDGE_NEED,
        source_path="causal_graph.edges[0]",
        cause="x",
        effect="y",
    )
    profile = CrossGraphEvidenceProfile(
        summary=CrossGraphEvidenceSummary(status="warning", total_needs=1),
        needs=[
            EvidenceNeedAssessment(
                need=need,
                legal_status=LegalStatus.ALLOWED,
                observability_status=ObservabilityStatus.DIRECT,
                evidence_status=EvidenceStatus.SUPPORTED,
                transport_status=TransportStatus.UNSUPPORTED,
                transport_mode=TransportMode.NONE,
                blocking_reasons=["transport_status=unsupported"],
                confidence=0.2,
                requires_expert_review=True,
            )
        ],
    )

    issues = CrossGraphEvidencePass().validate(
        PassContext(
            ir=None,
            state={"cross_graph_evidence_profile": profile.model_dump(mode="json")},
            registry_bundle=None,
            profile=ValidationProfile.strict(),
            run_id="run-1",
        )
    )

    assert any(issue.code == "CROSS_GRAPH_TRANSPORT_REVIEW_REQUIRED" for issue in issues)
    assert any(issue.severity.value == "blocker" for issue in issues)


def test_cross_graph_governance_pass_blocks_unknown_concepts_in_strict() -> None:
    profile = CrossGraphEvidenceProfile(
        summary=CrossGraphEvidenceSummary(status="warning", total_needs=1),
        diagnostics=[
            CrossGraphDiagnostic(
                code="cross_graph.ontology.unknown_concept",
                need_id="need_fixture_unknown",
                message="No ontology bridge resolved for fixture need.",
            )
        ],
    )

    issues = CrossGraphEvidencePass().validate(
        PassContext(
            ir=None,
            state={"cross_graph_evidence_profile": profile.model_dump(mode="json")},
            registry_bundle=None,
            profile=ValidationProfile.strict(),
            run_id="run-unknown",
        )
    )

    assert any(issue.code == "CROSS_GRAPH_UNKNOWN_CONCEPT" for issue in issues)
    assert any(issue.severity.value == "blocker" for issue in issues)


def test_assess_academic_need_uses_hybrid_edge_support(tmp_path) -> None:
    db_path = tmp_path / "academic.duckdb"
    con = duckdb.connect(str(db_path))
    try:
        ensure_skg_schema(con)
        next_skg_version(con, description="test")
        con.execute(
            """
            INSERT INTO ac_skg_family_edges(
                family_edge_id, src_family, dst_family, direction, n_articles, n_claims,
                article_refs, claim_refs, evidence_strength, confidence, quality_signals_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "fe_support",
                "governance.tax_enforcement",
                "fiscal.tax_compliance_rate",
                "positive",
                3,
                3,
                '["W1","W2","W3"]',
                '["c1","c2","c3"]',
                "quasi_natural",
                0.78,
                '{"conflict_flag": false}',
            ],
        )
        con.execute("CHECKPOINT")
    finally:
        con.close()

    need = EvidenceNeed(
        need_id="edge_need:test",
        need_type=EvidenceNeedType.CAUSAL_EDGE_NEED,
        source_path="causal_graph.edges[0]",
        cause="governance.tax_enforcement",
        effect="fiscal.tax_compliance_rate",
    )
    query = SKGQuery(db_path=db_path, index_dir=tmp_path / "idx")
    try:
        result = _assess_academic_need(
            need,
            concepts=[],
            academic_query=query,
            target_context=None,
        )
    finally:
        query.close()

    assert result.status is EvidenceStatus.SUPPORTED
    assert result.confidence >= 0.78


def test_assess_academic_need_adds_transport_rationale_for_weak_edge_transfer(tmp_path) -> None:
    db_path = tmp_path / "academic_transport.duckdb"
    con = duckdb.connect(str(db_path))
    try:
        ensure_skg_schema(con)
        version_id = next_skg_version(con, description="transport-test")
        con.execute(
            """
            INSERT INTO ac_skg_family_edges(
                family_edge_id, src_family, dst_family, direction, n_articles, n_claims,
                article_refs, claim_refs, evidence_strength, confidence, quality_signals_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "fe_transport",
                "tax.policy",
                "employment.rate",
                "positive",
                4,
                4,
                '["W1","W2","W3","W4"]',
                '["c1","c2","c3","c4"]',
                "quasi_natural",
                0.81,
                '{"conflict_flag": false}',
            ],
        )
        con.execute(
            """
            INSERT INTO ac_skg_transport_scores(
                transport_id, edge_id, target_context_id, base_confidence,
                generic_penalty, context_match_reward, transport_confidence,
                match_mode, matched_moderators_json, skg_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "tr1",
                "fe_transport",
                "UA",
                0.81,
                0.18,
                0.0,
                0.39,
                "",
                "[]",
                version_id,
            ],
        )
        con.execute("CHECKPOINT")
    finally:
        con.close()

    need = EvidenceNeed(
        need_id="edge_need:transport",
        need_type=EvidenceNeedType.CAUSAL_EDGE_NEED,
        source_path="causal_graph.edges[0]",
        cause="tax.policy",
        effect="employment.rate",
        target_context_id="UA",
    )
    query = SKGQuery(db_path=db_path, index_dir=tmp_path / "idx")
    try:
        result = _assess_academic_need(
            need,
            concepts=[],
            academic_query=query,
            target_context=ContextProfile(context_id="UA", context_label="Ukraine"),
        )
    finally:
        query.close()

    assert result.status is EvidenceStatus.MIXED
    assert result.transport_confidence == 0.39
    assert "weak_transfer_evidence" in result.transport_reasons
    assert any("moderator_mismatch" in action for action in result.recommended_actions)


def test_assess_academic_parameter_need_surfaces_raw_fallback_and_no_uncertainty(tmp_path) -> None:
    db_path = tmp_path / "academic_param.duckdb"
    con = duckdb.connect(str(db_path))
    try:
        ensure_skg_schema(con)
        con.execute(
            """
            INSERT INTO ac_skg_parameters(param_id, canonical_name, openalex_id, parameter_json, context_json)
            VALUES (
                'p1',
                'fiscal_multiplier',
                'W1',
                '{"name":"fiscal_multiplier","value":1.1,"parameter_type":"quantitative","evidence_strength":"quasi_natural"}',
                '{"context_id":"PL","income_level":"upper_middle","institutional_quality":0.6}'
            )
            """
        )
        con.execute(
            """
            INSERT INTO ac_skg_context_profiles(profile_id, context_id, profile_json, skg_version)
            VALUES
                ('profile_pl', 'PL', '{"context_id":"PL","context_label":"Poland"}', 1),
                ('profile_ua', 'UA', '{"context_id":"UA","context_label":"Ukraine"}', 1)
            """
        )
        con.execute("CHECKPOINT")
    finally:
        con.close()

    need = EvidenceNeed(
        need_id="parameter_need:test",
        need_type=EvidenceNeedType.PARAMETER_NEED,
        source_path="policy_spec.parameters[0]",
        parameter_name="fiscal_multiplier",
        target_context_id="UA",
    )
    query = SKGQuery(db_path=db_path, index_dir=tmp_path / "idx")
    try:
        result = _assess_academic_need(
            need,
            concepts=[],
            academic_query=query,
            target_context=ContextProfile(context_id="UA", context_label="Ukraine"),
        )
    finally:
        query.close()

    assert result.status is not EvidenceStatus.SUPPORTED
    assert any("simulation-ready" in action.lower() for action in result.recommended_actions)
    assert any("uncertainty" in action.lower() for action in result.recommended_actions)


def test_assess_academic_need_treats_moderated_conflict_as_supported_when_replicated(
    tmp_path,
) -> None:
    db_path = tmp_path / "academic_moderated.duckdb"
    con = duckdb.connect(str(db_path))
    try:
        ensure_skg_schema(con)
        next_skg_version(con, description="moderated-test")
        con.execute(
            """
            INSERT INTO ac_skg_family_edges(
                family_edge_id, src_family, dst_family, direction, n_articles, n_claims,
                article_refs, claim_refs, evidence_strength, confidence, quality_signals_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "fe_moderated",
                "labor.minimum_wage",
                "labor.employment_rate",
                "positive",
                3,
                3,
                '["W1","W2","W3"]',
                '["c1","c2","c3"]',
                "quasi_natural",
                0.79,
                '{"conflict_flag": true, "moderated_conflict": true, "direction_agreement": 0.68}',
            ],
        )
        con.execute("CHECKPOINT")
    finally:
        con.close()

    need = EvidenceNeed(
        need_id="edge_need:moderated",
        need_type=EvidenceNeedType.CAUSAL_EDGE_NEED,
        source_path="causal_graph.edges[0]",
        cause="labor.minimum_wage",
        effect="labor.employment_rate",
    )
    query = SKGQuery(db_path=db_path, index_dir=tmp_path / "idx")
    try:
        result = _assess_academic_need(
            need,
            concepts=[],
            academic_query=query,
            target_context=None,
        )
    finally:
        query.close()

    assert result.status is EvidenceStatus.SUPPORTED
    assert any("moderator-explained" in action.lower() for action in result.recommended_actions)
