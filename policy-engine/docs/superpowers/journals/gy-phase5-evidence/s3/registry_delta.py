"""Reconcile complete frozen/current education S0 registry identities and leaf differences."""
from __future__ import annotations

import json
from pathlib import Path

from polisyos.runtime.quality.substrate_registry import build_substrate_registry_from_existing_catalogs
from tools.quality.validation import check_layer3_gy_second_domain_pack as pack_owner


def main() -> None:
    root = Path(__file__).resolve().parents[5]
    frozen = pack_owner._load_frozen_bundle(root)
    before = frozen["pack"]["owner_query_results"]["s0_registry"]["registry_payload"]
    current = build_substrate_registry_from_existing_catalogs(root).model_dump(mode="json")
    def indexed(payload):
        return {(entry["source_id"], entry["family_id"], entry["layer"]): entry
                for entry in payload["entries"]}
    left, right = indexed(before), indexed(current)
    assert len(left) == len(before["entries"]) and len(right) == len(current["entries"])
    raw_sets = [sorted(tuple(row[field] for field in ("source_id", "family_id", "layer"))
                       for row in p["entries"]) for p in (before, current)]
    assert raw_sets == [sorted(left), sorted(right)]
    missing = object()
    def compare(a, b, path=()):
        if isinstance(a, dict) and isinstance(b, dict):
            return [row for key in sorted(set(a) | set(b))
                    for row in compare(a.get(key, missing), b.get(key, missing), (*path, key))]
        if isinstance(a, list) and isinstance(b, list):
            return [row for index in range(max(len(a), len(b)))
                    for row in compare(a[index] if index < len(a) else missing,
                                       b[index] if index < len(b) else missing, (*path, index))]
        if a == b:
            return []
        return [{"path": path, "frozen": {"present": a is not missing,
                                          "value": a if a is not missing else None},
                 "current": {"present": b is not missing,
                              "value": b if b is not missing else None}}]
    print(json.dumps({"frozen_keys": sorted(left), "current_keys": sorted(right),
        "independent_frozen_keys": raw_sets[0], "independent_current_keys": raw_sets[1],
        "frozen_only": sorted(set(left)-set(right)), "current_only": sorted(set(right)-set(left)),
        "differences": [{"entry_identity": key, "leaves": compare(left[key], right[key])}
                        for key in sorted(set(left) & set(right)) if left[key] != right[key]],
        "registry_envelope_differences": compare({k:v for k,v in before.items() if k != "entries"},
                                                  {k:v for k,v in current.items() if k != "entries"})}, indent=2))


if __name__ == "__main__":
    main()
