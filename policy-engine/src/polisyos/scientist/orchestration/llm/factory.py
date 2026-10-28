"""Factory helpers for creating traced gateway-backed LLM clients."""

from __future__ import annotations

import os
import threading
from collections.abc import Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any

from polisyos.core.llm import LLMProducerIntent, LLMSettlementOwnershipError
from polisyos.core.llm.cache_settlement import session_for_cache_client
from polisyos.core.llm.sanitization import PromptSanitizer
from polisyos.core.llm.traced_client import TracedLLMClient

from .fallback_router import EndpointConfig, FallbackRouter
from .gateway_client import GatewayLLMClient
from .prompt_cache import (
    CacheReusePrincipal,
    CachingLLMClient,
    InMemoryPromptCache,
    PromptCacheProtocol,
)
from .simulated_gateway import DEFAULT_SIMULATED_MODEL_IDS, SimulatedGatewayLLMClient

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware

    from .prompt_cache import CacheReuseAuthorizer, CacheReuseGuard


@dataclass(slots=True)
class _AdmissionTicket:
    started: bool = False
    finished: bool = False
    waiter_done: bool = False
    cancelled: bool = False


@dataclass(slots=True)
class _AdmissionState:
    lock: Any = field(default_factory=threading.Lock)
    active: bool = True
    failed: bool = False
    tickets: dict[int, _AdmissionTicket] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class _GatewayCacheReuseScope:
    """One job's dependencies and short-lock admission state, never an I/O lock."""

    authorizer: CacheReuseAuthorizer | None
    principal: CacheReusePrincipal | None
    context: Mapping[str, Any] | None
    cache: PromptCacheProtocol | None
    run_id: str
    settlement_store: BudgetMiddleware
    reuse_guard: CacheReuseGuard
    validate_admission: Callable[[], None] | None
    intent_observer: Callable[[LLMProducerIntent, object], None] | None
    on_close: Callable[[bool], None] | None
    state: _AdmissionState = field(default_factory=_AdmissionState)


_GATEWAY_CACHE_REUSE_SCOPE: ContextVar[_GatewayCacheReuseScope | None] = ContextVar(
    "gateway_cache_reuse_scope", default=None
)


@contextmanager
def _gateway_cache_reuse_scope(
    *,
    authorizer: CacheReuseAuthorizer | None,
    principal: CacheReusePrincipal | None,
    context: Mapping[str, Any] | None,
    cache: PromptCacheProtocol | None,
    run_id: str,
    settlement_store: BudgetMiddleware,
    reuse_guard: CacheReuseGuard,
    validate_admission: Callable[[], None] | None = None,
    intent_observer: Callable[[LLMProducerIntent, object], None] | None = None,
    on_close: Callable[[bool], None] | None = None,
) -> Iterator[None]:
    """Close admission without waiting for a timed-out dependency thread."""
    scope = _GatewayCacheReuseScope(
        authorizer,
        principal,
        context,
        cache,
        run_id,
        settlement_store,
        reuse_guard,
        validate_admission,
        intent_observer,
        on_close,
    )
    token = _GATEWAY_CACHE_REUSE_SCOPE.set(scope)
    try:
        yield
    finally:
        with scope.state.lock:
            scope.state.active = False
            pending = any(not ticket.finished for ticket in scope.state.tickets.values())
            complete = not scope.state.failed and not pending
            for ticket in scope.state.tickets.values():
                ticket.cancelled = True
        try:
            if scope.on_close is not None:
                scope.on_close(complete)
        finally:
            _GATEWAY_CACHE_REUSE_SCOPE.reset(token)


