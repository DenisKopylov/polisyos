from __future__ import annotations

import importlib.util
import sys
from importlib import metadata
from pathlib import Path
from typing import Iterable

from .metadata import ComponentMetadata
from .protocols import ComponentProvider

ENTRY_POINT_GROUP = "polisyos.components"


def discover_entry_points(
    *,
    group: str = ENTRY_POINT_GROUP,
) -> list[ComponentMetadata | ComponentProvider]:
    """Discover components via entry points."""
    try:
        eps = metadata.entry_points()
        group_eps = eps.select(group=group) if hasattr(eps, "select") else eps.get(group, [])
    except Exception:
        return []

    results: list[ComponentMetadata | ComponentProvider] = []
    for ep in group_eps:
        try:
            obj = ep.load()
        except Exception:
            continue
        if isinstance(obj, ComponentMetadata):
            results.append(obj)
            continue
        if isinstance(obj, ComponentProvider):
            results.append(obj)
            continue
        if callable(obj):
            try:
                created = obj()
            except Exception:
                continue
            if isinstance(created, ComponentMetadata) or isinstance(created, ComponentProvider):
                results.append(created)
    return results


def discover_dev_components(
    root: Path,
) -> list[ComponentMetadata]:
    """Scan a directory for __polisyos_components__ declarations (dev only)."""
    components: list[ComponentMetadata] = []
    for path in root.rglob("*.py"):
        if path.name.startswith("_"):
            continue
        module_name = f"polisyos.components.scan.{path.stem}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        try:
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
        except Exception:
            continue
        finally:
            sys.modules.pop(module_name, None)
        declared = getattr(module, "__polisyos_components__", None)
        if not declared:
            continue
        if isinstance(declared, Iterable):
            for item in declared:
                if isinstance(item, ComponentMetadata):
                    components.append(item)
    return components
