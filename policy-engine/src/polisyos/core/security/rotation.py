"""Secret and trust-anchor rotation helpers for runtime security operations."""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from polisyos.common.serialization import fast_json_dumps
from polisyos.core.artifacts.signing import (
    DEFAULT_IDENTITIES_PATH,
    DEFAULT_REVOKED_DIR,
    DEFAULT_TRUST_DIR,
    KeyPair,
)

DEFAULT_JWT_TRUST_ANCHORS_PATH = Path(".polisyos/security/jwt-trust-anchors.json")


@dataclass(frozen=True, slots=True)
class JWTRotationResult:
    """Result of updating the JWT trust-anchor rotation manifest."""

    manifest_path: Path
    issuer: str
    jwks_uri: str
    audience: str
    active_kids: tuple[str, ...]
    next_kids: tuple[str, ...]
    retired_kids: tuple[str, ...]
    revoked_kids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest_path": str(self.manifest_path),
            "issuer": self.issuer,
            "jwks_uri": self.jwks_uri,
            "audience": self.audience,
            "active_kids": list(self.active_kids),
            "next_kids": list(self.next_kids),
            "retired_kids": list(self.retired_kids),
            "revoked_kids": list(self.revoked_kids),
        }


@dataclass(frozen=True, slots=True)
class Ed25519RotationResult:
    """Result of generating and trusting a new Ed25519 signing key."""

    key_id: str
    private_key_path: Path
    public_key_path: Path
    trusted_key_path: Path
    identities_path: Path
    revoked_key_paths: tuple[Path, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "key_id": self.key_id,
            "private_key_path": str(self.private_key_path),
            "public_key_path": str(self.public_key_path),
            "trusted_key_path": str(self.trusted_key_path),
            "identities_path": str(self.identities_path),
            "revoked_key_paths": [str(path) for path in self.revoked_key_paths],
        }


def update_jwt_trust_anchor_manifest(
    *,
    manifest_path: Path | str = DEFAULT_JWT_TRUST_ANCHORS_PATH,
    issuer: str,
    jwks_uri: str,
    audience: str,
    active_kids: tuple[str, ...] = (),
    next_kids: tuple[str, ...] = (),
    retire_kids: tuple[str, ...] = (),
    revoke_kids: tuple[str, ...] = (),
    rotated_by: str | None = None,
) -> JWTRotationResult:
    """Update the operator manifest used to coordinate JWT signing-key rotation."""
    path = Path(manifest_path)
    current = _read_json_object(path)
    previous_active = _as_tuple(current.get("active_kids"))
    previous_next = _as_tuple(current.get("next_kids"))
    previous_retired = _as_tuple(current.get("retired_kids"))
    previous_revoked = _as_tuple(current.get("revoked_kids"))

    active = _dedupe((*previous_active, *active_kids))
    next_values = _dedupe((*previous_next, *next_kids))
    retired = _dedupe((*previous_retired, *retire_kids))
    revoked = _dedupe((*previous_revoked, *revoke_kids))

    active = tuple(kid for kid in active if kid not in retired and kid not in revoked)
    next_values = tuple(kid for kid in next_values if kid not in retired and kid not in revoked)
    retired = tuple(kid for kid in retired if kid not in revoked)

    now = datetime.now(UTC).isoformat()
    history = current.get("history")
    if not isinstance(history, list):
        history = []
    history.append(
        {
            "updated_at": now,
            "rotated_by": rotated_by or "",
            "active_kids": list(active_kids),
            "next_kids": list(next_kids),
            "retire_kids": list(retire_kids),
            "revoke_kids": list(revoke_kids),
        }
    )
    manifest = {
        "schema_version": "1",
        "updated_at": now,
        "issuer": issuer,
        "jwks_uri": jwks_uri,
        "audience": audience,
        "active_kids": list(active),
        "next_kids": list(next_values),
        "retired_kids": list(retired),
        "revoked_kids": list(revoked),
        "history": history,
    }
    _atomic_write_json(path, manifest)
    return JWTRotationResult(
        manifest_path=path,
        issuer=issuer,
        jwks_uri=jwks_uri,
        audience=audience,
        active_kids=active,
        next_kids=next_values,
        retired_kids=retired,
        revoked_kids=revoked,
    )


def rotate_ed25519_signing_key(
    *,
    key_base: Path | str,
    identity: str,
    trust_dir: Path | str = DEFAULT_TRUST_DIR,
    identities_path: Path | str = DEFAULT_IDENTITIES_PATH,
    revoked_dir: Path | str = DEFAULT_REVOKED_DIR,
    revoke_public_keys: tuple[Path | str, ...] = (),
    force: bool = False,
) -> Ed25519RotationResult:
    """Generate a new signer, trust its public key, and optionally revoke old keys."""
    keypair = KeyPair.generate()
    base = Path(key_base).expanduser()
    private_path = base.with_suffix(".pem")
    public_path = base.with_suffix(".pub")
    trusted_path = Path(trust_dir) / public_path.name
    revoked_root = Path(revoked_dir)

    _write_secret_file(private_path, keypair.private_pem(), mode=0o600, force=force)
    _write_public_file(public_path, keypair.public_pem(), mode=0o644, force=force)
    _write_public_file(trusted_path, keypair.public_pem(), mode=0o644, force=True)

    identities = _read_json_object(Path(identities_path))
    identities[keypair.key_id] = identity
    _atomic_write_json(Path(identities_path), identities)

    revoked_paths: list[Path] = []
    for source in revoke_public_keys:
        source_path = Path(source).expanduser()
        target_path = revoked_root / source_path.name
        _write_public_file(target_path, source_path.read_bytes(), mode=0o644, force=True)
        revoked_paths.append(target_path)

    return Ed25519RotationResult(
        key_id=keypair.key_id,
        private_key_path=private_path,
        public_key_path=public_path,
        trusted_key_path=trusted_path,
        identities_path=Path(identities_path),
        revoked_key_paths=tuple(revoked_paths),
    )


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected object JSON at {path}")
    return payload


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    _atomic_write_bytes(path, (fast_json_dumps(payload, sort_keys=True) + "\n").encode("utf-8"), 0o644)


def _write_secret_file(path: Path, data: bytes, *, mode: int, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"Refusing to overwrite existing secret file: {path}")
    _atomic_write_bytes(path, data, mode)


def _write_public_file(path: Path, data: bytes, *, mode: int, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"Refusing to overwrite existing public file: {path}")
    _atomic_write_bytes(path, data, mode)


def _atomic_write_bytes(path: Path, data: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=str(path.parent), delete=False) as handle:
        tmp_path = Path(handle.name)
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp_path, path)
    os.chmod(path, mode)


def _as_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


def _dedupe(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value.strip() for value in values if value.strip()))


__all__ = [
    "DEFAULT_JWT_TRUST_ANCHORS_PATH",
    "Ed25519RotationResult",
    "JWTRotationResult",
    "rotate_ed25519_signing_key",
    "update_jwt_trust_anchor_manifest",
]
