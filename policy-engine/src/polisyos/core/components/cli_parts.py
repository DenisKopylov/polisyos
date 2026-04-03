"""CLI facade assembled from focused sub-modules."""

from __future__ import annotations

import argparse
import importlib
import sys
from importlib.metadata import PackageNotFoundError, version
from datetime import datetime, timezone

from polisyos.core.artifacts.signing import (
    DEFAULT_IDENTITIES_PATH,
    DEFAULT_REVOKED_DIR,
    DEFAULT_TRUST_DIR,
)
from polisyos.core.components import ComponentKind


def main(argv: list[str] | None = None) -> int:
    """Main helper."""
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--version" in argv:
        print(f"polisyos {_cli_version()}")
        return 0

    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "components" and args.components_command == "list":
        from ._cli_components import _cmd_components_list

        return _cmd_components_list(args)
    if args.command == "components" and args.components_command == "bootstrap":
        from ._cli_components import _cmd_components_bootstrap

        return _cmd_components_bootstrap(args)
    if args.command == "registry" and args.registry_command == "build":
        from ._cli_components import _cmd_registry_build

        return _cmd_registry_build(args)
    if args.command == "scholar" and args.scholar_command == "enrich":
        from ._cli_scholar import _cmd_scholar_enrich

        return _cmd_scholar_enrich(args)
    if args.command == "lex" and args.lex_command == "normpack" and args.lex_normpack_command == "build":
        from ._cli_lex import _cmd_lex_normpack_build

        return _cmd_lex_normpack_build(args)
    if args.command == "lex" and args.lex_command == "impact":
        from ._cli_lex import _cmd_lex_impact

        return _cmd_lex_impact(args)
    if (
        args.command == "scientist"
        and args.scientist_command == "burn-in"
    ):
        from ._cli_scientist import _cmd_scientist_burn_in

        return _cmd_scientist_burn_in(args)
    if (
        args.command == "scientist"
        and args.scientist_command == "calibration-report"
    ):
        from ._cli_scientist import _cmd_scientist_calibration_report

        return _cmd_scientist_calibration_report(args)
    if (
        args.command == "scientist"
        and args.scientist_command == "sensitivity"
        and args.scientist_sensitivity_command == "run"
    ):
        from ._cli_scientist import _cmd_scientist_sensitivity_run

        return _cmd_scientist_sensitivity_run(args)
    if args.command == "scientist" and args.scientist_command == "stress-test":
        from ._cli_scientist import _cmd_scientist_stress_test

        return _cmd_scientist_stress_test(args)
    if args.command == "scientist" and args.scientist_command == "backtest":
        from ._cli_scientist import _cmd_scientist_backtest

        return _cmd_scientist_backtest(args)
    if args.command == "replay":
        from ._cli_replay import _cmd_replay

        return _cmd_replay(args)
    if args.command == "resume":
        from ._cli_replay import _cmd_resume

        return _cmd_resume(args)
    if args.command == "keygen":
        from ._cli_crypto import _cmd_keygen

        return _cmd_keygen(args)
    if args.command == "sign":
        from ._cli_crypto import _cmd_sign

        return _cmd_sign(args)
    if args.command == "verify":
        from ._cli_crypto import _cmd_verify

        return _cmd_verify(args)
    if args.command == "audit" and args.audit_command == "export":
        from ._cli_audit import _cmd_audit_export

        return _cmd_audit_export(args)
    if args.command == "audit" and args.audit_command == "verify":
        from ._cli_audit import _cmd_audit_verify

        return _cmd_audit_verify(args)

    parser.print_help()
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="polisyos")
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {_cli_version()}",
    )

    components = parser.add_subparsers(dest="command")

    cmd_components = components.add_parser("components")
    components_sub = cmd_components.add_subparsers(dest="components_command")
    list_parser = components_sub.add_parser("list")
    list_parser.add_argument("--kind", choices=[kind.value for kind in ComponentKind], default=None)
    list_parser.add_argument("--domain", default=None)
    list_parser.add_argument("--jurisdiction", default=None)
    list_parser.add_argument("--tag", default=None)
    list_parser.add_argument("--json", action="store_true")
    list_parser.add_argument("--dev-scan-path", action="append", default=[])

    bootstrap_parser = components_sub.add_parser("bootstrap")
    bootstrap_parser.add_argument("--group", action="append", default=[])
    bootstrap_parser.add_argument("--dev-scan-path", action="append", default=[])
    bootstrap_parser.add_argument("--no-dev-scan", action="store_true")
    bootstrap_parser.add_argument("--skip-connectors", action="store_true")
    bootstrap_parser.add_argument("--skip-methods", action="store_true")
    bootstrap_parser.add_argument("--skip-evaluators", action="store_true")
    bootstrap_parser.add_argument("--skip-extractors", action="store_true")
    bootstrap_parser.add_argument("--skip-providers", action="store_true")
    bootstrap_parser.add_argument("--skip-nodes", action="store_true")
    bootstrap_parser.add_argument("--json", action="store_true")

    cmd_registry = components.add_parser("registry")
    registry_sub = cmd_registry.add_subparsers(dest="registry_command")
    build_registry = registry_sub.add_parser("build")
    build_registry.add_argument("--domain", required=True)
    build_registry.add_argument("--jurisdiction", default=None)
    build_registry.add_argument("--cas-root", default=".polisyos/cas")
    build_registry.add_argument("--dev-scan-path", action="append", default=[])

    cmd_scholar = components.add_parser("scholar")
    scholar_sub = cmd_scholar.add_subparsers(dest="scholar_command")
    enrich = scholar_sub.add_parser("enrich")
    enrich.add_argument("--intent", required=True)
    enrich.add_argument("--cas-root", default=".polisyos/cas")
    enrich.add_argument("--fact-log-root", default=".polisyos/facts")

    cmd_lex = components.add_parser("lex")
    lex_sub = cmd_lex.add_subparsers(dest="lex_command")
    normpack = lex_sub.add_parser("normpack")
    normpack_sub = normpack.add_subparsers(dest="lex_normpack_command")
    build_normpack = normpack_sub.add_parser("build")
    build_normpack.add_argument("--jurisdiction", required=True)
    build_normpack.add_argument("--domain", default=None)
    build_normpack.add_argument("--as-of", default=datetime.now(timezone.utc).date().isoformat())
    build_normpack.add_argument("--cas-root", default=".polisyos/cas")
    build_normpack.add_argument("--fact-log-root", default=".polisyos/facts")

    impact = lex_sub.add_parser("impact")
    impact.add_argument("old_ref", help="Old NormPack artifact id or JSON file path")
    impact.add_argument("new_ref", help="New NormPack artifact id or JSON file path")
    impact.add_argument("--passes", default="legal,safety")
    impact.add_argument("--profile", choices=["fast", "mvp", "strict"], default="strict")
    impact.add_argument("--format", choices=["json", "md"], default="md")
    impact.add_argument("--output", default=None)
    impact.add_argument("--cas-root", default=".polisyos")

    cmd_scientist = components.add_parser("scientist")
    scientist_sub = cmd_scientist.add_subparsers(dest="scientist_command")

    burn_in = scientist_sub.add_parser("burn-in")
    burn_in.add_argument("--config", required=True, help="JSON config path")
    burn_in.add_argument("--output", default=None)
    burn_in.add_argument("--format", choices=["json"], default="json")
    burn_in.add_argument("--cas-root", default=".polisyos")

    calibration_report = scientist_sub.add_parser("calibration-report")
    calibration_report.add_argument("--config", required=True, help="JSON config path")
    calibration_report.add_argument("--output", default=None)
    calibration_report.add_argument("--format", choices=["json", "md"], default="md")
    calibration_report.add_argument("--cas-root", default=".polisyos")

    sensitivity = scientist_sub.add_parser("sensitivity")
    sensitivity_sub = sensitivity.add_subparsers(dest="scientist_sensitivity_command")
    sensitivity_run = sensitivity_sub.add_parser("run")
    sensitivity_run.add_argument("--config", required=True, help="JSON config path")
    sensitivity_run.add_argument("--output", default=None)
    sensitivity_run.add_argument("--format", choices=["json"], default="json")
    sensitivity_run.add_argument("--cas-root", default=".polisyos")

    stress_test = scientist_sub.add_parser("stress-test")
    stress_test.add_argument("--config", required=True, help="JSON config path")
    stress_test.add_argument("--output", default=None)
    stress_test.add_argument("--format", choices=["json"], default="json")
    stress_test.add_argument("--cas-root", default=".polisyos")

    backtesting_cli = importlib.import_module("polisyos.scientist.backtesting.cli")
    backtesting_cli.add_backtest_subparser(scientist_sub)

    cmd_replay = components.add_parser("replay")
    cmd_replay.add_argument("packet_ref", help="DecisionPacket ref (sha256:<hex> or <hex>)")
    cmd_replay.add_argument("--cas-root", default=".polisyos", help="CAS root directory")
    cmd_replay.add_argument(
        "--mode",
        choices=["bit_exact", "ci_bounded", "skip"],
        default="bit_exact",
        help="Verification mode",
    )
    cmd_replay.add_argument(
        "--strategy",
        choices=["auto", "foundry", "scientist"],
        default="auto",
        help="Replay execution strategy",
    )
    cmd_replay.add_argument(
        "--check-only",
        action="store_true",
        help="Only run dependency completeness checks",
    )
    cmd_replay.add_argument(
        "--export",
        default=None,
        metavar="PATH",
        help="Export replay subgraph to tar.gz archive",
    )
    cmd_replay.add_argument(
        "--bundle",
        default=None,
        metavar="PATH",
        help="Import replay bundle from archive/directory and run against it",
    )
    cmd_replay.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip verification after replay execution",
    )
    cmd_replay.add_argument(
        "--tolerance",
        type=float,
        default=1e-6,
        help="Relative tolerance for ci_bounded mode",
    )
    cmd_replay.add_argument(
        "--confidence-level",
        type=float,
        default=0.95,
        help="Confidence level for ci_bounded reports",
    )
    cmd_replay.add_argument("--json", action="store_true")

    cmd_resume = components.add_parser("resume")
    cmd_resume.add_argument("run_id", help="Run ID to resume (e.g. R_abc123)")
    cmd_resume.add_argument("--cas-root", default=".polisyos", help="CAS root directory")
    cmd_resume.add_argument(
        "--checkpoint-policy",
        choices=["off", "strict", "best_effort"],
        default="strict",
        help="Checkpoint persistence policy during resumed execution",
    )
    cmd_resume.add_argument(
        "--force",
        action="store_true",
        help="Attempt resume even if run lock metadata suggests another holder",
    )
    cmd_resume.add_argument("--dry-run", action="store_true", help="Only inspect checkpoint metadata")
    cmd_resume.add_argument("--json", action="store_true")

    cmd_keygen = components.add_parser("keygen")
    cmd_keygen.add_argument(
        "--output",
        default="~/.polisyos/keys/polisyos-signing",
        help="Base output path (without extension). Writes .pem and .pub files.",
    )
    cmd_keygen.add_argument("--name", default=None, help="Signer identity label")
    cmd_keygen.add_argument("--force", action="store_true", help="Overwrite existing key files")
    cmd_keygen.add_argument(
        "--public-only",
        action="store_true",
        help="Print generated public key to stdout without writing files",
    )
    cmd_keygen.add_argument("--json", action="store_true")

    cmd_sign = components.add_parser("sign")
    cmd_sign.add_argument("artifact_ref", nargs="?", help="Artifact ref (sha256:<hex> or <hex>)")
    cmd_sign.add_argument("--all", action="store_true", help="Sign all artifacts in CAS")
    cmd_sign.add_argument("--cas-root", default=".polisyos", help="CAS root directory")
    cmd_sign.add_argument("--key", default=None, help="Path to private Ed25519 key (PEM)")
    cmd_sign.add_argument("--identity", default=None, help="Signer identity hint")
    cmd_sign.add_argument("--workers", type=int, default=8, help="Workers for --all")
    cmd_sign.add_argument(
        "--resign",
        action="store_true",
        help="Re-sign already signed artifacts when used with --all",
    )
    cmd_sign.add_argument("--json", action="store_true")

    cmd_verify = components.add_parser("verify")
    cmd_verify.add_argument("artifact_ref", nargs="?", help="Artifact ref (sha256:<hex> or <hex>)")
    cmd_verify.add_argument("--all", action="store_true", help="Verify all artifacts in CAS")
    cmd_verify.add_argument("--cas-root", default=".polisyos", help="CAS root directory")
    cmd_verify.add_argument(
        "--public-key",
        action="append",
        default=[],
        help="Explicit trusted public key PEM path (repeatable)",
    )
    cmd_verify.add_argument(
        "--trust-dir",
        default=str(DEFAULT_TRUST_DIR),
        help="Directory containing trusted public keys (*.pub)",
    )
    cmd_verify.add_argument(
        "--revoked-dir",
        default=str(DEFAULT_REVOKED_DIR),
        help="Directory containing revoked public keys (*.pub)",
    )
    cmd_verify.add_argument(
        "--identities",
        default=str(DEFAULT_IDENTITIES_PATH),
        help="JSON mapping key_id->identity for identity binding checks",
    )
    cmd_verify.add_argument("--workers", type=int, default=8, help="Workers for --all")
    cmd_verify.add_argument("--json", action="store_true")
    cmd_verify.add_argument("--quiet", action="store_true")
    cmd_verify.add_argument("--fail-unsigned", action="store_true")
    cmd_verify.add_argument("--strict-identity", action="store_true")

    cmd_audit = components.add_parser("audit")
    audit_sub = cmd_audit.add_subparsers(dest="audit_command")

    audit_export = audit_sub.add_parser("export")
    audit_export.add_argument("run_id")
    audit_export.add_argument("--cas-root", default=".polisyos", help="CAS root directory")
    audit_export.add_argument(
        "--runs-dir",
        default=".polisyos/runs",
        help="Run manifests directory",
    )
    audit_export.add_argument("--output", "-o", default=None, help="Output archive path")
    audit_export.add_argument(
        "--profile",
        choices=["full", "manifests_only"],
        default="full",
        help="Export profile",
    )
    audit_export.add_argument(
        "--exclude-kinds",
        default="",
        help="Comma-separated artifact kinds to exclude",
    )
    audit_export.add_argument(
        "--signing-policy",
        choices=["strict", "warn", "skip"],
        default="warn",
    )
    audit_export.add_argument(
        "--slsa-mode",
        choices=["off", "local", "private", "public"],
        default=None,
        help="SLSA mode override (default comes from environment)",
    )
    audit_export.add_argument(
        "--slsa-policy",
        choices=["best_effort", "required"],
        default=None,
        help="SLSA policy override (default comes from environment)",
    )
    audit_export.add_argument(
        "--no-visualization",
        action="store_true",
    )
    audit_export.add_argument("--json", action="store_true")

    audit_verify = audit_sub.add_parser("verify")
    audit_verify.add_argument("package", help="Path to audit package file or directory")
    audit_verify.add_argument(
        "--trusted-key",
        action="append",
        default=[],
        help="Trusted public key path (repeatable)",
    )
    audit_verify.add_argument(
        "--trusted-keys-dir",
        default=None,
        help="Directory with trusted PEM keys",
    )
    audit_verify.add_argument(
        "--allow-package-keys",
        action="store_true",
        help="Treat package keys as trusted (not recommended)",
    )
    audit_verify.add_argument(
        "--fail-unsigned",
        action="store_true",
        help="Fail verification when unsigned artifacts are present",
    )
    audit_verify.add_argument(
        "--require-slsa",
        action="store_true",
        help="Fail verification if SLSA evidence is missing or invalid",
    )
    audit_verify.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
        help="Report format",
    )
    audit_verify.add_argument("--output", "-o", default=None, help="Report output path")
    audit_verify.add_argument("--json", action="store_true")

    return parser


def _cli_version() -> str:
    try:
        return version("policy-engine")
    except PackageNotFoundError:
        return "0+unknown"


__all__ = ["main"]


if __name__ == "__main__":  # pragma: no cover - CLI execution path
    raise SystemExit(main())
