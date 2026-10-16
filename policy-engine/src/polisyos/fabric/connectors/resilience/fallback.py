"""
Fallback Strategies for Graceful Degradation.

Implements fallback patterns when primary operations fail:
- CacheFallback: Return stale data from cache
- MockFallback: Return synthetic/empty data
- RaiseFallback: Propagate error (default behavior)
- FallbackChain: Chain multiple strategies
"""

from __future__ import annotations

from abc import abstractmethod
from datetime import UTC, datetime
from functools import wraps
from typing import TYPE_CHECKING, Any, Protocol, TypeVar, cast, runtime_checkable

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode, Tracer

from polisyos.common.logger import get_logger
from polisyos.core.observability import get_metrics
from polisyos.fabric.connectors.base import (
    ConnectionHandle,
    FetchRequest,
    FetchResult,
    ResilienceInfo,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from polisyos.core.observability import MetricsRegistry

logger = get_logger(__name__)
DEFAULT_TRACER = trace.get_tracer(__name__)

T = TypeVar("T")
DataT = TypeVar("DataT")


def _default_metrics() -> MetricsRegistry:
    return get_metrics()


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _extract_request(args: tuple[Any, ...], kwargs: dict[str, Any]) -> FetchRequest | None:
    request = kwargs.get("request")
    if isinstance(request, FetchRequest):
        return request
    return next((arg for arg in args if isinstance(arg, FetchRequest)), None)


def _extract_handle(args: tuple[Any, ...], kwargs: dict[str, Any]) -> ConnectionHandle | None:
    handle = kwargs.get("handle")
    if isinstance(handle, ConnectionHandle):
        return handle
    return next((arg for arg in args if isinstance(arg, ConnectionHandle)), None)


def _callable_chain_contains(candidate: object, target: object) -> bool:
    pending = [candidate]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        if current is target:
            return True
        identity = id(current)
        if identity in seen:
            continue
        seen.add(identity)
        if isinstance(current, (classmethod, staticmethod)):
            pending.append(current.__func__)
            continue
        wrapped = getattr(current, "__wrapped__", None)
        if wrapped is not None:
            pending.append(wrapped)
    return False


def _callable_owner(func: Callable[..., Awaitable[Any]], args: tuple[Any, ...]) -> object | None:
    bound_owner = getattr(func, "__self__", None)
    if bound_owner is not None:
        return bound_owner
    if not args:
        return None
    candidate = args[0]
    for owner_type in type(candidate).__mro__:
        if any(
            _callable_chain_contains(descriptor, func) for descriptor in vars(owner_type).values()
        ):
            return candidate
    return None


def _annotate_fallback[ResultT](result: ResultT, strategy: str) -> ResultT:
    if isinstance(result, FetchResult):
        existing = result.resilience
        update = {
            "fallback_used": True,
            "fallback_strategy": strategy,
        }
        if existing is not None:
            data = existing.model_dump()
            data.update(update)
            info = ResilienceInfo(**data)
        else:
            info = ResilienceInfo(**update)
        return cast("ResultT", result.model_copy(update={"resilience": info}))
    return result


def _fallback_diagnostic(strategy: str, error: Exception) -> dict[str, str]:
    return {
        "strategy": strategy,
        "error_type": type(error).__name__,
        "error_message": str(error),
    }


def _raise_with_fallback_diagnostics(
    primary_error: Exception,
    fallback_errors: list[dict[str, str]],
    *,
    cause: Exception | None = None,
) -> None:
    primary_error.fallback_errors = tuple(fallback_errors)
    note = "Fallback failures: " + ", ".join(
        f"{item['strategy']}[{item['error_type']}]: {item['error_message']}"
        for item in fallback_errors
    )
    if hasattr(primary_error, "add_note"):
        primary_error.add_note(note)
    if cause is not None:
        raise primary_error from cause
    raise primary_error


@runtime_checkable
class FallbackStrategy[DataT](Protocol):
    """Protocol for fallback strategies."""

    @abstractmethod
    async def handle_failure(
        self,
        error: Exception,
        func: Callable[..., Awaitable[DataT]],
        *args: Any,
        **kwargs: Any,
    ) -> DataT | None: ...


class RaiseFallback[DataT]:
    """Fallback strategy that propagates the original error."""

    async def handle_failure(
        self,
        error: Exception,
        func: Callable[..., Awaitable[DataT]],
        *args: Any,
        **kwargs: Any,
    ) -> DataT | None:
        logger.debug(
            "Fallback: Raising original error",
            error_type=type(error).__name__,
            error_message=str(error),
        )
        raise error


class MockFallback[DataT]:
    """Fallback strategy that returns mock/synthetic data."""

    def __init__(self, mock_data: DataT | None = None) -> None:
        self.mock_data = mock_data

    async def handle_failure(
        self,
        error: Exception,
        func: Callable[..., Awaitable[DataT]],
        *args: Any,
        **kwargs: Any,
    ) -> DataT | None:
        logger.warning(
            "Fallback: Using mock data",
            error_type=type(error).__name__,
            has_mock_data=self.mock_data is not None,
        )

        if self.mock_data is not None:
            return _annotate_fallback(self.mock_data, type(self).__name__)

        try:
            from polisyos.fabric.connectors.base import FetchResult
            from polisyos.ir.connectors import DataVersion, VersionStrategy

            return cast(
                "DataT",
                _annotate_fallback(
                    FetchResult(
                        data=[],
                        row_count=0,
                        schema_id="mock",
                        schema_version="1.0.0",
                        version=DataVersion(
                            strategy=VersionStrategy.TIMESTAMP,
                            value="mock",
                            timestamp=_utc_now(),
                        ),
                        fetched_at=_utc_now(),
                        completeness=0.0,
                    ),
                    type(self).__name__,
                ),
            )
        except Exception:
            return None


class CacheFallback[DataT]:
    """Fallback strategy that returns stale data from cache."""

    def __init__(
        self,
        cache_store: Any | None = None,
        max_staleness_seconds: float | None = None,
    ) -> None:
        self.cache_store = cache_store
        self.max_staleness_seconds = max_staleness_seconds

    async def handle_failure(
        self,
        error: Exception,
        func: Callable[..., Awaitable[DataT]],
        *args: Any,
        **kwargs: Any,
    ) -> DataT | None:
        if self.cache_store is None:
            logger.debug("Cache fallback: No cache store configured")
            return None

        request = _extract_request(args, kwargs)
        if request is None:
            logger.debug("Cache fallback: No typed fetch request found in args")
            return None

        handle = _extract_handle(args, kwargs)
        owner = _callable_owner(func, args)
        if handle is None or owner is None:
            logger.debug("Cache fallback: No source owner bound to the primary callable")
            return None
        connector_id = getattr(owner, "connector_id", None)
        if not isinstance(connector_id, str) or not connector_id:
            logger.debug("Cache fallback: Primary callable owner has no connector identity")
            return None
        from polisyos.fabric.connectors.cache import capture_cache_source_intent

        try:
            selected_intent = capture_cache_source_intent(
                handle,
                request,
                expected_connector_id=connector_id,
            )
        except (TypeError, ValueError):
            logger.debug("Cache fallback: Handle is not admitted for the primary owner")
            return None
        source_config = handle.config

        cached = None
        try:
            if hasattr(self.cache_store, "get_any"):
                cached = self.cache_store.get_any(
                    request,
                    connector_id=selected_intent.connector_id,
                    max_staleness_seconds=self.max_staleness_seconds,
                    source_config=source_config,
                )
            elif hasattr(self.cache_store, "get"):
                cached = self.cache_store.get(
                    request,
                    connector_id=selected_intent.connector_id,
                    source_config=source_config,
                )
        except Exception as cache_error:
            logger.warning(
                "Cache fallback failed",
                error=str(cache_error),
            )
            return None

        if cached is None:
            return None

        result = getattr(cached, "result", cached)
        metadata = getattr(cached, "metadata", None)
        age_seconds = None
        if metadata is not None and hasattr(metadata, "cached_at"):
            age_seconds = (_utc_now() - metadata.cached_at).total_seconds()

        logger.warning(
            "Fallback: Using cached data",
            cache_key=getattr(request, "cache_key", None),
            error_type=type(error).__name__,
            cache_age_seconds=age_seconds,
        )

        return cast("DataT", _annotate_fallback(result, type(self).__name__))


class FallbackChain[DataT]:
    """
    Chain of fallback strategies tried in order.
    """

    def __init__(
        self,
        strategies: list[FallbackStrategy[DataT]],
        *,
        metrics: MetricsRegistry | None = None,
        tracer: Tracer | None = None,
    ) -> None:
        if not strategies:
            raise ValueError("Fallback chain requires at least one strategy")
        self.strategies = strategies
        self._metrics = metrics if metrics is not None else _default_metrics()
        self._tracer = tracer or DEFAULT_TRACER

        logger.debug(
            "Fallback chain initialized",
            strategy_count=len(strategies),
            strategy_types=[type(s).__name__ for s in strategies],
        )

    async def execute(
        self,
        func: Callable[..., Awaitable[DataT]],
        *args: Any,
        **kwargs: Any,
    ) -> DataT:
        with self._tracer.start_as_current_span(
            "connector.fallback.execute",
            attributes={
                "fallback.strategy_count": len(self.strategies),
            },
        ) as parent_span:
            try:
                result = await func(*args, **kwargs)
                parent_span.set_status(Status(StatusCode.OK))
                return result

            except Exception as primary_error:
                logger.warning(
                    "Primary operation failed, trying fallbacks",
                    error_type=type(primary_error).__name__,
                    error_message=str(primary_error),
                    fallback_count=len(self.strategies),
                )

                parent_span.record_exception(primary_error)
                fallback_errors: list[dict[str, str]] = []
                last_fallback_error: Exception | None = None

                for idx, strategy in enumerate(self.strategies):
                    strategy_name = type(strategy).__name__

                    fallback_triggered = getattr(
                        self._metrics,
                        "connector_fallback_triggered_total",
                        None,
                    )
                    if fallback_triggered is not None:
                        labels = {
                            "strategy": strategy_name,
                        }
                        fallback_triggered.add(1, labels)

                    with self._tracer.start_as_current_span(
                        f"connector.fallback.strategy_{idx}",
                        attributes={
                            "fallback.strategy": strategy_name,
                            "fallback.index": idx,
                        },
                    ) as strategy_span:
                        try:
                            fallback_result = await strategy.handle_failure(
                                primary_error,
                                func,
                                *args,
                                **kwargs,
                            )

                            if fallback_result is not None:
                                logger.info(
                                    "Fallback succeeded",
                                    strategy=strategy_name,
                                    index=idx,
                                )

                                fallback_success = getattr(
                                    self._metrics,
                                    "connector_fallback_success_total",
                                    None,
                                )
                                if fallback_success is not None:
                                    labels = {
                                        "strategy": strategy_name,
                                    }
                                    fallback_success.add(1, labels)

                                strategy_span.set_status(Status(StatusCode.OK))
                                parent_span.set_attribute(
                                    "fallback.success_strategy",
                                    strategy_name,
                                )
                                parent_span.set_status(Status(StatusCode.OK))

                                return fallback_result

                            logger.debug(
                                "Fallback strategy returned None",
                                strategy=strategy_name,
                            )

                        except Exception as fallback_error:
                            logger.debug(
                                "Fallback strategy raised error",
                                strategy=strategy_name,
                                error_type=type(fallback_error).__name__,
                            )

                            strategy_span.set_status(Status(StatusCode.ERROR, str(fallback_error)))
                            strategy_span.record_exception(fallback_error)
                            fallback_errors.append(
                                _fallback_diagnostic(strategy_name, fallback_error)
                            )
                            last_fallback_error = fallback_error

                logger.error(
                    "All fallback strategies exhausted",
                    strategy_count=len(self.strategies),
                )

                parent_span.set_status(Status(StatusCode.ERROR, "All fallbacks exhausted"))
                if fallback_errors:
                    _raise_with_fallback_diagnostics(
                        primary_error,
                        fallback_errors,
                        cause=last_fallback_error,
                    )
                raise primary_error


def with_fallback(
    chain: FallbackChain[T] | list[FallbackStrategy[T]],
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """
    Decorator to add fallback chain to async functions.
    """
    if isinstance(chain, list):
        chain = FallbackChain(chain)

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            return await chain.execute(func, *args, **kwargs)

        wrapper._fallback_chain = chain  # type: ignore[attr-defined]
        return wrapper

    return decorator
