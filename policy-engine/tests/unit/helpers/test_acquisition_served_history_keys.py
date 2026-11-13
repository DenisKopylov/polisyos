"""Retained fixture institution keys survive a fresh demo deployment."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.core import artifacts
from tests._helpers.acquisition_served_history import _existing_key_config, _key_config


def _key_bytes(root: Path) -> dict[str, bytes]:
    return {path.name: path.read_bytes() for path in root.iterdir() if path.is_file()}


def test_existing_keys_reopen_exact_institutions_without_writes(tmp_path: Path) -> None:
    original = SimpleNamespace(raw={})
    original_signers, original_identities = _key_config(tmp_path, original)
    before = _key_bytes(tmp_path)
    fresh = SimpleNamespace(raw={})

    signers, identities = _existing_key_config(tmp_path, fresh)

    assert _key_bytes(tmp_path) == before
    assert identities == original_identities
    assert {name: signer.key_id for name, signer in signers.items()} == {
        name: signer.key_id for name, signer in original_signers.items()
    }
    assert fresh.raw == original.raw
    assert fresh.raw["acquisition_authority"]["mandates"] == []


def test_existing_keys_refuse_missing_institution_without_repair(tmp_path: Path) -> None:
    _key_config(tmp_path, SimpleNamespace(raw={}))
    (tmp_path / "custody.pem").unlink()
    before = _key_bytes(tmp_path)
    fresh = SimpleNamespace(raw={})

    with pytest.raises(FileNotFoundError):
        _existing_key_config(tmp_path, fresh)

    assert fresh.raw == {}
    assert _key_bytes(tmp_path) == before


def test_existing_keys_refuse_foreign_public_key_without_repair(tmp_path: Path) -> None:
    _key_config(tmp_path, SimpleNamespace(raw={}))
    (tmp_path / "owner.pub").write_bytes(artifacts.KeyPair.generate().public_pem())
    before = _key_bytes(tmp_path)
    fresh = SimpleNamespace(raw={})

    with pytest.raises(ValueError, match="retained_fixture_institution_key_pair_mismatch"):
        _existing_key_config(tmp_path, fresh)

    assert fresh.raw == {}
    assert _key_bytes(tmp_path) == before
