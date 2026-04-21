"""Machine-readable manifest for the documented IR package facades.

The root :mod:`polisyos.ir` package remains the compatibility boundary for the
widest schema surface. The package facades below are intentionally narrower:

- ``polisyos.ir.analytics`` is a curated convenience facade, not a wildcard
  mirror of every analytics implementation module.
- ``polisyos.ir.kernel`` and ``polisyos.ir.world`` expose their full stable
  contract sets, but now do so lazily to avoid eager import chains.

Tests use this manifest as the export-audit source of truth, and the reference
docs summarize the same package counts and naming rules.
"""
from __future__ import annotations

from typing import TypeAlias

RegistryItemId: TypeAlias = str
"""Canonical registry item key used by fragment composition/linker diagnostics."""

IR_NAMING_CONVENTIONS: dict[str, str] = {
    "_id": (
        "Stable domain identifier stored in payloads and used for referential integrity. "
        "Prefer '*_id' for author-controlled identifiers such as policy_id or slot_id."
    ),
    "_ref": (
        "Typed reference to another persisted artifact or contract boundary. "
        "Inside IR prefer ArtifactRefModel or typed '*Ref' wrappers; reserve raw "
        "'ArtifactRef' naming for core/runtime CAS manifests."
    ),
    "*_key": (
        "Derived lookup or cache key computed from canonical content. "
        "Keys must be reproducible and never double as mutable business identifiers."
    ),
    "ArtifactRef": (
        "Reserved for runtime/core manifest types. IR contracts should expose "
        "ArtifactRefModel or typed '*Ref' classes instead of untyped ArtifactRef payloads."
    ),
    "RegistryItemId": (
        "Conceptual label for registry fragment item keys used in composition, linker, "
        "and diagnostics. It is not a separate wire-format object."
    ),
}

