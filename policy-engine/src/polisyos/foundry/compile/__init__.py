"""Expose the compile facade without importing the Trinity compiler eagerly.

The package-level `compile` export is a stable alias of
`polisyos.foundry.compile.api.compile`. It is resolved lazily so tooling can
inspect the package without paying the import cost of the compiler stack.
"""

from __future__ import annotations

import importlib
import sys
import types
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .api import build_method_housekeeping_nodes, verify_expected_candidate_rejection
    from .manifest_inputs import execution_plan_input_refs, program_graph_input_refs
    from .randomization import TreasuryPlan, build_treasury_plan

__all__ = [
    "TreasuryPlan",
    "build_treasury_plan",
    "build_method_housekeeping_nodes",
    "compile",
    "execution_plan_input_refs",
    "program_graph_input_refs",
    "replay_method_program_graph",
    "verify_expected_candidate_rejection",
]

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "compile": ("polisyos.foundry.compile.api", "compile"),
    "build_method_housekeeping_nodes": (
        "polisyos.foundry.compile.api",
        "build_method_housekeeping_nodes",
    ),
    "TreasuryPlan": ("polisyos.foundry.compile.randomization", "TreasuryPlan"),
    "build_treasury_plan": ("polisyos.foundry.compile.randomization", "build_treasury_plan"),
    "execution_plan_input_refs": (
        "polisyos.foundry.compile.manifest_inputs",
        "execution_plan_input_refs",
    ),
    "program_graph_input_refs": (
        "polisyos.foundry.compile.manifest_inputs",
        "program_graph_input_refs",
    ),
    "replay_method_program_graph": ("polisyos.foundry.compile.api", "replay_method_program_graph"),
    "verify_expected_candidate_rejection": (
        "polisyos.foundry.compile.api",
        "verify_expected_candidate_rejection",
    ),
}


def __getattr__(name: str) -> Any:
    """Resolve the lazy `compile` export or raise for unknown names."""
    if name in _LAZY_IMPORTS:
        module_name, attr_name = _LAZY_IMPORTS[name]
        module = importlib.import_module(module_name)
        value = getattr(module, attr_name)
        globals()[name] = value
        return value

    module_name = f"{__name__}.{name}"
    try:
        value = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name == module_name:
            raise AttributeError(name) from None
        raise
    globals()[name] = value
    return value


class _CallableCompileModule(types.ModuleType):
    """Allow `polisyos.foundry.compile(...)` while preserving package imports."""

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return __getattr__("compile")(*args, **kwargs)


sys.modules[__name__].__class__ = _CallableCompileModule

parent = sys.modules.get("polisyos.foundry")
if parent is not None:
    parent.__dict__["compile"] = sys.modules[__name__]
    parent.__dict__["compile_program"] = sys.modules[__name__]
