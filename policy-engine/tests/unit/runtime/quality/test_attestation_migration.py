"""Replay actual old writer bytes, rather than relabeling new diagnostic data.

The 16,926-byte test archive contains a small real CAS/control-event root emitted
by the unchanged legacy writer on Main 8534fafd7f2564d22754402b9c56d40236fe3558,
tree b6dbb0c6a2a43b01a7425dc061d2eae9c25bd97c. Its legacy production labels
are historical producer declarations, not an institutional verification witness.
The capture command, measurement and 434 actual Main source origins are retained
in _cache/e02/canary-attestation-repair-20261116/main-pinned{,-run}.
"""

from __future__ import annotations

import hashlib
import json
import tarfile
from dataclasses import replace
from pathlib import Path

import pytest

from polisyos.core.artifacts import ArtifactRef, PutOptions, SchemaInfo
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.runtime.http.services.control.artifacts import (
    verify_runtime_authority_artifact_identity,
    write_runtime_authority_artifact,
)
from polisyos.runtime.quality.attestation import (
    DIAGNOSTIC_ATTESTATION_SCHEMA_VERSION,
    evaluate_trust_boundary_attestation,
)
from tests.unit.runtime.quality.test_authority_reconciliation import (
    _opts,
    _runtime_context,
    _stores,
)

_ARCHIVE = (
    Path(__file__).resolve().parents[3] / "fixtures/runtime_quality/attestation_v1_writer.tar.gz"
)
_ARCHIVE_SHA256 = "d51938f8fdd033a2abc547209af9f69967f6c36ad266a843a12e12daed97b60d"
_PAYLOAD = {"status": "pass", "claims": [{"claim_id": "claim-1"}]}


def _cas_bytes(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and (path.suffix == ".blob" or path.name.endswith(".manifest.json"))
    }


def test_actual_legacy_writer_restarts_without_reissuing_refs_or_events(tmp_path: Path) -> None:
    assert hashlib.sha256(_ARCHIVE.read_bytes()).hexdigest() == _ARCHIVE_SHA256
    with tarfile.open(_ARCHIVE) as archive:
        archive.extractall(tmp_path, filter="data")
    captured = json.loads((tmp_path / "legacy-capture.json").read_text())
    root = tmp_path / "legacy-root"
    immutable_before = _cas_bytes(root / "cas")
    expected_ref = ArtifactRef.model_validate(captured["result_ref"])
    for _restart in range(2):
        store, log = _stores(root)
        try:
            result = write_runtime_authority_artifact(
                store,
                log,
                _PAYLOAD,
                _opts(captured["source_ref"]),
                **_runtime_context(captured["source_ref"]),
            )
            assert result.cas_ref == expected_ref
            assert result.authority_envelope_ref.model_dump(mode="json") == captured["envelope_ref"]
            assert result.diagnostic_event_ref.model_dump(mode="json") == captured["event_ref"]
            assert result.identity_context.attestation_ref == captured["attestation_ref"]
            assert len(log.list_events(run_id="run-wave-2", job_id="job-wave-2")) == 1
            old = from_canonical_bytes(store.get_bytes(captured["attestation_ref"]))
            assert old["schema_version"] == "polisyos.runtime.attestation.v1"
            assert old["consumer_verification"] == "verified"
            assert not evaluate_trust_boundary_attestation(
                boundary_id="cas_writer", attestations=[old]
            ).production_closeout_satisfied
            verify_runtime_authority_artifact_identity(
                store,
                artifact_id=expected_ref,
                opts=_opts(captured["source_ref"]),
                expected_context=result.identity_context,
            )
            with pytest.raises(ValueError, match="existing authority identity mismatch"):
                verify_runtime_authority_artifact_identity(
                    store,
                    artifact_id=expected_ref,
                    opts=_opts(captured["source_ref"]),
                    expected_context=replace(result.identity_context, job_id="another-job"),
                )
        finally:
            log._store.close()
        assert _cas_bytes(root / "cas") == immutable_before


def test_fresh_writer_emits_only_diagnostic_profile_and_reuses_it(tmp_path: Path) -> None:
    store, log = _stores(tmp_path)
    try:
        source = store.put_json(
            {"source": "runtime-input"},
            PutOptions(kind="runtime.input", media_type="application/json"),
        )
        result = write_runtime_authority_artifact(
            store,
            log,
            _PAYLOAD,
            _opts(str(source.artifact_id)),
            **_runtime_context(str(source.artifact_id)),
        )
        ref = result.identity_context.attestation_ref
        assert ref is not None
        body = from_canonical_bytes(store.get_bytes(ref))
        assert body["schema_version"] == DIAGNOSTIC_ATTESTATION_SCHEMA_VERSION
        assert store.get_manifest(ref).artifact_schema.version == "1.1"
        assert body["consumer_verification"] == "not_verified"
        assert body["tamper_check_status"] == "not_checked"
        assert body["isolation_status"] == "unknown"
        assert "signature_ref" not in body
        assert body["observed_materials"] == body["observed_products"] == []
        assert body["metadata"]["authority_role"] == "diagnostic_only"
        assert body["metadata"]["predicate_class"] == "not_established"
        before = _cas_bytes(tmp_path / "cas")
        repeated = write_runtime_authority_artifact(
            store,
            log,
            _PAYLOAD,
            _opts(str(source.artifact_id)),
            **_runtime_context(str(source.artifact_id)),
        )
        assert repeated == result
        assert _cas_bytes(tmp_path / "cas") == before
        assert len(log.list_events(run_id="run-wave-2", job_id="job-wave-2")) == 1
    finally:
        log._store.close()


@pytest.mark.parametrize("schema_version", ["1.0", "9.0"])
def test_retained_writer_refuses_mixed_or_unknown_attestation_format(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, schema_version: str
) -> None:
    from polisyos.runtime.http.services.control import artifacts as owner
    from polisyos.runtime.http.services.control.artifacts import (
        _cas_writer_attestation_write_options,
    )

    store, log = _stores(tmp_path)
    try:
        source = store.put_json(
            {"source": "runtime-input"},
            PutOptions(kind="runtime.input", media_type="application/json"),
        )
        opts = _opts(str(source.artifact_id))
        result = write_runtime_authority_artifact(
            store, log, _PAYLOAD, opts, **_runtime_context(str(source.artifact_id))
        )
        ref = result.identity_context.attestation_ref
        body = from_canonical_bytes(store.get_bytes(ref))
        write_options = _cas_writer_attestation_write_options(
            producer=opts.producer, tenant_id="tenant-1", cell_id="cell-a"
        )
        alternate = store.put_json(
            body,
            replace(
                write_options,
                schema=SchemaInfo(
                    name="polisyos.runtime.quality.AttestationRecord", version=schema_version
                ),
            ),
            CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        assert str(alternate.artifact_id) == ref
        assert store.get_manifest(alternate).artifact_schema.version == schema_version
        actual_read = owner.read_core_manifest_profile

        def selected_bad_attestation(view, selector):
            # Script only selection of a genuinely persisted alternate profile;
            # all selected bytes/manifest parsing still use the real CAS owner.
            if str(getattr(selector, "artifact_id", selector)) == ref:
                return actual_read(view, alternate)
            return actual_read(view, selector)

        monkeypatch.setattr(owner, "read_core_manifest_profile", selected_bad_attestation)
        with pytest.raises(ValueError, match="existing authority identity mismatch"):
            verify_runtime_authority_artifact_identity(
                store,
                artifact_id=result.cas_ref,
                opts=opts,
                expected_context=result.identity_context,
            )
    finally:
        log._store.close()
