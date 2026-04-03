"""Expose the observation contract stack through a lazy package facade.

The stable surface spans raw records/panels, family governance policy,
measurement routing, bundle manifests, compiler-facing contracts, and
readiness/execution artifacts. Names in ``__all__`` are imported lazily so
callers can depend on IR schemas without eagerly loading every compiler or
runtime protocol dependency.
"""
from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "ObservationFamily",
    "EntityScope",
    "IdentificationMode",
    "SourceConfidenceTier",
    "MultiplexGraphLayerId",
    "StrategicResponseChannel",
    "ObservationRecord",
    "ObservationPanel",
    "GovernancePassAliasStatus",
    "GovernancePassAlias",
    "GovernancePassAliasRegistry",
    "ObservationFamilyPolicy",
    "ObservationFamilyPolicyRegistry",
    "GovernancePassMappingRegistry",
    "DEFAULT_GOVERNANCE_PASS_ALIAS_REGISTRY",
    "DEFAULT_OBSERVATION_FAMILY_POLICY_REGISTRY",
    "DEFAULT_GOVERNANCE_PASS_MAPPING_REGISTRY",
    "MeasurementTrustTier",
    "MeasurementTierRule",
    "ProxyMappingRule",
    "SchemaChangepoint",
    "SchemaRegimeSpec",
    "RegimeCalendarEntry",
    "ShockCalendarEntry",
    "RegimeCalendar",
    "ShockCalendar",
    "SchemaRegimeRegistry",
    "MeasurementRegistry",
    "IdentificationRoute",
    "IdentificationModeRouter",
    "ContractCompatibilityTarget",
    "BundleLineageRef",
    "RequiredArraySpec",
    "RequiredColumnSpec",
    "BundleAxisSemantic",
    "ObservationContractRoute",
    "ObservationContractArtifact",
    "BoundsChannelSpec",
    "ProxyChannelSpec",
    "SpecificationCurveSource",
    "StrategicResponseSpec",
    "TransportabilityCheckSpec",
    "CounterfactualCheckSpec",
    "InterferenceLossTargetSpec",
    "LessonRegistrySeedEntry",
    "CalibrationTargetBundleManifest",
    "MicrosimSurveyContractBundle",
    "NetworkContractBundle",
    "NetworkCausalContractBundle",
    "CausalPanelBundleManifest",
    "BacktestPlanBundle",
    "ObservationToContractManifest",
    "BoundsEstimationBundle",
    "ProxyIdentificationBundle",
    "DTRTreatmentSequenceBundleManifest",
    "PanelEconometricBundleManifest",
    "SurvivalDataBundleManifest",
    "AgentFactorEmbeddingsBundleManifest",
    "CellPrototypeEmbeddingsBundleManifest",
    "BilevelProblemBundle",
    "HeckmanCorrectionBundle",
    "SurvivalHazardBundle",
    "SobolDiagnosticsBundle",
    "SpecificationCurveDiagnosticsBundle",
    "SpecificationCurveBundle",
    "LeontiefIOBundle",
    "StrategicResponseSpecsBundle",
    "TransportabilityCheckBundle",
    "CounterfactualCheckBundle",
    "InterferenceLossSpecBundle",
    "GovernancePassMappingBundle",
    "LessonRegistrySeedBundle",
    "SURVEY_MICRODATA_TARGET",
    "NETWORK_DATA_TARGET",
    "NETWORK_ANALYSIS_TARGET",
    "MULTIPLEX_NETWORK_TARGET",
    "PANEL_OBSERVATIONAL_TARGET",
    "PROXY_MEASUREMENT_TARGET",
    "DYNAMIC_TREATMENT_TARGET",
    "PANEL_ECONOMETRIC_TARGET",
    "SURVIVAL_DATA_TARGET",
    "BACKTEST_PLAN_TARGET",
    "LESSON_CARD_TARGET",
    "SECTION_15_7_BUNDLE_MODELS",
    "ObservationContractCompileError",
    "BoundsEstimationInput",
    "SpecificationCurveInput",
    "LeontiefIOInput",
    "GraphEdge",
    "GraphBipartiteEdge",
    "GraphArtifacts",
    "FirmEventRecord",
    "FirmEvents",
    "FirmPanelRow",
    "FirmPanels",
    "RegionSectorFlowRow",
    "RegionSectorPanels",
    "ProxyMap",
    "SurveyMicroDataCompileSpec",
    "NetworkContractCompileSpec",
    "NetworkCausalCompileSpec",
    "PanelObservationalCompileSpec",
    "DynamicTreatmentCompileSpec",
    "SurvivalCompileSpec",
    "PanelEconometricCompileSpec",
    "BoundsEstimationCompileSpec",
    "ProxyMeasurementCompileSpec",
    "HistoricalValidationCompileSpec",
    "SpecificationCurveSourceSpec",
    "SpecificationCurveCompileSpec",
    "LeontiefIOCompileSpec",
    "CompiledObservationArtifact",
    "HistoricalValidationCompilation",
    "ObservationContractSuiteResult",
    "SparseDenseBridge",
    "ObservationCompilerContext",
    "SurveyMicroDataCompiler",
    "NetworkContractCompiler",
    "NetworkCausalDataCompiler",
    "PanelObservationalCompiler",
    "DynamicTreatmentCompiler",
    "SurvivalDataCompiler",
    "PanelEconometricCompiler",
    "BoundsInputCompiler",
    "ProxyMeasurementCompiler",
    "HistoricalValidationPlanCompiler",
    "SpecificationCurveCompiler",
    "LeontiefIOCompiler",
    "write_json_bundle",
    "load_json_bundle",
    "write_npz_payload",
    "load_npz_payload",
    "write_parquet_rows",
    "load_parquet_rows",
    "ObservationContractCompilerSuite",
    "CalibrationSplitLabel",
    "CalibrationSplitWindow",
    "CalibrationSplitPlan",
    "NegativeControlSpec",
    "CalibrationSplitter",
    "CalibrationTargetBundleCompiler",
    "NegativeControlGenerator",
    "BoundsEstimationTask",
    "TemporalDTRTask",
    "BoundsEstimationEntry",
    "TemporalDTRExecutionEntry",
    "CausalExecutionBundle",
    "persist_causal_execution_bundle",
    "load_causal_execution_bundle",
    "ProxyIdentificationEntry",
    "TransportabilityCheckEntry",
    "StrategicResponseEntry",
    "CounterfactualCheckEntry",
    "InterferenceReadinessEntry",
    "CausalReadinessBundle",
    "persist_causal_readiness_bundle",
    "load_causal_readiness_bundle",
]

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "ObservationFamily": ("polisyos.ir.observation.contracts", "ObservationFamily"),
    "EntityScope": ("polisyos.ir.observation.contracts", "EntityScope"),
    "IdentificationMode": ("polisyos.ir.observation.contracts", "IdentificationMode"),
    "SourceConfidenceTier": ("polisyos.ir.observation.contracts", "SourceConfidenceTier"),
    "MultiplexGraphLayerId": ("polisyos.ir.observation.contracts", "MultiplexGraphLayerId"),
    "StrategicResponseChannel": (
        "polisyos.ir.observation.contracts",
        "StrategicResponseChannel",
    ),
    "ObservationRecord": ("polisyos.ir.observation.contracts", "ObservationRecord"),
    "ObservationPanel": ("polisyos.ir.observation.contracts", "ObservationPanel"),
    "GovernancePassAliasStatus": (
        "polisyos.ir.observation.governance",
        "GovernancePassAliasStatus",
    ),
    "GovernancePassAlias": ("polisyos.ir.observation.governance", "GovernancePassAlias"),
    "GovernancePassAliasRegistry": (
        "polisyos.ir.observation.governance",
        "GovernancePassAliasRegistry",
    ),
    "ObservationFamilyPolicy": (
        "polisyos.ir.observation.governance",
        "ObservationFamilyPolicy",
    ),
    "ObservationFamilyPolicyRegistry": (
        "polisyos.ir.observation.governance",
        "ObservationFamilyPolicyRegistry",
    ),
    "GovernancePassMappingRegistry": (
        "polisyos.ir.observation.governance",
        "GovernancePassMappingRegistry",
    ),
    "DEFAULT_GOVERNANCE_PASS_ALIAS_REGISTRY": (
        "polisyos.ir.observation.governance",
        "DEFAULT_GOVERNANCE_PASS_ALIAS_REGISTRY",
    ),
    "DEFAULT_OBSERVATION_FAMILY_POLICY_REGISTRY": (
        "polisyos.ir.observation.governance",
        "DEFAULT_OBSERVATION_FAMILY_POLICY_REGISTRY",
    ),
    "DEFAULT_GOVERNANCE_PASS_MAPPING_REGISTRY": (
        "polisyos.ir.observation.governance",
        "DEFAULT_GOVERNANCE_PASS_MAPPING_REGISTRY",
    ),
    "MeasurementTrustTier": (
        "polisyos.ir.observation.measurement",
        "MeasurementTrustTier",
    ),
    "MeasurementTierRule": ("polisyos.ir.observation.measurement", "MeasurementTierRule"),
    "ProxyMappingRule": ("polisyos.ir.observation.measurement", "ProxyMappingRule"),
    "SchemaChangepoint": ("polisyos.ir.observation.measurement", "SchemaChangepoint"),
    "SchemaRegimeSpec": ("polisyos.ir.observation.measurement", "SchemaRegimeSpec"),
    "RegimeCalendarEntry": ("polisyos.ir.observation.measurement", "RegimeCalendarEntry"),
    "ShockCalendarEntry": ("polisyos.ir.observation.measurement", "ShockCalendarEntry"),
    "RegimeCalendar": ("polisyos.ir.observation.measurement", "RegimeCalendar"),
    "ShockCalendar": ("polisyos.ir.observation.measurement", "ShockCalendar"),
    "SchemaRegimeRegistry": ("polisyos.ir.observation.measurement", "SchemaRegimeRegistry"),
    "MeasurementRegistry": ("polisyos.ir.observation.measurement", "MeasurementRegistry"),
    "IdentificationRoute": ("polisyos.ir.observation.measurement", "IdentificationRoute"),
    "IdentificationModeRouter": (
        "polisyos.ir.observation.measurement",
        "IdentificationModeRouter",
    ),
    "ContractCompatibilityTarget": (
        "polisyos.ir.observation.bundles",
        "ContractCompatibilityTarget",
    ),
    "BundleLineageRef": ("polisyos.ir.observation.bundles", "BundleLineageRef"),
    "RequiredArraySpec": ("polisyos.ir.observation.bundles", "RequiredArraySpec"),
    "RequiredColumnSpec": ("polisyos.ir.observation.bundles", "RequiredColumnSpec"),
    "BundleAxisSemantic": ("polisyos.ir.observation.bundles", "BundleAxisSemantic"),
    "ObservationContractRoute": (
        "polisyos.ir.observation.bundles",
        "ObservationContractRoute",
    ),
    "ObservationContractArtifact": (
        "polisyos.ir.observation.bundles",
        "ObservationContractArtifact",
    ),
    "BoundsChannelSpec": ("polisyos.ir.observation.bundles", "BoundsChannelSpec"),
    "ProxyChannelSpec": ("polisyos.ir.observation.bundles", "ProxyChannelSpec"),
    "SpecificationCurveSource": (
        "polisyos.ir.observation.bundles",
        "SpecificationCurveSource",
    ),
    "StrategicResponseSpec": (
        "polisyos.ir.observation.bundles",
        "StrategicResponseSpec",
    ),
    "TransportabilityCheckSpec": (
        "polisyos.ir.observation.bundles",
        "TransportabilityCheckSpec",
    ),
    "CounterfactualCheckSpec": (
        "polisyos.ir.observation.bundles",
        "CounterfactualCheckSpec",
    ),
    "InterferenceLossTargetSpec": (
        "polisyos.ir.observation.bundles",
        "InterferenceLossTargetSpec",
    ),
    "LessonRegistrySeedEntry": (
        "polisyos.ir.observation.bundles",
        "LessonRegistrySeedEntry",
    ),
    "CalibrationTargetBundleManifest": (
        "polisyos.ir.observation.bundles",
        "CalibrationTargetBundleManifest",
    ),
    "MicrosimSurveyContractBundle": (
        "polisyos.ir.observation.bundles",
        "MicrosimSurveyContractBundle",
    ),
    "NetworkContractBundle": ("polisyos.ir.observation.bundles", "NetworkContractBundle"),
    "NetworkCausalContractBundle": (
        "polisyos.ir.observation.bundles",
        "NetworkCausalContractBundle",
    ),
    "CausalPanelBundleManifest": (
        "polisyos.ir.observation.bundles",
        "CausalPanelBundleManifest",
    ),
    "BacktestPlanBundle": ("polisyos.ir.observation.bundles", "BacktestPlanBundle"),
    "ObservationToContractManifest": (
        "polisyos.ir.observation.bundles",
        "ObservationToContractManifest",
    ),
    "BoundsEstimationBundle": ("polisyos.ir.observation.bundles", "BoundsEstimationBundle"),
    "ProxyIdentificationBundle": (
        "polisyos.ir.observation.bundles",
        "ProxyIdentificationBundle",
    ),
    "DTRTreatmentSequenceBundleManifest": (
        "polisyos.ir.observation.bundles",
        "DTRTreatmentSequenceBundleManifest",
    ),
    "PanelEconometricBundleManifest": (
        "polisyos.ir.observation.bundles",
        "PanelEconometricBundleManifest",
    ),
    "SurvivalDataBundleManifest": (
        "polisyos.ir.observation.bundles",
        "SurvivalDataBundleManifest",
    ),
    "AgentFactorEmbeddingsBundleManifest": (
        "polisyos.ir.observation.bundles",
        "AgentFactorEmbeddingsBundleManifest",
    ),
    "CellPrototypeEmbeddingsBundleManifest": (
        "polisyos.ir.observation.bundles",
        "CellPrototypeEmbeddingsBundleManifest",
    ),
    "BilevelProblemBundle": ("polisyos.ir.observation.bundles", "BilevelProblemBundle"),
    "HeckmanCorrectionBundle": (
        "polisyos.ir.observation.bundles",
        "HeckmanCorrectionBundle",
    ),
    "SurvivalHazardBundle": ("polisyos.ir.observation.bundles", "SurvivalHazardBundle"),
    "SobolDiagnosticsBundle": ("polisyos.ir.observation.bundles", "SobolDiagnosticsBundle"),
    "SpecificationCurveDiagnosticsBundle": (
        "polisyos.ir.observation.bundles",
        "SpecificationCurveDiagnosticsBundle",
    ),
    "SpecificationCurveBundle": (
        "polisyos.ir.observation.bundles",
        "SpecificationCurveBundle",
    ),
    "LeontiefIOBundle": ("polisyos.ir.observation.bundles", "LeontiefIOBundle"),
    "StrategicResponseSpecsBundle": (
        "polisyos.ir.observation.bundles",
        "StrategicResponseSpecsBundle",
    ),
    "TransportabilityCheckBundle": (
        "polisyos.ir.observation.bundles",
        "TransportabilityCheckBundle",
    ),
    "CounterfactualCheckBundle": (
        "polisyos.ir.observation.bundles",
        "CounterfactualCheckBundle",
    ),
    "InterferenceLossSpecBundle": (
        "polisyos.ir.observation.bundles",
        "InterferenceLossSpecBundle",
    ),
    "GovernancePassMappingBundle": (
        "polisyos.ir.observation.bundles",
        "GovernancePassMappingBundle",
    ),
    "LessonRegistrySeedBundle": (
        "polisyos.ir.observation.bundles",
        "LessonRegistrySeedBundle",
    ),
    "SURVEY_MICRODATA_TARGET": ("polisyos.ir.observation.bundles", "SURVEY_MICRODATA_TARGET"),
    "NETWORK_DATA_TARGET": ("polisyos.ir.observation.bundles", "NETWORK_DATA_TARGET"),
    "NETWORK_ANALYSIS_TARGET": (
        "polisyos.ir.observation.bundles",
        "NETWORK_ANALYSIS_TARGET",
    ),
    "MULTIPLEX_NETWORK_TARGET": (
        "polisyos.ir.observation.bundles",
        "MULTIPLEX_NETWORK_TARGET",
    ),
    "PANEL_OBSERVATIONAL_TARGET": (
        "polisyos.ir.observation.bundles",
        "PANEL_OBSERVATIONAL_TARGET",
    ),
    "PROXY_MEASUREMENT_TARGET": (
        "polisyos.ir.observation.bundles",
        "PROXY_MEASUREMENT_TARGET",
    ),
    "DYNAMIC_TREATMENT_TARGET": (
        "polisyos.ir.observation.bundles",
        "DYNAMIC_TREATMENT_TARGET",
    ),
    "PANEL_ECONOMETRIC_TARGET": (
        "polisyos.ir.observation.bundles",
        "PANEL_ECONOMETRIC_TARGET",
    ),
    "SURVIVAL_DATA_TARGET": ("polisyos.ir.observation.bundles", "SURVIVAL_DATA_TARGET"),
    "BACKTEST_PLAN_TARGET": ("polisyos.ir.observation.bundles", "BACKTEST_PLAN_TARGET"),
    "LESSON_CARD_TARGET": ("polisyos.ir.observation.bundles", "LESSON_CARD_TARGET"),
    "SECTION_15_7_BUNDLE_MODELS": (
        "polisyos.ir.observation.bundles",
        "SECTION_15_7_BUNDLE_MODELS",
    ),
    "ObservationContractCompileError": (
        "polisyos.ir.observation.contract_compilers",
        "ObservationContractCompileError",
    ),
    "BoundsEstimationInput": (
        "polisyos.ir.observation.contract_compilers",
        "BoundsEstimationInput",
    ),
    "SpecificationCurveInput": (
        "polisyos.ir.observation.contract_compilers",
        "SpecificationCurveInput",
    ),
    "LeontiefIOInput": ("polisyos.ir.observation.contract_compilers", "LeontiefIOInput"),
    "GraphEdge": ("polisyos.ir.observation.contract_compilers", "GraphEdge"),
    "GraphBipartiteEdge": (
        "polisyos.ir.observation.contract_compilers",
        "GraphBipartiteEdge",
    ),
    "GraphArtifacts": ("polisyos.ir.observation.contract_compilers", "GraphArtifacts"),
    "FirmEventRecord": ("polisyos.ir.observation.contract_compilers", "FirmEventRecord"),
    "FirmEvents": ("polisyos.ir.observation.contract_compilers", "FirmEvents"),
    "FirmPanelRow": ("polisyos.ir.observation.contract_compilers", "FirmPanelRow"),
    "FirmPanels": ("polisyos.ir.observation.contract_compilers", "FirmPanels"),
    "RegionSectorFlowRow": (
        "polisyos.ir.observation.contract_compilers",
        "RegionSectorFlowRow",
    ),
    "RegionSectorPanels": (
        "polisyos.ir.observation.contract_compilers",
        "RegionSectorPanels",
    ),
    "ProxyMap": ("polisyos.ir.observation.contract_compilers", "ProxyMap"),
    "SurveyMicroDataCompileSpec": (
        "polisyos.ir.observation.contract_compilers",
        "SurveyMicroDataCompileSpec",
    ),
    "NetworkContractCompileSpec": (
        "polisyos.ir.observation.contract_compilers",
        "NetworkContractCompileSpec",
    ),
    "NetworkCausalCompileSpec": (
        "polisyos.ir.observation.contract_compilers",
        "NetworkCausalCompileSpec",
    ),
    "PanelObservationalCompileSpec": (
        "polisyos.ir.observation.contract_compilers",
        "PanelObservationalCompileSpec",
    ),
    "DynamicTreatmentCompileSpec": (
        "polisyos.ir.observation.contract_compilers",
        "DynamicTreatmentCompileSpec",
    ),
    "SurvivalCompileSpec": (
        "polisyos.ir.observation.contract_compilers",
        "SurvivalCompileSpec",
    ),
    "PanelEconometricCompileSpec": (
        "polisyos.ir.observation.contract_compilers",
        "PanelEconometricCompileSpec",
    ),
    "BoundsEstimationCompileSpec": (
        "polisyos.ir.observation.contract_compilers",
        "BoundsEstimationCompileSpec",
    ),
    "ProxyMeasurementCompileSpec": (
        "polisyos.ir.observation.contract_compilers",
        "ProxyMeasurementCompileSpec",
    ),
    "HistoricalValidationCompileSpec": (
        "polisyos.ir.observation.contract_compilers",
        "HistoricalValidationCompileSpec",
    ),
    "SpecificationCurveSourceSpec": (
        "polisyos.ir.observation.contract_compilers",
        "SpecificationCurveSourceSpec",
    ),
    "SpecificationCurveCompileSpec": (
        "polisyos.ir.observation.contract_compilers",
        "SpecificationCurveCompileSpec",
    ),
    "LeontiefIOCompileSpec": (
        "polisyos.ir.observation.contract_compilers",
        "LeontiefIOCompileSpec",
    ),
    "CompiledObservationArtifact": (
        "polisyos.ir.observation.contract_compilers",
        "CompiledObservationArtifact",
    ),
    "HistoricalValidationCompilation": (
        "polisyos.ir.observation.contract_compilers",
        "HistoricalValidationCompilation",
    ),
    "ObservationContractSuiteResult": (
        "polisyos.ir.observation.contract_compilers",
        "ObservationContractSuiteResult",
    ),
    "SparseDenseBridge": ("polisyos.ir.observation.contract_compilers", "SparseDenseBridge"),
    "ObservationCompilerContext": (
        "polisyos.ir.observation.contract_compilers",
        "ObservationCompilerContext",
    ),
    "SurveyMicroDataCompiler": (
        "polisyos.ir.observation.contract_compilers",
        "SurveyMicroDataCompiler",
    ),
    "NetworkContractCompiler": (
        "polisyos.ir.observation.contract_compilers",
        "NetworkContractCompiler",
    ),
    "NetworkCausalDataCompiler": (
        "polisyos.ir.observation.contract_compilers",
        "NetworkCausalDataCompiler",
    ),
    "PanelObservationalCompiler": (
        "polisyos.ir.observation.contract_compilers",
        "PanelObservationalCompiler",
    ),
    "DynamicTreatmentCompiler": (
        "polisyos.ir.observation.contract_compilers",
        "DynamicTreatmentCompiler",
    ),
    "SurvivalDataCompiler": (
        "polisyos.ir.observation.contract_compilers",
        "SurvivalDataCompiler",
    ),
    "PanelEconometricCompiler": (
        "polisyos.ir.observation.contract_compilers",
        "PanelEconometricCompiler",
    ),
    "BoundsInputCompiler": (
        "polisyos.ir.observation.contract_compilers",
        "BoundsInputCompiler",
    ),
    "ProxyMeasurementCompiler": (
        "polisyos.ir.observation.contract_compilers",
        "ProxyMeasurementCompiler",
    ),
    "HistoricalValidationPlanCompiler": (
        "polisyos.ir.observation.contract_compilers",
        "HistoricalValidationPlanCompiler",
    ),
    "SpecificationCurveCompiler": (
        "polisyos.ir.observation.contract_compilers",
        "SpecificationCurveCompiler",
    ),
    "LeontiefIOCompiler": (
        "polisyos.ir.observation.contract_compilers",
        "LeontiefIOCompiler",
    ),
    "write_json_bundle": ("polisyos.ir.observation.contract_compilers", "write_json_bundle"),
    "load_json_bundle": ("polisyos.ir.observation.contract_compilers", "load_json_bundle"),
    "write_npz_payload": ("polisyos.ir.observation.contract_compilers", "write_npz_payload"),
    "load_npz_payload": ("polisyos.ir.observation.contract_compilers", "load_npz_payload"),
    "write_parquet_rows": ("polisyos.ir.observation.contract_compilers", "write_parquet_rows"),
    "load_parquet_rows": ("polisyos.ir.observation.contract_compilers", "load_parquet_rows"),
    "ObservationContractCompilerSuite": (
        "polisyos.ir.observation.contract_compilers",
        "ObservationContractCompilerSuite",
    ),
    "CalibrationSplitLabel": ("polisyos.ir.observation.compiler", "CalibrationSplitLabel"),
    "CalibrationSplitWindow": ("polisyos.ir.observation.compiler", "CalibrationSplitWindow"),
    "CalibrationSplitPlan": ("polisyos.ir.observation.compiler", "CalibrationSplitPlan"),
    "NegativeControlSpec": ("polisyos.ir.observation.compiler", "NegativeControlSpec"),
    "CalibrationSplitter": ("polisyos.ir.observation.compiler", "CalibrationSplitter"),
    "CalibrationTargetBundleCompiler": (
        "polisyos.ir.observation.compiler",
        "CalibrationTargetBundleCompiler",
    ),
    "NegativeControlGenerator": (
        "polisyos.ir.observation.compiler",
        "NegativeControlGenerator",
    ),
    "BoundsEstimationTask": (
        "polisyos.ir.observation.causal_execution",
        "BoundsEstimationTask",
    ),
    "TemporalDTRTask": ("polisyos.ir.observation.causal_execution", "TemporalDTRTask"),
    "BoundsEstimationEntry": (
        "polisyos.ir.observation.causal_execution",
        "BoundsEstimationEntry",
    ),
    "TemporalDTRExecutionEntry": (
        "polisyos.ir.observation.causal_execution",
        "TemporalDTRExecutionEntry",
    ),
    "CausalExecutionBundle": (
        "polisyos.ir.observation.causal_execution",
        "CausalExecutionBundle",
    ),
    "persist_causal_execution_bundle": (
        "polisyos.ir.observation.causal_execution",
        "persist_causal_execution_bundle",
    ),
    "load_causal_execution_bundle": (
        "polisyos.ir.observation.causal_execution",
        "load_causal_execution_bundle",
    ),
    "ProxyIdentificationEntry": (
        "polisyos.ir.observation.causal_readiness",
        "ProxyIdentificationEntry",
    ),
    "TransportabilityCheckEntry": (
        "polisyos.ir.observation.causal_readiness",
        "TransportabilityCheckEntry",
    ),
    "StrategicResponseEntry": (
        "polisyos.ir.observation.causal_readiness",
        "StrategicResponseEntry",
    ),
    "CounterfactualCheckEntry": (
        "polisyos.ir.observation.causal_readiness",
        "CounterfactualCheckEntry",
    ),
    "InterferenceReadinessEntry": (
        "polisyos.ir.observation.causal_readiness",
        "InterferenceReadinessEntry",
    ),
    "CausalReadinessBundle": (
        "polisyos.ir.observation.causal_readiness",
        "CausalReadinessBundle",
    ),
    "persist_causal_readiness_bundle": (
        "polisyos.ir.observation.causal_readiness",
        "persist_causal_readiness_bundle",
    ),
    "load_causal_readiness_bundle": (
        "polisyos.ir.observation.causal_readiness",
        "load_causal_readiness_bundle",
    ),
}


def __getattr__(name: str) -> Any:
    """Resolve a lazily exported observation contract by public name."""
    if name in _LAZY_IMPORTS:
        module_name, attr = _LAZY_IMPORTS[name]
        module = importlib.import_module(module_name)
        value = getattr(module, attr)
        globals()[name] = value
        return value
    raise AttributeError(f"module 'polisyos.ir.observation' has no attribute '{name}'")


def __dir__() -> list[str]:
    """Return eagerly defined names plus lazily exported observation symbols."""
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
