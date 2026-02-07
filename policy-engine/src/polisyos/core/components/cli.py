from __future__ import annotations

import argparse
import importlib
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from polisyos.core.artifacts.store import FileSystemCAS
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
    if args.command == "replay":
        return _cmd_replay(args)

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


__all__ = ["main"]


if __name__ == "__main__":  # pragma: no cover - CLI execution path
    raise SystemExit(main())
