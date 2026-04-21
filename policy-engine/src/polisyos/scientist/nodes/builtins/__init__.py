"""Lazy catalog of production Scientist nodes and their concrete DAG components.

The package-level contract is the `builtin_nodes()` registry snapshot plus direct
access to node classes for testing and documentation. Imports are deferred until
first use so inspecting the facade does not eagerly import Foundry, Fabric, Lex,
or causal-method dependencies.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from polisyos.scientist.engine.protocol import Node

__all__ = [
    "BuildDataSnapshotNode",
    "PlanPolicyRequestNode",
    "BindFoundryInputsNode",
    "EnrichKnowledgeNode",
    "LinkTrinityNode",
    "FormalizeVerifiedPolicyNode",
    "CompileFoundryNode",
    "RunSimulationNode",
    "RunMetricValidationNode",
    "BuildLiteraturePriorNode",
    "CounterfactualIdentificationGateNode",
    "ReconcileCausalGraphNode",
    "RunCausalReadinessNode",
    "RunCausalContractExecutionNode",
    "ResolveParametersNode",
    "RunABMConsistencyCheckNode",
    "RunCausalEnsembleNode",
    "RunCausalQueriesNode",
    "RunTransportabilityNode",
    "RunCausalEvaluationNode",
    "RunDistributionalAnalysisNode",
    "PropagateUncertaintyNode",
    "LegalCheckNode",
    "DataPlaneGateNode",
    "RunNormativeArbitrationNode",
    "RunGovernanceNode",
    "BuildDecisionPacketNode",
    "BuildExecutionPlanNode",
    "BuildMethodCatalogSnapshotNode",
    "CompileCrossGraphEvidenceNode",
    "RunHierarchicalPolicySearchNode",
    "AssembleLegalCandidatePackNode",
    "ExpandLegalSourcePackNode",
    "RunSourceVerificationNode",
    "RunSourceGapReviewNode",
    "DraftPolicyOptionsNode",
    "RunPreflightNode",
    "ReadyToRunNode",
    "RunEvaluatorNode",
    "BuildPolicyOutputBundleNode",
    "BuildVerifiedPolicyReportNode",
    "RunPolicyBlueprintRuntimeNode",
    "RunPolicyTranslationNode",
    "RunTranslatorComplianceNode",
    "RunDiscoveryBlueprintRuntimeNode",
    "builtin_nodes",
]


def builtin_nodes() -> list["Node"]:
    """Instantiate every builtin node in dependency order for registry bootstrap.

    Returns:
        Concrete node objects whose `spec.node_id` values are referenced by the
        builtin workflow DAGs.
    """
    from polisyos.scientist.nodes.builtins.causal.build_literature_prior import (
        BuildLiteraturePriorNode,
    )
    from polisyos.scientist.nodes.builtins.causal.counterfactual_identification_gate import (
        CounterfactualIdentificationGateNode,
    )
    from polisyos.scientist.nodes.builtins.causal.reconcile_causal_graph import (
        ReconcileCausalGraphNode,
    )
    from polisyos.scientist.nodes.builtins.causal.run_causal_readiness import (
        RunCausalReadinessNode,
    )
    from polisyos.scientist.nodes.builtins.causal.run_causal_contract_execution import (
        RunCausalContractExecutionNode,
    )
    from polisyos.scientist.nodes.builtins.causal.resolve_parameters import (
        ResolveParametersNode,
    )
    from polisyos.scientist.nodes.builtins.causal.resolve_transport import (
        RunTransportabilityNode,
    )
    from polisyos.scientist.nodes.builtins.causal.run_abm_consistency import (
        RunABMConsistencyCheckNode,
    )
    from polisyos.scientist.nodes.builtins.causal.run_causal_ensemble import (
        RunCausalEnsembleNode,
    )
    from polisyos.scientist.nodes.builtins.causal.run_causal_queries import (
        RunCausalQueriesNode,
    )
    from polisyos.scientist.nodes.builtins.compile.compile_foundry import CompileFoundryNode
    from polisyos.scientist.nodes.builtins.compile.formalize_verified_policy import (
        FormalizeVerifiedPolicyNode,
    )
    from polisyos.scientist.nodes.builtins.compile.link_trinity import LinkTrinityNode
    from polisyos.scientist.nodes.builtins.data.bind_foundry_inputs import BindFoundryInputsNode
    from polisyos.scientist.nodes.builtins.data.build_data_snapshot import BuildDataSnapshotNode
    from polisyos.scientist.nodes.builtins.data.enrich_knowledge import EnrichKnowledgeNode
    from polisyos.scientist.nodes.builtins.decide.build_decision_packet import (
        BuildDecisionPacketNode,
    )
    from polisyos.scientist.nodes.builtins.decide.build_policy_output_bundle import (
        BuildPolicyOutputBundleNode,
    )
    from polisyos.scientist.nodes.builtins.decide.build_verified_policy_report import (
        BuildVerifiedPolicyReportNode,
    )
    from polisyos.scientist.nodes.builtins.decide.run_policy_blueprint_runtime import (
        RunPolicyBlueprintRuntimeNode,
    )
    from polisyos.scientist.nodes.builtins.decide.run_policy_translation import (
        RunPolicyTranslationNode,
    )
    from polisyos.scientist.nodes.builtins.decide.run_translator_compliance import (
        RunTranslatorComplianceNode,
    )
    from polisyos.scientist.nodes.builtins.governance.data_plane_gate import DataPlaneGateNode
    from polisyos.scientist.nodes.builtins.governance.legal_check import LegalCheckNode
    from polisyos.scientist.nodes.builtins.governance.run_normative_arbitration import (
        RunNormativeArbitrationNode,
    )
    from polisyos.scientist.nodes.builtins.governance.run_governance import RunGovernanceNode
    from polisyos.scientist.nodes.builtins.planning.build_execution_plan import (
        BuildExecutionPlanNode,
    )
    from polisyos.scientist.nodes.builtins.planning.assemble_legal_candidate_pack import (
        AssembleLegalCandidatePackNode,
    )
    from polisyos.scientist.nodes.builtins.planning.build_method_catalog_snapshot import (
        BuildMethodCatalogSnapshotNode,
    )
    from polisyos.scientist.nodes.builtins.planning.compile_cross_graph_evidence import (
        CompileCrossGraphEvidenceNode,
    )
    from polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search import (
        RunHierarchicalPolicySearchNode,
    )
    from polisyos.scientist.nodes.builtins.planning.draft_policy_options import (
        DraftPolicyOptionsNode,
    )
    from polisyos.scientist.nodes.builtins.planning.expand_legal_source_pack import (
        ExpandLegalSourcePackNode,
    )
    from polisyos.scientist.nodes.builtins.planning.plan_policy_request import (
        PlanPolicyRequestNode,
    )
    from polisyos.scientist.nodes.builtins.planning.ready_to_run import ReadyToRunNode
    from polisyos.scientist.nodes.builtins.planning.run_source_gap_review import (
        RunSourceGapReviewNode,
    )
    from polisyos.scientist.nodes.builtins.planning.run_source_verification import (
        RunSourceVerificationNode,
    )
    from polisyos.scientist.nodes.builtins.planning.run_evaluator import RunEvaluatorNode
    from polisyos.scientist.nodes.builtins.planning.run_preflight import RunPreflightNode
    from polisyos.scientist.nodes.builtins.planning.run_discovery_blueprint_runtime import (
        RunDiscoveryBlueprintRuntimeNode,
    )
    from polisyos.scientist.nodes.builtins.simulate.propagate_uncertainty import (
        PropagateUncertaintyNode,
    )
    from polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation import (
        RunCausalEvaluationNode,
    )
    from polisyos.scientist.nodes.builtins.simulate.run_distributional_analysis import (
        RunDistributionalAnalysisNode,
    )
    from polisyos.scientist.nodes.builtins.simulate.run_metric_validation import (
        RunMetricValidationNode,
    )
    from polisyos.scientist.nodes.builtins.simulate.run_simulation import RunSimulationNode

    return [
        BuildDataSnapshotNode(),
        PlanPolicyRequestNode(),
        BindFoundryInputsNode(),
        EnrichKnowledgeNode(),
        BuildExecutionPlanNode(),
        BuildMethodCatalogSnapshotNode(),
        AssembleLegalCandidatePackNode(),
        ExpandLegalSourcePackNode(),
        RunSourceVerificationNode(),
        RunSourceGapReviewNode(),
        DraftPolicyOptionsNode(),
        RunPreflightNode(),
        ReadyToRunNode(),
        LinkTrinityNode(),
        FormalizeVerifiedPolicyNode(),
        CompileFoundryNode(),
        CompileCrossGraphEvidenceNode(),
        RunHierarchicalPolicySearchNode(),
        RunSimulationNode(),
        RunMetricValidationNode(),
        BuildLiteraturePriorNode(),
        CounterfactualIdentificationGateNode(),
        ReconcileCausalGraphNode(),
        RunCausalReadinessNode(),
        RunCausalContractExecutionNode(),
        ResolveParametersNode(),
        RunABMConsistencyCheckNode(),
        RunCausalQueriesNode(),
        RunCausalEnsembleNode(),
        RunTransportabilityNode(),
        RunDistributionalAnalysisNode(),
        RunCausalEvaluationNode(),
        PropagateUncertaintyNode(),
        LegalCheckNode(),
        DataPlaneGateNode(),
        RunNormativeArbitrationNode(),
        RunGovernanceNode(),
        RunEvaluatorNode(),
        BuildVerifiedPolicyReportNode(),
        RunPolicyBlueprintRuntimeNode(),
        RunPolicyTranslationNode(),
        RunTranslatorComplianceNode(),
        RunDiscoveryBlueprintRuntimeNode(),
        BuildPolicyOutputBundleNode(),
        BuildDecisionPacketNode(),
    ]


def __getattr__(name: str) -> Any:
    """Resolve individual node classes lazily from their owning modules."""
    if name == "BindFoundryInputsNode":
        from polisyos.scientist.nodes.builtins.data.bind_foundry_inputs import (
            BindFoundryInputsNode,
        )

        return BindFoundryInputsNode
    if name == "BuildDataSnapshotNode":
        from polisyos.scientist.nodes.builtins.data.build_data_snapshot import BuildDataSnapshotNode

        return BuildDataSnapshotNode
    if name == "PlanPolicyRequestNode":
        from polisyos.scientist.nodes.builtins.planning.plan_policy_request import (
            PlanPolicyRequestNode,
        )

        return PlanPolicyRequestNode
    if name == "EnrichKnowledgeNode":
        from polisyos.scientist.nodes.builtins.data.enrich_knowledge import EnrichKnowledgeNode

        return EnrichKnowledgeNode
    if name == "LinkTrinityNode":
        from polisyos.scientist.nodes.builtins.compile.link_trinity import LinkTrinityNode

        return LinkTrinityNode
    if name == "CompileFoundryNode":
        from polisyos.scientist.nodes.builtins.compile.compile_foundry import CompileFoundryNode

        return CompileFoundryNode
    if name == "FormalizeVerifiedPolicyNode":
        from polisyos.scientist.nodes.builtins.compile.formalize_verified_policy import (
            FormalizeVerifiedPolicyNode,
        )

        return FormalizeVerifiedPolicyNode
    if name == "RunSimulationNode":
        from polisyos.scientist.nodes.builtins.simulate.run_simulation import RunSimulationNode

        return RunSimulationNode
    if name == "RunMetricValidationNode":
        from polisyos.scientist.nodes.builtins.simulate.run_metric_validation import (
            RunMetricValidationNode,
        )

        return RunMetricValidationNode
    if name == "BuildLiteraturePriorNode":
        from polisyos.scientist.nodes.builtins.causal.build_literature_prior import (
            BuildLiteraturePriorNode,
        )

        return BuildLiteraturePriorNode
    if name == "CounterfactualIdentificationGateNode":
        from polisyos.scientist.nodes.builtins.causal.counterfactual_identification_gate import (
            CounterfactualIdentificationGateNode,
        )

        return CounterfactualIdentificationGateNode
    if name == "ReconcileCausalGraphNode":
        from polisyos.scientist.nodes.builtins.causal.reconcile_causal_graph import (
            ReconcileCausalGraphNode,
        )

        return ReconcileCausalGraphNode
    if name == "RunCausalReadinessNode":
        from polisyos.scientist.nodes.builtins.causal.run_causal_readiness import (
            RunCausalReadinessNode,
        )

        return RunCausalReadinessNode
    if name == "RunCausalContractExecutionNode":
        from polisyos.scientist.nodes.builtins.causal.run_causal_contract_execution import (
            RunCausalContractExecutionNode,
        )

        return RunCausalContractExecutionNode
    if name == "ResolveParametersNode":
        from polisyos.scientist.nodes.builtins.causal.resolve_parameters import (
            ResolveParametersNode,
        )

        return ResolveParametersNode
    if name == "RunABMConsistencyCheckNode":
        from polisyos.scientist.nodes.builtins.causal.run_abm_consistency import (
            RunABMConsistencyCheckNode,
        )

        return RunABMConsistencyCheckNode
    if name == "RunCausalEnsembleNode":
        from polisyos.scientist.nodes.builtins.causal.run_causal_ensemble import (
            RunCausalEnsembleNode,
        )

        return RunCausalEnsembleNode
    if name == "RunCausalEvaluationNode":
        from polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation import (
            RunCausalEvaluationNode,
        )

        return RunCausalEvaluationNode
    if name == "RunCausalQueriesNode":
        from polisyos.scientist.nodes.builtins.causal.run_causal_queries import (
            RunCausalQueriesNode,
        )

        return RunCausalQueriesNode
    if name == "RunTransportabilityNode":
        from polisyos.scientist.nodes.builtins.causal.resolve_transport import (
            RunTransportabilityNode,
        )

        return RunTransportabilityNode
    if name == "RunDistributionalAnalysisNode":
        from polisyos.scientist.nodes.builtins.simulate.run_distributional_analysis import (
            RunDistributionalAnalysisNode,
        )

        return RunDistributionalAnalysisNode
    if name == "PropagateUncertaintyNode":
        from polisyos.scientist.nodes.builtins.simulate.propagate_uncertainty import (
            PropagateUncertaintyNode,
        )

        return PropagateUncertaintyNode
    if name == "LegalCheckNode":
        from polisyos.scientist.nodes.builtins.governance.legal_check import LegalCheckNode

        return LegalCheckNode
    if name == "DataPlaneGateNode":
        from polisyos.scientist.nodes.builtins.governance.data_plane_gate import DataPlaneGateNode

        return DataPlaneGateNode
    if name == "RunNormativeArbitrationNode":
        from polisyos.scientist.nodes.builtins.governance.run_normative_arbitration import (
            RunNormativeArbitrationNode,
        )

        return RunNormativeArbitrationNode
    if name == "BuildExecutionPlanNode":
        from polisyos.scientist.nodes.builtins.planning.build_execution_plan import (
            BuildExecutionPlanNode,
        )

        return BuildExecutionPlanNode
    if name == "BuildMethodCatalogSnapshotNode":
        from polisyos.scientist.nodes.builtins.planning.build_method_catalog_snapshot import (
            BuildMethodCatalogSnapshotNode,
        )

        return BuildMethodCatalogSnapshotNode
    if name == "AssembleLegalCandidatePackNode":
        from polisyos.scientist.nodes.builtins.planning.assemble_legal_candidate_pack import (
            AssembleLegalCandidatePackNode,
        )

        return AssembleLegalCandidatePackNode
    if name == "CompileCrossGraphEvidenceNode":
        from polisyos.scientist.nodes.builtins.planning.compile_cross_graph_evidence import (
            CompileCrossGraphEvidenceNode,
        )

        return CompileCrossGraphEvidenceNode
    if name == "RunHierarchicalPolicySearchNode":
        from polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search import (
            RunHierarchicalPolicySearchNode,
        )

        return RunHierarchicalPolicySearchNode
    if name == "ExpandLegalSourcePackNode":
        from polisyos.scientist.nodes.builtins.planning.expand_legal_source_pack import (
            ExpandLegalSourcePackNode,
        )

        return ExpandLegalSourcePackNode
    if name == "RunSourceVerificationNode":
        from polisyos.scientist.nodes.builtins.planning.run_source_verification import (
            RunSourceVerificationNode,
        )

        return RunSourceVerificationNode
    if name == "RunSourceGapReviewNode":
        from polisyos.scientist.nodes.builtins.planning.run_source_gap_review import (
            RunSourceGapReviewNode,
        )

        return RunSourceGapReviewNode
    if name == "DraftPolicyOptionsNode":
        from polisyos.scientist.nodes.builtins.planning.draft_policy_options import (
            DraftPolicyOptionsNode,
        )

        return DraftPolicyOptionsNode
    if name == "RunPreflightNode":
        from polisyos.scientist.nodes.builtins.planning.run_preflight import RunPreflightNode

        return RunPreflightNode
    if name == "ReadyToRunNode":
        from polisyos.scientist.nodes.builtins.planning.ready_to_run import ReadyToRunNode

        return ReadyToRunNode
    if name == "RunGovernanceNode":
        from polisyos.scientist.nodes.builtins.governance.run_governance import RunGovernanceNode

        return RunGovernanceNode
    if name == "RunEvaluatorNode":
        from polisyos.scientist.nodes.builtins.planning.run_evaluator import RunEvaluatorNode

        return RunEvaluatorNode
    if name == "BuildDecisionPacketNode":
        from polisyos.scientist.nodes.builtins.decide.build_decision_packet import (
            BuildDecisionPacketNode,
        )

        return BuildDecisionPacketNode
    if name == "BuildPolicyOutputBundleNode":
        from polisyos.scientist.nodes.builtins.decide.build_policy_output_bundle import (
            BuildPolicyOutputBundleNode,
        )

        return BuildPolicyOutputBundleNode
    if name == "BuildVerifiedPolicyReportNode":
        from polisyos.scientist.nodes.builtins.decide.build_verified_policy_report import (
            BuildVerifiedPolicyReportNode,
        )

        return BuildVerifiedPolicyReportNode
    if name == "RunPolicyBlueprintRuntimeNode":
        from polisyos.scientist.nodes.builtins.decide.run_policy_blueprint_runtime import (
            RunPolicyBlueprintRuntimeNode,
        )

        return RunPolicyBlueprintRuntimeNode
    if name == "RunPolicyTranslationNode":
        from polisyos.scientist.nodes.builtins.decide.run_policy_translation import (
            RunPolicyTranslationNode,
        )

        return RunPolicyTranslationNode
    if name == "RunTranslatorComplianceNode":
        from polisyos.scientist.nodes.builtins.decide.run_translator_compliance import (
            RunTranslatorComplianceNode,
        )

        return RunTranslatorComplianceNode
    if name == "RunDiscoveryBlueprintRuntimeNode":
        from polisyos.scientist.nodes.builtins.planning.run_discovery_blueprint_runtime import (
            RunDiscoveryBlueprintRuntimeNode,
        )

        return RunDiscoveryBlueprintRuntimeNode
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
