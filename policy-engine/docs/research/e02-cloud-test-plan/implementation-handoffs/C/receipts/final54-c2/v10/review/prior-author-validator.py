from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[5]
BASE = "198076863e143dea9f89f02734b13d50dae3eed5"
BASE_COVERAGE_PATH = "policy-engine/docs/research/e02-cloud-test-plan/closure-decisions/coverage.json"


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def git_bytes(spec: str) -> bytes:
    return subprocess.check_output(["git", "show", spec], cwd=ROOT)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def resolve_pointer(document: object, pointer: str) -> object:
    if pointer == "":
        return document
    if not pointer.startswith("/"):
        raise ValueError(f"invalid RFC 6901 pointer: {pointer!r}")
    current = document
    for raw in pointer[1:].split("/"):
        chars = []
        i = 0
        while i < len(raw):
            if raw[i] == "~":
                if i + 1 >= len(raw) or raw[i + 1] not in "01":
                    raise ValueError(f"invalid RFC 6901 escape: {pointer!r}")
                chars.append("/" if raw[i + 1] == "1" else "~")
                i += 2
            else:
                chars.append(raw[i])
                i += 1
        segment = "".join(chars)
        if isinstance(current, list):
            if not segment.isdigit() or (len(segment) > 1 and segment.startswith("0")):
                raise KeyError(f"invalid array index {segment!r} in {pointer!r}")
            current = current[int(segment)]
        elif isinstance(current, dict):
            current = current[segment]
        else:
            raise KeyError(f"cannot traverse {segment!r} in {pointer!r}")
    return current


