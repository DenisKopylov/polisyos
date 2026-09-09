"""Compare complete L CLI/GX receipt evidence; never invoke a product gate."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib
import json
from pathlib import Path

r = importlib.import_module(
    "docs.superpowers.journals.gy-eight-gaps-evidence.l.probes.l_receipt_reconcile"
)


def identities(issues):
    r.require(type(issues) is list and all(type(x) is dict for x in issues),
              "issues_absent_null_or_nonobject")
    primary = Counter(r.canonical(x) for x in issues)
    independent = Counter(r.structural(x) for x in issues)
    r.require(Counter({r.structural(r.strict_json(k)): v for k, v in primary.items()})
              == independent, "complete_issue_derivations_disagree")
    return primary


def differences(before, after, path="$", output=None):
    if output is None:
        output = []
    if type(before) is not type(after):
        output.append({"path": path, "before": before, "after": after})
    elif type(before) is dict:
        for key in sorted(set(before) | set(after)):
            if key not in before or key not in after:
                row = {"path": path + "/" + key,
                       "before_present": key in before, "after_present": key in after}
                if key in before:
                    row["before"] = before[key]
                if key in after:
                    row["after"] = after[key]
                output.append(row)
            else:
                differences(before[key], after[key], path + "/" + key, output)
    elif type(before) is list:
        for index in range(max(len(before), len(after))):
            if index >= len(before) or index >= len(after):
                row = {"path": path + "/" + str(index),
                       "before_present": index < len(before),
                       "after_present": index < len(after)}
                if index < len(before):
                    row["before"] = before[index]
                if index < len(after):
                    row["after"] = after[index]
                output.append(row)
            else:
                differences(before[index], after[index], path + "/" + str(index), output)
    elif before != after:
        output.append({"path": path, "before": before, "after": after})
    return output


def read(path):
    raw = path.read_bytes()
    receipt = r.strict_json(raw)
    report = r.strict_json(r.field(receipt, "stdout", str))
    issue_counts = identities(r.field(report, "issues", list))
    packets = r.packets(receipt, "GY_POST_OUTPUT_GX ")
    r.require(len(packets) == 1, "complete_gx_packet_not_unique:" + str(path))
    reconciled, findings = r.reconcile_gx(packets[0])
    r.require(findings is not None, "gx_result_not_established:" + str(path))
    r.require(path.read_bytes() == raw, "receipt_changed_during_read:" + str(path))
    return {
        "path": str(path), "receipt_sha256": hashlib.sha256(raw).hexdigest(),
        "returncode": r.field(receipt, "returncode", int),
        "elapsed_seconds": receipt["elapsed_seconds"], "status": report["status"],
        "issue_row_denominator": len(report["issues"]),
        "issue_identity_denominator": len(issue_counts),
        "duplicate_issue_row_denominator": sum(issue_counts.values()) - len(issue_counts),
        "gx_reconciliation": reconciled,
    }, report, issue_counts, packets[0]["payload"], findings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    args = parser.parse_args()
    before, old_report, old_counts, old_packet, old_gx = read(args.before)
    after, new_report, new_counts, new_packet, new_gx = read(args.after)
    raw_delta = differences(old_packet, new_packet)
    equal = r.canonical(old_packet) == r.canonical(new_packet)
    r.require(equal == (r.structural(old_packet) == r.structural(new_packet)),
              "complete_gx_packet_comparison_disagrees")
    old_other = {k: v for k, v in old_report.items() if k != "issues"}
    new_other = {k: v for k, v in new_report.items() if k != "issues"}
    print(json.dumps({
        "scope": "complete retained CLI issues and full emitted GX/read-basis packets; no current repository or product execution",
        "before": before, "after": after,
        "cli_finding_identity_delta": {
            k: [r.strict_json(x) for x in values]
            for k, values in r.delta(set(old_counts), set(new_counts)).items()
        },
        "cli_issue_multiplicity_changes": [
            {"identity": r.strict_json(key), "before": old_counts[key], "after": new_counts[key]}
            for key in sorted(set(old_counts) | set(new_counts))
            if old_counts[key] != new_counts[key]
            and ((key in old_counts and key in new_counts)
                 or max(old_counts[key], new_counts[key]) > 1)
        ],
        "cli_other_field_delta": differences(old_other, new_other),
        "gx_finding_identity_delta": {
            k: [r.strict_json(x) for x in values]
            for k, values in r.delta(old_gx, new_gx).items()
        },
        "complete_gx_packet_equal": equal,
        "complete_gx_packet_delta": raw_delta,
        "independent_canonical_structural_comparisons_agree": True,
        "normalizations": "Object key order only. Types, absence/null, list order, findings, values and all emitted read/source/native bases remain exact.",
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
