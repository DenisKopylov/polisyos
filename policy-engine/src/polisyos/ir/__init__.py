from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "AccessTier",
    "ConnectorCapability",
    "ConnectorMetadataSpec",
    "DataFilter",
    "DataViewRequest",
    "DataViewType",
    "QualityTier",
    "TrustLevel",
    "NormPack",
    "NormRule",
    "NormRef",
    "RuleType",
    "load_policy",
    "CalibrationConfig",
    "CalibrationTarget",
    "ProblemFrame",
    "ProblemDomain",
    "KPISpec",
    "SuccessCriterion",
    "ProblemConstraintSpec",
    "ConstraintType",
    "StakeholderSpec",
    "PolicySpec",
    "PolicyInterventionSpec",
    "MechanismBinding",
    "ParameterSpec",
    "ModelSpec",
    "FidelityLevel",
    "AssumptionSpec",
    "AssumptionType",
    "AgentConfig",
    "AgentTypeConfig",
    "EnvironmentConfig",
    "EnvironmentParam",
    "GateContext",
    "GateDecision",
    "GateEvent",
    "GateEventType",
    "GatePriority",
    "GateRequest",
    "GateVerdict",
    "DistributionFamily",
    "IntervalSemantics",
    "PropagationMethod",
    "UncertaintyEnvelope",
    "UncertaintySource",
]

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "CalibrationConfig": ("polisyos.ir.calibration", "CalibrationConfig"),
    "CalibrationTarget": ("polisyos.ir.calibration", "CalibrationTarget"),
    "ConnectorCapability": ("polisyos.ir.connectors", "ConnectorCapability"),
    "ConnectorMetadataSpec": ("polisyos.ir.connectors", "ConnectorMetadataSpec"),
    "QualityTier": ("polisyos.ir.connectors", "QualityTier"),
    "TrustLevel": ("polisyos.ir.connectors", "TrustLevel"),
    "AccessTier": ("polisyos.ir.data_views", "AccessTier"),
    "DataFilter": ("polisyos.ir.data_views", "DataFilter"),
    "DataViewRequest": ("polisyos.ir.data_views", "DataViewRequest"),
    "DataViewType": ("polisyos.ir.data_views", "DataViewType"),
    "load_policy": ("polisyos.ir.loaders", "load_policy"),
    "NormPack": ("polisyos.ir.norm_pack", "NormPack"),
    "NormRule": ("polisyos.ir.norm_pack", "NormRule"),
    "NormRef": ("polisyos.ir.norm_pack", "NormRef"),
    "RuleType": ("polisyos.ir.norm_pack", "RuleType"),
    "AgentConfig": ("polisyos.ir.model_spec", "AgentConfig"),
    "AgentTypeConfig": ("polisyos.ir.model_spec", "AgentTypeConfig"),
    "AssumptionSpec": ("polisyos.ir.model_spec", "AssumptionSpec"),
    "AssumptionType": ("polisyos.ir.model_spec", "AssumptionType"),
    "EnvironmentConfig": ("polisyos.ir.model_spec", "EnvironmentConfig"),
    "EnvironmentParam": ("polisyos.ir.model_spec", "EnvironmentParam"),
    "FidelityLevel": ("polisyos.ir.model_spec", "FidelityLevel"),
    "ModelSpec": ("polisyos.ir.model_spec", "ModelSpec"),
    "GateContext": ("polisyos.ir.gate", "GateContext"),
    "GateDecision": ("polisyos.ir.gate", "GateDecision"),
    "GateEvent": ("polisyos.ir.gate", "GateEvent"),
    "GateEventType": ("polisyos.ir.gate", "GateEventType"),
    "GatePriority": ("polisyos.ir.gate", "GatePriority"),
    "GateRequest": ("polisyos.ir.gate", "GateRequest"),
    "GateVerdict": ("polisyos.ir.gate", "GateVerdict"),
    "DistributionFamily": ("polisyos.ir.uncertainty", "DistributionFamily"),
    "IntervalSemantics": ("polisyos.ir.uncertainty", "IntervalSemantics"),
    "PropagationMethod": ("polisyos.ir.uncertainty", "PropagationMethod"),
    "MechanismBinding": ("polisyos.ir.policy_spec", "MechanismBinding"),
    "ParameterSpec": ("polisyos.ir.policy_spec", "ParameterSpec"),
    "PolicyInterventionSpec": ("polisyos.ir.policy_spec", "InterventionSpec"),
    "PolicySpec": ("polisyos.ir.policy_spec", "PolicySpec"),
    "ConstraintType": ("polisyos.ir.problem_frame", "ConstraintType"),
    "KPISpec": ("polisyos.ir.problem_frame", "KPISpec"),
    "ProblemConstraintSpec": ("polisyos.ir.problem_frame", "ConstraintSpec"),
    "ProblemDomain": ("polisyos.ir.problem_frame", "ProblemDomain"),
    "ProblemFrame": ("polisyos.ir.problem_frame", "ProblemFrame"),
    "StakeholderSpec": ("polisyos.ir.problem_frame", "StakeholderSpec"),
    "SuccessCriterion": ("polisyos.ir.problem_frame", "SuccessCriterion"),
    "UncertaintyEnvelope": ("polisyos.ir.uncertainty", "UncertaintyEnvelope"),
    "UncertaintySource": ("polisyos.ir.uncertainty", "UncertaintySource"),
}


def __getattr__(name: str) -> Any:
    if name in _LAZY_IMPORTS:
        module_name, attr = _LAZY_IMPORTS[name]
        module = importlib.import_module(module_name)
        value = getattr(module, attr)
        globals()[name] = value
        return value
    raise AttributeError(f"module 'polisyos.ir' has no attribute '{name}'")


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
