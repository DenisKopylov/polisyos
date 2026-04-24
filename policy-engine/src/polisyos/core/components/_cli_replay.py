"""CLI sub-module: replay and resume commands."""

from __future__ import annotations

import importlib
import json
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

from polisyos.core.components._cli_store import build_cli_filesystem_cas

if TYPE_CHECKING:
    from polisyos.core.artifacts.store import FileSystemCAS

__all__ = [
    "_cmd_replay",
    "_cmd_replay_with_store",
    "_cmd_resume",
]


def _cmd_replay(args: Any) -> int:
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
            store = build_cli_filesystem_cas(Path(tmp_dir))
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

    store = build_cli_filesystem_cas(Path(args.cas_root))
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
    args: Any,
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


def _cmd_resume(args: Any) -> int:
    checkpoint = importlib.import_module("polisyos.scientist.engine.checkpoint")
    normalize_checkpoint_policy = checkpoint.normalize_checkpoint_policy
    resolve_latest_checkpoint = checkpoint.resolve_latest_checkpoint
    resume_from_checkpoint = checkpoint.resume_from_checkpoint

    cas = build_cli_filesystem_cas(Path(args.cas_root))
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
        print(f"checkpoint.writer={summary['writer_hostname']}:{summary['writer_pid']}")
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