ANALYTICS_FACADE_EXPORTS: dict[str, tuple[str, str]] = {
    "AccessTier": ("polisyos.ir.analytics.data_views", "AccessTier"),
    "BacktestReport": ("polisyos.ir.analytics.backtest", "BacktestReport"),
    "BacktestScenario": ("polisyos.ir.analytics.backtest", "BacktestScenario"),
    "BiasDirection": ("polisyos.ir.analytics.backtest", "BiasDirection"),
    "CausalDiscoveryReport": (
        "polisyos.ir.analytics.causal_discovery",
        "CausalDiscoveryReport",
    ),
    "CausalBridgeTarget": (
        "polisyos.ir.analytics.ecosystem_bridges",
        "CausalBridgeTarget",
    ),
    "CausalNexGraphBridge": (
        "polisyos.ir.analytics.ecosystem_bridges",
        "CausalNexGraphBridge",
    ),
    "CausalEdge": ("polisyos.ir.analytics.causal_graph", "CausalEdge"),
    "CausalEffectReport": ("polisyos.ir.analytics.causal", "CausalEffectReport"),
    "CausalGraphModel": ("polisyos.ir.analytics.causal_graph", "CausalGraphModel"),
    "CausalInterventionSpec": (
        "polisyos.ir.analytics.causal_queries",
        "CausalInterventionSpec",
    ),
    "CausalMethod": ("polisyos.ir.analytics.causal", "CausalMethod"),
    "CausalModelEnsemble": (
        "polisyos.ir.analytics.causal_ensemble",
        "CausalModelEnsemble",
    ),
    "CausalQuery": ("polisyos.ir.analytics.causal_queries", "CausalQuery"),
    "CausalQueryResult": (
        "polisyos.ir.analytics.causal_queries",
        "CausalQueryResult",
    ),
    "CausalRunSnapshot": (
        "polisyos.ir.analytics.causal_run_snapshot",
        "CausalRunSnapshot",
    ),
    "CohortDimension": ("polisyos.ir.analytics.distributional", "CohortDimension"),
    "CohortImpact": ("polisyos.ir.analytics.distributional", "CohortImpact"),
    "DataFilter": ("polisyos.ir.analytics.data_views", "DataFilter"),
    "DataViewRequest": ("polisyos.ir.analytics.data_views", "DataViewRequest"),
    "DataViewType": ("polisyos.ir.analytics.data_views", "DataViewType"),
    "DiagnosticTest": ("polisyos.ir.analytics.causal", "DiagnosticTest"),
    "DoWhyGraphBridge": (
        "polisyos.ir.analytics.ecosystem_bridges",
        "DoWhyGraphBridge",
    ),
    "DimensionBreakdown": (
        "polisyos.ir.analytics.distributional",
        "DimensionBreakdown",
    ),
    "DistributionFamily": ("polisyos.ir.analytics.uncertainty", "DistributionFamily"),
    "DistributionalReport": (
        "polisyos.ir.analytics.distributional",
        "DistributionalReport",
    ),
    "MetricValidationReport": (
        "polisyos.ir.analytics.metric_validation_report",
        "MetricValidationReport",
    ),
    "EdgeMark": ("polisyos.ir.analytics.causal_graph", "EdgeMark"),
    "EdgeSource": ("polisyos.ir.analytics.causal_graph", "EdgeSource"),
    "EconMLDesignBridge": (
        "polisyos.ir.analytics.ecosystem_bridges",
        "EconMLDesignBridge",
    ),
    "EnsembleMember": ("polisyos.ir.analytics.causal_ensemble", "EnsembleMember"),
    "EstimationStatus": ("polisyos.ir.analytics.causal", "EstimationStatus"),
    "FeatureImportance": ("polisyos.ir.analytics.hte", "FeatureImportance"),
    "FiniteStrategicPayoffTable": (
        "polisyos.ir.analytics.strategic",
        "FiniteStrategicPayoffTable",
    ),
    "LatentConfounderContract": (
        "polisyos.ir.analytics.representation_learning",
        "LatentConfounderContract",
    ),
    "RepresentationLearningResult": (
        "polisyos.ir.analytics.representation_learning",
        "RepresentationLearningResult",
    ),
    "RepresentationModelFamily": (
        "polisyos.ir.analytics.representation_learning",
        "RepresentationModelFamily",
    ),
    "GraphType": ("polisyos.ir.analytics.causal_graph", "GraphType"),
    "HTEResult": ("polisyos.ir.analytics.hte", "HTEResult"),
    "ImpactDirection": ("polisyos.ir.analytics.distributional", "ImpactDirection"),
    "EnvironmentShiftType": (
        "polisyos.ir.analytics.invariance",
        "EnvironmentShiftType",
    ),
    "InvarianceMethod": ("polisyos.ir.analytics.invariance", "InvarianceMethod"),
    "InvarianceResult": ("polisyos.ir.analytics.invariance", "InvarianceResult"),
    "InvarianceVerdict": ("polisyos.ir.analytics.invariance", "InvarianceVerdict"),
    "RegimeShiftIdentificationCertificate": (
        "polisyos.ir.analytics.invariance",
        "RegimeShiftIdentificationCertificate",
    ),
    "RegimeShiftIdentificationCertificateRef": (
        "polisyos.ir.refs",
        "RegimeShiftIdentificationCertificateRef",
    ),
    "MultiEnvironmentCausalContract": (
        "polisyos.ir.analytics.invariance",
        "MultiEnvironmentCausalContract",
    ),
    "DPUtilityManifest": (
        "polisyos.ir.analytics.privacy_transportability",
        "DPUtilityManifest",
    ),
    "PrivacyAwareTransportCertificate": (
        "polisyos.ir.analytics.privacy_transportability",
        "PrivacyAwareTransportCertificate",
    ),
    "PrivacyAwareTransportCertificateRef": (
        "polisyos.ir.refs",
        "PrivacyAwareTransportCertificateRef",
    ),
    "PrivacyObservedMode": (
        "polisyos.ir.analytics.privacy_transportability",
        "PrivacyObservedMode",
    ),
    "InterventionSpec": ("polisyos.ir.analytics.causal_queries", "InterventionSpec"),
    "InterventionType": ("polisyos.ir.analytics.causal_queries", "InterventionType"),
    "InterventionCertificate": (
        "polisyos.ir.analytics.interventions",
        "InterventionCertificate",
    ),
    "InterventionQuery": (
        "polisyos.ir.analytics.interventions",
        "InterventionQuery",
    ),
    "ProofKernelInterventionType": (
        "polisyos.ir.analytics.interventions",
        "ProofKernelInterventionType",
    ),
    "IntervalSemantics": ("polisyos.ir.analytics.uncertainty", "IntervalSemantics"),
    "CausalDecisionProcessType": (
        "polisyos.ir.analytics.causal_rl",
        "CausalDecisionProcessType",
    ),
    "CausalRLContract": ("polisyos.ir.analytics.causal_rl", "CausalRLContract"),
    "CausalRLResult": ("polisyos.ir.analytics.causal_rl", "CausalRLResult"),
    "CounterfactualPolicyOptimizationSpec": (
        "polisyos.ir.analytics.causal_rl",
        "CounterfactualPolicyOptimizationSpec",
    ),
    "MechanismFamily": (
        "polisyos.ir.analytics.structural_causal_model",
        "MechanismFamily",
    ),
    "MechanismSource": (
        "polisyos.ir.analytics.structural_causal_model",
        "MechanismSource",
    ),
    "MetricUnit": ("polisyos.ir.analytics.distributional", "MetricUnit"),
    "NodeMechanism": (
        "polisyos.ir.analytics.structural_causal_model",
        "NodeMechanism",
    ),
    "OutcomeComparison": ("polisyos.ir.analytics.backtest", "OutcomeComparison"),
    "PAGIdentificationPolicy": (
        "polisyos.ir.analytics.causal_graph",
        "PAGIdentificationPolicy",
    ),
    "PgmpyGraphBridge": (
        "polisyos.ir.analytics.ecosystem_bridges",
        "PgmpyGraphBridge",
    ),
    "PlaceboResult": ("polisyos.ir.analytics.causal", "PlaceboResult"),
    "PolicyRecommendation": ("polisyos.ir.analytics.hte", "PolicyRecommendation"),
    "PropagationMethod": ("polisyos.ir.analytics.uncertainty", "PropagationMethod"),
    "QueryType": ("polisyos.ir.analytics.causal_queries", "QueryType"),
    "RefutationResult": ("polisyos.ir.analytics.causal", "RefutationResult"),
    "RefutationTestType": ("polisyos.ir.analytics.causal", "RefutationTestType"),
    "JointDecisionCertificate": (
        "polisyos.ir.analytics.recoverability",
        "JointDecisionCertificate",
    ),
    "JointDecisionStatus": (
        "polisyos.ir.analytics.recoverability",
        "JointDecisionStatus",
    ),
    "KernelEstimatorSpec": (
        "polisyos.ir.analytics.kernel_causal",
        "KernelEstimatorSpec",
    ),
    "KernelEstimatorSpecRef": (
        "polisyos.ir.refs",
        "KernelEstimatorSpecRef",
    ),
    "KernelEstimatorTemplate": (
        "polisyos.ir.analytics.kernel_causal",
        "KernelEstimatorTemplate",
    ),
    "KernelLoweringDisposition": (
        "polisyos.ir.analytics.kernel_causal",
        "KernelLoweringDisposition",
    ),
    "KernelSpec": (
        "polisyos.ir.analytics.kernel_causal",
        "KernelSpec",
    ),
    "KernelTargetRepresentation": (
        "polisyos.ir.analytics.kernel_causal",
        "KernelTargetRepresentation",
    ),
    "RecoverabilityCertificate": (
        "polisyos.ir.analytics.recoverability",
        "RecoverabilityCertificate",
    ),
    "RecoverabilityCertificateStatus": (
        "polisyos.ir.analytics.recoverability",
        "RecoverabilityCertificateStatus",
    ),
    "RecourseAction": ("polisyos.ir.analytics.recourse", "RecourseAction"),
    "RecourseActionType": ("polisyos.ir.analytics.recourse", "RecourseActionType"),
    "RecourseFeasibility": ("polisyos.ir.analytics.recourse", "RecourseFeasibility"),
    "RecoursePlan": ("polisyos.ir.analytics.recourse", "RecoursePlan"),
    "RecourseReport": ("polisyos.ir.analytics.recourse", "RecourseReport"),
    "CounterfactualExplanation": (
        "polisyos.ir.analytics.recourse",
        "CounterfactualExplanation",
    ),
    "ContrastiveExplanation": (
        "polisyos.ir.analytics.recourse",
        "ContrastiveExplanation",
    ),
    "MeanFieldEquilibriumCertificate": (
        "polisyos.ir.analytics.strategic",
        "MeanFieldEquilibriumCertificate",
    ),
    "MeanFieldMacroSimulationConfig": (
        "polisyos.ir.analytics.strategic",
        "MeanFieldMacroSimulationConfig",
    ),
    "MeanFieldPerturbationSpec": (
        "polisyos.ir.analytics.strategic",
        "MeanFieldPerturbationSpec",
    ),
    "PerformativeInstabilityReason": (
        "polisyos.ir.analytics.strategic",
        "PerformativeInstabilityReason",
    ),
    "PerformativeLoopAnalysisScope": (
        "polisyos.ir.analytics.strategic",
        "PerformativeLoopAnalysisScope",
    ),
    "PerformativeLoopCertificate": (
        "polisyos.ir.analytics.strategic",
        "PerformativeLoopCertificate",
    ),
    "PerformativeLoopProofFamily": (
        "polisyos.ir.analytics.strategic",
        "PerformativeLoopProofFamily",
    ),
    "PerformativeLoopRecommendedAction": (
        "polisyos.ir.analytics.strategic",
        "PerformativeLoopRecommendedAction",
    ),
    "PerformativeLoopStabilityStatus": (
        "polisyos.ir.analytics.strategic",
        "PerformativeLoopStabilityStatus",
    ),
    "PerformativeLoopWitnessStrength": (
        "polisyos.ir.analytics.strategic",
        "PerformativeLoopWitnessStrength",
    ),
    "PerformativeShiftSummary": (
        "polisyos.ir.analytics.strategic",
        "PerformativeShiftSummary",
    ),
    "StrategicAdmissibilityRecord": (
        "polisyos.ir.analytics.strategic",
        "StrategicAdmissibilityRecord",
    ),
    "StrategicDecompositionCertificate": (
        "polisyos.ir.analytics.strategic",
        "StrategicDecompositionCertificate",
    ),
    "StrategicDecompositionFailureCard": (
        "polisyos.ir.analytics.strategic",
        "StrategicDecompositionFailureCard",
    ),
    "StrategicDecompositionSemantics": (
        "polisyos.ir.analytics.strategic",
        "StrategicDecompositionSemantics",
    ),
    "StrategicDecompositionStatus": (
        "polisyos.ir.analytics.strategic",
        "StrategicDecompositionStatus",
    ),
    "StrategicEquilibriumDescriptor": (
        "polisyos.ir.analytics.strategic",
        "StrategicEquilibriumDescriptor",
    ),
    "StrategicEquilibriumConcept": (
        "polisyos.ir.analytics.strategic",
        "StrategicEquilibriumConcept",
    ),
    "StrategicFallbackMode": (
        "polisyos.ir.analytics.strategic",
        "StrategicFallbackMode",
    ),
    "StrategicGameClass": (
        "polisyos.ir.analytics.strategic",
        "StrategicGameClass",
    ),
    "StrategicResponseBundle": (
        "polisyos.ir.analytics.strategic",
        "StrategicResponseBundle",
    ),
    "StrategicSCM": ("polisyos.ir.analytics.strategic", "StrategicSCM"),
    "StrategicSolutionConcept": (
        "polisyos.ir.analytics.strategic",
        "StrategicSolutionConcept",
    ),
    "StrategicTractabilityClass": (
        "polisyos.ir.analytics.strategic",
        "StrategicTractabilityClass",
    ),
    "StructuralCausalModelSpec": (
        "polisyos.ir.analytics.structural_causal_model",
        "StructuralCausalModelSpec",
    ),
    "SubgroupEffect": ("polisyos.ir.analytics.hte", "SubgroupEffect"),
    "SystematicBias": ("polisyos.ir.analytics.backtest", "SystematicBias"),
    "TargetingRule": ("polisyos.ir.analytics.hte", "TargetingRule"),
    "TemporalDiscoveryMethod": (
        "polisyos.ir.analytics.temporal_frontier",
        "TemporalDiscoveryMethod",
    ),
    "DynamicProcessFamily": (
        "polisyos.ir.analytics.temporal_frontier",
        "DynamicProcessFamily",
    ),
    "EquivalenceClassType": (
        "polisyos.ir.analytics.temporal_frontier",
        "EquivalenceClassType",
    ),
    "TemporalDiscoveryFrontierReport": (
        "polisyos.ir.analytics.temporal_frontier",
        "TemporalDiscoveryFrontierReport",
    ),
    "TemporalDiscoveryEdge": (
        "polisyos.ir.analytics.temporal_frontier",
        "TemporalDiscoveryEdge",
    ),
    "TigramiteEdge": ("polisyos.ir.analytics.ecosystem_bridges", "TigramiteEdge"),
    "TigramitePCMCIBridge": (
        "polisyos.ir.analytics.ecosystem_bridges",
        "TigramitePCMCIBridge",
    ),
    "TransportabilityResult": (
        "polisyos.ir.analytics.transportability",
        "TransportabilityResult",
    ),
    "ForecastCalibrationMethod": (
        "polisyos.ir.analytics.forecasting_uncertainty",
        "ForecastCalibrationMethod",
    ),
    "ForecastCoverageDiagnostic": (
        "polisyos.ir.analytics.forecasting_uncertainty",
        "ForecastCoverageDiagnostic",
    ),
    "ForecastIntervalSemantics": (
        "polisyos.ir.analytics.forecasting_uncertainty",
        "ForecastIntervalSemantics",
    ),
    "ForecastingUncertaintyBundle": (
        "polisyos.ir.analytics.forecasting_uncertainty",
        "ForecastingUncertaintyBundle",
    ),
    "FanChartSpec": (
        "polisyos.ir.analytics.forecasting_uncertainty",
        "FanChartSpec",
    ),
    "HorizonInterval": (
        "polisyos.ir.analytics.forecasting_uncertainty",
        "HorizonInterval",
    ),
    "HorizonPolicySpec": (
        "polisyos.ir.analytics.forecasting_uncertainty",
        "HorizonPolicySpec",
    ),
    "UncertaintyEnvelope": (
        "polisyos.ir.analytics.uncertainty",
        "UncertaintyEnvelope",
    ),
    "UncertaintySource": ("polisyos.ir.analytics.uncertainty", "UncertaintySource"),
    "to_causalnex_graph_bridge": (
        "polisyos.ir.analytics.ecosystem_bridges",
        "to_causalnex_graph_bridge",
    ),
    "to_dowhy_graph_bridge": (
        "polisyos.ir.analytics.ecosystem_bridges",
        "to_dowhy_graph_bridge",
    ),
    "to_econml_design_bridge": (
        "polisyos.ir.analytics.ecosystem_bridges",
        "to_econml_design_bridge",
    ),
    "to_pgmpy_graph_bridge": (
        "polisyos.ir.analytics.ecosystem_bridges",
        "to_pgmpy_graph_bridge",
    ),
    "to_tigramite_pcmci_bridge": (
        "polisyos.ir.analytics.ecosystem_bridges",
        "to_tigramite_pcmci_bridge",
    ),
    "WinnersLosersEntry": (
        "polisyos.ir.analytics.distributional",
        "WinnersLosersEntry",
    ),
    "WinnersLosersTable": (
        "polisyos.ir.analytics.distributional",
        "WinnersLosersTable",
    ),
}

