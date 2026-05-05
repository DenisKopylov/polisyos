from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.claims.lifecycle import AppendOnlyClaimLedger
from polisyos.scientist.claims.models import (
    ClaimPublishability,
    ClaimRecord,
    ClaimSupportStatus,
    ClaimType,
)
from polisyos.scientist.orchestrator.decision_card import DecisionCard
from polisyos.scientist.orchestrator.publisher import (
    DecisionGradeExport,
    OutputAudience,
    OutputOmissionRecord,
    assert_decision_grade_exports_consistent,
    compile_decision_grade_export,
    compile_decision_grade_exports,
    decision_grade_export_inputs,
    load_decision_grade_export,
    persist_decision_grade_export,
)
from polisyos.scientist.research_dag.models import (
    ResearchDAGArtifact,
    ResearchDAGEdge,
    ResearchDAGNode,
    ResearchEdgeType,
    ResearchNodeType,
)
from polisyos.scientist.search.readiness import DecisionReadiness
from pydantic import ValidationError


def _ref(seed: str, *, kind: str = "scientist.test") -> ArtifactRef:
    return ArtifactRef(
        artifact_id=ArtifactID.model_validate(
            "sha256:" + hashlib.sha256(seed.encode("utf-8")).hexdigest()
        ),
        kind=kind,
        media_type="application/json",
    )


def _claim(
    claim_id: str,
    *,
    publishability: ClaimPublishability,
) -> ClaimRecord:
    blocked = publishability is ClaimPublishability.BLOCKED
    return ClaimRecord(
        claim_id=claim_id,
        run_id="run_compiler",
        claim_type=ClaimType.FACTUAL,
        text=f"{claim_id} decision claim.",
        support_status=ClaimSupportStatus.CONTESTED if blocked else ClaimSupportStatus.SUPPORTED,
        publishability=publishability,
        readiness_level=DecisionReadiness.ANALYST_ADVISORY,
        evidence_refs=[_ref(f"{claim_id}-evidence", kind="scientist.source_snippet")],
        counterevidence_refs=[_ref(f"{claim_id}-counter", kind="scientist.source_snippet")]
        if blocked
        else [],
        blocked_reasons=["counterevidence unresolved"] if blocked else [],
        source_attribution=["source A"] if not blocked else [],
    )


def _ledger() -> AppendOnlyClaimLedger:
    return AppendOnlyClaimLedger(
        run_id="run_compiler",
        current_claims=[
            _claim("claim_public", publishability=ClaimPublishability.PUBLISHABLE),
            _claim("claim_blocked", publishability=ClaimPublishability.BLOCKED),
        ],
    )


def _legacy_ledger_without_dag_ref() -> AppendOnlyClaimLedger:
    return AppendOnlyClaimLedger(
        run_id="run_legacy_dag",
        current_claims=[
            ClaimRecord(
                claim_id="claim_public",
                run_id="run_legacy_dag",
                claim_type=ClaimType.FACTUAL,
                text="Legacy DAG-compatible claim.",
                support_status=ClaimSupportStatus.SUPPORTED,
                publishability=ClaimPublishability.PUBLISHABLE,
                readiness_level=DecisionReadiness.ANALYST_ADVISORY,
                evidence_refs=[_ref("legacy-evidence")],
            )
        ],
    )


def _dag() -> ResearchDAGArtifact:
    source_ref = _ref("source", kind="scientist.source")
    return ResearchDAGArtifact(
        run_id="run_compiler",
        workflow_id="scientist_policy_design",
        created_at=datetime(2026, 4, 28, tzinfo=UTC),
        claim_ledger_ref=_ref("claims", kind="scientist.claim_ledger_v2"),
        nodes=[
            ResearchDAGNode(
                node_id="question",
                node_type=ResearchNodeType.QUESTION,
                run_id="run_compiler",
                workflow_id="scientist_policy_design",
                producer="planner",
                summary="Normalize policy question.",
            ),
            ResearchDAGNode(
                node_id="source",
                node_type=ResearchNodeType.SOURCE_READ,
                run_id="run_compiler",
                workflow_id="scientist_policy_design",
                producer="safe_fetch",
                summary="Read public source.",
                artifact_refs=[source_ref],
                output_fingerprint="source-fingerprint",
            ),
            ResearchDAGNode(
                node_id="synthesis",
                node_type=ResearchNodeType.SYNTHESIS,
                run_id="run_compiler",
                workflow_id="scientist_policy_design",
                producer="compiler",
                summary="Synthesize approved claim.",
                claim_ids=["claim_public", "claim_blocked"],
            ),
        ],
        edges=[
            ResearchDAGEdge(
                source_node_id="question",
                target_node_id="source",
                edge_type=ResearchEdgeType.DEPENDS_ON,
            ),
            ResearchDAGEdge(
                source_node_id="source",
                target_node_id="synthesis",
                edge_type=ResearchEdgeType.SUPPORTS,
                claim_ids=["claim_public"],
            ),
        ],
    )


