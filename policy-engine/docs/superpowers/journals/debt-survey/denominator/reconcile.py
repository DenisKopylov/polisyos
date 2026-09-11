"""Read-only, independent identity reconciliation of the survey subject.

Run from policy-engine. The register supplies membership, never tree evidence.
The second derivation does not use the checker's line/cell/status helpers.
"""

import collections
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
from tools.quality.validation import check_debt_ledger as checker


def independent(document):
    """Enumerate complete table blocks; recognize whole status cells lexically.

    Only the first cell is split: later pipes may belong to code/prose. Status is
    a whole-cell token, not a column offset. Terminal-section/strikethrough
    semantics are the register's explicit presentation grammar.
    """
    result = []
    rejected = []
    sections = list(re.finditer(r"(?m)^## ([A-Z])\. .*$", document))
    for i, section in enumerate(sections):
        letter = section.group(1)
        if letter not in "ABCDEFG":
            continue
        end = sections[i + 1].start() if i + 1 < len(sections) else len(document)
        content = document[section.end():end]
        table_seen = False
        for block in re.findall(r"(?m)(?:^\|.*(?:\n|$))+", content):
            lines = block.splitlines()
            # All debt tables identify their first column as id/debt.
            has_header = bool(re.match(r"^\|\s*(?:id|debt)\s*\|", lines[0], re.I))
            table_seen |= has_header
            if not table_seen:
                continue
            for line in lines[1:] if has_header else lines:
                first, _, remainder = line[1:].partition("|")
                identifiers = re.findall(r"`([^`]+)`", first)
                if not identifiers:
                    if not re.fullmatch(r"\s*:?-+:?\s*", first):
                        rejected.append({"section": letter, "first_cell": first})
                    continue
                debt_id = identifiers[0]
                if letter == "E" and debt_id.startswith("codex/"):
                    continue
                if "~~" in first or letter == "G":
                    status = "closed"
                elif letter == "E":
                    status = "folded"
                else:
                    # Anchored boundaries avoid matching narrative mentions of a
                    # status within the subject or supersession history.
                    hits = re.findall(
                        r"(?:^|\|)\s*(?:\*\*)?`?"
                        r"(open_unmerged|open|blocked|closed|folded|ambiguous|foreign)"
                        r"`?(?:\*\*)?\s*(?=\|)", remainder
                    )
                    status = hits[0] if len(set(hits)) == 1 else "ambiguous"
                result.append((debt_id, letter, status))
    return result, rejected


def main():
    document = (ROOT / checker.REGISTER_PATH).read_text()
    parsed, irregular = checker._parse_register(document)
    a = [(r.debt_id, r.section, r.status) for r in parsed]
    b, rejected = independent(document)
    if len(a) != len(set(a)) or len(b) != len(set(b)):
        raise AssertionError("duplicate occurrences require explicit reconciliation")
    a_set, b_set = set(a), set(b)
    a_ids = {(i,s) for i,s,t in a}
    b_ids = {(i,s) for i,s,t in b}
    a_live = {x for x in a if x[2] in {"open", "blocked"}}
    b_live = {x for x in b if x[2] in {"open", "blocked"}}
    if a_ids != b_ids or a_live != b_live or rejected:
        print(json.dumps({"checker_only": sorted(a_set-b_set),
                          "independent_only": sorted(b_set-a_set),
                          "unclassified_first_cells": rejected}, indent=2))
        raise SystemExit(1)
    anchor = next(r for r in parsed if r.debt_id == "w5-institutional-authority-slots")
    assert (anchor.debt_id, "B", "blocked") in a_set & b_set
    routes_a = sorted(set(re.findall(r"W5-(?:R[2-6]|O5)-Q\d{2}", anchor.raw)))
    routes_b = sorted({token for token in anchor.raw.split("`")[1::2]
                       if token.startswith("W5-")})
    assert routes_a == routes_b and len(routes_a) == 18
    disagreements = [{"id": i, "section": s, "checker_status": t,
                      "whole_cell_status": next(v for j,u,v in b if (j,u)==(i,s)),
                      "survey_status": "ambiguous"}
                     for i,s,t in sorted(a_set-b_set)]
    identities = sorted(a_live)
    digest = hashlib.sha256(json.dumps(identities, separators=(",", ":")).encode()).hexdigest()
    naive = sum(r.section != "G" and bool(re.search(
        r"\|\s*`(?:open_unmerged|open|blocked|closed|folded|ambiguous|foreign)`\s*\|", r.raw))
                for r in parsed)
    report = {
        "base": "fc823071a",
        "derivation_a": "imported checker._parse_register; column-offset parser",
        "derivation_b": "independent table-block/whole-status-cell lexer",
        "all_identity_section_sets_equal": True,
        "live_identity_section_status_sets_equal": True,
        "live_identity_section_status_sha256": digest,
        "status_disagreements_retained_as_ambiguous": disagreements,
        "published_unique_id_denominator": checker.PUBLISHED_DENOMINATORS["register"],
        "observed_unique_id_denominator": len({x[0] for x in a}),
        "parsed_row_occurrences": len(a),
        "literal_status_debt_rows_outside_G": naive,
        "literal_scan_gap_partition": {"explicit_status_A_B_C_D_F": naive,
                                       "section_G_implicit_closed": sum(r.section == "G" for r in parsed),
                                       "section_E_implicit_folded": sum(r.section == "E" for r in parsed)},
        "status_distribution": dict(sorted(collections.Counter(x[2] for x in a).items())),
        "section_status_distribution": {s: dict(sorted(collections.Counter(x[2] for x in a if x[1] == s).items())) for s in "ABCDEFG"},
        "w5_ground_truth": {"section": anchor.section, "status": anchor.status, "unique_routes": routes_a},
        "irregular_branch_records_not_debts": irregular,
        "unclassifiable_ids": [x[0] for x in a if x[2] == "ambiguous"],
        "nonterminal": [{"id": i, "section": s, "status": t} for i,s,t in sorted(a) if t not in {"closed", "folded"}],
    }
    assert report["observed_unique_id_denominator"] == report["published_unique_id_denominator"]
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
