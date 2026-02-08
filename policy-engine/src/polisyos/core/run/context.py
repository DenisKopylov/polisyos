from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from polisyos.core.security.access_scope import AccessScope

from ..artifacts.manifest import ArtifactRef, EnvInfo, InputRef, ProducerInfo, SchemaInfo
from ..artifacts.store import FileSystemCAS, PutOptions
from ..trace.record import TraceRecord
from ..trace.sink import JsonlTraceSink, TraceSink
from .manifest import RunManifest


def new_run_id() -> str:
    return "R_" + secrets.token_hex(8)


@dataclass
class RunContext:
    store: FileSystemCAS
    trace: TraceSink
    run_manifest: RunManifest
    _trace_path: Path | None = None
    tenant_id: str | None = None
    cell_id: str | None = None
    access_scope: AccessScope | None = None

    @property
    def trace_path(self) -> Path | None:
        return self._trace_path

    @classmethod
    def start(
        cls,
        store: FileSystemCAS,
        registry_bundle: ArtifactRef,
        producer: ProducerInfo | None = None,
        env: EnvInfo | None = None,
        run_dir: Path | None = None,
        run_id: str | None = None,
        *,
        tenant_id: str | None = None,
        cell_id: str | None = None,
        access_scope: AccessScope | None = None,
    ) -> "RunContext":
        run_id = run_id or new_run_id()
        run_dir = run_dir or (store.root / "runs" / run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        trace_path = run_dir / "trace.jsonl"

        ctx = cls(
            store=store,
            trace=JsonlTraceSink(trace_path),
            run_manifest=RunManifest(
                run_id=run_id,
                registry_bundle=registry_bundle,
                producer=producer,
                env=env,
                tenant_id=tenant_id,
                cell_id=cell_id,
            ),
            _trace_path=trace_path,
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
            refs={"inputs": inputs or [], "outputs": outputs or []},
            metrics=metrics or {},
        )
        self.trace.emit(rec)

    def add_input(self, ref: ArtifactRef) -> None:
        self.run_manifest.inputs.append(ref)
        self.emit("core", "RUN_INPUT_ADDED", inputs=[ref])

    def add_output(self, ref: ArtifactRef) -> None:
        self.run_manifest.outputs.append(ref)
        self.emit("core", "RUN_OUTPUT_ADDED", outputs=[ref])

    def finalize(self, status: str = "ok", *, errors: list[dict] | None = None) -> ArtifactRef:
        self.run_manifest.status = status
        if errors:
            self.run_manifest.errors.extend(errors)
        self.run_manifest.finished_at = self.run_manifest.finished_at or datetime.now(
            timezone.utc
        ).replace(microsecond=0)

        trace_ref = None
        if self._trace_path and self._trace_path.exists():
            data = self._trace_path.read_bytes()
            trace_ref = self.store.put_bytes(
                data,
                PutOptions(kind="core.trace.jsonl", media_type="application/jsonl"),
            )
            self.run_manifest.trace_ref = trace_ref

        run_ref = self.store.put_json(
            self.run_manifest,
            PutOptions(
                kind="core.run_manifest",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.core.RunManifest", version="0.1.0"),
                producer=self.run_manifest.producer,
                env=self.run_manifest.env,
                inputs=[
                    InputRef(
                        artifact_id=self.run_manifest.registry_bundle.artifact_id,
                        role="registry_bundle",
                    )
                ],
            ),
        )
        self.emit(
            "core",
            "RUN_FINALIZED",
            outputs=[run_ref],
            metrics={"status_ok": 1 if status == "ok" else 0},
        )
        return run_ref