def receipt_bytes(receipt: dict) -> bytes:
    path = receipt["path_at_sha256"].rsplit("@sha256:", 1)[0]
    if "head" in receipt:
        head = receipt["head"]
        if git("rev-parse", f"{head}^{{tree}}") != receipt["tree"]:
            raise AssertionError((receipt["path_at_sha256"], "tree mismatch"))
        actual = git_bytes(f"{head}:{path}")
        if receipt.get("blob") and git("rev-parse", f"{head}:{path}") != receipt["blob"]:
            raise AssertionError((receipt["path_at_sha256"], "blob mismatch"))
        return actual
    return (ROOT / path).read_bytes()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cut", type=Path)
    args = parser.parse_args()
    cut_path = args.cut if args.cut.is_absolute() else ROOT / args.cut
    cut_raw = cut_path.read_bytes()
    cut = json.loads(cut_raw)

    assert cut["status"] == "DRAFT_ONLY_PENDING_ROOT_ADJUDICATION"
    assert cut["final_verdicts_assigned"] is False
    assert cut["baseline_use_limit"].startswith("G97 is navigation only")
    snapshot = cut["snapshot"]
    assert git("rev-parse", snapshot["commit"] + "^{tree}") == snapshot["tree"]
    assert git("symbolic-ref", "--short", "HEAD") == snapshot["branch"]
    assert git("rev-parse", "HEAD") == snapshot["commit"]
    assert git("rev-parse", f"{BASE}^{{tree}}") == cut["base"]["tree"]

    coverage = json.loads(git_bytes(f"{BASE}:{BASE_COVERAGE_PATH}"))
    coverage_totals = {
        "all_bundles": len(coverage["bundles"]),
        "all_findings": len(coverage["findings"]),
        "canonical_criterion_occurrences": coverage["denominator"]["canonical_source_block_occurrences"],
    }
    assert coverage_totals == {
        key: cut["coverage_denominator_derived_from_pinned_coverage_json"][key]
        for key in coverage_totals
    }
    c_bundles = {x["id"] for x in coverage["bundles"] if x["unit"] == "C"}
    c_findings = {x["id"] for x in coverage["findings"] if x["unit"] == "C"}
    rows = cut["rows"]
    assert len(rows) == len(c_findings) == 54
    assert {row["id"] for row in rows} == c_findings
    assert {bundle for row in rows for bundle in row["bundles"]} == c_bundles
    assert sum(len(row["criterion_refs"]) for row in rows) == 59
    allowed_verdicts = {"closed", "limited", "held", "pending_review"}
    assert all(row["root_proposed_verdict"]["value"] in allowed_verdicts for row in rows)
    assert all(row["root_proposed_verdict"]["status"] == "provisional_not_final_root_adjudication" for row in rows)
    assert all(row["historical_status"] and row["code_outcome"] and row["deciding_receipts"] for row in rows)
    assert all(row["missing_inputs_or_skipped_backend"] and row["remaining_verification"] and row["next_owner"] for row in rows)

    criterion_index = cut["criterion_document_index"]
    for row in rows:
        for criterion in row["criterion_refs"]:
            ref = criterion_index[criterion["document_ref"]]
            git("cat-file", "-e", f"{ref['git_blob']}^{{blob}}")
            assert len(criterion["criterion_sha256"]) == 64
            assert criterion["line_span"]

    receipt_index = cut["receipt_index"]
    resolved_pointer_count = 0
    for receipt_id, receipt in receipt_index.items():
        raw = receipt_bytes(receipt)
        assert sha(raw) == receipt["sha256"], (receipt_id, "SHA-256 mismatch")
        assert len(raw) == receipt["size_bytes"], (receipt_id, "byte-count mismatch")
    for row in rows:
        for reference in row["deciding_receipts"]:
            receipt = receipt_index[reference["receipt_id"]]
            pointers = reference["json_pointers"]
            if pointers:
                raw = receipt_bytes(receipt)
                try:
                    document = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise AssertionError((reference["receipt_id"], "pointer targets non-JSON receipt")) from exc
                for pointer in pointers:
                    resolve_pointer(document, pointer)
                    resolved_pointer_count += 1

    assert cut["pointer_validation"]["standard"] == "RFC 6901"
    assert cut["pointer_validation"]["all_row_pointers_resolved"] is True
    assert cut["pointer_validation"]["resolved_pointer_count"] == resolved_pointer_count

    family_caps = {"DFI": 56, "CAT": 74}
    for family, expected_count in family_caps.items():
        family_ref = cut["topic_source_refs"][family]
        receipt_ids = family_ref["evidence_artifact_receipt_ids"]
        assert family_ref["evidence_artifact_count"] == expected_count == len(receipt_ids)
        assert all(receipt_id in receipt_index for receipt_id in receipt_ids)
        handoff = receipt_index[family_ref["handoff_receipt_id"]]
        handoff_raw = receipt_bytes(handoff)
        handoff_doc = json.loads(handoff_raw)
        entries = handoff_doc["evidence_artifacts"] if family == "DFI" else handoff_doc["evidence_files"]
        assert len(entries) == expected_count
        expected = {(entry["path"], entry["sha256"]) for entry in entries}
        actual = {
            (receipt_index[receipt_id]["path_at_sha256"].rsplit("@sha256:", 1)[0], receipt_index[receipt_id]["sha256"])
            for receipt_id in receipt_ids
        }
        assert actual == expected, (family, "evidence index mismatch")

    dag = cut["source_dag_review"]
    assert dag["semantic_closure_claimed"] is False
    assert len(dag["receipt_ids"]) == 3
    pubs = {
        "DFI": cut["input_receipts"]["DFI_current_publication_receipt_id"],
        "CAT": cut["input_receipts"]["CAT_current_publication_receipt_id"],
    }
    for family, receipt_id in pubs.items():
        publication = json.loads(receipt_bytes(receipt_index[receipt_id]))
        assert publication["complete"] is True
        topic = publication["topics"][0]
        assert topic["remote_readback_validated"] is True
        ref = cut["topic_source_refs"][family]
        assert topic["expected_head"] == ref["handoff_head"]
        assert topic["handoff_sha256"] == receipt_index[ref["handoff_receipt_id"]]["sha256"]

    print(json.dumps({
        "result": "PASS",
        "cut_path": str(cut_path.relative_to(ROOT)),
        "cut_sha256": sha(cut_raw),
        "snapshot": snapshot,
        "coverage": cut["coverage_denominator_derived_from_pinned_coverage_json"],
        "provisional_proposal_counts": cut["draft_root_proposal_counts_from_all_54_rows_not_final_closure_counts"],
        "rows": len(rows),
        "hash_bound_criterion_occurrences": 59,
        "tracked_receipts_hash_and_size_checked": len(receipt_index),
        "rfc6901_row_pointers_resolved": resolved_pointer_count,
        "evidence_caps": family_caps,
        "source_dag_semantic_closure_claimed": dag["semantic_closure_claimed"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
