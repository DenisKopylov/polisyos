"""LLM utilities for Scientist agents."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "GatewayLLMClient",
    "GatewayLLMConfig",
    "GatewayLLMResponse",
    "GatewayUsage",
    "LLMClientProtocol",
    "ProviderCapabilityVerification",
    "ProviderSmokeCheck",
    "ProviderSmokeReport",
    "SimulatedGatewayLLMClient",
    "TracedLLMClient",
    "build_model_variant_adjudication",
    "create_traced_gateway_client",
    "is_provider_capability_verified",
    "load_provider_verification",
    "provider_verification_path",
    "resolve_gonka_api_key",
    "run_gonka_provider_smoke",
    "save_provider_verification",
]

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "GatewayLLMConfig": ("polisyos.scientist.orchestration.llm.factory", "GatewayLLMConfig"),
    "create_traced_gateway_client": (
        "polisyos.scientist.orchestration.llm.factory",
        "create_traced_gateway_client",
    ),
    "build_model_variant_adjudication": (
        "polisyos.scientist.orchestration.llm.adjudication",
        "build_model_variant_adjudication",
    ),
    "GatewayLLMClient": ("polisyos.scientist.orchestration.llm.gateway_client", "GatewayLLMClient"),
    "GatewayLLMResponse": (
        "polisyos.scientist.orchestration.llm.gateway_client",
        "GatewayLLMResponse",
    ),
    "GatewayUsage": ("polisyos.scientist.orchestration.llm.gateway_client", "GatewayUsage"),
    "SimulatedGatewayLLMClient": (
        "polisyos.scientist.orchestration.llm.simulated_gateway",
        "SimulatedGatewayLLMClient",
    ),
    "ProviderCapabilityVerification": (
        "polisyos.scientist.orchestration.llm.provider_verification",
        "ProviderCapabilityVerification",
    ),
    "ProviderSmokeCheck": (
        "polisyos.scientist.orchestration.llm.provider_verification",
        "ProviderSmokeCheck",
    ),
    "ProviderSmokeReport": (
        "polisyos.scientist.orchestration.llm.provider_verification",
        "ProviderSmokeReport",
    ),
    "is_provider_capability_verified": (
        "polisyos.scientist.orchestration.llm.provider_verification",
        "is_provider_capability_verified",
    ),
    "load_provider_verification": (
        "polisyos.scientist.orchestration.llm.provider_verification",
        "load_provider_verification",
    ),
    "provider_verification_path": (
        "polisyos.scientist.orchestration.llm.provider_verification",
        "provider_verification_path",
    ),
    "resolve_gonka_api_key": (
        "polisyos.scientist.orchestration.llm.provider_verification",
        "resolve_gonka_api_key",
    ),
    "run_gonka_provider_smoke": (
        "polisyos.scientist.orchestration.llm.provider_verification",
        "run_gonka_provider_smoke",
    ),
    "save_provider_verification": (
        "polisyos.scientist.orchestration.llm.provider_verification",
        "save_provider_verification",
    ),
    "LLMClientProtocol": (
        "polisyos.scientist.orchestration.llm.traced_client",
        "LLMClientProtocol",
    ),
    "TracedLLMClient": ("polisyos.scientist.orchestration.llm.traced_client", "TracedLLMClient"),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(
            f"module 'polisyos.scientist.orchestration.llm' has no attribute {name!r}"
        )
    module_name, attr_name = _LAZY_IMPORTS[name]
    value = getattr(importlib.import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
