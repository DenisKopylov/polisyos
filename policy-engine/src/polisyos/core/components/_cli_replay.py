"""CLI sub-module: replay and resume commands."""

from __future__ import annotations

import importlib
import json
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager, redirect_stdout
from pathlib import Path
from typing import TYPE_CHECKING, Any

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.components._cli_store import build_cli_filesystem_cas

if TYPE_CHECKING:
    from polisyos.core.artifacts.store import FileSystemCAS

__all__ = [
    "_cmd_replay",
    "_cmd_replay_with_store",
    "_cmd_resume",
]


@contextmanager
def _library_output(as_json: bool) -> Iterator[None]:
    """Keep CLI JSON stdout separate from unsilenced library diagnostics."""
    if as_json:
        with redirect_stdout(sys.stderr):
            yield
    else:
        yield


def _artifact_ref_payload(ref: Any) -> dict[str, str | None]:
    """Project one selected CAS view without dropping its profile identity."""
    return {
        "artifact_id": str(ref.artifact_id),
        "kind": ref.kind,
        "media_type": ref.media_type,
        "manifest_profile_sha256": ref.manifest_profile_sha256,
    }


def _bundle_import_payload(report: Any) -> dict[str, Any]:
    """Project every import outcome from the same typed report fields."""
    payload = {
        "imported_files": report.imported_files,
        "imported_artifacts": report.imported_artifacts,
        "received_artifact_ids": list(report.received_artifact_ids),
        "received_artifact_count_basis": "unique recognized IDs from incoming CAS members",
        "published_refs": [_artifact_ref_payload(ref) for ref in report.published_refs],
        "reused_refs": [_artifact_ref_payload(ref) for ref in report.reused_refs],
        "integrity_verification_requested": report.integrity_verification_requested,
        "integrity_verified_refs": [
            _artifact_ref_payload(ref) for ref in report.integrity_verified_refs
        ],
        "verification_failed": report.verification_failed,
        "disposition_basis": report.disposition_basis,
    }
    if getattr(report, "signature_verification_requested", False):
        payload["signature_verification_requested"] = True
        payload["signature_verified_refs"] = [
            _artifact_ref_payload(ref) for ref in report.signature_verified_refs
        ]
    return payload


def _bundle_import_summary(report: Any) -> str:
    """Render the same outcome fields for every human-readable CLI branch."""
    requested = "requested" if report.integrity_verification_requested else "not_requested"
    signature = (
        f" signature=required:{len(report.signature_verified_refs)}"
        if getattr(report, "signature_verification_requested", False)
        else ""
    )
    return (
        f"bundle_import received_unique_ids={report.imported_artifacts} "
        f"published_views={len(report.published_refs)} reused_views={len(report.reused_refs)} "
        f"integrity={requested}:{len(report.integrity_verified_refs)} "
        f"verification_failed={len(report.verification_failed)} "
        f"disposition_basis={report.disposition_basis}{signature}"
    )


