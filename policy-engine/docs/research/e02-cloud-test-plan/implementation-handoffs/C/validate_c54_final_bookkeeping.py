from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path.cwd()
BASE = ""
SNAPSHOT = ""
COVERAGE_PATH = "policy-engine/docs/research/e02-cloud-test-plan/closure-decisions/coverage.json"
C_MD_PATH = "policy-engine/docs/research/e02-cloud-test-plan/closure-decisions/C.md"
INVENTORY_PATH = ""
EXPECTED_CUT_SHA: str | None = None
EXPECTED_MD_SHA: str | None = None
EXPECTED_INVENTORY_SHA: str | None = None
MARKDOWN_PATH: Path | None = None
EXPECTED_COVERAGE = {"all_bundles": 127, "all_findings": 282, "canonical_criterion_occurrences": 291,
                     "C_bundles": 33, "C_findings": 54, "C_hash_bound_criteria": 59}
ALLOWED_PROPOSALS = {"closed", "limited", "held", "pending_review"}


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def git_bytes(spec: str) -> bytes:
    return subprocess.check_output(["git", "show", spec], cwd=ROOT)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def resolve_pointer(document: object, pointer: str) -> object:
    if pointer == "":
        return document
    if not pointer.startswith("/"):
        raise ValueError(f"invalid RFC 6901 pointer: {pointer!r}")
    current = document
    for raw in pointer[1:].split("/"):
        chars: list[str] = []
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
                raise KeyError(f"invalid RFC 6901 array index {segment!r}: {pointer!r}")
            index = int(segment)
            if index >= len(current):
                raise KeyError(f"array index out of bounds {segment!r}: {pointer!r}")
            current = current[index]
        elif isinstance(current, dict):
            if segment not in current:
                raise KeyError(f"missing RFC 6901 object key {segment!r}: {pointer!r}")
            current = current[segment]
        else:
            raise KeyError(f"cannot traverse {segment!r} through {type(current).__name__}: {pointer!r}")
    return current


def declared_receipt_ids(value: object) -> set[str]:
    """Collect receipt references outside the receipt index itself."""
    found: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "receipt_index":
                continue
            found.update(declared_receipt_ids(child))
    elif isinstance(value, list):
        for child in value:
            found.update(declared_receipt_ids(child))
    elif isinstance(value, str) and re.fullmatch(r"R\d{2,3}", value):
        found.add(value)
    return found


receipt_cache: dict[tuple[str, str], bytes] = {}


def receipt_bytes(receipt: dict) -> bytes:
    entry = receipt["path_at_sha256"]
    path, separator, digest = entry.rpartition("@sha256:")
    if not separator or digest != receipt["sha256"]:
        raise AssertionError((entry, "locator suffix does not bind declared SHA-256"))
    head = receipt.get("head")
    if head:
        tree = git("rev-parse", f"{head}^{{tree}}")
        if tree != receipt.get("tree"):
            raise AssertionError((entry, "tree mismatch", tree, receipt.get("tree")))
        key = (head, path)
        raw = receipt_cache.get(key)
        if raw is None:
            raw = git_bytes(f"{head}:{path}")
            receipt_cache[key] = raw
        if receipt.get("blob"):
            blob = git("rev-parse", f"{head}:{path}")
            if blob != receipt["blob"]:
                raise AssertionError((entry, "blob mismatch", blob, receipt.get("blob")))
    else:
        raw = (ROOT / path).read_bytes()
    if sha(raw) != receipt["sha256"]:
        raise AssertionError((entry, "SHA-256 mismatch", sha(raw), receipt["sha256"]))
    if len(raw) != receipt["size_bytes"]:
        raise AssertionError((entry, "byte-count mismatch", len(raw), receipt["size_bytes"]))
    return raw


def norm_ws(value: str) -> str:
    return " ".join(value.split())


