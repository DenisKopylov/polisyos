"""Compiler report contracts plus CAS persistence helpers for link and compile results."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.ir.linker import LinkReport


class CompileReport(BaseModel):
    """High-level status report emitted by Foundry compilation and lowering workflows."""
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    ok: bool
    policy_ref: ArtifactRef | None = None
    registry_bundle_ref: ArtifactRef | None = None
    link_report_ref: ArtifactRef | None = None
    lowered_ir_ref: ArtifactRef | None = None
    program_graph_ref: ArtifactRef | None = None
    exec_plan_ref: ArtifactRef | None = None
    slot_layout_ref: ArtifactRef | None = None
    treasury_plan_ref: ArtifactRef | None = None
    semantic_closure_notes: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


def put_link_report(
    store: FileSystemCAS, report: LinkReport, *, inputs: list[InputRef] | None = None
) -> ArtifactRef:
    """Persist an IR linker report into CAS with the compiler link-report schema metadata."""
    return store.put_json(
        report,
        PutOptions(
            kind="compiler.link_report",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.LinkReport", version=report.schema_version),
            inputs=inputs,
        ),
    )


def put_compile_report(
    store: FileSystemCAS, report: CompileReport, *, inputs: list[InputRef] | None = None
) -> ArtifactRef:
    """Persist a compile report into CAS so runtime and audit surfaces can reference it."""
    return store.put_json(
        report,
        PutOptions(
            kind="compiler.compile_report",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.CompileReport", version=report.schema_version),
            inputs=inputs,
        ),
    )
