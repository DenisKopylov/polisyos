"""Load explicit sibling test modules without relying on pytest import mode."""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def load_sibling_test(caller_file: str | Path, module_stem: str) -> ModuleType:
    """Load and cache one regular ``test_*.py`` sibling by its resolved path.

    This keeps Q2 test helpers available when pytest's canonical configuration
    uses importlib mode, which deliberately does not add test directories to
    ``sys.path``. The module identity is path-derived, so collection order and
    duplicate test basenames elsewhere cannot change resolution.
    """
    if (
        not isinstance(module_stem, str)
        or not module_stem.startswith("test_")
        or not module_stem.isidentifier()
    ):
        raise ImportError("q2_sibling_test_name_is_not_canonical")

    caller = Path(caller_file).resolve(strict=True)
    sibling = caller.with_name(f"{module_stem}.py")
    if sibling.is_symlink() or not sibling.is_file():
        raise ImportError(f"q2_sibling_test_is_unavailable: {module_stem}")
    sibling = sibling.resolve(strict=True)
    module_name = "_e02_q2_sibling_test_" + hashlib.sha256(str(sibling).encode("utf-8")).hexdigest()
    cached = sys.modules.get(module_name)
    if cached is not None:
        cached_path = getattr(cached, "__file__", None)
        if not isinstance(cached_path, str) or Path(cached_path).resolve(strict=True) != sibling:
            raise ImportError(f"q2_sibling_test_cache_identity_changed: {module_stem}")
        return cached

    spec = importlib.util.spec_from_file_location(module_name, sibling)
    if spec is None or spec.loader is None:
        raise ImportError(f"q2_sibling_test_loader_unavailable: {module_stem}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        if sys.modules.get(module_name) is module:
            sys.modules.pop(module_name, None)
        raise
    return module
