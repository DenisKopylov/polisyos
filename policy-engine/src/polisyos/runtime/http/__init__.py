"""Lazy public facade for the runtime HTTP app and middleware symbols."""

from __future__ import annotations

__all__ = [
    "TENANT_HEADER",
    "AuthzMiddleware",
    "CellRouterMiddleware",
    "JWTAuthMiddleware",
    "create_runtime_api_app",
    "export_runtime_openapi_schema",
    "get_current_user",
]

_EXPORTS: dict[str, tuple[str, str]] = {
    "AuthzMiddleware": ("polisyos.runtime.http.authz_middleware", "AuthzMiddleware"),
    "CellRouterMiddleware": ("polisyos.runtime.http.cell_router_middleware", "CellRouterMiddleware"),
    "JWTAuthMiddleware": ("polisyos.runtime.http.jwt_auth_middleware", "JWTAuthMiddleware"),
    "TENANT_HEADER": ("polisyos.runtime.http.cell_router_middleware", "TENANT_HEADER"),
    "create_runtime_api_app": ("polisyos.runtime.http.app", "create_runtime_api_app"),
    "export_runtime_openapi_schema": ("polisyos.runtime.http.app", "export_runtime_openapi_schema"),
    "get_current_user": ("polisyos.runtime.http.jwt_auth_middleware", "get_current_user"),
}


def __getattr__(name: str) -> object:
    """Resolve runtime HTTP facade exports without importing FastAPI eagerly."""

    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = target
    from importlib import import_module

    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value