def _execute_scope_ticket[T](
    scope: _GatewayCacheReuseScope,
    operation: Callable[[], T],
    *,
    bounded: bool,
) -> T:
    state = scope.state
    ticket = _AdmissionTicket()
    with state.lock:
        if not state.active:
            raise LLMSettlementOwnershipError("producer_job_scope_closed")
        if scope.settlement_store is None:
            raise LLMSettlementOwnershipError("producer_job_ledger_unavailable")
        state.tickets[id(ticket)] = ticket

    def checked() -> T:
        with state.lock:
            if ticket.cancelled or not state.active:
                raise LLMSettlementOwnershipError("producer_job_scope_closed")
            ticket.started = True
        try:
            result = operation()
            with state.lock:
                if ticket.cancelled or not state.active:
                    raise LLMSettlementOwnershipError("producer_job_scope_closed")
            return result
        finally:
            with state.lock:
                ticket.finished = True
                if ticket.waiter_done:
                    state.tickets.pop(id(ticket), None)

    try:
        return scope.reuse_guard(checked) if bounded else checked()
    except BaseException:
        with state.lock:
            state.failed = True
            ticket.cancelled = True
        raise
    finally:
        with state.lock:
            ticket.waiter_done = True
            # A cancelled queued callback is permitted to run only its closed
            # check later; do not retain one record per never-started timeout.
            if not ticket.started:
                ticket.finished = True
            if ticket.finished:
                state.tickets.pop(id(ticket), None)


def _current_producer_admission[T](
    scope: _GatewayCacheReuseScope,
    operation: Callable[[], T],
) -> T:
    def admitted() -> T:
        if scope.validate_admission is not None:
            scope.validate_admission()
        result = operation()
        if scope.validate_admission is not None:
            scope.validate_admission()
        return result

    return _execute_scope_ticket(scope, admitted, bounded=False)


def _current_cache_reuse_admission[T](
    scope: _GatewayCacheReuseScope,
    operation: Callable[[], T],
) -> T:
    return _current_producer_admission(
        scope, lambda: _execute_scope_ticket(scope, operation, bounded=True)
    )


