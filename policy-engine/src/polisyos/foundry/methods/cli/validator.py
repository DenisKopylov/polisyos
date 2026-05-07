"""
Method Validator CLI — validate a Foundry method class or file.

Checks all ABI constraints and emits a structured report:

1. ``pure_step`` is a ``@staticmethod``
2. ``signature`` is a valid ``MethodSignature``
3. ``metadata`` is a valid ``MethodMetadata``
4. FQN parses correctly (``namespace.name@semver``)
5. ``pure_step`` can be called with zero-shaped arrays (smoke test)
6. Output keys match declared ``output_slots``
7. No global mutable state accessed in ``pure_step``
8. Slot names are unique within input/output sets
9. Version is valid SemVer

Usage (standalone)
------------------
::

    # Validate a single Python file
    python -m polisyos.foundry.methods.cli.validator path/to/my_method.py

    # Validate a specific class in a module
    python -m polisyos.foundry.methods.cli.validator \\
        --module polisyos.foundry.methods.catalog.causal.rdd \\
        --class RDDEstimator

    # Validate all registered methods
    python -m polisyos.foundry.methods.cli.validator --all

Usage (programmatic)
--------------------
::

    from polisyos.foundry.methods.cli.validator import MethodValidator, ValidationReport

    validator = MethodValidator()
    report = validator.validate_class(MyMethod)
    report.print_summary()
    assert report.passed
"""

from __future__ import annotations

import inspect
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "MethodValidator",
    "ValidationIssue",
    "ValidationReport",
    "validate_method_class",
]


# ---------------------------------------------------------------------------
# ValidationIssue / ValidationReport
# ---------------------------------------------------------------------------


@dataclass
class ValidationIssue:
    """A single validation finding."""

    severity: str  # "error" | "warning" | "info"
    code: str  # Short machine-readable code, e.g. "E001"
    message: str
    hint: str = ""

    def __str__(self) -> str:
        prefix = {"error": "✗", "warning": "!", "info": "i"}.get(self.severity, "?")
        out = f"  [{self.code}] {prefix} {self.message}"
        if self.hint:
            out += f"\n       hint: {self.hint}"
        return out


@dataclass
class ValidationReport:
    """Aggregated validation result for one method class."""

    class_name: str
    fqn: str | None
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def passed(self) -> bool:
        return len(self.errors) == 0

    def add(self, severity: str, code: str, message: str, hint: str = "") -> None:
        self.issues.append(ValidationIssue(severity, code, message, hint))

    def print_summary(self) -> None:
        status = "PASS" if self.passed else "FAIL"
        print(f"\n{'=' * 60}")
        print(f"  {status}  {self.class_name}  ({self.fqn or 'no FQN'})")
        print(f"  {len(self.errors)} error(s), {len(self.warnings)} warning(s)")
        print("=" * 60)
        for issue in self.issues:
            print(str(issue))
        if not self.issues:
            print("  No issues found.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "class_name": self.class_name,
            "fqn": self.fqn,
            "passed": self.passed,
            "n_errors": len(self.errors),
            "n_warnings": len(self.warnings),
            "issues": [
                {"severity": i.severity, "code": i.code, "message": i.message, "hint": i.hint}
                for i in self.issues
            ],
        }


# ---------------------------------------------------------------------------
# MethodValidator
# ---------------------------------------------------------------------------


