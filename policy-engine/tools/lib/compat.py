"""Compatibility helpers for legacy tool module and script entry points."""

from __future__ import annotations

import importlib
import inspect
import sys
from collections.abc import Sequence
from typing import Any

DEFAULT_SHIM_SUNSET = "2026-09-01"


def expose_module(target_globals: dict[str, Any], module_name: str) -> Any:
    """Populate a shim module namespace from a canonical implementation module."""

    module = importlib.import_module(module_name)
    exported = getattr(module, "__all__", None)
    if exported is None:
        exported = [name for name in vars(module) if not name.startswith("__")]
    target_globals.update({name: getattr(module, name) for name in exported})
    target_globals.setdefault("__doc__", getattr(module, "__doc__", None))
    target_globals.setdefault("__all__", tuple(exported))
    return module


def run_module_entrypoint(
    module_name: str,
    *,
    argv: Sequence[str] | None = None,
    preferred_names: Sequence[str] = ("main", "check"),
) -> int:
    """Invoke a conventional ``main``/``check`` function from a shim module."""

    module = importlib.import_module(module_name)
    target = None
    for name in preferred_names:
        candidate = getattr(module, name, None)
        if callable(candidate):
            target = candidate
            break
    if target is None:
        raise AttributeError(f"{module_name} does not expose any of {preferred_names!r}")

    args = list(argv if argv is not None else sys.argv[1:])
    try:
        signature = inspect.signature(target)
    except (TypeError, ValueError):
        signature = None

    try:
        if signature is not None and len(signature.parameters) == 0:
            result = target()
        else:
            result = target(args)
    except SystemExit as exc:
        if isinstance(exc.code, int):
            return exc.code
        return 0 if exc.code is None else 1

    if result is None:
        return 0
    if isinstance(result, int):
        return result
    raise TypeError(f"{module_name} entry point returned unsupported type: {type(result).__name__}")


def run_legacy_module_entrypoint(
    module_name: str,
    *,
    legacy_path: str,
    replacement: str,
    argv: Sequence[str] | None = None,
    preferred_names: Sequence[str] = ("main", "check"),
) -> int:
    """Warn about a legacy script path, then invoke its canonical target."""

    warn_legacy_entrypoint(legacy_path, replacement)
    return run_module_entrypoint(module_name, argv=argv, preferred_names=preferred_names)


def warn_legacy_entrypoint(
    legacy_path: str,
    replacement: str,
    *,
    sunset: str = DEFAULT_SHIM_SUNSET,
) -> None:
    """Emit a standardized deprecation warning for a compatibility wrapper."""

    sys.stderr.write(
        "DEPRECATED: "
        f"`{legacy_path}` is a compatibility wrapper; "
        f"use `{replacement}` instead. "
        f"This shim sunsets on {sunset}.\n"
    )
