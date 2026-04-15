"""LLM utilities for Scientist agents."""

from .factory import GatewayLLMConfig, create_traced_gateway_client
from .gateway_client import GatewayLLMClient, GatewayLLMResponse, GatewayUsage
from .provider_verification import (
    ProviderCapabilityVerification,
    ProviderSmokeCheck,
    ProviderSmokeReport,
    is_provider_capability_verified,
    load_provider_verification,
    provider_verification_path,
    resolve_gonka_api_key,
    run_gonka_provider_smoke,
    save_provider_verification,
)
from .traced_client import LLMClientProtocol, TracedLLMClient

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