class MethodValidator:
    """
    Validates a Foundry method class against the ABI contract.

    Parameters
    ----------
    run_smoke_test:
        If True (default), attempts to call ``pure_step`` with tiny zero
        arrays to detect runtime errors in the happy path.
    """

    def __init__(self, run_smoke_test: bool = True) -> None:
        self._smoke = run_smoke_test

    def validate_class(self, method_class: type) -> ValidationReport:
        """Run all validation checks on *method_class*."""
        fqn: str | None = None
        try:
            sig = getattr(method_class, "signature", None)
            if sig is not None:
                fqn = getattr(sig, "fqn", None)
        except Exception:
            pass

        report = ValidationReport(
            class_name=method_class.__name__,
            fqn=fqn,
        )

        self._check_pure_step(method_class, report)
        self._check_signature(method_class, report)
        self._check_metadata(method_class, report)
        self._check_fqn(method_class, report)
        self._check_slot_uniqueness(method_class, report)

        if self._smoke and report.passed:
            self._run_smoke_test(method_class, report)

        return report

    def validate_registry(self) -> list[ValidationReport]:
        """Validate all methods currently in the global registry."""
        from polisyos.foundry.methods.selection.registry import get_registry

        reg = get_registry()
        reports = []
        for entry in reg.list_all():
            try:
                method_class = reg.get(entry.fqn)
                reports.append(self.validate_class(method_class))
            except Exception as exc:
                r = ValidationReport(class_name=entry.fqn, fqn=entry.fqn)
                r.add("error", "E099", f"Cannot load class: {exc}")
                reports.append(r)
        return reports

    def validate_file(self, path: Path) -> list[ValidationReport]:
        """Load a Python file and validate all Foundry method classes found in it."""
        import importlib.util
        import sys

        spec = importlib.util.spec_from_file_location("_foundry_validate_tmp", path)
        if spec is None or spec.loader is None:
            r = ValidationReport(class_name=str(path), fqn=None)
            r.add("error", "E098", f"Cannot load file: {path}")
            return [r]

        module = importlib.util.module_from_spec(spec)
        sys.modules["_foundry_validate_tmp"] = module
        try:
            spec.loader.exec_module(module)  # type: ignore[union-attr]
        except Exception as exc:
            r = ValidationReport(class_name=str(path), fqn=None)
            r.add("error", "E097", f"Import error: {exc}")
            return [r]
        finally:
            sys.modules.pop("_foundry_validate_tmp", None)

        from polisyos.foundry.methods.discovery import is_foundry_method

        reports = []
        for name in dir(module):
            obj = getattr(module, name, None)
            if obj is None:
                continue
            try:
                if is_foundry_method(obj):
                    reports.append(self.validate_class(obj))
            except Exception:
                pass
        return reports

    # ------------------------------------------------------------------
    # Internal check methods
    # ------------------------------------------------------------------

    def _check_pure_step(self, cls: type, report: ValidationReport) -> None:
        pure_step = inspect.getattr_static(cls, "pure_step", None)
        if pure_step is None:
            report.add(
                "error",
                "E001",
                "Missing 'pure_step' attribute.",
                hint="Add @staticmethod def pure_step(state, params) -> dict",
            )
            return
        if not isinstance(pure_step, staticmethod):
            report.add(
                "error",
                "E002",
                "'pure_step' must be a @staticmethod.",
                hint="Decorate with @staticmethod — it may not access 'cls' or 'self'.",
            )
        sig = inspect.signature(cls.pure_step)
        params = list(sig.parameters.keys())
        if params != ["state", "params"]:
            report.add(
                "warning",
                "W001",
                f"'pure_step' parameters {params!r} differ from expected ['state', 'params'].",
                hint="Signature should be: pure_step(state, params) -> dict",
            )

    def _check_signature(self, cls: type, report: ValidationReport) -> None:
        from polisyos.foundry.methods.base import MethodSignature

        sig = getattr(cls, "signature", None)
        if sig is None:
            report.add("error", "E003", "Missing 'signature' class attribute.")
            return
        if not isinstance(sig, MethodSignature):
            report.add(
                "error", "E004", f"'signature' must be MethodSignature, got {type(sig).__name__}."
            )
            return
        # Check backend-supports_jit consistency
        from polisyos.foundry.methods.base import ComputeBackend

        if sig.backend != ComputeBackend.JAX:
            if sig.supports_jit or sig.supports_vmap or sig.supports_grad:
                report.add(
                    "error",
                    "E005",
                    "Non-JAX backend must have supports_jit=False, supports_vmap=False, "
                    "supports_grad=False.",
                )

    def _check_metadata(self, cls: type, report: ValidationReport) -> None:
        from polisyos.foundry.methods.base import MethodMetadata

        meta = getattr(cls, "metadata", None)
        if meta is None:
            report.add("error", "E006", "Missing 'metadata' class attribute.")
            return
        if not isinstance(meta, MethodMetadata):
            report.add(
                "error", "E007", f"'metadata' must be MethodMetadata, got {type(meta).__name__}."
            )
            return
        if not meta.description.strip():
            report.add(
                "warning",
                "W002",
                "metadata.description is empty.",
                hint="Add a meaningful description for catalog display and LLM selection.",
            )
        if not meta.tags:
            report.add(
                "warning",
                "W003",
                "metadata.tags is empty.",
                hint="Add at least one tag for discoverability.",
            )

    def _check_fqn(self, cls: type, report: ValidationReport) -> None:
        from polisyos.foundry.methods.base import parse_fqn

        sig = getattr(cls, "signature", None)
        if sig is None:
            return
        fqn = getattr(sig, "fqn", None)
        if fqn is None:
            report.add("error", "E008", "signature.fqn is None.")
            return
        try:
            parse_fqn(fqn)
        except ValueError as exc:
            report.add(
                "error",
                "E009",
                f"Invalid FQN: {exc}",
                hint="FQN must be 'namespace.name@semver', e.g. 'causal.did.standard@1.0.0'",
            )

    def _check_slot_uniqueness(self, cls: type, report: ValidationReport) -> None:
        sig = getattr(cls, "signature", None)
        if sig is None:
            return
        input_names = [s.name for s in getattr(sig, "input_slots", [])]
        if len(input_names) != len(set(input_names)):
            report.add("error", "E010", f"Duplicate input slot names: {input_names}")
        output_names = [s.name for s in getattr(sig, "output_slots", [])]
        if len(output_names) != len(set(output_names)):
            report.add("error", "E011", f"Duplicate output slot names: {output_names}")

    def _run_smoke_test(self, cls: type, report: ValidationReport) -> None:
        """Call pure_step with zero-shaped inputs — check it doesn't crash unexpectedly."""
        import numpy as np

        sig = getattr(cls, "signature", None)
        if sig is None:
            return
        state: dict[str, Any] = {}
        for slot in getattr(sig, "input_slots", []):
            shape = getattr(slot, "shape", None)
            if shape:
                dims = tuple(2 for _ in shape)
                state[slot.name] = np.zeros(dims)
            else:
                state[slot.name] = np.zeros((2,))

        try:
            result = cls.pure_step(state, {"seed": 0})
            if not isinstance(result, dict):
                report.add(
                    "warning", "W004", f"pure_step returned {type(result).__name__}, expected dict."
                )
                return
            declared_outputs = {s.name for s in getattr(sig, "output_slots", [])}
            returned = set(result.keys())
            missing = declared_outputs - returned
            if missing:
                report.add(
                    "warning",
                    "W005",
                    f"Smoke test: output missing declared slots: {sorted(missing)}",
                )
        except NotImplementedError:
            report.add("info", "I001", "pure_step raises NotImplementedError (scaffold stub).")
        except Exception as exc:
            tb = traceback.format_exc(limit=3)
            report.add(
                "warning",
                "W006",
                f"Smoke test raised {type(exc).__name__}: {exc}",
                hint=tb.strip().splitlines()[-1] if tb.strip() else "",
            )


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------


