"""Reconcile the whole recorded L/M1 temporary-copy overlap; no live scans."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib
import json
from pathlib import Path, PurePosixPath
import re

r = importlib.import_module(
    "docs.superpowers.journals.gy-eight-gaps-evidence.l.probes.l_receipt_reconcile"
)


def read(path, key):
    raw = path.read_bytes()
    receipt = r.strict_json(raw)
    report = r.strict_json(r.field(receipt, "stdout", str))
    rows = r.field(report, key, list)
    r.require(all(type(x) is dict for x in rows), "finding_not_object")
    values = Counter(r.canonical(x) for x in rows)
    independent = Counter(r.structural(x) for x in rows)
    r.require(Counter({r.structural(r.strict_json(k)): v for k, v in values.items()})
              == independent, "full_finding_derivations_disagree")
    r.require(path.read_bytes() == raw, "receipt_changed_during_read")
    return receipt, report, rows, set(values), hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("m1", type=Path)
    parser.add_argument("check", type=Path)
    parser.add_argument("corrupt", type=Path)
    parser.add_argument("--temporary-root", required=True)
    args = parser.parse_args()
    temporary = PurePosixPath(args.temporary_root)
    r.require(not temporary.is_absolute() and ".." not in temporary.parts,
              "temporary_root_not_relative")
    m1, report, rows, whole, m1_hash = read(args.m1, "violations")
    check, _, check_rows, base, check_hash = read(args.check, "issues")
    corrupt, _, corrupt_rows, changed, corrupt_hash = read(args.corrupt, "issues")
    r.require(report["violation_count"] == len(rows) == len(whole),
              "m1_complete_violation_count_disagrees")
    codes = Counter(x["code"] for x in rows)
    groups = {code: [x for x in rows if x["code"] == code] for code in codes}
    r.require(dict(codes) == {k: len(v) for k, v in groups.items()},
              "violation_type_derivations_disagree")
    unregistered = groups["layer3_gy_artifact_not_registered"]
    copy_paths = r.unique_strings([r.field(x, "path", str) for x in unregistered],
                                  "unregistered_paths")
    r.require(all(PurePosixPath(x).is_relative_to(temporary) for x in copy_paths),
              "unregistered_path_outside_exact_temporary_root")
    suffixes = Counter(PurePosixPath(x).suffix for x in copy_paths)
    independent_suffixes = Counter("." + x.rsplit("/", 1)[-1].rsplit(".", 1)[-1]
                                   for x in copy_paths)
    r.require(suffixes == independent_suffixes, "file_type_derivations_disagree")
    lists = groups["gy_detected_artifact_list_drift"]
    r.require(len(lists) == 1 and lists[0]["detail"]["key"] == "paths",
              "detected_artifact_drift_shape")
    detail = lists[0]["detail"]
    recorded = r.unique_strings(detail["actual"], "recorded_detected_paths")
    observed = r.unique_strings(detail["expected"], "observed_detected_paths")
    r.require(observed - recorded == copy_paths and recorded - observed == set(),
              "audit_drift_not_exactly_temporary_copy_paths")
    r.require(len(observed) == len(recorded) + len(copy_paths),
              "complete_detected_path_denominators_disagree")
    summary = {}
    for item in groups["summary_semantics_drift"]:
        match = re.fullmatch(r"([^=]+)=(\d+); expected (\d+)", item["detail"])
        r.require(match is not None and match[1] not in summary,
                  "summary_drift_not_unique_typed_count")
        summary[match[1]] = {"recorded": int(match[2]), "observed": int(match[3])}
    r.require(summary == {
        "gy_artifact_files_detected": {"recorded": len(recorded), "observed": len(observed)},
        "gy_lifecycle_orphan_count": {"recorded": 0, "observed": len(copy_paths)},
    }, "summary_drift_has_noncopy_difference")
    r.require(set(codes) == {"layer3_gy_artifact_not_registered",
                            "summary_semantics_drift", "gy_detected_artifact_list_drift"},
              "other_m1_violation_type_present")
    copy_findings = {r.canonical(x) for x in unregistered}
    added, lost = changed - base, base - changed
    remaining = added - copy_findings
    r.require(copy_findings <= added, "corrupt_copy_findings_do_not_match_m1")
    print(json.dumps({
        "scope": "complete original retained receipt finding/path populations; no live repository scan or inherited-red attribution",
        "receipts": {str(args.m1): {"sha256": m1_hash, "returncode": m1["returncode"],
                                    "elapsed_seconds": m1["elapsed_seconds"]},
                     str(args.check): {"sha256": check_hash, "returncode": check["returncode"]},
                     str(args.corrupt): {"sha256": corrupt_hash, "returncode": corrupt["returncode"],
                                         "elapsed_seconds": corrupt["elapsed_seconds"]}},
        "temporary_root": str(temporary), "m1_violation_denominator": len(rows),
        "m1_complete_type_denominators": dict(codes),
        "all_unregistered_paths_inside_exact_temporary_root": True,
        "unregistered_suffix_denominators": dict(suffixes),
        "audit_added_paths_equal_complete_unregistered_paths": True,
        "audit_lost_paths": [], "audit_path_denominators": summary,
        "complete_temporary_path_identity_sha256": r.digest(sorted(copy_paths)),
        "other_m1_violation_identities": [],
        "corruption_cli_row_denominators": {"before": len(check_rows), "after": len(corrupt_rows)},
        "corruption_cli_identity_denominators": {"before": len(base), "after": len(changed)},
        "corruption_added_identity_denominator": len(added),
        "corruption_added_copy_identity_denominator": len(copy_findings),
        "corruption_added_noncopy_identities": [r.strict_json(x) for x in sorted(remaining)],
        "corruption_lost_identities": [r.strict_json(x) for x in sorted(lost)],
        "independent_complete_identity_derivations_agree": True,
        "raw_full_copy_identities": "retained once in the pinned input receipts; no derived duplicate",
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
