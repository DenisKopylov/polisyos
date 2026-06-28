"""Factory helpers for creating traced gateway-backed LLM clients."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from polisyos.core.llm.sanitization import PromptSanitizer
from polisyos.core.llm.traced_client import TracedLLMClient

from .fallback_router import EndpointConfig, FallbackRouter
from .gateway_client import GatewayLLMClient
from .prompt_cache import CachingLLMClient, InMemoryPromptCache
from .simulated_gateway import DEFAULT_SIMULATED_MODEL_IDS, SimulatedGatewayLLMClient

if TYPE_CHECKING:
    from collections.abc import Callable


def _as_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _is_plausible_gateway_api_key(value: str) -> bool:
    key = value.strip()
    return key.startswith("sk-") and len(key) >= 16 and not any(char.isspace() for char in key)


def _load_gateway_dotenv() -> None:
    """Load gateway env values from a local .env file without overriding env."""

    for path in _candidate_dotenv_paths():
        if not path.is_file():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, raw_value = line.split("=", 1)
            key = key.strip()
            if not key or key in os.environ:
                continue
            value = raw_value.strip().strip('"').strip("'")
            os.environ[key] = value
        return


def _candidate_dotenv_paths() -> tuple[Path, ...]:
    cwd = Path.cwd()
    module_root = Path(__file__).resolve().parents[5]
    return (
        cwd / ".env",
        cwd.parent / ".env",
        module_root / ".env",
        module_root.parent / ".env",
    )


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
    # Provider policy
    default_preset: str | None = None
    enable_privacy_sanitization_plugin: bool = False
    # First-party sanitization
    enable_prompt_sanitizer: bool = True

    @classmethod
    def from_env(cls) -> GatewayLLMConfig | None:
        _load_gateway_dotenv()
        base_url = (
            os.getenv("POLISYOS_LLM_GATEWAY_BASE_URL", "").strip()
            or "https://proxy.gonka.gg/v1"
        )
        api_key = os.getenv("POLISYOS_LLM_GATEWAY_API_KEY", "").strip()
        if not api_key:
            return None
        if not _is_plausible_gateway_api_key(api_key):
            return None
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
        fallback_urls = (
            tuple(u.strip() for u in raw_fallback.split(",") if u.strip()) if raw_fallback else ()
        )
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
            default_preset=(os.getenv("POLISYOS_LLM_GATEWAY_PRESET") or "").strip() or None,
            enable_privacy_sanitization_plugin=_as_bool(
                os.getenv("POLISYOS_LLM_GATEWAY_PRIVACY_SANITIZATION"),
                default=False,
            ),
            enable_prompt_sanitizer=_as_bool(
                os.getenv("POLISYOS_LLM_PROMPT_SANITIZER"),
                default=True,
            ),
        )


def create_traced_gateway_client(
    *,
    model_name: str,
    provider_hint: str | None = None,
    run_id: str | None = None,
    model_variant_id: str | None = None,
    call_observer: Callable[[dict[str, Any]], None] | None = None,
    config: GatewayLLMConfig | None = None,
    tracer: Any | None = None,
    metrics: Any | None = None,
) -> TracedLLMClient | None:
    """Create traced LLM client from env-backed gateway config."""
    if _as_bool(os.getenv("POLISYOS_LLM_SIMULATION_MODE"), default=False):
        simulated_model_ids = tuple(dict.fromkeys((model_name, *DEFAULT_SIMULATED_MODEL_IDS)))
        raw_client = SimulatedGatewayLLMClient(
            model=model_name,
            provider_hint=provider_hint or "simulated_gateway",
            supported_model_ids=simulated_model_ids,
        )
        return TracedLLMClient(
            raw_client,
            model_name=model_name,
            capture_prompt=False,
            run_id=run_id,
            model_variant_id=model_variant_id,
            call_observer=call_observer,
            provider_name="simulated_gateway",
            prompt_sanitizer=None,
            tracer=tracer,
            metrics=metrics,
        )
    cfg = config or GatewayLLMConfig.from_env()
    if cfg is None:
        return None
    resolved_provider = provider_hint or cfg.default_provider
    default_plugins: tuple[dict[str, Any], ...] = ()
    if cfg.enable_privacy_sanitization_plugin:
        default_plugins = ({"id": "privacy-sanitization"},)
    if cfg.fallback_urls:
        endpoints = [
            EndpointConfig(
                url=cfg.base_url,
                api_key=cfg.api_key,
                model=model_name,
                provider_hint=resolved_provider,
                priority=0,
                timeout_s=cfg.timeout_s,
                max_retries=cfg.max_retries,
                preset=cfg.default_preset,
                default_plugins=default_plugins,
            ),
            *[
                EndpointConfig(
                    url=url,
                    api_key=cfg.api_key,
                    model=model_name,
                    provider_hint=resolved_provider,
                    priority=index + 1,
                    timeout_s=cfg.timeout_s,
                    max_retries=cfg.max_retries,
                    preset=cfg.default_preset,
                    default_plugins=default_plugins,
                )
                for index, url in enumerate(cfg.fallback_urls)
            ],
        ]
        raw_client = FallbackRouter(endpoints)
    else:
        raw_client = GatewayLLMClient(
            base_url=cfg.base_url,
            api_key=cfg.api_key,
            model=model_name,
            timeout_s=cfg.timeout_s,
            max_retries=cfg.max_retries,
            provider_hint=resolved_provider,
            preset=cfg.default_preset,
            default_plugins=[dict(plugin) for plugin in default_plugins],
        )
    if cfg.cache_maxsize > 0 and cfg.cache_ttl_s > 0:
        raw_client = CachingLLMClient(
            raw_client,
            cache=InMemoryPromptCache(
                maxsize=cfg.cache_maxsize,
                default_ttl_s=cfg.cache_ttl_s,
            ),
            model=model_name,
            ttl_s=cfg.cache_ttl_s,
        )
    prompt_sanitizer = PromptSanitizer() if cfg.enable_prompt_sanitizer else None
    return TracedLLMClient(
        raw_client,
        model_name=model_name,
        capture_prompt=cfg.capture_prompt,
        max_prompt_length=cfg.max_prompt_length,
        run_id=run_id,
        model_variant_id=model_variant_id,
        call_observer=call_observer,
        provider_name=resolved_provider or "gateway",
        prompt_sanitizer=prompt_sanitizer,
        tracer=tracer,
        metrics=metrics,
    )


__all__ = [
    "GatewayLLMConfig",
    "create_traced_gateway_client",
]
