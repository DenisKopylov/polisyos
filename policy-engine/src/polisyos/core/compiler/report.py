from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.ir.linker import LinkReport


class CompileReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    ok: bool
    policy_ref: ArtifactRef | None = None
    registry_bundle_ref: ArtifactRef | None = None
    link_report_ref: ArtifactRef | None = None
    program_graph_ref: ArtifactRef | None = None
    exec_plan_ref: ArtifactRef | None = None
    notes: list[str] = Field(default_factory=list)


def put_link_report(
    store: FileSystemCAS, report: LinkReport, *, inputs: list[InputRef] | None = None
) -> ArtifactRef:
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
    return store.put_json(
        report,
        PutOptions(
            kind="compiler.compile_report",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.CompileReport", version=report.schema_version),
            inputs=inputs,
        ),
    )
