"""Decode exact public Q2 backend inputs and reuse the canonical quarantine gate.

This only materializes ten hash-bound regular input files.  It does not install,
build, import PolicyOS runtime, fetch a URL, or certify backend execution.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import io
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path, PurePosixPath


def digest(raw: bytes) -> str:
    """Return the SHA-256 of exact transport bytes."""
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    """Reconcile immutable source inputs and produce one exact flat quarantine."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-tree", required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    for label, value in (("commit", args.source_commit), ("tree", args.source_tree)):
        if re.fullmatch(r"[0-9a-f]{40}", value) is None:
            raise ValueError(f"source {label} must be a full lowercase 40-hex identity")
    source = args.source_root.resolve(strict=True)
    carrier = Path(__file__).resolve(strict=True).parent
    reads: list[dict[str, object]] = []

    def git(*argv: str) -> bytes:
        if argv in (("rev-parse", "HEAD"), ("rev-parse", "HEAD^{tree}")):
            command = ["/usr/bin/git", *argv]
        elif len(argv) == 3 and argv[:2] == ("cat-file", "blob"):
            prefix = args.source_commit + ":"
            if not argv[2].startswith(prefix):
                raise ValueError("blob read must name the admitted full source commit")
            relative = argv[2][len(prefix) :]
            path = PurePosixPath(relative)
            if (
                not relative
                or not path.parts
                or path.is_absolute()
                or path.as_posix() != relative
                or any(part in {".", ".."} for part in path.parts)
                or "\\" in relative
                or "\0" in relative
            ):
                raise ValueError("blob read must name one normalized in-tree source path")
            command = ["/usr/bin/git", "cat-file", "blob", argv[2]]
        else:
            raise ValueError(
                "only the two fixed HEAD reads and admitted source-blob reads are allowed"
            )
        # S603: absolute executable, fixed read-only verbs/arity and SHA:path validation above;
        # no shell, option slot or caller-selected executable reaches this subprocess.
        completed = subprocess.run(  # noqa: S603
            command, cwd=source, capture_output=True, check=False
        )
        reads.append(
            {
                "command": command,
                "returncode": completed.returncode,
                "stdout_bytes": len(completed.stdout),
                "stdout_sha256": digest(completed.stdout),
                "stderr_bytes": len(completed.stderr),
                "stderr_sha256": digest(completed.stderr),
            }
        )
        if completed.returncode or completed.stderr:
            raise RuntimeError(f"source Git read failed: {argv!r}")
        return completed.stdout

    if git("rev-parse", "HEAD").decode().strip() != args.source_commit:
        raise ValueError("actual source HEAD differs from the published execution input")
    if git("rev-parse", "HEAD^{tree}").decode().strip() != args.source_tree:
        raise ValueError("actual source tree differs from the published execution input")

    def bound_read(path: Path) -> bytes:
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"input is not a regular nonsymlink file: {path}")
        relative = path.relative_to(source).as_posix()
        expected = git("cat-file", "blob", args.source_commit + ":" + relative)
        raw = path.read_bytes()
        if expected != raw:
            raise ValueError(f"actual input differs from immutable Git: {relative}")
        return raw

    decoder_raw = bound_read(Path(__file__).resolve(strict=True))
    manifest_raw = bound_read(carrier / "manifest.json")
    manifest = json.loads(manifest_raw)
    if manifest["schema"] != "policyos.e02.q2.public_backend_carrier.v1":
        raise ValueError("unsupported carrier manifest")
    product = source / "policy-engine"
    bindings = manifest["canonical_source_bindings"]
    helper_path = product / bindings["helper"]["path"]
    helper_raw = bound_read(helper_path)
    lock_raw = bound_read(product / bindings["lock"]["path"])
    profile_raw = bound_read(product / bindings["profile"]["path"])
    for role, raw in (("helper", helper_raw), ("lock", lock_raw), ("profile", profile_raw)):
        if digest(raw) != bindings[role]["sha256"]:
            raise ValueError(f"canonical {role} no longer matches this carrier")
    project_raw = bound_read(product / "pyproject.toml")
    profile = tomllib.loads(profile_raw.decode("utf-8"))
    spec = importlib.util.spec_from_file_location("q2_carrier_canonical_helper", helper_path)
    if spec is None or spec.loader is None:
        raise ValueError("cannot load the source-bound canonical Q2 helper")
    helper = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = helper
    spec.loader.exec_module(helper)
    validated_profile = helper.verify_pyproject_profile(
        project_raw,
        profile_raw=profile_raw,
        helper_path=bindings["helper"]["path"],
        helper_sha256=digest(helper_raw),
        lock_path=bindings["lock"]["path"],
        lock_sha256=digest(lock_raw),
    )
    if profile != validated_profile:
        raise ValueError("carrier source profile differs from pyproject")
    lock = helper.load_lock(lock_raw, expected_sha256=digest(lock_raw))
    helper.verify_profile_lock(profile, lock)
    expected_names = {row["filename"] for row in lock["artifacts"]} | {
        row["name"] + "-" + row["version"] + ".json" for row in lock["artifacts"]
    }
    rows = manifest["payloads"]
    if len(rows) != len(expected_names) or {row["raw_filename"] for row in rows} != expected_names:
        raise ValueError("carrier payload set differs from the complete canonical lock")
    destination = args.destination.resolve()
    if destination.is_relative_to(source) or destination.exists() or destination.is_symlink():
        raise ValueError("destination must be a fresh task directory outside checkout ancestry")
    destination.mkdir(parents=True, exist_ok=False)
    inventory = []
    for row in rows:
        name, compressed_name = row["raw_filename"], row["compressed_filename"]
        if Path(name).name != name or name in {"", ".", ".."} or compressed_name != name + ".gz":
            raise ValueError("carrier paths must be the exact declared flat basenames")
        compressed = bound_read(carrier / compressed_name)
        if (
            len(compressed) != row["compressed_bytes"]
            or digest(compressed) != row["compressed_sha256"]
        ):
            raise ValueError(f"compressed input drift: {compressed_name}")
        with gzip.GzipFile(fileobj=io.BytesIO(compressed), mode="rb") as stream:
            raw = stream.read(row["raw_bytes"] + 1)
        if len(raw) != row["raw_bytes"] or digest(raw) != row["raw_sha256"]:
            raise ValueError(f"decoded input drift: {name}")
        target = destination / name
        with target.open("xb") as output:
            output.write(raw)
        if target.read_bytes() != raw:
            raise ValueError(f"decoded regular file readback drift: {name}")
        inventory.append({"path": name, "bytes": len(raw), "sha256": digest(raw)})
    # This is the existing authoritative full wheel/record/closure validation,
    # not another parser, installer or replacement wheel verifier.
    quarantine = helper.validate_quarantine(lock, destination)
    sys.stdout.write(
        json.dumps(
            {
                "schema": "policyos.e02.q2.public_backend_decode_receipt.v1",
                "outcome": "PASS",
                "property": "exact input transport + canonical quarantine validation",
                "source_commit": args.source_commit,
                "source_tree": args.source_tree,
                "decoder_sha256": digest(decoder_raw),
                "manifest_sha256": digest(manifest_raw),
                "lock_sha256": digest(lock_raw),
                "helper_sha256": digest(helper_raw),
                "profile_sha256": digest(profile_raw),
                "destination": str(destination),
                "decoded_files": inventory,
                "decoded_bytes": sum(row["bytes"] for row in inventory),
                "source_reads": reads,
                "canonical_quarantine_result": quarantine,
                "backend_installation_execution": "UNRUN",
                "G_acceptance": False,
                "closure_ids": [],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