def _cmd_replay(args: Any) -> int:
    for name in ("export_max_retained_generations", "export_max_retained_bytes"):
        limit = getattr(args, name, None)
        if limit is not None and (not args.export or type(limit) is not int or limit < 0):
            print(
                "ERROR: export retention limits require --export and nonnegative integers",
                file=sys.stderr,
            )
            return 2
    if getattr(args, "require_bundle_signatures", False) and not args.bundle:
        print("ERROR: --require-bundle-signatures requires --bundle", file=sys.stderr)
        return 2
    with _library_output(args.json):
        scientist_replay = importlib.import_module("polisyos.scientist.replay.deterministic")
    normalize_artifact_id = scientist_replay.normalize_artifact_id
    completeness_check = scientist_replay.completeness_check
    VerificationConfig = scientist_replay.VerificationConfig
    VerificationMode = scientist_replay.VerificationMode
    ReplayStrategy = scientist_replay.ReplayStrategy

    if args.check_only and args.export:
        print("ERROR: --check-only and --export cannot be used together", file=sys.stderr)
        return 2

    packet_ref = normalize_artifact_id(args.packet_ref)
    if args.bundle:
        from polisyos.core.artifacts import ImportSignatureVerificationError
        from polisyos.core.artifacts.signing import Ed25519Verifier

        signature_verifier = None
        if getattr(args, "require_bundle_signatures", False):
            try:
                signature_verifier = Ed25519Verifier(
                    strict_identity=bool(args.bundle_strict_identity)
                )
                signature_verifier.load_trust_dir(Path(args.bundle_trust_dir))
                signature_verifier.load_revoked_dir(Path(args.bundle_revoked_dir))
                signature_verifier.load_identity_bindings(Path(args.bundle_identities))
            except (OSError, ValueError, TypeError) as error:
                print(
                    f"ERROR: required bundle trust configuration unavailable: {error}",
                    file=sys.stderr,
                )
                return 2
        refusal: dict[str, Any] | None = None
        with tempfile.TemporaryDirectory(prefix="polisyos-replay-") as tmp_dir:
            with _library_output(args.json):
                store = build_cli_filesystem_cas(Path(tmp_dir))
                options: dict[str, Any] = {"verify_integrity": False}
                if signature_verifier is not None:
                    options["signature_verifier"] = signature_verifier
                try:
                    import_report = store.import_subgraph(Path(args.bundle), **options)
                except ImportSignatureVerificationError as error:
                    refusal = {
                        "error": "required_bundle_signature_refused",
                        "artifact_ref": _artifact_ref_payload(error.artifact_ref),
                        "signature_result": error.result.model_dump(mode="json"),
                    }
            if refusal is not None:
                if args.json:
                    print(json.dumps(refusal, sort_keys=True))
                else:
                    print(
                        f"ERROR: {refusal['error']}: {refusal['signature_result']['status']}",
                        file=sys.stderr,
                    )
                return 1
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

    with _library_output(args.json):
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
    with _library_output(args.json):
        completeness = completeness_check(store, packet_ref)

    if args.export:
        if completeness.graph is None:
            if args.json:
                payload: dict[str, Any] = {"error": "dependency graph is unavailable"}
                if import_report is not None:
                    payload["bundle_import"] = _bundle_import_payload(import_report)
                print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
            else:
                print("ERROR: dependency graph is unavailable", file=sys.stderr)
                if import_report is not None:
                    print(_bundle_import_summary(import_report), file=sys.stderr)
            return 1
        from polisyos.core.artifacts import ExportResourceError

        limits = {
            name: value
            for name in ("max_retained_generations", "max_retained_bytes")
            if (value := getattr(args, f"export_{name}", None)) is not None
        }
        try:
            with _library_output(args.json):
                export_report = store.export_subgraph(
                    completeness.graph.all_artifact_ids(),
                    Path(args.export),
                    compress=True,
                    include_manifests=True,
                    **limits,
                )
        except ExportResourceError as error:
            refusal = {
                "error": "export_resource_refused",
                "reason": error.reason,
                "target": str(error.target),
                "lock_path": str(error.lock_path),
                "replaced": error.replaced,
                "staging_path": str(error.staging_path) if error.staging_path is not None else None,
                "occupied_paths": [str(path) for path in error.occupied_paths],
                "occupied_bytes": error.occupied_bytes,
                "max_retained_generations": error.max_retained_generations,
                "max_retained_bytes": error.max_retained_bytes,
            }
            if args.json:
                print(json.dumps(refusal, sort_keys=True))
            else:
                print(f"ERROR: {error}", file=sys.stderr)
            return 1
        retained_paths = getattr(export_report, "retained_paths", ())
        retention = {
            "paths": [str(path) for path in retained_paths],
            "logical_bytes": getattr(export_report, "retained_bytes", 0),
            "max_generations": getattr(export_report, "max_retained_generations", None),
            "max_logical_bytes": getattr(export_report, "max_retained_bytes", None),
            "reclamation": "manual_inspection_no_foreign_deletion",
        }
        if args.json:
            payload: dict[str, Any] = {
                "exported_artifacts": export_report.exported_artifacts,
                "total_bytes": export_report.total_bytes,
                "output_path": str(export_report.output_path),
                "missing_artifacts": export_report.missing_artifacts,
                "missing_manifests": export_report.missing_manifests,
            }
            if retained_paths or limits:
                payload["retention"] = retention
            if export_report.previous_generation is not None:
                payload["previous_generation"] = str(export_report.previous_generation)
                payload["previous_generation_retention"] = "caller_owned_manual_reclamation"
            if import_report is not None:
                payload["bundle_import"] = _bundle_import_payload(import_report)
            print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
        else:
            print(
                f"exported={export_report.exported_artifacts} "
                f"bytes={export_report.total_bytes} "
                f"path={export_report.output_path}"
            )
            if export_report.previous_generation is not None:
                print(
                    f"previous_generation={export_report.previous_generation} "
                    "retention=caller_owned_manual_reclamation"
                )
            if retained_paths or limits:
                print(
                    f"retained_count={len(retained_paths)} "
                    f"retained_logical_bytes={retention['logical_bytes']} "
                    f"limits={retention['max_generations']}/{retention['max_logical_bytes']}"
                )
            if import_report is not None:
                print(_bundle_import_summary(import_report))
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
                        "manifest_profile_sha256": item.manifest_profile_sha256,
                        "role": item.role,
                        "critical": item.critical,
                        "status": item.status.value,
                    }
                    for item in completeness.missing
                ],
                "corrupted": [
                    {
                        "artifact_id": item.artifact_id,
                        "manifest_profile_sha256": item.manifest_profile_sha256,
                        "role": item.role,
                        "critical": item.critical,
                        "status": item.status.value,
                    }
                    for item in completeness.corrupted
                ],
                "reason_codes": completeness.reason_codes,
            }
            if import_report is not None:
                payload["bundle_import"] = _bundle_import_payload(import_report)
            print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
        else:
            print(completeness.summary())
            if import_report is not None:
                print(_bundle_import_summary(import_report))
        return 0 if completeness.ok else 1

    mode_map = {
        "bit_exact": VerificationMode.BIT_EXACT,
        "ci_bounded": VerificationMode.CI_BOUNDED,
        "skip": VerificationMode.SKIP,
    }
    strategy = None
    if args.strategy != "auto":
        strategy = ReplayStrategy(args.strategy)
    try:
        config = VerificationConfig(
            mode=mode_map[args.mode],
            relative_tolerance=float(args.tolerance),
            confidence_level=float(args.confidence_level),
        )
    except (TypeError, ValueError, OverflowError) as exc:
        print(f"ERROR: invalid verification configuration: {exc}", file=sys.stderr)
        return 2
    with _library_output(args.json):
        replay_backend = importlib.import_module("polisyos.scientist.replay.backend")
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
            "replay_artifact_refs": {
                role: _artifact_ref_payload(ref)
                for role, ref in result.replay_artifact_refs.items()
            },
            "errors": result.errors,
            "warnings": result.warnings,
            "completeness": {
                "level": result.completeness.level.value if result.completeness else None,
                "strategy": result.completeness.strategy.value if result.completeness else None,
                "reason_codes": result.completeness.reason_codes if result.completeness else [],
            }
            if result.completeness
            else None,
            "verification": {
                "passed": result.verification.passed if result.verification else None,
                "skipped": result.verification.skipped if result.verification else None,
                "mode": result.verification.mode.value if result.verification else None,
                "details": result.verification.details if result.verification else None,
            }
            if result.verification
            else None,
        }
        if import_report is not None:
            payload["bundle_import"] = _bundle_import_payload(import_report)
        print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    else:
        status = "SUCCESS" if result.success else "FAILED"
        print(f"{status} run_id={result.run_id} strategy={result.strategy.value}")
        if result.verification is not None:
            verification_status = (
                "skipped"
                if result.verification.skipped
                else "passed"
                if result.verification.passed
                else "failed"
            )
            print(f"verification={verification_status} mode={result.verification.mode.value}")
        if result.replay_simulation_result_ref:
            print(f"simulation_result_ref={result.replay_simulation_result_ref}")
        if result.replay_decision_packet_ref:
            print(f"decision_packet_ref={result.replay_decision_packet_ref}")
        for role, ref in result.replay_artifact_refs.items():
            if ref.manifest_profile_sha256 is not None:
                print(f"{role}_manifest_profile_sha256={ref.manifest_profile_sha256}")
        for warning in result.warnings:
            print(f"warning: {warning}")
        for error in result.errors:
            print(f"error: {error}")
        if import_report is not None:
            print(_bundle_import_summary(import_report))

    return 0 if result.success else 1


