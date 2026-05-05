"""Refresh the Foundry signature baseline through the canonical tools surface."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime

from tools.lib.fs import atomic_write_text
from tools.lib.imports import repo_root_from

REPO_ROOT = repo_root_from(__file__)
SRC_ROOT = REPO_ROOT / "src"
BASELINE_PATH = REPO_ROOT / "tests" / "foundry" / "fixtures" / "signature_baseline.json"


def build_hashes() -> dict[str, str]:
    if str(SRC_ROOT) not in sys.path:
        sys.path.insert(0, str(SRC_ROOT))

    from polisyos.foundry.methods.registry import MethodRegistry

    try:
        from polisyos.foundry.methods.catalog import ensure_all_methods_registered

        ensure_all_methods_registered()
    except ImportError:
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
    if not BASELINE_PATH.exists():
        return {}
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("signatures", {})


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print the diff without writing")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print each changed FQN")
    args = parser.parse_args(list(argv) if argv is not None else None)

    print("Building current signature hashes ...")
    current = build_hashes()
    existing = load_existing()

    added = sorted(set(current) - set(existing))
    removed = sorted(set(existing) - set(current))
    changed = sorted(fqn for fqn in set(current) & set(existing) if current[fqn] != existing[fqn])

    print("\nSummary:")
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
            print(f"  ~ {fqn}  ({existing[fqn]!r} -> {current[fqn]!r})")

    if args.dry_run:
        print("\n[dry-run] No files written.")
        return 0

    payload = {
        "schema_version": "1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "method_count": len(current),
        "signatures": current,
    }
    atomic_write_text(
        BASELINE_PATH,
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"\nWrote baseline to {BASELINE_PATH}")
    print("Commit this file to source control to enable breaking-change detection.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
