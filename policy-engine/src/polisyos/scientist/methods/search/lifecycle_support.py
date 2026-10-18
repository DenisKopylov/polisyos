"""Shared runtime support for the legacy search facade and lifecycle owner."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from polisyos.common.logger import get_logger
from polisyos.scientist.orchestration.engine.error_semantics import emit_degraded_path

if TYPE_CHECKING:
    from polisyos.core.observability import MetricsRegistry


logger = get_logger("polisyos.scientist.methods.search.controller")
_IMPORT_ERRORS = (ImportError, ModuleNotFoundError)
_SEARCH_DEGRADED_ERRORS = (AttributeError, TypeError, ValidationError, ValueError)


@dataclass(frozen=True)
class _PolicyEvaluationResolution:
    """Keep absent, valid, and invalid typed results distinct at the consumer."""

    value: Any | None
    status: str
    reason: str | None = None


_PolicyEvaluationResolution.__module__ = "polisyos.scientist.methods.search.controller"


def _default_metrics() -> MetricsRegistry:
    """Resolve the existing process metrics registry only when needed."""
    from polisyos.core.observability import get_metrics

    return get_metrics()


def _search_degraded(
    *,
    operation: str,
    reason: str,
    exc: BaseException,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Emit one degraded-path record under the historical controller logger."""
    return emit_degraded_path(
        component="search.controller",
        operation=operation,
        reason=reason,
        exc=exc,
        details=details,
        log=logger,
    )


def _as_bool(raw: str | None, default: bool = False) -> bool:
    """Interpret one environment flag using the existing accepted spellings."""
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}