def _legacy_dag_without_claim_ref() -> ResearchDAGArtifact:
    return ResearchDAGArtifact(
        run_id="run_legacy_dag",
        workflow_id="scientist_policy_design",
        created_at=datetime(2026, 4, 28, tzinfo=UTC),
        nodes=[
            ResearchDAGNode(
                node_id="question",
                node_type=ResearchNodeType.QUESTION,
                run_id="run_legacy_dag",
                workflow_id="scientist_policy_design",
                producer="planner",
                summary="Normalize legacy DAG question.",
            )
        ],
    )


def test_compiles_four_audience_tiers_from_same_claim_ledger_and_dag() -> None:
    claims_ref = _ref("claims", kind="scientist.claim_ledger_v2")
    dag_ref = _ref("dag", kind="scientist.research_dag")

    exports = compile_decision_grade_exports(
        run_id="run_compiler",
        claims_ref=claims_ref,
        research_dag_ref=dag_ref,
        claim_ledger=_ledger(),
        research_dag=_dag(),
        decision_payload={"policy_summary": "Approved claim summary."},
    )

    assert set(exports) == set(OutputAudience)
    assert_decision_grade_exports_consistent(exports.values())
    public = exports[OutputAudience.PUBLIC]
    reviewer = exports[OutputAudience.REVIEWER]
    expert = exports[OutputAudience.EXPERT]
    machine = exports[OutputAudience.MACHINE]

    assert public.payload["approved_claims"][0]["claim_id"] == "claim_public"
    assert public.payload["blocked_claim_summary"]["blocked_claims_omitted"] is True
    assert public.omissions
    assert (
        reviewer.payload["blocked_claim_summary"]["blocked_claims"][0]["claim_id"]
        == "claim_blocked"
    )
    assert expert.payload["methods"]["workflow_id"] == "scientist_policy_design"
    assert machine.payload["frontend_trust_view"]["claims_ref"]["artifact_id"] == str(
        claims_ref.artifact_id
    )
    assert machine.payload["frontend_trust_view"]["research_step_count"] == 3


def test_decision_grade_export_persists_with_claim_and_dag_lineage(tmp_path) -> None:
    claims_ref = _ref("claims", kind="scientist.claim_ledger_v2")
    dag_ref = _ref("dag", kind="scientist.research_dag")
    export = compile_decision_grade_export(
        run_id="run_compiler",
        audience=OutputAudience.MACHINE,
        claims_ref=claims_ref,
        research_dag_ref=dag_ref,
        claim_ledger=_ledger(),
        research_dag=_dag(),
    )

    inputs = decision_grade_export_inputs(export)
    assert [item.role for item in inputs] == ["claims", "research_dag"]

    store = FileSystemCAS(tmp_path)
    export_ref = persist_decision_grade_export(store, export)

    assert export_ref.kind == "scientist.decision_grade_export"
    assert load_decision_grade_export(store, export_ref) == export


def test_compiler_rejects_mismatched_run_or_dag_claim_ref() -> None:
    claims_ref = _ref("claims", kind="scientist.claim_ledger_v2")
    dag_ref = _ref("dag", kind="scientist.research_dag")

    with pytest.raises(ValueError, match="claim ledger run_id"):
        compile_decision_grade_export(
            run_id="different_run",
            audience=OutputAudience.MACHINE,
            claims_ref=claims_ref,
            research_dag_ref=dag_ref,
            claim_ledger=_ledger(),
            research_dag=_dag(),
        )

    with pytest.raises(ValueError, match="claim_ledger_ref"):
        compile_decision_grade_export(
            run_id="run_compiler",
            audience=OutputAudience.MACHINE,
            claims_ref=_ref("different-claims", kind="scientist.claim_ledger_v2"),
            research_dag_ref=dag_ref,
            claim_ledger=_ledger(),
            research_dag=_dag(),
        )

    legacy = compile_decision_grade_export(
        run_id="run_legacy_dag",
        audience=OutputAudience.MACHINE,
        claims_ref=claims_ref,
        research_dag_ref=dag_ref,
        claim_ledger=_legacy_ledger_without_dag_ref(),
        research_dag=_legacy_dag_without_claim_ref(),
    )
    assert legacy.payload["trust_provenance"]["claim_count"] == 1


def test_public_export_rejects_hidden_benchmark_private_refs() -> None:
    claims_ref = _ref("claims", kind="scientist.claim_ledger_v2")
    dag_ref = _ref("dag", kind="scientist.research_dag")

    with pytest.raises(ValidationError, match="forbidden value"):
        DecisionGradeExport(
            run_id="run_compiler",
            audience=OutputAudience.PUBLIC,
            claims_ref=claims_ref,
            research_dag_ref=dag_ref,
            payload={
                "trust_provenance": {
                    "claims_ref": {
                        "artifact_id": str(claims_ref.artifact_id),
                        "kind": claims_ref.kind,
                        "media_type": claims_ref.media_type,
                    },
                    "research_dag_ref": {
                        "artifact_id": str(dag_ref.artifact_id),
                        "kind": dag_ref.kind,
                        "media_type": dag_ref.media_type,
                    },
                },
                "benchmark_note": "hidden_holdout_answer_ref",
            },
        )


