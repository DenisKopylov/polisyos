"""CLI sub-module: audit export and verification commands."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

from polisyos.core.components._cli_store import build_cli_filesystem_cas

__all__ = [
    "_cmd_audit_export",
    "_cmd_audit_runtime_query",
    "_cmd_audit_runtime_retention",
    "_cmd_audit_verify",
]


def _cmd_audit_export(args: Any) -> int:
    audit_mod = importlib.import_module("polisyos.core.audit")
    AuditPackageAssembler = audit_mod.AuditPackageAssembler
    ExportOptions = audit_mod.ExportOptions
    ExportProfile = audit_mod.ExportProfile
    SigningPolicy = audit_mod.SigningPolicy

    cas = build_cli_filesystem_cas(Path(args.cas_root))
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


def _cmd_audit_verify(args: Any) -> int:
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


def _cmd_audit_runtime_query(args: Any) -> int:
    compliance = importlib.import_module("polisyos.runtime.http.compliance")
    query = compliance.RuntimeAuditQuery(
        stream=args.stream,
        tenant_id=args.tenant_id,
        actor=args.actor,
        resource_id=args.resource_id,
        endpoint=args.endpoint,
        operation=args.operation,
        outcome=args.outcome,
        since=compliance.parse_audit_time(args.since),
        until=compliance.parse_audit_time(args.until),
    )
    try:
        entries = compliance.query_runtime_audit(Path(args.cas_root), query)
    except Exception as exc:
        print(f"ERROR: runtime audit query failed: {exc}", file=sys.stderr)
        return 1

    if args.output:
        compliance.write_runtime_audit_report(
            entries,
            Path(args.output),
            output_format=args.format,
        )
        if not args.json:
            print(f"written={args.output}")
        return 0

    payload = {
        "summary": compliance.summarize_runtime_audit(entries),
        "entries": entries,
    }
    if args.format == "jsonl":
        for entry in entries:
            print(json.dumps(entry, ensure_ascii=True, sort_keys=True))
        return 0
    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    return 0


def _cmd_audit_runtime_retention(args: Any) -> int:
    compliance = importlib.import_module("polisyos.runtime.http.compliance")
    try:
        result = compliance.apply_runtime_audit_retention(
            Path(args.cas_root),
            retention_days=int(args.retention_days),
            archive_dir=Path(args.archive_dir) if args.archive_dir else None,
            dry_run=bool(args.dry_run),
        )
    except Exception as exc:
        print(f"ERROR: runtime audit retention failed: {exc}", file=sys.stderr)
        return 1
    payload = result.to_dict()
    if args.json:
        print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    else:
        print(
            "scanned={scanned} kept={kept} archived={archived} dry_run={dry_run}".format(
                **payload
            )
        )
        for path in payload["archive_paths"]:
            print(f"archive={path}")
    return 0
