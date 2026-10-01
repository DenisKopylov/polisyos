"""Lazy package facade for the runtime control service modules."""

from importlib import import_module
from typing import Any

_API_MODULE = f"{__name__}.api"


def __getattr__(name: str) -> Any:
    """Resolve child modules before loading the public service API."""
    if name == "__all__":
        return getattr(import_module(_API_MODULE), name)

    child_module = f"{__name__}.{name}"
    try:
        return import_module(child_module)
    except ModuleNotFoundError as exc:
        if exc.name != child_module:
            raise

    api = import_module(_API_MODULE)
    try:
        return getattr(api, name)
    except AttributeError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
