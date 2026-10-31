"""Actual Runtime-owned bounded binary transport and independent Core checks."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

import pytest

from polisyos.core.artifacts import (
    ArtifactReadBoundsError,
    ArtifactRef,
    ArtifactWriteOptions,
    CoreJsonReadLimits,
    FileSystemCAS,
    read_core_json_artifact_bounded,
    read_core_manifest_profile_bounded,
)
from polisyos.core.artifacts.child_release import ChildReleaseUnavailableError
from polisyos.runtime.http.resilience import ChildGuardedReadOwner
from tests.unit.runtime.http.test_guarded_child_control_bridge import _run_owned_fixture

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    "probe",
    [
        "normal",
        "oversize",
        "manifest",
        "grown_manifest",
        "bytes",
        "receipt",
        "usage",
        "unsealed",
        "registration",
    ],
)
def test_actual_guarded_binary_transport_keeps_limits_and_receipts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, probe: str
) -> None:
    """A real worker/CAS appointment never falls back to an unbounded read."""

    def exercise(root, _control, custody, reader, fence, _grant, binding):
        intent = custody.job_session_intent(binding)
        custody.bind_job_intent(intent, fence.begin_session(intent))
        managed = custody.parent_store(binding, input_refs=())
        payload = b"actual bounded binary payload"
        ref = managed.put_bytes(
            payload,
            ArtifactWriteOptions(kind="tests.binary", media_type="application/octet-stream"),
            return_selected_profile=True,
        )
        selected = read_core_manifest_profile_bounded(
            managed, ref, max_manifest_bytes=100000, allow_profile_absent=True
        )
        if probe == "manifest":
            other = managed.put_bytes(
                b"other bytes",
                ArtifactWriteOptions(kind="tests.binary", media_type="application/octet-stream"),
                return_selected_profile=True,
            )
            selected = read_core_manifest_profile_bounded(
                managed, other, max_manifest_bytes=100000, allow_profile_absent=True
            )
        unbounded = FileSystemCAS.get_bytes
        service_read = ChildGuardedReadOwner.read_blob_bounded
        entered = []

        def reject_selected_unbounded(store, artifact_id):
            actual_id = (
                artifact_id.artifact_id if isinstance(artifact_id, ArtifactRef) else artifact_id
            )
            if str(actual_id) == str(ref.artifact_id):
                pytest.fail("bounded child transport called get_bytes for the binary source")
            return unbounded(store, artifact_id)

        def altered_service(owner, capability, **options):
            assert options["max_manifest_bytes"] == len(selected.raw_manifest_bytes)
            actual, receipt, usage = service_read(owner, capability, **options)
            entered.append(True)
            if probe == "bytes":
                actual = b"X" + actual[1:]
            elif probe == "receipt":
                receipt = replace(receipt, sha256="0" * 64)
            elif probe == "usage":
                usage = replace(usage, observed_payload_bytes=len(actual) + 1)
            elif probe == "unsealed":
                usage = replace(usage, _seal=None)
            elif probe == "registration":
                owner._stage_proxy._guard._timeout_seconds += 1
            return actual, receipt, usage

        with monkeypatch.context() as patch:
            patch.setattr(FileSystemCAS, "get_bytes", reject_selected_unbounded)
            patch.setattr(ChildGuardedReadOwner, "read_blob_bounded", altered_service)
            if probe == "normal":
                actual, usage = managed._read_owned_blob_bounded(
                    ref, manifest_read=selected, max_member_bytes=len(payload)
                )
                assert actual == payload
                assert entered == [True]
                assert usage.observed_manifest_selection_bytes == 0
                assert usage.observed_manifest_verification_bytes == len(
                    selected.raw_manifest_bytes
                )
                assert usage.observed_payload_bytes == usage.observed_payload_size == len(payload)
                assert usage.observed_source_bytes == len(selected.raw_manifest_bytes) + len(
                    payload
                )
                assert usage.payload_integrity_verified
                assert not reader.has_unsettled_operations()
            elif probe == "oversize":
                with pytest.raises(ArtifactReadBoundsError, match="read_limit_exceeded"):
                    managed._read_owned_blob_bounded(
                        ref, manifest_read=selected, max_member_bytes=1
                    )
                assert not entered
            elif probe == "manifest":
                with pytest.raises(ChildReleaseUnavailableError, match="selection_invalid"):
                    managed._read_owned_blob_bounded(
                        ref, manifest_read=selected, max_member_bytes=len(payload)
                    )
                assert not entered
            elif probe == "grown_manifest":
                path = custody._stage._manifest_path_for_ref(
                    ref.artifact_id, ref.manifest_profile_sha256
                )
                original = path.read_bytes()
                replacement = path.with_name(path.name + ".probe")
                replacement.write_bytes(original + b" " * 16)
                replacement.replace(path)
                try:
                    with pytest.raises(ArtifactReadBoundsError, match="read_limit_exceeded"):
                        managed._read_owned_blob_bounded(
                            ref, manifest_read=selected, max_member_bytes=len(payload)
                        )
                finally:
                    replacement.write_bytes(original)
                    replacement.replace(path)
                assert not entered
            elif probe == "registration":
                with pytest.raises(ValueError, match="guard_binding_changed"):
                    managed._read_owned_blob_bounded(
                        ref, manifest_read=selected, max_member_bytes=len(payload)
                    )
                assert entered == [True]
            else:
                with pytest.raises(ChildReleaseUnavailableError, match="receipt_mismatch"):
                    managed._read_owned_blob_bounded(
                        ref, manifest_read=selected, max_member_bytes=len(payload)
                    )
                assert entered == [True]

    _run_owned_fixture(tmp_path, monkeypatch, "runtime_core_bootstrap", before_session=exercise)


@pytest.mark.parametrize("primed", [True, False])
def test_actual_guarded_json_reuses_the_selected_manifest_without_a_hidden_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, primed: bool
) -> None:
    """A supplied sealed selection prevents a second uncharged selection read."""

    def exercise(_root, _control, custody, _reader, fence, _grant, binding):
        intent = custody.job_session_intent(binding)
        custody.bind_job_intent(intent, fence.begin_session(intent))
        managed = custody.parent_store(binding, input_refs=())
        ref = managed.put_json(
            {"value": 4},
            ArtifactWriteOptions(kind="tests.json", media_type="application/json"),
            return_selected_profile=True,
        )
        selected = read_core_manifest_profile_bounded(managed, ref, max_manifest_bytes=100000)
        raw_read = FileSystemCAS.read_raw_manifest_bytes_bounded
        selections = []

        def observe_selection(owner, artifact_id, **options):
            actual_id = (
                artifact_id.artifact_id if isinstance(artifact_id, ArtifactRef) else artifact_id
            )
            if str(actual_id) == str(ref.artifact_id):
                selections.append(True)
            return raw_read(owner, artifact_id, **options)

        limits = CoreJsonReadLimits(
            max_bytes=selected.manifest.byte_size,
            max_depth=20,
            max_elements=100,
            max_manifest_bytes=len(selected.raw_manifest_bytes),
        )
        with monkeypatch.context() as patch:
            patch.setattr(FileSystemCAS, "read_raw_manifest_bytes_bounded", observe_selection)
            result = read_core_json_artifact_bounded(
                managed, ref, limits=limits, manifest_read=selected if primed else None
            )
        assert result.value == {"value": 4}
        assert selections == ([] if primed else [True])
        assert result.observed_manifest_verification_bytes == len(selected.raw_manifest_bytes)
        assert result.observed_payload_bytes == selected.manifest.byte_size

    _run_owned_fixture(tmp_path, monkeypatch, "runtime_core_bootstrap", before_session=exercise)
