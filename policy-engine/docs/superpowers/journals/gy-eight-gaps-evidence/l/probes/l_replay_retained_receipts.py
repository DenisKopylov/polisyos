"""Reconstruct original L receipt paths without rewriting evidence or ancestry.

Run from the recorded product-root station. This invokes only the retained stdlib
receipt reconciler, never a product gate. --check-only neither writes nor invokes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

PINS = {
    "native-live-wave-after-typed-readback.json":
        "68ca192072dcb0cc52587bda2e5bafa89113ba3f2d64ec03a91efafe075d016d",
    "native-corrections-wave.json":
        "07658d2ffe45b82bf1899a9794918a1f6765b7c9da4f1f55abdfe33cc1f423d4",
    "native-positive-delta-correction.json":
        "01fa4535ca85b1f9473513e0774b9218dfec7a55b55f38e9846a248a4cefc0cf",
}
RECONCILER_SHA256 = "f56915ec22846aa5aa5d3742ba35ba3dbc553f4696201f4baea9af25fc2b7895"
DESTINATION = Path("_build/gy-gaps/l")


def require(condition: bool, reason: str) -> None:
    """Refuse any substitution of the preserved evidence or original station."""
    if not condition:
        raise ValueError(reason)


def main() -> int:
    """Check pinned bytes, restore only absent original paths, then reconcile."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("retained", type=Path)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    root = Path.cwd().resolve()
    retained = args.retained.resolve(strict=True)
    retained.relative_to(root)
    utility = retained / "probes/l_receipt_reconcile.py"
    utility_raw = utility.read_bytes()
    require(hashlib.sha256(utility_raw).hexdigest() == RECONCILER_SHA256,
            "retained_reconciler_hash_mismatch")
    module = ".".join(utility.relative_to(root).with_suffix("").parts)
    copies = []
    for name, expected in PINS.items():
        source = retained / name
        raw = source.read_bytes()
        require(hashlib.sha256(raw).hexdigest() == expected,
                "retained_receipt_hash_mismatch:" + name)
        receipt = json.loads(raw)
        require(type(receipt) is dict and type(receipt.get("cwd")) is str,
                "recorded_station_missing:" + name)
        require(Path(receipt["cwd"]).resolve() == root,
                "recorded_station_differs_no_ancestry_relocation:" + name)
        target = root / DESTINATION / name
        for entry in (root / "_build", root / "_build/gy-gaps", root / DESTINATION, target):
            require(not entry.is_symlink(), "original_path_is_symlink:" + str(entry))
        if target.exists():
            require(target.is_file() and target.read_bytes() == raw,
                    "existing_original_receipt_differs:" + name)
        copies.append((target, raw))
    paths = [str(DESTINATION / name) for name in PINS]
    command = [sys.executable, "-m", module, paths[0],
               "--correction", paths[1], "--correction", paths[2]]
    print(json.dumps({"mode": "check_only" if args.check_only else "receipt_replay",
                      "cwd": str(root), "pinned_receipts": PINS,
                      "reconciler_sha256": RECONCILER_SHA256,
                      "command": command,
                      "product_gate_executed": False}, sort_keys=True), flush=True)
    if args.check_only:
        return 0
    for target, raw in copies:
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with target.open("xb") as stream:
                stream.write(raw)
        except FileExistsError:
            require(not target.is_symlink() and target.is_file() and target.read_bytes() == raw,
                    "existing_original_receipt_differs:" + target.name)
        require(target.read_bytes() == raw, "restored_receipt_readback_differs:" + target.name)
    require(utility.read_bytes() == utility_raw, "retained_reconciler_changed_during_replay")
    return subprocess.run(command, check=False,
                          env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}).returncode


if __name__ == "__main__":
    raise SystemExit(main())
