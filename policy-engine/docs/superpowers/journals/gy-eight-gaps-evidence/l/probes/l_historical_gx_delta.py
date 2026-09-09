"""Compare complete measured GX issue identities; never attribute a red as inherited."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess

JOURNAL = "policy-engine/docs/superpowers/journals/2026-09-08-gy-ambiguous-census.md"
REVISION = "43580c80b"
STDOUT_SOURCE = "_build/gy-census/outcome/gx_new_projection_check/stdout.txt"


def sha(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def strict_json(raw: str | bytes):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate_json_key:" + key)
            result[key] = value
        return result

    def constant(value):
        raise ValueError("nonfinite_json:" + value)

    def finite(value):
        result = float(value)
        if not math.isfinite(result):
            raise ValueError("nonfinite_float:" + value)
        return result

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant, parse_float=finite)


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def structural(value):
    if isinstance(value, dict):
        return ("object", tuple((key, structural(item)) for key, item in sorted(value.items())))
    if isinstance(value, list):
        return ("array", tuple(map(structural, value)))
    return (type(value).__name__, repr(value))


def field(value, key, kind):
    if type(value) is not dict or key not in value or type(value[key]) is not kind:
        raise ValueError("required_field_absent_null_or_wrong_type:" + key)
    return value[key]


def identities(report):
    issues = field(report, "issues", list)
    if not all(type(issue) is dict for issue in issues):
        raise ValueError("non_object_finding")
    declared = field(field(report, "summary", dict), "issue_count", int)
    assert declared == len(issues), "report_issue_denominator_disagrees"
    serialized = Counter(map(canonical, issues))
    independent = Counter(map(structural, issues))
    assert len(serialized) == len(independent)
    assert Counter({structural(strict_json(key)): count for key, count in serialized.items()}) == independent
    return set(serialized), independent, {
        "status": field(report, "status", str), "issue_row_denominator": len(issues),
        "declared_issue_denominator": declared, "identity_denominator": len(serialized),
        "independent_structural_identity_denominator": len(independent),
        "duplicate_row_count": len(issues) - len(serialized),
        "identity_set_sha256": sha(canonical(sorted(serialized)).encode()),
        "complete_report_sha256": sha(canonical(report).encode()),
    }


def original_report():
    ref = subprocess.check_output(["git", "rev-parse", REVISION + "^{commit}"], text=True).strip()
    raw = subprocess.check_output(["git", "show", ref + ":" + JOURNAL])
    text = raw.decode("utf-8")
    headings = list(re.finditer(r"^## GY-L\b[^\n]*$", text, re.M))
    assert len(headings) == 1, "GY_L_section_not_unique"
    start = headings[0].start()
    next_heading = re.search(r"^## ", text[headings[0].end():], re.M)
    end = headings[0].end() + next_heading.start() if next_heading else len(text)
    section = text[start:end]
    pattern = re.compile(r"Source `" + re.escape(STDOUT_SOURCE)
                         + r"`; UTF-8 bytes `(\d+)`; SHA-256 `([0-9a-f]{64})`\.\n\n```text\n(.*?)^```$", re.M | re.S)
    matches = list(pattern.finditer(section))
    assert len(matches) == 1, "complete_original_stdout_not_unique"
    match = matches[0]
    stdout = match[3].encode("utf-8")
    assert len(stdout) == int(match[1])
    assert sha(stdout) == "sha256:" + match[2]
    first = text.count("\n", 0, start + match.start(3)) + 1
    last = first + stdout.count(b"\n") - 1
    report = strict_json(stdout)
    return report, {
        "tracked_source": JOURNAL + "@" + ref, "journal_sha256": sha(raw),
        "section_start_line": text.count("\n", 0, start) + 1,
        "complete_stdout_start_line": first, "complete_stdout_end_line": last,
        "quoted_stdout_raw_byte_count": len(stdout), "quoted_stdout_sha256": sha(stdout),
        "quoted_stdout_integrity_independently_recomputed": True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--packet", type=int)
    args = parser.parse_args()
    old, provenance = original_report()
    raw = args.receipt.read_bytes()
    receipt = strict_json(raw)
    packets = []
    for stream in ("stdout", "stderr"):
        for number, line in enumerate(field(receipt, stream, str).splitlines(), 1):
            match = re.match(r"^[.FEspxXS]*GY_POST_OUTPUT_GX (.*)$", line)
            if match:
                packets.append((stream, number, strict_json(match[1])))
    assert args.packet is not None or len(packets) == 1, "select_exact_current_packet_no_unions"
    index = 0 if args.packet is None else args.packet
    assert 0 <= index < len(packets), "current_packet_index_unavailable"
    stream, line, packet = packets[index]
    current = field(packet, "report", dict)
    verification = field(packet, "verification", dict)
    before, before_structural, old_summary = identities(old)
    after, after_structural, current_summary = identities(current)
    declared = field(verification, "finding_identities", list)
    assert all(type(identity) is str for identity in declared)
    assert set(declared) == after and len(declared) == len(after), "current_verification_identity_drift"
    assert verification["status"] == current["status"]
    lost, added, same = before - after, after - before, before & after
    assert {structural(strict_json(key)) for key in lost} == set(before_structural) - set(after_structural)
    assert {structural(strict_json(key)) for key in added} == set(after_structural) - set(before_structural)
    assert {structural(strict_json(key)) for key in same} == set(before_structural) & set(after_structural)
    assert len(lost) + len(same) == len(before)
    assert len(added) + len(same) == len(after)
    assert args.receipt.read_bytes() == raw, "receipt_changed_during_read"
    print(json.dumps({
        "scope": "complete exact top-level GX finding identity sets; not transitive source-equivalence or inherited-red attribution",
        "original": {**provenance, **old_summary},
        "current": {"receipt": str(args.receipt), "receipt_sha256": sha(raw),
                    "receipt_returncode": field(receipt, "returncode", int),
                    "packet_index": index, "packet_stream": stream, "packet_line": line,
                    **current_summary},
        "exact_delta": {"unchanged_count": len(same), "lost_count": len(lost), "added_count": len(added),
                        "lost": [strict_json(identity) for identity in sorted(lost)],
                        "added": [strict_json(identity) for identity in sorted(added)]},
        "independent_structural_identity_delta_equal": True,
        "normalizations": "JSON object key order only; field names, values, types, absence/null, lines, hashes, counts, paths and list order remain exact",
        "attribution": "not_established: no slice-base command replay plus complete changed-input intersection has been established (P41)",
        "runtime_executed": False, "product_files_written": False,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
