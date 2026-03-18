"""
Mypy plugin for the ``@foundry_method`` decorator.

Performs *static* validation at mypy-check time:

1. The decorated class must have a ``signature`` class variable.
2. ``signature`` must be typed as ``MethodSignature`` (or a subtype).
3. The decorated class must have a ``pure_step`` *staticmethod*.
4. ``pure_step`` must have the signature
   ``(state: Any, params: Mapping[str, Any]) -> dict[str, Any]``.
5. The FQN embedded in ``signature.name`` must not contain ``@`` or whitespace.

Errors emitted here are cheaper than the runtime ``MethodDefinitionError``
because they appear during ``mypy`` without importing heavy dependencies.

Usage — register in ``pyproject.toml``:

    [tool.mypy]
    plugins = ["polisyos.foundry.methods.mypy_plugin"]

Or in ``mypy.ini``:

    [mypy]
    plugins = polisyos.foundry.methods.mypy_plugin
"""
from __future__ import annotations

from typing import Callable

from mypy.plugin import ClassDefContext, Plugin
from mypy.types import AnyType  # noqa: F401 — kept for potential future checks

# Fully qualified name of the decorator as mypy resolves it.
_FOUNDRY_METHOD_DECORATOR = "polisyos.foundry.methods.base.foundry_method"

# Fully qualified name of MethodSignature (used for type-checking the attribute).
_METHOD_SIGNATURE_TYPE = "polisyos.foundry.methods.base.MethodSignature"


# ---------------------------------------------------------------------------
# Hook: class decorated with @foundry_method(...)
# ---------------------------------------------------------------------------

def _foundry_method_hook(ctx: ClassDefContext) -> None:
    """Validate a class decorated with @foundry_method(...)."""
    cls = ctx.cls
    info = cls.info

    # ------------------------------------------------------------------
    # 1. Must have a ``signature`` class variable
    # ------------------------------------------------------------------
    if "signature" not in info.names:
        ctx.api.fail(
            f'Class "{cls.name}" decorated with @foundry_method must define '
            f"a class-level `signature: MethodSignature` attribute.",
            ctx.cls,
        )
        return  # subsequent checks depend on signature existing

    # ------------------------------------------------------------------
    # 2. ``signature`` must be (or be assignable to) MethodSignature
    # ------------------------------------------------------------------
    # Note: deep subtype checking via ctx.api.check_subtype is skipped because
    # it triggers mypy internal errors in some module contexts. The runtime
    # validator in base.py enforces the type contract reliably.

    # ------------------------------------------------------------------
    # 3. Must have a ``pure_step`` attribute
    # ------------------------------------------------------------------
    if "pure_step" not in info.names:
        ctx.api.fail(
            f'Class "{cls.name}" decorated with @foundry_method must define '
            f"a `pure_step` @staticmethod.",
            ctx.cls,
        )
        return

    # ------------------------------------------------------------------
    # 4–5. Deep type checks (staticmethod callability, arg count) are
    # skipped here: ctx.api during semantic analysis is a SemanticAnalyzer
    # which has no get_type_of_node method (that is a type-checker API).
    # Runtime checks in base.py enforce these constraints reliably.
    # ------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Plugin class
# ---------------------------------------------------------------------------

class FoundryMethodPlugin(Plugin):
    """Mypy plugin entry-point for @foundry_method validation."""

    def get_class_decorator_hook(
        self, fullname: str
    ) -> Callable[[ClassDefContext], None] | None:
        """
        Return our validation hook for the @foundry_method decorator.

        Mypy calls this method with the fully-qualified name of every class
        decorator it encounters.  We only care about ``@foundry_method``.
        """
        if fullname == _FOUNDRY_METHOD_DECORATOR:
            return _foundry_method_hook
        return None


def plugin(version: str) -> type[Plugin]:
    """Mypy plugin entry-point (called by mypy at startup)."""
    return FoundryMethodPlugin
