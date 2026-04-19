from __future__ import annotations

from datetime import datetime

import pytest

from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain
from polisyos.ir.governance.problem_frame import ProblemFrame as IRProblemFrame
from polisyos.ir.model_spec import ModelSpec
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.agent.protocols import ProblemFrame as AgentProblemFrame
from polisyos.scientist.agent.rag import (
    CASRAGIndex,
    HashEmbeddingBackend,
    RAGCaseEntry,
    RAGSearchResult,
    build_or_load_rag_index,
    format_few_shot_block,
)


def _make_trinity(problem_id: str, domain: ProblemDomain) -> TrinityBundle:
    problem_frame = IRProblemFrame(
        problem_id=problem_id,
        domain=domain,
        narrative=f"Policy challenge for {problem_id}",
    )
    policy_spec = PolicySpec(
        policy_id=f"policy_{problem_id}",
        interventions=[
            InterventionSpec(
                intervention_id=f"intv_{problem_id}",
                kind="tax_subsidy",
                target={
                    "kind": "predicate",
                    "field": "income",
                    "operator": "<",
                    "value": "1000",
                },
                schedule={"start_step": 0, "duration_steps": 12},
                params={"rate": "0.2"},
            )
        ],
    )
    model_spec = ModelSpec(
        model_id=f"model_{problem_id}",
        data_snapshot_ref="sha256:" + ("0" * 64),
    )
    return TrinityBundle(
        problem_frame=problem_frame,
        policy_spec=policy_spec,
        model_spec=model_spec,
    )


def test_rag_build_from_cas_and_search(tmp_path) -> None:
    cas = FileSystemCAS(tmp_path)
    trinity = _make_trinity("poverty_fiscal", ProblemDomain.FISCAL)
    trinity_ref = cas.put_json(
        trinity.model_dump(mode="json"),
        PutOptions(kind="ir.trinity_bundle", media_type="application/json"),
    )
    cas.put_json(
        {
            "run_id": "run_approve_1",
            "generated_at": datetime.utcnow().isoformat(),
            "governance": {"verdict": "APPROVE", "issues": []},
            "simulation_results": {"gdp_change": 1, "gini_coefficient": 0},
            "inputs": {"trinity_bundle_ref": str(trinity_ref.artifact_id)},
        },
        PutOptions(kind="scientist.decision_packet", media_type="application/json"),
    )
    cas.put_json(
        {
            "run_id": "run_reject_1",
            "generated_at": datetime.utcnow().isoformat(),
            "governance": {"verdict": "REJECT", "issues": []},
            "inputs": {"trinity_bundle_ref": str(trinity_ref.artifact_id)},
        },
        PutOptions(kind="scientist.decision_packet", media_type="application/json"),
    )

    index = CASRAGIndex(HashEmbeddingBackend(dimension=64), similarity_threshold=0.0)
    indexed = index.build_from_cas(cas, max_entries=100)

    assert indexed == 1
    assert index.size == 1
    query = AgentProblemFrame(
        frame_id="pf_query",
        domain="fiscal",
        problem_statement="Reduce poverty with targeted support",
        goals=("reduce poverty",),
        constraints=("Budget <= 1000000",),
    )
    results = index.search(query, top_k=3, domain_filter=True, similarity_threshold=0.0)
    assert len(results) == 1
    assert results[0].entry.run_id == "run_approve_1"


