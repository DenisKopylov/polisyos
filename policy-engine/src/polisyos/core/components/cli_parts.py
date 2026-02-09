from __future__ import annotations

import argparse
import importlib
import json
import os
import re
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.artifacts.signing import (
    DEFAULT_IDENTITIES_PATH,
    DEFAULT_PRIVATE_KEY_ENV,
    DEFAULT_PRIVATE_KEY_FILE_ENV,
    DEFAULT_PRIVATE_KEY_PATH,
    DEFAULT_REVOKED_DIR,
    DEFAULT_TRUST_DIR,
    Ed25519Signer,
    Ed25519Verifier,
    KeyPair,
    SignatureVerificationStatus,
    ensure_private_key_permissions,
    safe_short_key_id,
)
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.components import (
    ComponentEntry,
    ComponentKind,
    ComponentRegistry,
    DuplicateComponentIdPolicy,
    discover_components,
)
from polisyos.core.registry import build_registry_bundle_from_components
from polisyos.core.registry.builder_from_fragments import FragmentPrecedencePolicy
from polisyos.core.contracts.scholar import ResearchIntent

_SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "components" and args.components_command == "list":
        return _cmd_components_list(args)
    if args.command == "registry" and args.registry_command == "build":
        return _cmd_registry_build(args)
    if args.command == "scholar" and args.scholar_command == "enrich":
        return _cmd_scholar_enrich(args)
    if args.command == "lex" and args.lex_command == "normpack" and args.lex_normpack_command == "build":
        return _cmd_lex_normpack_build(args)
    if args.command == "lex" and args.lex_command == "impact":
        return _cmd_lex_impact(args)
    if (
        args.command == "scientist"
        and args.scientist_command == "sensitivity"
        and args.scientist_sensitivity_command == "run"
    ):
        return _cmd_scientist_sensitivity_run(args)
    if args.command == "scientist" and args.scientist_command == "stress-test":
        return _cmd_scientist_stress_test(args)
    if args.command == "scientist" and args.scientist_command == "backtest":
        return _cmd_scientist_backtest(args)
    if args.command == "replay":
        return _cmd_replay(args)
    if args.command == "resume":
        return _cmd_resume(args)
    if args.command == "keygen":
        return _cmd_keygen(args)
    if args.command == "sign":
        return _cmd_sign(args)
    if args.command == "verify":
        return _cmd_verify(args)
    if args.command == "audit" and args.audit_command == "export":
        return _cmd_audit_export(args)
    if args.command == "audit" and args.audit_command == "verify":
        return _cmd_audit_verify(args)

    parser.print_help()
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="polisyos")

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
    audit_export.add_argument("--no-visualization", action="store_true")
    audit_export.add_argument("--json", action="store_true")

    audit_verify = audit_sub.add_parser("verify")
    audit_verify.add_argument("package", help="Path to audit package file or directory")
    audit_verify.add_argument("--trusted-keys-dir", default=None, help="Directory with trusted PEM keys")
    audit_verify.add_argument(
        "--trusted-key",
        action="append",
        default=[],
        help="Explicit trusted public key PEM path (repeatable)",
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
    audit_verify.add_argument("--output", "-o", default=None, help="Report output path")
    audit_verify.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
        help="Report format",
    )
    audit_verify.add_argument("--json", action="store_true")

    return parser


def _cmd_components_list(args: argparse.Namespace) -> int:
    report = discover_components(
        include_dev_scan=True,
        dev_scan_paths=[Path(path) for path in args.dev_scan_path] if args.dev_scan_path else None,
    )

    rows: list[dict[str, Any]] = []
    for item in report.components:
        meta = item.metadata
        if args.kind and meta.kind.value != args.kind:
            continue
        if args.domain and args.domain not in meta.domains:
            continue
        if args.jurisdiction and meta.jurisdictions and args.jurisdiction not in meta.jurisdictions:
            continue
        if args.tag and args.tag not in meta.tags:
            continue

        rows.append(
            {
                "component_id": str(meta.component_id),
                "kind": meta.kind.value,
                "domains": list(meta.domains),
                "jurisdictions": list(meta.jurisdictions),
                "abi_targets": dict(meta.abi_targets),
                "source": {
                    "type": item.source.source_type,
                    "location": item.source.location,
                },
            }
        )

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        for row in rows:
            print(
                f"{row['component_id']}\t{row['kind']}\t"
                f"domains={','.join(row['domains']) or '-'}\t"
                f"jurisdictions={','.join(row['jurisdictions']) or '-'}\t"
                f"source={row['source']['type']}:{row['source']['location']}"
            )

    if report.errors:
        for error in report.errors:
            print(
                f"discovery_error: {error.source}:{error.item or '<unknown>'}: {error.message}"
            )
    return 0