def _current_producer_begin_executor[T](
    scope: _GatewayCacheReuseScope,
    operation: Callable[[], T],
) -> T:
    return _execute_scope_ticket(scope, operation, bounded=True)


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
            os.getenv("POLISYOS_LLM_GATEWAY_BASE_URL", "").strip() or "https://proxy.gonka.gg/v1"
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
    required_accounting: Callable[[dict[str, Any]], None] | None = None,
    config: GatewayLLMConfig | None = None,
    tracer: Any | None = None,
    metrics: Any | None = None,
    cache_reuse_authorizer: Any | None = None,
    cache_reuse_principal: CacheReusePrincipal | None = None,
    cache_reuse_context: Mapping[str, Any] | None = None,
    prompt_cache: PromptCacheProtocol | None = None,
    require_reuse_authorization: bool = False,
    producer_settlement_store: Any | None = None,
    producer_budget_key: str = "run",
) -> TracedLLMClient | None:
    """Create traced LLM client from env-backed gateway config."""
    reuse_scope = _GATEWAY_CACHE_REUSE_SCOPE.get()
    reuse_guard = None
    if reuse_scope is not None:
        cache_reuse_authorizer = reuse_scope.authorizer
        cache_reuse_principal = reuse_scope.principal
        cache_reuse_context = reuse_scope.context
        prompt_cache = reuse_scope.cache
        require_reuse_authorization = True
        run_id = reuse_scope.run_id
        producer_settlement_store = reuse_scope.settlement_store
        producer_budget_key = f"nl-run:{run_id}"
        reuse_guard = partial(_current_cache_reuse_admission, reuse_scope)
    if _as_bool(os.getenv("POLISYOS_LLM_SIMULATION_MODE"), default=False):
        simulated_model_ids = tuple(dict.fromkeys((model_name, *DEFAULT_SIMULATED_MODEL_IDS)))
        raw_client: (
            SimulatedGatewayLLMClient | CachingLLMClient | FallbackRouter | GatewayLLMClient
        ) = SimulatedGatewayLLMClient(
            model=model_name,
            provider_hint=provider_hint or "simulated_gateway",
            supported_model_ids=simulated_model_ids,
        )
        simulated_config = config
        if simulated_config is None and reuse_scope is not None and prompt_cache is not None:
            simulated_config = GatewayLLMConfig.from_env()
        if (
            simulated_config is not None
            and simulated_config.cache_maxsize > 0
            and simulated_config.cache_ttl_s > 0
        ):
            raw_client = CachingLLMClient(
                raw_client,
                cache=(
                    prompt_cache
                    if prompt_cache is not None
                    else InMemoryPromptCache(
                        maxsize=simulated_config.cache_maxsize,
                        default_ttl_s=simulated_config.cache_ttl_s,
                    )
                ),
                model=model_name,
                ttl_s=simulated_config.cache_ttl_s,
                origin_retention_limit=simulated_config.cache_maxsize,
                provider_route="simulated_gateway",
                reuse_authorizer=cache_reuse_authorizer,
                reuse_principal=cache_reuse_principal,
                reuse_context=cache_reuse_context,
                require_reuse_authorization=require_reuse_authorization,
                reuse_guard=reuse_guard,
            )
        return TracedLLMClient(
            raw_client,
            model_name=model_name,
            capture_prompt=False,
            run_id=run_id,
            model_variant_id=model_variant_id,
            call_observer=call_observer,
            required_accounting=required_accounting,
            prompt_mode="user",
            provider_name="simulated_gateway",
            prompt_sanitizer=None,
            tracer=tracer,
            metrics=metrics,
            producer_settlement_store=producer_settlement_store,
            producer_budget_key=producer_budget_key,
            cache_settlement_session=session_for_cache_client(raw_client),
            producer_admission_guard=(
                partial(_current_producer_admission, reuse_scope)
                if reuse_scope is not None
                else None
            ),
            producer_begin_executor=(
                partial(_current_producer_begin_executor, reuse_scope)
                if reuse_scope is not None
                else None
            ),
            producer_intent_observer=(
                reuse_scope.intent_observer if reuse_scope is not None else None
            ),
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
            cache=(
                prompt_cache
                if prompt_cache is not None
                else InMemoryPromptCache(
                    maxsize=cfg.cache_maxsize,
                    default_ttl_s=cfg.cache_ttl_s,
                )
            ),
            model=model_name,
            ttl_s=cfg.cache_ttl_s,
            origin_retention_limit=cfg.cache_maxsize,
            provider_route=resolved_provider or "gateway",
            inflight_timeout_s=cfg.timeout_s,
            reuse_authorizer=cache_reuse_authorizer,
            reuse_principal=cache_reuse_principal,
            reuse_context=cache_reuse_context,
            require_reuse_authorization=require_reuse_authorization,
            reuse_guard=reuse_guard,
        )
    cache_settlement_session = getattr(raw_client, "_cache_settlement_session", None)
    if cache_settlement_session is None:
        cache_settlement_session = session_for_cache_client(raw_client)
    prompt_sanitizer = PromptSanitizer() if cfg.enable_prompt_sanitizer else None
    return TracedLLMClient(
        raw_client,
        model_name=model_name,
        capture_prompt=cfg.capture_prompt,
        max_prompt_length=cfg.max_prompt_length,
        run_id=run_id,
        model_variant_id=model_variant_id,
        call_observer=call_observer,
        required_accounting=required_accounting,
        prompt_mode="user",
        provider_name=resolved_provider or "gateway",
        prompt_sanitizer=prompt_sanitizer,
        tracer=tracer,
        metrics=metrics,
        cache_settlement_session=cache_settlement_session,
        producer_settlement_store=producer_settlement_store,
        producer_budget_key=producer_budget_key,
        producer_admission_guard=(
            partial(_current_producer_admission, reuse_scope) if reuse_scope is not None else None
        ),
        producer_begin_executor=(
            partial(_current_producer_begin_executor, reuse_scope)
            if reuse_scope is not None
            else None
        ),
        producer_intent_observer=(reuse_scope.intent_observer if reuse_scope is not None else None),
    )


__all__ = [
    "GatewayLLMConfig",
    "create_traced_gateway_client",
]
