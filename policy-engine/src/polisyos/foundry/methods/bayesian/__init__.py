"""Lazy facade for sampling-heavy Bayesian catalog methods."""

from __future__ import annotations

import ast
from importlib import import_module
from pathlib import Path
from typing import Any


def _read_exports() -> tuple[str, ...]:
    tree = ast.parse(Path(__file__).with_name("_facade.py").read_text())
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets
        ):
            continue
        return tuple(str(name) for name in ast.literal_eval(node.value))
    return ()


__all__ = _read_exports()


def __getattr__(name: str) -> Any:
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module("polisyos.foundry.methods.bayesian._facade"), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted({*globals(), *__all__})
