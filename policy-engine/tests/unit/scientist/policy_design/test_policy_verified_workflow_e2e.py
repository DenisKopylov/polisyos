from __future__ import annotations

from decimal import Decimal

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef
from polisyos.core.contracts.foundry import StateSnapshotRef
from polisyos.core.registry import build_default_registry_bundle
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.execute.executor import put_state_snapshot
from polisyos.lex.knowledge.types import LegalFactResult, LegalSourceAnchor, LegalSourceBundle
from polisyos.scientist.adapters.foundry_bridge import DefaultFoundryPort
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins.state_keys import REPORT_GOVERNANCE_REPORT_REF
from polisyos.scientist.policy_verified import (
    load_source_verification_report,
    load_verified_policy_report,
)
from polisyos.scientist.policy_verified.models import LegalCandidatePack, LegalSourcePack
from polisyos.scientist.workflows.builder import run_selected_workflow


def _passing_judge_verdict() -> dict[str, object]:
    return {
        "per_judge": {
            name: {"judge_name": name, "passed": True, "is_fatal": True}
            for name in (
                "structural",
                "statistical",
                "robustness",
                "governance",
                "reproducibility",
                "compute",
            )
        },
        "composite_decision": "promote",
        "blocking_failures": [],
        "warnings": [],
    }


def _put_data_snapshot(
    store: FileSystemCAS, state_snapshot_ref: StateSnapshotRef
) -> DataSnapshotRef:
    snapshot = DataSnapshot(data_ref=state_snapshot_ref)
    ref = store.put_json(
        snapshot,
        PutOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.1.0"),
        ),
    )
    return DataSnapshotRef(artifact_id=ref.artifact_id)


def test_policy_verified_workflow_runs_end_to_end_with_verified_artifacts(
    monkeypatch, tmp_path
) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store)
    base_state = GlobalState.empty(n_agents=5, n_firms=2)
    snapshot_ref_payload = put_state_snapshot(store, state=base_state, step=0)
    state_snapshot_ref = StateSnapshotRef(artifact_id=snapshot_ref_payload.artifact_id)
    data_snapshot_ref = _put_data_snapshot(store, state_snapshot_ref)

    class _FakeLegalToolkit:
        def assemble_legal_candidate_pack(
            self, query, *, jurisdiction="UA", domain=None, as_of=None
        ):
            del jurisdiction, domain, as_of
            return LegalCandidatePack(
                request_id="toolkit",
                queries=[query],
                fact_hits=[
                    LegalFactResult(
                        fact_id="lf-1",
                        subject_name="Держава",
                        predicate="requires",
                        object_name="ліцензія",
                        fact_text="Ліцензія є обов'язковою для діяльності перевізника.",
                        confidence=0.93,
                        norm_type="obligation",
                        norm_type_canon="obligation",
                        source_quote_uk="Ліцензія є обов'язковою для діяльності перевізника.",
                        trust_tier="grounded_fact",
                        grounding_status="exact_quote",
                        canonical_status="canonicalized",
                        legal_unit_subtype="core_normative_clause",
                        route_class="reasoning",
                        doc_id="doc-1",
                        version_id="v-1",
                        jurisdiction="UA",
                        top_domain="transport",
                        doc_name="Mock transport law",
                        doc_reestr_code="123",
                        provision_anchor="art:1",
                        provision_citation="стаття 1",
                        similarity=0.99,
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
                        doc_name="Mock transport law",
                        doc_reestr_code="123",
                        source_family="law",
                        primary_anchors=[
                            LegalSourceAnchor(
                                doc_id="doc-1",
                                version_id="v-1",
                                anchor="art:1",
                                citation_label="стаття 1",
                                provision_text="Ліцензія є обов'язковою для діяльності перевізника.",
                                struct_kind="article",
                                section_role="normative_unit",
                                legal_unit_subtype="core_normative_clause",
                                route_class="reasoning",
                                context_prefix=["Розділ I"],
                            )
                        ],
                        candidate_fact_ids=["lf-1"],
                    )
                ],
            )

    monkeypatch.setattr(
        "polisyos.scientist.policy_verified.service._build_legal_toolkit",
        lambda ctx, state: _FakeLegalToolkit(),
    )

    state = ExperimentState(
        run_id="R_policy_verified_e2e",
        inputs={
            "registry_bundle_ref": registry_bundle.bundle_ref,
            "data_snapshot_ref": data_snapshot_ref,
        },
        params={
            "policy_answer_mode": "verified_async",
            "policy_question": "Як реформувати ліцензування перевізників?",
            "policy_request_domain": "transport",
            "initial_rate": Decimal("0.1"),
            "judge_verdict": _passing_judge_verdict(),
        },
    )

    result = run_selected_workflow(state, store=store, foundry=DefaultFoundryPort())

    assert result.state.policy_request_ref is not None
    assert result.state.legal_candidate_pack_ref is not None
    assert result.state.legal_source_pack_ref is not None
    assert result.state.source_verification_report_ref is not None
    assert result.state.policy_option_set_ref is not None
    assert result.state.verified_policy_report_ref is not None
    assert result.state.inputs.get("trinity_bundle_ref") is not None
    assert "workflow_report" in result.state.reports_index

    verification_report = load_source_verification_report(
        store, result.state.source_verification_report_ref
    )
    assert len(verification_report.verified_claims) == 1
    assert verification_report.verified_claims[0].claim_type == "obligation"

    verified_policy_report = load_verified_policy_report(
        store, result.state.verified_policy_report_ref
    )
    assert verified_policy_report.verified_findings
    assert verified_policy_report.policy_options
    assert (
        result.state.reports_index[REPORT_GOVERNANCE_REPORT_REF].kind
        == "scientist.governance_report"
    )
