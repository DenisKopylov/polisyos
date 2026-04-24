"""Public run context module API."""

from __future__ import annotations

import json
import os
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast

from polisyos.common.logger import get_logger
from polisyos.common.serialization import fast_json_dumps

from ..artifacts._atomic_write import AtomicFileWriter
from ..artifacts.manifest import ArtifactRef, EnvInfo, InputRef, ProducerInfo, SchemaInfo
from ..artifacts.write_contract import ArtifactWriteOptions
from ..trace.record import TraceRecord, TraceRefs
from ..trace.sink import CompositeTraceSink, JsonlTraceSink, TraceSink
from .manifest import RunManifest

if TYPE_CHECKING:
    from polisyos.core.security.access_scope import AccessScope

    from ..artifacts.protocol import ArtifactStore

logger = get_logger(__name__)
_FINALIZE_JOURNAL_SCHEMA_VERSION = "1.0"
_FINALIZE_JOURNAL_NAME = ".finalize-journal.json"


class _AuditTraceSink(Protocol):
    """Trace sink protocol that also supports explicit shutdown."""

    def emit(self, rec: TraceRecord) -> None: ...

    def close(self) -> None: ...


def _run_manifest_write_options(run_manifest: RunManifest) -> ArtifactWriteOptions:
    return ArtifactWriteOptions(
        kind="core.run_manifest",
        media_type="application/json",
        schema=SchemaInfo(name="polisyos.core.RunManifest", version="0.1.0"),
        producer=run_manifest.producer,
        env=run_manifest.env,
        inputs=[
            InputRef(
                artifact_id=run_manifest.registry_bundle.artifact_id,
                role="registry_bundle",
            )
        ],
    )


def _finalize_journal_path(run_dir: Path) -> Path:
    return run_dir / _FINALIZE_JOURNAL_NAME


def _write_finalize_journal(run_dir: Path, run_manifest: RunManifest) -> None:
    payload = {
        "schema_version": _FINALIZE_JOURNAL_SCHEMA_VERSION,
        "run_manifest": run_manifest.model_dump(mode="json"),
    }
    AtomicFileWriter.write_atomic(
        _finalize_journal_path(run_dir),
        (fast_json_dumps(payload, sort_keys=True) + "\n").encode("utf-8"),
    )


def _clear_finalize_journal(run_dir: Path) -> None:
    _finalize_journal_path(run_dir).unlink(missing_ok=True)


