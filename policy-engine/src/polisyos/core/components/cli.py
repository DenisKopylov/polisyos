from __future__ import annotations

import argparse
import importlib
import json
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


__all__ = ["main"]


if __name__ == "__main__":  # pragma: no cover - CLI execution path
    raise SystemExit(main())