def _cmd_resume(args: Any) -> int:
    workflow_id = getattr(args, "workflow_ref", None)
    workflow_profile = getattr(args, "workflow_profile", None)
    if (workflow_id is None) != (workflow_profile is None):
        print(
            "ERROR: --workflow-ref and --workflow-profile must be supplied together",
            file=sys.stderr,
        )
        return 2
    workflow_ref: ArtifactRef | None = None
    if workflow_id is not None:
        try:
            if not isinstance(workflow_id, str) or not isinstance(workflow_profile, str):
                raise TypeError("selected workflow ID and profile must be strings")
            workflow_ref = ArtifactRef(
                artifact_id=ArtifactID.model_validate(
                    workflow_id if workflow_id.startswith("sha256:") else f"sha256:{workflow_id}"
                ),
                kind="scientist.workflow_spec",
                media_type="application/json",
                manifest_profile_sha256=workflow_profile,
            )
        except (TypeError, ValueError) as exc:
            print(f"ERROR: invalid selected workflow reference: {exc}", file=sys.stderr)
            return 2

    with _library_output(args.json):
        checkpoint = importlib.import_module("polisyos.scientist.orchestration.engine.checkpoint")
    normalize_checkpoint_policy = checkpoint.normalize_checkpoint_policy
    resolve_latest_checkpoint = checkpoint.resolve_latest_checkpoint
    resume_from_checkpoint = checkpoint.resume_from_checkpoint

    with _library_output(args.json):
        cas = build_cli_filesystem_cas(Path(args.cas_root))
    run_id = str(args.run_id)
    policy = normalize_checkpoint_policy(args.checkpoint_policy)

    try:
        with _library_output(args.json):
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
        selected_workflow = {"workflow_ref": workflow_ref} if workflow_ref is not None else {}
        with _library_output(args.json):
            result = resume_from_checkpoint(
                cas,
                run_id,
                checkpoint_policy=policy,
                force_lock=bool(args.force),
                **selected_workflow,
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
