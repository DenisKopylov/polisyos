from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path

# ruff: noqa: S101
import pytest

from polisyos.common.canonical_profile import CanonicalProfileRefusalError
from polisyos.core import artifacts, canon
from polisyos.runtime.quality import epoch_certificate_issuance as issuance
from polisyos.runtime.quality.epoch_certificate_issuance import (
    AdmittedDecisionPacketExecutionClosure,
    DecisionPacketEpochIssuanceOwner,
)
from polisyos.runtime.quality.epoch_validity_cascade import DerivationRecipeBinding
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


def test_execution_recipe_reads_the_complete_admitted_source_denominator(tmp_path: Path) -> None:
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


def test_basis_reader_rejects_extra_manifest_input_from_real_owner_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The issuance writer's exact source projection is checked before model admission."""
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    refs = {
        name: _put(store, name)
        for name in (
            "epoch",
            "input",
            "admission",
            "verifier",
            "invocation",
            "recipe",
            "history",
            "complete",
            "code",
            "tool",
            "environment",
            "environment-profile",
        )
    }
    inputs = issuance.EpochCertificateIssuanceInputs(
        run_id="run-a",
        canonical_producer_ref=(
            "polisyos.scientist.nodes.builtins.decide.decision_packet.builder."
            "BuildDecisionPacketNode.execute"
        ),
        epoch_manifest_ref=refs["epoch"],
        recipe=None,
        input_certificate_refs=(refs["input"],),
        native_coordinate_refs=("sha256:" + "a" * 64,),
        rule_schema_profile_refs=("sha256:" + "b" * 64,),
        requested_query_context_ref="sha256:" + "c" * 64,
        authority_purpose="decision_validity_epoch_transition",
        admission_evidence_ref=refs["admission"],
        verifier_provenance_ref=refs["verifier"],
    )
    closure = AdmittedDecisionPacketExecutionClosure(
        invocation_ref=refs["invocation"],
        invocation_content_hash=str(refs["invocation"].artifact_id),
        epoch_manifest_ref=refs["epoch"],
        authority_purpose="decision_validity_epoch_transition",
        requested_query_context_ref=inputs.requested_query_context_ref,
        input_certificate_refs=inputs.input_certificate_refs,
        code_source_refs=(refs["code"],),
        tool_source_refs=(refs["tool"],),
        environment_manifest_ref=refs["environment"],
        environment_profile_ref=refs["environment-profile"],
        admission_evidence_ref=refs["admission"],
        verifier_provenance_ref=refs["verifier"],
    )
    basis = issuance._IssuanceBasis(
        inputs=inputs,
        invocation_input_refs=inputs.input_certificate_refs,
        invocation_ref=refs["invocation"],
        execution_closure=closure,
        execution_recipe=DerivationRecipeBinding(
            recipe_ref=refs["recipe"],
            recipe_content_hash=str(refs["recipe"].artifact_id),
            recipe_schema_profile_ref="sha256:" + "d" * 64,
            input_roles=("execution.source[0]",),
        ),
        complete_input_certificate_refs=(refs["complete"],),
        epoch_history_snapshot_ref=refs["history"],
        epoch_history_snapshot_content_hash=str(refs["history"].artifact_id),
    )
    writer_input_refs = (
        *inputs.input_certificate_refs,
        inputs.epoch_manifest_ref,
        refs["recipe"],
        refs["invocation"],
        *basis.complete_input_certificate_refs,
        inputs.admission_evidence_ref,
        inputs.verifier_provenance_ref,
        basis.epoch_history_snapshot_ref,
    )
    expected_rows = issuance._issuance_model_manifest_inputs(basis)
    assert expected_rows == [
        artifacts.InputRef(
            artifact_id=ref.artifact_id,
            role=f"source[{index}]",
            manifest_profile_sha256=ref.manifest_profile_sha256,
        )
        for index, ref in enumerate(issuance._canonical_refs(tuple(writer_input_refs)))
    ]

    source_ref = _put(store, "unexpected-parent")
    extra_input = artifacts.input_ref_from_artifact_ref(
        source_ref,
        role="unexpected_parent",
    )
    raw = canon.to_canonical_bytes(basis.model_dump(mode="json"), issuance._CANON)
    expected_id = artifacts.ArtifactID("sha256:" + hashlib.sha256(raw).hexdigest())
    target_ids = {expected_id}
    reads: list[str] = []
    original_put_bytes = type(store).put_bytes
    original_get_bytes = type(store).get_bytes
    original_verify = type(store).verify
    emitted_refs: list[artifacts.ArtifactRef] = []

    def inject_extra_input(
        owner: artifacts.FileSystemCAS,
        data: bytes,
        options: artifacts.ArtifactWriteOptions,
        *args: object,
        **kwargs: object,
    ) -> artifacts.ArtifactRef:
        if options.kind == issuance._BASIS_KIND:
            options = replace(options, inputs=[*(options.inputs or ()), extra_input])
            kwargs["return_selected_profile"] = True
        ref = original_put_bytes(owner, data, options, *args, **kwargs)
        if options.kind == issuance._BASIS_KIND:
            emitted_refs.append(ref)
        return ref

    def record_get_bytes(owner: object, ref: object) -> bytes:
        if getattr(ref, "artifact_id", ref) in target_ids:
            reads.append("get_bytes")
        return original_get_bytes(owner, ref)

    def record_verify(owner: object, ref: object) -> object:
        if getattr(ref, "artifact_id", ref) in target_ids:
            reads.append("verify")
        return original_verify(owner, ref)

    monkeypatch.setattr(type(store), "put_bytes", inject_extra_input)
    monkeypatch.setattr(type(store), "get_bytes", record_get_bytes)
    monkeypatch.setattr(type(store), "verify", record_verify)
    owner = DecisionPacketEpochIssuanceOwner(store=store, root=tmp_path / "owner")

    with pytest.raises(CanonicalProfileRefusalError) as refused:
        owner._persist(basis, issuance._BASIS_KIND, input_refs=writer_input_refs)

    assert refused.value.code == "canon_profile_typed_artifact_profile_mismatch"
    assert len(emitted_refs) == 1
    assert emitted_refs[0].manifest_profile_sha256 is not None
    assert original_get_bytes(store, emitted_refs[0]) == raw
    assert store.get_manifest(emitted_refs[0]).inputs == [*expected_rows, extra_input]
    assert reads == []
