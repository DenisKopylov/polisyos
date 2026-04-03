"""Tenant-scoped execution context utilities."""
from __future__ import annotations

import contextvars
import functools
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Iterator, ParamSpec, TypeVar

from polisyos.core.security.db_backend import DatabaseBackend
from polisyos.core.security.exceptions import TenantContextNotSetError

if TYPE_CHECKING:
    from polisyos.core.security.access_scope import AccessScope

P = ParamSpec("P")
R = TypeVar("R")

_current_tenant: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_tenant", default=None
)
_current_cell: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_cell", default=None
)
_current_access_scope: contextvars.ContextVar["AccessScope | None"] = contextvars.ContextVar(
    "current_access_scope", default=None
)


@dataclass(frozen=True)
class TenantContext:
    """Capture the active tenant and optional cell binding for one scoped block."""
    tenant_id: str
    cell_id: str | None = None


def get_current_tenant_id() -> str:
    """Return current tenant id."""
    tenant_id = _current_tenant.get()
    if tenant_id is None:
        raise TenantContextNotSetError(
            "No tenant context active. Use tenant_scope(...) before tenant-scoped operations."
        )
    return tenant_id


def get_current_tenant_id_or_none() -> str | None:
    """Return current tenant id or none."""
    return _current_tenant.get()


def get_current_cell_id() -> str | None:
    """Return current cell id."""
    return _current_cell.get()


def set_current_access_scope(
    scope: "AccessScope | None",
) -> contextvars.Token["AccessScope | None"]:
    """Install the current request access scope and return a reset token."""
    return _current_access_scope.set(scope)


def reset_current_access_scope(
    token: contextvars.Token["AccessScope | None"],
) -> None:
    """Restore the previous access scope from a `ContextVar` token."""
    _current_access_scope.reset(token)


def get_current_access_scope_or_none() -> "AccessScope | None":
    """Return current access scope or none."""
    return _current_access_scope.get()


@contextmanager
def tenant_scope(
    backend: DatabaseBackend | None,
    *,
    tenant_id: str,
    cell_id: str | None = None,
) -> Iterator[TenantContext]:
    """Enter a tenant-scoped contextvars and optional backend transaction scope."""
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
    """Decorate a function so it fails fast when no tenant context is active."""
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
    "get_current_access_scope_or_none",
    "set_current_access_scope",
    "reset_current_access_scope",
]
