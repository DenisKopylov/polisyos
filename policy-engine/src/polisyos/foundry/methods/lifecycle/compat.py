"""
Breaking Change Detection for Foundry Method Signatures.

``SignatureDiff`` compares two ``MethodSignature`` versions and returns a
list of ``BreakingChange`` objects.  Breaking changes are any modifications
that could cause an existing caller to fail without code changes.

Breaking change taxonomy:
- ``removed_input_slot``       — slot consumers will break
- ``removed_output_slot``      — downstream slot consumers will break
- ``input_dtype_changed``      — runtime shape mismatches
- ``output_dtype_changed``     — downstream type errors
- ``input_shape_rank_changed`` — rank mismatch at dispatch time
- ``output_shape_rank_changed``
- ``removed_parameter``        — callers passing this param will error
- ``parameter_bounds_narrowed``— previously valid values now rejected
- ``backend_changed``          — environment requirements change

Non-breaking changes (not reported):
- Adding new optional input slots
- Adding new output slots
- Widening parameter bounds
- Adding tags / metadata changes
- Version bump only

Usage
-----
::

    from polisyos.foundry.methods.lifecycle.compat import SignatureDiff

    diff = SignatureDiff()
    changes = diff.diff(old_signature, new_signature)
    if changes:
        print(f"{len(changes)} breaking change(s) detected!")
        for c in changes:
            print(f"  [{c.kind}] {c.slot_or_param}: {c.old_value!r} → {c.new_value!r}")

CI Integration
--------------
::

    # In CI — fail if breaking changes exist without a major version bump
    from polisyos.foundry.methods.lifecycle.compat import assert_no_breaking_changes
    assert_no_breaking_changes(old_sig, new_sig)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

__all__ = [
    "BreakingChange",
    "BreakingChangeError",
    "SignatureDiff",
    "assert_no_breaking_changes",
]

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

BreakingChangeKind = Literal[
    "removed_input_slot",
    "removed_output_slot",
    "input_dtype_changed",
    "output_dtype_changed",
    "input_shape_rank_changed",
    "output_shape_rank_changed",
    "removed_parameter",
    "parameter_bounds_narrowed",
    "backend_changed",
]


@dataclass(frozen=True)
class BreakingChange:
    """
    A single detected breaking change between two method signature versions.

    Attributes
    ----------
    kind:
        Category of breaking change.
    slot_or_param:
        Name of the affected slot or parameter.
    old_value:
        Value in the old signature (slot dtype, param bound, backend, etc.).
    new_value:
        Value in the new signature.
    description:
        Human-readable explanation.
    """

    kind: str  # BreakingChangeKind value
    slot_or_param: str
    old_value: Any
    new_value: Any
    description: str = ""


class BreakingChangeError(Exception):
    """Raised by ``assert_no_breaking_changes`` when breaking changes exist."""

    def __init__(self, changes: list[BreakingChange]) -> None:
        lines = "\n".join(
            f"  [{c.kind}] {c.slot_or_param}: {c.old_value!r} → {c.new_value!r}" for c in changes
        )
        super().__init__(f"{len(changes)} breaking change(s) detected:\n{lines}")
        self.changes = changes


# ---------------------------------------------------------------------------
# SignatureDiff
# ---------------------------------------------------------------------------


class SignatureDiff:
    """
    Compares two ``MethodSignature`` objects and identifies breaking changes.
    """

    def diff(self, old: Any, new: Any) -> list[BreakingChange]:
        """
        Compute breaking changes from *old* to *new*.

        Parameters
        ----------
        old, new:
            ``MethodSignature`` instances (or any object with
            ``input_slots``, ``output_slots``, ``parameters``,
            and ``backend`` attributes).

        Returns
        -------
        list[BreakingChange]
            Sorted by kind, then slot/param name.  Empty if no breaking
            changes detected.
        """
        changes: list[BreakingChange] = []

        changes.extend(
            self._diff_slots(
                old_slots=list(old.input_slots),
                new_slots=list(new.input_slots),
                kind_removed="removed_input_slot",
                kind_dtype="input_dtype_changed",
                kind_rank="input_shape_rank_changed",
                direction="input",
            )
        )

        changes.extend(
            self._diff_slots(
                old_slots=list(old.output_slots),
                new_slots=list(new.output_slots),
                kind_removed="removed_output_slot",
                kind_dtype="output_dtype_changed",
                kind_rank="output_shape_rank_changed",
                direction="output",
            )
        )

        changes.extend(
            self._diff_parameters(
                old_params=list(getattr(old, "parameters", []) or []),
                new_params=list(getattr(new, "parameters", []) or []),
            )
        )

        changes.extend(self._diff_backend(old, new))

        return sorted(changes, key=lambda c: (c.kind, c.slot_or_param))

    # ------------------------------------------------------------------
    # Internal diff helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _diff_slots(
        old_slots: list[Any],
        new_slots: list[Any],
        kind_removed: str,
        kind_dtype: str,
        kind_rank: str,
        direction: str,
    ) -> list[BreakingChange]:
        changes: list[BreakingChange] = []
        old_by_name = {s.name: s for s in old_slots}
        new_by_name = {s.name: s for s in new_slots}

        for name, old_slot in old_by_name.items():
            if name not in new_by_name:
                changes.append(
                    BreakingChange(
                        kind=kind_removed,
                        slot_or_param=name,
                        old_value=str(getattr(old_slot, "dtype", "?")),
                        new_value=None,
                        description=f"{direction} slot '{name}' removed",
                    )
                )
                continue

            new_slot = new_by_name[name]

            # dtype change
            old_dtype = str(getattr(old_slot, "dtype", None))
            new_dtype = str(getattr(new_slot, "dtype", None))
            if old_dtype != new_dtype and old_dtype != "None" and new_dtype != "None":
                changes.append(
                    BreakingChange(
                        kind=kind_dtype,
                        slot_or_param=name,
                        old_value=old_dtype,
                        new_value=new_dtype,
                        description=(
                            f"{direction} slot '{name}' dtype changed: {old_dtype} → {new_dtype}"
                        ),
                    )
                )

            # shape rank change
            old_shape = getattr(old_slot, "shape", None)
            new_shape = getattr(new_slot, "shape", None)
            if old_shape is not None and new_shape is not None and len(old_shape) != len(new_shape):
                changes.append(
                    BreakingChange(
                        kind=kind_rank,
                        slot_or_param=name,
                        old_value=old_shape,
                        new_value=new_shape,
                        description=(
                            f"{direction} slot '{name}' shape rank changed: "
                            f"{old_shape} → {new_shape}"
                        ),
                    )
                )

        return changes

    @staticmethod
    def _diff_parameters(
        old_params: list[Any],
        new_params: list[Any],
    ) -> list[BreakingChange]:
        changes: list[BreakingChange] = []
        old_by_name = {p.name: p for p in old_params}
        new_by_name = {p.name: p for p in new_params}

        for name, old_p in old_by_name.items():
            if name not in new_by_name:
                # Only breaking if it was a required parameter
                if not getattr(old_p, "optional", True):
                    changes.append(
                        BreakingChange(
                            kind="removed_parameter",
                            slot_or_param=name,
                            old_value=getattr(old_p, "default", "?"),
                            new_value=None,
                            description=f"required parameter '{name}' removed",
                        )
                    )
                continue

            new_p = new_by_name[name]

            # Check if bounds were narrowed
            old_min = getattr(old_p, "min_value", None)
            new_min = getattr(new_p, "min_value", None)
            old_max = getattr(old_p, "max_value", None)
            new_max = getattr(new_p, "max_value", None)

            narrowed = False
            if old_min is not None and new_min is not None and new_min > old_min:
                narrowed = True
            if old_max is not None and new_max is not None and new_max < old_max:
                narrowed = True

            if narrowed:
                changes.append(
                    BreakingChange(
                        kind="parameter_bounds_narrowed",
                        slot_or_param=name,
                        old_value=(old_min, old_max),
                        new_value=(new_min, new_max),
                        description=(
                            f"parameter '{name}' bounds narrowed from "
                            f"[{old_min}, {old_max}] to [{new_min}, {new_max}]"
                        ),
                    )
                )

        return changes

    @staticmethod
    def _diff_backend(old: Any, new: Any) -> list[BreakingChange]:
        changes: list[BreakingChange] = []
        old_backend = getattr(old, "backend", None)
        new_backend = getattr(new, "backend", None)
        if old_backend is not None and new_backend is not None and old_backend != new_backend:
            changes.append(
                BreakingChange(
                    kind="backend_changed",
                    slot_or_param="backend",
                    old_value=getattr(old_backend, "value", str(old_backend)),
                    new_value=getattr(new_backend, "value", str(new_backend)),
                    description=(f"compute backend changed: {old_backend} → {new_backend}"),
                )
            )
        return changes


# ---------------------------------------------------------------------------
# CI helper
# ---------------------------------------------------------------------------


def assert_no_breaking_changes(old: Any, new: Any) -> None:
    """
    Raise ``BreakingChangeError`` if *old* → *new* introduces breaking changes.

    Intended for CI hooks:

    ::

        from polisyos.foundry.methods.lifecycle.compat import assert_no_breaking_changes
        assert_no_breaking_changes(old_sig, new_sig)
        # Passes silently if no breaking changes

    To allow breaking changes with a major version bump::

        from polisyos.foundry.methods.base import parse_fqn

        old_major = int(parse_fqn(old_sig.fqn)[2].split(".")[0])
        new_major = int(parse_fqn(new_sig.fqn)[2].split(".")[0])
        if new_major > old_major:
            return  # major version bump — breaking changes allowed

        assert_no_breaking_changes(old_sig, new_sig)
    """
    changes = SignatureDiff().diff(old, new)
    if changes:
        raise BreakingChangeError(changes)
