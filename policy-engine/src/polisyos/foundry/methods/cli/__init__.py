"""
Foundry Methods CLI — ``polisyos-foundry`` entrypoint.

Subcommands
-----------
scaffold    Generate a new Foundry method skeleton.
validate    Validate a method class or an entire registry.
catalog     Print the catalog snapshot (FQNs, fidelity, backend).
capabilities Export machine-readable capability metadata.
advisor     Rank methods for a concrete problem framing.
evidence    Emit operator-facing applicability and replay evidence.
release-acceptance  Run the bundle-backed acceptance roundtrip.
compat      Check for breaking signature changes vs. a baseline.

Usage::

    polisyos-foundry --help
    polisyos-foundry scaffold --namespace causal.did --name my_estimator --version 1.0.0
    polisyos-foundry validate --all
    polisyos-foundry catalog --namespace causal
    polisyos-foundry release-acceptance --manifest-path bundle/release_manifest.json --runtime-bundle-dir bundle/runtime --method-contract-bundle-dir bundle/contracts --store-root .foundry-release-cas --json
    polisyos-foundry compat --baseline tests/unit/foundry/fixtures/signature_baseline.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict, is_dataclass
from pathlib import Path

_CLI_SOFT_FAILURES = (
    AttributeError,
    FileNotFoundError,
    ImportError,
    ModuleNotFoundError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)

# ---------------------------------------------------------------------------
# Sub-command handlers
# ---------------------------------------------------------------------------


def _json_ready(value):
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if is_dataclass(value):
        return _json_ready(asdict(value))
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    return str(value)


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
    from polisyos.foundry.methods.catalog import ensure_all_methods_registered
    from polisyos.foundry.methods.registry import MethodRegistry

    try:
        ensure_all_methods_registered()
    except _CLI_SOFT_FAILURES:
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

    from polisyos.foundry.methods.catalog import ensure_all_methods_registered
    from polisyos.foundry.methods.registry import MethodRegistry

    try:
        ensure_all_methods_registered()
    except _CLI_SOFT_FAILURES:
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
        except _CLI_SOFT_FAILURES:
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


def _load_catalog_snapshot():
    from polisyos.foundry.methods.catalog_snapshot import build_method_catalog_snapshot

    return build_method_catalog_snapshot(run_id="cli")


def _cmd_capabilities(args: argparse.Namespace) -> int:
    from polisyos.foundry.methods.catalog_snapshot import build_method_capability_matrix

    snapshot = _load_catalog_snapshot()
    rows = build_method_capability_matrix(snapshot, runnable_only=args.runnable_only)
    if args.namespace:
        rows = [row for row in rows if str(row["namespace"]).startswith(args.namespace)]
    if args.family:
        rows = [row for row in rows if str(row["family"]).startswith(args.family)]

    if args.json:
        print(
            json.dumps(
                {
                    "snapshot_id": snapshot.snapshot_id,
                    "method_count": len(rows),
                    "capability_matrix": rows,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    print(f"{'FQN':<60} {'RUNNABLE':<9} {'BACKEND':<10} {'DET_TIER':<22} {'TRUTHFULNESS'}")
    print("-" * 128)
    for row in rows:
        print(
            f"{row['fqn']!s:<60} "
            f"{row['runnable']!s:<9} "
            f"{row['execution_backend']!s:<10} "
            f"{row.get('determinism_tier') or '-'!s: <22} "
            f"{row['truthfulness_tier']!s}"
        )
    print(f"\nTotal: {len(rows)} method(s)")
    return 0


def _cmd_evidence(args: argparse.Namespace) -> int:
    from polisyos.foundry.methods.catalog_snapshot import build_method_operator_evidence

    snapshot = _load_catalog_snapshot()
    if args.namespace or args.family:
        filtered_entries = [
            entry
            for entry in snapshot.entries
            if (
                (not args.namespace or entry.namespace.startswith(args.namespace))
                and (not args.family or entry.family.startswith(args.family))
            )
        ]
        snapshot = snapshot.model_copy(update={"entries": filtered_entries})
    payload = build_method_operator_evidence(snapshot, runnable_only=args.runnable_only)

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    print(
        f"snapshot={payload['snapshot_id']} methods={payload['method_count']} "
        f"runnable={payload['runnable_count']} blocked={payload['blocked_count']}"
    )
    print("\nBackends:")
    for item in payload["backend_summary"]:
        print(
            f"  {item['value']}: total={item['count']} "
            f"runnable={item['runnable_count']} blocked={item['blocked_count']}"
        )
    print("\nReplay Contracts:")
    for item in payload["replay_contracts"]:
        print(f"  {item['determinism_tier']}: {item['replay_semantics']}")
    if payload["blocked_methods"]:
        print("\nBlocked Methods:")
        for item in payload["blocked_methods"]:
            reasons = ",".join(item["disabled_reasons"]) or "-"
            print(f"  {item['fqn']} [{item['execution_backend']}] -> {reasons}")
    return 0


def _cmd_release_acceptance(args: argparse.Namespace) -> int:
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.foundry.release_acceptance import ReleaseAcceptanceRunner

    store = FileSystemCAS(args.store_root)
    report = ReleaseAcceptanceRunner(store).run(
        release_manifest_path=args.manifest_path,
        runtime_bundle_dir=args.runtime_bundle_dir,
        method_contract_bundle_dir=args.method_contract_bundle_dir,
    )

    if args.json:
        print(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))
        return 0 if report.passed else 1

    print(
        f"passed={report.passed} manifest={report.manifest_path} "
        f"release_bundle_root={report.release_bundle_root}"
    )
    if report.governance_verdict:
        print(f"governance_verdict={report.governance_verdict}")
    if report.packet_ref:
        print(f"packet_ref={report.packet_ref}")
    print("\nSteps:")
    for step in report.steps:
        print(f"  {step.step_id}: {step.status}")
    if report.notes:
        print("\nNotes:")
        for note in report.notes:
            print(f"  {note}")
    return 0 if report.passed else 1


def _cmd_advisor(args: argparse.Namespace) -> int:
    from polisyos.foundry.methods.selection import (
        DataCharacteristics,
        MethodAdvisorQuery,
        MethodSelectionCriteria,
        advise_methods,
    )

    snapshot = _load_catalog_snapshot()
    criteria = MethodSelectionCriteria(
        preferred_kind=args.kind,
        preferred_family=args.family,
        preferred_variant=args.variant,
        family_prefixes=tuple(args.family_prefix or ()),
        preferred_execution_backends=tuple(args.backend or ()),
        required_data_modalities=tuple(args.required_modality or ()),
        preferred_data_modalities=tuple(args.preferred_modality or ()),
        preferred_determinism_tier=args.determinism_tier,
        minimum_fidelity_tier=args.minimum_fidelity_tier,
        runnable_only=not args.include_unrunnable,
    )
    data = DataCharacteristics(n_obs=args.n_obs) if args.n_obs is not None else None
    cost_budget: dict[str, float] | None = None
    if args.cost_budget_ms is not None or args.cost_budget_usd is not None:
        cost_budget = {}
        if args.cost_budget_ms is not None:
            cost_budget["max_total_ms"] = float(args.cost_budget_ms)
        if args.cost_budget_usd is not None:
            cost_budget["run_budget_usd"] = float(args.cost_budget_usd)
    query = MethodAdvisorQuery(
        criteria=criteria,
        data=data,
        runtime_budget_ms=args.runtime_budget_ms,
        limit=args.limit,
        runnable_only=not args.include_unrunnable,
        loss_profile_id=args.loss_profile_id,
        coverage_floor=args.coverage_floor,
        confidence_level=args.confidence_level,
        cost_policy=args.cost_policy,
        cost_budget=cost_budget,
        risk_delta=args.risk_delta,
        return_certificate=args.return_certificate,
        dominance_mode=args.dominance_mode,
        allow_heuristic_cost_estimate=not args.no_heuristic_cost_estimate,
        require_declared_accuracy_estimate=args.require_declared_accuracy_estimate,
    )
    result = advise_methods(snapshot, query)

    if args.json:
        print(
            json.dumps(
                {
                    "query": _json_ready(result.query),
                    "recommended": [entry.model_dump(mode="json") for entry in result.recommended],
                    "payload": list(result.payload),
                    "capability_matrix": list(result.capability_matrix),
                    "family_summary": list(result.family_summary),
                    "score_trace": [asdict(item) for item in result.score_trace],
                    "calibrated_regret_certificate": (
                        None
                        if result.calibrated_regret_certificate is None
                        else asdict(result.calibrated_regret_certificate)
                    ),
                    "cross_method_consensus": (
                        None
                        if result.cross_method_consensus is None
                        else asdict(result.cross_method_consensus)
                    ),
                    "advisor_optimization": _json_ready(result.advisor_optimization),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    print(f"{'FQN':<60} {'BACKEND':<10} {'FIDELITY':<8} {'DET_TIER':<22} {'TRUTHFULNESS'}")
    print("-" * 128)
    for entry in result.recommended:
        print(
            f"{entry.fqn:<60} "
            f"{entry.execution_backend:<10} "
            f"{entry.fidelity_tier:<8} "
            f"{entry.determinism_tier or '-'!s: <22} "
            f"{entry.truthfulness_tier}"
        )
    print(f"\nRecommended: {len(result.recommended)} method(s)")
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
    p_scaffold.add_argument(
        "--backend", default="numpy", choices=["numpy", "jax", "solver", "bayesian"]
    )
    p_scaffold.add_argument("--fidelity", default="MEDIUM", choices=["LOW", "MEDIUM", "HIGH"])
    p_scaffold.add_argument("--output-dir", default=".", help="Target directory")
    p_scaffold.add_argument("--overwrite", action="store_true", help="Overwrite existing files")

    # --- validate ---
    p_validate = sub.add_parser("validate", help="Validate method(s)")
    p_validate.add_argument("--all", action="store_true", help="Validate all registered methods")
    p_validate.add_argument("--file", help="Path to Python file containing method class")
    p_validate.add_argument(
        "--module", help="Module path (e.g. polisyos.foundry.methods.catalog.causal.rdd)"
    )
    p_validate.add_argument("--class", dest="cls", help="Class name within module/file")

    # --- catalog ---
    p_catalog = sub.add_parser("catalog", help="Print the method catalog")
    p_catalog.add_argument("--namespace", help="Filter by namespace prefix")

    # --- compat ---
    p_compat = sub.add_parser("compat", help="Check for breaking signature changes")
    p_compat.add_argument(
        "--baseline",
        default="tests/unit/foundry/fixtures/signature_baseline.json",
        help="Path to signature baseline JSON",
    )

    # --- capabilities ---
    p_capabilities = sub.add_parser(
        "capabilities", help="Export machine-readable capability metadata"
    )
    p_capabilities.add_argument("--namespace", help="Filter by namespace prefix")
    p_capabilities.add_argument("--family", help="Filter by family prefix")
    p_capabilities.add_argument(
        "--runnable-only", action="store_true", help="Only emit runnable methods"
    )
    p_capabilities.add_argument("--json", action="store_true", help="Emit JSON instead of a table")

    # --- evidence ---
    p_evidence = sub.add_parser(
        "evidence", help="Export operator-facing applicability and replay evidence"
    )
    p_evidence.add_argument("--namespace", help="Filter by namespace prefix")
    p_evidence.add_argument("--family", help="Filter by family prefix")
    p_evidence.add_argument(
        "--runnable-only", action="store_true", help="Only emit runnable methods"
    )
    p_evidence.add_argument("--json", action="store_true", help="Emit JSON instead of a table")

    # --- release-acceptance ---
    p_release_acceptance = sub.add_parser(
        "release-acceptance",
        help="Run the bundle-backed Foundry release acceptance roundtrip",
    )
    p_release_acceptance.add_argument(
        "--manifest-path",
        type=Path,
        required=True,
        help="Release manifest JSON path",
    )
    p_release_acceptance.add_argument(
        "--runtime-bundle-dir",
        type=Path,
        required=True,
        help="Directory containing runtime parquet bundle files",
    )
    p_release_acceptance.add_argument(
        "--method-contract-bundle-dir",
        type=Path,
        required=True,
        help="Directory containing acceptance contract bundle JSON",
    )
    p_release_acceptance.add_argument(
        "--store-root",
        type=Path,
        required=True,
        help="Writable CAS root for the acceptance run",
    )
    p_release_acceptance.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of a text summary",
    )

    # --- advisor ---
    p_advisor = sub.add_parser("advisor", help="Recommend methods for a concrete problem framing")
    p_advisor.add_argument("--kind", help="Preferred method kind")
    p_advisor.add_argument("--family", help="Preferred family")
    p_advisor.add_argument("--variant", help="Preferred variant")
    p_advisor.add_argument(
        "--family-prefix", action="append", help="Additional acceptable family prefix"
    )
    p_advisor.add_argument("--backend", action="append", help="Preferred execution backend")
    p_advisor.add_argument("--required-modality", action="append", help="Required data modality")
    p_advisor.add_argument("--preferred-modality", action="append", help="Preferred data modality")
    p_advisor.add_argument("--determinism-tier", help="Preferred determinism tier")
    p_advisor.add_argument("--minimum-fidelity-tier", choices=["low", "medium", "high"])
    p_advisor.add_argument("--n-obs", type=int, help="Observation count available to the method")
    p_advisor.add_argument("--runtime-budget-ms", type=float, help="Runtime budget in milliseconds")
    p_advisor.add_argument(
        "--cost-policy",
        default="ignore",
        choices=["ignore", "annotate", "filter", "pareto"],
        help="Optional cost-aware advisor mode",
    )
    p_advisor.add_argument(
        "--cost-budget-ms",
        type=float,
        help="Hard method budget in milliseconds for cost-aware modes",
    )
    p_advisor.add_argument(
        "--cost-budget-usd",
        type=float,
        help="Hard method budget in USD for cost-aware modes",
    )
    p_advisor.add_argument(
        "--risk-delta",
        type=float,
        default=0.05,
        help="Tail probability used for cost upper bounds",
    )
    p_advisor.add_argument(
        "--dominance-mode",
        default="point",
        choices=["point", "robust"],
        help="Pareto dominance relation for cost-aware modes",
    )
    p_advisor.add_argument(
        "--no-heuristic-cost-estimate",
        action="store_true",
        help="Require declared catalog cost estimates instead of heuristic fallback",
    )
    p_advisor.add_argument(
        "--require-declared-accuracy-estimate",
        action="store_true",
        help="Require declared catalog accuracy estimates for cost-value selection",
    )
    p_advisor.add_argument(
        "--return-certificate",
        action="store_true",
        help="Include a budget certificate for annotate mode",
    )
    p_advisor.add_argument(
        "--loss-profile-id",
        default="balanced",
        choices=["balanced", "coverage_strict", "latency_sensitive"],
        help="Decision-theoretic loss profile used by the regret certificate",
    )
    p_advisor.add_argument(
        "--coverage-floor",
        type=float,
        help="Optional downstream coverage floor used in proxy loss normalization",
    )
    p_advisor.add_argument(
        "--confidence-level",
        type=float,
        default=0.95,
        help="Confidence level for calibrated regret diagnostics",
    )
    p_advisor.add_argument(
        "--limit", type=int, default=5, help="Maximum number of methods to return"
    )
    p_advisor.add_argument(
        "--include-unrunnable", action="store_true", help="Include unrunnable methods"
    )
    p_advisor.add_argument("--json", action="store_true", help="Emit JSON instead of a table")

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
        "capabilities": _cmd_capabilities,
        "evidence": _cmd_evidence,
        "release-acceptance": _cmd_release_acceptance,
        "advisor": _cmd_advisor,
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
    except _CLI_SOFT_FAILURES as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
