from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
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
LOCAL_EVIDENCE_ROOT: Path | None = None
EXPECTED_COVERAGE = {
    "all_bundles": 127,
    "all_findings": 282,
    "canonical_criterion_occurrences": 291,
    "C_bundles": 33,
    "C_findings": 54,
    "C_hash_bound_criteria": 59,
}
ALLOWED_PROPOSALS = {"closed", "limited", "held", "pending_review"}
C3_CUT_SCHEMA = "policyos.e02.c54.c3.current-evidence-census.v2"
C3_INPUT_SCHEMA = "policyos.e02.c54.c3.current-evaluation-input.v2"
C3_FINAL_CUT_SCHEMA = "policyos.e02.c54.c3.current-root-adjudication.v1"
C3_FINAL_INPUT_SCHEMA = "policyos.e02.c54.c3.current-root-adjudication-input.v1"
C3_INPUT_PATH = (
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/C/"
    "C54-c3-current-evaluation-input.json"
)
C3_V10_PATH = (
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/C/"
    "C54-final-20261006-v10.json"
)
C3_V10_MARKDOWN_PATH = (
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/C/"
    "C54-final-20261006-v10.md"
)
C3_COVERAGE_PATH = "policy-engine/docs/research/e02-cloud-test-plan/closure-decisions/coverage.json"
C3_FINDING_OWNERS_PATH = (
    "policy-engine/docs/research/e02-cloud-test-plan/execution-organization/finding-owners.tsv"
)
C3_BUNDLE_OWNERS_PATH = (
    "policy-engine/docs/research/e02-cloud-test-plan/execution-organization/bundle-owners.tsv"
)
C3_EXPECTED_C2_COMMIT = "c158689d692d47b6300609ac2ba5e7dac28650dc"
C3_EXPECTED_C2_TREE = "573063f560533e73518ef87d29acc1a46959cf33"
C3_EXPECTED_C2_BLOB = "61e1abe90ae5f81e37077e2dc8e92f7e4de0cb76"
C3_EXPECTED_C2_SHA = "38db6cac4195f210425502bd4c7fdf2884ccdb5ae42ef87170d17020a6358dcc"
C3_EXPECTED_G_COMMIT = "a0ac10fc11975c345312034d0e568b4cfc330d76"
C3_EXPECTED_G_TREE = "ae067d9bcd96ff123b76d3b6eebef27a1736079c"
C3_FINAL_EXPECTED_G_COMMIT = "ebae80eaa25482d84bc6ad2e78721bc318bc0228"
C3_FINAL_EXPECTED_G_TREE = "4bc0ca606eaf5145e23769da3968a673d99a9abf"


def git(*args: str) -> str:
    return subprocess.check_output(  # noqa: S603 - trusted Git command with argv; shell disabled.
        ["git", *args],  # noqa: S607 - trusted Git executable resolved by PATH.
        cwd=ROOT,
        text=True,
    ).strip()


def git_bytes(spec: str) -> bytes:
    return subprocess.check_output(  # noqa: S603 - trusted Git command with argv; shell disabled.
        ["git", "show", spec],  # noqa: S607 - trusted Git executable resolved by PATH.
        cwd=ROOT,
    )


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
            raise KeyError(
                f"cannot traverse {segment!r} through {type(current).__name__}: {pointer!r}"
            )
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
PORTABLE_RECEIPT_OVERRIDES: dict[str, bytes] = {}


