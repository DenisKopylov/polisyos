"""
Foundry Methods CLI — ``polisyos-foundry`` entrypoint.

Subcommands
-----------
scaffold    Generate a new Foundry method skeleton.
validate    Validate a method class or an entire registry.
catalog     Print the catalog snapshot (FQNs, fidelity, backend).
compat      Check for breaking signature changes vs. a baseline.

Usage::

    polisyos-foundry --help
    polisyos-foundry scaffold --namespace causal.did --name my_estimator --version 1.0.0
    polisyos-foundry validate --all
    polisyos-foundry catalog --namespace causal
    polisyos-foundry compat --baseline tests/foundry/fixtures/signature_baseline.json
"""
from __future__ import annotations

import argparse
import sys
from typing import Sequence


# ---------------------------------------------------------------------------
# Sub-command handlers
# ---------------------------------------------------------------------------

def _cmd_scaffold(args: argparse.Namespace) -> int:
    from polisyos.foundry.methods.cli.scaffold import MethodScaffold, ScaffoldConfig

    cfg = ScaffoldConfig(
        namespace=args.namespace,
        name=args.name,
        version=args.version,
        backend=args.backend,
        output_dir=args.output_dir,
        fidelity=args.fidelity,
        overwrite=args.overwrite,
    )
    scaffold = MethodScaffold(cfg)
    result = scaffold.generate()
    print(f"Generated: {result.method_file}")
    if result.boot_file:
        print(f"  + boot:  {result.boot_file}")
    if result.test_file:
        print(f"  + test:  {result.test_file}")
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    from polisyos.foundry.methods.cli.validator import MethodValidator

    validator = MethodValidator()
    if args.all:
        report = validator.validate_all()
    elif args.module and args.cls:
        report = validator.validate_module(args.module, args.cls)
    elif args.file:
        report = validator.validate_file(args.file, args.cls)
    else:
        print("Error: specify --all, --file, or --module + --class", file=sys.stderr)
        return 2

    for item in report.items:
        status = "OK" if item.passed else "FAIL"
        print(f"  [{status}] {item.fqn}: {item.message}")

    print(f"\n{report.passed}/{report.total} checks passed.")
    return 0 if report.all_passed else 1


def _cmd_catalog(args: argparse.Namespace) -> int:
    from polisyos.foundry.methods.registry import MethodRegistry
    from polisyos.foundry.methods.catalog import ensure_all_methods_registered  # noqa

    try:
        ensure_all_methods_registered()
    except (ImportError, Exception):
        pass

    registry = MethodRegistry.get_instance()
    sigs = list(registry.list_all())

    if args.namespace:
        sigs = [s for s in sigs if s.namespace == args.namespace]

    print(f"{'FQN':<60} {'FIDELITY':<8} {'BACKEND':<10} {'SLOTS_IN':<9} {'SLOTS_OUT'}")
    print("-" * 110)
    for sig in sorted(sigs, key=lambda s: s.fqn):
        print(
            f"{sig.fqn:<60} "
            f"{sig.fidelity.name:<8} "
            f"{sig.backend.value:<10} "
            f"{len(sig.input_slots):<9} "
            f"{len(sig.output_slots)}"
        )
    print(f"\nTotal: {len(sigs)} method(s)")
    return 0


def _cmd_compat(args: argparse.Namespace) -> int:
    import json
    from pathlib import Path
    from polisyos.foundry.methods.registry import MethodRegistry
    from polisyos.foundry.methods.catalog import ensure_all_methods_registered  # noqa

    try:
        ensure_all_methods_registered()
    except (ImportError, Exception):
        pass

    registry = MethodRegistry.get_instance()
    snapshot = registry.snapshot()

    baseline_path = Path(args.baseline)
    if not baseline_path.exists():
        print(f"Baseline not found: {baseline_path}", file=sys.stderr)
        return 2

    with baseline_path.open() as f:
        baseline: dict[str, str] = json.load(f).get("signatures", {})

    breaking: list[str] = []
    for fqn, old_hash in baseline.items():
        entry = snapshot._methods.get(fqn)
        if entry is None:
            breaking.append(f"REMOVED: {fqn}")
            continue
        try:
            current_hash = entry.signature.stable_digest()
        except Exception:
            current_hash = "<error>"
        if current_hash != old_hash:
            breaking.append(f"CHANGED: {fqn}\n  baseline: {old_hash}\n  current:  {current_hash}")

    if breaking:
        print(f"{len(breaking)} breaking change(s) detected:")
        for b in breaking:
            print(f"  {b}")
        return 1

    print("No breaking changes detected.")
    return 0


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="polisyos-foundry",
        description="Foundry Methods developer CLI",
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    # --- scaffold ---
    p_scaffold = sub.add_parser("scaffold", help="Generate a new method skeleton")
    p_scaffold.add_argument("--namespace", required=True, help="Method namespace (e.g. causal.did)")
    p_scaffold.add_argument("--name", required=True, help="Method name")
    p_scaffold.add_argument("--version", default="1.0.0", help="Initial version (default: 1.0.0)")
    p_scaffold.add_argument("--backend", default="numpy", choices=["numpy", "jax", "solver", "bayesian"])
    p_scaffold.add_argument("--fidelity", default="MEDIUM", choices=["LOW", "MEDIUM", "HIGH"])
    p_scaffold.add_argument("--output-dir", default=".", help="Target directory")
    p_scaffold.add_argument("--overwrite", action="store_true", help="Overwrite existing files")

    # --- validate ---
    p_validate = sub.add_parser("validate", help="Validate method(s)")
    p_validate.add_argument("--all", action="store_true", help="Validate all registered methods")
    p_validate.add_argument("--file", help="Path to Python file containing method class")
    p_validate.add_argument("--module", help="Module path (e.g. polisyos.foundry.methods.catalog.causal.rdd)")
    p_validate.add_argument("--class", dest="cls", help="Class name within module/file")

    # --- catalog ---
    p_catalog = sub.add_parser("catalog", help="Print the method catalog")
    p_catalog.add_argument("--namespace", help="Filter by namespace prefix")

    # --- compat ---
    p_compat = sub.add_parser("compat", help="Check for breaking signature changes")
    p_compat.add_argument(
        "--baseline",
        default="tests/foundry/fixtures/signature_baseline.json",
        help="Path to signature baseline JSON",
    )

    return parser


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main(argv: Sequence[str] | None = None) -> int:
    """Run the Foundry methods CLI and dispatch to the selected subcommand."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    handlers = {
        "scaffold": _cmd_scaffold,
        "validate": _cmd_validate,
        "catalog": _cmd_catalog,
        "compat": _cmd_compat,
    }

    handler = handlers.get(args.command)
    if handler is None:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        return 2

    try:
        return handler(args)
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
