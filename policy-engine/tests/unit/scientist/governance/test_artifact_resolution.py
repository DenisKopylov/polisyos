from __future__ import annotations

from polisyos.core.artifacts import ensure_ir_artifact_store
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.governance.passes.base import IssueSeverity, PassContext
from polisyos.core.governance.profiles import ValidationProfile
from polisyos.ir.analytics.causal_graph import (
    CausalGraphModel,
    GraphType,
    load_causal_graph_model,
    persist_causal_graph_model,
)
from polisyos.ir.registry.refs import CausalGraphModelRef
from polisyos.scientist.governance.passes._artifact_resolution import (
    resolve_optional_artifact_model,
)


def test_optional_artifact_resolution_adapts_core_store_for_ir_loader(tmp_path) -> None:
    core_store = FileSystemCAS(tmp_path)
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["policy", "outcome"],
        edges=[],
        discovery_method="artifact_resolution_test",
    )
    graph_ref = persist_causal_graph_model(ensure_ir_artifact_store(core_store), graph)
    context = PassContext(
        ir=None,
        state={
            "_store": core_store,
            "artifacts_index": {"causal_graph_ref": graph_ref},
        },
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="R_artifact_resolution_core_store",
    )

    resolution = resolve_optional_artifact_model(
        ctx=context,
        pass_id="artifact_resolution_test",
        direct_key="causal_graph",
        ref_key="causal_graph_ref",
        model_cls=CausalGraphModel,
        ref_model=CausalGraphModelRef,
        load_model=load_causal_graph_model,
        severity=IssueSeverity.WARNING,
        code="CAUSAL_GRAPH_INVALID",
        message="Causal graph could not be loaded.",
        suggestion="Rebuild the causal graph.",
        log=None,
    )

    assert resolution.value == graph
    assert resolution.issues == []


def test_optional_artifact_resolution_refuses_wrong_kind_and_profile(tmp_path) -> None:
    core_store = FileSystemCAS(tmp_path)
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["policy", "outcome"],
        edges=[],
        discovery_method="artifact_resolution_test",
    )
    graph_ref = persist_causal_graph_model(ensure_ir_artifact_store(core_store), graph)
    context = PassContext(
        ir=None,
        state={"_store": core_store},
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="R_artifact_resolution_wrong_ref",
    )

    wrong_kind = graph_ref.model_dump(mode="python")
    wrong_kind["kind"] = "ir.causal_effect_report"
    wrong_profile = graph_ref.model_dump(mode="python")
    wrong_profile["manifest_profile_sha256"] = "sha256:" + "f" * 64

    for raw_ref in (wrong_kind, wrong_profile):
        context.state["artifacts_index"] = {"causal_graph_ref": raw_ref}
        resolution = resolve_optional_artifact_model(
            ctx=context,
            pass_id="artifact_resolution_test",
            direct_key="causal_graph",
            ref_key="causal_graph_ref",
            model_cls=CausalGraphModel,
            ref_model=CausalGraphModelRef,
            load_model=load_causal_graph_model,
            severity=IssueSeverity.WARNING,
            code="CAUSAL_GRAPH_INVALID",
            message="Causal graph could not be loaded.",
            suggestion="Rebuild the causal graph.",
            log=None,
        )

        assert resolution.value is None
        assert len(resolution.issues) == 1
        assert resolution.issues[0].code == "CAUSAL_GRAPH_INVALID"


def test_optional_artifact_resolution_refuses_corrupt_payload_and_absent_ref(tmp_path) -> None:
    core_store = FileSystemCAS(tmp_path)
    corrupt_ref = core_store.put_json(
        {"not_a_graph": True},
        PutOptions(kind="ir.causal_graph_model", media_type="application/json"),
    )
    context = PassContext(
        ir=None,
        state={"_store": core_store},
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="R_artifact_resolution_corrupt_payload",
    )
    context.state["artifacts_index"] = {"causal_graph_ref": corrupt_ref.model_dump(mode="python")}

    corrupt_resolution = resolve_optional_artifact_model(
        ctx=context,
        pass_id="artifact_resolution_test",
        direct_key="causal_graph",
        ref_key="causal_graph_ref",
        model_cls=CausalGraphModel,
        ref_model=CausalGraphModelRef,
        load_model=load_causal_graph_model,
        severity=IssueSeverity.WARNING,
        code="CAUSAL_GRAPH_INVALID",
        message="Causal graph could not be loaded.",
        suggestion="Rebuild the causal graph.",
        log=None,
    )

    assert corrupt_resolution.value is None
    assert len(corrupt_resolution.issues) == 1
    assert corrupt_resolution.issues[0].code == "CAUSAL_GRAPH_INVALID"

    context.state["artifacts_index"] = {}
    absent_resolution = resolve_optional_artifact_model(
        ctx=context,
        pass_id="artifact_resolution_test",
        direct_key="causal_graph",
        ref_key="causal_graph_ref",
        model_cls=CausalGraphModel,
        ref_model=CausalGraphModelRef,
        load_model=load_causal_graph_model,
        severity=IssueSeverity.WARNING,
        code="CAUSAL_GRAPH_INVALID",
        message="Causal graph could not be loaded.",
        suggestion="Rebuild the causal graph.",
        log=None,
    )

    assert absent_resolution.value is None
    assert absent_resolution.issues == []
