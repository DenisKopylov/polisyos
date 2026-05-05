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
    "TracedLLMClient",
    "create_traced_gateway_client",
    "is_provider_capability_verified",
    "load_provider_verification",
    "provider_verification_path",
    "resolve_gonka_api_key",
    "run_gonka_provider_smoke",
    "save_provider_verification",
]

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "GatewayLLMConfig": ("polisyos.scientist.llm.factory", "GatewayLLMConfig"),
    "create_traced_gateway_client": (
        "polisyos.scientist.llm.factory",
        "create_traced_gateway_client",
    ),
    "GatewayLLMClient": ("polisyos.scientist.llm.gateway_client", "GatewayLLMClient"),
    "GatewayLLMResponse": ("polisyos.scientist.llm.gateway_client", "GatewayLLMResponse"),
    "GatewayUsage": ("polisyos.scientist.llm.gateway_client", "GatewayUsage"),
    "ProviderCapabilityVerification": (
        "polisyos.scientist.llm.provider_verification",
        "ProviderCapabilityVerification",
    ),
    "ProviderSmokeCheck": (
        "polisyos.scientist.llm.provider_verification",
        "ProviderSmokeCheck",
    ),
    "ProviderSmokeReport": (
        "polisyos.scientist.llm.provider_verification",
        "ProviderSmokeReport",
    ),
    "is_provider_capability_verified": (
        "polisyos.scientist.llm.provider_verification",
        "is_provider_capability_verified",
    ),
    "load_provider_verification": (
        "polisyos.scientist.llm.provider_verification",
        "load_provider_verification",
    ),
    "provider_verification_path": (
        "polisyos.scientist.llm.provider_verification",
        "provider_verification_path",
    ),
    "resolve_gonka_api_key": (
        "polisyos.scientist.llm.provider_verification",
        "resolve_gonka_api_key",
    ),
    "run_gonka_provider_smoke": (
        "polisyos.scientist.llm.provider_verification",
        "run_gonka_provider_smoke",
    ),
    "save_provider_verification": (
        "polisyos.scientist.llm.provider_verification",
        "save_provider_verification",
    ),
    "LLMClientProtocol": ("polisyos.scientist.llm.traced_client", "LLMClientProtocol"),
    "TracedLLMClient": ("polisyos.scientist.llm.traced_client", "TracedLLMClient"),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module 'polisyos.scientist.llm' has no attribute {name!r}")
    module_name, attr_name = _LAZY_IMPORTS[name]
    value = getattr(importlib.import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
