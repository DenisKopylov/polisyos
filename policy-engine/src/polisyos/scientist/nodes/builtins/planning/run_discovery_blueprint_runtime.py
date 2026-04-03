"""Public planning run discovery blueprint runtime module API."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

import numpy as np

from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.ir.analytics.causal import CausalEffectReport
from polisyos.ir.analytics.causal_queries import CausalQuery
from polisyos.ir.analytics.context import ContextProfile
from polisyos.ir.analytics.transportability import SNode, SelectionDiagram
from polisyos.scientist.discovery.aggregator import EvidenceWeightedAggregator
from polisyos.scientist.discovery.output import (
    DiscoveryArtifactBuildInput,
    DiscoveryArtifactBuilder,
    load_discovery_artifact_bundle,
)
from polisyos.scientist.discovery.portfolio import (
    GraphDiscoveryPortfolioRunner,
    PortfolioRunnerConfig,
    run_discovery_method,
)
from polisyos.scientist.discovery.prior_miner import PriorMiner, PriorMinerConfig
from polisyos.scientist.discovery.priors import GraphPriorBuilder
from polisyos.scientist.evidence_sources import normalize_evidence_sources_config
from polisyos.scientist.discovery.schema import (
    ComputeFootprint,
    GraphHypothesis,
    edge_key_for_edge,
    graph_hypothesis_from_report,
)
from polisyos.scientist.discovery.stability import BootstrapStabilityAnalyzer
from polisyos.scientist.discovery.utility_judge import (
    DownstreamUtilityJudge,
    UtilityJudgeInput,
)
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.protocol import NodeError, NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.engine.state import ExperimentState
from polisyos.foundry.methods.catalog.causal.protocols import (
    TabularCausalDiscoveryData,
    TimeSeriesCausalData,
)
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_DISCOVERY_ARTIFACT_BUNDLE_REF,
    INPUT_GRAPH_PRIOR_BUNDLE_REF,
    INPUT_PRIOR_KNOWLEDGE_BUNDLE_REF,
)

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_run_discovery_blueprint_runtime@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Run Discovery Blueprint Runtime",
    description="Execute the blueprint-native discovery portfolio and publish GraphPriorBundle artifacts.",
    tags=["builtin", "planning", "discovery"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=[
        "run_id",
        "params.discovery_data",
        "params.discovery_variable_names",
        "params.discovery_query",
        "params.discovery_time_series",
        "params.discovery_time_index",
        "params.discovery_domain",
        "params.discovery_notes",
        "params.discovery_algebraic_blocks",
        "params.discovery_selection_diagram",
        "params.discovery_source_context",
        "params.discovery_target_context",
        "params.discovery_s_nodes",
        "params.discovery_benchmark_reports",
        "params.evidence_sources",
    ],
    state_writes=[
        "params.graph_prior_bundle_ref",
        "params.prior_knowledge_bundle_ref",
        "params.discovery_artifact_bundle_ref",
        f"inputs.{INPUT_GRAPH_PRIOR_BUNDLE_REF}",
        f"inputs.{INPUT_PRIOR_KNOWLEDGE_BUNDLE_REF}",
        f"artifacts_index.{ARTIFACT_DISCOVERY_ARTIFACT_BUNDLE_REF}",
    ],
    produces=[ARTIFACT_DISCOVERY_ARTIFACT_BUNDLE_REF],
)


@dataclass(frozen=True)
class RunDiscoveryBlueprintRuntimeNode:
    """Run discovery blueprint runtime node implementation."""
    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        data = state.params.get("discovery_data")
        variable_names = state.params.get("discovery_variable_names")
        if not isinstance(variable_names, list) or not variable_names:
            return NodeOutcome(
                status="skip",
                state=state,
                events=[NodeEvent(level="info", message="Discovery runtime skipped: no discovery_variable_names present.")],
            )
        if not isinstance(data, list) or not data:
            return NodeOutcome(
                status="skip",
                state=state,
                events=[NodeEvent(level="info", message="Discovery runtime skipped: no discovery_data present.")],
            )

        discovery_state = _discovery_state_from_params(state)
        evidence_sources = normalize_evidence_sources_config(state.params)
        try:
            causal_query = _resolve_causal_query(state, variable_names)
        except ValueError as exc:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_SCHEMA_MISMATCH,
                    message=str(exc),
                ),
            )
        portfolio_config = PortfolioRunnerConfig(
            algebraic_blocks=list(state.params.get("discovery_algebraic_blocks", []) or [])
        )
        portfolio_runner = GraphDiscoveryPortfolioRunner(config=portfolio_config)
        portfolio_result = portfolio_runner.run(discovery_state)
        hypotheses = [candidate.hypothesis for candidate in portfolio_result.candidates]
        stability_report = BootstrapStabilityAnalyzer().analyze(
            portfolio_result.candidates,
            discovery_state,
            causal_query=causal_query,
        )
        utility_judge = DownstreamUtilityJudge()
        baseline_utility_report = utility_judge.evaluate(
            UtilityJudgeInput(
                hypotheses=hypotheses,
                stability_report=stability_report,
                causal_query=causal_query,
            )
        )
        shortlist_hypotheses = [
            hypothesis
            for hypothesis in hypotheses
            if hypothesis.hypothesis_id in set(baseline_utility_report.recommended_shortlist)
        ]
        selection_diagram = _resolve_selection_diagram(
            state,
            hypotheses=shortlist_hypotheses or hypotheses,
        )
        s_nodes = _resolve_s_nodes(state, selection_diagram)
        benchmark_reports = _load_shortlist_benchmark_reports(
            state,
            shortlist_hypotheses,
            evidence_sources=evidence_sources,
        )
        utility_report = utility_judge.evaluate(
            UtilityJudgeInput(
                hypotheses=hypotheses,
                stability_report=stability_report,
                causal_query=causal_query,
                selection_diagram=selection_diagram,
                s_nodes=s_nodes,
                benchmark_reports=benchmark_reports,
            )
        )
        matrix = EvidenceWeightedAggregator().aggregate(
            hypotheses,
            stability_report,
            utility_report,
        )
        measured_seed_scores = _measure_seed_reproducibility(
            discovery_state,
            portfolio_config=portfolio_config,
            shortlist=[
                hypothesis
                for hypothesis in hypotheses
                if hypothesis.hypothesis_id in set(utility_report.recommended_shortlist)
            ],
        )
        graph_prior_bundle = GraphPriorBuilder().build(matrix, utility_report)
        prior_knowledge_bundle = PriorMiner(
            config=PriorMinerConfig(
                academic_db_path=evidence_sources.academic_db_path,
                academic_index_dir=evidence_sources.academic_index_dir,
                domain=str(state.params.get("discovery_domain") or "").strip() or None,
            )
        ).mine(graph_prior_bundle)
        channel_coverage = dict(utility_report.metadata.get("channel_coverage") or {})
        graph_prior_bundle = graph_prior_bundle.model_copy(
            update={
                "metadata": {
                    **dict(graph_prior_bundle.metadata),
                    "channel_coverage": channel_coverage,
                    "source_grade": (
                        "full"
                        if channel_coverage.get("transportability")
                        and channel_coverage.get("benchmark")
                        and prior_knowledge_bundle.status == "ok"
                        else "degraded"
                    ),
                    "prior_mining_status": prior_knowledge_bundle.status,
                }
            }
        )
        builder = DiscoveryArtifactBuilder()
        bundle_ref = builder.build(
            ctx.store,
            DiscoveryArtifactBuildInput(
                run_id=state.run_id,
                task_id=f"discovery::{state.run_id}",
                variable_names=[str(item) for item in variable_names],
                causal_query=causal_query,
                data_characteristics=portfolio_result.data_characteristics,
                hypotheses=hypotheses,
                portfolio_result=portfolio_result,
                portfolio_config=portfolio_config,
                edge_confidence_matrix=matrix,
                bootstrap_stability_report=stability_report,
                downstream_utility_report=utility_report,
                graph_prior_bundle=graph_prior_bundle,
                prior_knowledge_bundle=prior_knowledge_bundle,
                seed_replay_scores=measured_seed_scores,
                notes=[str(item) for item in state.params.get("discovery_notes", [])]
                if isinstance(state.params.get("discovery_notes"), list)
                else [],
                metadata={
                    "workflow_id": "scientist_discovery",
                    "strict_mode": True,
                    "baseline_shortlist": list(baseline_utility_report.recommended_shortlist),
                },
            ),
        )
        bundle = load_discovery_artifact_bundle(ctx.store, bundle_ref)

        new_state = state.model_copy(deep=True)
        new_state.artifacts_index[ARTIFACT_DISCOVERY_ARTIFACT_BUNDLE_REF] = bundle_ref
        new_state.inputs[INPUT_GRAPH_PRIOR_BUNDLE_REF] = bundle.graph_prior_bundle_ref
        new_state.inputs[INPUT_PRIOR_KNOWLEDGE_BUNDLE_REF] = bundle.prior_knowledge_bundle_ref
        new_state.params["graph_prior_bundle_ref"] = bundle.graph_prior_bundle_ref.model_dump(
            mode="json"
        )
        new_state.params["prior_knowledge_bundle_ref"] = bundle.prior_knowledge_bundle_ref.model_dump(
            mode="json"
        )
        new_state.params["discovery_artifact_bundle_ref"] = bundle_ref.model_dump(mode="json")

        return NodeOutcome(
            status="ok",
            state=new_state,
            artifacts=[bundle_ref],
            events=[
                NodeEvent(
                    level="info",
                    message="Discovery blueprint runtime produced GraphPriorBundle and artifact bundle.",
                    attrs={
                        "hypothesis_count": len(hypotheses),
                        "shortlist_size": len(utility_report.recommended_shortlist),
                    },
                )
            ],
        )


def _discovery_state_from_params(
    state: ExperimentState,
) -> TabularCausalDiscoveryData | TimeSeriesCausalData:
    raw = np.asarray(state.params["discovery_data"], dtype=float)
    variable_names = [str(item) for item in state.params["discovery_variable_names"]]
    if bool(state.params.get("discovery_time_series")):
        return TimeSeriesCausalData(
            data=raw,
            variable_names=variable_names,
            time_index=state.params.get("discovery_time_index"),
            metadata={"run_id": state.run_id},
        )
    return TabularCausalDiscoveryData(
        data=raw,
        variable_names=variable_names,
        metadata={"run_id": state.run_id},
    )


def _resolve_causal_query(
    state: ExperimentState,
    variable_names: list[Any],
) -> CausalQuery:
    raw = state.params.get("discovery_query")
    if isinstance(raw, dict):
        try:
            return CausalQuery.model_validate(raw)
        except Exception as exc:
            raise ValueError(f"Invalid discovery_query payload: {exc}") from exc
    if len(variable_names) < 2:
        raise ValueError("Discovery runtime requires at least two variables.")
    return CausalQuery(
        treatment_variable=str(variable_names[0]),
        outcome_variable=str(variable_names[1]),
    )


def _resolve_selection_diagram(
    state: ExperimentState,
    *,
    hypotheses: list[GraphHypothesis],
) -> SelectionDiagram | None:
    if not hypotheses:
        return None
    base_graph = (hypotheses[0].resolved_graph or hypotheses[0].graph)
    raw = state.params.get("discovery_selection_diagram")
    if isinstance(raw, dict):
        try:
            payload = dict(raw)
            payload["base_graph"] = base_graph.model_dump(mode="json")
            return SelectionDiagram.model_validate(payload)
        except Exception:
            return None

    raw_source = state.params.get("discovery_source_context")
    raw_target = state.params.get("discovery_target_context")
    if isinstance(raw_source, dict) and isinstance(raw_target, dict):
        try:
            return SelectionDiagram(
                base_graph=base_graph,
                source_context=ContextProfile.model_validate(raw_source),
                target_context=ContextProfile.model_validate(raw_target),
            )
        except Exception:
            return None
    return None


def _resolve_s_nodes(
    state: ExperimentState,
    selection_diagram: SelectionDiagram | None,
) -> list[SNode]:
    if selection_diagram is not None and selection_diagram.s_nodes:
        return list(selection_diagram.s_nodes)
    raw = state.params.get("discovery_s_nodes")
    if not isinstance(raw, list):
        return []
    s_nodes: list[SNode] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            s_nodes.append(SNode.model_validate(item))
        except Exception:
            continue
    return s_nodes


def _load_shortlist_benchmark_reports(
    state: ExperimentState,
    hypotheses: list[GraphHypothesis],
    *,
    evidence_sources,
) -> dict[str, CausalEffectReport]:
    hypothesis_ids = {hypothesis.hypothesis_id for hypothesis in hypotheses}
    raw = state.params.get("discovery_benchmark_reports")
    if not raw and evidence_sources.benchmark_report_path:
        try:
            raw_text = Path(evidence_sources.benchmark_report_path).read_text(encoding="utf-8")
            raw = json.loads(raw_text)
        except Exception:
            raw = None

    reports: dict[str, CausalEffectReport] = {}
    if isinstance(raw, dict):
        iterable = raw.items()
    elif isinstance(raw, list):
        iterable = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            hypothesis_id = str(item.get("hypothesis_id") or "").strip()
            if hypothesis_id:
                iterable.append((hypothesis_id, item.get("report")))
    else:
        iterable = []

    for hypothesis_id, payload in iterable:
        if hypothesis_id not in hypothesis_ids:
            continue
        candidate_payload = payload
        if isinstance(candidate_payload, CausalEffectReport):
            reports[hypothesis_id] = candidate_payload
            continue
        if not isinstance(candidate_payload, dict):
            continue
        try:
            reports[hypothesis_id] = CausalEffectReport.model_validate(candidate_payload)
        except Exception:
            continue
    return reports


def _measure_seed_reproducibility(
    discovery_state: TabularCausalDiscoveryData | TimeSeriesCausalData,
    *,
    portfolio_config: PortfolioRunnerConfig,
    shortlist: list[GraphHypothesis],
    replay_count: int = 2,
) -> dict[str, float]:
    measured: dict[str, float] = {}
    for hypothesis in shortlist:
        base_graph = hypothesis.resolved_graph or hypothesis.graph
        base_edges = {edge_key_for_edge(edge) for edge in base_graph.edges}
        overlaps: list[float] = []
        for replay_index in range(1, replay_count + 1):
            params = portfolio_config.params_for(
                hypothesis.method,
                seed_offset=100 + replay_index,
            )
            try:
                report = run_discovery_method(discovery_state, hypothesis.method, params)
            except Exception:
                continue
            replay = graph_hypothesis_from_report(
                report,
                hypothesis_id=f"{hypothesis.hypothesis_id}_seed_{replay_index}",
                compute_footprint=ComputeFootprint(method_params=params),
            )
            replay_edges = {
                edge_key_for_edge(edge)
                for edge in (replay.resolved_graph or replay.graph).edges
            }
            overlaps.append(_edge_jaccard(base_edges, replay_edges))
        if overlaps:
            measured[hypothesis.hypothesis_id] = float(sum(overlaps) / len(overlaps))
    return measured


def _edge_jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    if not union:
        return 1.0
    return float(len(left & right) / len(union))


__all__ = ["RunDiscoveryBlueprintRuntimeNode"]
