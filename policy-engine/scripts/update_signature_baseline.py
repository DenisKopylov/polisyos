#!/usr/bin/env python3
"""
Update the Foundry signature baseline for breaking-change detection.

Run this script:
1. After an approved breaking change (method signature updated + major version bumped)
2. When adding the first baseline (initially empty registry)

Usage
-----
::

    cd policy-engine
    python scripts/update_signature_baseline.py

The script writes tests/foundry/fixtures/signature_baseline.json.
Commit the result to source control.

Options
-------
--dry-run   Print what would change without writing to disk.
--verbose   Print each FQN and its hash.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add src to path for direct execution
_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

_BASELINE_PATH = _REPO_ROOT / "tests" / "foundry" / "fixtures" / "signature_baseline.json"


def build_hashes() -> dict[str, str]:
    """Return {fqn: signature_stable_digest} for all registered methods."""
    from polisyos.foundry.methods.registry import MethodRegistry
    from polisyos.foundry.methods.catalog import ensure_all_methods_registered  # noqa

    try:
        ensure_all_methods_registered()
    except ImportError:
        # May not exist — fall back to registry as-is
        pass

    registry = MethodRegistry.get_instance()
    snapshot = registry.snapshot()
    hashes: dict[str, str] = {}
    for fqn, entry in snapshot.items():
        try:
            hashes[fqn] = entry.signature.stable_digest()
        except Exception as exc:
            print(f"  WARNING: could not hash {fqn}: {exc}", file=sys.stderr)
            hashes[fqn] = "<error>"
    return hashes


def load_existing() -> dict[str, str]:
    if not _BASELINE_PATH.exists():
        return {}
    with _BASELINE_PATH.open() as f:
        return json.load(f).get("signatures", {})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    print("Building current signature hashes ...")
    current = build_hashes()
    existing = load_existing()

    added = sorted(set(current) - set(existing))
    removed = sorted(set(existing) - set(current))
    changed = sorted(
        fqn for fqn in set(current) & set(existing) if current[fqn] != existing[fqn]
    )

    print(f"\nSummary:")
    print(f"  Total methods: {len(current)}")
    print(f"  Added:         {len(added)}")
    print(f"  Removed:       {len(removed)}")
    print(f"  Changed:       {len(changed)}")

    if args.verbose:
        for fqn in added:
            print(f"  + {fqn}")
        for fqn in removed:
            print(f"  - {fqn}")
        for fqn in changed:
            print(f"  ~ {fqn}  ({existing[fqn]!r} → {current[fqn]!r})")

    if args.dry_run:
        print("\n[dry-run] No files written.")
        return

    _BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method_count": len(current),
        "signatures": current,
    }
    with _BASELINE_PATH.open("w") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
        f.write("\n")

    print(f"\nWrote baseline to {_BASELINE_PATH}")
    print("Commit this file to source control to enable breaking-change detection.")


if __name__ == "__main__":
    main()
