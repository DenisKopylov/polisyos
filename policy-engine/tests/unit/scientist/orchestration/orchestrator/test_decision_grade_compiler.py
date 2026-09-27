from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.core.contracts.c4_persisted_profiles import c4_semantic_digest
from polisyos.scientist.evidence.claims.export import (
    ClaimExportAudience,
    ClaimLedgerExport,
    _format_resolved_claim_ledger,
)
from polisyos.scientist.evidence.claims.head_index import (
    CLAIM_LEDGER_AUTHORITY_PURPOSE,
    ClaimBridgePendingProjection,
    ClaimLedgerHeadStatement,
    ClaimLedgerOwnerKey,
    ClaimLedgerOwnerKeyDerivationInput,
    PersistedClaimLedgerHead,
    derive_claim_ledger_owner_scope_ref,
)
from polisyos.scientist.evidence.claims.lifecycle import AppendOnlyClaimLedger
from polisyos.scientist.evidence.claims.models import (
    ClaimPublishability,
    ClaimRecord,
    ClaimSupportStatus,
    ClaimType,
)
from polisyos.scientist.methods.research_dag.models import (
    ResearchDAGArtifact,
    ResearchDAGEdge,
    ResearchDAGNode,
    ResearchEdgeType,
    ResearchNodeType,
)
from polisyos.scientist.methods.search.readiness import DecisionReadiness
from polisyos.scientist.orchestration.orchestrator.decision_card import DecisionCard
from polisyos.scientist.publishing.publisher import (
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


@dataclass(frozen=True, slots=True)
class _StableClaimOwner:
    ledger: AppendOnlyClaimLedger
    head: PersistedClaimLedgerHead

    def resolve_current(self, *, owner_key: ClaimLedgerOwnerKey) -> PersistedClaimLedgerHead:
        assert owner_key == self.head.statement.owner_key
        return self.head

    def export_current(
        self,
        *,
        owner_key: ClaimLedgerOwnerKey,
        audience: ClaimExportAudience,
    ) -> ClaimLedgerExport:
        assert owner_key == self.head.statement.owner_key
        return _format_resolved_claim_ledger(
            self.ledger,
            audience=audience,
            pending_projection=ClaimBridgePendingProjection(
                completed_batch_denominator_established=True,
            ),
        )


def _stable_owner(
    ledger: AppendOnlyClaimLedger,
    claims_ref: ArtifactRef,
) -> tuple[_StableClaimOwner, ClaimLedgerOwnerKey]:
    derivation = ClaimLedgerOwnerKeyDerivationInput(
        base_claims_ref=claims_ref,
        base_claims_content_hash=str(claims_ref.artifact_id),
        requested_authority_purpose=CLAIM_LEDGER_AUTHORITY_PURPOSE,
    )
    owner_key = ClaimLedgerOwnerKey(
        scope_ref=derive_claim_ledger_owner_scope_ref(derivation),
        claim_owner_ref="fixture-decision-grade-owner",
        authority_purpose=CLAIM_LEDGER_AUTHORITY_PURPOSE,
        derivation_input=derivation,
    )
    statement = ClaimLedgerHeadStatement(
        root_identity=str(_ref("root-identity").artifact_id),
        root_receipt_ref=_ref("root", kind="scientist.claims.ledger_root"),
        root_receipt_content_hash=str(_ref("root-content").artifact_id),
        owner_key=owner_key,
        ledger_artifact_ref=claims_ref,
        ledger_raw_cas_hash=str(claims_ref.artifact_id),
        generation=0,
        predecessor_head_ref=None,
        bridge_result_refs=(),
        issuance_verifier_receipt_ref=_ref(
            "issuance-verifier",
            kind="scientist.claims.ledger_root_verification",
        ),
        issuance_verifier_receipt_content_hash=str(_ref("issuance-verifier-content").artifact_id),
    )
    head = PersistedClaimLedgerHead(
        head_ref=_ref("head", kind="scientist.claims.ledger_head"),
        head_content_hash=c4_semantic_digest("claim_ledger_head", statement),
        statement=statement,
    )
    return _StableClaimOwner(ledger=ledger, head=head), owner_key


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
    claim_owner, owner_key = _stable_owner(_ledger(), claims_ref)

    exports = compile_decision_grade_exports(
        run_id="run_compiler",
        research_dag_ref=dag_ref,
        claim_owner=claim_owner,
        claim_owner_key=owner_key,
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
    current_head = public.payload["claim_current_head"]
    assert current_head["head_ref"]["artifact_id"] == str(claim_owner.head.head_ref.artifact_id)
    assert current_head["ledger_artifact_ref"]["artifact_id"] == str(claims_ref.artifact_id)
    assert current_head["predicate_class"] == "independently_reconciled"
    forged = public.model_dump(mode="json")
    forged["payload"]["claim_current_head"]["head_content_hash"] = str(
        _ref("forged-current-head").artifact_id
    )
    with pytest.raises(
        ValidationError,
        match="decision-grade claim current-head trust mismatch",
    ):
        DecisionGradeExport.model_validate(forged)
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
    claim_owner, owner_key = _stable_owner(_ledger(), claims_ref)
    export = compile_decision_grade_export(
        run_id="run_compiler",
        audience=OutputAudience.MACHINE,
        research_dag_ref=dag_ref,
        claim_owner=claim_owner,
        claim_owner_key=owner_key,
        research_dag=_dag(),
    )

    inputs = decision_grade_export_inputs(export)
    assert [item.role for item in inputs] == ["claims", "research_dag"]

    store = FileSystemCAS(tmp_path)
    export_ref = persist_decision_grade_export(
        store,
        export,
        claim_owner=claim_owner,
        claim_owner_key=owner_key,
    )

    assert export_ref.kind == "scientist.decision_grade_export"
    assert load_decision_grade_export(store, export_ref) == export

    substituted = export.model_copy(
        update={
            "payload": {
                **export.payload,
                "claim_ledger_export": {
                    **export.payload["claim_ledger_export"],
                    "claims": [],
                },
            }
        }
    )
    with pytest.raises(ValueError, match="claim_owner_projection_mismatch"):
        persist_decision_grade_export(
            store,
            substituted,
            claim_owner=claim_owner,
            claim_owner_key=owner_key,
        )


def test_decision_grade_export_binds_selected_view_in_lineage_and_trust(tmp_path) -> None:
    claims_profile = "sha256:" + "a" * 64
    dag_profile = "sha256:" + "b" * 64
    claims_ref = _ref("claims", kind="scientist.claim_ledger_v2").model_copy(
        update={"manifest_profile_sha256": claims_profile}
    )
    dag_ref = _ref("dag", kind="scientist.research_dag").model_copy(
        update={"manifest_profile_sha256": dag_profile}
    )
    claim_owner, owner_key = _stable_owner(_ledger(), claims_ref)
    dag = _dag().model_copy(update={"claim_ledger_ref": claims_ref})

    export = compile_decision_grade_export(
        run_id="run_compiler",
        audience=OutputAudience.MACHINE,
        research_dag_ref=dag_ref,
        claim_owner=claim_owner,
        claim_owner_key=owner_key,
        research_dag=dag,
    )

    assert decision_grade_export_inputs(export) == [
        InputRef(
            artifact_id=claims_ref.artifact_id,
            role="claims",
            manifest_profile_sha256=claims_profile,
        ),
        InputRef(
            artifact_id=dag_ref.artifact_id,
            role="research_dag",
            manifest_profile_sha256=dag_profile,
        ),
    ]
    trust = export.payload["trust_provenance"]
    assert trust["claims_ref"]["manifest_profile_sha256"] == claims_profile
    assert trust["research_dag_ref"]["manifest_profile_sha256"] == dag_profile
    assert export.schema_version == "1.1"
    assert export.payload["schema_version"] == "1.1"
    assert export.payload["trust_provenance"]["schema_version"] == "1.1"

    for nested_schema in ("payload", "trust_provenance"):
        forged = export.model_dump(mode="json")
        nested = forged["payload"]
        if nested_schema == "trust_provenance":
            nested = nested["trust_provenance"]
        nested["schema_version"] = "1.0"
        with pytest.raises(ValidationError, match="schema_version_mismatch"):
            DecisionGradeExport.model_validate(forged)

    for replacement_profile in (None, "sha256:" + "c" * 64):
        forged = export.model_dump(mode="json")
        claims_payload = forged["payload"]["trust_provenance"]["claims_ref"]
        if replacement_profile is None:
            claims_payload.pop("manifest_profile_sha256")
        else:
            claims_payload["manifest_profile_sha256"] = replacement_profile
        with pytest.raises(ValidationError, match="claims_ref does not match"):
            DecisionGradeExport.model_validate(forged)

    store = FileSystemCAS(tmp_path / "cas")
    forged_export = export.model_copy(
        update={
            "payload": {
                **export.payload,
                "trust_provenance": {
                    **export.payload["trust_provenance"],
                    "claims_ref": {
                        "artifact_id": str(claims_ref.artifact_id),
                        "kind": claims_ref.kind,
                        "media_type": claims_ref.media_type,
                    },
                },
            }
        }
    )
    with pytest.raises(ValidationError, match="claims_ref does not match"):
        persist_decision_grade_export(
            store,
            forged_export,
            claim_owner=claim_owner,
            claim_owner_key=owner_key,
        )
    with pytest.raises(ValueError, match="lineage_inputs_missing_or_unbound"):
        persist_decision_grade_export(
            store,
            export,
            claim_owner=claim_owner,
            claim_owner_key=owner_key,
            inputs=[
                InputRef(artifact_id=claims_ref.artifact_id, role="claims"),
                InputRef(artifact_id=dag_ref.artifact_id, role="research_dag"),
            ],
        )

    export_ref = persist_decision_grade_export(
        store,
        export,
        claim_owner=claim_owner,
        claim_owner_key=owner_key,
    )
    assert store.get_manifest(export_ref).inputs == decision_grade_export_inputs(export)
    assert load_decision_grade_export(store, export_ref) == export


def test_decision_grade_export_v1_projection_replays_but_cannot_be_re_admitted(
    tmp_path,
) -> None:
    claims_ref = _ref("claims", kind="scientist.claim_ledger_v2").model_copy(
        update={"manifest_profile_sha256": "sha256:" + "a" * 64}
    )
    dag_ref = _ref("dag", kind="scientist.research_dag").model_copy(
        update={"manifest_profile_sha256": "sha256:" + "b" * 64}
    )
    claim_owner, owner_key = _stable_owner(_ledger(), claims_ref)
    export = compile_decision_grade_export(
        run_id="run_compiler",
        audience=OutputAudience.MACHINE,
        research_dag_ref=dag_ref,
        claim_owner=claim_owner,
        claim_owner_key=owner_key,
        research_dag=_dag().model_copy(update={"claim_ledger_ref": claims_ref}),
    )
    legacy_projection = export.model_dump(mode="json")
    legacy_projection["schema_version"] = "1.0"
    legacy_projection["payload"]["schema_version"] = "1.0"

    def strip_selector(value):
        if isinstance(value, dict):
            result = {key: strip_selector(item) for key, item in value.items()}
            if {"artifact_id", "kind", "media_type"}.issubset(result):
                result.pop("manifest_profile_sha256", None)
            return result
        if isinstance(value, list):
            return [strip_selector(item) for item in value]
        return value

    legacy_projection["payload"]["trust_provenance"] = strip_selector(
        legacy_projection["payload"]["trust_provenance"]
    )
    legacy_projection["payload"]["trust_provenance"]["schema_version"] = "1.0"
    legacy_projection["payload"]["refs"] = strip_selector(legacy_projection["payload"]["refs"])
    legacy_projection["payload"]["frontend_trust_view"] = strip_selector(
        legacy_projection["payload"]["frontend_trust_view"]
    )

    replayed = DecisionGradeExport.model_validate(legacy_projection)

    assert replayed.schema_version == "1.0"
    assert replayed.model_dump(mode="json") == legacy_projection
    canon_spec = CanonSpec(forbid_floats=False)
    assert to_canonical_bytes(replayed, canon_spec) == to_canonical_bytes(
        legacy_projection, canon_spec
    )
    with pytest.raises(ValueError, match="legacy.*not_current_admission"):
        persist_decision_grade_export(
            FileSystemCAS(tmp_path / "cas"),
            replayed,
            claim_owner=claim_owner,
            claim_owner_key=owner_key,
        )


def test_compiler_rejects_mismatched_run_or_dag_claim_ref() -> None:
    claims_ref = _ref("claims", kind="scientist.claim_ledger_v2")
    dag_ref = _ref("dag", kind="scientist.research_dag")
    claim_owner, owner_key = _stable_owner(_ledger(), claims_ref)

    with pytest.raises(ValueError, match="claim ledger run_id"):
        compile_decision_grade_export(
            run_id="different_run",
            audience=OutputAudience.MACHINE,
            research_dag_ref=dag_ref,
            claim_owner=claim_owner,
            claim_owner_key=owner_key,
            research_dag=_dag(),
        )

    different_ref = _ref("different-claims", kind="scientist.claim_ledger_v2")
    different_owner, different_key = _stable_owner(_ledger(), different_ref)
    with pytest.raises(ValueError, match="claim_ledger_ref"):
        compile_decision_grade_export(
            run_id="run_compiler",
            audience=OutputAudience.MACHINE,
            research_dag_ref=dag_ref,
            claim_owner=different_owner,
            claim_owner_key=different_key,
            research_dag=_dag(),
        )

    legacy_owner, legacy_key = _stable_owner(
        _legacy_ledger_without_dag_ref(),
        claims_ref,
    )
    legacy = compile_decision_grade_export(
        run_id="run_legacy_dag",
        audience=OutputAudience.MACHINE,
        research_dag_ref=dag_ref,
        claim_owner=legacy_owner,
        claim_owner_key=legacy_key,
        research_dag=_legacy_dag_without_claim_ref(),
    )
    assert legacy.payload["trust_provenance"]["claim_count"] == 1


def test_stale_caller_ledger_cannot_bypass_current_head_public_export() -> None:
    current_claims_ref = _ref("claims", kind="scientist.claim_ledger_v2")
    stale_claims_ref = _ref("stale-claims", kind="scientist.claim_ledger_v2")
    dag_ref = _ref("dag", kind="scientist.research_dag")
    claim_owner, owner_key = _stable_owner(_ledger(), current_claims_ref)
    stale_dag = _dag().model_copy(update={"claim_ledger_ref": stale_claims_ref})

    with pytest.raises(ValueError, match="claim_ledger_ref"):
        compile_decision_grade_export(
            run_id="run_compiler",
            audience=OutputAudience.PUBLIC,
            research_dag_ref=dag_ref,
            claim_owner=claim_owner,
            claim_owner_key=owner_key,
            research_dag=stale_dag,
        )

    current = compile_decision_grade_export(
        run_id="run_compiler",
        audience=OutputAudience.PUBLIC,
        research_dag_ref=dag_ref,
        claim_owner=claim_owner,
        claim_owner_key=owner_key,
        research_dag=_dag(),
    )
    assert current.claims_ref == current_claims_ref
    assert current.payload["claim_current_head"]["ledger_artifact_ref"]["artifact_id"] == str(
        current_claims_ref.artifact_id
    )
    assert current.payload["trust_provenance"]["claims_ref"]["artifact_id"] == str(
        current_claims_ref.artifact_id
    )


def test_public_export_rejects_hidden_benchmark_private_refs() -> None:
    claims_ref = _ref("claims", kind="scientist.claim_ledger_v2")
    dag_ref = _ref("dag", kind="scientist.research_dag")
    claim_owner, owner_key = _stable_owner(_ledger(), claims_ref)
    valid = compile_decision_grade_export(
        run_id="run_compiler",
        audience=OutputAudience.PUBLIC,
        research_dag_ref=dag_ref,
        claim_owner=claim_owner,
        claim_owner_key=owner_key,
        research_dag=_dag(),
    ).model_dump(mode="json")
    valid["payload"]["benchmark_note"] = "hidden_holdout_answer_ref"

    with pytest.raises(ValidationError, match="forbidden value"):
        DecisionGradeExport.model_validate(valid)


def test_blockers_cannot_be_silently_omitted() -> None:
    claims_ref = _ref("claims", kind="scientist.claim_ledger_v2")
    dag_ref = _ref("dag", kind="scientist.research_dag")
    claim_owner, owner_key = _stable_owner(_ledger(), claims_ref)
    valid = compile_decision_grade_export(
        run_id="run_compiler",
        audience=OutputAudience.PUBLIC,
        research_dag_ref=dag_ref,
        claim_owner=claim_owner,
        claim_owner_key=owner_key,
        research_dag=_dag(),
    ).model_dump(mode="json")
    valid["omissions"] = []

    with pytest.raises(ValidationError, match="silently omitted"):
        DecisionGradeExport.model_validate(valid)

    unrelated_omission = {
        **valid,
        "omissions": [
            OutputOmissionRecord(
                field_path="claim_ledger_export.claims[claim_draft]",
                audience=OutputAudience.PUBLIC,
                reason="draft claim hidden from public audience",
            ).model_dump(mode="json")
        ],
    }
    with pytest.raises(ValidationError, match="silently omitted"):
        DecisionGradeExport.model_validate(unrelated_omission)

    with pytest.raises(ValidationError, match="cannot be blank"):
        OutputOmissionRecord(
            field_path="blocked_claim_summary.blocked_claims",
            audience=OutputAudience.PUBLIC,
            reason=" ",
        )


def test_reviewer_export_missing_blocked_claims_fails() -> None:
    claims_ref = _ref("claims", kind="scientist.claim_ledger_v2")
    dag_ref = _ref("dag", kind="scientist.research_dag")
    claim_owner, owner_key = _stable_owner(_ledger(), claims_ref)
    invalid = compile_decision_grade_export(
        run_id="run_compiler",
        audience=OutputAudience.REVIEWER,
        research_dag_ref=dag_ref,
        claim_owner=claim_owner,
        claim_owner_key=owner_key,
        research_dag=_dag(),
    ).model_dump(mode="json")
    invalid["payload"]["blocked_claim_summary"]["blocked_claims"] = []
    invalid["payload"]["claim_ledger_export"]["claims"] = [
        row
        for row in invalid["payload"]["claim_ledger_export"]["claims"]
        if row["claim_id"] != "claim_blocked"
    ]

    with pytest.raises(ValidationError, match="must include blocked claims"):
        DecisionGradeExport.model_validate(invalid)


def test_machine_export_requires_refs_and_decision_card_bridge_keeps_legacy_loadable() -> None:
    claims_ref = _ref("claims", kind="scientist.claim_ledger_v2")
    dag_ref = _ref("dag", kind="scientist.research_dag")
    claim_owner, owner_key = _stable_owner(_ledger(), claims_ref)

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
        research_dag_ref=dag_ref,
        claim_owner=claim_owner,
        claim_owner_key=owner_key,
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