KERNEL_FACADE_EXPORTS: dict[str, tuple[str, str]] = {
    "ConflictResolution": ("polisyos.ir.kernel.merge_rules", "ConflictResolution"),
    "ConstraintRegistry": ("polisyos.ir.kernel.constraints", "ConstraintRegistry"),
    "ConstraintSpec": ("polisyos.ir.kernel.constraints", "ConstraintSpec"),
    "CountUnit": ("polisyos.ir.kernel.units", "CountUnit"),
    "CountValue": ("polisyos.ir.kernel.values", "CountValue"),
    "DEFAULT_CONSTRAINT_REGISTRY": (
        "polisyos.ir.kernel.constraints",
        "DEFAULT_CONSTRAINT_REGISTRY",
    ),
    "DEFAULT_MECHANISM_REGISTRY": (
        "polisyos.ir.kernel.mechanisms",
        "DEFAULT_MECHANISM_REGISTRY",
    ),
    "DEFAULT_MERGE_RULE_REGISTRY": (
        "polisyos.ir.kernel.merge_rules",
        "DEFAULT_MERGE_RULE_REGISTRY",
    ),
    "DEFAULT_METRIC_REGISTRY": (
        "polisyos.ir.kernel.metrics",
        "DEFAULT_METRIC_REGISTRY",
    ),
    "DEFAULT_SELECTOR_FIELD_REGISTRY": (
        "polisyos.ir.kernel.selector_fields",
        "DEFAULT_SELECTOR_FIELD_REGISTRY",
    ),
    "DEFAULT_SLOT_REGISTRY": ("polisyos.ir.kernel.slots", "DEFAULT_SLOT_REGISTRY"),
    "DEFAULT_TRUST_REGISTRY": ("polisyos.ir.kernel.trust", "DEFAULT_TRUST_REGISTRY"),
    "DEFAULT_UNITS_REGISTRY": ("polisyos.ir.kernel.units", "DEFAULT_UNITS_REGISTRY"),
    "DecimalValue": ("polisyos.ir.kernel.numbers", "DecimalValue"),
    "DimensionlessUnit": ("polisyos.ir.kernel.units", "DimensionlessUnit"),
    "DurationUnit": ("polisyos.ir.kernel.units", "DurationUnit"),
    "DurationValue": ("polisyos.ir.kernel.values", "DurationValue"),
    "GenericUnit": ("polisyos.ir.kernel.units", "GenericUnit"),
    "ID_PATTERN": ("polisyos.ir.kernel.base", "ID_PATTERN"),
    "KernelModel": ("polisyos.ir.kernel.base", "KernelModel"),
    "MechanismTypeRegistry": (
        "polisyos.ir.kernel.mechanisms",
        "MechanismTypeRegistry",
    ),
    "MechanismTypeSpec": ("polisyos.ir.kernel.mechanisms", "MechanismTypeSpec"),
    "MergeOverride": ("polisyos.ir.kernel.slots", "MergeOverride"),
    "MergeRuleKind": ("polisyos.ir.kernel.merge_rules", "MergeRuleKind"),
    "MergeRuleRef": ("polisyos.ir.kernel.merge_rules", "MergeRuleRef"),
    "MergeRuleRegistry": ("polisyos.ir.kernel.merge_rules", "MergeRuleRegistry"),
    "MergeRuleSpec": ("polisyos.ir.kernel.merge_rules", "MergeRuleSpec"),
    "MetricRegistry": ("polisyos.ir.kernel.metrics", "MetricRegistry"),
    "MetricSpec": ("polisyos.ir.kernel.metrics", "MetricSpec"),
    "MoneyUnit": ("polisyos.ir.kernel.units", "MoneyUnit"),
    "MoneyValue": ("polisyos.ir.kernel.values", "MoneyValue"),
    "NonNegativeDecimal": ("polisyos.ir.kernel.numbers", "NonNegativeDecimal"),
    "ParamSpec": ("polisyos.ir.kernel.mechanisms", "ParamSpec"),
    "ParamType": ("polisyos.ir.kernel.mechanisms", "ParamType"),
    "PositiveDecimal": ("polisyos.ir.kernel.numbers", "PositiveDecimal"),
    "RateUnit": ("polisyos.ir.kernel.units", "RateUnit"),
    "RateValue": ("polisyos.ir.kernel.values", "RateValue"),
    "SLOT_ID_PATTERN": ("polisyos.ir.kernel.base", "SLOT_ID_PATTERN"),
    "SelectorFieldRegistry": (
        "polisyos.ir.kernel.selector_fields",
        "SelectorFieldRegistry",
    ),
    "SelectorFieldSpec": (
        "polisyos.ir.kernel.selector_fields",
        "SelectorFieldSpec",
    ),
    "SlotKind": ("polisyos.ir.kernel.slots", "SlotKind"),
    "SlotRegistry": ("polisyos.ir.kernel.slots", "SlotRegistry"),
    "SlotScope": ("polisyos.ir.kernel.slots", "SlotScope"),
    "SlotSpec": ("polisyos.ir.kernel.slots", "SlotSpec"),
    "SlotValueType": ("polisyos.ir.kernel.slots", "SlotValueType"),
    "TimeSemantics": ("polisyos.ir.kernel.time_semantics", "TimeSemantics"),
    "TrustPolicySpec": ("polisyos.ir.kernel.trust", "TrustPolicySpec"),
    "TrustRegistry": ("polisyos.ir.kernel.trust", "TrustRegistry"),
    "UnitKind": ("polisyos.ir.kernel.units", "UnitKind"),
    "UnitRef": ("polisyos.ir.kernel.units", "UnitRef"),
    "UnitSpecType": ("polisyos.ir.kernel.units", "UnitSpecType"),
    "UnitsRegistry": ("polisyos.ir.kernel.units", "UnitsRegistry"),
}