def receipt_bytes(receipt: dict) -> bytes:
    entry = receipt["path_at_sha256"]
    path, separator, digest = entry.rpartition("@sha256:")
    if not separator or digest != receipt["sha256"]:
        raise AssertionError((entry, "locator suffix does not bind declared SHA-256"))
    portable_raw = PORTABLE_RECEIPT_OVERRIDES.get(entry)
    if portable_raw is not None:
        raw = portable_raw
        if sha(raw) != receipt["sha256"] or len(raw) != receipt["size_bytes"]:
            raise AssertionError(
                (entry, "portable companion differs from historical receipt bytes")
            )
        return raw
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
        local_path = ROOT / path
        if not local_path.exists() and LOCAL_EVIDENCE_ROOT is not None:
            local_path = LOCAL_EVIDENCE_ROOT / path
        raw = local_path.read_bytes()
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
        if '<a id="finding-' not in line:
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
        raise AssertionError(
            ("snapshot commit differs from --snapshot-commit", snapshot.get("commit"), SNAPSHOT)
        )
    if git("rev-parse", f"{SNAPSHOT}^{{tree}}") != snapshot.get("tree"):
        raise AssertionError(
            ("pinned snapshot tree mismatch", snapshot.get("commit"), snapshot.get("tree"))
        )
    if cut["base"].get("commit") != BASE:
        raise AssertionError(
            ("base commit differs from --base-commit", cut["base"].get("commit"), BASE)
        )
    if git("rev-parse", f"{BASE}^{{tree}}") != cut["base"].get("tree"):
        raise AssertionError(("pinned base tree mismatch", BASE, cut["base"].get("tree")))
    if (
        subprocess.run(  # noqa: S603 - trusted Git ancestry query; argv and shell disabled.
            ["git", "merge-base", "--is-ancestor", BASE, SNAPSHOT],  # noqa: S607 - Git executable.
            cwd=ROOT,
        ).returncode
        != 0
    ):
        raise AssertionError(("pinned base is not an ancestor of snapshot", BASE, SNAPSHOT))

    coverage = json.loads(git_bytes(f"{BASE}:{COVERAGE_PATH}"))
    all_counts = {
        "all_bundles": len(coverage["bundles"]),
        "all_findings": len(coverage["findings"]),
        "canonical_criterion_occurrences": coverage["denominator"][
            "canonical_source_block_occurrences"
        ],
    }
    c_findings = {x["id"]: x for x in coverage["findings"] if x["unit"] == "C"}
    c_bundles = {x["id"] for x in coverage["bundles"] if x["unit"] == "C"}
    criteria_count = sum(len(f.get("criterion_refs", [])) for f in c_findings.values())
    derived = {
        **all_counts,
        "C_bundles": len(c_bundles),
        "C_findings": len(c_findings),
        "C_hash_bound_criteria": criteria_count,
    }
    if (
        derived != EXPECTED_COVERAGE
        or derived != cut["coverage_denominator_derived_from_pinned_coverage_json"]
    ):
        raise AssertionError(("coverage denominator mismatch", derived))

    rows = cut["rows"]
    if (
        cut.get("status") == "DRAFT_ONLY_PENDING_ROOT_ADJUDICATION"
        and cut.get("final_verdicts_assigned") is False
    ):
        verdict_field = "root_proposed_verdict"
        allowed_verdicts = {"closed", "limited", "held", "pending_review"}
        allowed_verdict_status = "provisional_not_final_root_adjudication"
        expected_summary = {"closed": 31, "limited": 9, "held": 14}
        final_mode = False
    elif (
        cut.get("status") == "final_root_adjudicated" and cut.get("final_verdicts_assigned") is True
    ):
        verdict_field = "root_finding_verdict"
        allowed_verdicts = {"closed", "limited", "held", "open"}
        allowed_verdict_status = "final_root_adjudication"
        expected_summary = {"closed": 31, "limited": 9, "held": 14}
        final_mode = True
    else:
        raise AssertionError(
            (
                "cut status and final_verdicts_assigned do not form an accepted typed state",
                cut.get("status"),
                cut.get("final_verdicts_assigned"),
            )
        )
    ids = {row["id"] for row in rows}
    if len(rows) != 54 or ids != set(c_findings):
        raise AssertionError(("C row identity mismatch", len(rows), len(ids), len(c_findings)))
    if sum(len(row["criterion_refs"]) for row in rows) != 59:
        raise AssertionError("criterion occurrence count is not 59")
    if {bundle for row in rows for bundle in row["bundles"]} != c_bundles:
        raise AssertionError("bundle union mismatch")
    verdict_values = []
    for row in rows:
        if (
            verdict_field not in row
            or ("root_proposed_verdict" if final_mode else "root_finding_verdict") in row
        ):
            raise AssertionError(
                (row.get("id"), "verdict field does not match global cut state", verdict_field)
            )
        verdict = row[verdict_field]
        if not isinstance(verdict, dict) or verdict.get("status") != allowed_verdict_status:
            raise AssertionError(
                (row.get("id"), "verdict status does not match global cut state", verdict)
            )
        if (
            verdict.get("value") not in allowed_verdicts
            or not isinstance(verdict.get("reason"), str)
            or not verdict["reason"].strip()
        ):
            raise AssertionError(
                (row.get("id"), "invalid typed verdict value or missing reason", verdict)
            )
        if final_mode and any(
            token in verdict["reason"].casefold()
            for token in ("provisional", "proposal", "pending root adjudication")
        ):
            raise AssertionError(
                (
                    row.get("id"),
                    "final reason still describes a pending proposal",
                    verdict["reason"],
                )
            )
        verdict_values.append(verdict["value"])
    verdict_counts = Counter(verdict_values)
    if verdict_counts != Counter(expected_summary):
        raise AssertionError(("verdict counts mismatch", dict(verdict_counts), expected_summary))
    verdict_summary_aliases: list[dict[str, object]] = []

    def collect_verdict_summaries(value: object, path: str = "") -> None:
        if isinstance(value, dict):
            if (
                value
                and set(value).issubset(allowed_verdicts)
                and all(type(count) is int and count >= 0 for count in value.values())
            ):
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
            raise AssertionError(
                (
                    "declared verdict summary differs from the complete row set",
                    alias,
                    dict(verdict_counts),
                )
            )

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
            expected_criteria.append(
                (
                    c["criterion_id"],
                    doc_map[c["document"]],
                    f"{c['lines'][0]}-{c['lines'][1]}",
                    c["sha256"],
                )
            )
        actual_criteria = [
            (c["criterion_id"], c["document_ref"], c["line_span"], c["criterion_sha256"])
            for c in row["criterion_refs"]
        ]
        if Counter(actual_criteria) != Counter(expected_criteria):
            raise AssertionError(
                (
                    finding_id,
                    "criterion refs differ from pinned coverage",
                    actual_criteria,
                    expected_criteria,
                )
            )
        for criterion in row["criterion_refs"]:
            doc_ref = criterion_index[criterion["document_ref"]]
            path = doc_ref["path"]
            blob = git("rev-parse", f"{BASE}:{path}")
            if blob != doc_ref["git_blob"]:
                raise AssertionError(
                    (finding_id, "criterion source blob mismatch", blob, doc_ref["git_blob"])
                )
            source = git_bytes(f"{BASE}:{path}").splitlines(keepends=True)
            start_s, end_s = criterion["line_span"].split("-")
            start, end = int(start_s), int(end_s)
            if not (1 <= start <= end <= len(source)):
                raise AssertionError(
                    (finding_id, "criterion span is out of bounds", criterion["line_span"])
                )
            actual_sha = sha(b"".join(source[start - 1 : end]))
            if actual_sha != criterion["criterion_sha256"]:
                raise AssertionError(
                    (
                        finding_id,
                        "criterion source-span SHA mismatch",
                        criterion["line_span"],
                        actual_sha,
                        criterion["criterion_sha256"],
                    )
                )
        if row["capability_label"] != (canonical.get("capability_label") or ""):
            raise AssertionError(
                (
                    finding_id,
                    "base capability-label value mismatch",
                    row["capability_label"],
                    canonical.get("capability_label"),
                )
            )
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
        raise AssertionError(
            (
                "current C.md denominator mismatch",
                len(current_md),
                len(ids),
                sorted(set(current_md) ^ ids),
            )
        )
    if set(base_md) != ids:
        raise AssertionError(("base C.md denominator mismatch", len(base_md), len(ids)))
    label_deltas = []
    for finding_id, row in ((r["id"], r) for r in rows):
        cov = c_findings[finding_id]
        expected_state = (cov["ledger_status_historical"], cov.get("capability_label") or "")
        if current_md[finding_id] != expected_state:
            raise AssertionError(
                (
                    finding_id,
                    "current C.md differs from pinned coverage",
                    current_md[finding_id],
                    expected_state,
                )
            )
        if current_md[finding_id][1] != row["capability_label"]:
            raise AssertionError(
                (
                    finding_id,
                    "draft capability label differs from current C.md",
                    row["capability_label"],
                    current_md[finding_id],
                )
            )
        if base_md[finding_id] != current_md[finding_id]:
            label_deltas.append(
                {"id": finding_id, "base": base_md[finding_id], "current": current_md[finding_id]}
            )

    # Independently check all historical columns against the canonical tracked TSV/hash.
    input_receipts = cut["input_receipts"]
    inventory_locator = input_receipts.get("inventory_tsv_path_at_sha256")
    if not isinstance(inventory_locator, str) or "@sha256:" not in inventory_locator:
        raise AssertionError("canonical inventory locator is missing")
    inventory_relative, inventory_locator_sha = inventory_locator.rsplit("@sha256:", 1)
    inventory_input_path = (ROOT / inventory_relative).resolve()
    if (
        inventory_locator_sha != EXPECTED_INVENTORY_SHA
        or inventory_input_path != Path(INVENTORY_PATH).resolve()
    ):
        raise AssertionError(
            (
                "canonical inventory locator differs from the validator input",
                inventory_locator,
                str(Path(INVENTORY_PATH).resolve()),
                EXPECTED_INVENTORY_SHA,
            )
        )
    inventory_capture_locator = input_receipts.get("inventory_raw_capture_path_at_sha256")
    if (
        not isinstance(inventory_capture_locator, str)
        or "@sha256:" not in inventory_capture_locator
    ):
        raise AssertionError("historical raw inventory capture locator is missing")
    inventory_capture_path, inventory_capture_sha = inventory_capture_locator.rsplit("@sha256:", 1)
    if (
        inventory_capture_sha != EXPECTED_INVENTORY_SHA
        or inventory_capture_path == inventory_relative
    ):
        raise AssertionError(
            (
                "historical raw inventory provenance is not distinct from the canonical input",
                inventory_capture_locator,
                inventory_locator,
            )
        )
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
        raise AssertionError(
            (
                "tracked reviewed-source archive SHA mismatch",
                source_archive_relative,
                sha(source_archive_raw),
                source_archive_sha,
            )
        )
    source_uncompressed_sha = input_receipts.get("reviewed_source_uncompressed_sha256")
    if sha(gzip.decompress(source_archive_raw)) != source_uncompressed_sha:
        raise AssertionError(
            ("tracked reviewed-source archive content SHA mismatch", source_uncompressed_sha)
        )
    source_capture_locator = input_receipts.get("reviewed_source_raw_capture_path_at_sha256")
    if not isinstance(source_capture_locator, str) or "@sha256:" not in source_capture_locator:
        raise AssertionError("historical reviewed-source capture locator is missing")
    source_capture_path, source_capture_sha = source_capture_locator.rsplit("@sha256:", 1)
    if (
        source_capture_sha != source_uncompressed_sha
        or source_capture_path == source_archive_relative
    ):
        raise AssertionError(
            (
                "historical reviewed-source provenance is not distinct from the canonical input",
                source_capture_locator,
                source_archive_locator,
            )
        )
    inventory_rows = {
        row["finding_id"]: row
        for row in csv.DictReader(inventory_raw.decode("utf-8").splitlines(), delimiter="\t")
    }
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
                raise AssertionError(
                    (
                        row["id"],
                        "historical TSV value mismatch",
                        draft_key,
                        row["historical_status"][draft_key],
                        inv[inv_key],
                    )
                )

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
            raise AssertionError(
                (receipt_id, "nested file manifest pointer does not resolve to a list")
            )
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                raise AssertionError((receipt_id, index, "nested manifest item is not an object"))
            path_value = entry.get(path_field)
            digest_value = entry.get(sha_field)
            size_value = entry.get(size_field)
            if (
                not isinstance(path_value, str)
                or not isinstance(digest_value, str)
                or not isinstance(size_value, int)
            ):
                raise AssertionError(
                    (receipt_id, index, "nested manifest item has invalid path, hash, or size")
                )
            nested_path = Path(path_value)
            if nested_path.is_absolute() or ".." in nested_path.parts:
                raise AssertionError(
                    (
                        receipt_id,
                        index,
                        "nested manifest path must stay under repository root",
                        path_value,
                    )
                )
            nested_raw = (ROOT / nested_path).read_bytes()
            if sha(nested_raw) != digest_value or len(nested_raw) != size_value:
                raise AssertionError(
                    (receipt_id, index, "nested file hash/size mismatch", path_value)
                )
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
                    raise AssertionError(
                        (row["id"], receipt_id, "JSON pointer targets a non-JSON receipt")
                    )
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
            raise AssertionError(
                (receipt_id, "manifest index receipt is absent or not JSON", index_id)
            )
        entry = resolve_pointer(docs[index_id], receipt["manifest_json_pointer"])
        if not isinstance(entry, dict):
            raise AssertionError((receipt_id, "manifest pointer does not resolve to an object"))
        path = receipt["path_at_sha256"].rsplit("@sha256:", 1)[0]
        expected_entry = {
            "path": path,
            "sha256": receipt["sha256"],
            "size_bytes": receipt["size_bytes"],
        }
        actual_entry = {key: entry.get(key) for key in expected_entry}
        if actual_entry != expected_entry:
            raise AssertionError(
                (receipt_id, "declared manifest-index value mismatch", actual_entry, expected_entry)
            )
        manifest_bound_receipts.append(receipt_id)
    if resolved != 282 or cut["pointer_validation"] != {
        "standard": "RFC 6901",
        "all_row_pointers_resolved": True,
        "resolved_pointer_count": 282,
    }:
        raise AssertionError(
            ("pointer validation count/claim mismatch", resolved, cut["pointer_validation"])
        )

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
            if not isinstance(source_record, dict) or not isinstance(
                source_record.get(evidence["field"]), str
            ):
                raise AssertionError(
                    (row["id"], "source-field binding does not reach string field")
                )
            source_value = norm_ws(source_record[evidence["field"]])
            source_hash = sha(source_value.encode("utf-8"))
            if (
                source_hash != evidence["source_value_sha256"]
                or source_value != row["code_outcome"]
            ):
                raise AssertionError(
                    (
                        row["id"],
                        "complete source-field content binding mismatch",
                        source_hash,
                        evidence["source_value_sha256"],
                    )
                )
            if not any(ref["receipt_id"] == receipt_id for ref in row["deciding_receipts"]):
                raise AssertionError(
                    (row["id"], "source-field receipt is not listed among deciding receipts")
                )
        elif mode not in {
            "authored_criterion_summary_cited_by_deciding_receipts",
            "authored_family_scope_summary_cited_by_deciding_receipts",
        }:
            raise AssertionError((row["id"], "unknown source summary evidence mode", mode))
        if row["source_family"] == "ING" and row["code_outcome"] in {
            "implemented_bounded_with_typed_refusal",
            "implemented_and_independently_verified",
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
    table_rows = [
        line for line in md_text.splitlines() if re.match(r"^\|\s*(?:B\d+|LA-\d+)\s*\|", line)
    ]
    if len(table_rows) != 54 or len(set(visible_ids)) < 54:
        # The visible ID regex accommodates B138 and LA-031; use the table rows as denominator.
        raise AssertionError(
            ("Markdown table denominator mismatch", len(table_rows), len(visible_ids))
        )
    table_header_lines = [
        line
        for line in md_text.splitlines()
        if line.startswith("| ID | Bundles / hash-bound criteria |")
    ]
    if len(table_header_lines) != 1:
        raise AssertionError(
            ("Markdown table header count is not exactly one", len(table_header_lines))
        )
    if any(f"| {row['id']} |" not in md_text for row in rows):
        raise AssertionError("Markdown table omits a JSON row")

    dag = cut["source_dag_review"]
    if dag["semantic_closure_claimed"] is not False or any(
        r not in receipt_index for r in dag["receipt_ids"]
    ):
        raise AssertionError("source DAG scope/receipt binding mismatch")
    declared_ids = declared_receipt_ids(cut)
    if declared_ids != set(receipt_index):
        raise AssertionError(
            (
                "receipt-index does not equal the complete declared receipt set",
                sorted(declared_ids - set(receipt_index)),
                sorted(set(receipt_index) - declared_ids),
            )
        )
    if resolved != 282:
        raise AssertionError(("RFC 6901 pointer denominator mismatch", resolved))

    per_row = []
    for row in rows:
        per_row.append(
            {
                "id": row["id"],
                "verdict": row[verdict_field]["value"],
                "historical": row["historical_status"],
                "baseline_capability_label": row["capability_label"],
                "source_family": row["source_family"],
                "evidence_mode": row["code_outcome_evidence"]["mode"],
                "criterion_occurrences": len(row["criterion_refs"]),
                "deciding_receipts": len(row["deciding_receipts"]),
                "resolved_pointers": pointers_by_row[row["id"]],
            }
        )
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


def git_blob_bytes(revision: str, path: str) -> bytes:
    return subprocess.check_output(  # noqa: S603 - trusted Git object lookup; argv, no shell.
        ["git", "show", f"{revision}:{path}"],  # noqa: S607 - trusted Git executable.
        cwd=ROOT,
    )


def git_source_file(
    commit: str,
    tree: str,
    path: str,
    *,
    expected_sha256: str | None = None,
    expected_blob: str | None = None,
    expected_size: int | None = None,
) -> tuple[bytes, str]:
    """Read a source only when the path is present in the pinned Git tree."""
    relative = Path(path)
    if (
        not re.fullmatch(r"[0-9a-f]{40}", commit)
        or not re.fullmatch(r"[0-9a-f]{40}", tree)
        or relative.is_absolute()
        or ".." in relative.parts
        or "\\" in path
    ):
        raise AssertionError("Git source reference has an invalid commit, tree, or path")
    if git("rev-parse", f"{commit}^{{tree}}") != tree:
        raise AssertionError(("Git source tree mismatch", commit, path))
    spec = f"{commit}:{relative.as_posix()}"
    exists = subprocess.run(  # noqa: S603 - trusted Git object query; argv and shell disabled.
        ["git", "cat-file", "-e", spec],  # noqa: S607 - Git executable resolved by PATH.
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    if exists.returncode != 0:
        raise AssertionError(("Git source path is absent from pinned tree", spec))
    if git("cat-file", "-t", spec) != "blob":
        raise AssertionError(("Git source path is not a file blob", spec))
    raw = git_blob_bytes(commit, relative.as_posix())
    blob = git("rev-parse", spec)
    if expected_blob is not None and blob != expected_blob:
        raise AssertionError(("Git source blob mismatch", spec, blob, expected_blob))
    if expected_sha256 is not None and sha(raw) != expected_sha256:
        raise AssertionError(("Git source SHA-256 mismatch", spec, sha(raw), expected_sha256))
    if expected_size is not None and len(raw) != expected_size:
        raise AssertionError(("Git source size mismatch", spec, len(raw), expected_size))
    return raw, blob


def git_path_exists(revision: str, path: str) -> bool:
    return (
        subprocess.run(  # noqa: S603 - trusted Git path query; argv, no shell.
            ["git", "cat-file", "-e", f"{revision}:{path}"],  # noqa: S607 - Git executable.
            cwd=ROOT,
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )


def required_portable_receipt_ids(c2_cut: dict, c2_source: dict) -> set[str]:
    """Derive portable slots from the frozen receipt index and its Git tree."""
    required = set()
    for receipt_id, receipt in c2_cut["receipt_index"].items():
        if receipt.get("head"):
            continue
        path = receipt["path_at_sha256"].rsplit("@sha256:", 1)[0]
        if not git_path_exists(c2_source["commit"], path):
            required.add(receipt_id)
    return required


def derive_c3_state(finding_id: str, source_family: str, c3_input: dict, verified: dict) -> str:
    """Derive current state from scope membership and bound evidence, not labels."""
    override = c3_input.get("row_overrides", {}).get(finding_id, {})
    if source_family in verified:
        return "fresh_source_handoff_reviewed"
    if source_family in c3_input.get("family_refresh_states", {}) and source_family != "default":
        return "c3_source_refresh_pending"
    if override.get("code_outcome") and override.get("evidence_refs"):
        return "criterion_binding_corrected"
    return "c2_frozen_evidence_carried_forward"


def c3_state_note(state: str, source_family: str) -> str:
    if state == "fresh_source_handoff_reviewed":
        return f"A current source-family handoff for {source_family} is bound and verified."
    if state == "c3_source_refresh_pending":
        return (
            f"A C3 source refresh is in scope for {source_family}, but no current source-family "
            "handoff is bound."
        )
    if state == "criterion_binding_corrected":
        return (
            "The row-specific criterion and evidence binding is corrected by the listed receipts."
        )
    return (
        "No C3 source refresh or row correction is bound; "
        "the frozen C2 evidence is carried forward."
    )


def verify_current_source_family_refs(c2_cut: dict, c3_input: dict) -> dict:
    """Verify current handoff claims against candidate and handoff Git objects."""
    raw_refs = c3_input.get("current_source_family_refs", {})
    if not isinstance(raw_refs, dict):
        raise AssertionError("current source-family refs must be an object")
    prior_families = c2_cut["topic_source_refs"]
    verified = {}
    required_fields = {
        "candidate_commit",
        "candidate_tree",
        "handoff_commit",
        "handoff_tree",
        "handoff_path",
        "handoff_sha256",
        "handoff_git_blob",
        "candidate_commit_pointer",
        "candidate_tree_pointer",
        "handoff_branch",
        "handoff_branch_pointer",
        "implementation_changed_paths",
        "evidence_pointers",
    }
    for family, ref in raw_refs.items():
        if family not in prior_families or not isinstance(ref, dict):
            raise AssertionError((family, "unknown or malformed current source-family ref"))
        missing = required_fields - set(ref)
        if missing:
            raise AssertionError((family, "unbound source-family proof fields", sorted(missing)))
        candidate_commit = ref["candidate_commit"]
        candidate_tree = ref["candidate_tree"]
        handoff_commit = ref["handoff_commit"]
        handoff_tree = ref["handoff_tree"]
        if git("rev-parse", f"{candidate_commit}^{{tree}}") != candidate_tree:
            raise AssertionError((family, "candidate commit/tree mismatch"))
        if git("rev-parse", f"{handoff_commit}^{{tree}}") != handoff_tree:
            raise AssertionError((family, "handoff commit/tree mismatch"))
        if (
            subprocess.run(  # noqa: S603 - trusted Git ancestry query; argv, shell disabled.
                ["git", "merge-base", "--is-ancestor", candidate_commit, handoff_commit],  # noqa: S607 - trusted Git executable.
                cwd=ROOT,
                capture_output=True,
                check=False,
            ).returncode
            != 0
        ):
            raise AssertionError((family, "candidate is not an ancestor of the handoff"))

        candidate_ancestors = []
        for pin in prior_families[family].get("source_pins", []):
            if git("rev-parse", f"{pin['commit']}^{{tree}}") != pin["tree"]:
                raise AssertionError((family, "prior source pin tree mismatch", pin))
            if (
                subprocess.run(  # noqa: S603 - trusted Git ancestry query; argv, shell disabled.
                    ["git", "merge-base", "--is-ancestor", pin["commit"], candidate_commit],  # noqa: S607 - trusted Git executable.
                    cwd=ROOT,
                    capture_output=True,
                    check=False,
                ).returncode
                == 0
            ):
                candidate_ancestors.append(pin["commit"])
        if not candidate_ancestors:
            raise AssertionError((family, "candidate is not descended from a frozen source pin"))

        changed_paths = ref["implementation_changed_paths"]
        if (
            not isinstance(changed_paths, list)
            or not changed_paths
            or any(
                not isinstance(path, str)
                or not path
                or Path(path).is_absolute()
                or ".." in Path(path).parts
                for path in changed_paths
            )
        ):
            raise AssertionError((family, "implementation changed-path list is invalid"))
        actual_delta_paths = set()
        for prior_commit in candidate_ancestors:
            actual_delta_paths.update(
                path
                for path in git(
                    "diff", "--name-only", f"{prior_commit}..{candidate_commit}"
                ).splitlines()
                if path
            )
        if not set(changed_paths).issubset(actual_delta_paths):
            raise AssertionError((family, "implementation paths are absent from the Git delta"))

        handoff_path = Path(ref["handoff_path"])
        handoff_raw, handoff_blob = git_source_file(
            handoff_commit,
            handoff_tree,
            handoff_path.as_posix(),
            expected_sha256=ref["handoff_sha256"],
            expected_blob=ref["handoff_git_blob"],
        )
        handoff_doc = json.loads(handoff_raw)
        if (
            resolve_pointer(handoff_doc, ref["candidate_commit_pointer"]) != candidate_commit
            or resolve_pointer(handoff_doc, ref["candidate_tree_pointer"]) != candidate_tree
            or resolve_pointer(handoff_doc, ref["handoff_branch_pointer"]) != ref["handoff_branch"]
        ):
            raise AssertionError((family, "handoff does not bind candidate commit and tree"))
        evidence_pointers = ref["evidence_pointers"]
        if not isinstance(evidence_pointers, list) or not evidence_pointers:
            raise AssertionError((family, "no selected handoff evidence pointers"))
        for pointer in evidence_pointers:
            selected = resolve_pointer(handoff_doc, pointer)
            if selected is None or selected == "" or selected == [] or selected == {}:
                raise AssertionError((family, "empty selected handoff evidence", pointer))
        verified[family] = {
            "candidate_commit": candidate_commit,
            "candidate_tree": candidate_tree,
            "handoff_commit": handoff_commit,
            "handoff_tree": handoff_tree,
            "handoff_path_at_sha256": f"{handoff_path.as_posix()}@sha256:{ref['handoff_sha256']}",
            "handoff_git_blob": handoff_blob,
            "implementation_changed_paths": list(changed_paths),
            "candidate_commit_pointer": ref["candidate_commit_pointer"],
            "candidate_tree_pointer": ref["candidate_tree_pointer"],
            "branch": ref["handoff_branch"],
            "head": handoff_commit,
            "tree": handoff_tree,
            "handoff_branch_pointer": ref["handoff_branch_pointer"],
            "evidence_pointers": list(evidence_pointers),
        }
    return verified


def nested_git_file_refs(value: object) -> list[dict]:
    """Find relative path/SHA objects inside selected evidence values."""
    found = []
    if isinstance(value, dict):
        if isinstance(value.get("path"), str) and isinstance(value.get("sha256"), str):
            found.append(value)
        else:
            for child in value.values():
                found.extend(nested_git_file_refs(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(nested_git_file_refs(child))
    return found


def verify_supplemental_source_handoffs(
    c2_cut: dict, c3_input: dict
) -> tuple[list[dict], dict[str, list[str]]]:
    """Resolve supplemental handoffs, candidates, and files from committed Git trees."""
    raw_refs = c3_input.get("supplemental_source_handoffs", [])
    if not isinstance(raw_refs, list):
        raise AssertionError("supplemental source handoffs must be an array")
    c2_rows = {row["id"]: row for row in c2_cut["rows"]}
    verified = []
    refs_by_finding: dict[str, list[str]] = {}
    seen_refs: set[str] = set()
    for ref in raw_refs:
        if not isinstance(ref, dict):
            raise AssertionError("supplemental source handoff entry must be an object")
        ref_id = ref.get("ref_id")
        family = ref.get("family")
        if not isinstance(ref_id, str) or not ref_id or ref_id in seen_refs:
            raise AssertionError("supplemental source handoff ref_id is missing or duplicated")
        seen_refs.add(ref_id)
        if family not in c2_cut["topic_source_refs"]:
            raise AssertionError((ref_id, "unknown source family"))
        handoff_raw, handoff_blob = git_source_file(
            ref["source_commit"],
            ref["source_tree"],
            ref["path"],
            expected_sha256=ref["sha256"],
            expected_blob=ref["git_blob"],
            expected_size=ref.get("size_bytes"),
        )
        handoff_doc = json.loads(handoff_raw)
        finding_ids = ref.get("finding_ids")
        if (
            not isinstance(finding_ids, list)
            or not finding_ids
            or len(set(finding_ids)) != len(finding_ids)
        ):
            raise AssertionError((ref_id, "finding scope is empty or duplicated"))
        criterion_ids: set[str] = set()
        for finding_id in finding_ids:
            row = c2_rows.get(finding_id)
            if row is None or row["source_family"] != family:
                raise AssertionError(
                    (ref_id, finding_id, "finding absent or outside source family")
                )
            criterion_ids.update(item["criterion_id"] for item in row["criterion_refs"])
            refs_by_finding.setdefault(finding_id, []).append(ref_id)
        declared_criteria = resolve_pointer(handoff_doc, ref["criterion_ids_pointer"])
        if (
            not isinstance(declared_criteria, list)
            or len(declared_criteria) != len(set(declared_criteria))
            or set(declared_criteria) != criterion_ids
        ):
            raise AssertionError((ref_id, "handoff criterion IDs differ from row scope"))
        evidence_pointers = ref.get("evidence_pointers")
        if not isinstance(evidence_pointers, list) or not evidence_pointers:
            raise AssertionError((ref_id, "selected evidence pointers are empty"))
        selected_evidence_files = []
        for pointer in evidence_pointers:
            selected = resolve_pointer(handoff_doc, pointer)
            if selected is None or selected == "" or selected == [] or selected == {}:
                raise AssertionError((ref_id, pointer, "selected evidence pointer is empty"))
            for file_ref in nested_git_file_refs(selected):
                path = file_ref["path"]
                if Path(path).is_absolute():
                    raise AssertionError(
                        (ref_id, path, "selected supplemental evidence is not repository-portable")
                    )
                file_raw, file_blob = git_source_file(
                    ref["source_commit"],
                    ref["source_tree"],
                    path,
                    expected_sha256=file_ref["sha256"],
                    expected_blob=file_ref.get("git_blob"),
                    expected_size=file_ref.get("bytes", file_ref.get("size_bytes")),
                )
                selected_evidence_files.append(
                    {
                        "path": path,
                        "sha256": sha(file_raw),
                        "git_blob": file_blob,
                        "size_bytes": len(file_raw),
                    }
                )
        candidate_records = []
        candidates = ref.get("candidate_bindings")
        if not isinstance(candidates, list) or not candidates:
            raise AssertionError((ref_id, "candidate bindings are empty"))
        for candidate in candidates:
            commit = resolve_pointer(handoff_doc, candidate["commit_pointer"])
            tree = resolve_pointer(handoff_doc, candidate["tree_pointer"])
            if not re.fullmatch(r"[0-9a-f]{40}", commit) or not re.fullmatch(r"[0-9a-f]{40}", tree):
                raise AssertionError((ref_id, "candidate identity is malformed"))
            if git("rev-parse", f"{commit}^{{tree}}") != tree:
                raise AssertionError((ref_id, "candidate commit/tree mismatch"))
            if (
                subprocess.run(  # noqa: S603 - trusted Git ancestry query; argv and shell disabled.
                    ["git", "merge-base", "--is-ancestor", commit, ref["source_commit"]],  # noqa: S607 - Git executable.
                    cwd=ROOT,
                    capture_output=True,
                    check=False,
                ).returncode
                != 0
            ):
                raise AssertionError((ref_id, "candidate is not in handoff ancestry"))
            parents = git("show", "-s", "--format=%P", commit).split()
            parents_pointer = candidate.get("parents_pointer")
            if parents_pointer and resolve_pointer(handoff_doc, parents_pointer) != parents:
                raise AssertionError((ref_id, "candidate parent list mismatch"))
            source_files = []
            for pointer in candidate.get("source_file_pointers", []):
                file_ref = resolve_pointer(handoff_doc, pointer)
                if not isinstance(file_ref, dict) or file_ref.get("commit") != commit:
                    raise AssertionError((ref_id, pointer, "source-file commit binding mismatch"))
                file_raw, file_blob = git_source_file(
                    commit,
                    tree,
                    file_ref["path"],
                    expected_sha256=file_ref["sha256"],
                    expected_blob=file_ref["git_blob"],
                    expected_size=file_ref.get("bytes"),
                )
                source_files.append(
                    {
                        "path": file_ref["path"],
                        "source_file_pointer": pointer,
                        "sha256": sha(file_raw),
                        "git_blob": file_blob,
                        "size_bytes": len(file_raw),
                    }
                )
            candidate_records.append(
                {
                    "role": candidate["role"],
                    "commit": commit,
                    "tree": tree,
                    "commit_pointer": candidate["commit_pointer"],
                    "tree_pointer": candidate["tree_pointer"],
                    "parents": parents,
                    "parents_pointer": parents_pointer,
                    "source_files": source_files,
                }
            )
        verified.append(
            {
                "ref_id": ref_id,
                "family": family,
                "source_commit": ref["source_commit"],
                "source_tree": ref["source_tree"],
                "path_at_sha256": f"{ref['path']}@sha256:{ref['sha256']}",
                "git_blob": handoff_blob,
                "size_bytes": len(handoff_raw),
                "finding_ids": finding_ids,
                "criterion_ids": sorted(criterion_ids),
                "criterion_ids_pointer": ref["criterion_ids_pointer"],
                "evidence_pointers": evidence_pointers,
                "selected_evidence_files": selected_evidence_files,
                "candidate_bindings": candidate_records,
            }
        )
    return verified, refs_by_finding


def parse_tsv_bytes(raw: bytes) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(raw.decode("utf-8")), delimiter="\t"))


def verify_portable_receipt_bindings(c2_cut: dict, c2_source: dict, c3_input: dict) -> list[dict]:
    c2_index = c2_cut["receipt_index"]
    result = []
    seen_ids = set()
    PORTABLE_RECEIPT_OVERRIDES.clear()
    for binding in c3_input.get("portable_receipt_bindings", []):
        receipt_id = binding["receipt_id"]
        source_receipt = c2_index.get(receipt_id)
        if source_receipt is None or receipt_id in seen_ids:
            raise AssertionError((receipt_id, "portable receipt is missing or duplicated"))
        seen_ids.add(receipt_id)
        historical_locator = source_receipt["path_at_sha256"]
        if (
            historical_locator != binding["historical_path_at_sha256"]
            or source_receipt.get("sha256") != binding["sha256"]
            or source_receipt.get("size_bytes") != binding["size_bytes"]
            or source_receipt.get("head")
        ):
            raise AssertionError(
                (receipt_id, "portable binding differs from local-only C2 receipt")
            )
        relative_path = Path(binding["portable_path"])
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise AssertionError((receipt_id, "portable path escapes the repository"))
        if binding.get("source_path") != relative_path.as_posix():
            raise AssertionError((receipt_id, "portable source path differs from indexed path"))
        raw, blob = git_source_file(
            binding["source_commit"],
            binding["source_tree"],
            binding["source_path"],
            expected_sha256=binding["sha256"],
            expected_blob=binding["source_git_blob"],
            expected_size=binding["size_bytes"],
        )
        digest = sha(raw)
        expected = {
            "receipt_id": receipt_id,
            "historical_path_at_sha256": historical_locator,
            "historical_source_status": "verification_missing",
            "path_at_sha256": f"{relative_path.as_posix()}@sha256:{digest}",
            "git_blob": blob,
            "source_commit": binding["source_commit"],
            "source_tree": binding["source_tree"],
            "size_bytes": len(raw),
            "current_content_status": "verified_from_pinned_git_tree",
            "role": binding["role"],
        }
        result.append(expected)
        PORTABLE_RECEIPT_OVERRIDES[historical_locator] = raw
    missing = required_portable_receipt_ids(c2_cut, c2_source) - seen_ids
    if missing:
        raise AssertionError(
            "portable bindings omit historical local-only receipt(s): " + ", ".join(sorted(missing))
        )
    return result


def derive_historical_local_only_receipts(
    c2_cut: dict, c2_source: dict, portable: list[dict]
) -> list[dict]:
    portable_by_id = {receipt["receipt_id"]: receipt for receipt in portable}
    result = []
    for receipt_id, receipt in c2_cut["receipt_index"].items():
        if receipt.get("head"):
            continue
        path = receipt["path_at_sha256"].rsplit("@sha256:", 1)[0]
        if git_path_exists(c2_source["commit"], path):
            continue
        replacement = portable_by_id.get(receipt_id)
        result.append(
            {
                "receipt_id": receipt_id,
                "path_at_sha256": receipt["path_at_sha256"],
                "sha256": receipt["sha256"],
                "size_bytes": receipt["size_bytes"],
                "historical_source_status": "verification_missing",
                "current_portable_replacement_path_at_sha256": (
                    replacement["path_at_sha256"] if replacement else None
                ),
            }
        )
    return result


def json_pointer_reference_count(value: object) -> int:
    if isinstance(value, dict):
        count = 0
        for key, child in value.items():
            if (key.endswith("_source_pointer") and isinstance(child, str)) or (
                key == "source_pointer" and isinstance(child, str)
            ):
                count += 1
            elif key == "json_pointers" and isinstance(child, list):
                count += len(child)
            else:
                count += json_pointer_reference_count(child)
        return count
    if isinstance(value, list):
        return sum(json_pointer_reference_count(child) for child in value)
    return 0


def run_c3(
    cut_path: Path,
    markdown_path: Path,
    input_path: Path,
    expected_cut_sha: str | None,
    expected_markdown_sha: str | None,
    final_mode: bool = False,
) -> dict:
    global \
        ROOT, \
        BASE, \
        SNAPSHOT, \
        INVENTORY_PATH, \
        EXPECTED_CUT_SHA, \
        EXPECTED_MD_SHA, \
        EXPECTED_INVENTORY_SHA, \
        MARKDOWN_PATH
    cut_raw = cut_path.read_bytes()
    if expected_cut_sha and sha(cut_raw) != expected_cut_sha:
        raise AssertionError(("unexpected C3 input cut hash", sha(cut_raw), expected_cut_sha))
    cut = json.loads(cut_raw)
    expected_cut_schema = C3_FINAL_CUT_SCHEMA if final_mode else C3_CUT_SCHEMA
    expected_cut_status = (
        "c3_current_root_adjudicated"
        if final_mode
        else "c3_current_evidence_crosswalk_not_adjudication"
    )
    if cut.get("schema") != expected_cut_schema or cut.get("status") != expected_cut_status:
        raise AssertionError(
            ("C3 artifact schema/status mismatch", cut.get("schema"), cut.get("status"))
        )
    if cut.get("final_verdicts_assigned") is not final_mode:
        raise AssertionError("C3 final-verdict assignment flag differs from validation mode")

    input_raw = input_path.read_bytes()
    input_sha = sha(input_raw)
    expected_input_schema = C3_FINAL_INPUT_SCHEMA if final_mode else C3_INPUT_SCHEMA
    if cut.get("c3_input") != {
        "path": str(input_path.relative_to(ROOT)),
        "sha256": input_sha,
        "bytes": len(input_raw),
        "schema": expected_input_schema,
    }:
        raise AssertionError(("C3 typed input locator/hash/schema mismatch", cut.get("c3_input")))
    c3_input = json.loads(input_raw)
    if c3_input.get("schema") != expected_input_schema:
        raise AssertionError("C3 typed input schema mismatch")

    c2_source = c3_input["c2_source"]
    if (
        c2_source.get("commit") != C3_EXPECTED_C2_COMMIT
        or c2_source.get("tree") != C3_EXPECTED_C2_TREE
        or c2_source.get("git_blob") != C3_EXPECTED_C2_BLOB
        or c2_source.get("sha256") != C3_EXPECTED_C2_SHA
        or c2_source.get("path") != C3_V10_PATH
    ):
        raise AssertionError("C3 typed input is not bound to the exact frozen C2 report")
    g_snapshot = c3_input.get("g_snapshot")
    expected_g_snapshot = (
        (C3_FINAL_EXPECTED_G_COMMIT, C3_FINAL_EXPECTED_G_TREE)
        if final_mode
        else (C3_EXPECTED_G_COMMIT, C3_EXPECTED_G_TREE)
    )
    if g_snapshot and (
        g_snapshot.get("commit") != expected_g_snapshot[0]
        or g_snapshot.get("tree") != expected_g_snapshot[1]
    ):
        raise AssertionError("C3 typed input is not bound to the pinned G review snapshot")
    c2_raw = git_blob_bytes(c2_source["commit"], c2_source["path"])
    if (
        sha(c2_raw) != c2_source["sha256"]
        or len(c2_raw) != c2_source["bytes"]
        or git("rev-parse", f"{c2_source['commit']}:{c2_source['path']}") != c2_source["git_blob"]
    ):
        raise AssertionError("C2 source cut byte/blob binding mismatch")
    c2_cut = json.loads(c2_raw)
    verified_current_families = verify_current_source_family_refs(c2_cut, c3_input)
    verified_supplemental_handoffs, supplemental_by_finding = verify_supplemental_source_handoffs(
        c2_cut, c3_input
    )
    if final_mode:
        required_refresh_families = set(c3_input["family_refresh_states"]) - {"default"}
        missing_refresh_families = required_refresh_families - set(verified_current_families)
        if missing_refresh_families:
            raise AssertionError(
                "final C3 input lacks verified source handoffs for refresh families: "
                + ", ".join(sorted(missing_refresh_families))
            )
    portable_index = verify_portable_receipt_bindings(c2_cut, c2_source, c3_input)
    historical_local_only = derive_historical_local_only_receipts(c2_cut, c2_source, portable_index)
    if cut.get("c2_source") != c2_source | {"bytes": len(c2_raw)}:
        raise AssertionError("C3 C2 source binding differs from typed input")
    if cut.get("c2_adjudication_snapshot", {}).get("snapshot") != c2_cut["snapshot"]:
        raise AssertionError("C3 frozen C2 snapshot differs from C2 source")
    if cut.get("baseline_use_limit") != c2_cut["baseline_use_limit"]:
        raise AssertionError("C3 baseline-use boundary differs from C2 source")

    # Re-run the already complete C2 source-span, history, receipt, and 282-pointer validator
    # against the exact tracked C2 source that this C3 view cites.
    ROOT = ROOT.resolve()
    BASE = c2_cut["base"]["commit"]
    SNAPSHOT = c2_cut["snapshot"]["commit"]
    EXPECTED_CUT_SHA = c2_source["sha256"]
    MARKDOWN_PATH = ROOT / C3_V10_MARKDOWN_PATH
    c2_markdown_raw = git_blob_bytes(c2_source["commit"], C3_V10_MARKDOWN_PATH)
    EXPECTED_MD_SHA = sha(c2_markdown_raw)
    inventory_locator = c2_cut["input_receipts"]["inventory_tsv_path_at_sha256"]
    inventory_path, EXPECTED_INVENTORY_SHA = inventory_locator.rsplit("@sha256:", 1)
    INVENTORY_PATH = str(ROOT / inventory_path)
    c2_validation = run(ROOT / C3_V10_PATH, EXPECTED_CUT_SHA)
    if cut.get("portable_receipt_index") != portable_index:
        raise AssertionError("portable C3 receipt index differs from its typed inputs")
    if cut.get("historical_local_only_receipts") != historical_local_only:
        raise AssertionError("historical local-only receipt status differs from C2 source")

    source_families = {
        family: {
            key: source_ref[key]
            for key in (
                "source_pins",
                "declared_candidate_tree",
                "handoff_receipt_id",
                "handoff_branch",
                "handoff_head",
                "handoff_tree",
            )
            if key in source_ref
        }
        for family, source_ref in c2_cut["topic_source_refs"].items()
    }
    if cut.get("topic_source_refs") != source_families:
        raise AssertionError("C3 family refs differ from the compact exact C2 source pins")
    if cut.get("current_source_family_refs") != verified_current_families:
        raise AssertionError("C3 current source-family refs are not the verified handoff set")
    if cut.get("supplemental_source_handoffs", []) != verified_supplemental_handoffs:
        raise AssertionError("C3 supplemental handoffs differ from the verified Git source set")
    for family, source_ref in source_families.items():
        for pin in source_ref["source_pins"]:
            if git("rev-parse", f"{pin['commit']}^{{tree}}") != pin["tree"]:
                raise AssertionError((family, "source pin tree mismatch", pin))
        handoff = c2_cut["receipt_index"].get(source_ref["handoff_receipt_id"])
        if not isinstance(handoff, dict):
            raise AssertionError(
                (family, "handoff receipt is missing", source_ref["handoff_receipt_id"])
            )
        handoff_identity = {
            "branch": source_ref.get("handoff_branch"),
            "head": source_ref.get("handoff_head"),
            "tree": source_ref.get("handoff_tree"),
        }
        if any(handoff.get(key) != value for key, value in handoff_identity.items()):
            raise AssertionError((family, "topic handoff identity differs from receipt index"))

    base = c3_input["base"]
    g_snapshot = c3_input["g_snapshot"]
    if cut.get("base") != base or c2_cut["base"] != base:
        raise AssertionError("base commit/tree differs between C3 input and frozen C2 source")
    if cut.get("g_snapshot") != g_snapshot:
        raise AssertionError("G source snapshot differs from the typed C3 input")
    for revision, expected_tree, label in (
        (base["commit"], base["tree"], "base"),
        (c2_source["commit"], c2_source["tree"], "C2 source"),
        (g_snapshot["commit"], g_snapshot["tree"], "G source"),
    ):
        actual_tree = git("rev-parse", f"{revision}^{{tree}}")
        if actual_tree != expected_tree:
            raise AssertionError((f"{label} Git tree mismatch", actual_tree, expected_tree))
    if subprocess.run(  # noqa: S603 - trusted Git ancestry query; argv and shell disabled.
        ["git", "merge-base", "--is-ancestor", base["commit"], c2_source["commit"]],  # noqa: S607 - Git executable.
        cwd=ROOT,
    ).returncode:
        raise AssertionError("base is not an ancestor of the frozen C2 source")

    g_input_refs = {}
    g_raw_by_name = {}
    for name, ref in c3_input["g_inputs"].items():
        raw = git_blob_bytes(g_snapshot["commit"], ref["path"])
        blob = git("rev-parse", f"{g_snapshot['commit']}:{ref['path']}")
        if len(raw) != ref["bytes"] or sha(raw) != ref["sha256"] or blob != ref["git_blob"]:
            raise AssertionError(("G input byte/blob binding mismatch", name, ref["path"]))
        g_input_refs[name] = {**ref, "source_commit": g_snapshot["commit"]}
        g_raw_by_name[name] = raw
    if cut.get("g_input_refs") != g_input_refs:
        raise AssertionError("C3 rendered G input refs differ from typed input bindings")

    coverage = json.loads(git_blob_bytes(g_snapshot["commit"], C3_COVERAGE_PATH))
    allocation = json.loads(
        git_blob_bytes(
            g_snapshot["commit"],
            "policy-engine/docs/research/e02-cloud-test-plan/execution-organization/allocation.json",
        )
    )
    g_findings = {row["id"]: row for row in coverage["findings"] if row["unit"] == "C"}
    c2_rows = {row["id"]: row for row in c2_cut["rows"]}
    c3_rows = {row["id"]: row for row in cut["rows"]}
    if (
        len(c3_rows) != 54
        or len(cut["rows"]) != 54
        or set(c3_rows) != set(g_findings)
        or set(c3_rows) != set(c2_rows)
    ):
        raise AssertionError("C3 finding denominator/identity mismatch")
    if allocation.get("schema") is None:
        raise AssertionError("pinned G allocation document has no schema")
    finding_owners = {
        row["finding_id"]: row for row in parse_tsv_bytes(g_raw_by_name["finding_owners"])
    }
    bundle_owners = {
        row["bundle_id"]: row for row in parse_tsv_bytes(g_raw_by_name["bundle_owners"])
    }
    if set(finding_owners) != {row["id"] for row in coverage["findings"]}:
        raise AssertionError("full G finding-owner TSV denominator mismatch")

    c_bundle_rows = {row["id"]: row for row in coverage["bundles"] if row["unit"] == "C"}
    derived_coverage = {
        "all_bundles": len(coverage["bundles"]),
        "all_findings": len(coverage["findings"]),
        "canonical_criterion_occurrences": coverage["denominator"][
            "canonical_source_block_occurrences"
        ],
        "C_bundles": len(c_bundle_rows),
        "C_findings": len(g_findings),
        "C_hash_bound_criteria": sum(
            len(row.get("criterion_refs", [])) for row in g_findings.values()
        ),
    }
    expected_coverage = {
        "all_bundles": 127,
        "all_findings": 282,
        "canonical_criterion_occurrences": 291,
        "C_bundles": 33,
        "C_findings": 54,
        "C_hash_bound_criteria": 59,
    }
    if derived_coverage != expected_coverage or cut.get("coverage_denominator") != derived_coverage:
        raise AssertionError(("G/C denominator mismatch", derived_coverage))

    c2_doc_index = c2_cut["criterion_document_index"]
    g_doc_aliases = {"B_r19": "CD01", "LA_r09": "CD02"}
    for alias, document in coverage["criterion_documents"].items():
        document_ref = g_doc_aliases[alias]
        c2_document = c2_doc_index[document_ref]
        if document["path"] != c2_document["path"]:
            raise AssertionError(("G/C criterion source path differs", alias))
        blob = git("rev-parse", f"{base['commit']}:{document['path']}")
        if blob != document["blob"] or blob != c2_document["git_blob"]:
            raise AssertionError(("original criterion source Git blob mismatch", alias, blob))
    criterion_occurrences = 0
    resolved_c3 = 0
    c2_receipt_index = c2_cut["receipt_index"]
    override_map = c3_input["row_overrides"]
    family_states = c3_input["family_refresh_states"]
    root_adjudications = c3_input.get("root_current_adjudications", {})
    if final_mode and (
        not isinstance(root_adjudications, dict) or set(root_adjudications) != set(c3_rows)
    ):
        raise AssertionError("final C3 input does not adjudicate the complete finding set")
    c2_row_index = {row["id"]: index for index, row in enumerate(c2_cut["rows"])}
    for finding_id, row in c3_rows.items():
        c2 = c2_rows[finding_id]
        g = g_findings[finding_id]
        owner = finding_owners[finding_id]
        index = c2_row_index[finding_id]
        if row["historical_status"] != c2["historical_status"]:
            raise AssertionError((finding_id, "historical status is not preserved from C2"))
        if row["bundles"] != c2["bundles"] or set(row["bundles"]) != set(g["companion_bundles"]):
            raise AssertionError((finding_id, "bundle mapping differs between C2 and G coverage"))
        if (
            row["source_family"] != c2["source_family"]
            or row["current_evaluation"]["source_family_ref_key"] != c2["source_family"]
        ):
            raise AssertionError((finding_id, "source-family linkage mismatch"))
        if row["current_evaluation"].get("supplemental_evidence_refs", []) != (
            supplemental_by_finding.get(finding_id, [])
        ):
            raise AssertionError(
                (finding_id, "supplemental evidence refs differ from source bindings")
            )
        if row["c2_snapshot"] != {
            "source_row_index": index,
            "capability_label": c2["capability_label"],
            "code_outcome_source_pointer": f"/rows/{index}/code_outcome",
            "deciding_receipts_source_pointer": f"/rows/{index}/deciding_receipts",
            "root_verdict": {
                "value": c2["root_finding_verdict"]["value"],
                "status": c2["root_finding_verdict"]["status"],
            },
            "root_verdict_source_pointer": f"/rows/{index}/root_finding_verdict",
        }:
            raise AssertionError((finding_id, "frozen C2 row summary/pointers mismatch"))
        for pointer_key in (
            "code_outcome_source_pointer",
            "deciding_receipts_source_pointer",
            "root_verdict_source_pointer",
        ):
            resolve_pointer(c2_cut, row["c2_snapshot"][pointer_key])
            resolved_c3 += 1
        if row["g_current"] != {
            "unit": g["unit"],
            "formal_status": g["closure_now"],
            "capability_label": g.get("capability_label") or "",
            "canonical_source_owner": owner["source_closure_owner"],
            "source_owner_bundle_ids": [
                part.strip() for part in owner["source_bundle_ids"].split(";")
            ],
            "primary_bundle": g["primary_bundle"],
            "companion_bundles": list(g["companion_bundles"]),
        }:
            raise AssertionError(
                (finding_id, "G formal state/canonical owner/capability/bundle mismatch")
            )
        if row["g_current"]["formal_status"] != "not_adjudicated":
            raise AssertionError(
                (finding_id, "G status must remain a separate not_adjudicated state")
            )

        expected_criteria = []
        for item in g.get("criterion_refs", []):
            alias = item["document"]
            doc_ref = g_doc_aliases[alias]
            line_span = f"{item['lines'][0]}-{item['lines'][1]}"
            expected_criteria.append((item["criterion_id"], doc_ref, line_span, item["sha256"]))
        actual_criteria = [
            (
                item["criterion_id"],
                item["document_ref"],
                item["line_span"],
                item["criterion_sha256"],
            )
            for item in row["criterion_refs"]
        ]
        if Counter(actual_criteria) != Counter(expected_criteria) or Counter(
            actual_criteria
        ) != Counter(
            (
                item["criterion_id"],
                item["document_ref"],
                item["line_span"],
                item["criterion_sha256"],
            )
            for item in c2["criterion_refs"]
        ):
            raise AssertionError(
                (finding_id, "59 exact criterion tuples differ from G coverage or C2 source")
            )
        for criterion in row["criterion_refs"]:
            document = c2_doc_index[criterion["document_ref"]]
            source_lines = git_blob_bytes(base["commit"], document["path"]).splitlines(
                keepends=True
            )
            start_s, end_s = criterion["line_span"].split("-")
            start, end = int(start_s), int(end_s)
            if not 1 <= start <= end <= len(source_lines):
                raise AssertionError(
                    (finding_id, "criterion span outside the exact source document")
                )
            if sha(b"".join(source_lines[start - 1 : end])) != criterion["criterion_sha256"]:
                raise AssertionError((finding_id, "criterion inclusive source-span SHA mismatch"))
            criterion_occurrences += 1

        current = row["current_evaluation"]
        override = override_map.get(finding_id, {})
        final_decision = root_adjudications.get(finding_id, {}) if final_mode else {}
        source_state_key = (
            row["source_family"] if row["source_family"] in family_states else "default"
        )
        expected_state = derive_c3_state(
            finding_id, row["source_family"], c3_input, verified_current_families
        )
        if current["state"] != expected_state:
            raise AssertionError(
                (finding_id, "C3 current-evaluation state is not evidence-derived")
            )
        if current.get("state_note") != c3_state_note(expected_state, row["source_family"]):
            raise AssertionError((finding_id, "C3 state explanation is not evidence-derived"))
        expected_state_pointer = (
            f"/current_source_family_refs/{row['source_family']}"
            if row["source_family"] in verified_current_families
            else (
                f"/row_overrides/{finding_id}"
                if expected_state == "criterion_binding_corrected"
                else f"/family_refresh_states/{source_state_key}"
            )
        )
        if current["state_note_source_pointer"] != expected_state_pointer:
            raise AssertionError((finding_id, "current-evaluation state note pointer mismatch"))
        state_note = resolve_pointer(c3_input, current["state_note_source_pointer"])
        if not isinstance(state_note, dict):
            raise AssertionError((finding_id, "state note pointer does not reach an input object"))
        resolved_c3 += 1

        if override:
            if (
                current["code_outcome"] != override["code_outcome"]
                or current["code_outcome_source_pointer"] is not None
            ):
                raise AssertionError(
                    (finding_id, "corrected C3 code outcome is not bound to typed input")
                )
            if (
                current["evidence_refs"] != override["evidence_refs"]
                or current["evidence_ref_source_pointer"] is not None
            ):
                raise AssertionError(
                    (finding_id, "corrected C3 evidence refs differ from typed input")
                )
            if current["tree_path_checks"] != override.get("git_tree_path_checks", []):
                raise AssertionError((finding_id, "tree-path evidence differs from typed input"))
            expected_remaining = override.get("remaining_work")
            if expected_remaining is None:
                expected_remaining = {
                    "mechanism": {
                        "status": "not_reassessed_in_C3",
                        "note_ref": "status_semantics/c3_current_evaluation",
                    },
                    "verification": {
                        "status": "source_refresh_pending"
                        if expected_state == "c3_source_refresh_pending"
                        else "carried_from_C2_handoff",
                        "source_pointer": f"/rows/{index}/remaining_verification",
                    },
                    "input": {
                        "status": "carried_from_C2_handoff",
                        "source_pointer": f"/rows/{index}/missing_inputs_or_skipped_backend",
                    },
                    "decision": {
                        "status": "carried_from_C2_handoff",
                        "source_pointer": f"/rows/{index}/next_owner",
                    },
                }
        else:
            expected_code_outcome = c2["code_outcome"] if final_mode else None
            if (
                current["code_outcome"] != expected_code_outcome
                or current["code_outcome_source_pointer"] != f"/rows/{index}/code_outcome"
            ):
                raise AssertionError(
                    (finding_id, "carried code outcome must resolve through the pinned C2 source")
                )
            if (
                current["evidence_refs"]
                or current["evidence_ref_source_pointer"] != f"/rows/{index}/deciding_receipts"
            ):
                raise AssertionError(
                    (finding_id, "carried evidence refs must resolve through the pinned C2 source")
                )
            if current["tree_path_checks"]:
                raise AssertionError((finding_id, "unexpected C3 tree-path claim"))
            expected_remaining = {
                "mechanism": {
                    "status": "not_reassessed_in_C3",
                    "note_ref": "status_semantics/c3_current_evaluation",
                },
                "verification": {
                    "status": "source_refresh_pending"
                    if expected_state == "c3_source_refresh_pending"
                    else "carried_from_C2_handoff",
                    "source_pointer": f"/rows/{index}/remaining_verification",
                },
                "input": {
                    "status": "carried_from_C2_handoff",
                    "source_pointer": f"/rows/{index}/missing_inputs_or_skipped_backend",
                },
                "decision": {
                    "status": "carried_from_C2_handoff",
                    "source_pointer": f"/rows/{index}/next_owner",
                },
            }
        if current["remaining_work"] != expected_remaining:
            raise AssertionError(
                (finding_id, "remaining mechanism/verification/input/decision fields differ")
            )
        if final_mode:
            expected_code_outcome = override.get("code_outcome", c2["code_outcome"])
            expected_capability = override.get("capability_label", c2["capability_label"])
            expected_missing = override.get(
                "missing_inputs_or_skipped_backend", c2["missing_inputs_or_skipped_backend"]
            )
            expected_remaining_text = override.get(
                "remaining_verification", c2["remaining_verification"]
            )
            expected_next_owner = override.get("next_owner", c2["next_owner"])
            if current.get("code_outcome") != expected_code_outcome:
                raise AssertionError((finding_id, "final current code outcome differs from source"))
            if current.get("current_capability_label") != expected_capability:
                raise AssertionError((finding_id, "final capability label differs from source"))
            if current.get("missing_inputs_or_skipped_backend") != expected_missing:
                raise AssertionError(
                    (finding_id, "final missing-input statement differs from source")
                )
            if current.get("remaining_verification") != expected_remaining_text:
                raise AssertionError((finding_id, "final remaining-verification text differs"))
            if current.get("next_owner") != expected_next_owner:
                raise AssertionError((finding_id, "final next-owner statement differs from source"))
            expected_basis = {
                "fresh_source_handoff_reviewed": "fresh_source_handoff_reviewed",
                "criterion_binding_corrected": "criterion_evidence_binding_corrected",
                "c2_frozen_evidence_carried_forward": (
                    "unchanged_source_prior_criterion_evidence_reviewed"
                ),
            }.get(expected_state)
            if expected_basis is None or current.get("evidence_basis") != expected_basis:
                raise AssertionError((finding_id, "final evidence basis is not evidence-derived"))
            verdict = final_decision.get("value")
            if verdict not in {"closed", "limited", "held", "open"}:
                raise AssertionError((finding_id, "invalid final root verdict", verdict))
            if "reason" in final_decision:
                expected_reason = final_decision["reason"]
                expected_reason_pointer = None
            else:
                expected_reason_pointer = final_decision.get("reason_source_pointer")
                expected_reason = resolve_pointer(c2_cut, expected_reason_pointer)
            expected_verdict_object = {
                "value": verdict,
                "status": "final_root_adjudication",
                "basis": expected_basis,
                "reason": expected_reason,
                "reason_source_pointer": expected_reason_pointer,
            }
            if row.get("current_root_verdict") != expected_verdict_object:
                raise AssertionError((finding_id, "current root verdict differs from typed input"))
            if not isinstance(expected_reason, str) or not expected_reason.strip():
                raise AssertionError((finding_id, "final root reason is empty"))
        for pointer in (
            current["code_outcome_source_pointer"],
            current["evidence_ref_source_pointer"],
        ):
            if pointer:
                resolve_pointer(c2_cut, pointer)
                resolved_c3 += 1
        for item in current["remaining_work"].values():
            if "source_pointer" in item:
                resolve_pointer(c2_cut, item["source_pointer"])
                resolved_c3 += 1
            if "note_ref" in item:
                resolve_pointer(c3_input, "/" + item["note_ref"])
                resolved_c3 += 1

        for evidence_ref in current["evidence_refs"]:
            receipt_id = evidence_ref["receipt_id"]
            if receipt_id not in c2_receipt_index:
                raise AssertionError(
                    (finding_id, "unknown C2 receipt in corrected evidence refs", receipt_id)
                )
            receipt = c2_receipt_index[receipt_id]
            raw = receipt_bytes(receipt)
            if receipt.get("format") != "json":
                raise AssertionError(
                    (finding_id, "corrected C3 pointer does not target JSON", receipt_id)
                )
            document = json.loads(raw)
            for pointer in evidence_ref["json_pointers"]:
                resolve_pointer(document, pointer)
                resolved_c3 += 1

        for check in current["tree_path_checks"]:
            tree = git("rev-parse", f"{check['commit']}^{{tree}}")
            if tree != check["tree"]:
                raise AssertionError((finding_id, "tree path check commit/tree mismatch"))
            entries = subprocess.check_output(  # noqa: S603 - trusted Git tree query; argv, no shell.
                ["git", "ls-tree", "-r", "--name-only", check["commit"], "--", check["path"]],  # noqa: S607 - Git executable.
                cwd=ROOT,
                text=True,
            ).splitlines()
            if len(entries) != check["tracked_entry_count"]:
                raise AssertionError(
                    (finding_id, "tracked path entry count mismatch", check["path"], entries)
                )

    if criterion_occurrences != 59:
        raise AssertionError(("criterion occurrence denominator mismatch", criterion_occurrences))
    if {bundle for row in cut["rows"] for bundle in row["bundles"]} != set(c_bundle_rows):
        raise AssertionError("C bundle union is not the complete 33-bundle set")
    expected_bundle_crosswalk = []
    for bundle_id in sorted(c_bundle_rows):
        g_bundle = c_bundle_rows[bundle_id]
        owner_item = bundle_owners.get(bundle_id)
        if owner_item is None:
            raise AssertionError(("missing G bundle-owner row", bundle_id))
        members = [row for row in cut["rows"] if bundle_id in row["bundles"]]
        expected_bundle_crosswalk.append(
            {
                "bundle_id": bundle_id,
                "g_unit": g_bundle["unit"],
                "initial_writer_family": owner_item["initial_writer_family"],
                "c_finding_ids": [row["id"] for row in members],
                "c_source_families": sorted({row["source_family"] for row in members}),
                "g_source_closure_owners": sorted(
                    {row["g_current"]["canonical_source_owner"] for row in members}
                ),
            }
        )
    if (
        cut.get("bundle_crosswalk") != expected_bundle_crosswalk
        or len(expected_bundle_crosswalk) != 33
    ):
        raise AssertionError("full 33-bundle crosswalk mismatch")

    c2_verdict_counts = dict(
        sorted(Counter(row["c2_snapshot"]["root_verdict"]["value"] for row in cut["rows"]).items())
    )
    g_status_counts = dict(
        sorted(Counter(row["g_current"]["formal_status"] for row in cut["rows"]).items())
    )
    state_counts = dict(
        sorted(Counter(row["current_evaluation"]["state"] for row in cut["rows"]).items())
    )
    current_root_counts = (
        dict(sorted(Counter(row["current_root_verdict"]["value"] for row in cut["rows"]).items()))
        if final_mode
        else {}
    )
    if c2_verdict_counts != {"closed": 31, "held": 14, "limited": 9}:
        raise AssertionError(("C2 context counts differ from 54 row records", c2_verdict_counts))
    if g_status_counts != {"not_adjudicated": 54}:
        raise AssertionError(("G formal status counts differ", g_status_counts))
    if cut.get("c2_root_verdict_counts_derived_from_all_54_rows") != c2_verdict_counts:
        raise AssertionError("C2 summary is not derived from all rows")
    if cut.get("g_formal_status_counts") != g_status_counts:
        raise AssertionError("G status summary is not derived from all rows")
    if cut.get("current_evaluation_state_counts_derived_from_all_54_rows") != state_counts:
        raise AssertionError("C3 evaluation state summary is not derived from all rows")
    if final_mode:
        if cut.get("current_root_verdict_counts_derived_from_all_54_rows") != current_root_counts:
            raise AssertionError("current root verdict summary is not derived from all rows")
        if cut.get("root_adjudication_authority") != "root":
            raise AssertionError("current root verdict authority is not identified")
        if cut.get("root_adjudication_scope") != (
            "All 54 allocated C findings evaluated against their original hash-bound criteria. "
            "Historical status and G formal status remain separate."
        ):
            raise AssertionError("current root adjudication scope is missing or changed")
    if cut.get("status_semantics") != c3_input["status_semantics"]:
        raise AssertionError("C3 interpretation semantics differ from typed input")
    if (
        cut.get("pointer_validation", {}).get("C2_frozen_rows_resolved_by_source_validator")
        != c2_validation["RFC_6901_pointers_resolved"]
    ):
        raise AssertionError("C2 pointer-validation summary does not match source validator")
    if cut.get("pointer_validation", {}).get("C3_explicit_receipt_pointer_count") != sum(
        len(ref["json_pointers"])
        for row in cut["rows"]
        for ref in row["current_evaluation"]["evidence_refs"]
    ):
        raise AssertionError("C3 explicit receipt pointer count mismatch")
    expected_supplemental_counts = {
        "supplemental_source_handoff_count": len(verified_supplemental_handoffs),
        "supplemental_candidate_binding_count": sum(
            len(item["candidate_bindings"]) for item in verified_supplemental_handoffs
        ),
        "supplemental_selected_file_reference_occurrences": sum(
            len(item["selected_evidence_files"])
            + sum(len(candidate["source_files"]) for candidate in item["candidate_bindings"])
            for item in verified_supplemental_handoffs
        ),
    }
    for key, expected in expected_supplemental_counts.items():
        if cut.get("pointer_validation", {}).get(key) != expected:
            raise AssertionError((key, "supplemental source summary mismatch", expected))

    md_raw = markdown_path.read_bytes()
    md_hash = sha(md_raw)
    if expected_markdown_sha and md_hash != expected_markdown_sha:
        raise AssertionError(("C3 Markdown SHA mismatch", md_hash, expected_markdown_sha))
    md_text = md_raw.decode("utf-8")
    table_rows = [
        line for line in md_text.splitlines() if re.match(r"^\|\s*(?:B\d+|LA-\d+)\s*\|", line)
    ]
    if len(table_rows) != 54:
        raise AssertionError(("C3 Markdown row denominator mismatch", len(table_rows)))
    for row in cut["rows"]:
        if f"| {row['id']} |" not in md_text:
            raise AssertionError(("C3 Markdown omits row", row["id"]))
    for handoff in verified_supplemental_handoffs:
        if (
            f"| {handoff['ref_id']} |" not in md_text
            or handoff["path_at_sha256"] not in md_text
            or any(pointer not in md_text for pointer in handoff["evidence_pointers"])
        ):
            raise AssertionError((handoff["ref_id"], "Markdown omits supplemental source binding"))
        for finding_id in handoff["finding_ids"]:
            row_lines = [
                line for line in md_text.splitlines() if line.startswith(f"| {finding_id} |")
            ]
            if len(row_lines) != 1 or handoff["ref_id"] not in row_lines[0]:
                raise AssertionError(
                    (finding_id, handoff["ref_id"], "Markdown row omits supplemental evidence ref")
                )
    for receipt in portable_index:
        expected_row = (
            f"| {receipt['receipt_id']} | {receipt['historical_source_status']} | "
            f"`{receipt['historical_path_at_sha256']}` | `{receipt['path_at_sha256']}` | "
            f"`{receipt['git_blob']}` | {receipt['size_bytes']} |"
        )
        if expected_row not in md_text:
            raise AssertionError((receipt["receipt_id"], "C3 Markdown omits portable receipt row"))

    return {
        "result": "PASS",
        "cut_sha256": sha(cut_raw),
        "markdown_sha256": md_hash,
        "input_sha256": input_sha,
        "C2_source_validator": c2_validation["result"],
        "C2_source_sha256": c2_source["sha256"],
        "C2_pointer_count": c2_validation["RFC_6901_pointers_resolved"],
        "historical_local_only_receipts": len(historical_local_only),
        "portable_receipt_overrides_used": [receipt["receipt_id"] for receipt in portable_index],
        "G_snapshot": g_snapshot,
        "coverage_denominator": derived_coverage,
        "rows": len(cut["rows"]),
        "criterion_occurrences_with_inclusive_source_hash": criterion_occurrences,
        "bundles": len(expected_bundle_crosswalk),
        "C2_root_verdict_context_counts": c2_verdict_counts,
        "G_formal_status_counts": g_status_counts,
        "C3_evaluation_state_counts": state_counts,
        "current_root_verdict_counts": current_root_counts,
        "C3_resolved_source_references": resolved_c3,
        "C3_explicit_receipt_pointers": cut["pointer_validation"][
            "C3_explicit_receipt_pointer_count"
        ],
        **expected_supplemental_counts,
        "tree_path_presence_checks": sum(
            len(row["current_evaluation"]["tree_path_checks"]) for row in cut["rows"]
        ),
        "markdown_rows": len(table_rows),
        "new_C3_verdicts_assigned": final_mode,
    }


def main() -> None:
    global \
        ROOT, \
        BASE, \
        SNAPSHOT, \
        INVENTORY_PATH, \
        EXPECTED_CUT_SHA, \
        EXPECTED_MD_SHA, \
        EXPECTED_INVENTORY_SHA, \
        MARKDOWN_PATH, \
        LOCAL_EVIDENCE_ROOT
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--mode", choices=("c2", "c3", "c3-final"), default="c2")
    parser.add_argument("--cut", required=True, type=Path)
    parser.add_argument("--markdown", required=True, type=Path)
    parser.add_argument("--inventory", type=Path)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--local-evidence-root", type=Path)
    parser.add_argument("--base-commit")
    parser.add_argument("--snapshot-commit")
    parser.add_argument("--expected-cut-sha")
    parser.add_argument("--expected-markdown-sha")
    parser.add_argument("--expected-inventory-sha")
    args = parser.parse_args()
    ROOT = args.repo_root.resolve()
    LOCAL_EVIDENCE_ROOT = args.local_evidence_root.resolve() if args.local_evidence_root else None
    if args.mode in {"c3", "c3-final"}:
        if args.input is None:
            raise SystemExit("--input is required with --mode c3 or c3-final")
        if not args.expected_cut_sha or not args.expected_markdown_sha:
            raise SystemExit(
                "--expected-cut-sha and --expected-markdown-sha are required with --mode c3"
            )
        cut_path = args.cut if args.cut.is_absolute() else ROOT / args.cut
        markdown_path = args.markdown if args.markdown.is_absolute() else ROOT / args.markdown
        input_path = args.input if args.input.is_absolute() else ROOT / args.input
        result = run_c3(
            cut_path,
            markdown_path,
            input_path,
            args.expected_cut_sha,
            args.expected_markdown_sha,
            final_mode=args.mode == "c3-final",
        )
        print(  # noqa: T201 - CLI emits the machine-readable validation receipt on stdout.
            json.dumps(result, ensure_ascii=False, indent=2)
        )
        return
    if not all(
        (
            args.inventory,
            args.base_commit,
            args.snapshot_commit,
            args.expected_markdown_sha,
            args.expected_inventory_sha,
        )
    ):
        raise SystemExit(
            "C2 validation requires --inventory, --base-commit, --snapshot-commit, "
            "--expected-markdown-sha, and --expected-inventory-sha"
        )
    BASE = args.base_commit
    SNAPSHOT = args.snapshot_commit
    EXPECTED_CUT_SHA = args.expected_cut_sha
    EXPECTED_MD_SHA = args.expected_markdown_sha
    EXPECTED_INVENTORY_SHA = args.expected_inventory_sha
    cut_path = args.cut if args.cut.is_absolute() else ROOT / args.cut
    MARKDOWN_PATH = args.markdown if args.markdown.is_absolute() else ROOT / args.markdown
    INVENTORY_PATH = str(args.inventory if args.inventory.is_absolute() else ROOT / args.inventory)
    result = run(cut_path, EXPECTED_CUT_SHA)
    print(  # noqa: T201 - CLI emits the machine-readable validation receipt on stdout.
        json.dumps(result, ensure_ascii=False, indent=2)
    )


if __name__ == "__main__":
    main()