def _cmd_registry_build(args: argparse.Namespace) -> int:
    report = discover_components(
        groups=["polisyos.ir_fragments"],
        include_dev_scan=True,
        dev_scan_paths=[Path(path) for path in args.dev_scan_path] if args.dev_scan_path else None,
    )

    index = ComponentRegistry()
    for row in report.components:
        index.register(
            ComponentEntry(metadata=row.metadata, component=row.component, source=row.source),
            on_duplicate=DuplicateComponentIdPolicy.WARN,
        )

    store = FileSystemCAS(Path(args.cas_root))
    bundle_ref, compose_report_ref = build_registry_bundle_from_components(
        store,
        components_index=index,
        domain=args.domain,
        jurisdiction=args.jurisdiction,
        precedence_policy=FragmentPrecedencePolicy(),
    )

    print(f"registry_bundle_ref={bundle_ref.artifact_id}")
    if compose_report_ref is not None:
        print(f"compose_report_ref={compose_report_ref.artifact_id}")
    return 0


def _cmd_scholar_enrich(args: argparse.Namespace) -> int:
    scholar_api = importlib.import_module("polisyos.scholar.api")
    enrich_topic = scholar_api.enrich_topic

    cas = FileSystemCAS(Path(args.cas_root))
    fact_log_root = Path(args.fact_log_root)
    payload = json.loads(Path(args.intent).read_text(encoding="utf-8"))
    intent = ResearchIntent.model_validate(payload)

    result = enrich_topic(
        cas=cas,
        fact_log_root=fact_log_root,
        intent=intent,
    )
    print(f"knowledge_bundle_ref={result.knowledge_bundle_ref.artifact_id}")
    print(f"bundle_id={result.bundle_id}")
    return 0


def _cmd_lex_normpack_build(args: argparse.Namespace) -> int:
    lex_api = importlib.import_module("polisyos.lex.api")
    lex_types = importlib.import_module("polisyos.lex.types")
    assemble_norm_pack = lex_api.assemble_norm_pack
    NormPackBuildRequest = lex_types.NormPackBuildRequest

    cas = FileSystemCAS(Path(args.cas_root))
    fact_log_root = Path(args.fact_log_root)
    request = NormPackBuildRequest(
        jurisdiction=args.jurisdiction,
        as_of=args.as_of,
        domain=args.domain,
    )

    result = assemble_norm_pack(
        cas=cas,
        fact_log_root=fact_log_root,
        request=request,
    )
    print(f"norm_pack_artifact_id={result.norm_pack_artifact_id}")
    print(f"norm_pack_world_id={result.norm_pack_world_id}")
    print(f"built_by={result.built_by}")
    return 0


def _cmd_lex_impact(args: argparse.Namespace) -> int:
    try:
        _validate_output_extension(args.output, args.format)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    lex_sim = importlib.import_module("polisyos.lex.simulator")
    lex_sim_cli = importlib.import_module("polisyos.lex.simulator.cli")
    governance_profiles = importlib.import_module("polisyos.scientist.governance.profiles")

    ValidationProfile = governance_profiles.ValidationProfile
    profile = getattr(ValidationProfile, args.profile)()

    pass_ids = tuple(
        token.strip()
        for token in str(args.passes).split(",")
        if token.strip()
    )
    if not pass_ids:
        print("ERROR: --passes cannot be empty", file=sys.stderr)
        return 2

    cas = FileSystemCAS(Path(args.cas_root))
    try:
        old_pack = lex_sim_cli.load_norm_pack(cas, args.old_ref)
        new_pack = lex_sim_cli.load_norm_pack(cas, args.new_ref)
    except Exception as exc:
        print(f"ERROR: failed to load NormPack(s): {exc}", file=sys.stderr)
        return 1

    analyzer = lex_sim.NormImpactAnalyzer(
        cas=cas,
        profile=profile,
        passes=pass_ids,
    )
    report = analyzer.analyze(old_pack, new_pack)

    rendered: str
    if args.format == "json":
        rendered = report.model_dump_json(indent=2)
    else:
        rendered = lex_sim_cli.render_impact_markdown(report)

    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
        print(f"impact_report={args.output}")
    else:
        print(rendered)
    return 0


