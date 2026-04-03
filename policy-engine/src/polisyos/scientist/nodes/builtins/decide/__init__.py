"""Lazy decision-stage facade for delivery nodes that emit reports, bundles, and translations."""
from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "BuildDecisionPacketNode",
    "BuildPolicyOutputBundleNode",
    "BuildVerifiedPolicyReportNode",
    "RunPolicyBlueprintRuntimeNode",
    "RunPolicyTranslationNode",
    "RunTranslatorComplianceNode",
]

_MODULE_BY_EXPORT = {
    "BuildDecisionPacketNode": "build_decision_packet",
    "BuildPolicyOutputBundleNode": "build_policy_output_bundle",
    "BuildVerifiedPolicyReportNode": "build_verified_policy_report",
    "RunPolicyBlueprintRuntimeNode": "run_policy_blueprint_runtime",
    "RunPolicyTranslationNode": "run_policy_translation",
    "RunTranslatorComplianceNode": "run_translator_compliance",
}


def __getattr__(name: str) -> Any:
    module_name = _MODULE_BY_EXPORT.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = importlib.import_module(f"{__name__}.{module_name}")
    return getattr(module, name)