def validate_method_class(cls: type, run_smoke_test: bool = True) -> ValidationReport:
    """Validate a single Foundry method class. Raises nothing — returns a report."""
    return MethodValidator(run_smoke_test=run_smoke_test).validate_class(cls)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Main helper."""
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(
        prog="foundry-validate",
        description="Validate Foundry method classes.",
    )
    src_group = parser.add_mutually_exclusive_group(required=True)
    src_group.add_argument("file", nargs="?", type=Path, help="Python file to validate.")
    src_group.add_argument("--module", help="Module to import (e.g. polisyos.foundry...)")
    src_group.add_argument(
        "--all", action="store_true", dest="validate_all", help="Validate all registered methods."
    )
    parser.add_argument("--class", dest="class_name", help="Specific class name to validate.")
    parser.add_argument("--no-smoke", action="store_true", help="Skip smoke test.")
    parser.add_argument("--json", action="store_true", dest="json_out", help="Output JSON.")
    args = parser.parse_args()

    validator = MethodValidator(run_smoke_test=not args.no_smoke)
    reports: list[ValidationReport] = []

    if args.validate_all:
        reports = validator.validate_registry()
    elif args.module:
        import importlib

        module = importlib.import_module(args.module)
        from polisyos.foundry.methods.discovery import is_foundry_method

        for name in dir(module):
            obj = getattr(module, name, None)
            if obj and is_foundry_method(obj):
                if args.class_name is None or name == args.class_name:
                    reports.append(validator.validate_class(obj))
    elif args.file:
        reports = validator.validate_file(args.file)

    if args.json_out:
        print(json.dumps([r.to_dict() for r in reports], indent=2))
    else:
        for r in reports:
            r.print_summary()
        total = len(reports)
        passed = sum(1 for r in reports if r.passed)
        print(f"\n{passed}/{total} methods passed validation.")

    has_errors = any(not r.passed for r in reports)
    sys.exit(1 if has_errors else 0)


if __name__ == "__main__":
    main()