def _cmd_scientist_sensitivity_run(args: argparse.Namespace) -> int:
    try:
        _validate_output_extension(args.output, args.format)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    payload = json.loads(Path(args.config).read_text(encoding="utf-8"))
    doe_designs = importlib.import_module("polisyos.scientist.doe.designs")
    doe_sampling = importlib.import_module("polisyos.scientist.doe.sampling")
    doe_analysis = importlib.import_module("polisyos.scientist.doe.analysis")

    plan_data = payload.get("plan", payload)
    try:
        plan = doe_designs.SensitivityPlan.model_validate(plan_data)
    except Exception as exc:
        print(f"ERROR: invalid sensitivity plan: {exc}", file=sys.stderr)
        return 2

    import numpy as np

    if "samples" in payload:
        samples = np.asarray(payload["samples"], dtype=float)
    else:
        try:
            samples = doe_sampling.generate_sensitivity_samples(plan)
        except Exception as exc:
            print(f"ERROR: failed to generate sensitivity samples: {exc}", file=sys.stderr)
            return 1

    if "outputs" in payload:
        outputs = np.asarray(payload["outputs"], dtype=float)
    else:
        try:
            outputs = _evaluate_builtin_sensitivity_objective(samples, payload.get("objective"))
        except Exception as exc:
            print(f"ERROR: failed to evaluate built-in objective: {exc}", file=sys.stderr)
            return 2

    try:
        result = doe_analysis.analyze_sensitivity(plan, samples, outputs)
    except Exception as exc:
        print(f"ERROR: sensitivity analysis failed: {exc}", file=sys.stderr)
        return 1

    cas = FileSystemCAS(Path(args.cas_root))
    ref = cas.put_json(
        result.model_dump(mode="json"),
        PutOptions(
            kind="scientist.sensitivity_result",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.scientist.SensitivityResult", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )

    out_payload = result.model_dump(mode="json")
    out_payload["cas_artifact_id"] = str(ref.artifact_id)

    rendered = json.dumps(out_payload, ensure_ascii=True, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
        print(f"sensitivity_report={args.output}")
    else:
        print(rendered)
    return 0


def _cmd_scientist_stress_test(args: argparse.Namespace) -> int:
    try:
        _validate_output_extension(args.output, args.format)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    payload = json.loads(Path(args.config).read_text(encoding="utf-8"))
    doe_designs = importlib.import_module("polisyos.scientist.doe.designs")
    search_objective = importlib.import_module("polisyos.scientist.search.objective")
    search_adversarial = importlib.import_module("polisyos.scientist.search.adversarial")

    plan_data = payload.get("plan", payload)
    try:
        plan = doe_designs.AdversarialPlan.model_validate(plan_data)
    except Exception as exc:
        print(f"ERROR: invalid adversarial plan: {exc}", file=sys.stderr)
        return 2

    param_names = [item.name for item in plan.parameter_specs]
    objective_spec = payload.get("objective") if isinstance(payload, dict) else None

    objective_callable = _build_builtin_objective_callable(param_names, objective_spec)
    composite_objective = search_objective.CompositeObjective(
        [_CallableObjective(name="stress_objective", fn=objective_callable)]
    )

    class _RandomGenerator:
        def __init__(self, specs: list[Any], seed: int | None):
            import random

            self._specs = specs
            self._rng = random.Random(seed)

        def generate(self, history: list[Any], current_best: dict[str, Any] | None, context: dict[str, Any]):
            del history, current_best, context
            candidate: dict[str, Any] = {"semantic": {"interventions": []}}
            for spec in self._specs:
                candidate[spec.name] = self._rng.uniform(spec.lower_bound, spec.upper_bound)
            return candidate

    def _stage_b(candidate: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        del context
        return {"simulation_results": {"stress_objective": objective_callable(candidate)}}

    cas = FileSystemCAS(Path(args.cas_root))
    report = search_adversarial.run_stress_test(
        adversarial_plan=plan,
        base_objective=composite_objective,
        stage_b_evaluator=_stage_b,
        candidate_generator=_RandomGenerator(plan.parameter_specs, plan.seed),
        context={},
        cas=cas,
    )

    rendered = json.dumps(report.model_dump(mode="json"), ensure_ascii=True, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
        print(f"stress_report={args.output}")
    else:
        print(rendered)
    return 0


def _cmd_scientist_backtest(args: argparse.Namespace) -> int:
    try:
        backtesting_cli = importlib.import_module("polisyos.scientist.backtesting.cli")
        code, rendered = backtesting_cli.run_backtest_command(args)
    except Exception as exc:
        print(f"ERROR: backtest failed: {exc}", file=sys.stderr)
        return 1

    if rendered:
        print(rendered)
    return code


def _validate_output_extension(output_path: str | None, output_format: str) -> None:
    if not output_path:
        return
    expected = ".json" if output_format == "json" else ".md"
    suffix = Path(output_path).suffix.lower()
    if suffix and suffix != expected:
        raise ValueError(
            f"output extension '{suffix}' does not match --format {output_format!r} "
            f"(expected '{expected}')"
        )


def _evaluate_builtin_sensitivity_objective(samples, objective_spec: Any):
    import numpy as np

    if objective_spec is None:
        objective_type = "quadratic"
        spec = {}
    elif isinstance(objective_spec, str):
        objective_type = objective_spec
        spec = {}
    elif isinstance(objective_spec, dict):
        objective_type = str(objective_spec.get("type", "quadratic"))
        spec = objective_spec
    else:
        raise ValueError("objective must be null, string, or object")

    if objective_type == "ishigami":
        if samples.shape[1] < 3:
            raise ValueError("ishigami objective requires at least 3 parameters")
        a = float(spec.get("a", 7.0))
        b = float(spec.get("b", 0.1))
        x1 = samples[:, 0]
        x2 = samples[:, 1]
        x3 = samples[:, 2]
        return np.sin(x1) + a * (np.sin(x2) ** 2) + b * (x3**4) * np.sin(x1)

    if objective_type == "quadratic":
        return np.sum(samples**2, axis=1)

    raise ValueError(f"unsupported built-in objective type: {objective_type}")


def _build_builtin_objective_callable(
    parameter_names: list[str],
    objective_spec: Any,
):
    if objective_spec is None:
        objective_spec = {"type": "quadratic"}
    if isinstance(objective_spec, str):
        objective_spec = {"type": objective_spec}
    if not isinstance(objective_spec, dict):
        raise ValueError("objective must be null, string, or object")

    objective_type = str(objective_spec.get("type", "quadratic"))
    center = objective_spec.get("center")
    if not isinstance(center, dict):
        center = {}
    weights = objective_spec.get("weights")
    if not isinstance(weights, dict):
        weights = {}

    def _objective(candidate: dict[str, Any]) -> float:
        total = 0.0
        for name in parameter_names:
            value = float(candidate.get(name, 0.0))
            c = float(center.get(name, 0.0))
            w = float(weights.get(name, 1.0))
            total += w * ((value - c) ** 2)
        if objective_type == "negative_quadratic":
            return -total
        if objective_type == "quadratic":
            return total
        raise ValueError(f"unsupported built-in objective type: {objective_type}")

    return _objective


class _CallableObjective:
    def __init__(self, name: str, fn):
        self._name = name
        self._fn = fn

    @property
    def name(self) -> str:
        return self._name

    @property
    def direction(self):
        objective_module = importlib.import_module("polisyos.scientist.search.objective")
        return objective_module.OptimizationDirection.MINIMIZE

    def evaluate(self, results: dict[str, Any]):
        objective_module = importlib.import_module("polisyos.scientist.search.objective")
        value = float(results.get("stress_objective", 0.0))
        return objective_module.ObjectiveValue(
            name=self._name,
            raw_value=value,
            direction=objective_module.OptimizationDirection.MINIMIZE,
        )


def _cmd_replay(args: argparse.Namespace) -> int:
    runtime_replay = importlib.import_module("polisyos.runtime.replay")
    normalize_artifact_id = runtime_replay.normalize_artifact_id
    completeness_check = runtime_replay.completeness_check
    VerificationConfig = runtime_replay.VerificationConfig
    VerificationMode = runtime_replay.VerificationMode
    ReplayStrategy = runtime_replay.ReplayStrategy

    if args.check_only and args.export:
        print("ERROR: --check-only and --export cannot be used together", file=sys.stderr)
        return 2

    packet_ref = normalize_artifact_id(args.packet_ref)
    if args.bundle:
        with tempfile.TemporaryDirectory(prefix="polisyos-replay-") as tmp_dir:
            store = FileSystemCAS(Path(tmp_dir))
            import_report = store.import_subgraph(Path(args.bundle), verify_integrity=False)
            return _cmd_replay_with_store(
                args=args,
                store=store,
                packet_ref=packet_ref,
                completeness_check=completeness_check,
                VerificationConfig=VerificationConfig,
                VerificationMode=VerificationMode,
                ReplayStrategy=ReplayStrategy,
                import_report=import_report,
            )

    store = FileSystemCAS(Path(args.cas_root))
    return _cmd_replay_with_store(
        args=args,
        store=store,
        packet_ref=packet_ref,
        completeness_check=completeness_check,
        VerificationConfig=VerificationConfig,
        VerificationMode=VerificationMode,
        ReplayStrategy=ReplayStrategy,
        import_report=None,
    )


def _cmd_replay_with_store(
    *,
    args: argparse.Namespace,
    store: FileSystemCAS,
    packet_ref: Any,
    completeness_check: Any,
    VerificationConfig: Any,
    VerificationMode: Any,
    ReplayStrategy: Any,
    import_report: Any,
) -> int:
    completeness = completeness_check(store, packet_ref)

    if args.export:
        if completeness.graph is None:
            print("ERROR: dependency graph is unavailable", file=sys.stderr)
            return 1
        export_report = store.export_subgraph(
            completeness.graph.all_artifact_ids(),
            Path(args.export),
            compress=True,
            include_manifests=True,
        )
        if args.json:
            payload: dict[str, Any] = {
                "exported_artifacts": export_report.exported_artifacts,
                "total_bytes": export_report.total_bytes,
                "output_path": str(export_report.output_path),
                "missing_artifacts": export_report.missing_artifacts,
                "missing_manifests": export_report.missing_manifests,
            }
            if import_report is not None:
                payload["bundle_import"] = {
                    "imported_files": import_report.imported_files,
                    "imported_artifacts": import_report.imported_artifacts,
                }
            print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
        else:
            print(
                f"exported={export_report.exported_artifacts} "
                f"bytes={export_report.total_bytes} "
                f"path={export_report.output_path}"
            )
        return 0 if not export_report.missing_artifacts else 1

    if args.check_only:
        if args.json:
            payload = {
                "level": completeness.level.value,
                "strategy": completeness.strategy.value,
                "total_artifacts": completeness.total_artifacts,
                "present_artifacts": completeness.present_artifacts,
                "missing": [
                    {
                        "artifact_id": item.artifact_id,
                        "role": item.role,
                        "critical": item.critical,
                        "status": item.status.value,
                    }
                    for item in completeness.missing
                ],
                "corrupted": [
                    {
                        "artifact_id": item.artifact_id,
                        "role": item.role,
                        "critical": item.critical,
                        "status": item.status.value,
                    }
                    for item in completeness.corrupted
                ],
                "reason_codes": completeness.reason_codes,
            }
            if import_report is not None:
                payload["bundle_import"] = {
                    "imported_files": import_report.imported_files,
                    "imported_artifacts": import_report.imported_artifacts,
                    "verification_failed": import_report.verification_failed,
                }
            print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
        else:
            print(completeness.summary())
        return 0 if completeness.ok else 1

    mode_map = {
        "bit_exact": VerificationMode.BIT_EXACT,
        "ci_bounded": VerificationMode.CI_BOUNDED,
        "skip": VerificationMode.SKIP,
    }
    strategy = None
    if args.strategy != "auto":
        strategy = ReplayStrategy(args.strategy)
    config = VerificationConfig(
        mode=mode_map[args.mode],
        relative_tolerance=float(args.tolerance),
        confidence_level=float(args.confidence_level),
    )
    replay_backend = importlib.import_module("polisyos.scientist.replay_backend")
    replay_packet = replay_backend.replay_packet
    result = replay_packet(
        store,
        packet_ref,
        verify=not args.no_verify,
        verification_config=config,
        force_strategy=strategy,
    )

    if args.json:
        payload = {
            "success": result.success,
            "run_id": result.run_id,
            "strategy": result.strategy.value,
            "original_packet_ref": result.original_packet_ref,
            "replay_decision_packet_ref": result.replay_decision_packet_ref,
            "replay_simulation_result_ref": result.replay_simulation_result_ref,
            "errors": result.errors,
            "warnings": result.warnings,
            "completeness": {
                "level": result.completeness.level.value if result.completeness else None,
                "strategy": result.completeness.strategy.value if result.completeness else None,
            }
            if result.completeness
            else None,
            "verification": {
                "passed": result.verification.passed if result.verification else None,
                "mode": result.verification.mode.value if result.verification else None,
                "details": result.verification.details if result.verification else None,
            }
            if result.verification
            else None,
        }
        if import_report is not None:
            payload["bundle_import"] = {
                "imported_files": import_report.imported_files,
                "imported_artifacts": import_report.imported_artifacts,
                "verification_failed": import_report.verification_failed,
            }
        print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    else:
        status = "SUCCESS" if result.success else "FAILED"
        print(f"{status} run_id={result.run_id} strategy={result.strategy.value}")
        if result.replay_simulation_result_ref:
            print(f"simulation_result_ref={result.replay_simulation_result_ref}")
        if result.replay_decision_packet_ref:
            print(f"decision_packet_ref={result.replay_decision_packet_ref}")
        for warning in result.warnings:
            print(f"warning: {warning}")
        for error in result.errors:
            print(f"error: {error}")

    return 0 if result.success else 1


def _cmd_resume(args: argparse.Namespace) -> int:
    checkpoint = importlib.import_module("polisyos.scientist.engine.checkpoint")
    normalize_checkpoint_policy = checkpoint.normalize_checkpoint_policy
    resolve_latest_checkpoint = checkpoint.resolve_latest_checkpoint
    resume_from_checkpoint = checkpoint.resume_from_checkpoint

    cas = FileSystemCAS(Path(args.cas_root))
    run_id = str(args.run_id)
    policy = normalize_checkpoint_policy(args.checkpoint_policy)

    try:
        resolved = resolve_latest_checkpoint(cas, run_id)
    except Exception as exc:
        print(f"ERROR: failed to resolve checkpoint for run_id={run_id}: {exc}", file=sys.stderr)
        return 1

    if resolved is None:
        print(f"ERROR: no checkpoint found for run_id={run_id}", file=sys.stderr)
        return 1

    head, checkpoint_artifact = resolved
    summary = {
        "run_id": run_id,
        "sequence_number": head.sequence_number,
        "node_alias": head.node_alias,
        "checkpoint_ref": str(head.checkpoint_ref.artifact_id),
        "workflow_id": checkpoint_artifact.metadata.workflow_id,
        "workflow_fingerprint": checkpoint_artifact.metadata.workflow_fingerprint,
        "fsm_phase": checkpoint_artifact.metadata.fsm_phase,
        "updated_at": head.updated_at.isoformat(),
        "writer_pid": head.writer_pid,
        "writer_hostname": head.writer_hostname,
        "completed_nodes_count": len(checkpoint_artifact.metadata.completed_nodes),
    }

    if not args.json:
        print(f"run_id={summary['run_id']}")
        print(f"checkpoint.sequence={summary['sequence_number']}")
        print(f"checkpoint.node={summary['node_alias']}")
        print(f"checkpoint.ref={summary['checkpoint_ref']}")
        print(f"workflow.id={summary['workflow_id']}")
        print(f"workflow.fingerprint={summary['workflow_fingerprint'][:16]}...")
        print(f"fsm.phase={summary['fsm_phase']}")
        print(f"checkpoint.updated_at={summary['updated_at']}")
        print(
            "checkpoint.writer="
            f"{summary['writer_hostname']}:{summary['writer_pid']}"
        )
        print(f"completed_nodes={summary['completed_nodes_count']}")

    if args.dry_run:
        if args.json:
            print(json.dumps(summary, ensure_ascii=True, indent=2, sort_keys=True))
        return 0

    try:
        result = resume_from_checkpoint(
            cas,
            run_id,
            checkpoint_policy=policy,
            force_lock=bool(args.force),
        )
    except Exception as exc:
        print(f"ERROR: resume failed for run_id={run_id}: {exc}", file=sys.stderr)
        return 1

    outcome = {
        "run_id": run_id,
        "status": result.report.status,
        "run_ref": str(result.run_ref.artifact_id) if result.run_ref is not None else None,
    }
    if args.json:
        payload = {"checkpoint": summary, "resume": outcome}
        print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    else:
        print(f"resume.status={result.report.status}")
        if result.run_ref is not None:
            print(f"run_ref={result.run_ref.artifact_id}")

    return 0 if result.report.status == "ok" else 1


def _cmd_audit_export(args: argparse.Namespace) -> int:
    audit_mod = importlib.import_module("polisyos.core.audit")
    AuditPackageAssembler = audit_mod.AuditPackageAssembler
    ExportOptions = audit_mod.ExportOptions
    ExportProfile = audit_mod.ExportProfile
    SigningPolicy = audit_mod.SigningPolicy

    cas = FileSystemCAS(Path(args.cas_root))
    exclude = frozenset(
        item.strip()
        for item in str(args.exclude_kinds).split(",")
        if item.strip()
    )
    options = ExportOptions(
        exclude_kinds=exclude,
        profile=ExportProfile(args.profile),
        include_visualization=not bool(args.no_visualization),
        signing_policy=SigningPolicy(args.signing_policy),
        slsa_mode=args.slsa_mode,
        slsa_policy=args.slsa_policy,
    )
    assembler = AuditPackageAssembler(
        cas=cas,
        runs_dir=Path(args.runs_dir),
        options=options,
    )
    try:
        result = assembler.export(
            run_id=args.run_id,
            output_path=Path(args.output) if args.output else None,
        )
    except Exception as exc:
        print(f"ERROR: audit export failed: {exc}", file=sys.stderr)
        return 1

    payload = {
        "run_id": result.run_id,
        "archive_path": str(result.archive_path),
        "artifacts_exported": result.artifacts_exported,
        "signatures_included": result.signatures_included,
        "unsigned_artifacts": result.unsigned_artifacts,
        "prov_entities": result.prov_entities,
        "prov_activities": result.prov_activities,
        "prov_agents": result.prov_agents,
        "warnings": result.warnings,
        "duration_seconds": round(result.duration_seconds, 3),
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    else:
        print(f"audit_package={result.archive_path}")
        print(f"artifacts={result.artifacts_exported} signatures={result.signatures_included}")
        if result.unsigned_artifacts:
            print(f"unsigned={len(result.unsigned_artifacts)}")
        for warning in result.warnings:
            print(f"warning: {warning}")
    return 0


def _cmd_audit_verify(args: argparse.Namespace) -> int:
    audit_mod = importlib.import_module("polisyos.core.audit")
    AuditPackageVerifier = audit_mod.AuditPackageVerifier
    render_markdown = audit_mod.render_markdown

    trusted_keys = [Path(path) for path in args.trusted_key] if args.trusted_key else []
    verifier = AuditPackageVerifier(
        trusted_keys=trusted_keys,
        trusted_keys_dir=Path(args.trusted_keys_dir) if args.trusted_keys_dir else None,
        allow_package_keys=bool(args.allow_package_keys),
        fail_unsigned=bool(args.fail_unsigned),
        require_slsa=bool(args.require_slsa),
    )
    try:
        report = verifier.verify(Path(args.package))
    except Exception as exc:
        print(f"ERROR: audit verify failed: {exc}", file=sys.stderr)
        return 2

    if args.format == "json":
        text = json.dumps(report.to_dict(), ensure_ascii=True, indent=2, sort_keys=True)
    else:
        text = render_markdown(report)

    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
        if not args.json:
            print(f"written={args.output}")
    else:
        print(text)

    if report.overall_status == "PASS":
        return 0
    return 1


def _normalize_artifact_ref(value: str) -> ArtifactID:
    if value.startswith("sha256:"):
        return ArtifactID.model_validate(value)
    if _SHA256_HEX_RE.fullmatch(value):
        return ArtifactID.from_sha256_hex(value)
    raise ValueError(f"Invalid artifact reference: {value}")


def _resolve_key_paths(output: str) -> tuple[Path, Path]:
    base = Path(output).expanduser()
    if base.suffix in {".pem", ".pub"}:
        base = base.with_suffix("")
    return base.with_suffix(".pem"), base.with_suffix(".pub")


def _write_private_key(path: Path, data: bytes, *, force: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not force and path.exists():
        raise FileExistsError(f"Private key exists: {path}")

    if force:
        tmp_path = path.with_suffix(path.suffix + f".tmp-{uuid.uuid4().hex}")
        fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, path)
            os.chmod(path, 0o600)
        finally:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
        return

    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def _write_public_key(path: Path, data: bytes, *, force: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not force and path.exists():
        raise FileExistsError(f"Public key exists: {path}")
    tmp_path = path.with_suffix(path.suffix + f".tmp-{uuid.uuid4().hex}")
    with open(tmp_path, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp_path, path)
    os.chmod(path, 0o644)


def _cmd_keygen(args: argparse.Namespace) -> int:
    keypair = KeyPair.generate()
    if args.public_only:
        public_pem = keypair.public_pem().decode("utf-8")
        if args.json:
            payload = {
                "key_id": keypair.key_id,
                "public_key": public_pem,
                "name": args.name,
            }
            print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
        else:
            print(public_pem)
        return 0

    private_path, public_path = _resolve_key_paths(args.output)
    try:
        _write_private_key(private_path, keypair.private_pem(), force=bool(args.force))
        _write_public_key(public_path, keypair.public_pem(), force=bool(args.force))
    except FileExistsError as exc:
        print(f"ERROR: {exc}. Use --force to overwrite.", file=sys.stderr)
        return 1

    private_mode = oct(private_path.stat().st_mode & 0o777)
    public_mode = oct(public_path.stat().st_mode & 0o777)
    payload = {
        "private_key": str(private_path),
        "private_mode": private_mode,
        "public_key": str(public_path),
        "public_mode": public_mode,
        "key_id": keypair.key_id,
        "name": args.name,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    else:
        print("Ed25519 key pair generated")
        print(f"  Private key: {private_path} (mode: {private_mode})")
        print(f"  Public key:  {public_path} (mode: {public_mode})")
        print(f"  Key ID:      {keypair.key_id}")
        if args.name:
            print(f"  Identity:    {args.name}")
    return 0


def _cmd_sign(args: argparse.Namespace) -> int:
    if args.all and args.artifact_ref:
        print("ERROR: artifact_ref cannot be used with --all", file=sys.stderr)
        return 2
    if not args.all and not args.artifact_ref:
        print("ERROR: artifact_ref is required unless --all is set", file=sys.stderr)
        return 2

    try:
        if args.key:
            key_path = Path(args.key).expanduser()
            ok, warning = ensure_private_key_permissions(key_path)
            if not ok and warning:
                print(f"WARNING: {warning}", file=sys.stderr)
            signer = Ed25519Signer.from_path(key_path)
        else:
            signer = Ed25519Signer.from_env_or_file(
                private_key_env=DEFAULT_PRIVATE_KEY_ENV,
                private_key_file_env=DEFAULT_PRIVATE_KEY_FILE_ENV,
                default_private_key_file=DEFAULT_PRIVATE_KEY_PATH,
            )
    except Exception as exc:
        print(f"ERROR: cannot load private signing key: {exc}", file=sys.stderr)
        return 2

    store = FileSystemCAS(Path(args.cas_root))
    identity = args.identity

    if args.all:
        report = store.sign_all_artifacts(
            signer,
            signer_identity=identity,
            only_unsigned=not bool(args.resign),
            max_workers=max(1, int(args.workers)),
        )
        if args.json:
            print(report.model_dump_json(indent=2))
        else:
            print(
                f"signed={report.signed} skipped={report.skipped} "
                f"errors={report.errors} total={report.total}"
            )
        return 0 if report.errors == 0 else 1

    try:
        artifact_id = _normalize_artifact_ref(args.artifact_ref)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if store.has_signature(artifact_id) and not args.resign:
        if args.json:
            payload = {
                "artifact_id": str(artifact_id),
                "status": "skipped",
                "message": "already signed",
            }
            print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
        else:
            print(f"Already signed: {artifact_id}")
        return 0

    try:
        sig = store.sign_artifact(artifact_id, signer, signer_identity=identity)
    except Exception as exc:
        print(f"ERROR: signing failed for {artifact_id}: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(sig.model_dump_json(indent=2, exclude_none=True))
    else:
        print(f"Signed {artifact_id} with key {safe_short_key_id(sig.key_id)}")
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    if args.all and args.artifact_ref:
        print("ERROR: artifact_ref cannot be used with --all", file=sys.stderr)
        return 2
    if not args.all and not args.artifact_ref:
        print("ERROR: artifact_ref is required unless --all is set", file=sys.stderr)
        return 2

    store = FileSystemCAS(Path(args.cas_root))
    verifier = Ed25519Verifier(strict_identity=bool(args.strict_identity))

    try:
        verifier.load_trust_dir(Path(args.trust_dir))
        verifier.load_revoked_dir(Path(args.revoked_dir))
        verifier.load_identity_bindings(Path(args.identities))
        for key_path in args.public_key:
            verifier.load_trusted_key_file(Path(key_path).expanduser())
    except Exception as exc:
        print(f"ERROR: failed to initialize trust store: {exc}", file=sys.stderr)
        return 2

    if args.all:
        report = store.verify_all_signatures(
            verifier,
            max_workers=max(1, int(args.workers)),
            strict_identity=bool(args.strict_identity),
        )
        if not args.quiet:
            if args.json:
                print(report.model_dump_json(indent=2))
            else:
                print(
                    f"valid={report.valid} unsigned={report.unsigned} invalid={report.invalid} "
                    f"untrusted={report.untrusted} revoked={report.revoked} "
                    f"errors={report.errors} total={report.total}"
                )
        if report.invalid or report.untrusted or report.revoked or report.errors:
            return 1
        if args.fail_unsigned and report.unsigned:
            return 1
        return 0

    try:
        artifact_id = _normalize_artifact_ref(args.artifact_ref)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    result = store.verify_signature(
        artifact_id,
        verifier,
        strict_identity=bool(args.strict_identity),
    )
    if not args.quiet:
        if args.json:
            print(result.model_dump_json(indent=2, exclude_none=True))
        else:
            print(f"status={result.status.value} artifact={result.artifact_id}")
            if result.key_id:
                print(f"key_id={result.key_id}")
            if result.signer_identity:
                print(f"signer_identity={result.signer_identity}")
            if result.expected_identity:
                print(f"expected_identity={result.expected_identity}")
            if result.message:
                print(f"message={result.message}")

    if result.status == SignatureVerificationStatus.VALID:
        return 0
    if result.status == SignatureVerificationStatus.UNSIGNED:
        return 1 if args.fail_unsigned else 0
    return 1


__all__ = ["main"]


if __name__ == "__main__":  # pragma: no cover - CLI execution path
    raise SystemExit(main())
