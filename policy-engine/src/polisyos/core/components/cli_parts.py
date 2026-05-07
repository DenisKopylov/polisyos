"""CLI facade assembled from focused sub-modules."""

from __future__ import annotations

import argparse
import importlib
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from typing import cast

from polisyos.core.artifacts.signing import (
    DEFAULT_IDENTITIES_PATH,
    DEFAULT_REVOKED_DIR,
    DEFAULT_TRUST_DIR,
)
from polisyos.core.components import ComponentKind
from polisyos.core.security.rotation import DEFAULT_JWT_TRUST_ANCHORS_PATH

CommandHandler = Callable[[argparse.Namespace], int]


def _dispatch_private(relative_module: str, handler_name: str, args: argparse.Namespace) -> int:
    module = importlib.import_module(relative_module, package=__package__)
    handler = cast("CommandHandler", getattr(module, handler_name))
    return handler(args)


def main(argv: list[str] | None = None) -> int:
    """Dispatch the `polisyos` console script and return a process exit code.

    Command handlers are imported lazily after argument parsing so importing
    `polisyos.core.components.cli_parts` is safe in docs/tests that only need
    parser metadata. `--version` exits early without loading subcommand modules.
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--version" in argv:
        sys.stdout.write(f"polisyos {_cli_version()}\n")
        return 0

    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "components" and args.components_command == "list":
        return _dispatch_private("._cli_components", "_cmd_components_list", args)
    if args.command == "components" and args.components_command == "bootstrap":
        return _dispatch_private("._cli_components", "_cmd_components_bootstrap", args)
    if args.command == "registry" and args.registry_command == "build":
        return _dispatch_private("._cli_components", "_cmd_registry_build", args)
    if args.command == "scholar" and args.scholar_command == "enrich":
        return _dispatch_private("._cli_scholar", "_cmd_scholar_enrich", args)
    if args.command == "metric-validate":
        return _dispatch_private("._cli_metric_validation", "_cmd_metric_validate", args)
    if (
        args.command == "lex"
        and args.lex_command == "normpack"
        and args.lex_normpack_command == "build"
    ):
        return _dispatch_private("._cli_lex", "_cmd_lex_normpack_build", args)
    if args.command == "lex" and args.lex_command == "impact":
        return _dispatch_private("._cli_lex", "_cmd_lex_impact", args)
    if args.command == "scientist" and args.scientist_command == "burn-in":
        return _dispatch_private("._cli_scientist", "_cmd_scientist_burn_in", args)
    if args.command == "scientist" and args.scientist_command == "calibration-report":
        return _dispatch_private("._cli_scientist", "_cmd_scientist_calibration_report", args)
    if (
        args.command == "scientist"
        and args.scientist_command == "sensitivity"
        and args.scientist_sensitivity_command == "run"
    ):
        return _dispatch_private("._cli_scientist", "_cmd_scientist_sensitivity_run", args)
    if args.command == "scientist" and args.scientist_command == "stress-test":
        return _dispatch_private("._cli_scientist", "_cmd_scientist_stress_test", args)
    if args.command == "scientist" and args.scientist_command == "provider-verify":
        return _dispatch_private("._cli_scientist", "_cmd_scientist_provider_verify", args)
    if args.command == "scientist" and args.scientist_command == "agent-smoke":
        return _dispatch_private("._cli_scientist", "_cmd_scientist_agent_smoke", args)
    if args.command == "scientist" and args.scientist_command == "agent-eval":
        return _dispatch_private("._cli_scientist", "_cmd_scientist_agent_eval", args)
    if args.command == "scientist" and args.scientist_command == "reflexion-replay-eval":
        return _dispatch_private("._cli_scientist", "_cmd_scientist_reflexion_replay_eval", args)
    if args.command == "scientist" and args.scientist_command == "backtest":
        return _dispatch_private("._cli_scientist", "_cmd_scientist_backtest", args)
    if args.command == "replay":
        return _dispatch_private("._cli_replay", "_cmd_replay", args)
    if args.command == "resume":
        return _dispatch_private("._cli_replay", "_cmd_resume", args)
    if args.command == "keygen":
        return _dispatch_private("._cli_crypto", "_cmd_keygen", args)
    if args.command == "sign":
        return _dispatch_private("._cli_crypto", "_cmd_sign", args)
    if args.command == "verify":
        return _dispatch_private("._cli_crypto", "_cmd_verify", args)
    if args.command == "audit" and args.audit_command == "export":
        return _dispatch_private("._cli_audit", "_cmd_audit_export", args)
    if args.command == "audit" and args.audit_command == "verify":
        return _dispatch_private("._cli_audit", "_cmd_audit_verify", args)
    if args.command == "audit" and args.audit_command == "runtime-query":
        return _dispatch_private("._cli_audit", "_cmd_audit_runtime_query", args)
    if args.command == "audit" and args.audit_command == "runtime-retention":
        return _dispatch_private("._cli_audit", "_cmd_audit_runtime_retention", args)
    if args.command == "security" and args.security_command == "rotate-jwt":
        return _dispatch_private("._cli_security", "_cmd_security_rotate_jwt", args)
    if args.command == "security" and args.security_command == "rotate-ed25519":
        return _dispatch_private("._cli_security", "_cmd_security_rotate_ed25519", args)

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

    metric_validate = components.add_parser("metric-validate")
    metric_validate.add_argument(
        "--observation-bundle-ref",
        required=True,
        help="Observation bundle artifact id (sha256:<hex> or <hex>)",
    )
    metric_validate.add_argument("--baseline", required=True, help="Baseline model id")
    metric_validate.add_argument(
        "--candidates",
        nargs="+",
        required=True,
        help="Candidate model ids to compare against the baseline",
    )
    metric_validate.add_argument(
        "--metrics",
        nargs="+",
        required=True,
        help="Metric ids to validate (e.g. roc_auc accuracy log_loss f1)",
    )
    metric_validate.add_argument("--alpha", type=float, default=0.05)
    metric_validate.add_argument(
        "--alternative",
        choices=["two-sided", "greater", "less"],
        default="two-sided",
    )
    metric_validate.add_argument("--n-resamples", type=int, default=20_000)
    metric_validate.add_argument("--confidence-level", type=float, default=0.95)
    metric_validate.add_argument(
        "--correction",
        choices=[
            "none",
            "bonferroni",
            "holm",
            "bh",
            "by",
            "westfall_young_maxT",
            "westfall_young_minP",
        ],
        default="holm",
    )
    metric_validate.add_argument(
        "--family-scope",
        choices=["per_candidate", "per_metric", "all_pairs_all_metrics"],
        default="all_pairs_all_metrics",
    )
    metric_validate.add_argument("--random-seed", type=int, default=None)
    metric_validate.add_argument("--exact-if-feasible", action="store_true", default=True)
    metric_validate.add_argument(
        "--format",
        choices=["summary-json", "json", "avro-json", "proto-json"],
        default="summary-json",
    )
    metric_validate.add_argument("--output", default=None)
    metric_validate.add_argument("--cas-root", default=".polisyos/cas")

    cmd_lex = components.add_parser("lex")
    lex_sub = cmd_lex.add_subparsers(dest="lex_command")
    normpack = lex_sub.add_parser("normpack")
    normpack_sub = normpack.add_subparsers(dest="lex_normpack_command")
    build_normpack = normpack_sub.add_parser("build")
    build_normpack.add_argument("--jurisdiction", required=True)
    build_normpack.add_argument("--domain", default=None)
    build_normpack.add_argument("--as-of", default=datetime.now(UTC).date().isoformat())
    build_normpack.add_argument("--cas-root", default=".polisyos/cas")
    build_normpack.add_argument("--fact-log-root", default=".polisyos/facts")

    impact = lex_sub.add_parser("impact")
    impact.add_argument("old_ref", help="Old NormPack artifact id or JSON file path")
    impact.add_argument("new_ref", help="New NormPack artifact id or JSON file path")
    impact.add_argument("--passes", default="legal,safety")
    impact.add_argument("--profile", choices=["fast", "mvp", "strict"], default="strict")
    impact.add_argument("--format", choices=["json", "md"], default="md")
    impact.add_argument("--output", default=None)
    impact.add_argument("--cas-root", default=".polisyos/cas")

    cmd_scientist = components.add_parser("scientist")
    scientist_sub = cmd_scientist.add_subparsers(dest="scientist_command")

    burn_in = scientist_sub.add_parser("burn-in")
    burn_in.add_argument("--config", required=True, help="JSON config path")
    burn_in.add_argument("--output", default=None)
    burn_in.add_argument("--format", choices=["json"], default="json")
    burn_in.add_argument("--cas-root", default=".polisyos/cas")

    calibration_report = scientist_sub.add_parser("calibration-report")
    calibration_report.add_argument("--config", required=True, help="JSON config path")
    calibration_report.add_argument("--output", default=None)
    calibration_report.add_argument("--format", choices=["json", "md"], default="md")
    calibration_report.add_argument("--cas-root", default=".polisyos/cas")

    sensitivity = scientist_sub.add_parser("sensitivity")
    sensitivity_sub = sensitivity.add_subparsers(dest="scientist_sensitivity_command")
    sensitivity_run = sensitivity_sub.add_parser("run")
    sensitivity_run.add_argument("--config", required=True, help="JSON config path")
    sensitivity_run.add_argument("--output", default=None)
    sensitivity_run.add_argument("--format", choices=["json"], default="json")
    sensitivity_run.add_argument("--cas-root", default=".polisyos/cas")

    stress_test = scientist_sub.add_parser("stress-test")
    stress_test.add_argument("--config", required=True, help="JSON config path")
    stress_test.add_argument("--output", default=None)
    stress_test.add_argument("--format", choices=["json"], default="json")
    stress_test.add_argument("--cas-root", default=".polisyos/cas")

    provider_verify = scientist_sub.add_parser("provider-verify")
    provider_verify.add_argument(
        "--model-id",
        default="qwen/qwen3-235b-a22b-instruct-2507-fp8",
    )
    provider_verify.add_argument(
        "--base-url",
        default="https://api.gonkagate.com/v1",
    )
    provider_verify.add_argument(
        "--verification-dir",
        default=".polisyos/provider_verification",
    )
    provider_verify.add_argument("--no-web-search", action="store_true")
    provider_verify.add_argument("--output", default=None)
    provider_verify.add_argument("--format", choices=["json"], default="json")

    agent_smoke = scientist_sub.add_parser("agent-smoke")
    agent_smoke.add_argument(
        "--model-id",
        default="qwen/qwen3-235b-a22b-instruct-2507-fp8",
    )
    agent_smoke.add_argument(
        "--base-url",
        default="https://api.gonkagate.com/v1",
    )
    agent_smoke.add_argument(
        "--verification-dir",
        default=".polisyos/provider_verification",
    )
    agent_smoke.add_argument("--no-web-search", action="store_true")
    agent_smoke.add_argument("--output", default=None)
    agent_smoke.add_argument("--format", choices=["json"], default="json")

    agent_eval = scientist_sub.add_parser("agent-eval")
    agent_eval.add_argument("--cas-root", default=".polisyos/cas")
    agent_eval.add_argument(
        "--model-id",
        default="qwen/qwen3-235b-a22b-instruct-2507-fp8",
    )
    agent_eval.add_argument(
        "--base-url",
        default="https://api.gonkagate.com/v1",
    )
    agent_eval.add_argument(
        "--verification-dir",
        default=".polisyos/provider_verification",
    )
    agent_eval.add_argument("--live-provider", action="store_true")
    agent_eval.add_argument("--output", default=None)
    agent_eval.add_argument("--format", choices=["json"], default="json")

    reflexion_replay_eval = scientist_sub.add_parser("reflexion-replay-eval")
    reflexion_replay_eval.add_argument("--input", required=True, help="JSON file with replay cases")
    reflexion_replay_eval.add_argument("--output", default=None)
    reflexion_replay_eval.add_argument("--format", choices=["json"], default="json")

    backtesting_cli = importlib.import_module("polisyos.scientist.backtesting.cli")
    backtesting_cli.add_backtest_subparser(scientist_sub)

    cmd_replay = components.add_parser("replay")
    cmd_replay.add_argument("packet_ref", help="DecisionPacket ref (sha256:<hex> or <hex>)")
    cmd_replay.add_argument("--cas-root", default=".polisyos/cas", help="CAS root directory")
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
    cmd_resume.add_argument("--cas-root", default=".polisyos/cas", help="CAS root directory")
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
    cmd_resume.add_argument(
        "--dry-run", action="store_true", help="Only inspect checkpoint metadata"
    )
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
    cmd_sign.add_argument("--cas-root", default=".polisyos/cas", help="CAS root directory")
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
    cmd_verify.add_argument("--cas-root", default=".polisyos/cas", help="CAS root directory")
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
    audit_export.add_argument("--cas-root", default=".polisyos/cas", help="CAS root directory")
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

    audit_runtime_query = audit_sub.add_parser("runtime-query")
    audit_runtime_query.add_argument("--cas-root", default=".polisyos/cas")
    audit_runtime_query.add_argument(
        "--stream",
        choices=["access", "mutation", "all"],
        default="all",
    )
    audit_runtime_query.add_argument("--tenant-id", default=None)
    audit_runtime_query.add_argument("--actor", default=None)
    audit_runtime_query.add_argument("--resource-id", default=None)
    audit_runtime_query.add_argument("--endpoint", default=None)
    audit_runtime_query.add_argument("--operation", default=None)
    audit_runtime_query.add_argument("--outcome", default=None)
    audit_runtime_query.add_argument("--since", default=None)
    audit_runtime_query.add_argument("--until", default=None)
    audit_runtime_query.add_argument("--output", "-o", default=None)
    audit_runtime_query.add_argument(
        "--format",
        choices=["json", "jsonl", "csv"],
        default="json",
    )
    audit_runtime_query.add_argument("--json", action="store_true")

    audit_runtime_retention = audit_sub.add_parser("runtime-retention")
    audit_runtime_retention.add_argument("--cas-root", default=".polisyos/cas")
    audit_runtime_retention.add_argument("--retention-days", type=int, required=True)
    audit_runtime_retention.add_argument("--archive-dir", default=None)
    audit_runtime_retention.add_argument("--dry-run", action="store_true")
    audit_runtime_retention.add_argument("--json", action="store_true")

    cmd_security = components.add_parser("security")
    security_sub = cmd_security.add_subparsers(dest="security_command")

    rotate_jwt = security_sub.add_parser("rotate-jwt")
    rotate_jwt.add_argument("--manifest", default=str(DEFAULT_JWT_TRUST_ANCHORS_PATH))
    rotate_jwt.add_argument("--issuer", required=True)
    rotate_jwt.add_argument("--jwks-uri", required=True)
    rotate_jwt.add_argument("--audience", required=True)
    rotate_jwt.add_argument("--active-kid", action="append", default=[])
    rotate_jwt.add_argument("--next-kid", action="append", default=[])
    rotate_jwt.add_argument("--retire-kid", action="append", default=[])
    rotate_jwt.add_argument("--revoke-kid", action="append", default=[])
    rotate_jwt.add_argument("--rotated-by", default=None)
    rotate_jwt.add_argument("--json", action="store_true")

    rotate_ed = security_sub.add_parser("rotate-ed25519")
    rotate_ed.add_argument("--output", required=True, help="Base output path for .pem/.pub")
    rotate_ed.add_argument("--identity", required=True)
    rotate_ed.add_argument("--trust-dir", default=str(DEFAULT_TRUST_DIR))
    rotate_ed.add_argument("--revoked-dir", default=str(DEFAULT_REVOKED_DIR))
    rotate_ed.add_argument("--identities", default=str(DEFAULT_IDENTITIES_PATH))
    rotate_ed.add_argument("--revoke-public-key", action="append", default=[])
    rotate_ed.add_argument("--force", action="store_true")
    rotate_ed.add_argument("--json", action="store_true")

    return parser


def _cli_version() -> str:
    try:
        return version("policy-engine")
    except PackageNotFoundError:
        return "0+unknown"


__all__ = ["main"]


if __name__ == "__main__":  # pragma: no cover - CLI execution path
    raise SystemExit(main())
