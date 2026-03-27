"""Factory helpers for creating traced gateway-backed LLM clients."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable

from polisyos.core.llm.traced_client import TracedLLMClient

from .gateway_client import GatewayLLMClient


def _as_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class GatewayLLMConfig:
    """Runtime configuration for gateway-backed LLM calls."""

    base_url: str
    api_key: str
    timeout_s: float = 60.0
    max_retries: int = 1
    default_provider: str | None = None
    capture_prompt: bool = False
    max_prompt_length: int = 200
    # Fallback routing
    fallback_urls: tuple[str, ...] = ()
    # Prompt caching
    cache_ttl_s: float = 300.0
    cache_maxsize: int = 128

    @classmethod
    def from_env(cls) -> GatewayLLMConfig | None:
        base_url = os.getenv("POLISYOS_LLM_GATEWAY_BASE_URL", "").strip()
        if not base_url:
            return None
        api_key = os.getenv("POLISYOS_LLM_GATEWAY_API_KEY", "").strip()
        try:
            timeout_s = float(os.getenv("POLISYOS_LLM_GATEWAY_TIMEOUT_S", "60").strip())
        except ValueError:
            timeout_s = 60.0
        try:
            max_retries = int(os.getenv("POLISYOS_LLM_GATEWAY_MAX_RETRIES", "1").strip())
        except ValueError:
            max_retries = 1
        try:
            max_prompt_length = int(
                os.getenv("POLISYOS_LLM_MAX_PROMPT_CAPTURE_CHARS", "200").strip()
            )
        except ValueError:
            max_prompt_length = 200
        try:
            cache_ttl_s = float(os.getenv("POLISYOS_LLM_CACHE_TTL_S", "300").strip())
        except ValueError:
            cache_ttl_s = 300.0
        try:
            cache_maxsize = int(os.getenv("POLISYOS_LLM_CACHE_MAXSIZE", "128").strip())
        except ValueError:
            cache_maxsize = 128
        raw_fallback = os.getenv("POLISYOS_LLM_FALLBACK_URLS", "").strip()
        fallback_urls = tuple(
            u.strip() for u in raw_fallback.split(",") if u.strip()
        ) if raw_fallback else ()
        return cls(
            base_url=base_url,
            api_key=api_key,
            timeout_s=max(timeout_s, 1.0),
            max_retries=max(max_retries, 0),
            default_provider=(os.getenv("POLISYOS_LLM_GATEWAY_PROVIDER") or "").strip() or None,
            capture_prompt=_as_bool(
                os.getenv("POLISYOS_LLM_CAPTURE_PROMPT"),
                default=False,
            ),
            max_prompt_length=max(max_prompt_length, 50),
            fallback_urls=fallback_urls,
            cache_ttl_s=max(cache_ttl_s, 0.0),
            cache_maxsize=max(cache_maxsize, 0),
        )


def create_traced_gateway_client(
    *,
    model_name: str,
    provider_hint: str | None = None,
    run_id: str | None = None,
    model_variant_id: str | None = None,
    call_observer: Callable[[dict[str, Any]], None] | None = None,
    config: GatewayLLMConfig | None = None,
) -> TracedLLMClient | None:
    """Create traced LLM client from env-backed gateway config."""
    cfg = config or GatewayLLMConfig.from_env()
    if cfg is None:
        return None
    raw_client = GatewayLLMClient(
        base_url=cfg.base_url,
        api_key=cfg.api_key,
        model=model_name,
        timeout_s=cfg.timeout_s,
        max_retries=cfg.max_retries,
        provider_hint=provider_hint or cfg.default_provider,
    )
    return TracedLLMClient(
        raw_client,
        model_name=model_name,
        capture_prompt=cfg.capture_prompt,
        max_prompt_length=cfg.max_prompt_length,
        run_id=run_id,
        model_variant_id=model_variant_id,
        call_observer=call_observer,
        provider_name=provider_hint or cfg.default_provider or "gateway",
    )


__all__ = [
    "GatewayLLMConfig",
    "create_traced_gateway_client",
]
