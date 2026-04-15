"""CLI for fabric quarantine reporting and deterministic replay."""
from __future__ import annotations

import argparse
import importlib
import json
from typing import TYPE_CHECKING, Any, cast

from polisyos.core.artifacts.backends.config import ArtifactStoreConfig, build_artifact_store
from polisyos.fabric.data_plane.quarantine import (
    build_quarantine_report,
    list_quarantine_records,
    reprocess_quarantine_records,
)

if TYPE_CHECKING:
    from collections.abc import Callable


def _build_store(root: str) -> Any:
    return build_artifact_store(
        ArtifactStoreConfig(
            backend="filesystem",
            root=root,
        )
    )


def _load_handler(spec: str | None) -> Callable[[Any, Any], Any] | None:
    if spec is None:
        return None
    module_name, sep, attr = str(spec).partition(":")
    if not sep or not module_name or not attr:
        raise ValueError("--handler must use the form module:function")
    module = importlib.import_module(module_name)
    handler = getattr(module, attr)
    if not callable(handler):
        raise TypeError(f"{spec!r} does not resolve to a callable")
    return cast("Callable[[Any, Any], Any]", handler)


def _cmd_report(args: argparse.Namespace) -> int:
    store = _build_store(str(args.cas_root))
    records = list_quarantine_records(
        store,
        source=args.source,
        reason=args.reason,
        severity=args.severity,
    )
    report = build_quarantine_report(records)
    payload = {
        "total_records": report.total_records,
        "by_reason": report.by_reason,
        "by_severity": report.by_severity,
        "by_source": report.by_source,
        "downstream_impacts": report.downstream_impacts,
        "affected_sources": list(report.affected_sources),
        "artifact_ids": [artifact_id for artifact_id, _record in records],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def _cmd_reprocess(args: argparse.Namespace) -> int:
    store = _build_store(str(args.cas_root))
    handler = _load_handler(args.handler)
    result = reprocess_quarantine_records(
        store,
        artifact_ids=args.artifact_id or None,
        source=args.source,
        handler=handler,
    )
    print(
        json.dumps(
            {
                "attempted": result.attempted,
                "succeeded": result.succeeded,
                "failed": result.failed,
                "result_refs": list(result.result_refs),
                "failed_record_ids": list(result.failed_record_ids),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if result.failed == 0 else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fabric quarantine report and replay CLI")
    parser.add_argument("--cas-root", required=True, help="CAS root containing quarantine artifacts")
    subparsers = parser.add_subparsers(dest="command", required=True)

    report = subparsers.add_parser("report", help="Print a JSON quarantine summary")
    report.add_argument("--source")
    report.add_argument("--reason")
    report.add_argument("--severity")
    report.set_defaults(func=_cmd_report)

    reprocess = subparsers.add_parser("reprocess", help="Deterministically replay quarantined records")
    reprocess.add_argument("--source")
    reprocess.add_argument(
        "--artifact-id",
        action="append",
        default=[],
        help="Limit replay to explicit quarantine artifact ids (repeatable)",
    )
    reprocess.add_argument(
        "--handler",
        help="Import path for a replay handler in the form module:function",
    )
    reprocess.set_defaults(func=_cmd_reprocess)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