def _load_finalize_journal(run_dir: Path) -> RunManifest | None:
    journal_path = _finalize_journal_path(run_dir)
    if not journal_path.exists():
        return None
    try:
        payload = json.loads(journal_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        logger.warning("Ignoring unreadable finalize journal for %s: %s", run_dir, exc)
        return None
    run_manifest_payload = payload.get("run_manifest")
    if not isinstance(run_manifest_payload, dict):
        logger.warning("Ignoring malformed finalize journal for %s", run_dir)
        return None
    try:
        return RunManifest.model_validate(run_manifest_payload)
    except (TypeError, ValueError) as exc:
        logger.warning("Ignoring invalid finalize journal for %s: %s", run_dir, exc)
        return None


def _trace_has_run_finalized_event(trace_path: Path) -> bool:
    if not trace_path.exists():
        return False
    for line in trace_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = TraceRecord.model_validate_json(line)
        except (TypeError, ValueError):
            continue
        if record.event == "RUN_FINALIZED":
            return True
    return False


def _append_run_finalized_event(
    *,
    trace_path: Path,
    run_manifest: RunManifest,
    run_ref: ArtifactRef,
) -> None:
    JsonlTraceSink(trace_path).emit(
        TraceRecord(
            run_id=run_manifest.run_id,
            phase="core",
            event="RUN_FINALIZED",
            tenant_id=run_manifest.tenant_id,
            cell_id=run_manifest.cell_id,
            refs=TraceRefs(outputs=[run_ref]),
            metrics={"status_ok": 1 if run_manifest.status == "ok" else 0},
        )
    )


def recover_pending_run_finalize(store: ArtifactStore, run_dir: Path) -> ArtifactRef | None:
    """Resume a crashed run-finalize sequence from the local journal if present."""
    run_manifest = _load_finalize_journal(run_dir)
    if run_manifest is None:
        return None
    run_ref = store.put_json(
        run_manifest,
        _run_manifest_write_options(run_manifest),
    )
    trace_path = run_dir / "trace.jsonl"
    if not _trace_has_run_finalized_event(trace_path):
        _append_run_finalized_event(
            trace_path=trace_path,
            run_manifest=run_manifest,
            run_ref=run_ref,
        )
    _clear_finalize_journal(run_dir)
    return run_ref


def new_run_id() -> str:
    """New run ID helper."""
    return "R_" + secrets.token_hex(8)


@dataclass
class RunContext:
    """Run context public type."""

    store: ArtifactStore
    trace: TraceSink
    run_manifest: RunManifest
    _trace_path: Path | None = None
    _audit_sink: _AuditTraceSink | None = None
    tenant_id: str | None = None
    cell_id: str | None = None
    access_scope: AccessScope | None = None

    @property
    def trace_path(self) -> Path | None:
        return self._trace_path

    @classmethod
    def start(
        cls,
        store: ArtifactStore,
        registry_bundle: ArtifactRef,
        producer: ProducerInfo | None = None,
        env: EnvInfo | None = None,
        run_dir: Path | None = None,
        run_id: str | None = None,
        *,
        tenant_id: str | None = None,
        cell_id: str | None = None,
        access_scope: AccessScope | None = None,
    ) -> RunContext:
        run_id = run_id or new_run_id()
        run_dir = run_dir or _default_run_dir(store, run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        trace_path = run_dir / "trace.jsonl"
        trace_sink: TraceSink = JsonlTraceSink(trace_path)
        audit_sink: _AuditTraceSink | None = None

        if _audit_chain_enabled():
            try:
                from polisyos.core.security.audit_sink import (
                    ChainedAuditSink,
                    build_default_audit_backends_from_env,
                )

                chained_sink = ChainedAuditSink(
                    chain_id=_build_audit_chain_id(run_id, tenant_id=tenant_id, cell_id=cell_id),
                    local_path=run_dir / "audit.jsonl",
                    backends=build_default_audit_backends_from_env(),
                )
                audit_sink = cast("_AuditTraceSink", chained_sink)
                trace_sink = CompositeTraceSink([trace_sink, audit_sink])
            except (ImportError, RuntimeError, OSError, ValueError, TypeError) as exc:
                logger.debug(
                    "Failed to initialize audit chain for run %s: %s",
                    run_id,
                    exc,
                )
                audit_sink = None

        ctx = cls(
            store=store,
            trace=trace_sink,
            run_manifest=RunManifest(
                run_id=run_id,
                registry_bundle=registry_bundle,
                producer=producer,
                env=env,
                tenant_id=tenant_id,
                cell_id=cell_id,
            ),
            _trace_path=trace_path,
            _audit_sink=audit_sink,
            tenant_id=tenant_id,
            cell_id=cell_id,
            access_scope=access_scope,
        )
        ctx.emit("core", "RUN_STARTED")
        return ctx

    def emit(
        self,
        phase: str,
        event: str,
        *,
        inputs: list[ArtifactRef] | None = None,
        outputs: list[ArtifactRef] | None = None,
        metrics: dict[str, float | int] | None = None,
    ) -> None:
        rec = TraceRecord(
            run_id=self.run_manifest.run_id,
            phase=phase,
            event=event,
            tenant_id=self.tenant_id,
            cell_id=self.cell_id,
            refs=TraceRefs(inputs=inputs or [], outputs=outputs or []),
            metrics=metrics or {},
        )
        self.trace.emit(rec)

    def add_input(self, ref: ArtifactRef) -> None:
        self.run_manifest.inputs.append(ref)
        self.emit("core", "RUN_INPUT_ADDED", inputs=[ref])

    def add_output(self, ref: ArtifactRef) -> None:
        self.run_manifest.outputs.append(ref)
        self.emit("core", "RUN_OUTPUT_ADDED", outputs=[ref])

    def finalize(
        self,
        status: str = "ok",
        *,
        errors: list[dict[str, object]] | None = None,
    ) -> ArtifactRef:
        run_dir = self._trace_path.parent if self._trace_path is not None else None
        if run_dir is not None:
            recovered_ref = recover_pending_run_finalize(self.store, run_dir)
            if recovered_ref is not None:
                return recovered_ref
        self.run_manifest.status = status
        if errors:
            self.run_manifest.errors.extend(errors)
        self.run_manifest.finished_at = self.run_manifest.finished_at or datetime.now(UTC).replace(
            microsecond=0
        )

        trace_ref = None
        if self._trace_path and self._trace_path.exists():
            data = self._trace_path.read_bytes()
            trace_ref = self.store.put_bytes(
                data,
                ArtifactWriteOptions(kind="core.trace.jsonl", media_type="application/jsonl"),
            )
            self.run_manifest.trace_ref = trace_ref

        if run_dir is not None:
            _write_finalize_journal(run_dir, self.run_manifest)
        run_ref = self.store.put_json(
            self.run_manifest,
            _run_manifest_write_options(self.run_manifest),
        )
        self.emit(
            "core",
            "RUN_FINALIZED",
            outputs=[run_ref],
            metrics={"status_ok": 1 if status == "ok" else 0},
        )
        if run_dir is not None:
            _clear_finalize_journal(run_dir)
        if self._audit_sink is not None:
            try:
                self._audit_sink.close()
            except (OSError, RuntimeError, ValueError) as exc:
                logger.debug(
                    "Failed to close audit sink for run %s: %s",
                    self.run_manifest.run_id,
                    exc,
                )
        return run_ref


def _audit_chain_enabled() -> bool:
    return os.getenv("POLISYOS_AUDIT_CHAIN_ENABLED", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _default_run_dir(store: ArtifactStore, run_id: str) -> Path:
    root = getattr(store, "root", None)
    if isinstance(root, Path):
        return root / "runs" / run_id
    if isinstance(root, str):
        return Path(root) / "runs" / run_id
    return Path(".") / "runs" / run_id


def _build_audit_chain_id(run_id: str, *, tenant_id: str | None, cell_id: str | None) -> str:
    tenant = tenant_id or "global"
    cell = cell_id or "default"
    return f"{tenant}:{cell}:{run_id}"
