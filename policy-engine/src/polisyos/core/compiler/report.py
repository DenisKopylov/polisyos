"""Compiler report contracts plus CAS persistence helpers for link and compile results."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import Field, model_validator

from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    InputRef,
    SchemaInfo,
    artifact_ref_identity_key,
)
from polisyos.core.artifacts.protocol import _require_return_selected_profile_writer
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.ir.kernel.base import KernelModel

if TYPE_CHECKING:
    from polisyos.core.artifacts.protocol import ArtifactStore
    from polisyos.ir.linker import LinkReport


class CompileCandidateRejection(KernelModel):
    """Bind one completed parameter validator result to its exact source graph.

    This transport is not a permission, execution-attestation, or scope-closure
    decision. Consumers must recompute it and separately reconcile the actual
    producer invocation before treating a failed compile as a domain rejection.
    """

    schema_version: Literal["1.0"] = "1.0"
    kind: Literal["expected_candidate_rejection"] = "expected_candidate_rejection"
    validation_rule: Literal["trinity.strict_parameter_link.v1"] = (
        "trinity.strict_parameter_link.v1"
    )
    reason_code: Literal["strict_parameter_validation_failed"] = (
        "strict_parameter_validation_failed"
    )
    request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    policy_ref: ArtifactRef
    registry_bundle_ref: ArtifactRef
    link_report_ref: ArtifactRef

    @model_validator(mode="after")
    def require_selected_sources(self) -> CompileCandidateRejection:
        """Reject incomplete or differently typed selected-source bindings."""
        for ref, expected_kind in (
            (self.policy_ref, "ir.trinity_bundle"),
            (self.registry_bundle_ref, "core.registry_bundle"),
            (self.link_report_ref, "compiler.link_report"),
        ):
            if (
                ref.kind != expected_kind
                or ref.media_type != "application/json"
                or ref.manifest_profile_sha256 is None
            ):
                raise ValueError("compile_candidate_rejection_requires_selected_sources")
        return self


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
    candidate_rejection: CompileCandidateRejection | None = Field(
        default=None, exclude_if=lambda value: value is None
    )

    @model_validator(mode="after")
    def validate_candidate_rejection(self) -> CompileReport:
        """Keep a parameter rejection distinct from successful or opaque reports."""
        rejection = self.candidate_rejection
        if rejection is None:
            return self
        if self.schema_version != "1.1" or self.ok:
            raise ValueError("compile_candidate_rejection_requires_failed_report_1_1")
        for actual, expected in (
            (self.policy_ref, rejection.policy_ref),
            (self.registry_bundle_ref, rejection.registry_bundle_ref),
            (self.link_report_ref, rejection.link_report_ref),
        ):
            if actual is None or artifact_ref_identity_key(actual) != artifact_ref_identity_key(
                expected
            ):
                raise ValueError("compile_candidate_rejection_report_source_mismatch")
        if any(
            ref is not None
            for ref in (
                self.lowered_ir_ref,
                self.program_graph_ref,
                self.exec_plan_ref,
                self.slot_layout_ref,
                self.treasury_plan_ref,
            )
        ):
            raise ValueError("compile_candidate_rejection_cannot_contain_execution_outputs")
        return self


def put_link_report(
    store: ArtifactStore,
    report: LinkReport,
    *,
    inputs: list[InputRef] | None = None,
    return_selected_profile: bool = False,
) -> ArtifactRef:
    """Persist an IR linker report into CAS with the compiler link-report schema metadata."""
    if type(return_selected_profile) is not bool:
        raise TypeError("return_selected_profile must be a bool")
    if return_selected_profile:
        _require_return_selected_profile_writer(store, "put_json")
    return store.put_json(
        report,
        ArtifactWriteOptions(
            kind="compiler.link_report",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.LinkReport", version=report.schema_version),
            inputs=inputs,
        ),
        return_selected_profile=return_selected_profile,
    )


def put_compile_report(
    store: ArtifactStore,
    report: CompileReport,
    *,
    inputs: list[InputRef] | None = None,
    return_selected_profile: bool = False,
) -> ArtifactRef:
    """Persist a compile report into CAS so runtime and audit surfaces can reference it."""
    if type(return_selected_profile) is not bool:
        raise TypeError("return_selected_profile must be a bool")
    if return_selected_profile:
        _require_return_selected_profile_writer(store, "put_json")
    return store.put_json(
        report,
        ArtifactWriteOptions(
            kind="compiler.compile_report",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.CompileReport", version=report.schema_version),
            inputs=inputs,
        ),
        return_selected_profile=return_selected_profile,
    )
