"""Tenant-scoped execution context utilities."""
from __future__ import annotations

import contextvars
import functools
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable, Iterator, ParamSpec, TypeVar

from polisyos.core.security.db_backend import DatabaseBackend
from polisyos.core.security.exceptions import TenantContextNotSetError

P = ParamSpec("P")
R = TypeVar("R")

_current_tenant: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_tenant", default=None
)
_current_cell: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_cell", default=None
)


@dataclass(frozen=True)
class TenantContext:
    tenant_id: str
    cell_id: str | None = None


def get_current_tenant_id() -> str:
    tenant_id = _current_tenant.get()
    if tenant_id is None:
        raise TenantContextNotSetError(
            "No tenant context active. Use tenant_scope(...) before tenant-scoped operations."
        )
    return tenant_id


def get_current_tenant_id_or_none() -> str | None:
    return _current_tenant.get()


def get_current_cell_id() -> str | None:
    return _current_cell.get()


@contextmanager
def tenant_scope(
    backend: DatabaseBackend | None,
    *,
    tenant_id: str,
    cell_id: str | None = None,
) -> Iterator[TenantContext]:
    token_tenant = _current_tenant.set(tenant_id)
    token_cell = _current_cell.set(cell_id)
    try:
        if backend is None:
            yield TenantContext(tenant_id=tenant_id, cell_id=cell_id)
        else:
            with backend.tenant_scope(tenant_id):
                yield TenantContext(tenant_id=tenant_id, cell_id=cell_id)
    finally:
        _current_tenant.reset(token_tenant)
        _current_cell.reset(token_cell)


def require_tenant_context(func: Callable[P, R]) -> Callable[P, R]:
    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        _ = get_current_tenant_id()
        return func(*args, **kwargs)

    return wrapper


__all__ = [
    "TenantContext",
    "tenant_scope",
    "require_tenant_context",
    "get_current_tenant_id",
    "get_current_tenant_id_or_none",
    "get_current_cell_id",
]
