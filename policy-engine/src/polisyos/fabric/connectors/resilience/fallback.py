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
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Awaitable, Callable, Generic, Protocol, TypeVar, runtime_checkable

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from polisyos.common.logger import get_logger
from polisyos.core.observability import get_metrics
from polisyos.fabric.connectors.base import FetchResult, ResilienceInfo

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)

T = TypeVar("T")
DataT = TypeVar("DataT")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _extract_request(args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any | None:
    if "request" in kwargs:
        return kwargs["request"]
    for arg in args:
        if hasattr(arg, "cache_key") and hasattr(arg, "dataset_id"):
            return arg
    return None


def _extract_handle(args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any | None:
    if "handle" in kwargs:
        return kwargs["handle"]
    for arg in args:
        if hasattr(arg, "connector_id") and hasattr(arg, "config"):
            return arg
    return None


def _annotate_fallback(result: DataT, strategy: str) -> DataT:
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
        return result.model_copy(update={"resilience": info})  # type: ignore[return-value]
    return result


@runtime_checkable
class FallbackStrategy(Protocol, Generic[DataT]):
    """Protocol for fallback strategies."""

    @abstractmethod
    async def handle_failure(
        self,
        error: Exception,
        func: Callable[..., Awaitable[DataT]],
        *args: Any,
        **kwargs: Any,
    ) -> DataT | None:
        ...


class RaiseFallback(Generic[DataT]):
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


class MockFallback(Generic[DataT]):
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

            return _annotate_fallback(
                FetchResult(  # type: ignore[return-value]
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
            )
        except Exception:
            return None


class CacheFallback(Generic[DataT]):
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
            logger.debug("Cache fallback: No request found in args")
            return None

        handle = _extract_handle(args, kwargs)
        connector_id = getattr(handle, "connector_id", None) if handle else None

        cached = None
        try:
            if hasattr(self.cache_store, "get_any"):
                cached = self.cache_store.get_any(
                    request,
                    connector_id=connector_id,
                    max_staleness_seconds=self.max_staleness_seconds,
                )
            elif hasattr(self.cache_store, "get"):
                cached = self.cache_store.get(request, connector_id=connector_id)
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

        return _annotate_fallback(result, type(self).__name__)


class FallbackChain(Generic[DataT]):
    """
    Chain of fallback strategies tried in order.
    """

    def __init__(self, strategies: list[FallbackStrategy[DataT]]) -> None:
        if not strategies:
            raise ValueError("Fallback chain requires at least one strategy")
        self.strategies = strategies
        self._metrics = get_metrics()

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
        with tracer.start_as_current_span(
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

                for idx, strategy in enumerate(self.strategies):
                    strategy_name = type(strategy).__name__

                    if self._metrics and getattr(
                        self._metrics, "connector_fallback_triggered_total", None
                    ):
                        labels = {
                            "strategy": strategy_name,
                        }
                        self._metrics.connector_fallback_triggered_total.add(  # type: ignore[union-attr]
                            1,
                            labels,
                        )

                    with tracer.start_as_current_span(
                        f"connector.fallback.strategy_{idx}",
                        attributes={
                            "fallback.strategy": strategy_name,
                            "fallback.index": idx,
                        },
                    ) as strategy_span:
                        try:
                            result = await strategy.handle_failure(
                                primary_error,
                                func,
                                *args,
                                **kwargs,
                            )

                            if result is not None:
                                logger.info(
                                    "Fallback succeeded",
                                    strategy=strategy_name,
                                    index=idx,
                                )

                                if self._metrics and getattr(
                                    self._metrics, "connector_fallback_success_total", None
                                ):
                                    labels = {
                                        "strategy": strategy_name,
                                    }
                                    self._metrics.connector_fallback_success_total.add(  # type: ignore[union-attr]
                                        1,
                                        labels,
                                    )

                                strategy_span.set_status(Status(StatusCode.OK))
                                parent_span.set_attribute(
                                    "fallback.success_strategy",
                                    strategy_name,
                                )
                                parent_span.set_status(Status(StatusCode.OK))

                                return result

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

                            strategy_span.set_status(
                                Status(StatusCode.ERROR, str(fallback_error))
                            )
                            strategy_span.record_exception(fallback_error)

                            if idx == len(self.strategies) - 1:
                                raise

                logger.error(
                    "All fallback strategies exhausted",
                    strategy_count=len(self.strategies),
                )

                parent_span.set_status(
                    Status(StatusCode.ERROR, "All fallbacks exhausted")
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
