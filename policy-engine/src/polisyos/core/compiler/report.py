"""Compiler report contracts plus CAS persistence helpers for link and compile results."""
from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import Field

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.ir.kernel.base import KernelModel

if TYPE_CHECKING:
    from polisyos.core.artifacts.protocol import ArtifactStore
    from polisyos.ir.linker import LinkReport


class CompileReport(KernelModel):
    """High-level status report emitted by Foundry compilation and lowering workflows."""
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
    store: ArtifactStore, report: LinkReport, *, inputs: list[InputRef] | None = None
) -> ArtifactRef:
    """Persist an IR linker report into CAS with the compiler link-report schema metadata."""
    return store.put_json(
        report,
        ArtifactWriteOptions(
            kind="compiler.link_report",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.LinkReport", version=report.schema_version),
            inputs=inputs,
        ),
    )


def put_compile_report(
    store: ArtifactStore, report: CompileReport, *, inputs: list[InputRef] | None = None
) -> ArtifactRef:
    """Persist a compile report into CAS so runtime and audit surfaces can reference it."""
    return store.put_json(
        report,
        ArtifactWriteOptions(
            kind="compiler.compile_report",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.CompileReport", version=report.schema_version),
            inputs=inputs,
        ),
    )
