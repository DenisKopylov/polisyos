"""Validate combined-wave source custody, then reuse full L receipt reconciliation.

This reads receipts only. Exit zero means reconciliation succeeded, not tests passed.
No receipt or derived report is written. Native/GX bodies remain in their receipts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from _build.gy_gaps import l_receipt_reconcile as owner

SUITE = "gy_j_l_regression_and_importers.v1"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--after", type=Path)
    parser.add_argument("--correction", type=Path, action="append", default=[])
    parser.add_argument("--packet", type=int)
    parser.add_argument("--after-packet", type=int)
    args = parser.parse_args()
    paths = [args.receipt, *([args.after] if args.after else []), *args.correction]
    hashes, records = {}, []
    for path in dict.fromkeys(paths):
        raw = path.read_bytes()
        receipt = owner.strict_json(raw)
        populations = owner.packets(receipt, "GY_L_NATIVE_POPULATION ")
        readbacks = owner.packets(receipt, "GY_L_NATIVE_READBACK ")
        owner.require(len(populations) == len(readbacks) == 1,
                      "combined_native_packet_absent_or_duplicated:" + str(path))
        population, readback = populations[0]["payload"], readbacks[0]["payload"]
        owner.require(population.get("suite_id") == readback.get("suite_id") == SUITE,
                      "receipt_not_combined_J_L_suite:" + str(path))
        owner.require(readback.get("measurement_state") == "measured"
                      and readback.get("source_frozen") is True
                      and readback.get("complete_identity_readback") is True,
                      "source_or_identity_basis_not_established:" + str(path))
        before = owner.field(population, "source_before", dict)
        after = owner.field(readback, "source_after", dict)
        owner.require(before == after, "source_before_after_hashes_differ:" + str(path))
        owner.require(owner.field(readback, "complete_source_delta", dict)
                      == {"lost": {}, "added": {}, "changed": {}},
                      "nonempty_complete_source_delta:" + str(path))
        collected = owner.unique_strings(readback["collected"], "combined.collected")
        expected_hash = hashlib.sha256(json.dumps(
            sorted(collected), sort_keys=True, separators=(",", ":")
        ).encode()).hexdigest()
        owner.require(population["selected_expected_identity_sha256"] == expected_hash
                      and population["selected_expected_expanded_denominator"] == len(collected),
                      "selected_expected_collection_hash_mismatch:" + str(path))
        identity = path.resolve()
        hashes[identity] = hashlib.sha256(raw).hexdigest()
        predecessor = population["failed_from"]
        if predecessor is not None:
            owner.require(type(predecessor) is str, "correction_predecessor_not_string")
            prior = Path(predecessor)
            if not prior.is_absolute():
                prior = Path(owner.field(receipt, "cwd", str)) / prior
            owner.require(prior.resolve() in hashes
                          and population["failed_from_sha256"] == hashes[prior.resolve()],
                          "correction_predecessor_sha_or_supplied_order_mismatch:" + str(path))
        owner.require(path.read_bytes() == raw, "receipt_changed_during_source_reconciliation")
        records.append({
            "receipt": str(path), "receipt_sha256": hashes[identity],
            "complete_source_state_sha256": before["complete_source_state_sha256"],
            "source_frozen": True,
        })
    print("GY_J_L_SOURCE_RECONCILIATION " + json.dumps({
        "status": "reconciled", "receipts": records,
        "source_change_policy": "each invocation frozen; corrections do not rerun earlier passes",
    }, sort_keys=True))
    # Keep its unchanged full summary/progress/collection, GX, and predecessor checks.
    return owner.main()


if __name__ == "__main__":
    try:
        result = main()
    except (OSError, UnicodeError, ValueError, TypeError, KeyError) as error:
        print(json.dumps({"reconciliation_status": "not_established", "reason": str(error)}))
        result = 2
    raise SystemExit(result)
