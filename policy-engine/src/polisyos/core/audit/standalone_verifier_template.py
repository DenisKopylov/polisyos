#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import sys
import tarfile
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat, load_pem_public_key

try:
    from polisyos.core.canon import content_hash, streaming_hash
except Exception:  # pragma: no cover - template fallback for standalone runs
    def content_hash(payload: bytes | str, *, prefix: bool = False) -> str:
        raw = payload if isinstance(payload, bytes) else payload.encode("utf-8")
        digest = __import__("hashlib").sha256(raw).hexdigest()
        if prefix:
            return f"sha256:{digest}"
        return digest

    def streaming_hash(chunks: Iterable[bytes], *, prefix: bool = False) -> str:
        hasher = __import__("hashlib").sha256()
        for chunk in chunks:
            hasher.update(chunk)
        digest = hasher.hexdigest()
        if prefix:
            return f"sha256:{digest}"
        return digest


def _sha256(path: Path) -> str:
    def _chunks() -> Iterable[bytes]:
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    return
                yield chunk

    return streaming_hash(_chunks())


def _canonical_statement_bytes(statement: dict[str, Any]) -> bytes:
    return json.dumps(
        statement,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _safe_extract(
    archive: Path,
    target: Path,
    *,
    max_total_bytes: int = 2 * 1024 * 1024 * 1024,
) -> None:
    with tarfile.open(archive, "r:*") as tar:
        members = tar.getmembers()
        _validate_members(members, target, max_total_bytes=max_total_bytes)
        try:
            # Python 3.12+ safe extraction.
            tar.extractall(target, members=members, filter="data")
            return
        except TypeError:
            # Python < 3.12 fallback below.
            pass

        for member in members:
            rel = Path(member.name)
            out_path = target / rel
            if member.isdir():
                out_path.mkdir(parents=True, exist_ok=True)
                continue
            if not member.isfile():
                continue
            out_path.parent.mkdir(parents=True, exist_ok=True)
            extracted = tar.extractfile(member)
            if extracted is None:
                continue
            with extracted, out_path.open("wb") as handle:
                shutil.copyfileobj(extracted, handle)


def _validate_members(
    members: list[tarfile.TarInfo],
    target: Path,
    *,
    max_total_bytes: int,
) -> None:
    resolved_target = target.resolve()
    total_size = 0
    for member in members:
        if member.islnk() or member.issym() or member.isdev():
            raise RuntimeError(f"Unsafe archive member: {member.name}")
        rel = Path(member.name)
        if rel.is_absolute() or any(part in ("", "..") for part in rel.parts):
            raise RuntimeError(f"Unsafe path: {member.name}")
        total_size += int(member.size)
        if total_size > max_total_bytes:
            raise RuntimeError("Archive exceeds extraction size limit")
        resolved_out = (target / rel).resolve()
        if resolved_target not in resolved_out.parents and resolved_out != resolved_target:
            raise RuntimeError(f"Path traversal detected: {member.name}")


def _parse_artifact_hex(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.removeprefix("sha256:")
    if len(candidate) == 64 and all(ch in "0123456789abcdef" for ch in candidate):
        return candidate
    return None


def _resolve_profile(pkg_dir: Path, index: dict[str, Any]) -> str:
    opts_path = pkg_dir / "metadata" / "export_opts.json"
    if opts_path.exists():
        try:
            payload = json.loads(opts_path.read_text("utf-8"))
            if payload.get("profile") in {"full", "manifests_only"}:
                return str(payload["profile"])
            if payload.get("manifests_only") is True:
                return "manifests_only"
        except Exception:
            pass
    profile = index.get("export_profile")
    if profile in {"full", "manifests_only"}:
        return str(profile)
    return "full"


def _verify_checksums(pkg_dir: Path) -> list[str]:
    issues: list[str] = []
    checksums = pkg_dir / "verification" / "checksums.sha256"
    if not checksums.exists():
        return ["missing verification/checksums.sha256"]
    for line in checksums.read_text("utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        expected, rel = text.split("  ", 1)
        path = pkg_dir / rel
        if not path.exists():
            issues.append(f"missing file: {rel}")
            continue
        actual = _sha256(path)
        if actual != expected:
            issues.append(f"checksum mismatch: {rel}")
    return issues


def _verify_checksum_signature(pkg_dir: Path) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    warnings: list[str] = []
    sig_path = pkg_dir / "verification" / "checksums.sha256.sig"
    if not sig_path.exists():
        warnings.append("checksum signature is not present")
        return failures, warnings
    try:
        payload = json.loads(sig_path.read_text("utf-8"))
    except Exception as exc:
        failures.append(f"invalid checksum signature payload: {exc}")
        return failures, warnings
    key_id = payload.get("key_id")
    signature_hex = payload.get("signature_hex")
    if not isinstance(signature_hex, str):
        failures.append("invalid checksum signature payload: signature_hex missing")
        return failures, warnings
    statement = (pkg_dir / "verification" / "checksums.sha256").read_bytes()
    keys_dir = pkg_dir / "signatures" / "public_keys"
    matched = False
    for key_file in sorted(keys_dir.glob("*.pem")):
        try:
            public_key = load_pem_public_key(key_file.read_bytes())
            public_key.verify(bytes.fromhex(signature_hex), statement)
            matched = True
            break
        except Exception:
            continue
    if not matched:
        failures.append("checksum signature verification failed")
    if isinstance(key_id, str):
        warnings.append(f"checksum signed by package key_id={key_id}")
    return failures, warnings


def _key_id(public_key: Any) -> str:
    raw = public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)
    return content_hash(raw, prefix=True)


def _load_package_keys(pkg_dir: Path) -> dict[str, Any]:
    keys: dict[str, Any] = {}
    key_dir = pkg_dir / "signatures" / "public_keys"
    for key_file in sorted(key_dir.glob("*.pem")):
        try:
            key = load_pem_public_key(key_file.read_bytes())
        except Exception:
            continue
        try:
            keys[_key_id(key)] = key
        except Exception:
            continue
    return keys


def _verify_cas(
    pkg_dir: Path,
    *,
    profile: str,
) -> tuple[dict[str, dict[str, Any]], list[str], list[str]]:
    artifacts: dict[str, dict[str, Any]] = {}
    failures: list[str] = []
    warnings: list[str] = []
    for manifest_path in sorted((pkg_dir / "artifacts" / "sha256").rglob("*.manifest.json")):
        try:
            manifest = json.loads(manifest_path.read_text("utf-8"))
        except Exception as exc:
            failures.append(f"invalid manifest: {manifest_path}: {exc}")
            continue
        hex_id = _parse_artifact_hex(manifest.get("artifact_id"))
        if hex_id is None:
            failures.append(f"invalid artifact_id in manifest: {manifest_path}")
            continue
        blob_path = manifest_path.with_name(f"{hex_id}.blob")
        manifest_sha = _sha256(manifest_path)
        entry: dict[str, Any] = {
            "manifest": manifest,
            "manifest_path": manifest_path,
            "manifest_sha": manifest_sha,
            "blob_path": blob_path,
            "blob_sha": None,
        }
        if blob_path.exists():
            blob_sha = _sha256(blob_path)
            entry["blob_sha"] = blob_sha
            if blob_sha != hex_id:
                failures.append(f"CAS integrity mismatch for {hex_id}")
            size = manifest.get("byte_size")
            if isinstance(size, int) and blob_path.stat().st_size != size:
                failures.append(f"blob size mismatch for {hex_id}")
            integrity = manifest.get("integrity")
            if isinstance(integrity, dict):
                declared = integrity.get("sha256")
                if isinstance(declared, str) and declared != hex_id:
                    failures.append(f"manifest integrity mismatch for {hex_id}")
        else:
            if profile == "manifests_only":
                warnings.append(f"blob absent in manifests-only profile: {hex_id}")
            else:
                failures.append(f"missing blob for {hex_id}")
        artifacts[hex_id] = entry
    return artifacts, failures, warnings


def _verify_signatures(
    pkg_dir: Path,
    artifacts: dict[str, dict[str, Any]],
    *,
    profile: str,
) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    warnings: list[str] = []
    keys = _load_package_keys(pkg_dir)
    if not keys:
        warnings.append("no package public keys found")
    sig_files = sorted((pkg_dir / "signatures" / "sha256").rglob("*.sig"))
    if not sig_files:
        warnings.append("no detached signatures found")
        return failures, warnings

    signed_ids: set[str] = set()
    for sig_path in sig_files:
        try:
            signature = json.loads(sig_path.read_text("utf-8"))
        except Exception as exc:
            failures.append(f"invalid signature file: {sig_path}: {exc}")
            continue
        statement = signature.get("statement")
        if not isinstance(statement, dict):
            failures.append(f"signature has no statement: {sig_path}")
            continue
        hex_id = _parse_artifact_hex(statement.get("artifact_id"))
        if hex_id is None:
            failures.append(f"signature statement artifact_id invalid: {sig_path}")
            continue
        signed_ids.add(hex_id)
        artifact = artifacts.get(hex_id)
        if artifact is None:
            failures.append(f"signature references unknown artifact: {hex_id}")
            continue

        manifest_sha_expected = statement.get("manifest_sha256")
        manifest_sha_actual = artifact["manifest_sha"]
        if manifest_sha_expected != manifest_sha_actual:
            failures.append(f"signature manifest hash mismatch: {hex_id}")
            continue

        blob_sha_expected = statement.get("blob_sha256")
        blob_sha_actual = artifact.get("blob_sha")
        if isinstance(blob_sha_actual, str):
            if blob_sha_expected != blob_sha_actual:
                failures.append(f"signature blob hash mismatch: {hex_id}")
                continue
        else:
            if profile == "manifests_only":
                integrity = artifact["manifest"].get("integrity")
                declared = integrity.get("sha256") if isinstance(integrity, dict) else None
                if not isinstance(declared, str) or blob_sha_expected != declared:
                    failures.append(f"indirect signature blob hash mismatch: {hex_id}")
                    continue
                warnings.append(f"indirect signature verification for {hex_id} (blob absent)")
            else:
                failures.append(f"signature cannot be verified; blob missing: {hex_id}")
                continue

        key_id = signature.get("key_id")
        signature_hex = signature.get("signature_hex")
        if not isinstance(key_id, str) or not isinstance(signature_hex, str):
            failures.append(f"signature key_id/signature_hex missing: {sig_path}")
            continue
        key = keys.get(key_id)
        if key is None:
            failures.append(f"signature key not found in package: {key_id}")
            continue
        try:
            payload = _canonical_statement_bytes(statement)
            key.verify(bytes.fromhex(signature_hex), payload)
        except InvalidSignature:
            failures.append(f"invalid signature bytes for {hex_id}")
            continue
        except Exception as exc:
            failures.append(f"signature verification error for {hex_id}: {exc}")
            continue

    unsigned = sorted(set(artifacts) - signed_ids)
    if unsigned:
        warnings.append(f"unsigned artifacts: {', '.join(unsigned[:8])}")
    return failures, warnings


def _verify_slsa(
    pkg_dir: Path,
    artifacts: dict[str, dict[str, Any]],
) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    warnings: list[str] = []

    slsa_dir = pkg_dir / "slsa"
    if not slsa_dir.exists():
        warnings.append("slsa evidence not found (legacy package or disabled mode)")
        return failures, warnings

    attestation_path = slsa_dir / "attestation.json"
    if not attestation_path.exists():
        failures.append("missing slsa/attestation.json")
        return failures, warnings

    try:
        attestation = json.loads(attestation_path.read_text("utf-8"))
    except Exception as exc:
        failures.append(f"invalid slsa attestation json: {exc}")
        return failures, warnings

    if attestation.get("_type") != "https://in-toto.io/Statement/v1":
        failures.append("invalid in-toto statement _type")
    if attestation.get("predicateType") != "https://slsa.dev/provenance/v1":
        failures.append("invalid in-toto predicateType")

    subjects = attestation.get("subject", [])
    if isinstance(subjects, list) and subjects:
        first = subjects[0]
        if isinstance(first, dict):
            digest = first.get("digest", {})
            if isinstance(digest, dict):
                subject_sha = digest.get("sha256")
                if isinstance(subject_sha, str):
                    index_data = json.loads((pkg_dir / "index.json").read_text("utf-8"))
                    root_ref = index_data.get("artifacts", {}).get("root_artifact_id", "")
                    root_sha = (
                        root_ref.removeprefix("sha256:")
                        if isinstance(root_ref, str)
                        else ""
                    )
                    if root_sha and subject_sha != root_sha:
                        failures.append("slsa subject digest does not match root_artifact_id")
                else:
                    failures.append("slsa subject digest.sha256 missing")
            else:
                failures.append("slsa subject digest missing")
        else:
            failures.append("slsa subject entry malformed")
    else:
        failures.append("slsa subject list is empty")

    predicate = attestation.get("predicate", {})
    if isinstance(predicate, dict):
        build_def = predicate.get("buildDefinition", {})
        deps = build_def.get("resolved_dependencies", []) if isinstance(build_def, dict) else []
        if isinstance(deps, list):
            for dep in deps:
                if not isinstance(dep, dict):
                    failures.append("malformed slsa dependency descriptor")
                    continue
                digest = dep.get("digest", {})
                if not isinstance(digest, dict):
                    failures.append("malformed slsa dependency digest")
                    continue
                dep_sha = digest.get("sha256")
                if not isinstance(dep_sha, str):
                    failures.append("missing dependency digest.sha256")
                    continue
                if dep_sha not in artifacts:
                    failures.append(f"slsa dependency missing from package: {dep_sha}")

    signature_path = slsa_dir / "signature.json"
    if not signature_path.exists():
        warnings.append("slsa/signature.json is absent")
    else:
        try:
            signature_payload = json.loads(signature_path.read_text("utf-8"))
        except Exception as exc:
            failures.append(f"invalid slsa signature payload: {exc}")
        else:
            payload_sha = signature_payload.get("payload_sha256")
            canonical = _canonical_statement_bytes(attestation)
            canonical_sha = content_hash(canonical)
            if isinstance(payload_sha, str) and payload_sha != canonical_sha:
                failures.append("slsa signature payload hash mismatch")

    transparency_path = slsa_dir / "transparency_entry.json"
    if transparency_path.exists():
        try:
            transparency = json.loads(transparency_path.read_text("utf-8"))
        except Exception as exc:
            failures.append(f"invalid slsa transparency payload: {exc}")
        else:
            entry_sha = transparency.get("payload_sha256")
            canonical_sha = content_hash(_canonical_statement_bytes(attestation))
            if isinstance(entry_sha, str) and entry_sha != canonical_sha:
                failures.append("slsa transparency hash mismatch")
    else:
        warnings.append("slsa/transparency_entry.json is absent")

    return failures, warnings


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    package = Path(argv[0]) if argv else Path.cwd().parent
    if package.is_dir():
        pkg_dir = package
    else:
        tmp_dir = Path(tempfile.mkdtemp(prefix="polisyos-audit-verify-"))
        _safe_extract(package, tmp_dir)
        pkg_dir = tmp_dir

    index_path = pkg_dir / "index.json"
    if not index_path.exists():
        print("FAIL")
        print("- missing index.json")
        return 1
    try:
        index = json.loads(index_path.read_text("utf-8"))
    except Exception as exc:
        print("FAIL")
        print(f"- invalid index.json: {exc}")
        return 1

    profile = _resolve_profile(pkg_dir, index)
    failures: list[str] = []
    warnings: list[str] = []

    failures.extend(_verify_checksums(pkg_dir))
    checksum_failures, checksum_warnings = _verify_checksum_signature(pkg_dir)
    failures.extend(checksum_failures)
    warnings.extend(checksum_warnings)

    artifacts, cas_failures, cas_warnings = _verify_cas(pkg_dir, profile=profile)
    failures.extend(cas_failures)
    warnings.extend(cas_warnings)

    sig_failures, sig_warnings = _verify_signatures(pkg_dir, artifacts, profile=profile)
    failures.extend(sig_failures)
    warnings.extend(sig_warnings)

    slsa_failures, slsa_warnings = _verify_slsa(pkg_dir, artifacts)
    failures.extend(slsa_failures)
    warnings.extend(slsa_warnings)

    if failures:
        print("FAIL")
        for item in failures:
            print(f"- {item}")
        if warnings:
            print("WARNINGS")
            for item in warnings:
                print(f"- {item}")
        return 1

    print("PASS")
    if warnings:
        print("WARNINGS")
        for item in warnings:
            print(f"- {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
