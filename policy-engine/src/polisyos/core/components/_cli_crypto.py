"""CLI sub-module: cryptographic key management, signing and verification commands."""

from __future__ import annotations

import json
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.signing import (
    DEFAULT_IDENTITIES_PATH,
    DEFAULT_PRIVATE_KEY_ENV,
    DEFAULT_PRIVATE_KEY_FILE_ENV,
    DEFAULT_PRIVATE_KEY_PATH,
    DEFAULT_REVOKED_DIR,
    DEFAULT_TRUST_DIR,
    Ed25519Signer,
    Ed25519Verifier,
    KeyPair,
    SignatureVerificationStatus,
    ensure_private_key_permissions,
    safe_short_key_id,
)
from polisyos.core.artifacts.store import FileSystemCAS

_SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")

__all__ = [
    "_cmd_keygen",
    "_cmd_sign",
    "_cmd_verify",
    "_normalize_artifact_ref",
    "_resolve_key_paths",
    "_write_private_key",
    "_write_public_key",
    "_SHA256_HEX_RE",
]


def _normalize_artifact_ref(value: str) -> ArtifactID:
    if value.startswith("sha256:"):
        return ArtifactID.model_validate(value)
    if _SHA256_HEX_RE.fullmatch(value):
        return ArtifactID.from_sha256_hex(value)
    raise ValueError(f"Invalid artifact reference: {value}")


def _resolve_key_paths(output: str) -> tuple[Path, Path]:
    base = Path(output).expanduser()
    if base.suffix in {".pem", ".pub"}:
        base = base.with_suffix("")
    return base.with_suffix(".pem"), base.with_suffix(".pub")


