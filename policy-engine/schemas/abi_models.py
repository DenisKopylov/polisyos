from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class Priority(str, Enum):
    P0 = "p0"
    P1 = "p1"
    P2 = "p2"


class CompatMode(str, Enum):
    STRICT = "strict"
    TOLERANT = "tolerant"


class Lifecycle(str, Enum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"


@dataclass(frozen=True)
class ABIModelEntry:
    abi_key: str
    fqn: str
    module: str
    schema_file: str
    priority: Priority
    compat_mode: CompatMode = CompatMode.STRICT
    version_field: str | None = "schema_version"
    lifecycle: Lifecycle = Lifecycle.ACTIVE
    aliases: tuple[str, ...] = ()
    allow_missing: bool = False


IR_ABI_MODELS: tuple[ABIModelEntry, ...] = (
    ABIModelEntry(
        abi_key="trinity_bundle",
        fqn="polisyos.ir.trinity.TrinityBundle",
        module="ir",
        schema_file="trinity_bundle.schema.json",
        priority=Priority.P0,
    ),
    ABIModelEntry(
        abi_key="problem_frame",
        fqn="polisyos.ir.governance.problem_frame.ProblemFrame",
        module="ir",
        schema_file="problem_frame.schema.json",
        priority=Priority.P0,
    ),
    ABIModelEntry(
        abi_key="policy_spec",
        fqn="polisyos.ir.governance.policy_spec.PolicySpec",
        module="ir",
        schema_file="policy_spec.schema.json",
        priority=Priority.P0,
    ),
    ABIModelEntry(
        abi_key="policy_portfolio",
        fqn="polisyos.ir.portfolio.PolicyPortfolio",
        module="ir",
        schema_file="policy_portfolio.schema.json",
        priority=Priority.P0,
    ),
    ABIModelEntry(
        abi_key="model_spec",
        fqn="polisyos.ir.model_spec.ModelSpec",
        module="ir",
        schema_file="model_spec.schema.json",
        priority=Priority.P0,
    ),
    ABIModelEntry(
        abi_key="norm_pack",
        fqn="polisyos.ir.norm_pack.NormPack",
        module="ir",
        schema_file="norm_pack.schema.json",
        priority=Priority.P0,
    ),
    ABIModelEntry(
        abi_key="norm_rule",
        fqn="polisyos.ir.norm_pack.NormRule",
        module="ir",
        schema_file="norm_rule.schema.json",
        priority=Priority.P0,
    ),
    ABIModelEntry(
        abi_key="norm_ref",
        fqn="polisyos.ir.norm_pack.NormRef",
        module="ir",
        schema_file="norm_ref.schema.json",
        priority=Priority.P0,
    ),
    ABIModelEntry(
        abi_key="claim",
        fqn="polisyos.ir.world.claim.Claim",
        module="ir",
        schema_file="claim.schema.json",
        priority=Priority.P0,
    ),
    ABIModelEntry(
        abi_key="conflict_set",
        fqn="polisyos.ir.world.conflict.ConflictSet",
        module="ir",
        schema_file="conflict_set.schema.json",
        priority=Priority.P0,
    ),
    ABIModelEntry(
        abi_key="conflict_set_resolution",
        fqn="polisyos.ir.world.conflict.ConflictSetResolution",
        module="ir",
        schema_file="conflict_set_resolution.schema.json",
        priority=Priority.P0,
    ),
    ABIModelEntry(
        abi_key="conflict_resolution",
        fqn="polisyos.ir.world.conflict.ConflictResolution",
        module="ir",
        schema_file="conflict_resolution.schema.json",
        priority=Priority.P0,
    ),
    ABIModelEntry(
        abi_key="world_event",
        fqn="polisyos.ir.world.event.WorldEvent",
        module="ir",
        schema_file="world_event.schema.json",
        priority=Priority.P0,
    ),
    ABIModelEntry(
        abi_key="prov_activity",
        fqn="polisyos.ir.world.event.ProvActivity",
        module="ir",
        schema_file="prov_activity.schema.json",
        priority=Priority.P0,
    ),
    ABIModelEntry(
        abi_key="doc_fragment",
        fqn="polisyos.ir.world.doc.DocFragment",
        module="ir",
        schema_file="doc_fragment.schema.json",
        priority=Priority.P1,
    ),
    ABIModelEntry(
        abi_key="doc_meta",
        fqn="polisyos.ir.world.doc.DocMeta",
        module="ir",
        schema_file="doc_meta.schema.json",
        priority=Priority.P1,
    ),
    ABIModelEntry(
        abi_key="trust_assessment",
        fqn="polisyos.ir.world.trust.TrustAssessment",
        module="ir",
        schema_file="trust_assessment.schema.json",
        priority=Priority.P1,
    ),
    ABIModelEntry(
        abi_key="quality_report",
        fqn="polisyos.ir.world.quality.QualityReport",
        module="ir",
        schema_file="quality_report.schema.json",
        priority=Priority.P1,
    ),
    ABIModelEntry(
        abi_key="uncertainty_envelope",
        fqn="polisyos.ir.analytics.uncertainty.UncertaintyEnvelope",
        module="ir",
        schema_file="uncertainty_envelope.schema.json",
        priority=Priority.P1,
    ),
    ABIModelEntry(
        abi_key="causal_effect_report",
        fqn="polisyos.ir.analytics.causal.CausalEffectReport",
        module="ir",
        schema_file="causal_effect_report.schema.json",
        priority=Priority.P1,
    ),
    ABIModelEntry(
        abi_key="abm_alignment_report",
        fqn="polisyos.ir.analytics.abm_bridge.ABMAlignmentReport",
        module="ir",
        schema_file="abm_alignment_report.schema.json",
        priority=Priority.P1,
    ),
    ABIModelEntry(
        abi_key="transportability_result",
        fqn="polisyos.ir.analytics.transportability.TransportabilityResult",
        module="ir",
        schema_file="transportability_result.schema.json",
        priority=Priority.P1,
    ),
    ABIModelEntry(
        abi_key="refutation_result",
        fqn="polisyos.ir.analytics.causal.RefutationResult",
        module="ir",
        schema_file="refutation_result.schema.json",
        priority=Priority.P1,
    ),
    ABIModelEntry(
        abi_key="causal_graph_model",
        fqn="polisyos.ir.analytics.causal_graph.CausalGraphModel",
        module="ir",
        schema_file="causal_graph_model.schema.json",
        priority=Priority.P1,
    ),
    ABIModelEntry(
        abi_key="structural_causal_model_spec",
        fqn="polisyos.ir.analytics.structural_causal_model.StructuralCausalModelSpec",
        module="ir",
        schema_file="structural_causal_model_spec.schema.json",
        priority=Priority.P1,
    ),
    ABIModelEntry(
        abi_key="causal_query_result",
        fqn="polisyos.ir.analytics.causal_queries.CausalQueryResult",
        module="ir",
        schema_file="causal_query_result.schema.json",
        priority=Priority.P1,
    ),
    ABIModelEntry(
        abi_key="causal_discovery_report",
        fqn="polisyos.ir.analytics.causal_discovery.CausalDiscoveryReport",
        module="ir",
        schema_file="causal_discovery_report.schema.json",
        priority=Priority.P1,
    ),
    ABIModelEntry(
        abi_key="causal_model_ensemble",
        fqn="polisyos.ir.analytics.causal_ensemble.CausalModelEnsemble",
        module="ir",
        schema_file="causal_model_ensemble.schema.json",
        priority=Priority.P1,
    ),
    ABIModelEntry(
        abi_key="causal_sensitivity_result",
        fqn="polisyos.ir.analytics.sensitivity.SensitivityResult",
        module="ir",
        schema_file="sensitivity_result.schema.json",
        priority=Priority.P1,
    ),
    ABIModelEntry(
        abi_key="distributional_report",
        fqn="polisyos.ir.analytics.distributional.DistributionalReport",
        module="ir",
        schema_file="distributional_report.schema.json",
        priority=Priority.P1,
    ),
    ABIModelEntry(
        abi_key="hte_result",
        fqn="polisyos.ir.analytics.hte.HTEResult",
        module="ir",
        schema_file="hte_result.schema.json",
        priority=Priority.P1,
    ),
    ABIModelEntry(
        abi_key="policy_recommendation",
        fqn="polisyos.ir.analytics.hte.PolicyRecommendation",
        module="ir",
        schema_file="policy_recommendation.schema.json",
        priority=Priority.P1,
    ),
    ABIModelEntry(
        abi_key="backtest_report",
        fqn="polisyos.ir.analytics.backtest.BacktestReport",
        module="ir",
        schema_file="backtest_report.schema.json",
        priority=Priority.P1,
    ),
    ABIModelEntry(
        abi_key="fact",
        fqn="polisyos.ir.fact_log.Fact",
        module="ir",
        schema_file="fact.schema.json",
        priority=Priority.P0,
    ),
    ABIModelEntry(
        abi_key="fact_segment_manifest",
        fqn="polisyos.ir.fact_log.FactSegmentManifest",
        module="ir",
        schema_file="fact_segment_manifest.schema.json",
        priority=Priority.P0,
    ),
    ABIModelEntry(
        abi_key="calibration_config",
        fqn="polisyos.ir.analytics.calibration.CalibrationConfig",
        module="ir",
        schema_file="calibration_config.schema.json",
        priority=Priority.P2,
    ),
    ABIModelEntry(
        abi_key="data_view_request",
        fqn="polisyos.ir.analytics.data_views.DataViewRequest",
        module="ir",
        schema_file="data_view_request.schema.json",
        priority=Priority.P2,
        version_field=None,
    ),
    ABIModelEntry(
        abi_key="article_extraction_result",
        fqn="polisyos.ir.analytics.literature.ArticleExtractionResult",
        module="ir",
        schema_file="article_extraction_result.schema.json",
        priority=Priority.P2,
    ),
    ABIModelEntry(
        abi_key="literature_causal_prior",
        fqn="polisyos.ir.analytics.literature.LiteratureCausalPrior",
        module="ir",
        schema_file="literature_causal_prior.schema.json",
        priority=Priority.P2,
    ),
    ABIModelEntry(
        abi_key="context_adaptive_parameter_bundle",
        fqn="polisyos.ir.analytics.parameters.ContextAdaptiveParameterBundle",
        module="ir",
        schema_file="context_adaptive_parameter_bundle.schema.json",
        priority=Priority.P2,
    ),
    ABIModelEntry(
        abi_key="causal_query",
        fqn="polisyos.ir.analytics.causal_queries.CausalQuery",
        module="ir",
        schema_file="causal_query.schema.json",
        priority=Priority.P2,
    ),
    ABIModelEntry(
        abi_key="gate_context",
        fqn="polisyos.ir.governance.gate.GateContext",
        module="ir",
        schema_file="gate_context.schema.json",
        priority=Priority.P1,
    ),
    ABIModelEntry(
        abi_key="gate_request",
        fqn="polisyos.ir.governance.gate.GateRequest",
        module="ir",
        schema_file="gate_request.schema.json",
        priority=Priority.P1,
    ),
    ABIModelEntry(
        abi_key="gate_decision",
        fqn="polisyos.ir.governance.gate.GateDecision",
        module="ir",
        schema_file="gate_decision.schema.json",
        priority=Priority.P1,
    ),
    ABIModelEntry(
        abi_key="gate_event",
        fqn="polisyos.ir.governance.gate.GateEvent",
        module="ir",
        schema_file="gate_event.schema.json",
        priority=Priority.P1,
    ),
    ABIModelEntry(
        abi_key="partial_identification_result",
        fqn="polisyos.ir.analytics.partial_identification.PartialIdentificationResult",
        module="ir",
        schema_file="partial_identification_result.schema.json",
        priority=Priority.P2,
    ),
    ABIModelEntry(
        abi_key="certification_result",
        fqn="polisyos.ir.analytics.alignment_certification.CertificationResult",
        module="ir",
        schema_file="certification_result.schema.json",
        priority=Priority.P2,
        version_field=None,
    ),
    ABIModelEntry(
        abi_key="outer_search_result",
        fqn="polisyos.ir.analytics.alignment_certification.OuterSearchResult",
        module="ir",
        schema_file="outer_search_result.schema.json",
        priority=Priority.P2,
        version_field=None,
    ),
)


FABRIC_ABI_MODELS: tuple[ABIModelEntry, ...] = (
    ABIModelEntry(
        abi_key="edge_kind",
        fqn="polisyos.ir.world.abi.EdgeKind",
        module="fabric",
        schema_file="edge_kind.schema.json",
        priority=Priority.P0,
        version_field=None,
    ),
    ABIModelEntry(
        abi_key="node_kind",
        fqn="polisyos.ir.world.abi.NodeKind",
        module="fabric",
        schema_file="node_kind.schema.json",
        priority=Priority.P0,
        version_field=None,
    ),
)


ABI_MODELS: tuple[ABIModelEntry, ...] = IR_ABI_MODELS + FABRIC_ABI_MODELS


def iter_abi_entries(*, include_deprecated: bool = False) -> tuple[ABIModelEntry, ...]:
    if include_deprecated:
        return ABI_MODELS
    return tuple(entry for entry in ABI_MODELS if entry.lifecycle == Lifecycle.ACTIVE)


def select_abi_entries(
    filters: Iterable[str] | None,
    *,
    include_deprecated: bool = False,
) -> tuple[ABIModelEntry, ...]:
    entries = iter_abi_entries(include_deprecated=include_deprecated)
    if not filters:
        return entries

    normalized = tuple(token.strip().lower() for token in filters if token.strip())
    if not normalized:
        return entries

    selected: list[ABIModelEntry] = []
    for entry in entries:
        tags = {
            entry.abi_key.lower(),
            entry.module.lower(),
            entry.priority.value,
            entry.fqn.lower(),
        }
        tags.update(alias.lower() for alias in entry.aliases)
        if any(token in tags for token in normalized):
            selected.append(entry)
            continue
        if any(entry.abi_key.lower().startswith(token) for token in normalized):
            selected.append(entry)

    return tuple(selected)
