"""Requested reconciliation limitations survive the real method/CAS report route."""

from __future__ import annotations

import numpy as np
import pytest

from polisyos.core.artifacts import PutOptions, SchemaInfo
from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import CanonSpec
from polisyos.foundry.methods.catalog.causal import discovery_pipeline as pipeline_module
from polisyos.foundry.methods.catalog.causal.discovery_pipeline import UnifiedCausalDiscovery
from polisyos.foundry.methods.catalog.causal.graph_reconciliation import ReconcileCausalGraph
from polisyos.foundry.methods.catalog.causal.protocols import (
    LLMStructuralHint,
    UnifiedDiscoveryData,
)
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.analytics.causal_discovery import DiscoveryPipelineReport
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType
from polisyos.ir.analytics.literature import LiteratureCausalPrior
from polisyos.ir.artifacts import get_json_artifact
from polisyos.scientist.compute.job_spec import JobSpec
from polisyos.scientist.compute.runner import run_job


def _state(request: str) -> UnifiedDiscoveryData:
    rng = np.random.default_rng(701)
    x = rng.normal(size=160)
    y = 2.0 * x + rng.normal(size=160)
    return UnifiedDiscoveryData(
        data=np.column_stack((x, y)),
        variable_names=["X", "Y"],
        literature_prior=LiteratureCausalPrior() if request == "prior" else None,
        llm_hints=(
            [LLMStructuralHint(src="X", dst="Y", confidence=0.2)] if request == "hint" else []
        ),
    )


def _persisted_report(tmp_path, state: UnifiedDiscoveryData) -> DiscoveryPipelineReport:
    store = FileSystemCAS(tmp_path / "cas")
    source_ref = store.put_json(
        state.model_dump(mode="json"),
        PutOptions(
            kind="tests.synthetic.unified_discovery_data",
            media_type="application/json",
            schema=SchemaInfo(name="tests.UnifiedDiscoveryData", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    MethodRegistry.get_instance().register(UnifiedCausalDiscovery, override=True)
    job = run_job(
        JobSpec(
            job_kind="method",
            method_fqn=UnifiedCausalDiscovery.signature.fqn,
            method_params={"force_algorithms": "pc", "ci_backend": "jax", "n_bootstrap": 0},
            input_refs={"discovery_data": source_ref},
            seed=71,
        ),
        cas_root=store.root,
        method_state=state,
    )
    assert not job.issues and job.method_result_ref is not None, job.issues
    assert job.final_state["report"] is job.final_state["discovery_pipeline_report"]
    payload = get_json_artifact(
        _ensure_ir_artifact_store(FileSystemCAS(store.root)), job.method_result_ref.artifact_id
    )
    report = DiscoveryPipelineReport.model_validate(payload["discovery_pipeline_report"])
    assert payload["report"] == payload["discovery_pipeline_report"]
    assert report.n_algorithms_run == 1
    assert report.individual_results[0].metadata["ci_backend_runtime"] == "jax_partial_corr"
    assert report.unified_pag.graph_type is GraphType.PAG
    assert report.unified_pag.edges
    assert not any("algorithm_failed" in warning for warning in report.warnings)
    return report


@pytest.mark.parametrize("request_kind", ["prior", "hint"])
def test_requested_pag_reconciliation_limitation_survives_method_cas_reader(
    tmp_path, request_kind: str
) -> None:
    report = _persisted_report(tmp_path, _state(request_kind))
    limitation = report.metadata["reconciliation"]
    assert limitation["requested"] is True
    assert limitation["applied"] is False
    assert limitation["status"] == "not_applied"
    assert limitation["reason"] == "unsupported_profile"
    assert limitation["input_graph_type"] == "pag"
    assert limitation["output_graph_type"] == "pag"
    assert "Unsupported graph reconciliation profile" in limitation["detail"]
    assert "reconciliation_not_applied:unsupported_profile" in report.warnings
    assert (
        report.unified_pag
        == UnifiedCausalDiscovery.pure_step(
            _state("none"),
            {"force_algorithms": "pc", "ci_backend": "jax", "n_bootstrap": 0},
        )["report"].unified_pag
    )


def test_no_reconciliation_request_does_not_invent_limitation(tmp_path) -> None:
    report = _persisted_report(tmp_path, _state("none"))
    assert "reconciliation" not in report.metadata
    assert not any(warning.startswith("reconciliation_") for warning in report.warnings)


def _supported_dag() -> CausalGraphModel:
    return CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[
            CausalEdge(
                src="X",
                dst="Y",
                mark_src=EdgeMark.TAIL,
                mark_dst=EdgeMark.ARROW,
                data_confidence=0.9,
                combined_confidence=0.9,
                sources=["data"],
            )
        ],
    )


def test_supported_dag_reconciliation_does_not_report_false_refusal() -> None:
    graph = _supported_dag()
    reconciled, warnings, summary = pipeline_module._maybe_reconcile(graph, _state("prior"), {})
    assert warnings == []
    assert summary == {
        "requested": True,
        "applied": True,
        "status": "applied",
        "input_graph_type": "dag",
        "output_graph_type": "pag",
    }
    assert reconciled.edges == graph.edges


def test_unexpected_reconciliation_failure_is_visible_as_failure(monkeypatch) -> None:
    def fail_reconciliation(*args, **kwargs):
        raise RuntimeError("synthetic requested reconciliation failure")

    monkeypatch.setattr(ReconcileCausalGraph, "pure_step", fail_reconciliation)
    graph = _supported_dag()
    retained, warnings, summary = pipeline_module._maybe_reconcile(graph, _state("prior"), {})
    assert retained is graph
    assert summary["applied"] is False
    assert summary["reason"] == "reconciliation_failed"
    assert summary["detail"] == "RuntimeError: synthetic requested reconciliation failure"
    assert warnings == ["reconciliation_not_applied:reconciliation_failed"]


@pytest.mark.parametrize("request_kind", ["prior", "hint", "none"])
def test_discovery_failure_discloses_only_actual_requested_noop(monkeypatch, request_kind) -> None:
    # Controlled backend fault; the actual reporting and canonical slot producer still run.
    monkeypatch.setattr(pipeline_module, "_run_algorithms_parallel", lambda **kwargs: ([], {}))
    output = UnifiedCausalDiscovery.pure_step(_state(request_kind), {})
    report = output["discovery_pipeline_report"]
    assert report is output["report"]
    assert report.unified_pag.graph_type is GraphType.PAG
    assert report.unified_pag.edges == []
    assert report.n_algorithms_run == 0
    assert "all_algorithms_failed" in report.warnings
    if request_kind == "none":
        assert "reconciliation" not in report.metadata
        assert not any(warning.startswith("reconciliation_") for warning in report.warnings)
    else:
        assert report.metadata["reconciliation"]["applied"] is False
        assert report.metadata["reconciliation"]["reason"] == "discovery_failed"
        assert "reconciliation_not_applied:discovery_failed" in report.warnings
