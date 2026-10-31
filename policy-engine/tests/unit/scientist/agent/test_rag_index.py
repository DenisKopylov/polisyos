from __future__ import annotations

from datetime import datetime

import pytest

from polisyos.core.artifacts import artifact_manifest_profile_sha256, ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import ArtifactRef as CoreArtifactRef
from polisyos.core.artifacts.manifest import InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain
from polisyos.ir.governance.problem_frame import ProblemFrame as IRProblemFrame
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.registry.refs import ArtifactRefModel
from polisyos.ir.trinity import (
    TrinityBundle,
    load_trinity_bundle_artifact,
    persist_trinity_bundle_artifact,
)
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


def _persist_trinity(
    cas: FileSystemCAS,
    bundle: TrinityBundle,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRefModel:
    ref = persist_trinity_bundle_artifact(
        ensure_ir_artifact_store(cas),
        bundle,
        inputs=inputs,
    )
    assert ref.manifest_profile_sha256 is not None
    return ref


def _persist_trinity_views(
    cas: FileSystemCAS,
    bundle: TrinityBundle,
) -> tuple[ArtifactRefModel, ArtifactRefModel]:
    source_ref = cas.put_json(
        {"source": "lineage anchor"},
        PutOptions(
            kind="scientist.rag_test_source",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.scientist.RAGTestSource", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    source_profile = source_ref.manifest_profile_sha256
    assert source_profile is not None
    source_b = InputRef(
        artifact_id=str(source_ref.artifact_id),
        role="source-view-b",
        manifest_profile_sha256=source_profile,
    )
    source_a = InputRef(
        artifact_id=str(source_ref.artifact_id),
        role="source-view-a",
        manifest_profile_sha256=source_profile,
    )
    default_view = _persist_trinity(cas, bundle, inputs=[source_b])
    selected_view = _persist_trinity(cas, bundle, inputs=[source_a])
    assert default_view.artifact_id == selected_view.artifact_id
    assert default_view.manifest_profile_sha256 != selected_view.manifest_profile_sha256
    default_manifest = cas.get_manifest(selected_view.artifact_id)
    default_profile = artifact_manifest_profile_sha256(default_manifest)
    assert default_profile == default_view.manifest_profile_sha256
    assert default_profile != selected_view.manifest_profile_sha256
    assert default_manifest.inputs[0].role == "source-view-b"
    return default_view, selected_view


def _put_decision_packet(
    cas: FileSystemCAS,
    trinity_ref: CoreArtifactRef | ArtifactRefModel,
    *,
    run_id: str,
    verdict: str = "APPROVE",
    packet_inputs: list[InputRef] | None = None,
    simulation_results: dict[str, int | float] | None = None,
    payload_trinity_ref: CoreArtifactRef | ArtifactRefModel | None = None,
) -> CoreArtifactRef:
    if packet_inputs is None:
        profile_sha256 = trinity_ref.manifest_profile_sha256
        assert profile_sha256 is not None
        inputs = [
            InputRef(
                artifact_id=str(trinity_ref.artifact_id),
                role="input.trinity_bundle_ref",
                manifest_profile_sha256=profile_sha256,
            )
        ]
    else:
        inputs = packet_inputs
    payload_ref = trinity_ref if payload_trinity_ref is None else payload_trinity_ref
    payload = {
        "run_id": run_id,
        "governance": {"verdict": verdict, "issues": []},
        "inputs": {"trinity_bundle_ref": str(payload_ref.artifact_id)},
    }
    if simulation_results is not None:
        payload["simulation_results"] = simulation_results
    return cas.put_json(
        payload,
        PutOptions(
            kind="scientist.decision_packet",
            media_type="application/json",
            inputs=inputs,
        ),
    )


def test_rag_build_from_cas_and_search(tmp_path) -> None:
    cas = FileSystemCAS(tmp_path)
    trinity = _make_trinity("poverty_fiscal", ProblemDomain.FISCAL)
    trinity_ref = _persist_trinity(cas, trinity)
    _put_decision_packet(
        cas,
        trinity_ref,
        run_id="run_approve_1",
        simulation_results={"gdp_change": 1, "gini_coefficient": 0},
    )
    _put_decision_packet(
        cas,
        trinity_ref,
        run_id="run_reject_1",
        verdict="REJECT",
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
    trinity_ref = _persist_trinity(cas, trinity)
    _put_decision_packet(
        cas,
        trinity_ref,
        run_id="run_approve_2",
        simulation_results={"employment_change": 2},
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


def test_rag_uses_packet_selected_trinity_profile_over_default_view(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cas = FileSystemCAS(tmp_path)
    default_view, selected_view = _persist_trinity_views(
        cas,
        _make_trinity("selected_profile", ProblemDomain.FISCAL),
    )
    packet_ref = _put_decision_packet(
        cas,
        selected_view,
        run_id="run_selected_trinity_profile",
    )
    packet_manifest = cas.get_manifest(packet_ref)
    assert len(packet_manifest.inputs) == 1
    assert packet_manifest.inputs[0].manifest_profile_sha256 == (
        selected_view.manifest_profile_sha256
    )

    loaded_selectors: list[CoreArtifactRef] = []

    def _load_selected_trinity(store, selector):
        loaded_selectors.append(selector)
        return load_trinity_bundle_artifact(store, selector)

    monkeypatch.setattr(
        "polisyos.ir.trinity.load_trinity_bundle_artifact",
        _load_selected_trinity,
    )
    index = CASRAGIndex(HashEmbeddingBackend(dimension=32), similarity_threshold=0.0)

    assert index.build_from_cas(cas) == 1
    assert index.size == 1
    assert len(loaded_selectors) == 1
    assert loaded_selectors[0].manifest_profile_sha256 == selected_view.manifest_profile_sha256
    assert artifact_manifest_profile_sha256(cas.get_manifest(loaded_selectors[0])) == (
        selected_view.manifest_profile_sha256
    )
    assert default_view.manifest_profile_sha256 != selected_view.manifest_profile_sha256


def test_rag_skips_trinity_bundle_with_foreign_owner_schema(tmp_path) -> None:
    cas = FileSystemCAS(tmp_path)
    trinity = _make_trinity("foreign_owner", ProblemDomain.FISCAL)
    trinity_ref = cas.put_json(
        trinity.model_dump(mode="json"),
        PutOptions(
            kind=TrinityBundle.ARTIFACT_KIND,
            media_type=TrinityBundle.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name="polisyos.other.TrinityBundle",
                version=TrinityBundle.ARTIFACT_SCHEMA_VERSION,
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    _put_decision_packet(
        cas,
        trinity_ref,
        run_id="run_foreign_trinity_owner",
    )

    index = CASRAGIndex(HashEmbeddingBackend(dimension=32), similarity_threshold=0.0)

    assert index.build_from_cas(cas) == 0
    assert index.size == 0


def test_rag_skips_bare_trinity_reference_without_selected_packet_input(tmp_path) -> None:
    cas = FileSystemCAS(tmp_path)
    trinity_ref = _persist_trinity(
        cas,
        _make_trinity("unbound_reference", ProblemDomain.FISCAL),
    )
    _put_decision_packet(
        cas,
        trinity_ref,
        run_id="run_unbound_trinity_reference",
        packet_inputs=[],
    )

    index = CASRAGIndex(HashEmbeddingBackend(dimension=32), similarity_threshold=0.0)

    assert index.build_from_cas(cas) == 0
    assert index.size == 0


def test_rag_skips_trinity_input_edge_without_selected_profile(tmp_path) -> None:
    cas = FileSystemCAS(tmp_path)
    trinity_ref = _persist_trinity(
        cas,
        _make_trinity("missing_profile", ProblemDomain.FISCAL),
    )
    _put_decision_packet(
        cas,
        trinity_ref,
        run_id="run_missing_trinity_profile",
        packet_inputs=[
            InputRef(
                artifact_id=str(trinity_ref.artifact_id),
                role="input.trinity_bundle_ref",
            )
        ],
    )

    index = CASRAGIndex(HashEmbeddingBackend(dimension=32), similarity_threshold=0.0)

    assert index.build_from_cas(cas) == 0
    assert index.size == 0


def test_rag_skips_trinity_input_edge_with_mismatched_payload_id(tmp_path) -> None:
    cas = FileSystemCAS(tmp_path)
    packet_trinity_ref = _persist_trinity(
        cas,
        _make_trinity("packet_reference", ProblemDomain.FISCAL),
    )
    edge_trinity_ref = _persist_trinity(
        cas,
        _make_trinity("lineage_reference", ProblemDomain.FISCAL),
    )
    _put_decision_packet(
        cas,
        edge_trinity_ref,
        run_id="run_mismatched_trinity_id",
        payload_trinity_ref=packet_trinity_ref,
    )

    index = CASRAGIndex(HashEmbeddingBackend(dimension=32), similarity_threshold=0.0)

    assert index.build_from_cas(cas) == 0
    assert index.size == 0


def test_rag_skips_duplicate_same_id_trinity_profile_edges(tmp_path) -> None:
    cas = FileSystemCAS(tmp_path)
    bundle = _make_trinity("ambiguous_profile", ProblemDomain.FISCAL)
    view_b, view_a = _persist_trinity_views(cas, bundle)
    _put_decision_packet(
        cas,
        view_a,
        run_id="run_ambiguous_trinity_profile",
        packet_inputs=[
            InputRef(
                artifact_id=str(view_b.artifact_id),
                role="input.trinity_bundle_ref",
                manifest_profile_sha256=view_b.manifest_profile_sha256,
            ),
            InputRef(
                artifact_id=str(view_a.artifact_id),
                role="input.trinity_bundle_ref",
                manifest_profile_sha256=view_a.manifest_profile_sha256,
            ),
        ],
    )

    index = CASRAGIndex(HashEmbeddingBackend(dimension=32), similarity_threshold=0.0)

    assert index.build_from_cas(cas) == 0
    assert index.size == 0


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
    trinity_ref = _persist_trinity(
        cas,
        _make_trinity("assertion_propagation", ProblemDomain.FISCAL),
    )
    packet_ref = _put_decision_packet(
        cas,
        trinity_ref,
        run_id="run_approve_assertion",
    )
    manifest = cas.get_manifest(packet_ref)
    index = CASRAGIndex(HashEmbeddingBackend(dimension=32), similarity_threshold=0.0)
    payload = {
        "run_id": "run_approve_assertion",
        "governance": {"verdict": "APPROVE", "issues": []},
        "inputs": {"trinity_bundle_ref": str(trinity_ref.artifact_id)},
    }

    selected_refs: list[CoreArtifactRef] = []

    def _boom(_store, selector):
        selected_refs.append(selector)
        raise AssertionError("trinity validation invariant failed")

    monkeypatch.setattr(
        "polisyos.ir.trinity.load_trinity_bundle_artifact",
        _boom,
    )

    with pytest.raises(AssertionError, match="trinity validation invariant failed"):
        index._entry_from_decision_packet_payload(
            cas,
            payload,
            str(packet_ref.artifact_id),
            decision_packet_inputs=manifest.inputs,
        )
    assert selected_refs[0].manifest_profile_sha256 == trinity_ref.manifest_profile_sha256


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
