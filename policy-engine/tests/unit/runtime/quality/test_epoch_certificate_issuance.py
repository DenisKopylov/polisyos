from __future__ import annotations

# ruff: noqa: S101
import pytest

from polisyos.core import artifacts
from polisyos.runtime.quality.epoch_certificate_issuance import (
    AdmittedDecisionPacketExecutionClosure,
    DecisionPacketEpochIssuanceOwner,
)
from polisyos.scientist.validation.epoch_certificate_issuance import (
    DecisionPacketInvocationRecord,
)


def _put(store: artifacts.FileSystemCAS, label: str) -> artifacts.ArtifactRef:
    return store.put_bytes(
        label.encode("utf-8"),
        artifacts.ArtifactWriteOptions(
            kind=f"fixture.{label}",
            media_type="application/octet-stream",
        ),
    )


def test_execution_recipe_reads_the_complete_admitted_source_denominator(tmp_path) -> None:
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    refs = {
        name: _put(store, name)
        for name in (
            "invocation",
            "epoch",
            "input-a",
            "input-b",
            "state",
            "run",
            "spec",
            "implementation",
            "loaded-code",
            "tool",
            "environment",
            "profile",
            "admission",
            "verifier",
        )
    }
    invocation_inputs = tuple(
        sorted(
            (refs["epoch"], refs["input-a"], refs["input-b"]),
            key=lambda ref: (
                *artifacts.artifact_ref_identity_key(ref)[:3],
                artifacts.artifact_ref_identity_key(ref)[3] or "",
            ),
        )
    )
    record = DecisionPacketInvocationRecord(
        state_ref=refs["state"],
        run_manifest_ref=refs["run"],
        node_spec_ref=refs["spec"],
        implementation_ref=refs["implementation"],
        loaded_code_ref=refs["loaded-code"],
        input_refs=invocation_inputs,
    )
    closure = AdmittedDecisionPacketExecutionClosure(
        invocation_ref=refs["invocation"],
        invocation_content_hash=str(refs["invocation"].artifact_id),
        epoch_manifest_ref=refs["epoch"],
        authority_purpose="decision_validity_epoch_transition",
        requested_query_context_ref="sha256:" + "a" * 64,
        input_certificate_refs=invocation_inputs,
        code_source_refs=(refs["implementation"], refs["loaded-code"]),
        tool_source_refs=(refs["tool"],),
        environment_manifest_ref=refs["environment"],
        environment_profile_ref=refs["profile"],
        admission_evidence_ref=refs["admission"],
        verifier_provenance_ref=refs["verifier"],
    )
    owner = DecisionPacketEpochIssuanceOwner(store=store, root=tmp_path / "owner")

    complete_refs = owner._complete_recipe_inputs(record=record, closure=closure)

    expected = (
        *invocation_inputs,
        refs["state"],
        refs["run"],
        refs["spec"],
        refs["implementation"],
        refs["loaded-code"],
        refs["tool"],
        refs["environment"],
        refs["profile"],
        refs["admission"],
        refs["verifier"],
    )

    def identity(ref: artifacts.ArtifactRef) -> tuple[str, str, str, str | None]:
        return (
            str(ref.artifact_id),
            ref.kind,
            ref.media_type,
            ref.manifest_profile_sha256,
        )

    assert {identity(ref) for ref in complete_refs} == {identity(ref) for ref in expected}
    assert len(complete_refs) == len(expected)

    narrowed = closure.model_copy(update={"input_certificate_refs": (refs["input-a"],)})
    with pytest.raises(ValueError, match="epoch_certificate_issuance_evidence_unresolved"):
        owner._complete_recipe_inputs(record=record, closure=narrowed)

    absent_tool = artifacts.ArtifactRef(
        artifact_id=artifacts.ArtifactID.model_validate("sha256:" + "f" * 64),
        kind="fixture.absent-tool",
        media_type="application/octet-stream",
    )
    unresolved = closure.model_copy(update={"tool_source_refs": (absent_tool,)})
    with pytest.raises(ValueError, match="epoch_certificate_issuance_evidence_unresolved"):
        owner._complete_recipe_inputs(record=record, closure=unresolved)