def test_blockers_cannot_be_silently_omitted() -> None:
    claims_ref = _ref("claims", kind="scientist.claim_ledger_v2")
    dag_ref = _ref("dag", kind="scientist.research_dag")

    with pytest.raises(ValidationError, match="silently omitted"):
        DecisionGradeExport(
            run_id="run_compiler",
            audience=OutputAudience.PUBLIC,
            claims_ref=claims_ref,
            research_dag_ref=dag_ref,
            payload={
                "trust_provenance": {
                    "claims_ref": {
                        "artifact_id": str(claims_ref.artifact_id),
                        "kind": claims_ref.kind,
                        "media_type": claims_ref.media_type,
                    },
                    "research_dag_ref": {
                        "artifact_id": str(dag_ref.artifact_id),
                        "kind": dag_ref.kind,
                        "media_type": dag_ref.media_type,
                    },
                },
                "blocked_claim_summary": {"blocked_count": 1, "blocked_claims": []},
            },
        )

    with pytest.raises(ValidationError, match="silently omitted"):
        DecisionGradeExport(
            run_id="run_compiler",
            audience=OutputAudience.PUBLIC,
            claims_ref=claims_ref,
            research_dag_ref=dag_ref,
            payload={
                "trust_provenance": {
                    "claims_ref": {
                        "artifact_id": str(claims_ref.artifact_id),
                        "kind": claims_ref.kind,
                        "media_type": claims_ref.media_type,
                    },
                    "research_dag_ref": {
                        "artifact_id": str(dag_ref.artifact_id),
                        "kind": dag_ref.kind,
                        "media_type": dag_ref.media_type,
                    },
                },
                "blocked_claim_summary": {"blocked_count": 1, "blocked_claims": []},
            },
            omissions=[
                OutputOmissionRecord(
                    field_path="claim_ledger_export.claims[claim_draft]",
                    audience=OutputAudience.PUBLIC,
                    reason="draft claim hidden from public audience",
                )
            ],
        )

    with pytest.raises(ValidationError, match="cannot be blank"):
        OutputOmissionRecord(
            field_path="blocked_claim_summary.blocked_claims",
            audience=OutputAudience.PUBLIC,
            reason=" ",
        )


def test_reviewer_export_missing_blocked_claims_fails() -> None:
    claims_ref = _ref("claims", kind="scientist.claim_ledger_v2")
    dag_ref = _ref("dag", kind="scientist.research_dag")

    with pytest.raises(ValidationError, match="must include blocked claims"):
        DecisionGradeExport(
            run_id="run_compiler",
            audience=OutputAudience.REVIEWER,
            claims_ref=claims_ref,
            research_dag_ref=dag_ref,
            payload={
                "trust_provenance": {
                    "claims_ref": {
                        "artifact_id": str(claims_ref.artifact_id),
                        "kind": claims_ref.kind,
                        "media_type": claims_ref.media_type,
                    },
                    "research_dag_ref": {
                        "artifact_id": str(dag_ref.artifact_id),
                        "kind": dag_ref.kind,
                        "media_type": dag_ref.media_type,
                    },
                },
                "blocked_claim_summary": {"blocked_count": 1, "blocked_claims": []},
            },
        )


def test_machine_export_requires_refs_and_decision_card_bridge_keeps_legacy_loadable() -> None:
    claims_ref = _ref("claims", kind="scientist.claim_ledger_v2")
    dag_ref = _ref("dag", kind="scientist.research_dag")

    with pytest.raises(ValidationError, match="Field required"):
        DecisionGradeExport(
            run_id="run_compiler",
            audience=OutputAudience.MACHINE,
            research_dag_ref=dag_ref,
            payload={"trust_provenance": {}},
        )

    machine = compile_decision_grade_export(
        run_id="run_compiler",
        audience=OutputAudience.MACHINE,
        claims_ref=claims_ref,
        research_dag_ref=dag_ref,
        claim_ledger=_ledger(),
        research_dag=_dag(),
        decision_payload={"policy_summary": "Compiler-backed card."},
    )
    card = DecisionCard.from_decision_grade_export(machine)

    assert card.trust_provenance is not None
    assert card.trust_provenance.claims_ref == str(claims_ref.artifact_id)
    assert "Trust And Provenance" in card.render_markdown()

    legacy_card = DecisionCard.from_packet(
        SimpleNamespace(
            run_id="legacy",
            generated_at="2026-04-28T00:00:00+00:00",
            feedback={"verdict": "APPROVE", "issues": []},
            simulation_results={},
            policy_ir=None,
            diagnostics_summary={},
        )
    )
    assert legacy_card.run_id == "legacy"
    assert legacy_card.trust_provenance is None
