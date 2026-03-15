"""CLI sub-module: component discovery and registry build commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.components import (
    ComponentEntry,
    ComponentRegistry,
    DuplicateComponentIdPolicy,
    discover_components,
)
from polisyos.core.components.bootstrap import bootstrap_plugin_registries, build_components_index
from polisyos.core.registry import build_registry_bundle_from_components
from polisyos.core.registry.builder_from_fragments import FragmentPrecedencePolicy

__all__ = [
    "_cmd_components_bootstrap",
    "_cmd_components_list",
    "_cmd_registry_build",
]


def _cmd_components_list(args: Any) -> int:
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


def _cmd_registry_build(args: Any) -> int:
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


def _cmd_components_bootstrap(args: Any) -> int:
    groups = list(args.group) if args.group else None
    components_index, discovery_report = build_components_index(
        groups=groups,
        include_dev_scan=not args.no_dev_scan,
        dev_scan_paths=[Path(path) for path in args.dev_scan_path] if args.dev_scan_path else None,
    )

    bootstrap_report = bootstrap_plugin_registries(
        components_index,
        bootstrap_connectors=not args.skip_connectors,
        bootstrap_methods=not args.skip_methods,
        bootstrap_evaluators=not args.skip_evaluators,
        bootstrap_extractors=not args.skip_extractors,
        bootstrap_providers=not args.skip_providers,
        bootstrap_nodes=not args.skip_nodes,
    )
    bootstrap_report.sources_processed = discovery_report.sources_processed
    bootstrap_report.discovery_errors = [
        f"{error.source}:{error.item or '<unknown>'}: {error.message}"
        for error in discovery_report.errors
    ]

    if args.json:
        print(
            json.dumps(
                {
                    "components_total": bootstrap_report.components_total,
                    "sources_processed": bootstrap_report.sources_processed,
                    "success": bootstrap_report.success,
                    "discovery_errors": bootstrap_report.discovery_errors,
                    "domains": {
                        name: {
                            "registered": domain_report.registered,
                            "duplicates": domain_report.duplicates,
                            "errors": domain_report.errors,
                            "discovery_errors": domain_report.discovery_errors,
                            "success": domain_report.success,
                        }
                        for name, domain_report in sorted(bootstrap_report.domains.items())
                    },
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    print(f"components_total={bootstrap_report.components_total}")
    print(f"sources_processed={bootstrap_report.sources_processed}")
    for error in bootstrap_report.discovery_errors:
        print(f"discovery_error: {error}")
    for name, domain_report in sorted(bootstrap_report.domains.items()):
        print(
            f"{name}: registered={len(domain_report.registered)} "
            f"duplicates={len(domain_report.duplicates)} "
            f"errors={len(domain_report.errors)}"
        )
        for error in domain_report.errors:
            print(f"  {name}_error: {error}")
    return 0 if bootstrap_report.success else 1
