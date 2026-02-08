from __future__ import annotations

import io
import tarfile
from pathlib import Path

from polisyos.core.artifacts.manifest import InputRef
from polisyos.core.artifacts.signing import Ed25519Signer, KeyPair
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.audit import (
    AuditPackageAssembler,
    AuditPackageVerifier,
    ExportOptions,
    ExportProfile,
    SigningPolicy,
    StepStatus,
    render_markdown,
)
from polisyos.core.run.context import RunContext


def _build_signed_run(tmp_path: Path) -> tuple[FileSystemCAS, str, Path]:
    store = FileSystemCAS(tmp_path / ".polisyos")
    registry_ref = store.put_json(
        {"registry": {"version": 1}},
        PutOptions(kind="core.registry_bundle", media_type="application/json"),
    )
    run_id = "R_audit_test"
    run = RunContext.start(store=store, registry_bundle=registry_ref, run_id=run_id)

    source = store.put_json(
        {"source": True},
        PutOptions(kind="fabric.data_snapshot", media_type="application/json"),
    )
    packet = store.put_json(
        {
            "schema_version": "3.0",
            "run_id": run_id,
            "inputs": {"data_snapshot_ref": str(source.artifact_id)},
            "artifacts": {},
        },
        PutOptions(
            kind="scientist.decision_packet",
            media_type="application/json",
            inputs=[InputRef(artifact_id=source.artifact_id, role="input.data_snapshot_ref")],
        ),
    )
    run.add_output(packet)
    run.finalize("ok")

    keypair = KeyPair.generate()
    signer = Ed25519Signer.from_pem(keypair.private_pem())
    store.sign_all_artifacts(signer, only_unsigned=False, max_workers=2)

    trusted_dir = tmp_path / "trusted"
    trusted_dir.mkdir(parents=True, exist_ok=True)
    (trusted_dir / "audit.pub").write_bytes(keypair.public_pem())
    return store, run_id, trusted_dir


def test_audit_export_and_verify_full(tmp_path: Path) -> None:
    store, run_id, trusted_dir = _build_signed_run(tmp_path)
    assembler = AuditPackageAssembler(
        cas=store,
        runs_dir=store.root / "runs",
        options=ExportOptions(
            profile=ExportProfile.FULL,
            signing_policy=SigningPolicy.STRICT,
        ),
    )
    result = assembler.export(run_id, tmp_path / "audit_full")
    assert result.archive_path.exists()

    verifier = AuditPackageVerifier(trusted_keys_dir=trusted_dir)
    report = verifier.verify(result.archive_path)
    assert report.overall_status == "PASS"
    assert report.failures == []
    assert "Overall Status" in render_markdown(report)


def test_audit_export_and_verify_manifests_only(tmp_path: Path) -> None:
    store, run_id, trusted_dir = _build_signed_run(tmp_path)
    assembler = AuditPackageAssembler(
        cas=store,
        runs_dir=store.root / "runs",
        options=ExportOptions(
            profile=ExportProfile.MANIFESTS_ONLY,
            signing_policy=SigningPolicy.STRICT,
        ),
    )
    result = assembler.export(run_id, tmp_path / "audit_manifests")
    verifier = AuditPackageVerifier(trusted_keys_dir=trusted_dir)
    report = verifier.verify(result.archive_path)
    assert report.overall_status == "PASS"
    assert report.cas_integrity.status in {StepStatus.WARN, StepStatus.SKIP}


def test_audit_verify_requires_trust_anchor_by_default(tmp_path: Path) -> None:
    store, run_id, _ = _build_signed_run(tmp_path)
    assembler = AuditPackageAssembler(
        cas=store,
        runs_dir=store.root / "runs",
        options=ExportOptions(profile=ExportProfile.FULL, signing_policy=SigningPolicy.STRICT),
    )
    result = assembler.export(run_id, tmp_path / "audit_untrusted")

    report = AuditPackageVerifier().verify(result.archive_path)
    assert report.overall_status == "FAIL"
    assert any(item.code == "UNTRUSTED_KEY" for item in report.failures)


def test_audit_verify_require_slsa_fails_for_legacy_package(tmp_path: Path) -> None:
    store, run_id, trusted_dir = _build_signed_run(tmp_path)
    assembler = AuditPackageAssembler(
        cas=store,
        runs_dir=store.root / "runs",
        options=ExportOptions(
            profile=ExportProfile.FULL,
            signing_policy=SigningPolicy.STRICT,
            slsa_mode="off",
        ),
    )
    result = assembler.export(run_id, tmp_path / "audit_no_slsa")

    report = AuditPackageVerifier(
        trusted_keys_dir=trusted_dir,
        require_slsa=True,
    ).verify(result.archive_path)
    assert report.overall_status == "FAIL"
    assert any(item.code == "SLSA_MISSING" for item in report.failures)


def test_audit_export_with_local_slsa_and_verify(tmp_path: Path) -> None:
    store, run_id, trusted_dir = _build_signed_run(tmp_path)
    assembler = AuditPackageAssembler(
        cas=store,
        runs_dir=store.root / "runs",
        options=ExportOptions(
            profile=ExportProfile.FULL,
            signing_policy=SigningPolicy.STRICT,
            slsa_mode="local",
            slsa_policy="required",
        ),
    )
    result = assembler.export(run_id, tmp_path / "audit_with_slsa")

    report = AuditPackageVerifier(
        trusted_keys_dir=trusted_dir,
        require_slsa=True,
    ).verify(result.archive_path)
    assert report.overall_status == "PASS"
    assert report.slsa_verification.status == StepStatus.PASS


def test_audit_verify_blocks_path_traversal_archive(tmp_path: Path) -> None:
    archive = tmp_path / "malicious.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        payload = b"owned"
        info = tarfile.TarInfo("../evil.txt")
        info.size = len(payload)
        tar.addfile(info, io.BytesIO(payload))

    report = AuditPackageVerifier().verify(archive)
    assert report.overall_status == "FAIL"
    assert any(item.code == "UNSAFE_ARCHIVE" for item in report.failures)
