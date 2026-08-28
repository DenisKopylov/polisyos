from __future__ import annotations

import json
from pathlib import Path

from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from tools.ops_runners.runtime_cli import main


def test_keygen_creates_files_with_permissions(tmp_path: Path) -> None:
    base = tmp_path / "keys" / "polisyos-signing"

    code = main(["keygen", "--output", str(base)])

    assert code == 0
    private_path = base.with_suffix(".pem")
    public_path = base.with_suffix(".pub")
    assert private_path.exists()
    assert public_path.exists()
    assert private_path.stat().st_mode & 0o777 == 0o600
    assert public_path.stat().st_mode & 0o777 == 0o644


def test_keygen_no_overwrite_without_force(tmp_path: Path) -> None:
    base = tmp_path / "keys" / "polisyos-signing"

    assert main(["keygen", "--output", str(base)]) == 0
    assert main(["keygen", "--output", str(base)]) == 1


def test_sign_verify_cli_roundtrip(tmp_path: Path) -> None:
    cas_root = tmp_path / ".polisyos"
    store = FileSystemCAS(cas_root)
    ref = store.put_bytes(
        b"cli-roundtrip",
        PutOptions(kind="test.bytes", media_type="application/octet-stream"),
    )

    key_base = tmp_path / "keys" / "signing"
    trust_dir = tmp_path / "trust"
    revoked_dir = tmp_path / "revoked"
    trust_dir.mkdir(parents=True)
    revoked_dir.mkdir(parents=True)

    assert main(["keygen", "--output", str(key_base)]) == 0
    (trust_dir / "signing.pub").write_bytes((key_base.with_suffix(".pub")).read_bytes())

    sign_code = main(
        [
            "sign",
            str(ref.artifact_id),
            "--cas-root",
            str(cas_root),
            "--key",
            str(key_base.with_suffix(".pem")),
            "--identity",
            "ci-prod",
        ]
    )
    assert sign_code == 0

    verify_code = main(
        [
            "verify",
            str(ref.artifact_id),
            "--cas-root",
            str(cas_root),
            "--trust-dir",
            str(trust_dir),
            "--revoked-dir",
            str(revoked_dir),
        ]
    )
    assert verify_code == 0


def test_verify_fail_unsigned_exit_code(tmp_path: Path) -> None:
    cas_root = tmp_path / ".polisyos"
    store = FileSystemCAS(cas_root)
    ref = store.put_bytes(
        b"unsigned",
        PutOptions(kind="test.bytes", media_type="application/octet-stream"),
    )

    code_without_flag = main(
        [
            "verify",
            str(ref.artifact_id),
            "--cas-root",
            str(cas_root),
            "--trust-dir",
            str(tmp_path / "trust"),
            "--revoked-dir",
            str(tmp_path / "revoked"),
        ]
    )
    code_with_flag = main(
        [
            "verify",
            str(ref.artifact_id),
            "--cas-root",
            str(cas_root),
            "--trust-dir",
            str(tmp_path / "trust"),
            "--revoked-dir",
            str(tmp_path / "revoked"),
            "--fail-unsigned",
        ]
    )

    assert code_without_flag == 0
    assert code_with_flag == 1


def test_verify_all_json_output(capsys, tmp_path: Path) -> None:
    cas_root = tmp_path / ".polisyos"
    store = FileSystemCAS(cas_root)
    signed_ref = store.put_bytes(
        b"signed",
        PutOptions(kind="test.bytes", media_type="application/octet-stream"),
    )
    store.put_bytes(
        b"unsigned",
        PutOptions(kind="test.bytes", media_type="application/octet-stream"),
    )

    key_base = tmp_path / "keys" / "signing"
    trust_dir = tmp_path / "trust"
    revoked_dir = tmp_path / "revoked"
    trust_dir.mkdir(parents=True)
    revoked_dir.mkdir(parents=True)

    assert main(["keygen", "--output", str(key_base)]) == 0
    (trust_dir / "signing.pub").write_bytes((key_base.with_suffix(".pub")).read_bytes())
    assert (
        main(
            [
                "sign",
                str(signed_ref.artifact_id),
                "--cas-root",
                str(cas_root),
                "--key",
                str(key_base.with_suffix(".pem")),
            ]
        )
        == 0
    )
    _ = capsys.readouterr()

    code = main(
        [
            "verify",
            "--all",
            "--cas-root",
            str(cas_root),
            "--trust-dir",
            str(trust_dir),
            "--revoked-dir",
            str(revoked_dir),
            "--json",
        ]
    )
    captured = capsys.readouterr()

    assert code == 0
    payload = json.loads(captured.out)
    assert payload["total"] == 2
    assert payload["valid"] == 1
    assert payload["unsigned"] == 1