def parse_c_md(raw: bytes) -> dict[str, tuple[str, str]]:
    result: dict[str, tuple[str, str]] = {}
    for line in raw.decode("utf-8").splitlines():
        if "<a id=\"finding-" not in line:
            continue
        anchor = re.search(r'<a id="finding-([^"]+)"', line)
        cells = line.split("|")
        if anchor is None or len(cells) < 4:
            raise AssertionError(("unparseable C.md finding row", line[:160]))
        status_cell = cells[2]
        state = re.search(r"`([^`]+)`\s*/\s*`([^`]+)`", status_cell)
        if state is None:
            # A closed-bounded row uses an em dash, which denotes no missing capability label.
            state = re.search(r"`([^`]+)`\s*/\s*—", status_cell)
            if state is None:
                raise AssertionError(("unparseable C.md state", anchor.group(1), status_cell))
            status, capability = state.group(1), ""
        else:
            status, capability = state.group(1), state.group(2)
        finding_id = anchor.group(1).upper()
        finding_id = re.sub(r"^LA-(\d+)$", lambda m: f"LA-{int(m.group(1)):03d}", finding_id)
        if finding_id in result:
            raise AssertionError(("duplicate C.md finding row", finding_id))
        result[finding_id] = (status, capability)
    return result


def run(cut_path: Path, expected_sha: str | None) -> dict:
    cut_raw = cut_path.read_bytes()
    if expected_sha and sha(cut_raw) != expected_sha:
        raise AssertionError(("unexpected input cut hash", sha(cut_raw), expected_sha))
    cut = json.loads(cut_raw)
    if not cut["baseline_use_limit"].startswith("G97 is navigation only"):
        raise AssertionError("baseline use limit is missing")
    snapshot = cut["snapshot"]
    if snapshot.get("commit") != SNAPSHOT:
        raise AssertionError(("snapshot commit differs from --snapshot-commit", snapshot.get("commit"), SNAPSHOT))
    if git("rev-parse", f"{SNAPSHOT}^{{tree}}") != snapshot.get("tree"):
        raise AssertionError(("pinned snapshot tree mismatch", snapshot.get("commit"), snapshot.get("tree")))
    if cut["base"].get("commit") != BASE:
        raise AssertionError(("base commit differs from --base-commit", cut["base"].get("commit"), BASE))
    if git("rev-parse", f"{BASE}^{{tree}}") != cut["base"].get("tree"):
        raise AssertionError(("pinned base tree mismatch", BASE, cut["base"].get("tree")))
    if subprocess.run(["git", "merge-base", "--is-ancestor", BASE, SNAPSHOT], cwd=ROOT).returncode != 0:
        raise AssertionError(("pinned base is not an ancestor of snapshot", BASE, SNAPSHOT))

    coverage = json.loads(git_bytes(f"{BASE}:{COVERAGE_PATH}"))
    all_counts = {
        "all_bundles": len(coverage["bundles"]),
        "all_findings": len(coverage["findings"]),
        "canonical_criterion_occurrences": coverage["denominator"]["canonical_source_block_occurrences"],
    }
    c_findings = {x["id"]: x for x in coverage["findings"] if x["unit"] == "C"}
    c_bundles = {x["id"] for x in coverage["bundles"] if x["unit"] == "C"}
    criteria_count = sum(len(f.get("criterion_refs", [])) for f in c_findings.values())
    derived = {**all_counts, "C_bundles": len(c_bundles), "C_findings": len(c_findings),
               "C_hash_bound_criteria": criteria_count}
    if derived != EXPECTED_COVERAGE or derived != cut["coverage_denominator_derived_from_pinned_coverage_json"]:
        raise AssertionError(("coverage denominator mismatch", derived))

    rows = cut["rows"]
    if cut.get("status") == "DRAFT_ONLY_PENDING_ROOT_ADJUDICATION" and cut.get("final_verdicts_assigned") is False:
        verdict_field = "root_proposed_verdict"
        allowed_verdicts = {"closed", "limited", "held", "pending_review"}
        allowed_verdict_status = "provisional_not_final_root_adjudication"
        expected_summary = {"closed": 31, "limited": 9, "held": 14}
        final_mode = False
    elif cut.get("status") == "final_root_adjudicated" and cut.get("final_verdicts_assigned") is True:
        verdict_field = "root_finding_verdict"
        allowed_verdicts = {"closed", "limited", "held", "open"}
        allowed_verdict_status = "final_root_adjudication"
        expected_summary = {"closed": 31, "limited": 9, "held": 14}
        final_mode = True
    else:
        raise AssertionError(("cut status and final_verdicts_assigned do not form an accepted typed state",
                              cut.get("status"), cut.get("final_verdicts_assigned")))
    ids = {row["id"] for row in rows}
    if len(rows) != 54 or ids != set(c_findings):
        raise AssertionError(("C row identity mismatch", len(rows), len(ids), len(c_findings)))
    if sum(len(row["criterion_refs"]) for row in rows) != 59:
        raise AssertionError("criterion occurrence count is not 59")
    if {bundle for row in rows for bundle in row["bundles"]} != c_bundles:
        raise AssertionError("bundle union mismatch")
    verdict_values = []
    for row in rows:
        if verdict_field not in row or ("root_proposed_verdict" if final_mode else "root_finding_verdict") in row:
            raise AssertionError((row.get("id"), "verdict field does not match global cut state", verdict_field))
        verdict = row[verdict_field]
        if not isinstance(verdict, dict) or verdict.get("status") != allowed_verdict_status:
            raise AssertionError((row.get("id"), "verdict status does not match global cut state", verdict))
        if verdict.get("value") not in allowed_verdicts or not isinstance(verdict.get("reason"), str) or not verdict["reason"].strip():
            raise AssertionError((row.get("id"), "invalid typed verdict value or missing reason", verdict))
        if final_mode and any(token in verdict["reason"].casefold() for token in ("provisional", "proposal", "pending root adjudication")):
            raise AssertionError((row.get("id"), "final reason still describes a pending proposal", verdict["reason"]))
        verdict_values.append(verdict["value"])
    verdict_counts = Counter(verdict_values)
    if verdict_counts != Counter(expected_summary):
        raise AssertionError(("verdict counts mismatch", dict(verdict_counts), expected_summary))
    verdict_summary_aliases: list[dict[str, object]] = []

    def collect_verdict_summaries(value: object, path: str = "") -> None:
        if isinstance(value, dict):
            if value and set(value).issubset(allowed_verdicts) and all(type(count) is int and count >= 0 for count in value.values()):
                verdict_summary_aliases.append({"path": path or "/", "counts": dict(value)})
            for key, child in value.items():
                escaped = str(key).replace("~", "~0").replace("/", "~1")
                collect_verdict_summaries(child, f"{path}/{escaped}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                collect_verdict_summaries(child, f"{path}/{index}")

    collect_verdict_summaries(cut)
    if not verdict_summary_aliases:
        raise AssertionError("no declared verdict summary aliases were found")
    for alias in verdict_summary_aliases:
        if Counter(alias["counts"]) != verdict_counts:
            raise AssertionError(("declared verdict summary differs from the complete row set", alias, dict(verdict_counts)))

    criterion_index = cut["criterion_document_index"]
    doc_map = {}
    for document_ref, document in criterion_index.items():
        source_name = Path(document["path"]).name
        alias = source_name.removesuffix("_original.md")
        if alias in doc_map:
            raise AssertionError(("duplicate canonical criterion document alias", alias))
        doc_map[alias] = document_ref
    for finding_id, row in ((r["id"], r) for r in rows):
        canonical = c_findings[finding_id]
        if set(row["bundles"]) != set(canonical.get("companion_bundles", [])):
            raise AssertionError((finding_id, "bundle set differs from pinned coverage"))
        expected_criteria = []
        for c in canonical.get("criterion_refs", []):
            expected_criteria.append((c["criterion_id"], doc_map[c["document"]],
                                      f"{c['lines'][0]}-{c['lines'][1]}", c["sha256"]))
        actual_criteria = [(c["criterion_id"], c["document_ref"], c["line_span"], c["criterion_sha256"])
                           for c in row["criterion_refs"]]
        if Counter(actual_criteria) != Counter(expected_criteria):
            raise AssertionError((finding_id, "criterion refs differ from pinned coverage", actual_criteria, expected_criteria))
        for criterion in row["criterion_refs"]:
            doc_ref = criterion_index[criterion["document_ref"]]
            path = doc_ref["path"]
            blob = git("rev-parse", f"{BASE}:{path}")
            if blob != doc_ref["git_blob"]:
                raise AssertionError((finding_id, "criterion source blob mismatch", blob, doc_ref["git_blob"]))
            source = git_bytes(f"{BASE}:{path}").splitlines(keepends=True)
            start_s, end_s = criterion["line_span"].split("-")
            start, end = int(start_s), int(end_s)
            if not (1 <= start <= end <= len(source)):
                raise AssertionError((finding_id, "criterion span is out of bounds", criterion["line_span"]))
            actual_sha = sha(b"".join(source[start - 1:end]))
            if actual_sha != criterion["criterion_sha256"]:
                raise AssertionError((finding_id, "criterion source-span SHA mismatch", criterion["line_span"], actual_sha,
                                      criterion["criterion_sha256"]))
        if row["capability_label"] != (canonical.get("capability_label") or ""):
            raise AssertionError((finding_id, "base capability-label value mismatch", row["capability_label"], canonical.get("capability_label")))
        if row["historical_status"]["owner_tsv"] != canonical["ledger_status_historical"]:
            raise AssertionError((finding_id, "owner/history mismatch with pinned coverage"))
        if row["historical_status"]["appendix_C"] != canonical["appendix_c_status_separate"]:
            raise AssertionError((finding_id, "Appendix C history mismatch with pinned coverage"))
        verdict = row[verdict_field]
        if not verdict["reason"] or verdict["status"] != allowed_verdict_status:
            raise AssertionError((finding_id, "verdict lacks typed status or rationale"))
        if verdict["value"] not in allowed_verdicts:
            raise AssertionError((finding_id, "unrecognized verdict value"))
        if not row["code_outcome"] or not row["deciding_receipts"]:
            raise AssertionError((finding_id, "missing code outcome or deciding receipt"))

    # Bind current and base public C.md state rows to the pinned coverage labels.
    current_md = parse_c_md(git_bytes(f"{SNAPSHOT}:{C_MD_PATH}"))
    base_md = parse_c_md(git_bytes(f"{BASE}:{C_MD_PATH}"))
    if set(current_md) != ids:
        raise AssertionError(("current C.md denominator mismatch", len(current_md), len(ids), sorted(set(current_md) ^ ids)))
    if set(base_md) != ids:
        raise AssertionError(("base C.md denominator mismatch", len(base_md), len(ids)))
    label_deltas = []
    for finding_id, row in ((r["id"], r) for r in rows):
        cov = c_findings[finding_id]
        expected_state = (cov["ledger_status_historical"], cov.get("capability_label") or "")
        if current_md[finding_id] != expected_state:
            raise AssertionError((finding_id, "current C.md differs from pinned coverage", current_md[finding_id], expected_state))
        if current_md[finding_id][1] != row["capability_label"]:
            raise AssertionError((finding_id, "draft capability label differs from current C.md", row["capability_label"], current_md[finding_id]))
        if base_md[finding_id] != current_md[finding_id]:
            label_deltas.append({"id": finding_id, "base": base_md[finding_id], "current": current_md[finding_id]})

    # Independently check all historical columns against the canonical tracked TSV/hash.
    input_receipts = cut["input_receipts"]
    inventory_locator = input_receipts.get("inventory_tsv_path_at_sha256")
    if not isinstance(inventory_locator, str) or "@sha256:" not in inventory_locator:
        raise AssertionError("canonical inventory locator is missing")
    inventory_relative, inventory_locator_sha = inventory_locator.rsplit("@sha256:", 1)
    inventory_input_path = (ROOT / inventory_relative).resolve()
    if inventory_locator_sha != EXPECTED_INVENTORY_SHA or inventory_input_path != Path(INVENTORY_PATH).resolve():
        raise AssertionError(("canonical inventory locator differs from the validator input", inventory_locator,
                              str(Path(INVENTORY_PATH).resolve()), EXPECTED_INVENTORY_SHA))
    inventory_capture_locator = input_receipts.get("inventory_raw_capture_path_at_sha256")
    if not isinstance(inventory_capture_locator, str) or "@sha256:" not in inventory_capture_locator:
        raise AssertionError("historical raw inventory capture locator is missing")
    inventory_capture_path, inventory_capture_sha = inventory_capture_locator.rsplit("@sha256:", 1)
    if inventory_capture_sha != EXPECTED_INVENTORY_SHA or inventory_capture_path == inventory_relative:
        raise AssertionError(("historical raw inventory provenance is not distinct from the canonical input",
                              inventory_capture_locator, inventory_locator))
    inventory_raw = (ROOT / INVENTORY_PATH).read_bytes()
    if sha(inventory_raw) != EXPECTED_INVENTORY_SHA:
        raise AssertionError(("inventory SHA mismatch", sha(inventory_raw)))
    source_archive_locator = input_receipts.get("reviewed_source_archive_path_at_sha256")
    if not isinstance(source_archive_locator, str) or "@sha256:" not in source_archive_locator:
        raise AssertionError("tracked reviewed-source archive locator is missing")
    source_archive_relative, source_archive_sha = source_archive_locator.rsplit("@sha256:", 1)
    source_archive_path = (ROOT / source_archive_relative).resolve()
    source_archive_raw = source_archive_path.read_bytes()
    if sha(source_archive_raw) != source_archive_sha:
        raise AssertionError(("tracked reviewed-source archive SHA mismatch", source_archive_relative,
                              sha(source_archive_raw), source_archive_sha))
    source_uncompressed_sha = input_receipts.get("reviewed_source_uncompressed_sha256")
    if sha(gzip.decompress(source_archive_raw)) != source_uncompressed_sha:
        raise AssertionError(("tracked reviewed-source archive content SHA mismatch", source_uncompressed_sha))
    source_capture_locator = input_receipts.get("reviewed_source_raw_capture_path_at_sha256")
    if not isinstance(source_capture_locator, str) or "@sha256:" not in source_capture_locator:
        raise AssertionError("historical reviewed-source capture locator is missing")
    source_capture_path, source_capture_sha = source_capture_locator.rsplit("@sha256:", 1)
    if source_capture_sha != source_uncompressed_sha or source_capture_path == source_archive_relative:
        raise AssertionError(("historical reviewed-source provenance is not distinct from the canonical input",
                              source_capture_locator, source_archive_locator))
    inventory_rows = {row["finding_id"]: row for row in csv.DictReader(inventory_raw.decode("utf-8").splitlines(), delimiter="\t")}
    if set(inventory_rows) != ids:
        raise AssertionError(("inventory denominator mismatch", len(inventory_rows), len(ids)))
    history_columns = {
        "owner_tsv": "owner_TSV_source_status_historical",
        "G97_ledger": "residual_ledger_status_at_G97_historical",
        "appendix_C": "appendix_C_status_separate_historical",
        "historical_test": "historical_per_finding_test_status",
    }
    for row in rows:
        inv = inventory_rows[row["id"]]
        for draft_key, inv_key in history_columns.items():
            if row["historical_status"][draft_key] != inv[inv_key]:
                raise AssertionError((row["id"], "historical TSV value mismatch", draft_key,
                                      row["historical_status"][draft_key], inv[inv_key]))

    # Verify each indexed receipt's locator, Git tree/blob where provided, content hash, and size;
    # then resolve every row-declared RFC 6901 pointer with strict escaping and array-index rules.
    receipt_index = cut["receipt_index"]
    docs: dict[str, object] = {}
    for receipt_id, receipt in receipt_index.items():
        raw = receipt_bytes(receipt)
        if receipt.get("format") == "json":
            docs[receipt_id] = json.loads(raw)
    nested_manifest_receipts = []
    for receipt_id, receipt in receipt_index.items():
        pointer = receipt.get("nested_file_manifest_pointer")
        if pointer is None:
            continue
        if receipt_id not in docs:
            raise AssertionError((receipt_id, "nested file manifest is not JSON"))
        path_field = receipt.get("nested_file_path_field")
        sha_field = receipt.get("nested_file_sha256_field")
        size_field = receipt.get("nested_file_size_field")
        if not all(isinstance(name, str) and name for name in (path_field, sha_field, size_field)):
            raise AssertionError((receipt_id, "nested file manifest field mapping is incomplete"))
        entries = resolve_pointer(docs[receipt_id], pointer)
        if not isinstance(entries, list):
            raise AssertionError((receipt_id, "nested file manifest pointer does not resolve to a list"))
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                raise AssertionError((receipt_id, index, "nested manifest item is not an object"))
            path_value = entry.get(path_field)
            digest_value = entry.get(sha_field)
            size_value = entry.get(size_field)
            if not isinstance(path_value, str) or not isinstance(digest_value, str) or not isinstance(size_value, int):
                raise AssertionError((receipt_id, index, "nested manifest item has invalid path, hash, or size"))
            nested_path = Path(path_value)
            if nested_path.is_absolute() or ".." in nested_path.parts:
                raise AssertionError((receipt_id, index, "nested manifest path must stay under repository root", path_value))
            nested_raw = (ROOT / nested_path).read_bytes()
            if sha(nested_raw) != digest_value or len(nested_raw) != size_value:
                raise AssertionError((receipt_id, index, "nested file hash/size mismatch", path_value))
        nested_manifest_receipts.append({"receipt_id": receipt_id, "files": len(entries)})
    resolved = 0
    pointers_by_row: dict[str, int] = {}
    for row in rows:
        row_pointer_count = 0
        for ref in row["deciding_receipts"]:
            receipt_id = ref["receipt_id"]
            if receipt_id not in receipt_index:
                raise AssertionError((row["id"], "unknown deciding receipt", receipt_id))
            pointers = ref["json_pointers"]
            if pointers:
                if receipt_id not in docs:
                    raise AssertionError((row["id"], receipt_id, "JSON pointer targets a non-JSON receipt"))
                for pointer in pointers:
                    resolve_pointer(docs[receipt_id], pointer)
                    resolved += 1
                    row_pointer_count += 1
        pointers_by_row[row["id"]] = row_pointer_count
    # Reconcile any receipt-index binding declared by a receipt itself. Derive the
    # bound source IDs/pointers from the input rather than encoding one handoff's IDs.
    manifest_bound_receipts = []
    for receipt_id, receipt in receipt_index.items():
        has_manifest_link = "manifest_receipt_id" in receipt or "manifest_json_pointer" in receipt
        if not has_manifest_link:
            continue
        if not {"manifest_receipt_id", "manifest_json_pointer"}.issubset(receipt):
            raise AssertionError((receipt_id, "incomplete manifest receipt-index binding"))
        index_id = receipt["manifest_receipt_id"]
        if index_id not in docs:
            raise AssertionError((receipt_id, "manifest index receipt is absent or not JSON", index_id))
        entry = resolve_pointer(docs[index_id], receipt["manifest_json_pointer"])
        if not isinstance(entry, dict):
            raise AssertionError((receipt_id, "manifest pointer does not resolve to an object"))
        path = receipt["path_at_sha256"].rsplit("@sha256:", 1)[0]
        expected_entry = {"path": path, "sha256": receipt["sha256"], "size_bytes": receipt["size_bytes"]}
        actual_entry = {key: entry.get(key) for key in expected_entry}
        if actual_entry != expected_entry:
            raise AssertionError((receipt_id, "declared manifest-index value mismatch", actual_entry, expected_entry))
        manifest_bound_receipts.append(receipt_id)
    if resolved != 282 or cut["pointer_validation"] != {
        "standard": "RFC 6901", "all_row_pointers_resolved": True, "resolved_pointer_count": 282
    }:
        raise AssertionError(("pointer validation count/claim mismatch", resolved, cut["pointer_validation"]))

    # Verify complete source-field binding, not just the summary text.
    evidence_modes = Counter()
    enum_only_ing = []
    for row in rows:
        evidence = row["code_outcome_evidence"]
        mode = evidence["mode"]
        evidence_modes[mode] += 1
        if mode == "complete_source_field_whitespace_normalized":
            receipt_id = evidence["receipt_id"]
            if receipt_id not in docs:
                raise AssertionError((row["id"], "source-field receipt not JSON"))
            source_record = resolve_pointer(docs[receipt_id], evidence["json_pointer"])
            if not isinstance(source_record, dict) or not isinstance(source_record.get(evidence["field"]), str):
                raise AssertionError((row["id"], "source-field binding does not reach string field"))
            source_value = norm_ws(source_record[evidence["field"]])
            source_hash = sha(source_value.encode("utf-8"))
            if source_hash != evidence["source_value_sha256"] or source_value != row["code_outcome"]:
                raise AssertionError((row["id"], "complete source-field content binding mismatch", source_hash,
                                      evidence["source_value_sha256"]))
            if not any(ref["receipt_id"] == receipt_id for ref in row["deciding_receipts"]):
                raise AssertionError((row["id"], "source-field receipt is not listed among deciding receipts"))
        elif mode not in {"authored_criterion_summary_cited_by_deciding_receipts",
                          "authored_family_scope_summary_cited_by_deciding_receipts"}:
            raise AssertionError((row["id"], "unknown source summary evidence mode", mode))
        if row["source_family"] == "ING" and row["code_outcome"] in {
            "implemented_bounded_with_typed_refusal", "implemented_and_independently_verified"
        }:
            enum_only_ing.append(row["id"])

    # Review the supplied Markdown denominator/header and current source DAG handoff.
    if MARKDOWN_PATH is None:
        raise AssertionError("--markdown was not supplied")
    md_raw = MARKDOWN_PATH.read_bytes()
    md_hash = sha(md_raw)
    if EXPECTED_MD_SHA and md_hash != EXPECTED_MD_SHA:
        raise AssertionError(("Markdown SHA mismatch", md_hash, EXPECTED_MD_SHA))
    md_text = md_raw.decode("utf-8")
    visible_ids = re.findall(r"^\|\s*([A-Z]+(?:-\d+)?\d*)\s*\|", md_text, flags=re.MULTILINE)
    table_rows = [line for line in md_text.splitlines() if re.match(r"^\|\s*(?:B\d+|LA-\d+)\s*\|", line)]
    if len(table_rows) != 54 or len(set(visible_ids)) < 54:
        # The visible ID regex accommodates B138 and LA-031; use the table rows as denominator.
        raise AssertionError(("Markdown table denominator mismatch", len(table_rows), len(visible_ids)))
    table_header_lines = [line for line in md_text.splitlines() if line.startswith("| ID | Bundles / hash-bound criteria |")]
    if len(table_header_lines) != 1:
        raise AssertionError(("Markdown table header count is not exactly one", len(table_header_lines)))
    if any(f"| {row['id']} |" not in md_text for row in rows):
        raise AssertionError("Markdown table omits a JSON row")

    dag = cut["source_dag_review"]
    if dag["semantic_closure_claimed"] is not False or any(r not in receipt_index for r in dag["receipt_ids"]):
        raise AssertionError("source DAG scope/receipt binding mismatch")
    declared_ids = declared_receipt_ids(cut)
    if declared_ids != set(receipt_index):
        raise AssertionError(("receipt-index does not equal the complete declared receipt set",
                              sorted(declared_ids - set(receipt_index)),
                              sorted(set(receipt_index) - declared_ids)))
    if resolved != 282:
        raise AssertionError(("RFC 6901 pointer denominator mismatch", resolved))

    per_row = []
    for row in rows:
        per_row.append({
            "id": row["id"],
            "verdict": row[verdict_field]["value"],
            "historical": row["historical_status"],
            "baseline_capability_label": row["capability_label"],
            "source_family": row["source_family"],
            "evidence_mode": row["code_outcome_evidence"]["mode"],
            "criterion_occurrences": len(row["criterion_refs"]),
            "deciding_receipts": len(row["deciding_receipts"]),
            "resolved_pointers": pointers_by_row[row["id"]],
        })
    return {
        "result": "PASS",
        "cut_sha256": sha(cut_raw),
        "companion_markdown_sha256": md_hash,
        "snapshot": cut["snapshot"],
        "base": cut["base"],
        "coverage_denominator": derived,
        "rows": len(rows),
        "verdict_counts": dict(verdict_counts),
        "verdict_summary_aliases_checked": verdict_summary_aliases,
        "verdict_field": verdict_field,
        "verdict_status": allowed_verdict_status,
        "historical_inventory_rows_and_four_columns_checked": len(inventory_rows),
        "current_C_md_rows_checked": len(current_md),
        "base_to_current_C_md_state_deltas": label_deltas,
        "criterion_occurrences_source_line_span_and_SHA_checked": 59,
        "receipt_entries_SHA_size_locator_tree_blob_checked": len(receipt_index),
        "receipt_ids_derived_from_complete_declared_index": len(declared_ids),
        "nested_file_manifests_SHA_and_size_checked": nested_manifest_receipts,
        "RFC_6901_pointers_resolved": resolved,
        "code_outcome_evidence_modes": dict(evidence_modes),
        "ING_enum_only_code_outcomes": enum_only_ing,
        "companion_Markdown_rows": len(table_rows),
        "source_DAG_semantic_closure_claimed": dag["semantic_closure_claimed"],
        "manifest_index_bound_receipts": manifest_bound_receipts,
        "per_row": per_row,
    }


def main() -> None:
    global ROOT, BASE, SNAPSHOT, INVENTORY_PATH, EXPECTED_CUT_SHA, EXPECTED_MD_SHA, EXPECTED_INVENTORY_SHA, MARKDOWN_PATH
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--cut", required=True, type=Path)
    parser.add_argument("--markdown", required=True, type=Path)
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--base-commit", required=True)
    parser.add_argument("--snapshot-commit", required=True)
    parser.add_argument("--expected-cut-sha")
    parser.add_argument("--expected-markdown-sha", required=True)
    parser.add_argument("--expected-inventory-sha", required=True)
    args = parser.parse_args()
    ROOT = args.repo_root.resolve()
    BASE = args.base_commit
    SNAPSHOT = args.snapshot_commit
    EXPECTED_CUT_SHA = args.expected_cut_sha
    EXPECTED_MD_SHA = args.expected_markdown_sha
    EXPECTED_INVENTORY_SHA = args.expected_inventory_sha
    cut_path = args.cut if args.cut.is_absolute() else ROOT / args.cut
    MARKDOWN_PATH = args.markdown if args.markdown.is_absolute() else ROOT / args.markdown
    INVENTORY_PATH = str(args.inventory if args.inventory.is_absolute() else ROOT / args.inventory)
    result = run(cut_path, EXPECTED_CUT_SHA)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