WORLD_FACADE_EXPORTS: dict[str, tuple[str, str]] = {
    "Claim": ("polisyos.ir.world.claim", "Claim"),
    "ClaimSourceKind": ("polisyos.ir.world.claim", "ClaimSourceKind"),
    "ConflictKind": ("polisyos.ir.world.conflict", "ConflictKind"),
    "ConflictResolution": ("polisyos.ir.world.conflict", "ConflictResolution"),
    "ConflictResolutionCandidate": (
        "polisyos.ir.world.conflict",
        "ConflictResolutionCandidate",
    ),
    "ConflictResolutionInputs": (
        "polisyos.ir.world.conflict",
        "ConflictResolutionInputs",
    ),
    "ConflictSet": ("polisyos.ir.world.conflict", "ConflictSet"),
    "ConflictSetResolution": (
        "polisyos.ir.world.conflict",
        "ConflictSetResolution",
    ),
    "DocFragment": ("polisyos.ir.world.doc", "DocFragment"),
    "DocMeta": ("polisyos.ir.world.doc", "DocMeta"),
    "EdgeKind": ("polisyos.ir.world.abi", "EdgeKind"),
    "EventKind": ("polisyos.ir.world.event", "EventKind"),
    "NodeKind": ("polisyos.ir.world.abi", "NodeKind"),
    "ProvActivity": ("polisyos.ir.world.event", "ProvActivity"),
    "ProvActivityType": ("polisyos.ir.world.event", "ProvActivityType"),
    "ProvAgent": ("polisyos.ir.world.event", "ProvAgent"),
    "ProvAgentType": ("polisyos.ir.world.event", "ProvAgentType"),
    "ProvOActivityRecord": ("polisyos.ir.world.prov_o", "ProvOActivityRecord"),
    "ProvOAgent": ("polisyos.ir.world.prov_o", "ProvOAgent"),
    "ProvODocument": ("polisyos.ir.world.prov_o", "ProvODocument"),
    "ProvOEntity": ("polisyos.ir.world.prov_o", "ProvOEntity"),
    "ProvORelation": ("polisyos.ir.world.prov_o", "ProvORelation"),
    "ProvORelationType": ("polisyos.ir.world.prov_o", "ProvORelationType"),
    "ProvORecordType": ("polisyos.ir.world.prov_o", "ProvORecordType"),
    "QualityIssue": ("polisyos.ir.world.quality", "QualityIssue"),
    "QualityIssueSeverity": ("polisyos.ir.world.quality", "QualityIssueSeverity"),
    "QualityReport": ("polisyos.ir.world.quality", "QualityReport"),
    "QualityScope": ("polisyos.ir.world.quality", "QualityScope"),
    "RESERVED_WORLD_PREFIXES_V1": (
        "polisyos.ir.world.abi",
        "RESERVED_WORLD_PREFIXES_V1",
    ),
    "TrustAssessment": ("polisyos.ir.world.trust", "TrustAssessment"),
    "TrustTier": ("polisyos.ir.world.trust", "TrustTier"),
    "WORLD_ARTIFACT_ID": ("polisyos.ir.world.predicates", "WORLD_ARTIFACT_ID"),
    "WORLD_KIND": ("polisyos.ir.world.predicates", "WORLD_KIND"),
    "WORLD_LABEL": ("polisyos.ir.world.predicates", "WORLD_LABEL"),
    "WORLD_PROPS_REF": ("polisyos.ir.world.predicates", "WORLD_PROPS_REF"),
    "WORLD_REL_PREFIX": ("polisyos.ir.world.predicates", "WORLD_REL_PREFIX"),
    "WorldEvent": ("polisyos.ir.world.event", "WorldEvent"),
    "WorldObjectRef": ("polisyos.ir.world.event", "WorldObjectRef"),
    "artifact_id_to_world_id": (
        "polisyos.ir.world.ids",
        "artifact_id_to_world_id",
    ),
    "claim_id_from_payload": ("polisyos.ir.world.ids", "claim_id_from_payload"),
    "conflict_set_id_from_key": (
        "polisyos.ir.world.ids",
        "conflict_set_id_from_key",
    ),
    "doc_fragment_id": ("polisyos.ir.world.ids", "doc_fragment_id"),
    "doc_source_id": ("polisyos.ir.world.ids", "doc_source_id"),
    "doc_version_id_from_raw_artifact": (
        "polisyos.ir.world.ids",
        "doc_version_id_from_raw_artifact",
    ),
    "quality_report_id_from_payload": (
        "polisyos.ir.world.ids",
        "quality_report_id_from_payload",
    ),
    "rel": ("polisyos.ir.world.predicates", "rel"),
    "sha256_hex_from_artifact_id": (
        "polisyos.ir.world.ids",
        "sha256_hex_from_artifact_id",
    ),
    "stable_world_id_from_canon": (
        "polisyos.ir.world.ids",
        "stable_world_id_from_canon",
    ),
    "to_prov_o_activity": ("polisyos.ir.world.prov_o", "to_prov_o_activity"),
    "to_prov_o_agent": ("polisyos.ir.world.prov_o", "to_prov_o_agent"),
    "to_prov_o_entity": ("polisyos.ir.world.prov_o", "to_prov_o_entity"),
    "to_prov_o_world_event": ("polisyos.ir.world.prov_o", "to_prov_o_world_event"),
    "trust_assessment_id_from_payload": (
        "polisyos.ir.world.ids",
        "trust_assessment_id_from_payload",
    ),
    "world_event_id_from_payload": (
        "polisyos.ir.world.ids",
        "world_event_id_from_payload",
    ),
}

PACKAGE_FACADE_EXPORTS: dict[str, dict[str, tuple[str, str]]] = {
    "analytics": ANALYTICS_FACADE_EXPORTS,
    "kernel": KERNEL_FACADE_EXPORTS,
    "world": WORLD_FACADE_EXPORTS,
}

PACKAGE_FACADE_IMPORT_POLICY: dict[str, str] = {
    "analytics": "curated lazy facade",
    "kernel": "full lazy facade",
    "world": "full lazy facade",
}


def facade_export_names(package: str) -> list[str]:
    """Return the sorted export list for one documented package facade."""
    return sorted(PACKAGE_FACADE_EXPORTS[package])


__all__ = [
    "ANALYTICS_FACADE_EXPORTS",
    "IR_NAMING_CONVENTIONS",
    "KERNEL_FACADE_EXPORTS",
    "PACKAGE_FACADE_EXPORTS",
    "PACKAGE_FACADE_IMPORT_POLICY",
    "RegistryItemId",
    "WORLD_FACADE_EXPORTS",
    "facade_export_names",
]