def test_rag_snapshot_roundtrip(tmp_path) -> None:
    cas = FileSystemCAS(tmp_path)
    trinity = _make_trinity("labor_program", ProblemDomain.LABOR)
    trinity_ref = cas.put_json(
        trinity.model_dump(mode="json"),
        PutOptions(kind="ir.trinity_bundle", media_type="application/json"),
    )
    cas.put_json(
        {
            "run_id": "run_approve_2",
            "governance": {"verdict": "APPROVE", "issues": []},
            "inputs": {"trinity_bundle_ref": str(trinity_ref.artifact_id)},
            "simulation_results": {"employment_change": 2},
        },
        PutOptions(kind="scientist.decision_packet", media_type="application/json"),
    )

    embedder = HashEmbeddingBackend(dimension=48)
    index = CASRAGIndex(embedder, similarity_threshold=0.0)
    assert index.build_from_cas(cas) == 1
    snapshot_ref = index.save(cas)

    loaded = CASRAGIndex.load(cas, snapshot_ref=snapshot_ref, embedder=embedder)
    assert loaded.size == 1
    query = AgentProblemFrame(
        frame_id="pf_query_2",
        domain="labor",
        problem_statement="Improve labor outcomes",
        goals=("increase employment",),
        constraints=("Budget <= 2000000",),
    )
    results = loaded.search(query, top_k=1, domain_filter=True, similarity_threshold=0.0)
    assert len(results) == 1
    assert results[0].entry.decision_packet_ref.startswith("sha256:")


def test_format_few_shot_block() -> None:
    result = RAGSearchResult(
        entry=RAGCaseEntry(
            decision_packet_ref="sha256:" + ("a" * 64),
            trinity_bundle_ref="sha256:" + ("b" * 64),
            run_id="run_3",
            domain="fiscal",
            problem_text="reduce poverty",
            problem_summary="Reduce poverty with budget pressure",
            intervention_summary="tax_subsidy, income_tax",
            lesson_learned="gdp_change=0.02",
            confidence=0.8,
            indexed_at=datetime.utcnow().isoformat(),
        ),
        similarity=0.77,
    )
    block = format_few_shot_block([result], max_chars=2000)
    assert "SIMILAR PAST DECISIONS" in block
    assert "tax_subsidy" in block


def test_rag_build_from_cas_manifest_assertion_is_not_swallowed() -> None:
    class _BrokenCAS:
        def iter_artifact_ids(self):
            return ["sha256:" + ("a" * 64)]

        def get_manifest(self, _artifact_id):
            raise AssertionError("manifest invariant failed")

    index = CASRAGIndex(HashEmbeddingBackend(dimension=32), similarity_threshold=0.0)

    with pytest.raises(AssertionError, match="manifest invariant failed"):
        index.build_from_cas(_BrokenCAS())


def test_rag_entry_trinity_assertion_is_not_swallowed(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cas = FileSystemCAS(tmp_path)
    index = CASRAGIndex(HashEmbeddingBackend(dimension=32), similarity_threshold=0.0)
    payload = {
        "run_id": "run_approve_assertion",
        "governance": {"verdict": "APPROVE", "issues": []},
        "inputs": {"trinity_bundle_ref": "sha256:" + ("b" * 64)},
    }

    def _boom(_cls, _payload):
        raise AssertionError("trinity validation invariant failed")

    monkeypatch.setattr(
        "polisyos.scientist.agent.rag.TrinityBundle.model_validate",
        classmethod(_boom),
    )
    monkeypatch.setattr(cas, "get_bytes", lambda _artifact_id: b"{}")
    monkeypatch.setattr(
        "polisyos.scientist.agent.rag.from_canonical_bytes",
        lambda _payload: {},
    )

    with pytest.raises(AssertionError, match="trinity validation invariant failed"):
        index._entry_from_decision_packet_payload(
            cas,
            payload,
            "sha256:" + ("a" * 64),
        )


def test_build_or_load_rag_index_load_assertion_is_not_swallowed(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cas = FileSystemCAS(tmp_path)

    monkeypatch.setattr(
        "polisyos.scientist.agent.rag.find_latest_rag_snapshot_ref",
        lambda _cas: "sha256:" + ("c" * 64),
    )

    def _boom(_cls, cas, *, snapshot_ref, embedder):
        del _cls, cas, snapshot_ref, embedder
        raise AssertionError("rag load invariant failed")

    monkeypatch.setattr(
        "polisyos.scientist.agent.rag.CASRAGIndex.load",
        classmethod(_boom),
    )

    with pytest.raises(AssertionError, match="rag load invariant failed"):
        build_or_load_rag_index(
            cas,
            config=type("Cfg", (), {"similarity_threshold": 0.0, "max_entries": 10})(),
            embedder=HashEmbeddingBackend(dimension=16),
        )
