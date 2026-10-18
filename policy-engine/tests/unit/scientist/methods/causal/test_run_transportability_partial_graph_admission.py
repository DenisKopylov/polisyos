from __future__ import annotations

import logging
from pathlib import Path
from tempfile import TemporaryDirectory

from polisyos.core.artifacts import ensure_ir_artifact_store
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.analytics.causal import (
    CausalEffectReport,
    CausalMethod,
    EstimationStatus,
    load_causal_effect_report,
    persist_causal_effect_report,
)
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    GraphType,
    graph_content_sha256,
    persist_causal_graph_model,
)
from polisyos.ir.analytics.transportability import (
    TransportabilityStatus,
    TransportMode,
    load_transportability_result,
)
from polisyos.scientist.nodes.builtins.causal.resolve_transport import RunTransportabilityNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CAUSAL_REPORT_REF,
    ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF,
    ARTIFACT_TRANSPORTABILITY_RESULT_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _build_context(root: Path, *, run_id: str) -> ExecutionContext:
    store = FileSystemCAS(root)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id=run_id)
    return ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger(f"test.{run_id}"),
    )


def _base_report() -> CausalEffectReport:
    return CausalEffectReport(
        method=CausalMethod.DOWHY_BACKDOOR,
        status=EstimationStatus.SUCCESS,
        estimand="ATE",
        point_estimate=1.0,
        confidence_interval=(0.8, 1.2),
        inference_method="backdoor.linear_regression",
        sample_size=100,
        n_treated=50,
        n_control=50,
        pre_periods=0,
        post_periods=0,
        method_params={"treatment": "X", "outcome": "Y"},
    )


def test_partial_graph_refusal_is_persisted_for_fixed_and_ambiguous_queries() -> None:
    queries = (("X", "Y"), ("A", "B"))
    with TemporaryDirectory(prefix="partial-graph-node-") as temporary:
        root = Path(temporary)
        for treatment, outcome in queries:
            run_id = f"partial-{treatment}-{outcome}"
            context = _build_context(root / run_id, run_id=run_id)
            artifact_store = ensure_ir_artifact_store(context.store)
            report_ref = persist_causal_effect_report(
                artifact_store,
                _base_report(),
            )
            graph = CausalGraphModel(
                graph_type=GraphType.CPDAG,
                nodes=["X", "Y", "A", "B"],
                edges=[
                    CausalEdge(src="X", dst="Y"),
                    CausalEdge(
                        src="A",
                        dst="B",
                        mark_src=EdgeMark.TAIL,
                        mark_dst=EdgeMark.TAIL,
                    ),
                ],
            )
            graph_ref = persist_causal_graph_model(artifact_store, graph)
            profile = {
                "context_id": "DE",
                "income_level": "high",
                "institutional_quality": 0.8,
            }
            state = ExperimentState(
                run_id=run_id,
                artifacts_index={
                    ARTIFACT_CAUSAL_REPORT_REF: report_ref,
                    ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF: graph_ref,
                },
                params={
                    "source_context": profile,
                    "target_context": profile,
                    "query_treatment": treatment,
                    "query_outcome": outcome,
                },
            )

            output = RunTransportabilityNode().execute(context, state)
            _require(output.status == "ok", "node should complete with a persisted limitation")
            transport_ref = output.state.artifacts_index[ARTIFACT_TRANSPORTABILITY_RESULT_REF]
            result = load_transportability_result(artifact_store, transport_ref)
            _require(
                result.status is TransportabilityStatus.UNSUPPORTED,
                "partial graph must not produce an identified scalar result",
            )
            _require(
                result.transport_mode is TransportMode.NONE,
                "partial graph refusal must not carry a transport mode",
            )
            _require(
                result.unsupported_reason == "partial_graph_completion_semantics_not_established",
                "the persisted limitation must retain its specific reason",
            )
            _require(
                result.source_graph_type is GraphType.CPDAG,
                "the persisted result must retain the source graph type",
            )
            _require(
                result.source_graph_sha256 == graph_content_sha256(graph),
                "the persisted result must bind the graph content",
            )
            _require(
                result.query == f"P*({outcome}|do({treatment}))",
                "the persisted result must retain the requested query",
            )
            _require(
                result.transport_formula is None,
                "a refusal must not persist a transport formula",
            )

            updated_report = load_causal_effect_report(
                artifact_store,
                output.state.artifacts_index[ARTIFACT_CAUSAL_REPORT_REF],
            )
            _require(
                updated_report.transport_result == result,
                "the fresh report read must carry the same persisted refusal",
            )