def _write_private_key(path: Path, data: bytes, *, force: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not force and path.exists():
        raise FileExistsError(f"Private key exists: {path}")

    if force:
        tmp_path = path.with_suffix(path.suffix + f".tmp-{uuid.uuid4().hex}")
        fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, path)
            os.chmod(path, 0o600)
        finally:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
        return

    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def _write_public_key(path: Path, data: bytes, *, force: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not force and path.exists():
        raise FileExistsError(f"Public key exists: {path}")
    tmp_path = path.with_suffix(path.suffix + f".tmp-{uuid.uuid4().hex}")
    with open(tmp_path, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp_path, path)
    os.chmod(path, 0o644)


def _cmd_keygen(args: Any) -> int:
    keypair = KeyPair.generate()
    if args.public_only:
        public_pem = keypair.public_pem().decode("utf-8")
        if args.json:
            payload = {
                "key_id": keypair.key_id,
                "public_key": public_pem,
                "name": args.name,
            }
            print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
        else:
            print(public_pem)
        return 0

    private_path, public_path = _resolve_key_paths(args.output)
    try:
        _write_private_key(private_path, keypair.private_pem(), force=bool(args.force))
        _write_public_key(public_path, keypair.public_pem(), force=bool(args.force))
    except FileExistsError as exc:
        print(f"ERROR: {exc}. Use --force to overwrite.", file=sys.stderr)
        return 1

    private_mode = oct(private_path.stat().st_mode & 0o777)
    public_mode = oct(public_path.stat().st_mode & 0o777)
    payload = {
        "private_key": str(private_path),
        "private_mode": private_mode,
        "public_key": str(public_path),
        "public_mode": public_mode,
        "key_id": keypair.key_id,
        "name": args.name,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    else:
        print("Ed25519 key pair generated")
        print(f"  Private key: {private_path} (mode: {private_mode})")
        print(f"  Public key:  {public_path} (mode: {public_mode})")
        print(f"  Key ID:      {keypair.key_id}")
        if args.name:
            print(f"  Identity:    {args.name}")
    return 0


def _cmd_sign(args: Any) -> int:
    if args.all and args.artifact_ref:
        print("ERROR: artifact_ref cannot be used with --all", file=sys.stderr)
        return 2
    if not args.all and not args.artifact_ref:
        print("ERROR: artifact_ref is required unless --all is set", file=sys.stderr)
        return 2

    try:
        if args.key:
            key_path = Path(args.key).expanduser()
            ok, warning = ensure_private_key_permissions(key_path)
            if not ok and warning:
                print(f"WARNING: {warning}", file=sys.stderr)
            signer = Ed25519Signer.from_path(key_path)
        else:
            signer = Ed25519Signer.from_env_or_file(
                private_key_env=DEFAULT_PRIVATE_KEY_ENV,
                private_key_file_env=DEFAULT_PRIVATE_KEY_FILE_ENV,
                default_private_key_file=DEFAULT_PRIVATE_KEY_PATH,
            )
    except Exception as exc:
        print(f"ERROR: cannot load private signing key: {exc}", file=sys.stderr)
        return 2

    store = FileSystemCAS(Path(args.cas_root))
    identity = args.identity

    if args.all:
        report = store.sign_all_artifacts(
            signer,
            signer_identity=identity,
            only_unsigned=not bool(args.resign),
            max_workers=max(1, int(args.workers)),
        )
        if args.json:
            print(report.model_dump_json(indent=2))
        else:
            print(
                f"signed={report.signed} skipped={report.skipped} "
                f"errors={report.errors} total={report.total}"
            )
        return 0 if report.errors == 0 else 1

    try:
        artifact_id = _normalize_artifact_ref(args.artifact_ref)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if store.has_signature(artifact_id) and not args.resign:
        if args.json:
            payload = {
                "artifact_id": str(artifact_id),
                "status": "skipped",
                "message": "already signed",
            }
            print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
        else:
            print(f"Already signed: {artifact_id}")
        return 0

    try:
        sig = store.sign_artifact(artifact_id, signer, signer_identity=identity)
    except Exception as exc:
        print(f"ERROR: signing failed for {artifact_id}: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(sig.model_dump_json(indent=2, exclude_none=True))
    else:
        print(f"Signed {artifact_id} with key {safe_short_key_id(sig.key_id)}")
    return 0


def _cmd_verify(args: Any) -> int:
    if args.all and args.artifact_ref:
        print("ERROR: artifact_ref cannot be used with --all", file=sys.stderr)
        return 2
    if not args.all and not args.artifact_ref:
        print("ERROR: artifact_ref is required unless --all is set", file=sys.stderr)
        return 2

    store = FileSystemCAS(Path(args.cas_root))
    verifier = Ed25519Verifier(strict_identity=bool(args.strict_identity))

    try:
        verifier.load_trust_dir(Path(args.trust_dir))
        verifier.load_revoked_dir(Path(args.revoked_dir))
        verifier.load_identity_bindings(Path(args.identities))
        for key_path in args.public_key:
            verifier.load_trusted_key_file(Path(key_path).expanduser())
    except Exception as exc:
        print(f"ERROR: failed to initialize trust store: {exc}", file=sys.stderr)
        return 2

    if args.all:
        report = store.verify_all_signatures(
            verifier,
            max_workers=max(1, int(args.workers)),
            strict_identity=bool(args.strict_identity),
        )
        if not args.quiet:
            if args.json:
                print(report.model_dump_json(indent=2))
            else:
                print(
                    f"valid={report.valid} unsigned={report.unsigned} invalid={report.invalid} "
                    f"untrusted={report.untrusted} revoked={report.revoked} "
                    f"errors={report.errors} total={report.total}"
                )
        if report.invalid or report.untrusted or report.revoked or report.errors:
            return 1
        if args.fail_unsigned and report.unsigned:
            return 1
        return 0

    try:
        artifact_id = _normalize_artifact_ref(args.artifact_ref)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    result = store.verify_signature(
        artifact_id,
        verifier,
        strict_identity=bool(args.strict_identity),
    )
    if not args.quiet:
        if args.json:
            print(result.model_dump_json(indent=2, exclude_none=True))
        else:
            print(f"status={result.status.value} artifact={result.artifact_id}")
            if result.key_id:
                print(f"key_id={result.key_id}")
            if result.signer_identity:
                print(f"signer_identity={result.signer_identity}")
            if result.expected_identity:
                print(f"expected_identity={result.expected_identity}")
            if result.message:
                print(f"message={result.message}")

    if result.status == SignatureVerificationStatus.VALID:
        return 0
    if result.status == SignatureVerificationStatus.UNSIGNED:
        return 1 if args.fail_unsigned else 0
    return 1
