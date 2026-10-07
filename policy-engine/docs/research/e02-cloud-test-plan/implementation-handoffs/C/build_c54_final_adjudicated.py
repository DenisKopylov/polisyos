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

BASE_COMMIT = "198076863e143dea9f89f02734b13d50dae3eed5"
BASE_TREE = "2b754a92c27959e2e747738d47ed0b419f3b6dd8"
SOURCE_SNAPSHOT = "48af851db5c0e802c92d9b30226acbc4436c69ba"
SOURCE_SNAPSHOT_TREE = "84b6416c9cc84a975ceb2d5d4cd5a8a4f6b3d9e2"
SOURCE_SNAPSHOT_BRANCH = "codex/e02-C-continuation-20261006"
SOURCE_DRAFT = (
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/C/"
    "receipts/final54-c2/source-inputs/C54-final-reviewcut-20261006-v8.json.gz"
)
SOURCE_DRAFT_SHA256 = "8636e42db8fda1bb9df617cf718ae7e20d39eb11b40639d5ee6471a28160871a"
SOURCE_DRAFT_GZIP_SHA256 = "aa8c96a3dbf38874c750cf0dfdfc94de9be93925dee5ac193a2b37d595579639"
SOURCE_DRAFT_RAW_CAPTURE = (
    "policy-engine/.tmp/e02-C2/raw/census/C54-final-reviewcut-20261006-v8.json"
)
INVENTORY_PATH = (
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/C/"
    "receipts/final54-c2/source-inputs/C54-finding-inventory.tsv"
)
INVENTORY_SHA256 = "530f61eb0c356a9aa65b99154b233b19aadc09bde3f8f307a85a1f27965d16da"
INVENTORY_RAW_CAPTURE = "policy-engine/.tmp/e02-C2/raw/census/C54-finding-inventory.tsv"
LA039_MANIFEST = (
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/C/"
    "receipts/final54-c2/late-la039/evidence-manifest.json"
)
C3_INPUT_PATH = (
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/C/"
    "C54-c3-current-evaluation-input.json"
)
C3_OUTPUT_JSON = "policy-engine/.tmp/e02-C3/raw/census/C54-current-evaluation-20261007-v7.json"
C3_OUTPUT_MARKDOWN = "policy-engine/.tmp/e02-C3/raw/census/C54-current-evaluation-20261007-v7.md"
C3_FINAL_INPUT_PATH = (
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/C/"
    "C54-c3-final-adjudication-input.json"
)
C3_FINAL_OUTPUT_JSON = (
    "policy-engine/.tmp/e02-C3/raw/census/C54-current-root-adjudication-20261007-v1.json"
)
C3_FINAL_OUTPUT_MARKDOWN = (
    "policy-engine/.tmp/e02-C3/raw/census/C54-current-root-adjudication-20261007-v1.md"
)
C3_FINAL_INPUT_SCHEMA = "policyos.e02.c54.c3.current-root-adjudication-input.v1"
C3_FINAL_CUT_SCHEMA = "policyos.e02.c54.c3.current-root-adjudication.v1"
C4_FINAL_INPUT_SCHEMA = "policyos.e02.c54.c4.current-root-adjudication-input.v2"
C4_FINAL_CUT_SCHEMA = "policyos.e02.c54.c4.current-root-adjudication.v2"
C5_FINAL_INPUT_SCHEMA = "policyos.e02.c54.c5.current-root-adjudication-input.v2"
C5_FINAL_CUT_SCHEMA = "policyos.e02.c54.c5.current-root-adjudication.v2"
C4_FINAL_INPUT_PATH = (
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/C/"
    "C54-c4-current-root-adjudication-input.json"
)
C4_FINAL_OUTPUT_JSON = ".tmp/e02-C4/raw/census/C54-current-root-adjudication-20261007-v2.json"
C4_FINAL_OUTPUT_MARKDOWN = ".tmp/e02-C4/raw/census/C54-current-root-adjudication-20261007-v2.md"
C4_G_SNAPSHOT_COMMIT = "83e7c0e934d0b40644dec8a24264a0602ef013e7"
C4_G_SNAPSHOT_TREE = "dc1a7697f506b23f2db0f1c80bf929fd2d6a2e0d"
C5_FINAL_INPUT_PATH = (
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/C/"
    "C54-c5-current-inventory-input.json"
)
C5_FINAL_OUTPUT_JSON = ".tmp/e02-C5/raw/c54/C54-current-root-20261007-v1.json"
C5_FINAL_OUTPUT_MARKDOWN = ".tmp/e02-C5/raw/c54/C54-current-root-20261007-v1.md"
C5_C4_SOURCE_COMMIT = "847929e3e0cac30fb49ff61a47ecaf46d41ac94d"
C5_C4_SOURCE_TREE = "c4c392e8ecad5f1fb33297d8cbaa28597b22357c"
C5_G_SNAPSHOT_COMMIT = "9806442ddb47d624a2940bac75d9d6248e934c48"
C5_G_SNAPSHOT_TREE = "4a1caafc331990e0ebf0130a9051c08ae1ffcbd4"
C5_COVERAGE_PATH = "policy-engine/docs/research/e02-cloud-test-plan/closure-decisions/coverage.json"
C5_ALLOCATION_PATH = (
    "policy-engine/docs/research/e02-cloud-test-plan/execution-organization/allocation.json"
)
C5_FINDING_OWNERS_PATH = (
    "policy-engine/docs/research/e02-cloud-test-plan/execution-organization/finding-owners.tsv"
)
C5_BUNDLE_OWNERS_PATH = (
    "policy-engine/docs/research/e02-cloud-test-plan/execution-organization/bundle-owners.tsv"
)
C5_CLOSURE_C_PATH = "policy-engine/docs/research/e02-cloud-test-plan/closure-decisions/C.md"
C5_DECISIONS_PATH = (
    "policy-engine/docs/research/e02-cloud-test-plan/integration/reviews/"
    "2026-10-07-CD-C4-a795/C54-decisions.json"
)
C5_ACTIONS_PATH = (
    "policy-engine/docs/research/e02-cloud-test-plan/integration/reviews/"
    "2026-10-07-CD-C4-a795/C54-actions.md"
)
C2_C3_SOURCE_SHA256 = "38db6cac4195f210425502bd4c7fdf2884ccdb5ae42ef87170d17020a6358dcc"
C2_C3_SOURCE_BLOB = "61e1abe90ae5f81e37077e2dc8e92f7e4de0cb76"
C2_C3_SOURCE_PATH = (
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/C/"
    "C54-final-20261006-v10.json"
)
G_C3_COVERAGE_PATH = (
    "policy-engine/docs/research/e02-cloud-test-plan/closure-decisions/coverage.json"
)
G_C3_FINDING_OWNERS_PATH = (
    "policy-engine/docs/research/e02-cloud-test-plan/execution-organization/finding-owners.tsv"
)
G_C3_BUNDLE_OWNERS_PATH = (
    "policy-engine/docs/research/e02-cloud-test-plan/execution-organization/bundle-owners.tsv"
)


ROOT_VERDICTS = {
    "closed": {
        *(f"B{i}" for i in range(138, 146)),
        "B17",
        "B81",
        "B82",
        "B84",
        "B85",
        "B86",
        "B88",
        "LA-008",
        "LA-009",
        "LA-010",
        "LA-011",
        "LA-012",
        "LA-013",
        "LA-022",
        "LA-030",
        "LA-031",
        "LA-043",
        "LA-044",
        "LA-047",
        "LA-048",
        "LA-049",
        "B146",
        "B147",
    },
    "limited": {
        "B79",
        "LA-006",
        "LA-034",
        "LA-038",
        "LA-039",
        "LA-041",
        "LA-042",
        "LA-050",
        "LA-024",
    },
    "held": {
        "B80",
        "B83",
        "LA-005",
        "LA-018",
        "LA-021",
        "LA-023",
        "LA-025",
        "LA-026",
        "LA-027",
        "LA-028",
        "LA-029",
        "LA-032",
        "LA-036",
        "LA-040",
    },
}

ING_OUTCOMES = {
    "B79": (
        "The served batch_incremental route injects the exact persisted hint into the real REST "
        "request, and its since filter persists the independently expected rows. Promotion of "
        "that tenant cursor "
        "still lacks a source-confirmed evidence-content binder."
    ),
    "B80": (
        "Per-source storage and fail/retry behavior are exercised; unverified source progress is "
        "not promoted. The confirmed-cursor writer remains fail-closed until owner evidence "
        "content-binds dataset and ingestion_run_id."
    ),
    "B81": (
        "Failure, reopen, and retry compare exact raw source bytes, ordered row IDs, durable "
        "frontier, and cursor; "
        "the returned checkpoint reference resolves to the committed full payload."
    ),
    "B82": (
        "COUNT, TUMBLING, SESSION, and SLIDING checkpoints restore pending state; "
        "schema/window/key/TTL mismatch "
        "refuses before rewind or poll and preserves the predecessor CAS and cursor."
    ),
    "B83": (
        "The persisted UTC ingestion horizon is 86,400 seconds, composite primitive keys and "
        "source/partition isolation are exercised, and live-key overflow refuses before eviction. "
        "The connector does not supply "
        "source-owned event/version identity; synthesized _message_id is not that authority."
    ),
    "B84": (
        "Retained-state, input-row/serialized-byte, and output-reference budgets are checked "
        "before publication; lower-cap restore refuses before flush, write, rewind, poll, or "
        "frontier advance and preserves its predecessor. This makes no RSS, pre-return connector-"
        "allocation, or staged-spill claim; a real spill reader is absent."
    ),
    "B85": (
        "Every persisted window contributor ArtifactRef matches the independent "
        "source-row-to-chunk map across "
        "trigger, flush, and restart, and all exact chunk bytes are read back."
    ),
    "B86": (
        "Required, optional, missing, null, type, and finite row membership produces identical "
        "accepted IDs, keyed "
        "quarantine reasons, and accepted-data digest at batch sizes 1, 2, and 8."
    ),
    "B88": (
        "Served replay opens the retained exact owned CAS request/response artifact; missing or "
        "corrupt artifacts refuse without native connector egress from both repository and product "
        "working directories. Scope is the "
        "retained source-card replay profile."
    ),
}


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(  # noqa: S603 - trusted Git command with argv; shell disabled.
        ["git", *args],  # noqa: S607 - trusted Git executable resolved by PATH.
        cwd=root,
        text=True,
    ).strip()


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def markdown_cell(value: object) -> str:
    if isinstance(value, list):
        text = "; ".join(str(item) for item in value)
    elif isinstance(value, dict):
        text = "; ".join(f"{key}={item}" for key, item in value.items())
    else:
        text = str(value if value is not None else "—")
    return text.replace("|", "\\|").replace("\n", "<br>")


def json_pointer_value(document: object, pointer: str) -> object:
    if pointer == "":
        return document
    value = document
    for raw_segment in pointer[1:].split("/"):
        segment = raw_segment.replace("~1", "/").replace("~0", "~")
        value = value[int(segment)] if isinstance(value, list) else value[segment]
    return value


def declared_finding_scope(
    handoff_doc: dict, pointers: object, family: str, c2_rows: dict[str, dict]
) -> list[str]:
    """Resolve a handoff's finding scope from its selected Git-bound fields."""
    if (
        not isinstance(pointers, list)
        or not pointers
        or any(not isinstance(pointer, str) or not pointer.startswith("/") for pointer in pointers)
        or len(pointers) != len(set(pointers))
    ):
        raise RuntimeError(f"source-family finding-scope pointers are invalid: {family}")
    finding_ids: set[str] = set()
    for pointer in pointers:
        selected = json_pointer_value(handoff_doc, pointer)
        if not isinstance(selected, list):
            raise RuntimeError(
                f"source-family finding-scope pointer is not an array: {family} {pointer}"
            )
        pointer_ids: set[str] = set()
        for item in selected:
            finding_id = (
                item
                if isinstance(item, str)
                else item.get("id")
                if isinstance(item, dict)
                else None
            )
            if not isinstance(finding_id, str) or not finding_id or finding_id in pointer_ids:
                raise RuntimeError(
                    f"source-family finding scope has an invalid or repeated ID: {family}"
                )
            row = c2_rows.get(finding_id)
            if row is None or row["source_family"] != family:
                raise RuntimeError(
                    "source-family finding scope names an unknown or other-family row: "
                    f"{family} {finding_id}"
                )
            pointer_ids.add(finding_id)
        finding_ids.update(pointer_ids)
    return sorted(finding_ids)


def criterion_cell(row: dict) -> str:
    return "<br>".join(
        f"{item['criterion_id']} {item['document_ref']} L{item['line_span']} "
        f"`{item['criterion_sha256']}`"
        + (
            f"<br>Original wording: {markdown_cell(item['original_wording'])}"
            if "original_wording" in item
            else ""
        )
        for item in row["criterion_refs"]
    )


def derive_c3_evidence_state(
    finding_id: str,
    source_family: str,
    c3_input: dict,
    verified_current_families: dict,
    supplemental_by_finding: dict[str, list[str]],
    cycle_label: str = "C3",
    *,
    criterion_scoped: bool = False,
    row_criterion_ids: list[str] | None = None,
) -> str:
    """Classify evidence from scope and verified receipts, never state labels."""
    override = c3_input.get("row_overrides", {}).get(finding_id, {})
    refresh_scope = c3_input.get("family_refresh_states", {})
    current_ref = verified_current_families.get(source_family, {})
    family_scope_matches = finding_id in current_ref.get("declared_finding_scope_ids", [])
    if criterion_scoped:
        declared_criteria = set(current_ref.get("declared_criterion_scope_ids", []))
        family_scope_matches = bool(row_criterion_ids) and set(row_criterion_ids).issubset(
            declared_criteria
        )
    if family_scope_matches or supplemental_by_finding.get(finding_id):
        return "fresh_criterion_evidence_reviewed"
    if source_family in refresh_scope and source_family != "default" and not current_ref:
        return f"{cycle_label.lower()}_source_refresh_pending"
    if override.get("code_outcome") and override.get("evidence_refs"):
        return "criterion_binding_corrected"
    return "c2_frozen_evidence_carried_forward"


def c3_evidence_scope_source(
    finding_id: str,
    source_family: str,
    verified_current_families: dict,
    supplemental_by_finding: dict[str, list[str]],
    row_criterion_ids: list[str] | None = None,
    *,
    criterion_scoped: bool = False,
) -> str | None:
    """Return which bound handoff actually names this finding's criterion scope."""
    current_ref = verified_current_families.get(source_family, {})
    if criterion_scoped:
        declared = set(current_ref.get("declared_criterion_scope_ids", []))
        if row_criterion_ids and set(row_criterion_ids).issubset(declared):
            return "current_family"
    elif finding_id in current_ref.get("declared_finding_scope_ids", []):
        return "current_family"
    if supplemental_by_finding.get(finding_id):
        return "supplemental"
    return None


def c3_evidence_state_pointer(
    finding_id: str,
    source_family: str,
    state: str,
    family_state_key: str,
    c3_input: dict,
    verified_current_families: dict,
    supplemental_by_finding: dict[str, list[str]],
    row_criterion_ids: list[str] | None = None,
    *,
    criterion_scoped: bool = False,
) -> str:
    """Point to the bound input object that establishes the current evidence state."""
    scope_source = c3_evidence_scope_source(
        finding_id,
        source_family,
        verified_current_families,
        supplemental_by_finding,
        row_criterion_ids,
        criterion_scoped=criterion_scoped,
    )
    if scope_source == "current_family":
        return f"/current_source_family_refs/{source_family}"
    if scope_source == "supplemental":
        refs = supplemental_by_finding[finding_id]
        for index, item in enumerate(c3_input.get("supplemental_source_handoffs", [])):
            if item.get("ref_id") in refs:
                return f"/supplemental_source_handoffs/{index}"
        raise RuntimeError(f"supplemental state pointer is missing: {finding_id}")
    if state == "criterion_binding_corrected":
        return f"/row_overrides/{finding_id}"
    if source_family in verified_current_families:
        return f"/current_source_family_refs/{source_family}"
    return f"/family_refresh_states/{family_state_key}"


def source_family_version_binding(
    finding_id: str,
    source_family: str,
    verified_current_families: dict,
    row_criterion_ids: list[str] | None = None,
    *,
    criterion_scoped: bool = False,
) -> dict:
    """Keep current family-version verification separate from criterion evidence."""
    current_ref = verified_current_families.get(source_family)
    if current_ref is None:
        return {
            "status": "c2_source_family_version_carried_forward",
            "source_family_ref_key": source_family,
            "family_handoff_criterion_scope_includes_finding": None,
        }
    declared_ids = current_ref["declared_finding_scope_ids"]
    if criterion_scoped:
        declared_criterion_ids = current_ref.get("declared_criterion_scope_ids", [])
        return {
            "status": "current_source_family_version_verified",
            "source_family_ref_key": source_family,
            "candidate_commit": current_ref["candidate_commit"],
            "candidate_tree": current_ref["candidate_tree"],
            "handoff_path_at_sha256": current_ref["handoff_path_at_sha256"],
            "declared_finding_scope_ids": declared_ids,
            "finding_scope_pointers": current_ref["finding_scope_pointers"],
            "declared_criterion_scope_ids": declared_criterion_ids,
            "criterion_scope_pointers": current_ref["criterion_scope_pointers"],
            "family_handoff_criterion_scope_includes_finding": (
                bool(row_criterion_ids)
                and set(row_criterion_ids).issubset(set(declared_criterion_ids))
            ),
        }
    return {
        "status": "current_source_family_version_verified",
        "source_family_ref_key": source_family,
        "candidate_commit": current_ref["candidate_commit"],
        "candidate_tree": current_ref["candidate_tree"],
        "handoff_path_at_sha256": current_ref["handoff_path_at_sha256"],
        "declared_finding_scope_ids": declared_ids,
        "finding_scope_pointers": current_ref["finding_scope_pointers"],
        "family_handoff_criterion_scope_includes_finding": finding_id in declared_ids,
    }


def parse_c_md_labels(raw: bytes) -> dict[str, tuple[str, str]]:
    """Read finding status/capability labels from the pinned G C.md rows."""
    labels: dict[str, tuple[str, str]] = {}
    for line in raw.decode("utf-8").splitlines():
        if '<a id="finding-' not in line:
            continue
        anchor = re.search(r'<a id="finding-([^\"]+)"', line)
        cells = line.split("|")
        if anchor is None or len(cells) < 4:
            raise RuntimeError("pinned G C.md contains an unparseable finding row")
        label = re.search(r"`([^`]+)`\s*/\s*`([^`]+)`", cells[2])
        if label is None:
            label = re.search(r"`([^`]+)`\s*/\s*—", cells[2])
            if label is None:
                raise RuntimeError(f"pinned G C.md has an unparseable label: {anchor.group(1)}")
            status, capability = label.group(1), ""
        else:
            status, capability = label.group(1), label.group(2)
        finding_id = anchor.group(1).upper()
        finding_id = re.sub(
            r"^LA-(\d+)$", lambda match: f"LA-{int(match.group(1)):03d}", finding_id
        )
        if finding_id in labels:
            raise RuntimeError(f"pinned G C.md repeats a finding row: {finding_id}")
        labels[finding_id] = (status, capability)
    return labels


def c3_evidence_state_note(
    state: str,
    source_family: str,
    scope_source: str | None,
    current_family_verified: bool,
    cycle_label: str = "C3",
) -> str:
    """Render a state explanation from the evidence classification."""
    if state == "fresh_criterion_evidence_reviewed":
        if scope_source == "supplemental":
            return (
                "A verified supplemental handoff explicitly declares this finding's "
                "criterion scope."
            )
        return (
            f"The verified {source_family} handoff explicitly declares this finding's "
            "criterion scope."
        )
    if state == f"{cycle_label.lower()}_source_refresh_pending":
        return (
            f"A {cycle_label} source refresh is in scope for {source_family}, but no current "
            "source-family "
            "handoff is bound."
        )
    if state == "criterion_binding_corrected":
        return (
            "The row-specific criterion and evidence binding is corrected by the listed receipts."
        )
    if current_family_verified:
        if cycle_label == "C4":
            return (
                f"The current {source_family} source-family version is verified, but its "
                "handoff does not declare this row's original criterion; the reviewed C2 "
                "criterion evidence is carried forward."
            )
        return (
            f"The current {source_family} source-family version is verified, but its declared "
            "finding scope does not include this row; frozen C2 criterion evidence is carried "
            "forward."
        )
    return (
        f"No {cycle_label} source refresh or row correction is bound; "
        "the frozen C2 evidence is carried forward."
    )


def required_portable_receipt_ids(root: Path, c2_cut: dict, c2_source: dict) -> set[str]:
    """Derive portable companions from the frozen receipt index and its Git source tree."""
    required = set()
    for receipt_id, receipt in c2_cut["receipt_index"].items():
        if receipt.get("head"):
            continue
        path = receipt["path_at_sha256"].rsplit("@sha256:", 1)[0]
        if not git_path_exists(root, c2_source["commit"], path):
            required.add(receipt_id)
    return required


def receipt_cell(row: dict) -> str:
    return "<br>".join(
        f"{ref['receipt_id']} "
        + (", ".join(ref["json_pointers"]) if ref["json_pointers"] else "(whole-file SHA)")
        for ref in row["deciding_receipts"]
    )


def render_markdown(cut: dict) -> str:
    counts = cut["final_verdict_counts_derived_from_all_54_rows"]
    coverage = cut["coverage_denominator_derived_from_pinned_coverage_json"]
    lines = [
        "# C54 final criterion-backed adjudication",
        "",
        (
            "This table records the root-adjudicated candidate verdict for every C finding. "
            "Historical status is kept in a separate column and is not projected into "
            "the new verdict."
        ),
        "",
        (
            f"Source snapshot: `{cut['snapshot']['commit']}` / tree `{cut['snapshot']['tree']}`. "
            f"Baseline: `{cut['base']['commit']}` / tree `{cut['base']['tree']}`."
        ),
        "",
        (
            f"Pinned full denominator: "
            f"{coverage['all_bundles']} bundles, "
            f"{coverage['all_findings']} findings, "
            f"and {coverage['canonical_criterion_occurrences']} "
            "canonical criterion occurrences. "
            f"C allocation: {coverage['C_bundles']} bundles, "
            f"{coverage['C_findings']} findings, "
            f"and {coverage['C_hash_bound_criteria']} "
            "hash-bound criterion occurrences."
        ),
        "",
        (
            f"Root verdicts derived from all 54 rows: {counts['closed']} closed, "
            f"{counts['limited']} limited, {counts['held']} held."
        ),
        "",
        cut["baseline_use_limit"],
        "",
        (
            "| ID | Bundles / hash-bound criteria | Historical status | Capability label | "
            "Code outcome | Root final verdict and reason | Missing input / skipped backend | "
            "Remaining verification | "
            "Deciding receipts | Next owner |"
        ),
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in cut["rows"]:
        hist = row["historical_status"]
        historical = "; ".join(f"{key}={value}" for key, value in hist.items())
        verdict = row["root_finding_verdict"]
        cells = [
            row["id"],
            f"{markdown_cell(row['bundles'])}<br>{criterion_cell(row)}",
            markdown_cell(historical),
            markdown_cell(row["capability_label"] or "—"),
            markdown_cell(row["code_outcome"]),
            f"**{verdict['value'].upper()}** — {markdown_cell(verdict['reason'])}",
            markdown_cell(row["missing_inputs_or_skipped_backend"]),
            markdown_cell(row["remaining_verification"]),
            receipt_cell(row),
            markdown_cell(row["next_owner"]),
        ]
        lines.append("| " + " | ".join(cells) + " |")

    lines.extend(
        [
            "",
            "## Criterion document index",
            "",
            (
                "Every criterion occurrence above binds the pinned source document, inclusive line "
                "span, and SHA-256 of those exact source lines."
            ),
            "",
            "| Ref | Path | Git blob | Source commit |",
            "| --- | --- | --- | --- |",
        ]
    )
    for document_ref, item in cut["criterion_document_index"].items():
        lines.append(
            f"| {document_ref} | `{item['path']}` | `{item['git_blob']}` | "
            f"`{item.get('source_commit', cut['base']['commit'])}` |"
        )

    lines.extend(
        [
            "",
            "## Receipt index",
            "",
            (
                "The row references above resolve through this exact path/SHA index. JSON pointers "
                "are RFC 6901 and were checked against the cited bytes."
            ),
            "",
            "| Receipt | Path at SHA-256 | Bytes | Git identity | Role |",
            "| --- | --- | ---: | --- | --- |",
        ]
    )
    for receipt_id, item in cut["receipt_index"].items():
        git_identity = (
            " / ".join(str(item[k]) for k in ("branch", "head", "tree") if item.get(k))
            or "local copied receipt; bytes pinned by SHA-256"
        )
        lines.append(
            f"| {receipt_id} | `{item['path_at_sha256']}` | {item['size_bytes']} | "
            f"`{markdown_cell(git_identity)}` | {markdown_cell(item['role'])} |"
        )

    lines.extend(
        [
            "",
            "## Source DAG and scope",
            "",
            (
                f"Source-DAG review: {markdown_cell(cut['source_dag_review']['decision'])}. "
                "It checks Git ancestry, source identity, and ownership; semantic closure is not "
                "inferred. Receipt IDs: "
                f"{', '.join(cut['source_dag_review']['receipt_ids'])}."
            ),
            "",
            (
                "Late LA-039 installed evidence is bound by the `R210` evidence manifest and its "
                "nested file hashes. The script's source digest is post-run-only; the recorded "
                "filesystem mtime precedes launch by 39.667 ms, but no cryptographic "
                "prelaunch/in-run "
                "digest exists. The scope is synthetic fixtures on the installed CAT 8dfa profile, "
                "not production corpus or model authority."
            ),
            "",
        ]
    )
    inputs = cut["input_receipts"]
    lines.extend(
        [
            "## Canonical reproduction inputs",
            "",
            (
                f"Reviewed v8 input: `{inputs['reviewed_source_archive_path_at_sha256']}`; "
                f"uncompressed SHA-256 `{inputs['reviewed_source_uncompressed_sha256']}`."
            ),
            (
                f"Exact historical inventory: `{inputs['inventory_tsv_path_at_sha256']}`. "
                "The raw capture locator is retained separately as provenance: "
                f"`{inputs['inventory_raw_capture_path_at_sha256']}`."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def render_c3_markdown(cut: dict, c2_cut: dict, c3_input: dict, cycle_label: str = "C3") -> str:
    final_mode = cut.get("final_verdicts_assigned") is True
    counts = cut["c2_root_verdict_counts_derived_from_all_54_rows"]
    state_counts = cut["current_evaluation_state_counts_derived_from_all_54_rows"]
    lines = [
        (
            f"# C54 {cycle_label} current-root adjudication"
            if final_mode
            else f"# C54 {cycle_label} current-evidence census"
        ),
        "",
        (
            (
                "This table assigns a current root verdict for each C finding from the reviewed "
                "criterion evidence. It keeps historical status, the prior C2 root verdict, and "
                "G's formal closure state separate. G closure is not inferred from C candidate "
                "evidence."
            )
            if final_mode
            else (
                f"This is a source-evidence crosswalk, not a {cycle_label} verdict. "
                "It keeps historical "
                "status, "
                "the frozen C2 root adjudication, and G's formal closure state in separate fields. "
                "G closure is not inferred from C2 candidate evidence."
            )
        ),
        "",
        (
            f"C2 source cut: `{cut['c2_source']['commit']}` / tree `{cut['c2_source']['tree']}`; "
            f"G source cut: `{cut['g_snapshot']['commit']}` / tree `{cut['g_snapshot']['tree']}`; "
            f"criterion baseline: `{cut['base']['commit']}` / tree `{cut['base']['tree']}`."
        ),
        "",
        (
            f"Pinned full denominator: {cut['coverage_denominator']['all_bundles']} bundles, "
            f"{cut['coverage_denominator']['all_findings']} findings, and "
            f"{cut['coverage_denominator']['canonical_criterion_occurrences']} canonical criterion "
            "occurrences. "
            f"C allocation: {cut['coverage_denominator']['C_bundles']} bundles, "
            f"{cut['coverage_denominator']['C_findings']} findings, and "
            f"{cut['coverage_denominator']['C_hash_bound_criteria']} hash-bound criteria."
        ),
        "",
        (
            (
                f"Current root verdicts from all 54 rows: "
                f"{cut['current_root_verdict_counts_derived_from_all_54_rows']}. "
                f"Prior C2 root verdict counts (context): {counts}. "
                f"G formal statuses: {cut['g_formal_status_counts']}."
            )
            if final_mode
            else (
                f"Frozen C2 root-adjudication counts (context only): {counts['closed']} closed, "
                f"{counts['limited']} limited, {counts['held']} held. "
                f"G formal statuses: {cut['g_formal_status_counts']}."
            )
        ),
        (
            f"Current evidence bases: {state_counts}."
            if final_mode
            else f"{cycle_label} evidence-crosswalk states: {state_counts}."
        ),
        "",
        cut["baseline_use_limit"],
        "",
        (
            (
                "| ID | Bundles / original criteria | Historical status | G formal status | "
                "G capability / owner | C source family | Prior C2 verdict | "
                "Current evidence basis | Current code outcome | Current verdict and reason | "
                "Missing input / skipped backend | "
                + (
                    "Remaining verification | Next action | Deciding evidence | Next owner |"
                    if cycle_label == "C4"
                    else "Remaining verification | Deciding evidence | Next owner |"
                )
            )
            if final_mode
            else (
                "| ID | Bundles / original criteria | Historical status | G formal status / "
                "capability | Canonical G owner | C source family | C2 frozen verdict | "
                f"{cycle_label} evidence state and current "
                "code outcome | Remaining mechanism / verification / input / decision | "
                "Evidence refs |"
            )
        ),
        (
            "| " + " | ".join(["---"] * (15 if final_mode and cycle_label == "C4" else 14)) + " |"
            if final_mode
            else "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"
        ),
    ]
    c2_rows_by_id = {row["id"]: row for row in c2_cut["rows"]}
    for row in cut["rows"]:
        hist = "; ".join(f"{key}={value}" for key, value in row["historical_status"].items())
        c2verdict = row["c2_snapshot"]["root_verdict"]
        current = row["current_evaluation"]
        remaining = current["remaining_work"]
        code_outcome = current.get("code_outcome")
        if code_outcome is None:
            code_outcome = c2_rows_by_id[row["id"]]["code_outcome"]
        state_note = current["state_note"]
        remaining_parts = []
        for label, item in remaining.items():
            if "source_pointer" in item:
                value = json_pointer_value(c2_cut, item["source_pointer"])
            else:
                value = item.get("text", item.get("owner", item.get("status", "—")))
            remaining_parts.append(f"{label}: {markdown_cell(value)}")
        remaining_cell = "<br>".join(remaining_parts)
        refs = []
        if current["evidence_ref_source_pointer"]:
            refs.append(f"C2:{current['evidence_ref_source_pointer']}")
        for ref in current["evidence_refs"]:
            pointers = (
                ", ".join(ref["json_pointers"]) if ref["json_pointers"] else "(whole-file SHA)"
            )
            refs.append(f"C2:{ref['receipt_id']} {pointers}")
        supplemental_by_id = {
            item["ref_id"]: item for item in cut.get("supplemental_source_handoffs", [])
        }
        for ref_id in current.get("supplemental_evidence_refs", []):
            supplemental = supplemental_by_id[ref_id]
            refs.append(
                f"{ref_id}:{supplemental['path_at_sha256']} "
                f"{', '.join(supplemental['evidence_pointers'])}"
            )
        if cycle_label == "C4":
            context_update = current.get("current_context_update")
            if context_update:
                refs.append(
                    f"context={context_update['source']['path_at_sha256']}"
                    f"#{context_update['source_pointer']}"
                )
                refs.extend(
                    f"context-support={cut['current_context_sources'][ref_id]['path_at_sha256']}"
                    for ref_id in context_update["supporting_source_ref_ids"]
                )
            family_binding = current["source_family_version_binding"]
            if family_binding.get("handoff_path_at_sha256"):
                refs.append(
                    "family="
                    f"{family_binding['handoff_path_at_sha256']} "
                    f"{family_binding.get('criterion_scope_pointers', [])}"
                )
        g = row["g_current"]
        source_family = row["source_family"]
        if final_mode:
            final_verdict = row["current_root_verdict"]
            current_refs = []
            if current["evidence_ref_source_pointer"]:
                current_refs.append(f"C2:{current['evidence_ref_source_pointer']}")
            current_refs.extend(refs)
            if cycle_label == "C4":
                label_sources = (
                    f"coverage.json={g['coverage_capability_label']!r}; "
                    f"C.md={g['c_md_capability_label']!r} ({g['capability_label_source_state']})"
                )
                if g.get("capability_label_source_note"):
                    label_sources += f"<br>{g['capability_label_source_note']}"
                source_binding = current["source_family_version_binding"]
                if source_binding.get("candidate_commit"):
                    family_cell = (
                        f"{source_family}<br>candidate `{source_binding['candidate_commit']}`"
                        f" / tree `{source_binding['candidate_tree']}`<br>"
                        f"{source_binding['handoff_path_at_sha256']}"
                    )
                else:
                    prior = cut["topic_source_refs"].get(source_family, {})
                    pins = prior.get("source_pins", [])
                    pin_cell = "<br>".join(
                        f"{item['role']}: `{item['commit']}` / tree `{item['tree']}`"
                        for item in pins
                    )
                    family_cell = (
                        f"{source_family}<br>prior handoff: "
                        f"{prior.get('prior_handoff_path_at_sha256', '—')}<br>{pin_cell}"
                    )
                evidence_basis_cell = (
                    f"{current['evidence_basis']}<br>{current['state_note']}<br>"
                    "handoff criterion scope includes row: "
                    f"{source_binding['family_handoff_criterion_scope_includes_finding']}"
                )
                cells = [
                    row["id"],
                    f"{markdown_cell(row['bundles'])}<br>{criterion_cell(row)}",
                    markdown_cell(hist),
                    markdown_cell(g["formal_status"]),
                    markdown_cell(
                        f"{label_sources}<br>canonical owner: {g['canonical_source_owner']}"
                    ),
                    markdown_cell(family_cell),
                    markdown_cell(f"{c2verdict['value']} ({c2verdict['status']})"),
                    markdown_cell(evidence_basis_cell),
                    markdown_cell(current.get("scoped_proven_part", current.get("code_outcome"))),
                    (
                        f"**{final_verdict['value'].upper()}** — "
                        f"{markdown_cell(final_verdict['reason'])}"
                    ),
                    markdown_cell(
                        current.get(
                            "missing_input_or_skipped_backend",
                            current["missing_inputs_or_skipped_backend"],
                        )
                    ),
                    markdown_cell(current["remaining_verification"]),
                    *([markdown_cell(current["next_action"])] if cycle_label == "C4" else []),
                    "<br>".join(current_refs),
                    markdown_cell(current["next_owner"]),
                ]
            else:
                cells = [
                    row["id"],
                    f"{markdown_cell(row['bundles'])}<br>{criterion_cell(row)}",
                    markdown_cell(hist),
                    markdown_cell(g["formal_status"]),
                    markdown_cell(
                        f"{g['capability_label'] or '—'}<br>{g['canonical_source_owner']}"
                    ),
                    markdown_cell(source_family),
                    markdown_cell(f"{c2verdict['value']} ({c2verdict['status']})"),
                    markdown_cell(
                        f"{current['evidence_basis']}<br>"
                        f"{current['state_note']}<br>"
                        f"source-family version: "
                        f"{current['source_family_version_binding']['status']}; "
                        f"family-handoff criterion scope includes finding: "
                        f"{current['source_family_version_binding']['family_handoff_criterion_scope_includes_finding']}"
                    ),
                    markdown_cell(current["code_outcome"]),
                    (
                        f"**{final_verdict['value'].upper()}** — "
                        f"{markdown_cell(final_verdict['reason'])}"
                    ),
                    markdown_cell(current["missing_inputs_or_skipped_backend"]),
                    markdown_cell(current["remaining_verification"]),
                    "<br>".join(current_refs),
                    markdown_cell(current["next_owner"]),
                ]
        else:
            cells = [
                row["id"],
                f"{markdown_cell(row['bundles'])}<br>{criterion_cell(row)}",
                markdown_cell(hist),
                markdown_cell(f"{g['formal_status']} / {g['capability_label'] or '—'}"),
                markdown_cell(g["canonical_source_owner"]),
                markdown_cell(source_family),
                markdown_cell(f"{c2verdict['value']} ({c2verdict['status']})"),
                f"**{markdown_cell(current['state'])}**<br>{markdown_cell(state_note)}<br>{markdown_cell(code_outcome)}",
                remaining_cell,
                "<br>".join(refs),
            ]
        lines.append("| " + " | ".join(cells) + " |")

    if cycle_label == "C4":
        empty_labels = [
            row["id"]
            for row in cut["rows"]
            if row["g_current"]["capability_label_source_state"] == "historical_source_label_empty"
        ]
        disagreements = [
            row
            for row in cut["rows"]
            if row["g_current"]["capability_label_source_state"]
            == "pinned_source_label_disagreement"
        ]
        lines.extend(
            [
                "",
                "## G capability-label source values",
                "",
                (
                    "The raw labels from coverage.json and C.md are displayed separately in each "
                    "row. Empty historical values remain empty; no new capability label is "
                    "inferred from a C disposition."
                ),
                "",
            ]
        )
        if disagreements:
            lines.append(
                "Pinned source disagreement: "
                + "; ".join(
                    f"{row['id']}: "
                    f"coverage.json={row['g_current']['coverage_capability_label']!r}, "
                    f"C.md={row['g_current']['c_md_capability_label']!r}"
                    for row in disagreements
                )
                + "."
            )
            lines.append("")
        if empty_labels:
            lines.append(
                "Both pinned source views have empty capability-label values for: "
                + ", ".join(f"`{finding_id}`" for finding_id in empty_labels)
                + ". The raw values remain unchanged; a finite criterion disposition does not "
                "infer a replacement whole-capability label."
            )
            lines.append("")
        lines.extend(
            [
                "## Original criterion documents",
                "",
                "Each row reproduces the exact inclusive source lines below after checking the "
                "document Git blob and SHA-256 of the complete line span.",
                "",
                "| Ref | Path | Commit / tree | Git blob | SHA-256 | Bytes |",
                "| --- | --- | --- | --- | --- | ---: |",
            ]
        )
        for document_ref, item in cut["criterion_document_index"].items():
            lines.append(
                "| "
                + " | ".join(
                    [
                        document_ref,
                        f"`{item['path']}`",
                        f"`{item['source_commit']}` / `{item['source_tree']}`",
                        f"`{item['git_blob']}`",
                        f"`{item['source_sha256']}`",
                        str(item["source_bytes"]),
                    ]
                )
                + " |"
            )

    current_source_families = cut.get("current_source_family_refs", {})
    if final_mode and current_source_families:
        lines.extend(
            [
                "",
                "## Current source-family pins",
                "",
                f"Fresh {cycle_label} source refs are shown separately from the frozen C2 "
                "source-family map.",
                "",
                (
                    "| Family | Branch | Candidate | Candidate tree | Handoff head/tree | "
                    "Criterion IDs | Handoff receipt |"
                    if cycle_label == "C4"
                    else "| Family | Branch | Head | Tree | Handoff receipt |"
                ),
                (
                    "| --- | --- | --- | --- | --- | --- | --- |"
                    if cycle_label == "C4"
                    else "| --- | --- | --- | --- | --- |"
                ),
            ]
        )
        for family, ref in sorted(current_source_families.items()):
            if cycle_label == "C4":
                family_cells = [
                    family,
                    markdown_cell(ref.get("branch", "—")),
                    f"`{markdown_cell(ref.get('candidate_commit', '—'))}`",
                    f"`{markdown_cell(ref.get('candidate_tree', '—'))}`",
                    f"`{markdown_cell(ref.get('head', '—'))}` / "
                    f"`{markdown_cell(ref.get('tree', '—'))}`",
                    markdown_cell(ref.get("declared_criterion_scope_ids", [])),
                    markdown_cell(ref.get("handoff_path_at_sha256", "—")),
                ]
            else:
                family_cells = [
                    family,
                    markdown_cell(ref.get("branch", "—")),
                    f"`{markdown_cell(ref.get('head', '—'))}`",
                    f"`{markdown_cell(ref.get('tree', '—'))}`",
                    markdown_cell(ref.get("handoff_path_at_sha256", "—")),
                ]
            lines.append("| " + " | ".join(family_cells) + " |")

    if cycle_label == "C4":
        lines.extend(
            [
                "",
                "## Frozen source-family map",
                "",
                "For rows without an explicit current criterion-scoped handoff, this map "
                "identifies "
                "the family source pins carried in the frozen C2 evidence cut. A family-version "
                "pin alone does not refresh a finding's criterion evidence.",
                "",
                "| Family | Prior handoff receipt | Prior candidate/tree pins |",
                "| --- | --- | --- |",
            ]
        )
        for family, ref in sorted(cut["topic_source_refs"].items()):
            pins = "<br>".join(
                f"{item['role']}: `{item['commit']}` / `{item['tree']}`"
                for item in ref.get("source_pins", [])
            )
            lines.append(
                f"| {family} | `{ref.get('prior_handoff_path_at_sha256', '—')}` | {pins} |"
            )

    supplemental_handoffs = cut.get("supplemental_source_handoffs", [])
    if supplemental_handoffs:
        lines.extend(
            [
                "",
                "## Supplemental source handoffs",
                "",
                (
                    "These committed handoffs supplement selected finding rows. Source and test "
                    "candidates are read from the exact Git trees shown; this does not change G's "
                    "separate formal status."
                ),
                "",
                "| Ref | Scope | Handoff | Source | Candidate files | Evidence |",
                "| --- | --- | --- | --- | --- | --- |",
            ]
        )
        for item in supplemental_handoffs:
            candidate_files = []
            for candidate in item["candidate_bindings"]:
                candidate_files.extend(
                    f"{source_file['path']}@{source_file['sha256']}"
                    for source_file in candidate["source_files"]
                )
            lines.append(
                "| "
                + " | ".join(
                    [
                        item["ref_id"],
                        markdown_cell(f"{item['family']} / {item['finding_ids']}"),
                        f"`{item['path_at_sha256']}`",
                        f"`{item['source_commit']}` / `{item['source_tree']}`",
                        markdown_cell(candidate_files),
                        markdown_cell(item["evidence_pointers"]),
                    ]
                )
                + " |"
            )

    lines.extend(
        [
            "",
            "## G bundle crosswalk",
            "",
            (
                "All 33 C bundles are joined to G coverage and the tracked bundle-owner table. "
                "Writer family is planning provenance; the finding-level source closure owner "
                "remains the canonical G owner."
            ),
            "",
            (
                "| Bundle | G unit | Initial writer family | C findings | C source families | "
                "G source closure owners |"
            ),
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for item in cut["bundle_crosswalk"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    item["bundle_id"],
                    item["g_unit"],
                    markdown_cell(item["initial_writer_family"]),
                    markdown_cell(item["c_finding_ids"]),
                    markdown_cell(item["c_source_families"]),
                    markdown_cell(item["g_source_closure_owners"]),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Pinned inputs and interpretation",
            "",
            (
                f"C2 source: `{cut['c2_source']['path']}@sha256:{cut['c2_source']['sha256']}`. "
                f"{cycle_label} typed input: "
                f"`{cut[f'{cycle_label.lower()}_input']['path']}@sha256:"
                f"{cut[f'{cycle_label.lower()}_input']['sha256']}`."
            ),
            "",
            (
                "G source documents are pinned by commit, tree, Git blob, SHA-256, and byte count "
                "in the JSON input references. The 59 original criterion spans are preserved from "
                "the C2 cut and rejoined to the exact C-unit coverage rows. The complete C2 "
                "receipt index stays in the pinned C2 source instead of being copied into this "
                "derived view."
            ),
            "",
            (
                "The historical C2 source-only receipt is explicitly marked `verification_missing` "
                f"at its original locator. The current {cycle_label} receipt index binds a "
                "repository "
                "companion with the same SHA-256 and size; this does not rewrite the C2 history."
            ),
            "",
            f"| Receipt | Historical status | Historical C2 locator | Current {cycle_label} "
            "path at SHA-256 | "
            "Git blob | Bytes |",
            "| --- | --- | --- | --- | --- | ---: |",
        ]
    )
    for receipt in cut["portable_receipt_index"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    receipt["receipt_id"],
                    receipt["historical_source_status"],
                    f"`{receipt['historical_path_at_sha256']}`",
                    f"`{receipt['path_at_sha256']}`",
                    f"`{receipt['git_blob']}`",
                    str(receipt["size_bytes"]),
                ]
            )
            + " |"
        )

    if cycle_label == "C4":
        lines.extend(
            [
                "",
                "## Current availability context sources",
                "",
                (
                    "These immutable sources update only missing-input, remaining-verification, "
                    "and next-owner fields. They do not change criterion-evidence state, code "
                    "outcome, or root-verdict basis."
                ),
                "",
                "| Ref | Pinned Git path | Git identity | Role |",
                "| --- | --- | --- | --- |",
            ]
        )
        for ref_id, source in cut.get("current_context_sources", {}).items():
            lines.append(
                f"| {ref_id} | `{source['path_at_sha256']}` | "
                f"`{source['source_commit']}` / tree `{source['source_tree']}` / "
                f"blob `{source['git_blob']}` | {markdown_cell(source['role'])} |"
            )

    if final_mode:
        lines.extend(
            [
                "",
                "Every row has a current root verdict and a named evidence basis. Rows marked "
                "`unchanged_source_prior_criterion_evidence_reviewed` carry forward the cited "
                "criterion evidence without representing a new runtime pass. C2 historical status "
                "and G formal status remain separate fields.",
                "",
            ]
        )
    else:
        pending_families = sorted(
            {
                row["source_family"]
                for row in cut["rows"]
                if row["current_evaluation"]["state"]
                == f"{cycle_label.lower()}_source_refresh_pending"
            }
        )
        corrected_rows = sum(
            row["current_evaluation"]["state"] == "criterion_binding_corrected"
            for row in cut["rows"]
        )
        pending_text = (
            "No source-family refresh is pending in this cut."
            if not pending_families
            else (
                f"A {cycle_label} source refresh remains pending for "
                + ", ".join(f"`{family}`" for family in pending_families)
                + " because no verified current handoff is bound."
            )
        )
        lines.extend(
            [
                "",
                "",
                (
                    f"{pending_text} Prior C2 code outcomes are carried context, "
                    f"not new {cycle_label} PASS evidence."
                ),
                (
                    f"{corrected_rows} row(s) have corrected criterion/evidence bindings. "
                    f"No {cycle_label} verdict is assigned."
                ),
                "",
            ]
        )
    return "\n".join(lines)


def apply_c3_root_adjudications(
    cut: dict,
    c2_cut: dict,
    c3_input: dict,
    verified_current_families: dict,
    cycle_label: str = "C3",
) -> dict:
    adjudications = c3_input.get("root_current_adjudications")
    row_ids = {row["id"] for row in cut["rows"]}
    if not isinstance(adjudications, dict) or set(adjudications) != row_ids:
        raise RuntimeError("final C3 input must explicitly adjudicate the complete 54-row set")

    allowed_verdicts = {"closed", "limited", "held", "open"}
    c2_rows = {row["id"]: row for row in c2_cut["rows"]}
    c2_indexes = {row["id"]: index for index, row in enumerate(c2_cut["rows"])}
    counts: Counter[str] = Counter()
    required_refresh_families = set(c3_input["family_refresh_states"]) - {"default"}
    missing_refresh_families = required_refresh_families - set(verified_current_families)
    if missing_refresh_families:
        raise RuntimeError(
            "final C3 cut lacks verified current handoffs for required refresh families: "
            + ", ".join(sorted(missing_refresh_families))
        )

    for row in cut["rows"]:
        finding_id = row["id"]
        decision = adjudications[finding_id]
        value = decision.get("value")
        if value not in allowed_verdicts:
            raise RuntimeError(f"invalid final C3 verdict or evidence basis: {finding_id}")
        current = row["current_evaluation"]
        derived_basis = {
            "fresh_criterion_evidence_reviewed": "fresh_criterion_evidence_reviewed",
            "criterion_binding_corrected": "criterion_evidence_binding_corrected",
            "c2_frozen_evidence_carried_forward": (
                "unchanged_source_prior_criterion_evidence_reviewed"
            ),
        }.get(current["state"])
        if derived_basis is None or (
            decision.get("basis") is not None and decision["basis"] != derived_basis
        ):
            raise RuntimeError(
                f"final evidence basis does not match bound row evidence: {finding_id}"
            )
        if "reason" in decision:
            reason = decision["reason"]
            reason_pointer = None
        else:
            reason_pointer = decision.get("reason_source_pointer")
            reason = json_pointer_value(c2_cut, reason_pointer) if reason_pointer else None
        if not isinstance(reason, str) or not reason.strip():
            raise RuntimeError(f"final C3 verdict reason is missing: {finding_id}")

        c2_row = c2_rows[finding_id]
        override = c3_input["row_overrides"].get(finding_id, {})
        code_outcome = override.get("code_outcome", c2_row["code_outcome"])
        capability_label = override.get("capability_label", c2_row["capability_label"])
        context_update = current.get("current_context_update") or {}
        missing = context_update.get(
            "missing_input",
            override.get(
                "missing_inputs_or_skipped_backend", c2_row["missing_inputs_or_skipped_backend"]
            ),
        )
        remaining = context_update.get(
            "remaining_verification",
            override.get("remaining_verification", c2_row["remaining_verification"]),
        )
        if cycle_label == "C4":
            next_action = decision.get("next_action")
            next_owner = decision.get("next_owner")
            if not isinstance(next_action, str) or not next_action.strip():
                raise RuntimeError(f"C4 next action is missing: {finding_id}")
            if not isinstance(next_owner, str) or not next_owner.strip():
                raise RuntimeError(f"C4 next owner is missing: {finding_id}")
        else:
            next_action = remaining
            next_owner = context_update.get(
                "next_owner", override.get("next_owner", c2_row["next_owner"])
            )
        if not all(
            isinstance(item, str) and item.strip()
            for item in (code_outcome, missing, remaining, next_owner)
        ):
            raise RuntimeError(
                f"final C3 row has incomplete current evaluation fields: {finding_id}"
            )

        current["evidence_basis"] = derived_basis
        current["code_outcome"] = code_outcome
        current["code_outcome_source_pointer"] = (
            None if "code_outcome" in override else f"/rows/{c2_indexes[finding_id]}/code_outcome"
        )
        current["current_capability_label"] = capability_label
        current["missing_inputs_or_skipped_backend"] = missing
        current["remaining_verification"] = remaining
        current["next_owner"] = next_owner
        current["decision_reason_source_pointer"] = reason_pointer
        if cycle_label == "C4":
            current["current_status"] = "current_root_adjudicated"
            current["scoped_proven_part"] = code_outcome
            current["missing_input_or_skipped_backend"] = missing
            current["next_action"] = next_action
            current["next_action_source_pointer"] = (
                f"/root_current_adjudications/{finding_id}/next_action"
            )
            current["next_owner_source_pointer"] = (
                f"/root_current_adjudications/{finding_id}/next_owner"
            )
            current["evidence_classification"] = derived_basis
            current["criterion_ids"] = [item["criterion_id"] for item in row["criterion_refs"]]
        row["current_root_verdict"] = {
            "value": value,
            "status": (
                "c4_current_root_adjudication" if cycle_label == "C4" else "final_root_adjudication"
            ),
            "basis": derived_basis,
            "reason": reason,
            "reason_source_pointer": reason_pointer,
        }
        counts[value] += 1

    pending_states = {
        f"{cycle_label.lower()}_source_refresh_pending",
        f"not_reassessed_in_{cycle_label}",
        "source_refresh_pending",
    }
    if any(row["current_evaluation"]["state"] in pending_states for row in cut["rows"]):
        raise RuntimeError("final C3 table cannot carry a pending current-evaluation state")

    cut["schema"] = C4_FINAL_CUT_SCHEMA if cycle_label == "C4" else C3_FINAL_CUT_SCHEMA
    cut["artifact"] = f"C54 {cycle_label} current root-adjudicated criterion evaluation"
    cut["status"] = f"{cycle_label.lower()}_current_root_adjudicated"
    cut["final_verdicts_assigned"] = True
    cut["current_root_verdict_counts_derived_from_all_54_rows"] = dict(sorted(counts.items()))
    cut["current_evaluation_state_counts_derived_from_all_54_rows"] = dict(
        sorted(Counter(row["current_evaluation"]["state"] for row in cut["rows"]).items())
    )
    cut["current_source_family_refs"] = verified_current_families
    cut["root_adjudication_authority"] = c3_input.get("root_adjudication_authority", "root")
    cut["root_adjudication_scope"] = (
        "All 54 allocated C findings have an explicit current C root disposition against "
        "their original hash-bound criteria. Evidence classification distinguishes current "
        "criterion-scoped handoffs, corrected bindings, and unchanged prior criterion evidence. "
        "Historical status and G formal status remain separate."
        if cycle_label == "C4"
        else "All 54 allocated C findings evaluated against their original hash-bound criteria. "
        "Historical status and G formal status remain separate."
    )
    return cut


def git_bytes(root: Path, spec: str) -> bytes:
    return subprocess.check_output(  # noqa: S603 - trusted Git command with argv; shell disabled.
        ["git", "show", spec],  # noqa: S607 - trusted Git executable resolved by PATH.
        cwd=root,
    )


def git_source_file(
    root: Path,
    commit: str,
    tree: str,
    path: str,
    *,
    expected_sha256: str | None = None,
    expected_blob: str | None = None,
    expected_size: int | None = None,
) -> tuple[bytes, str]:
    """Read a file only from a path present in the pinned Git tree."""
    relative = Path(path)
    if (
        not re.fullmatch(r"[0-9a-f]{40}", commit)
        or not re.fullmatch(r"[0-9a-f]{40}", tree)
        or relative.is_absolute()
        or ".." in relative.parts
        or "\\" in path
    ):
        raise RuntimeError("Git source reference has an invalid commit, tree, or path")
    if git(root, "rev-parse", f"{commit}^{{tree}}") != tree:
        raise RuntimeError(f"Git source tree mismatch for {commit}:{path}")
    spec = f"{commit}:{relative.as_posix()}"
    exists = subprocess.run(  # noqa: S603 - trusted Git object query; argv and shell disabled.
        ["git", "cat-file", "-e", spec],  # noqa: S607 - Git executable resolved by PATH.
        cwd=root,
        capture_output=True,
        check=False,
    )
    if exists.returncode != 0:
        raise RuntimeError(f"Git source path is absent from pinned tree: {spec}")
    if git(root, "cat-file", "-t", spec) != "blob":
        raise RuntimeError(f"Git source path is not a file blob in pinned tree: {spec}")
    raw = git_bytes(root, spec)
    blob = git(root, "rev-parse", spec)
    if expected_blob is not None and blob != expected_blob:
        raise RuntimeError(f"Git source blob mismatch for {spec}")
    if expected_sha256 is not None and sha256(raw) != expected_sha256:
        raise RuntimeError(f"Git source SHA-256 mismatch for {spec}")
    if expected_size is not None and len(raw) != expected_size:
        raise RuntimeError(f"Git source size mismatch for {spec}")
    return raw, blob


def bind_original_criterion_text(root: Path, base: dict, c2_cut: dict, rows: list[dict]) -> dict:
    """Attach exact original criterion text after verifying every source span."""
    source_index = c2_cut["criterion_document_index"]
    document_bytes: dict[str, tuple[bytes, dict]] = {}
    output_index = {}
    for document_ref, document in source_index.items():
        raw, _blob = git_source_file(
            root,
            base["commit"],
            base["tree"],
            document["path"],
            expected_blob=document["git_blob"],
        )
        document_bytes[document_ref] = (raw, document)
        output_index[document_ref] = {
            **document,
            "source_commit": base["commit"],
            "source_tree": base["tree"],
            "source_sha256": sha256(raw),
            "source_bytes": len(raw),
        }

    criterion_count = 0
    for row in rows:
        for criterion in row["criterion_refs"]:
            raw, _document = document_bytes[criterion["document_ref"]]
            source_lines = raw.splitlines(keepends=True)
            start_text, end_text = criterion["line_span"].split("-")
            start, end = int(start_text), int(end_text)
            if not 1 <= start <= end <= len(source_lines):
                raise RuntimeError(
                    f"original criterion span is outside its pinned document: {row['id']}"
                )
            selected = b"".join(source_lines[start - 1 : end])
            if sha256(selected) != criterion["criterion_sha256"]:
                raise RuntimeError(
                    f"original criterion span SHA mismatch: {row['id']} / "
                    f"{criterion['criterion_id']}"
                )
            criterion["original_wording"] = selected.decode("utf-8")
            criterion_count += 1
    if criterion_count != 59:
        raise RuntimeError(f"expected 59 original criterion spans; resolved {criterion_count}")
    return output_index


def git_path_exists(root: Path, revision: str, path: str) -> bool:
    return (
        subprocess.run(  # noqa: S603 - trusted Git command with argv; shell disabled.
            ["git", "cat-file", "-e", f"{revision}:{path}"],  # noqa: S607 - Git executable.
            cwd=root,
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )


def verify_current_source_family_refs(
    root: Path,
    c2_cut: dict,
    c3_input: dict,
    *,
    criterion_scoped: bool = False,
) -> dict:
    """Resolve source-refresh claims to handoff bytes and candidate Git objects."""
    raw_refs = c3_input.get("current_source_family_refs", {})
    if not isinstance(raw_refs, dict):
        raise RuntimeError("current source-family refs must be an object")
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
        "finding_scope_pointers",
    }
    if criterion_scoped:
        required_fields.add("criterion_scope_pointers")
    for family, ref in raw_refs.items():
        if family not in prior_families or not isinstance(ref, dict):
            raise RuntimeError(f"unknown or malformed current source-family ref: {family}")
        missing = required_fields - set(ref)
        if missing:
            raise RuntimeError(
                f"current source-family ref lacks bound proof fields: {family}: "
                + ", ".join(sorted(missing))
            )
        candidate_commit = ref["candidate_commit"]
        candidate_tree = ref["candidate_tree"]
        handoff_commit = ref["handoff_commit"]
        handoff_tree = ref["handoff_tree"]
        if git(root, "rev-parse", f"{candidate_commit}^{{tree}}") != candidate_tree:
            raise RuntimeError(f"candidate commit/tree mismatch for {family}")
        if git(root, "rev-parse", f"{handoff_commit}^{{tree}}") != handoff_tree:
            raise RuntimeError(f"handoff commit/tree mismatch for {family}")
        subprocess.run(  # noqa: S603 - trusted Git command; argv, shell disabled.
            ["git", "merge-base", "--is-ancestor", candidate_commit, handoff_commit],  # noqa: S607 - trusted Git executable.
            cwd=root,
            check=True,
            capture_output=True,
        )

        candidate_ancestors = []
        for pin in prior_families[family].get("source_pins", []):
            pin_commit = pin["commit"]
            if git(root, "rev-parse", f"{pin_commit}^{{tree}}") != pin["tree"]:
                raise RuntimeError(f"prior source pin tree mismatch for {family}")
            result = subprocess.run(  # noqa: S603 - trusted Git command; argv, shell disabled.
                ["git", "merge-base", "--is-ancestor", pin_commit, candidate_commit],  # noqa: S607 - trusted Git executable.
                cwd=root,
                check=False,
                capture_output=True,
            )
            if result.returncode == 0:
                candidate_ancestors.append(pin_commit)
        if not candidate_ancestors:
            raise RuntimeError(f"candidate is not descended from a frozen source pin: {family}")

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
            raise RuntimeError(f"source-family implementation change list is invalid: {family}")
        actual_delta_paths = set()
        for pin_commit in candidate_ancestors:
            actual_delta_paths.update(
                line
                for line in git(
                    root,
                    "diff",
                    "--name-only",
                    f"{pin_commit}..{candidate_commit}",
                ).splitlines()
                if line
            )
        if not set(changed_paths).issubset(actual_delta_paths):
            raise RuntimeError(f"source-family implementation paths are not in Git delta: {family}")

        handoff_path = Path(ref["handoff_path"])
        handoff_raw, handoff_blob = git_source_file(
            root,
            handoff_commit,
            handoff_tree,
            handoff_path.as_posix(),
            expected_sha256=ref["handoff_sha256"],
            expected_blob=ref["handoff_git_blob"],
        )
        handoff_doc = json.loads(handoff_raw)
        if (
            json_pointer_value(handoff_doc, ref["candidate_commit_pointer"]) != candidate_commit
            or json_pointer_value(handoff_doc, ref["candidate_tree_pointer"]) != candidate_tree
            or json_pointer_value(handoff_doc, ref["handoff_branch_pointer"])
            != ref["handoff_branch"]
        ):
            raise RuntimeError(f"handoff does not content-bind candidate identity: {family}")
        evidence_pointers = ref["evidence_pointers"]
        if not isinstance(evidence_pointers, list) or not evidence_pointers:
            raise RuntimeError(f"source-family handoff has no selected evidence pointers: {family}")
        for pointer in evidence_pointers:
            selected = json_pointer_value(handoff_doc, pointer)
            if selected is None or selected == "" or selected == [] or selected == {}:
                raise RuntimeError(f"source-family evidence pointer is empty: {family} {pointer}")
        source_rows = {row["id"]: row for row in c2_cut["rows"]}
        finding_scope_pointers = ref["finding_scope_pointers"]
        if criterion_scoped and finding_scope_pointers == []:
            finding_scope_ids = []
        else:
            finding_scope_ids = declared_finding_scope(
                handoff_doc, finding_scope_pointers, family, source_rows
            )

        criterion_scope_pointers = ref.get("criterion_scope_pointers", [])
        declared_criterion_scope_ids: list[str] = []
        if criterion_scoped:
            if (
                not isinstance(criterion_scope_pointers, list)
                or not criterion_scope_pointers
                or any(
                    not isinstance(pointer, str) or not pointer.startswith("/")
                    for pointer in criterion_scope_pointers
                )
                or len(criterion_scope_pointers) != len(set(criterion_scope_pointers))
            ):
                raise RuntimeError(f"current source-family criterion scope is invalid: {family}")
            family_criterion_ids = {
                item["criterion_id"]
                for row in source_rows.values()
                if row["source_family"] == family
                for item in row["criterion_refs"]
            }
            for pointer in criterion_scope_pointers:
                selected = json_pointer_value(handoff_doc, pointer)
                if not isinstance(selected, list):
                    raise RuntimeError(
                        f"criterion-scope pointer is not an array: {family} {pointer}"
                    )
                if any(not isinstance(criterion_id, str) for criterion_id in selected):
                    raise RuntimeError(
                        f"criterion-scope pointer contains a non-string ID: {family} {pointer}"
                    )
                if len(selected) != len(set(selected)):
                    raise RuntimeError(f"criterion-scope pointer repeats IDs: {family} {pointer}")
                if any(criterion_id not in family_criterion_ids for criterion_id in selected):
                    raise RuntimeError(
                        f"criterion-scope pointer names an unknown family criterion: "
                        f"{family} {pointer}"
                    )
                declared_criterion_scope_ids.extend(selected)
            if len(declared_criterion_scope_ids) != len(set(declared_criterion_scope_ids)):
                raise RuntimeError(f"current source-family criterion scopes overlap: {family}")

        verified_ref = {
            "candidate_commit": candidate_commit,
            "candidate_tree": candidate_tree,
            "handoff_commit": handoff_commit,
            "handoff_tree": handoff_tree,
            "handoff_path_at_sha256": (f"{handoff_path.as_posix()}@sha256:{ref['handoff_sha256']}"),
            "handoff_git_blob": handoff_blob,
            "implementation_changed_paths": list(changed_paths),
            "candidate_commit_pointer": ref["candidate_commit_pointer"],
            "candidate_tree_pointer": ref["candidate_tree_pointer"],
            "branch": ref["handoff_branch"],
            "head": handoff_commit,
            "tree": handoff_tree,
            "handoff_branch_pointer": ref["handoff_branch_pointer"],
            "evidence_pointers": list(evidence_pointers),
            "finding_scope_pointers": list(ref["finding_scope_pointers"]),
            "declared_finding_scope_ids": finding_scope_ids,
        }
        if criterion_scoped:
            verified_ref["criterion_scope_pointers"] = list(criterion_scope_pointers)
            verified_ref["declared_criterion_scope_ids"] = sorted(declared_criterion_scope_ids)
        verified[family] = verified_ref
    return verified


def verify_c4_current_context_updates(
    root: Path, c2_cut: dict, c4_input: dict
) -> tuple[dict, dict]:
    """Resolve current availability context from exact Git-bound sources."""
    raw_sources = c4_input.get("current_context_sources", {})
    raw_updates = c4_input.get("current_context_updates", {})
    if not isinstance(raw_sources, dict) or not isinstance(raw_updates, dict):
        raise RuntimeError("C4 context sources and updates must be objects")
    if not raw_sources or not raw_updates:
        raise RuntimeError("C4 final input requires bound current-context source updates")

    source_fields = {
        "source_commit",
        "source_tree",
        "path",
        "sha256",
        "git_blob",
        "size_bytes",
        "format",
        "role",
    }
    verified_sources = {}
    source_documents = {}
    for ref_id, source in raw_sources.items():
        if (
            not isinstance(ref_id, str)
            or not ref_id
            or not isinstance(source, dict)
            or set(source) != source_fields
        ):
            raise RuntimeError(f"malformed C4 context source declaration: {ref_id}")
        path = Path(source["path"])
        if path.is_absolute() or ".." in path.parts:
            raise RuntimeError(f"C4 context source is not repository-relative: {ref_id}")
        if source["format"] not in {"json", "text"}:
            raise RuntimeError(f"unsupported C4 context source format: {ref_id}")
        raw, blob = git_source_file(
            root,
            source["source_commit"],
            source["source_tree"],
            path.as_posix(),
            expected_sha256=source["sha256"],
            expected_blob=source["git_blob"],
            expected_size=source["size_bytes"],
        )
        if source["format"] == "json":
            document = json.loads(raw)
            if not isinstance(document, dict):
                raise RuntimeError(f"C4 context JSON source is not an object: {ref_id}")
            source_documents[ref_id] = document
        else:
            raw.decode("utf-8")
        verified_sources[ref_id] = {
            "path_at_sha256": f"{path.as_posix()}@sha256:{source['sha256']}",
            "source_commit": source["source_commit"],
            "source_tree": source["source_tree"],
            "git_blob": blob,
            "size_bytes": len(raw),
            "format": source["format"],
            "role": source["role"],
            "status": "verified_from_pinned_git_tree",
        }

    c2_rows = {row["id"]: row for row in c2_cut["rows"]}
    update_fields = {
        "source_ref_id",
        "availability_pointer",
        "missing_input_pointer",
        "remaining_verification_pointer",
        "next_owner_pointer",
        "supporting_source_ref_ids",
    }
    verified_updates = {}
    referenced_sources = set()
    for finding_id, update in raw_updates.items():
        if finding_id not in c2_rows or not isinstance(update, dict):
            raise RuntimeError(f"unknown or malformed C4 context update: {finding_id}")
        if set(update) != update_fields:
            raise RuntimeError(f"C4 context update fields differ from schema: {finding_id}")
        ref_id = update["source_ref_id"]
        document = source_documents.get(ref_id)
        if document is None:
            raise RuntimeError(f"C4 context update lacks a pinned JSON source: {finding_id}")
        pointers = {
            "availability": update["availability_pointer"],
            "missing_input": update["missing_input_pointer"],
            "remaining_verification": update["remaining_verification_pointer"],
            "next_owner": update["next_owner_pointer"],
        }
        base_pointer = f"/finding_notes/{finding_id.replace('~', '~0').replace('/', '~1')}"
        expected_pointers = {
            "availability": f"{base_pointer}/availability",
            "missing_input": f"{base_pointer}/missing_input",
            "remaining_verification": f"{base_pointer}/code_outcome",
            "next_owner": f"{base_pointer}/next_owner",
        }
        if pointers != expected_pointers:
            raise RuntimeError(
                f"C4 context field pointers do not bind the selected row: {finding_id}"
            )
        resolved = {}
        for name, pointer in pointers.items():
            value = json_pointer_value(document, pointer)
            if not isinstance(value, str) or not value.strip():
                raise RuntimeError(f"C4 context value is empty or untyped: {finding_id} {pointer}")
            resolved[name] = value
        support_ids = update["supporting_source_ref_ids"]
        if (
            not isinstance(support_ids, list)
            or any(not isinstance(ref, str) for ref in support_ids)
            or len(support_ids) != len(set(support_ids))
            or any(ref not in verified_sources for ref in support_ids)
        ):
            raise RuntimeError(f"C4 context support refs are invalid: {finding_id}")
        referenced_sources.add(ref_id)
        referenced_sources.update(support_ids)
        verified_updates[finding_id] = {
            "source_ref_id": ref_id,
            "source": verified_sources[ref_id],
            "source_pointer": base_pointer,
            "field_pointers": pointers,
            "supporting_source_ref_ids": list(support_ids),
            **resolved,
        }
    if referenced_sources != set(verified_sources):
        raise RuntimeError("C4 context source index has an unreferenced or missing source")
    return verified_sources, verified_updates


def verify_supplemental_source_handoffs(
    root: Path, c2_cut: dict, c3_input: dict
) -> tuple[list[dict], dict[str, list[str]]]:
    """Verify supplemental handoff evidence against committed source trees."""
    raw_refs = c3_input.get("supplemental_source_handoffs", [])
    if not isinstance(raw_refs, list):
        raise RuntimeError("supplemental source handoffs must be an array")
    c2_rows = {row["id"]: row for row in c2_cut["rows"]}
    verified = []
    refs_by_finding: dict[str, list[str]] = {}
    seen_refs: set[str] = set()
    for ref in raw_refs:
        if not isinstance(ref, dict):
            raise RuntimeError("supplemental source handoff entry must be an object")
        ref_id = ref.get("ref_id")
        family = ref.get("family")
        if not isinstance(ref_id, str) or not ref_id or ref_id in seen_refs:
            raise RuntimeError("supplemental source handoff ref_id is missing or duplicated")
        seen_refs.add(ref_id)
        if family not in c2_cut["topic_source_refs"]:
            raise RuntimeError(f"supplemental source handoff has unknown family: {family}")
        handoff_raw, handoff_blob = git_source_file(
            root,
            ref["source_commit"],
            ref["source_tree"],
            ref["path"],
            expected_sha256=ref["sha256"],
            expected_blob=ref["git_blob"],
            expected_size=ref.get("size_bytes"),
        )
        handoff_doc = json.loads(handoff_raw)
        finding_ids = ref.get("finding_ids")
        if not isinstance(finding_ids, list) or not finding_ids:
            raise RuntimeError(f"supplemental handoff has no finding scope: {ref_id}")
        if len(set(finding_ids)) != len(finding_ids):
            raise RuntimeError(f"supplemental handoff repeats a finding ID: {ref_id}")
        criterion_ids: set[str] = set()
        for finding_id in finding_ids:
            row = c2_rows.get(finding_id)
            if row is None or row["source_family"] != family:
                raise RuntimeError(
                    f"supplemental handoff finding is absent or outside its family: "
                    f"{ref_id} / {finding_id}"
                )
            criterion_ids.update(item["criterion_id"] for item in row["criterion_refs"])
            refs_by_finding.setdefault(finding_id, []).append(ref_id)
        declared_criteria = json_pointer_value(handoff_doc, ref["criterion_ids_pointer"])
        if (
            not isinstance(declared_criteria, list)
            or len(declared_criteria) != len(set(declared_criteria))
            or set(declared_criteria) != criterion_ids
        ):
            raise RuntimeError(
                f"supplemental handoff criterion scope differs from its findings: {ref_id}"
            )
        evidence_pointers = ref.get("evidence_pointers")
        if not isinstance(evidence_pointers, list) or not evidence_pointers:
            raise RuntimeError(f"supplemental handoff has no selected evidence: {ref_id}")
        selected_evidence_files = []
        for pointer in evidence_pointers:
            selected = json_pointer_value(handoff_doc, pointer)
            if selected is None or selected == "" or selected == [] or selected == {}:
                raise RuntimeError(f"supplemental evidence pointer is empty: {ref_id} {pointer}")
            for file_ref in nested_git_file_refs(selected):
                path = file_ref["path"]
                if Path(path).is_absolute():
                    raise RuntimeError(
                        f"selected supplemental evidence is not repository-portable: "
                        f"{ref_id} {path}"
                    )
                file_raw, file_blob = git_source_file(
                    root,
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
                        "sha256": sha256(file_raw),
                        "git_blob": file_blob,
                        "size_bytes": len(file_raw),
                    }
                )

        candidate_records = []
        candidates = ref.get("candidate_bindings")
        if not isinstance(candidates, list) or not candidates:
            raise RuntimeError(f"supplemental handoff lacks candidate bindings: {ref_id}")
        for candidate in candidates:
            commit = json_pointer_value(handoff_doc, candidate["commit_pointer"])
            tree = json_pointer_value(handoff_doc, candidate["tree_pointer"])
            if not re.fullmatch(r"[0-9a-f]{40}", commit) or not re.fullmatch(r"[0-9a-f]{40}", tree):
                raise RuntimeError(f"supplemental candidate identity is malformed: {ref_id}")
            actual_tree = git(root, "rev-parse", f"{commit}^{{tree}}")
            if actual_tree != tree:
                raise RuntimeError(f"supplemental candidate commit/tree mismatch: {ref_id}")
            ancestor = subprocess.run(  # noqa: S603 - trusted Git ancestry query; shell disabled.
                ["git", "merge-base", "--is-ancestor", commit, ref["source_commit"]],  # noqa: S607 - Git executable.
                cwd=root,
                capture_output=True,
                check=False,
            )
            if ancestor.returncode != 0:
                raise RuntimeError(f"supplemental candidate is not in handoff ancestry: {ref_id}")
            parents = git(root, "show", "-s", "--format=%P", commit).split()
            parents_pointer = candidate.get("parents_pointer")
            if parents_pointer and json_pointer_value(handoff_doc, parents_pointer) != parents:
                raise RuntimeError(f"supplemental candidate parent list mismatch: {ref_id}")
            source_files = []
            for pointer in candidate.get("source_file_pointers", []):
                file_ref = json_pointer_value(handoff_doc, pointer)
                if not isinstance(file_ref, dict):
                    raise RuntimeError(
                        f"supplemental source-file pointer is not an object: {ref_id} {pointer}"
                    )
                if file_ref.get("commit") != commit:
                    raise RuntimeError(
                        f"supplemental source-file commit differs from candidate: {ref_id}"
                    )
                file_raw, file_blob = git_source_file(
                    root,
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
                        "sha256": sha256(file_raw),
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


def nested_git_file_refs(value: object) -> list[dict]:
    """Find declared relative path/SHA objects inside selected evidence only."""
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


def tsv_rows(raw: bytes) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(raw.decode("utf-8")), delimiter="\t"))


def portable_receipt_index(root: Path, c2_cut: dict, c2_source: dict, c3_input: dict) -> list[dict]:
    c2_index = c2_cut["receipt_index"]
    result = []
    seen_ids = set()
    for binding in c3_input.get("portable_receipt_bindings", []):
        receipt_id = binding["receipt_id"]
        source_receipt = c2_index.get(receipt_id)
        if source_receipt is None or receipt_id in seen_ids:
            raise RuntimeError(f"portable receipt is missing or duplicated: {receipt_id}")
        seen_ids.add(receipt_id)
        if (
            source_receipt.get("path_at_sha256") != binding["historical_path_at_sha256"]
            or source_receipt.get("sha256") != binding["sha256"]
            or source_receipt.get("size_bytes") != binding["size_bytes"]
            or source_receipt.get("head")
        ):
            raise RuntimeError(
                f"portable receipt does not match the historical source record: {receipt_id}"
            )

        relative_path = Path(binding["portable_path"])
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise RuntimeError(f"portable receipt path must stay in the repository: {receipt_id}")
        source_path = binding.get("source_path")
        if source_path != relative_path.as_posix():
            raise RuntimeError(
                f"portable receipt source path differs from its indexed path: {receipt_id}"
            )
        raw, blob = git_source_file(
            root,
            binding["source_commit"],
            binding["source_tree"],
            source_path,
            expected_sha256=binding["sha256"],
            expected_blob=binding["source_git_blob"],
            expected_size=binding["size_bytes"],
        )
        digest = sha256(raw)
        result.append(
            {
                "receipt_id": receipt_id,
                "historical_path_at_sha256": source_receipt["path_at_sha256"],
                "historical_source_status": "verification_missing",
                "path_at_sha256": f"{relative_path.as_posix()}@sha256:{digest}",
                "git_blob": blob,
                "source_commit": binding["source_commit"],
                "source_tree": binding["source_tree"],
                "size_bytes": len(raw),
                "current_content_status": "verified_from_pinned_git_tree",
                "role": binding["role"],
            }
        )
    required_ids = required_portable_receipt_ids(root, c2_cut, c2_source)
    missing_ids = required_ids - seen_ids
    if missing_ids:
        raise RuntimeError(
            "portable companion bindings omit historical local-only receipts: "
            + ", ".join(sorted(missing_ids))
        )
    return result


def historical_local_only_receipts(
    root: Path, c2_cut: dict, c2_source: dict, portable: list[dict]
) -> list[dict]:
    portable_by_id = {receipt["receipt_id"]: receipt for receipt in portable}
    result = []
    for receipt_id, receipt in c2_cut["receipt_index"].items():
        if receipt.get("head"):
            continue
        path = receipt["path_at_sha256"].rsplit("@sha256:", 1)[0]
        if git_path_exists(root, c2_source["commit"], path):
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


def build_c3(root: Path, json_path: Path, markdown_path: Path, input_path: Path) -> dict:
    input_raw = input_path.read_bytes()
    c3_input = json.loads(input_raw)
    c3_schema = c3_input.get("schema")
    c4_mode = c3_schema == C4_FINAL_INPUT_SCHEMA
    cycle_label = "C4" if c4_mode else "C3"
    final_mode = c3_schema in {C3_FINAL_INPUT_SCHEMA, C4_FINAL_INPUT_SCHEMA}
    if c3_schema not in {
        "policyos.e02.c54.c3.current-evaluation-input.v2",
        C3_FINAL_INPUT_SCHEMA,
        C4_FINAL_INPUT_SCHEMA,
    }:
        raise RuntimeError(f"{cycle_label} current-evaluation input schema mismatch")

    base = c3_input["base"]
    c2_source = c3_input["c2_source"]
    g_snapshot = c3_input["g_snapshot"]
    for commit, expected_tree, label in (
        (base["commit"], base["tree"], "base"),
        (c2_source["commit"], c2_source["tree"], "C2 source"),
        (g_snapshot["commit"], g_snapshot["tree"], "G source"),
    ):
        actual_tree = git(root, "rev-parse", f"{commit}^{{tree}}")
        if actual_tree != expected_tree:
            raise RuntimeError(f"pinned {label} tree changed: {actual_tree} != {expected_tree}")
    git(root, "merge-base", "--is-ancestor", base["commit"], c2_source["commit"])

    c2_raw = git_bytes(root, f"{c2_source['commit']}:{c2_source['path']}")
    if (
        sha256(c2_raw) != C2_C3_SOURCE_SHA256
        or c2_source["sha256"] != C2_C3_SOURCE_SHA256
        or git(root, "rev-parse", f"{c2_source['commit']}:{c2_source['path']}") != C2_C3_SOURCE_BLOB
        or c2_source["git_blob"] != C2_C3_SOURCE_BLOB
    ):
        raise RuntimeError("pinned C2 v10 source changed")
    c2_cut = json.loads(c2_raw)
    if (
        c2_cut["base"] != base
        or c2_cut["snapshot"]["commit"] != "48af851db5c0e802c92d9b30226acbc4436c69ba"
    ):
        raise RuntimeError("C2 source cut is not the expected frozen C2 adjudication")
    verified_current_families = verify_current_source_family_refs(
        root, c2_cut, c3_input, criterion_scoped=c4_mode
    )
    verified_context_sources, verified_context_updates = (
        verify_c4_current_context_updates(root, c2_cut, c3_input) if c4_mode else ({}, {})
    )
    supplemental_handoffs, supplemental_by_finding = verify_supplemental_source_handoffs(
        root, c2_cut, c3_input
    )
    if final_mode:
        required_refresh_families = set(c3_input["family_refresh_states"]) - {"default"}
        missing_refresh_families = required_refresh_families - set(verified_current_families)
        if missing_refresh_families:
            raise RuntimeError(
                f"final {cycle_label} input lacks verified source handoffs for refresh families: "
                + ", ".join(sorted(missing_refresh_families))
            )
    portable_index = portable_receipt_index(root, c2_cut, c2_source, c3_input)
    historical_local_only = historical_local_only_receipts(root, c2_cut, c2_source, portable_index)

    g_inputs: dict[str, dict] = {}
    for name, ref in c3_input["g_inputs"].items():
        raw = git_bytes(root, f"{g_snapshot['commit']}:{ref['path']}")
        blob = git(root, "rev-parse", f"{g_snapshot['commit']}:{ref['path']}")
        if len(raw) != ref["bytes"] or sha256(raw) != ref["sha256"] or blob != ref["git_blob"]:
            raise RuntimeError(f"pinned G input changed: {name}")
        g_inputs[name] = {**ref, "source_commit": g_snapshot["commit"]}
    coverage = json.loads(git_bytes(root, f"{g_snapshot['commit']}:{G_C3_COVERAGE_PATH}"))
    allocation = json.loads(
        git_bytes(
            root,
            f"{g_snapshot['commit']}:policy-engine/docs/research/e02-cloud-test-plan/execution-organization/allocation.json",
        )
    )
    g_findings = {row["id"]: row for row in coverage["findings"] if row["unit"] == "C"}
    c2_rows = {row["id"]: row for row in c2_cut["rows"]}
    if len(c2_rows) != 54 or set(c2_rows) != set(g_findings):
        raise RuntimeError("C2/G C-finding denominator or ID set differs")
    if allocation.get("schema") is None:
        raise RuntimeError("pinned G allocation document has no schema")
    owner_rows = tsv_rows(git_bytes(root, f"{g_snapshot['commit']}:{G_C3_FINDING_OWNERS_PATH}"))
    bundle_rows = tsv_rows(git_bytes(root, f"{g_snapshot['commit']}:{G_C3_BUNDLE_OWNERS_PATH}"))
    finding_owners = {row["finding_id"]: row for row in owner_rows}
    bundle_owners = {row["bundle_id"]: row for row in bundle_rows}
    if set(finding_owners) != {row["id"] for row in coverage["findings"]}:
        raise RuntimeError("G finding-owner TSV denominator mismatch")
    c_md_labels = {}
    if c4_mode:
        closure_c_path = c3_input["g_inputs"]["closure_c"]["path"]
        c_md_labels = parse_c_md_labels(git_bytes(root, f"{g_snapshot['commit']}:{closure_c_path}"))
        if set(c_md_labels) != set(g_findings):
            raise RuntimeError("pinned G C.md label rows differ from coverage findings")

    denominator = {
        "all_bundles": len(coverage["bundles"]),
        "all_findings": len(coverage["findings"]),
        "canonical_criterion_occurrences": coverage["denominator"][
            "canonical_source_block_occurrences"
        ],
        "C_bundles": len({row["id"] for row in coverage["bundles"] if row["unit"] == "C"}),
        "C_findings": len(g_findings),
        "C_hash_bound_criteria": sum(
            len(row.get("criterion_refs", [])) for row in g_findings.values()
        ),
    }
    expected_denominator = {
        "all_bundles": 127,
        "all_findings": 282,
        "canonical_criterion_occurrences": 291,
        "C_bundles": 33,
        "C_findings": 54,
        "C_hash_bound_criteria": 59,
    }
    if denominator != expected_denominator:
        raise RuntimeError(f"{cycle_label} denominator changed: {denominator}")

    source_families_full = c2_cut["topic_source_refs"]
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
        for family, source_ref in source_families_full.items()
    }
    if c4_mode:
        for _family, source_ref in source_families.items():
            receipt = c2_cut["receipt_index"].get(source_ref.get("handoff_receipt_id"), {})
            source_ref["prior_handoff_path_at_sha256"] = receipt.get("path_at_sha256")
            source_ref["prior_handoff_sha256"] = receipt.get("sha256")
    family_states = c3_input["family_refresh_states"]
    overrides = c3_input["row_overrides"]
    row_ids = set(c2_rows)
    if not set(overrides).issubset(row_ids):
        raise RuntimeError(f"{cycle_label} input contains an unknown row override")

    rows = []
    c2_row_indexes = {row["id"]: index for index, row in enumerate(c2_cut["rows"])}
    for finding_id in sorted(
        c2_rows,
        key=lambda item: (
            item.startswith("LA-"),
            int(item[3:]) if item.startswith("LA-") else int(item[1:]),
        ),
    ):
        c2 = c2_rows[finding_id]
        g = g_findings[finding_id]
        owner = finding_owners[finding_id]
        source_family = c2["source_family"]
        if source_family not in source_families:
            raise RuntimeError(
                f"C2 source family is missing a topic pin: {finding_id} / {source_family}"
            )
        override = overrides.get(finding_id, {})
        family_state_key = source_family if source_family in family_states else "default"
        state = derive_c3_evidence_state(
            finding_id,
            source_family,
            c3_input,
            verified_current_families,
            supplemental_by_finding,
            cycle_label,
            criterion_scoped=c4_mode,
            row_criterion_ids=[item["criterion_id"] for item in c2["criterion_refs"]],
        )
        row_criterion_ids = [item["criterion_id"] for item in c2["criterion_refs"]]
        scope_source = c3_evidence_scope_source(
            finding_id,
            source_family,
            verified_current_families,
            supplemental_by_finding,
            row_criterion_ids,
            criterion_scoped=c4_mode,
        )
        c2_row_index = c2_row_indexes[finding_id]
        code_outcome = override.get("code_outcome")
        evidence_refs = override.get("evidence_refs", [])
        evidence_ref_source_pointer = (
            None if evidence_refs else f"/rows/{c2_row_index}/deciding_receipts"
        )
        code_outcome_source_pointer = None if code_outcome else f"/rows/{c2_row_index}/code_outcome"
        if not evidence_refs and not evidence_ref_source_pointer:
            raise RuntimeError(f"current evaluation has no evidence references: {finding_id}")

        c2_criteria = [
            (
                item["criterion_id"],
                item["document_ref"],
                item["line_span"],
                item["criterion_sha256"],
            )
            for item in c2["criterion_refs"]
        ]
        g_doc_map = {"B_r19": "CD01", "LA_r09": "CD02"}
        g_criteria = [
            (
                item["criterion_id"],
                g_doc_map[item["document"]],
                f"{item['lines'][0]}-{item['lines'][1]}",
                item["sha256"],
            )
            for item in g.get("criterion_refs", [])
        ]
        if sorted(c2_criteria) != sorted(g_criteria):
            raise RuntimeError(f"C2/G original criterion binding differs: {finding_id}")
        if set(c2["bundles"]) != set(g["companion_bundles"]):
            raise RuntimeError(f"C2/G companion bundle binding differs: {finding_id}")

        if c4_mode and final_mode:
            remaining = override.get("remaining_work", {})
        else:
            remaining = override.get(
                "remaining_work",
                {
                    "mechanism": {
                        "status": f"not_reassessed_in_{cycle_label}",
                        "note_ref": f"status_semantics/{cycle_label.lower()}_current_evaluation",
                    },
                    "verification": {
                        "status": "source_refresh_pending"
                        if state == f"{cycle_label.lower()}_source_refresh_pending"
                        else "carried_from_C2_handoff",
                        "source_pointer": f"/rows/{c2_row_index}/remaining_verification",
                    },
                    "input": {
                        "status": "carried_from_C2_handoff",
                        "source_pointer": f"/rows/{c2_row_index}/missing_inputs_or_skipped_backend",
                    },
                    "decision": {
                        "status": "carried_from_C2_handoff",
                        "source_pointer": f"/rows/{c2_row_index}/next_owner",
                    },
                },
            )
        current = {
            "state": state,
            "state_note": c3_evidence_state_note(
                state,
                source_family,
                scope_source,
                source_family in verified_current_families,
                cycle_label,
            ),
            "state_note_source_pointer": c3_evidence_state_pointer(
                finding_id,
                source_family,
                state,
                family_state_key,
                c3_input,
                verified_current_families,
                supplemental_by_finding,
                row_criterion_ids,
                criterion_scoped=c4_mode,
            ),
            "source_family_version_binding": source_family_version_binding(
                finding_id,
                source_family,
                verified_current_families,
                row_criterion_ids,
                criterion_scoped=c4_mode,
            ),
            "code_outcome": code_outcome,
            "code_outcome_source_pointer": code_outcome_source_pointer,
            "evidence_refs": evidence_refs,
            "evidence_ref_source_pointer": evidence_ref_source_pointer,
            "source_family": source_family,
            "source_family_ref_key": source_family,
            "remaining_work": override.get("remaining_work", remaining),
            "tree_path_checks": override.get("git_tree_path_checks", []),
            "supplemental_evidence_refs": supplemental_by_finding.get(finding_id, []),
        }
        if c4_mode:
            current["current_context_update"] = verified_context_updates.get(finding_id)
        g_current = {
            "unit": g["unit"],
            "formal_status": g["closure_now"],
            "capability_label": (
                g.get("capability_label") if c4_mode else g.get("capability_label") or ""
            ),
            "canonical_source_owner": owner["source_closure_owner"],
            "source_owner_bundle_ids": owner["source_bundle_ids"].split(";"),
            "primary_bundle": g["primary_bundle"],
            "companion_bundles": list(g["companion_bundles"]),
        }
        if c4_mode:
            coverage_label = g.get("capability_label")
            c_md_status, c_md_label = c_md_labels[finding_id]
            if coverage_label in (None, "") and c_md_label == "":
                label_state = "historical_source_label_empty"
                label_note = (
                    "Both pinned G source views leave the capability label empty. The C4 row "
                    "preserves those raw values and does not infer a replacement label."
                )
            elif coverage_label != c_md_label:
                label_state = "pinned_source_label_disagreement"
                label_note = (
                    "Pinned coverage.json and C.md provide different capability labels; both "
                    "source values are retained without choosing one as authoritative."
                )
            else:
                label_state = "pinned_source_labels_match"
                label_note = None
            g_current.update(
                {
                    "task_refs": list(g.get("task_refs", [])),
                    "coverage_capability_label": coverage_label,
                    "c_md_status_label": c_md_status,
                    "c_md_capability_label": c_md_label,
                    "capability_label_source_state": label_state,
                    "capability_label_source_note": label_note,
                }
            )
            if label_state == "historical_source_label_empty":
                current["capability_label_assessment"] = {
                    "status": "whole_capability_label_not_inferred",
                    "source_state": label_state,
                    "reason": (
                        "The C4 disposition applies to the cited finite criterion. Neither G "
                        "source view supplies a whole-capability label, so this criterion result "
                        "does not synthesize one."
                    ),
                }
        rows.append(
            {
                "id": finding_id,
                "bundles": list(c2["bundles"]),
                "criterion_refs": c2["criterion_refs"],
                "historical_status": c2["historical_status"],
                "source_family": source_family,
                "c2_snapshot": {
                    "source_row_index": c2_row_index,
                    "capability_label": c2["capability_label"],
                    "code_outcome_source_pointer": f"/rows/{c2_row_index}/code_outcome",
                    "deciding_receipts_source_pointer": f"/rows/{c2_row_index}/deciding_receipts",
                    "root_verdict": {
                        "value": c2["root_finding_verdict"]["value"],
                        "status": c2["root_finding_verdict"]["status"],
                    },
                    "root_verdict_source_pointer": f"/rows/{c2_row_index}/root_finding_verdict",
                },
                "g_current": g_current,
                "current_evaluation": current,
            }
        )

    criterion_document_index = c2_cut["criterion_document_index"]
    if c4_mode:
        criterion_document_index = bind_original_criterion_text(root, base, c2_cut, rows)

    if any(row["g_current"]["formal_status"] != "not_adjudicated" for row in rows):
        raise RuntimeError(
            f"unexpected G formal disposition; {cycle_label} input requires root review before "
            "updating this crosswalk"
        )

    c_bundle_rows = {item["id"]: item for item in coverage["bundles"] if item["unit"] == "C"}
    c_bundle_ids = {bundle for row in rows for bundle in row["bundles"]}
    if c_bundle_ids != set(c_bundle_rows):
        raise RuntimeError("C bundle union differs from G coverage")
    bundle_crosswalk = []
    for bundle_id in sorted(c_bundle_ids):
        g_bundle = c_bundle_rows[bundle_id]
        owner_item = bundle_owners.get(bundle_id)
        if owner_item is None:
            raise RuntimeError(f"G bundle-owner table is missing {bundle_id}")
        member_rows = [row for row in rows if bundle_id in row["bundles"]]
        bundle_crosswalk.append(
            {
                "bundle_id": bundle_id,
                "g_unit": g_bundle["unit"],
                "initial_writer_family": owner_item["initial_writer_family"],
                "c_finding_ids": [row["id"] for row in member_rows],
                "c_source_families": sorted({row["source_family"] for row in member_rows}),
                "g_source_closure_owners": sorted(
                    {row["g_current"]["canonical_source_owner"] for row in member_rows}
                ),
            }
        )

    c2_verdict_counts = Counter(row["c2_snapshot"]["root_verdict"]["value"] for row in rows)
    if c2_verdict_counts != Counter({"closed": 31, "limited": 9, "held": 14}):
        raise RuntimeError(f"frozen C2 verdict distribution changed: {dict(c2_verdict_counts)}")
    g_formal_status_counts = dict(
        sorted(Counter(row["g_current"]["formal_status"] for row in rows).items())
    )
    evaluation_counts = dict(
        sorted(Counter(row["current_evaluation"]["state"] for row in rows).items())
    )
    input_key = f"{cycle_label.lower()}_input"
    cut = {
        "schema": (
            C4_FINAL_CUT_SCHEMA if c4_mode else "policyos.e02.c54.c3.current-evidence-census.v2"
        ),
        "artifact": (
            f"C54 {cycle_label} current root-adjudicated criterion evaluation"
            if final_mode
            else f"C54 {cycle_label} current-evidence census; no {cycle_label} verdict assigned"
        ),
        "status": (
            f"{cycle_label.lower()}_current_root_adjudicated"
            if final_mode
            else "c3_current_evidence_crosswalk_not_adjudication"
        ),
        "final_verdicts_assigned": False,
        "status_semantics": c3_input["status_semantics"],
        "baseline_use_limit": c2_cut["baseline_use_limit"],
        "base": base,
        "c2_source": {**c2_source, "bytes": len(c2_raw)},
        "c2_adjudication_snapshot": {
            "snapshot": c2_cut["snapshot"],
            "status": c2_cut["status"],
            "final_verdicts_assigned": c2_cut["final_verdicts_assigned"],
            "counts_derived_from_54_rows": dict(sorted(c2_verdict_counts.items())),
            "receipt_index_entries": len(c2_cut["receipt_index"]),
            "pointer_count": c2_cut["pointer_validation"]["resolved_pointer_count"],
        },
        "g_snapshot": g_snapshot,
        "g_input_refs": g_inputs,
        "coverage_denominator": denominator,
        "g_formal_status_counts": g_formal_status_counts,
        "c2_root_verdict_counts_derived_from_all_54_rows": dict(sorted(c2_verdict_counts.items())),
        "current_evaluation_state_counts_derived_from_all_54_rows": evaluation_counts,
        "topic_source_refs": source_families,
        "current_source_family_refs": verified_current_families,
        "supplemental_source_handoffs": supplemental_handoffs,
        **({"current_context_sources": verified_context_sources} if c4_mode else {}),
        "bundle_crosswalk": bundle_crosswalk,
        "historical_local_only_receipts": historical_local_only,
        "portable_receipt_index": portable_index,
        "criterion_document_index": criterion_document_index,
        input_key: {
            "path": str(input_path.relative_to(root)),
            "sha256": sha256(input_raw),
            "bytes": len(input_raw),
            "schema": c3_input["schema"],
        },
        "pointer_validation": {
            "standard": "RFC 6901",
            "C2_frozen_rows_resolved_by_source_validator": c2_cut["pointer_validation"][
                "resolved_pointer_count"
            ],
            (
                "C4_explicit_receipt_pointer_count"
                if c4_mode
                else "C3_explicit_receipt_pointer_count"
            ): sum(
                len(ref["json_pointers"])
                for row in rows
                for ref in row["current_evaluation"]["evidence_refs"]
            ),
            "tree_path_query_count": sum(
                len(row["current_evaluation"]["tree_path_checks"]) for row in rows
            ),
            "supplemental_source_handoff_count": len(supplemental_handoffs),
            "supplemental_candidate_binding_count": sum(
                len(item["candidate_bindings"]) for item in supplemental_handoffs
            ),
            "supplemental_selected_file_reference_occurrences": sum(
                len(item["selected_evidence_files"])
                + sum(len(candidate["source_files"]) for candidate in item["candidate_bindings"])
                for item in supplemental_handoffs
            ),
        },
        "rows": rows,
    }
    if final_mode:
        cut = apply_c3_root_adjudications(
            cut, c2_cut, c3_input, verified_current_families, cycle_label
        )
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(cut, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(
        render_c3_markdown(cut, c2_cut, c3_input, cycle_label), encoding="utf-8"
    )
    result = {
        "json_path": str(json_path.relative_to(root)),
        "json_sha256": sha256(json_path.read_bytes()),
        "json_bytes": json_path.stat().st_size,
        "markdown_path": str(markdown_path.relative_to(root)),
        "markdown_sha256": sha256(markdown_path.read_bytes()),
        "markdown_bytes": markdown_path.stat().st_size,
        "rows": len(rows),
        "criterion_occurrences": sum(len(row["criterion_refs"]) for row in rows),
        "bundles": len(c_bundle_ids),
        "g_formal_status_counts": g_formal_status_counts,
        "current_evaluation_state_counts": cut[
            "current_evaluation_state_counts_derived_from_all_54_rows"
        ],
        "c2_root_verdict_counts_context_only": dict(sorted(c2_verdict_counts.items())),
    }
    if final_mode:
        result["current_root_verdict_counts"] = cut[
            "current_root_verdict_counts_derived_from_all_54_rows"
        ]
        result["final_verdicts_assigned"] = True
    return result


def render_c5_markdown(cut: dict) -> str:
    """Render a compact, source-linked 54-row current C/G disposition."""
    denominator = cut["coverage_denominator"]
    c4_counts = cut["c4_recommendation_counts_derived_from_all_54_rows"]
    current_counts = cut["current_root_verdict_counts_derived_from_all_54_rows"]
    assigned = cut["c5_verdicts_assigned"]
    root_decision = cut["root_adjudication"]
    lines = [
        "# C54 current C/G dispositions",
        "",
        (
            "This C5 view keeps C4 recommendations and historical status separate from the "
            "current C5 root disposition. Each C5 override is bound to a committed root "
            "decision source and its evidence pointers; unoverridden rows retain their C4 "
            "recommendation as directed by the root input. G formal status remains "
            "`not_adjudicated` for every row. Original criterion wording is resolved through "
            "the exact C4 source pointers in "
            "each row; the wording is not copied into this compact view."
        ),
        "",
        (
            f"C4 source: `{cut['c4_source']['commit']}` / tree "
            f"`{cut['c4_source']['tree']}`; G source: `{cut['g_snapshot']['commit']}` / tree "
            f"`{cut['g_snapshot']['tree']}`; criterion baseline: "
            f"`{cut['base']['commit']}` / tree `{cut['base']['tree']}`."
        ),
        "",
        (
            f"Pinned denominators: {denominator['all_bundles']} bundles, "
            f"{denominator['all_findings']} findings, "
            f"{denominator['canonical_criterion_occurrences']} criterion occurrences; "
            f"C has {denominator['C_bundles']} bundles, {denominator['C_findings']} findings, "
            f"and {denominator['C_hash_bound_criteria']} hash-bound criterion occurrences."
        ),
        "",
        (
            f"C4 recommendations across all 54 rows: {c4_counts.get('closed', 0)} closed, "
            f"{c4_counts.get('limited', 0)} limited, {c4_counts.get('held', 0)} held. "
            f"Current C5 root dispositions: {current_counts.get('closed', 0)} closed, "
            f"{current_counts.get('limited', 0)} limited, {current_counts.get('held', 0)} held. "
            f"Root disposition assigned: {str(assigned).lower()}. G formal status: "
            "54 not_adjudicated. These are separate fields and separate authorities."
        ),
        *(
            [
                "",
                (
                    f"Root carry-forward basis: `{root_decision['carry_forward_basis']}`. "
                    f"{markdown_cell(root_decision['carry_forward_reason'])}"
                ),
            ]
            if assigned
            else []
        ),
        "",
        (
            "| ID | Bundles and original criteria (source pointers) | Historical status | "
            "C4 recommendation / basis | Current C5 root disposition / basis | "
            "Current C code outcome and proven scope | "
            "Missing input / remaining verification | C next action / owner | "
            "G formal status / capability labels / owner | G execution action / owner | "
            "Deciding evidence source |"
        ),
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in cut["rows"]:
        criteria = "<br>".join(
            f"{item['criterion_id']} {item['document_ref']} L{item['line_span']} "
            f"`{item['criterion_sha256']}`<br>wording="
            f"`{item['wording_source']['commit']}:{item['wording_source']['path']}"
            f"#{item['wording_source']['json_pointer']}`"
            for item in row["original_criteria"]
        )
        historical = "; ".join(f"{key}={value}" for key, value in row["historical_status"].items())
        c_eval = row["current_c_evaluation"]
        g = row["g_current"]
        evidence = (
            f"C4 `{row['source_refs']['c4_evaluation_pointer']}`; "
            f"C4 history `{row['source_refs']['c4_historical_status_pointer']}`; "
            f"C2 receipts `{row['source_refs']['c2_receipts_pointer']}`; "
            f"G coverage `{row['source_refs']['g_coverage_pointer']}`; "
            f"G decisions `{row['source_refs']['g_decision_pointer']}`"
        )
        if row["current_root_verdict"].get("decision_source"):
            decision_source = row["current_root_verdict"]["decision_source"]
            evidence += (
                f"; C5 decision `{decision_source['commit']}:{decision_source['path']}"
                f"#{decision_source['json_pointer']}`"
            )
        evidence_refs = row["current_root_verdict"]["evidence_refs"]
        if evidence_refs:
            evidence += "<br>" + "; ".join(
                f"{ref['source_id']} `{ref['path']}@{ref['sha256']}#{ref['json_pointer']}`"
                for ref in evidence_refs
            )
        elif row["current_root_verdict"].get("root_review_source_pointer"):
            carry_source = root_decision["carry_forward_source"]
            evidence += (
                f"; C5 carry-forward `{carry_source['path']}@{carry_source['sha256']}"
                f"#{carry_source['json_pointer']}`"
            )
        recommendation = row["c_recommendation"]
        current_verdict = row["current_root_verdict"]
        cells = [
            row["id"],
            markdown_cell(row["bundles"]) + "<br>" + criteria,
            markdown_cell(historical),
            f"**{recommendation['value'].upper()}**<br>"
            f"{markdown_cell(recommendation['basis'])}<br>"
            f"{markdown_cell(recommendation['reason'])}",
            f"**{current_verdict['value'].upper()}**<br>"
            f"{markdown_cell(current_verdict['basis'])}<br>"
            f"{markdown_cell(current_verdict['reason'])}<br>"
            f"{markdown_cell(current_verdict['status'])}",
            f"{markdown_cell(c_eval['code_outcome'])}<br>"
            f"Proven scope: {markdown_cell(c_eval['scoped_proven_part'])}",
            f"{markdown_cell(c_eval['missing_input'])}<br>"
            f"Remaining: {markdown_cell(c_eval['remaining_verification'])}",
            f"{markdown_cell(c_eval['next_action'])}<br>Owner: "
            f"{markdown_cell(c_eval['next_owner'])}",
            f"{markdown_cell(g['formal_status'])}<br>coverage=`"
            f"{markdown_cell(g['coverage_capability_label'])}` / C.md=`"
            f"{markdown_cell(g['c_md_capability_label'])}`<br>"
            f"{markdown_cell(g['canonical_source_owner'])}",
            f"{markdown_cell(row['g_action']['execution_action'])}<br>Owner: "
            f"{markdown_cell(row['g_action']['next_owner'])}",
            markdown_cell(evidence),
        ]
        lines.append("| " + " | ".join(cells) + " |")
    lines.extend(
        [
            "",
            "## Source and authority notes",
            "",
            (
                "Historical status is copied from the C4 row and the current pinned coverage "
                "fields are shown separately. Empty or disagreeing capability labels remain "
                "explicit source values. C4 recommendations are preserved as a separate "
                "historical decision layer. Current C5 decisions are read from the pinned root "
                "input and do not assign G closure or claim product-level acceptance. G's "
                "`not_adjudicated` value is read from the pinned coverage and decisions inputs, "
                "not inferred from the C count."
            ),
            "",
            (
                "Each criterion pointer resolves to full wording in the pinned C4 JSON, and the "
                "criterion ID, document, inclusive source span, and SHA-256 are independently "
                "reconciled with the base coverage and source document. Evidence pointers resolve "
                "through the cited C4 row and C2 receipt source."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def c5_root_decisions(root: Path, root_record: dict, finding_ids: set[str]) -> dict:
    """Resolve root C5 decisions and their evidence only from pinned Git sources."""
    if root_record.get("authority") != "root":
        raise RuntimeError("C5 current decision authority must be root")
    status = root_record.get("status")
    if status not in {"draft", "final_root_adjudication"}:
        raise RuntimeError("C5 root decision status is invalid")
    raw_sources = root_record.get("sources", {})
    raw_overrides = root_record.get("overrides", {})
    if not isinstance(raw_sources, dict) or not isinstance(raw_overrides, dict):
        raise RuntimeError("C5 root sources and overrides must be mappings")
    if not set(raw_overrides).issubset(finding_ids):
        raise RuntimeError("C5 root override names a finding outside the complete C set")
    if status == "final_root_adjudication" and (
        not root_record.get("carry_forward_basis") or not root_record.get("carry_forward_reason")
    ):
        raise RuntimeError("final C5 root adjudication needs a carry-forward basis and reason")
    carry_binding = root_record.get("carry_forward_source")
    decision_scope_binding = root_record.get("decision_scope_source")
    if status == "final_root_adjudication" and (
        not isinstance(carry_binding, dict)
        or set(carry_binding) != {"source_id", "json_pointer"}
        or carry_binding.get("source_id") not in raw_sources
    ):
        raise RuntimeError("final C5 root adjudication needs a pinned carry-forward source")
    if status == "final_root_adjudication" and (
        not isinstance(decision_scope_binding, dict)
        or set(decision_scope_binding) != {"source_id", "json_pointer"}
        or decision_scope_binding.get("source_id") not in raw_sources
    ):
        raise RuntimeError("final C5 root adjudication needs a pinned decision-scope source")

    source_docs: dict[str, object] = {}
    source_refs: dict[str, dict] = {}
    for source_id, source_ref in raw_sources.items():
        if not isinstance(source_ref, dict):
            raise RuntimeError(f"C5 root source reference is malformed: {source_id}")
        required = {"commit", "tree", "path", "git_blob", "sha256", "bytes"}
        if set(source_ref) != required:
            raise RuntimeError(f"C5 root source locator fields differ from schema: {source_id}")
        source_raw, source_blob = git_source_file(
            root,
            source_ref["commit"],
            source_ref["tree"],
            source_ref["path"],
            expected_sha256=source_ref["sha256"],
            expected_blob=source_ref["git_blob"],
            expected_size=source_ref["bytes"],
        )
        try:
            source_docs[source_id] = json.loads(source_raw)
        except json.JSONDecodeError as error:
            raise RuntimeError(f"C5 root source is not JSON: {source_id}") from error
        source_refs[source_id] = {**source_ref, "git_blob": source_blob}

    valid_values = {"closed", "limited", "held"}
    required_decision_fields = {
        "value",
        "basis",
        "reason",
        "code_outcome",
        "scoped_proven_part",
        "missing_input",
        "remaining_verification",
        "next_action",
        "next_owner",
        "evidence_refs",
    }
    decisions: dict[str, dict] = {}
    for finding_id, binding in raw_overrides.items():
        if not isinstance(binding, dict) or set(binding) != {"source_id", "json_pointer"}:
            raise RuntimeError(f"C5 root override binding is malformed: {finding_id}")
        source_id = binding["source_id"]
        if source_id not in source_docs:
            raise RuntimeError(f"C5 root override references an unknown source: {finding_id}")
        pointer = binding["json_pointer"]
        decision = json_pointer_value(source_docs[source_id], pointer)
        if not isinstance(decision, dict) or not required_decision_fields.issubset(decision):
            raise RuntimeError(f"C5 root decision object is incomplete: {finding_id}")
        source_finding_id = decision.get("finding_id", decision.get("id"))
        pointer_key = pointer.rsplit("/", 1)[-1]
        if source_finding_id is not None:
            if source_finding_id != finding_id:
                raise RuntimeError(
                    f"C5 root decision source identifies another finding: {finding_id}"
                )
        elif pointer_key != finding_id:
            raise RuntimeError(
                f"C5 root decision source does not bind its finding ID: {finding_id}"
            )
        if decision["value"] not in valid_values:
            raise RuntimeError(f"C5 root decision value is invalid: {finding_id}")
        for field in required_decision_fields - {"value", "evidence_refs"}:
            if not isinstance(decision[field], str) or not decision[field].strip():
                raise RuntimeError(f"C5 root decision field {field} is empty: {finding_id}")
        if not isinstance(decision["evidence_refs"], list) or not decision["evidence_refs"]:
            raise RuntimeError(f"C5 root decision lacks evidence pointers: {finding_id}")
        evidence_refs = []
        for evidence_ref in decision["evidence_refs"]:
            if (
                not isinstance(evidence_ref, dict)
                or set(evidence_ref) != {"source_id", "json_pointer"}
                or evidence_ref["source_id"] not in source_docs
            ):
                raise RuntimeError(f"C5 decision evidence reference is malformed: {finding_id}")
            evidence_source_id = evidence_ref["source_id"]
            evidence_pointer = evidence_ref["json_pointer"]
            evidence_value = json_pointer_value(source_docs[evidence_source_id], evidence_pointer)
            if evidence_value in (None, "", [], {}):
                raise RuntimeError(f"C5 decision evidence pointer resolves empty: {finding_id}")
            evidence_refs.append(
                {
                    "source_id": evidence_source_id,
                    **source_refs[evidence_source_id],
                    "json_pointer": evidence_pointer,
                }
            )
        decisions[finding_id] = {
            **decision,
            "source_binding": {
                "source_id": source_id,
                **source_refs[source_id],
                "json_pointer": pointer,
            },
            "evidence_refs": evidence_refs,
        }
    carry_forward_source = None
    carry_forward_finding_ids: list[str] = []
    decision_scope_source = None
    decision_scope_finding_ids: list[str] = []
    if status == "final_root_adjudication":
        scope_source_id = decision_scope_binding["source_id"]
        scope_pointer = decision_scope_binding["json_pointer"]
        scope_value = json_pointer_value(source_docs[scope_source_id], scope_pointer)
        if not isinstance(scope_value, list) or any(
            not isinstance(item, dict) for item in scope_value
        ):
            raise RuntimeError("C5 decision-scope source must resolve to a list of decision rows")
        for index, decision_row in enumerate(scope_value):
            scope_finding_id = decision_row.get("finding_id", decision_row.get("id"))
            if not isinstance(scope_finding_id, str) or not scope_finding_id:
                raise RuntimeError("C5 decision-scope row has no finding identity")
            if scope_finding_id in decision_scope_finding_ids:
                raise RuntimeError("C5 decision-scope source contains duplicate finding IDs")
            decision_scope_finding_ids.append(scope_finding_id)
            binding = raw_overrides.get(scope_finding_id)
            expected_pointer = f"{scope_pointer.rstrip('/')}/{index}"
            if binding != {"source_id": scope_source_id, "json_pointer": expected_pointer}:
                raise RuntimeError(
                    "C5 root override does not bind its exact decision-scope row: "
                    f"{scope_finding_id}"
                )
        decision_scope_finding_ids.sort()
        if set(decision_scope_finding_ids) != set(decisions):
            raise RuntimeError("C5 root overrides do not cover the complete pinned decision scope")
        decision_scope_source = {
            "source_id": scope_source_id,
            **source_refs[scope_source_id],
            "json_pointer": scope_pointer,
        }
        carry_source_id = carry_binding["source_id"]
        carry_pointer = carry_binding["json_pointer"]
        carry_value = json_pointer_value(source_docs[carry_source_id], carry_pointer)
        if (
            not isinstance(carry_value, list)
            or any(not isinstance(item, str) for item in carry_value)
            or len(carry_value) != len(set(carry_value))
        ):
            raise RuntimeError("C5 carry-forward source must resolve to unique finding IDs")
        carry_forward_finding_ids = sorted(carry_value)
        if set(carry_forward_finding_ids) != finding_ids - set(decisions):
            raise RuntimeError("C5 carry-forward source does not bind the exact unoverridden set")
        carry_forward_source = {
            "source_id": carry_source_id,
            **source_refs[carry_source_id],
            "json_pointer": carry_pointer,
        }
    if status == "draft" and raw_overrides:
        raise RuntimeError("draft C5 input cannot assign root finding dispositions")
    return {
        "authority": "root",
        "status": status,
        "carry_forward_basis": root_record.get("carry_forward_basis"),
        "carry_forward_reason": root_record.get("carry_forward_reason"),
        "carry_forward_source": carry_forward_source,
        "carry_forward_finding_ids": carry_forward_finding_ids,
        "decision_scope_source": decision_scope_source,
        "decision_scope_finding_ids": decision_scope_finding_ids,
        "source_refs": source_refs,
        "overrides": decisions,
    }


def build_c5(root: Path, json_path: Path, markdown_path: Path, input_path: Path) -> dict:
    """Build C5 current dispositions from pinned C4, G, root, and evidence sources."""
    input_raw = input_path.read_bytes()
    c5_input = json.loads(input_raw)
    if c5_input.get("schema") != C5_FINAL_INPUT_SCHEMA:
        raise RuntimeError("C5 current-inventory input schema mismatch")

    c4_source = c5_input["c4_source"]
    g_snapshot = c5_input["g_snapshot"]
    for ref, label in ((c4_source, "C4"), (g_snapshot, "G")):
        actual_tree = git(root, "rev-parse", f"{ref['commit']}^{{tree}}")
        if actual_tree != ref["tree"]:
            raise RuntimeError(f"pinned {label} source tree mismatch: {actual_tree}")
    if (c4_source["commit"], c4_source["tree"]) != (
        C5_C4_SOURCE_COMMIT,
        C5_C4_SOURCE_TREE,
    ):
        raise RuntimeError("C5 input does not pin the frozen C4 source cut")
    if (g_snapshot["commit"], g_snapshot["tree"]) != (
        C5_G_SNAPSHOT_COMMIT,
        C5_G_SNAPSHOT_TREE,
    ):
        raise RuntimeError("C5 input does not pin the current G snapshot")

    report_ref = c4_source["report"]
    c4_raw, c4_blob = git_source_file(
        root,
        c4_source["commit"],
        c4_source["tree"],
        report_ref["path"],
        expected_sha256=report_ref["sha256"],
        expected_blob=report_ref["git_blob"],
        expected_size=report_ref["bytes"],
    )
    c4_cut = json.loads(c4_raw)
    if (
        c4_cut.get("schema") != C4_FINAL_CUT_SCHEMA
        or c4_cut.get("status") != "c4_current_root_adjudicated"
        or c4_cut.get("final_verdicts_assigned") is not True
        or c4_cut.get("base") != {"commit": BASE_COMMIT, "tree": BASE_TREE}
    ):
        raise RuntimeError("pinned C4 source does not have the expected final C4 structure")

    _c4_markdown, _ = git_source_file(
        root,
        c4_source["commit"],
        c4_source["tree"],
        c4_source["markdown"]["path"],
        expected_sha256=c4_source["markdown"]["sha256"],
        expected_blob=c4_source["markdown"]["git_blob"],
        expected_size=c4_source["markdown"]["bytes"],
    )
    c4_input_raw, _ = git_source_file(
        root,
        c4_source["commit"],
        c4_source["tree"],
        c4_source["input"]["path"],
        expected_sha256=c4_source["input"]["sha256"],
        expected_blob=c4_source["input"]["git_blob"],
        expected_size=c4_source["input"]["bytes"],
    )
    c4_document = json.loads(c4_input_raw)
    if c4_cut.get("c4_input", {}).get("sha256") != sha256(c4_input_raw):
        raise RuntimeError("C4 report does not bind its exact C4 source input")

    g_raw: dict[str, bytes] = {}
    g_docs: dict[str, object] = {}
    g_input_refs: dict[str, dict] = {}
    for name, ref in c5_input["g_inputs"].items():
        raw, _blob = git_source_file(
            root,
            g_snapshot["commit"],
            g_snapshot["tree"],
            ref["path"],
            expected_sha256=ref["sha256"],
            expected_blob=ref["git_blob"],
            expected_size=ref["bytes"],
        )
        g_raw[name] = raw
        g_input_refs[name] = {**ref, "source_commit": g_snapshot["commit"]}
        if name == "coverage" or name == "allocation" or name == "decisions":
            g_docs[name] = json.loads(raw)

    required_g_inputs = {
        "coverage",
        "allocation",
        "finding_owners",
        "bundle_owners",
        "closure_c",
        "decisions",
        "actions",
    }
    if set(g_input_refs) != required_g_inputs:
        raise RuntimeError("C5 input must bind the complete current G row/source set")
    coverage = g_docs["coverage"]
    allocation = g_docs["allocation"]
    decisions = g_docs["decisions"]
    if allocation.get("schema") != "policyos.e02.execution_organization.proposal.v1":
        raise RuntimeError("C5 G allocation source schema mismatch")
    c4_rows = {row["id"]: (index, row) for index, row in enumerate(c4_cut["rows"])}
    g_rows = {row["id"]: row for row in coverage["findings"] if row["unit"] == "C"}
    decision_rows = {row["id"]: row for row in decisions["rows"]}
    if len(c4_rows) != 54 or set(c4_rows) != set(g_rows) or set(c4_rows) != set(decision_rows):
        raise RuntimeError("C5 C-finding identity set is not exactly 54 rows")
    root_decisions = c5_root_decisions(root, c5_input.get("root_adjudication", {}), set(c4_rows))

    base_coverage_raw, _ = git_source_file(
        root,
        BASE_COMMIT,
        BASE_TREE,
        C5_COVERAGE_PATH,
    )
    base_coverage = json.loads(base_coverage_raw)
    base_findings = {row["id"]: row for row in base_coverage["findings"] if row["unit"] == "C"}
    denominator = {
        "all_bundles": len(coverage["bundles"]),
        "all_findings": len(coverage["findings"]),
        "canonical_criterion_occurrences": coverage["denominator"][
            "canonical_source_block_occurrences"
        ],
        "C_bundles": len({bundle["id"] for bundle in coverage["bundles"] if bundle["unit"] == "C"}),
        "C_findings": len(g_rows),
        "C_hash_bound_criteria": sum(len(row.get("criterion_refs", [])) for row in g_rows.values()),
    }
    expected_denominator = {
        "all_bundles": 127,
        "all_findings": 282,
        "canonical_criterion_occurrences": 291,
        "C_bundles": 33,
        "C_findings": 54,
        "C_hash_bound_criteria": 59,
    }
    if denominator != expected_denominator:
        raise RuntimeError(f"C5 pinned denominator changed: {denominator}")

    c4_input_summary = c4_cut["c4_input"]
    if (
        c4_input_summary["path"] != c4_source["input"]["path"]
        or c4_input_summary["bytes"] != len(c4_input_raw)
        or c4_input_summary["schema"] != c4_document.get("schema")
    ):
        raise RuntimeError("C4 input locator does not resolve to the exact pinned input")

    finding_owners = {row["finding_id"]: row for row in tsv_rows(g_raw["finding_owners"])}
    bundle_owners = {row["bundle_id"]: row for row in tsv_rows(g_raw["bundle_owners"])}
    if set(finding_owners) != {row["id"] for row in coverage["findings"]}:
        raise RuntimeError("C5 G finding-owner TSV denominator mismatch")

    c_md_labels = parse_c_md_labels(g_raw["closure_c"])
    if set(c_md_labels) != set(g_rows):
        raise RuntimeError("C5 G C.md labels do not match the C finding set")

    base_doc_index = c4_cut["criterion_document_index"]
    base_doc_bytes: dict[str, bytes] = {}
    for doc_ref, doc in base_doc_index.items():
        doc_raw, _blob = git_source_file(
            root,
            BASE_COMMIT,
            BASE_TREE,
            doc["path"],
            expected_blob=doc["git_blob"],
        )
        if sha256(doc_raw) != doc["source_sha256"]:
            raise RuntimeError(f"C5 base criterion document hash mismatch: {doc_ref}")
        base_doc_bytes[doc_ref] = doc_raw

    c4_source_ref = {
        "commit": c4_source["commit"],
        "tree": c4_source["tree"],
        "path": report_ref["path"],
        "git_blob": c4_blob,
        "sha256": report_ref["sha256"],
        "bytes": len(c4_raw),
    }
    rows = []
    for finding_id in sorted(
        c4_rows,
        key=lambda item: (
            item.startswith("LA-"),
            int(item[3:]) if item.startswith("LA-") else int(item[1:]),
        ),
    ):
        c4_index, c4_row = c4_rows[finding_id]
        g_row = g_rows[finding_id]
        decision = decision_rows[finding_id]
        base_row = base_findings[finding_id]
        if set(c4_row["bundles"]) != set(g_row["companion_bundles"]) or set(
            c4_row["bundles"]
        ) != set(base_row["companion_bundles"]):
            raise RuntimeError(f"C5 bundle membership mismatch: {finding_id}")
        if set(c4_row["bundles"]) != set(decision["bundles"]):
            raise RuntimeError(f"C5 decision bundle membership mismatch: {finding_id}")
        if (
            g_row["closure_now"] != "not_adjudicated"
            or decision["G_formal_status"] != "not_adjudicated"
        ):
            raise RuntimeError(f"C5 G formal status is not not_adjudicated: {finding_id}")
        if c4_row["current_root_verdict"]["value"] != decision["C_recommendation"]:
            raise RuntimeError(f"C5 C recommendation differs from C4: {finding_id}")
        if c4_row["current_root_verdict"]["value"] not in {"closed", "limited", "held"}:
            raise RuntimeError(f"C5 C recommendation has an unsupported value: {finding_id}")
        owner = finding_owners[finding_id]
        if owner["source_closure_owner"] != g_row["source_closure_owner_literal"]:
            raise RuntimeError(f"C5 canonical G owner mismatch: {finding_id}")
        c_md_status, c_md_label = c_md_labels[finding_id]
        g_criteria = g_row.get("criterion_refs", [])
        c4_criteria = c4_row["criterion_refs"]
        base_criteria = base_row["criterion_refs"]
        decision_criteria = decision.get("original_criteria", [])
        if len(decision_criteria) != len(c4_criteria):
            raise RuntimeError(f"C5 G decision criterion count mismatch: {finding_id}")
        if len(g_criteria) != len(c4_criteria):
            raise RuntimeError(f"C5 criterion occurrence count mismatch: {finding_id}")
        if len(base_criteria) != len(c4_criteria):
            raise RuntimeError(f"C5 base criterion occurrence count mismatch: {finding_id}")
        criteria = []
        for criterion_index, (
            criterion,
            g_criterion,
            base_criterion,
            decision_criterion,
        ) in enumerate(zip(c4_criteria, g_criteria, base_criteria, decision_criteria, strict=True)):
            doc = base_doc_index[criterion["document_ref"]]
            source_lines = base_doc_bytes[criterion["document_ref"]].splitlines(keepends=True)
            start_text, end_text = criterion["line_span"].split("-")
            start, end = int(start_text), int(end_text)
            selected = b"".join(source_lines[start - 1 : end])
            if (
                criterion["criterion_id"] != g_criterion["criterion_id"]
                or criterion["document_ref"]
                != {"B_r19": "CD01", "LA_r09": "CD02"}[g_criterion["document"]]
                or criterion["line_span"] != f"{g_criterion['lines'][0]}-{g_criterion['lines'][1]}"
                or criterion["criterion_sha256"] != g_criterion["sha256"]
                or base_criterion["criterion_id"] != criterion["criterion_id"]
                or base_criterion["document"] != g_criterion["document"]
                or base_criterion["lines"] != g_criterion["lines"]
                or base_criterion["sha256"] != g_criterion["sha256"]
                or decision_criterion["criterion_id"] != criterion["criterion_id"]
                or decision_criterion["document_ref"] != criterion["document_ref"]
                or decision_criterion["line_span"] != criterion["line_span"]
                or decision_criterion["sha256"] != criterion["criterion_sha256"]
                or sha256(selected) != criterion["criterion_sha256"]
                or criterion["original_wording"] != selected.decode("utf-8")
            ):
                raise RuntimeError(f"C5 original criterion binding mismatch: {finding_id}")
            criteria.append(
                {
                    "criterion_id": criterion["criterion_id"],
                    "document_ref": criterion["document_ref"],
                    "line_span": criterion["line_span"],
                    "criterion_sha256": criterion["criterion_sha256"],
                    "source_document": {
                        "commit": BASE_COMMIT,
                        "tree": BASE_TREE,
                        "path": doc["path"],
                        "git_blob": doc["git_blob"],
                    },
                    "wording_source": {
                        **c4_source_ref,
                        "json_pointer": (
                            f"/rows/{c4_index}/criterion_refs/{criterion_index}/original_wording"
                        ),
                    },
                }
            )

        g_status_label, g_capability_label = c_md_status, c_md_label
        c4_eval = c4_row["current_evaluation"]
        c4_verdict = c4_row["current_root_verdict"]
        c2_snapshot = c4_row["c2_snapshot"]
        c2_source = c4_cut["c2_source"]
        current_source_pointer = (
            f"/current_source_family_refs/{c4_row['source_family']}"
            if c4_row["source_family"] in c4_cut.get("current_source_family_refs", {})
            else f"/topic_source_refs/{c4_row['source_family']}"
        )
        coverage_index = next(
            index for index, item in enumerate(coverage["findings"]) if item["id"] == finding_id
        )
        decisions_index = next(
            index for index, item in enumerate(decisions["rows"]) if item["id"] == finding_id
        )
        history = {
            **c4_row["historical_status"],
            "G_coverage_ledger_status_historical": g_row.get("ledger_status_historical"),
            "G_coverage_appendix_C_status_separate": g_row.get("appendix_c_status_separate"),
        }
        root_override = root_decisions["overrides"].get(finding_id)
        if root_override:
            current_verdict = {
                "value": root_override["value"],
                "status": "root_c5_adjudication_override",
                "basis": root_override["basis"],
                "reason": root_override["reason"],
                "source_pointer": (f"/root_adjudication/overrides/{finding_id}/json_pointer"),
                "root_review_source_pointer": f"/root_adjudication/overrides/{finding_id}",
                "root_review_note": root_override["reason"],
                "decision_source": root_override["source_binding"],
                "evidence_refs": root_override["evidence_refs"],
            }
            current_evaluation = {
                "status": "root_c5_adjudication_override",
                "code_outcome": root_override["code_outcome"],
                "evidence_basis": root_override["basis"],
                "scoped_proven_part": root_override["scoped_proven_part"],
                "missing_input": root_override["missing_input"],
                "remaining_verification": root_override["remaining_verification"],
                "next_action": root_override["next_action"],
                "next_owner": root_override["next_owner"],
                "source_pointer": current_verdict["source_pointer"],
            }
        else:
            if (
                root_decisions["status"] == "final_root_adjudication"
                and finding_id not in root_decisions["carry_forward_finding_ids"]
            ):
                raise RuntimeError(f"C5 root did not bind the carry-forward finding: {finding_id}")
            current_verdict = {
                "value": c4_verdict["value"],
                "status": (
                    "retained_from_c4_under_c5_root_adjudication"
                    if root_decisions["status"] == "final_root_adjudication"
                    else "carried_forward_from_c4_pending_c5_root_adjudication"
                ),
                "basis": (
                    root_decisions["carry_forward_basis"]
                    if root_decisions["status"] == "final_root_adjudication"
                    else c4_verdict["basis"]
                ),
                "reason": c4_verdict["reason"],
                "source_pointer": (f"/rows/{c4_index}/current_root_verdict"),
                "root_review_source_pointer": (
                    "/root_adjudication/carry_forward_source"
                    if root_decisions["status"] == "final_root_adjudication"
                    else None
                ),
                "root_review_note": root_decisions["carry_forward_reason"],
                "decision_source": None,
                "evidence_refs": [],
            }
            current_evaluation = {
                "status": "retained_from_c4_evaluation",
                "code_outcome": c4_eval["code_outcome"],
                "evidence_basis": c4_eval["evidence_basis"],
                "scoped_proven_part": c4_eval["scoped_proven_part"],
                "missing_input": c4_eval["missing_input_or_skipped_backend"],
                "remaining_verification": c4_eval["remaining_verification"],
                "next_action": c4_eval["next_action"],
                "next_owner": c4_eval["next_owner"],
                "source_pointer": f"/rows/{c4_index}/current_evaluation",
            }
        rows.append(
            {
                "id": finding_id,
                "bundles": list(c4_row["bundles"]),
                "source_family": c4_row["source_family"],
                "historical_status": history,
                "original_criteria": criteria,
                "c_recommendation": {
                    "value": c4_verdict["value"],
                    "status": "carried_forward_from_c4_not_a_new_c5_verdict",
                    "basis": c4_verdict["basis"],
                    "reason": c4_verdict["reason"],
                    "source_pointer": f"/rows/{c4_index}/current_root_verdict",
                },
                "carried_c4_evaluation": {
                    "state": c4_eval["state"],
                    "code_outcome": c4_eval["code_outcome"],
                    "evidence_basis": c4_eval["evidence_basis"],
                    "scoped_proven_part": c4_eval["scoped_proven_part"],
                    "missing_input": c4_eval["missing_input_or_skipped_backend"],
                    "remaining_verification": c4_eval["remaining_verification"],
                    "next_action": c4_eval["next_action"],
                    "next_owner": c4_eval["next_owner"],
                    "source_pointer": f"/rows/{c4_index}/current_evaluation",
                },
                "current_root_verdict": current_verdict,
                "current_c_evaluation": current_evaluation,
                "g_current": {
                    "formal_status": g_row["closure_now"],
                    "coverage_capability_label": g_row.get("capability_label"),
                    "c_md_status_label": g_status_label,
                    "c_md_capability_label": g_capability_label,
                    "capability_label_source_state": (
                        "historical_source_label_empty"
                        if g_row.get("capability_label") in (None, "") and g_capability_label == ""
                        else "pinned_source_label_disagreement"
                        if g_row.get("capability_label") != g_capability_label
                        else "pinned_source_labels_match"
                    ),
                    "canonical_source_owner": owner["source_closure_owner"],
                    "source_owner_bundle_ids": owner["source_bundle_ids"].split(";"),
                    "primary_bundle": g_row["primary_bundle"],
                    "companion_bundles": list(g_row["companion_bundles"]),
                    "task_refs": list(g_row.get("task_refs", [])),
                    "source_pointer": f"/findings/{coverage_index}",
                    "source_owner_ref": {
                        "input_ref_name": "finding_owners",
                        "path": g_input_refs["finding_owners"]["path"],
                        "sha256": g_input_refs["finding_owners"]["sha256"],
                        "lookup_key": finding_id,
                    },
                    "c_md_source_ref": {
                        "input_ref_name": "closure_c",
                        "path": g_input_refs["closure_c"]["path"],
                        "sha256": g_input_refs["closure_c"]["sha256"],
                        "task_refs": list(g_row.get("task_refs", [])),
                    },
                },
                "g_action": {
                    "next_owner": decision["next_owner"],
                    "execution_action": decision["G_execution_action"],
                    "basis": decision["basis"],
                    "source_pointer": f"/rows/{decisions_index}",
                },
                "source_refs": {
                    "c4_evaluation_pointer": f"/rows/{c4_index}/current_evaluation",
                    "c4_recommendation_pointer": f"/rows/{c4_index}/current_root_verdict",
                    "c4_historical_status_pointer": f"/rows/{c4_index}/historical_status",
                    "c4_source_family_pointer": current_source_pointer,
                    "c2_receipts_pointer": c2_snapshot["deciding_receipts_source_pointer"],
                    "c2_source": c2_source,
                    "c4_source_row_index": c4_index,
                    "g_coverage_pointer": f"/findings/{coverage_index}",
                    "g_decision_pointer": f"/rows/{decisions_index}",
                },
                "c5_assessment": {
                    "state": current_verdict["status"],
                    "note": (
                        "C4 criterion evidence and recommendation remain visible separately; "
                        "this row assigns no G formal closure or product-level acceptance."
                    ),
                },
                "p37_property_basis": {
                    "criterion_source_binding": "recomputed",
                    "c4_candidate_evidence_basis": c4_eval["evidence_basis"],
                    "new_c5_runtime_property": "not_established",
                },
            }
        )

    c_bundle_rows = {item["id"]: item for item in coverage["bundles"] if item["unit"] == "C"}
    bundle_crosswalk = []
    for bundle_id in sorted(c_bundle_rows):
        owner = bundle_owners.get(bundle_id)
        if owner is None:
            raise RuntimeError(f"C5 G bundle-owner table is missing {bundle_id}")
        members = [row for row in rows if bundle_id in row["bundles"]]
        bundle_crosswalk.append(
            {
                "bundle_id": bundle_id,
                "initial_writer_family": owner["initial_writer_family"],
                "c_finding_ids": [row["id"] for row in members],
                "c_source_families": sorted({row["source_family"] for row in members}),
                "g_source_closure_owners": sorted(
                    {row["g_current"]["canonical_source_owner"] for row in members}
                ),
            }
        )
    c_bundle_ids = {bundle for row in rows for bundle in row["bundles"]}
    if c_bundle_ids != set(c_bundle_rows) or len(bundle_crosswalk) != 33:
        raise RuntimeError("C5 full 33-bundle union is inconsistent")

    c4_recommendations = dict(
        sorted(Counter(row["c_recommendation"]["value"] for row in rows).items())
    )
    current_recommendations = dict(
        sorted(Counter(row["current_root_verdict"]["value"] for row in rows).items())
    )
    g_status_counts = dict(
        sorted(Counter(row["g_current"]["formal_status"] for row in rows).items())
    )
    if c4_recommendations != {"closed": 31, "held": 14, "limited": 9}:
        raise RuntimeError("C5 carried C recommendation distribution differs from C4")
    if sum(current_recommendations.values()) != 54:
        raise RuntimeError("C5 current recommendation counts do not cover all 54 rows")
    if root_decisions["status"] == "final_root_adjudication" and current_recommendations != {
        "closed": 31,
        "limited": 12,
        "held": 11,
    }:
        raise RuntimeError(f"C5 root disposition count mismatch: {current_recommendations}")
    if root_decisions["status"] == "final_root_adjudication" and any(
        c4_rows[finding_id][1]["current_root_verdict"]["value"] != "closed"
        for finding_id in root_decisions["carry_forward_finding_ids"]
    ):
        raise RuntimeError("C5 unchanged finite scopes are not all closed in the C4 source")
    if g_status_counts != {"not_adjudicated": 54}:
        raise RuntimeError("C5 G formal status is not uniformly not_adjudicated")
    c5_verdicts_assigned = root_decisions["status"] == "final_root_adjudication"

    cut = {
        "schema": C5_FINAL_CUT_SCHEMA,
        "artifact": "C54 C5 current root dispositions; C4 and G status remain separate",
        "status": (
            "c5_current_root_adjudicated"
            if c5_verdicts_assigned
            else "c5_current_root_adjudication_draft"
        ),
        "c5_verdicts_assigned": c5_verdicts_assigned,
        "root_adjudication": root_decisions,
        "base": c4_cut["base"],
        "c4_source": {
            "commit": c4_source["commit"],
            "tree": c4_source["tree"],
            "report": {**report_ref, "git_blob": c4_blob},
            "markdown": c4_source["markdown"],
            "input": c4_source["input"],
        },
        "g_snapshot": g_snapshot,
        "g_input_refs": g_input_refs,
        "coverage_denominator": denominator,
        "c4_recommendation_counts_derived_from_all_54_rows": c4_recommendations,
        "current_root_verdict_counts_derived_from_all_54_rows": current_recommendations,
        "g_formal_status_counts_derived_from_all_54_rows": g_status_counts,
        "bundle_crosswalk": bundle_crosswalk,
        "criterion_document_index": {
            ref: {
                "path": document["path"],
                "git_blob": document["git_blob"],
                "source_commit": BASE_COMMIT,
                "source_tree": BASE_TREE,
                "source_sha256": sha256(base_doc_bytes[ref]),
                "source_bytes": len(base_doc_bytes[ref]),
            }
            for ref, document in base_doc_index.items()
        },
        "input": {
            "path": str(input_path.relative_to(root)),
            "sha256": sha256(input_raw),
            "bytes": len(input_raw),
            "schema": c5_input["schema"],
        },
        "root_adjudication_input_pointer": "/root_adjudication",
        "rows": rows,
        "scope_note": (
            "This C54 disposition keeps historical status and C4 recommendations distinct from "
            "the current C5 root adjudication. G remains not_adjudicated for every finding, and "
            "no product-level acceptance is inferred. Evidence and source-family refreshes are "
            "not inferred from row counts, historical labels, or unbound candidate references."
        ),
    }
    json_path.write_text(json.dumps(cut, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_c5_markdown(cut), encoding="utf-8")
    return {
        "json_path": str(json_path.relative_to(root)),
        "json_sha256": sha256(json_path.read_bytes()),
        "json_bytes": json_path.stat().st_size,
        "markdown_path": str(markdown_path.relative_to(root)),
        "markdown_sha256": sha256(markdown_path.read_bytes()),
        "markdown_bytes": markdown_path.stat().st_size,
        "rows": len(rows),
        "criterion_occurrences": sum(len(row["original_criteria"]) for row in rows),
        "bundles": len(c_bundle_ids),
        "c4_recommendation_counts": c4_recommendations,
        "current_root_verdict_counts": current_recommendations,
        "g_formal_status_counts": g_status_counts,
        "c5_verdicts_assigned": c5_verdicts_assigned,
    }


def build(root: Path, json_path: Path, markdown_path: Path) -> dict:
    head = git(root, "rev-parse", SOURCE_SNAPSHOT)
    tree = git(root, "rev-parse", f"{SOURCE_SNAPSHOT}^{{tree}}")
    if head != SOURCE_SNAPSHOT or tree != SOURCE_SNAPSHOT_TREE:
        raise RuntimeError(f"pinned source snapshot changed: {head} {tree}")
    if git(root, "rev-parse", f"{BASE_COMMIT}^{{tree}}") != BASE_TREE:
        raise RuntimeError("pinned base tree changed")
    git(root, "merge-base", "--is-ancestor", BASE_COMMIT, SOURCE_SNAPSHOT)
    branch = SOURCE_SNAPSHOT_BRANCH

    source_path = root / SOURCE_DRAFT
    source_gzip_raw = source_path.read_bytes()
    if sha256(source_gzip_raw) != SOURCE_DRAFT_GZIP_SHA256:
        raise RuntimeError("the tracked reviewed v8 source archive changed")
    source_raw = gzip.decompress(source_gzip_raw)
    if sha256(source_raw) != SOURCE_DRAFT_SHA256:
        raise RuntimeError("the reviewed v8 input cut changed")
    inventory_raw = (root / INVENTORY_PATH).read_bytes()
    if sha256(inventory_raw) != INVENTORY_SHA256:
        raise RuntimeError("the tracked exact 54-row historical inventory changed")
    cut = json.loads(source_raw)
    if len(cut["rows"]) != 54:
        raise RuntimeError("source cut does not contain the complete C denominator")

    source_values = {row["id"]: row["root_proposed_verdict"]["value"] for row in cut["rows"]}
    final_values = {
        finding_id: verdict for verdict, ids in ROOT_VERDICTS.items() for finding_id in ids
    }
    if set(source_values) != set(final_values) or source_values != final_values:
        raise RuntimeError(
            "root-approved full-set disposition differs from the reviewed input rows"
        )

    manifest_path = root / LA039_MANIFEST
    manifest_raw = manifest_path.read_bytes()
    manifest = json.loads(manifest_raw)
    if manifest.get("schema") != "policyos.c54.late-la039-evidence-manifest.v1":
        raise RuntimeError("LA-039 evidence manifest schema mismatch")
    for artifact in manifest["artifacts"]:
        raw = (root / artifact["path"]).read_bytes()
        if len(raw) != artifact["size_bytes"] or sha256(raw) != artifact["sha256"]:
            raise RuntimeError(f"late LA-039 artifact binding mismatch: {artifact['path']}")

    index = cut["receipt_index"]
    receipt_id = f"R{len(index) + 1:02d}"
    if receipt_id != "R210":
        raise RuntimeError(f"unexpected late evidence receipt slot {receipt_id}")
    index[receipt_id] = {
        "path_at_sha256": f"{LA039_MANIFEST}@sha256:{sha256(manifest_raw)}",
        "sha256": sha256(manifest_raw),
        "size_bytes": len(manifest_raw),
        "format": "json",
        "role": (
            "late LA-039 installed producer/reader evidence manifest with nested file SHA "
            "and size bindings"
        ),
        "nested_file_manifest_pointer": "/artifacts",
        "nested_file_path_field": "path",
        "nested_file_sha256_field": "sha256",
        "nested_file_size_field": "size_bytes",
    }
    cut["input_receipts"]["late_la039_evidence_manifest_receipt_id"] = receipt_id
    cut["input_receipts"]["reviewed_source_archive_path_at_sha256"] = (
        f"{SOURCE_DRAFT}@sha256:{SOURCE_DRAFT_GZIP_SHA256}"
    )
    cut["input_receipts"]["reviewed_source_uncompressed_sha256"] = SOURCE_DRAFT_SHA256
    cut["input_receipts"]["reviewed_source_raw_capture_path_at_sha256"] = (
        f"{SOURCE_DRAFT_RAW_CAPTURE}@sha256:{SOURCE_DRAFT_SHA256}"
    )
    cut["input_receipts"]["inventory_raw_capture_path_at_sha256"] = (
        f"{INVENTORY_RAW_CAPTURE}@sha256:{INVENTORY_SHA256}"
    )
    cut["input_receipts"]["inventory_tsv_path_at_sha256"] = (
        f"{INVENTORY_PATH}@sha256:{INVENTORY_SHA256}"
    )

    for row in cut["rows"]:
        finding_id = row["id"]
        if finding_id in ING_OUTCOMES:
            row["code_outcome"] = ING_OUTCOMES[finding_id]
            row["code_outcome_evidence"] = {
                "mode": "authored_criterion_summary_cited_by_deciding_receipts",
                "basis": (
                    "complete criterion_backed_result field in the final ING source handoff "
                    "and its listed deciding receipts"
                ),
            }
        if finding_id == "LA-013":
            row["missing_inputs_or_skipped_backend"] = (
                "No required input is missing for the bounded packaging and "
                "workspace-map criteria. "
                "Actual host dependency setup and external source history were not tested and "
                "remain outside this evidence scope."
            )
            row["remaining_verification"] = (
                "The final HYG source/archive evidence and independent bounded audit pass "
                "the exact "
                "archive/member/source-byte and five-root workspace-map checks. Actual host "
                "dependency setup and external source history are outside this evidence scope."
            )
        if finding_id == "LA-023":
            row["code_outcome"] = (
                "The installed one-call CPU PPO path writes the expected result through tenant CAS "
                "and the runtime consumer. Separate zero-gradient refusal and initialize-reset "
                "controls pass. This does not establish cross-call typed continuation; "
                "Product-owner "
                "public .train scope and historical TrainingResult compatibility remain unresolved."
            )
            row["code_outcome_evidence"] = {
                "mode": "authored_criterion_summary_cited_by_deciding_receipts",
                "basis": (
                    "latest PLG source handoff, installed evidence, and root-approved bounded "
                    "one-call scope"
                ),
            }
            for receipt in row["deciding_receipts"]:
                if receipt["receipt_id"] == "R11":
                    receipt["json_pointers"] = [
                        "/checks/1",
                        "/checks/10",
                        "/finding_dispositions/LA-023",
                    ]
                    break
            else:
                raise RuntimeError("LA-023 deciding receipt R11 is missing")
        if finding_id == "LA-039":
            row["code_outcome"] = (
                "Fresh installed CAT 8dfa probes exercise Academic's two-row producer through a "
                "complete 4D generation and ScholarKnowledgeStore readback, and Catalog's one-row "
                "graph/embedding producer through DatasetCatalogStore. Readers return the expected "
                "fixture IDs; removing a selected native index or deleting the contributing source "
                "row returns no result with markers retained. Native hnswlib is 0.8.0. The encoder "
                "is a fixture, not production weights."
            )
            row["code_outcome_evidence"] = {
                "mode": "authored_criterion_summary_cited_by_deciding_receipts",
                "basis": (
                    "late installed composition receipt, exact command/output, probe source-copy "
                    "binding, and CAT/DFI source handoffs"
                ),
            }
            row["remaining_verification"] = (
                "The fresh installed fixture producer-to-reader path and native-index/source-row "
                "removal controls pass. Production corpus membership, immutable "
                "encoder/tokenizer/weight provenance, external source history, and "
                "full-corpus performance remain not_established."
            )
            row["deciding_receipts"].append({"receipt_id": receipt_id, "json_pointers": []})

        row["root_finding_verdict"] = {
            "value": final_values[finding_id],
            "status": "final_root_adjudication",
            "reason": "",
        }
        row.pop("root_proposed_verdict", None)
        value = final_values[finding_id]
        code_outcome = str(row["code_outcome"])
        missing = str(row["missing_inputs_or_skipped_backend"])
        remaining = str(row["remaining_verification"])
        if value == "closed":
            reason = (
                "Closed for the bounded, hash-bound criterion scope. "
                f"The cited evidence shows: {code_outcome}"
            )
        elif value == "limited":
            reason = (
                "Limited to the demonstrated criterion scope. "
                f"Evidence: {code_outcome} Remaining boundary: {remaining}"
            )
        else:
            reason = (
                f"Held because {missing} Available candidate evidence is bounded as follows: "
                f"{code_outcome}"
            )
        row["root_finding_verdict"]["reason"] = reason

    # The nine ING narratives, LA-013, LA-023, and LA-039 are intentionally
    # authored complete summaries; no source text is truncated or sliced.
    counts = Counter(final_values.values())
    if counts != Counter({"closed": 31, "limited": 9, "held": 14}):
        raise RuntimeError(f"root disposition count mismatch: {dict(counts)}")
    cut["artifact"] = "C54 final root-adjudicated criterion-backed decision table"
    cut["status"] = "final_root_adjudicated"
    cut["final_verdicts_assigned"] = True
    cut.pop("draft_root_proposal_counts_from_all_54_rows_not_final_closure_counts", None)
    cut["final_verdict_counts_derived_from_all_54_rows"] = dict(sorted(counts.items()))
    cut["final_adjudication"] = {
        "authority": "root",
        "status": "final_root_adjudicated",
        "scope": (
            "All 54 allocated C findings, evaluated against their original hash-bound criteria; "
            "historical status remains separate."
        ),
        "counts": dict(sorted(counts.items())),
    }
    cut.pop("mandatory_pending_topics", None)
    cut["snapshot"] = {"branch": branch, "commit": head, "tree": tree}
    cut["audit_adjustments"].append(
        "Root assigned final criterion-scoped verdicts across all 54 rows after reading the "
        "complete table; all historical fields were preserved separately."
    )
    cut["audit_adjustments"].append(
        "LA-039 includes fresh installed CAT 8dfa Academic/Catalog producer-to-reader evidence "
        "and marker-kept-live native-index/source-row removals; fixture scope and post-run-only "
        "script hash grade remain explicit."
    )

    json_path.write_text(json.dumps(cut, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(cut), encoding="utf-8")
    return {
        "json_path": str(json_path.relative_to(root)),
        "json_sha256": sha256(json_path.read_bytes()),
        "json_bytes": json_path.stat().st_size,
        "markdown_path": str(markdown_path.relative_to(root)),
        "markdown_sha256": sha256(markdown_path.read_bytes()),
        "markdown_bytes": markdown_path.stat().st_size,
        "source_draft_sha256": sha256(source_raw),
        "late_la039_manifest_sha256": sha256(manifest_raw),
        "rows": len(cut["rows"]),
        "criterion_occurrences": sum(len(row["criterion_refs"]) for row in cut["rows"]),
        "bundles": len({bundle for row in cut["rows"] for bundle in row["bundles"]}),
        "receipt_index_entries": len(cut["receipt_index"]),
        "final_verdict_counts": dict(sorted(counts.items())),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument(
        "--mode", choices=("c2", "c3", "c3-final", "c4-final", "c5-final"), default="c2"
    )
    parser.add_argument("--input", type=Path, default=None)
    parser.add_argument("--json", type=Path, default=None)
    parser.add_argument("--markdown", type=Path, default=None)
    args = parser.parse_args()
    root = (
        args.repo_root.resolve()
        if args.repo_root
        else Path(git(Path.cwd(), "rev-parse", "--show-toplevel"))
    )
    if args.mode == "c5-final":
        json_arg = args.json or Path(C5_FINAL_OUTPUT_JSON)
        markdown_arg = args.markdown or Path(C5_FINAL_OUTPUT_MARKDOWN)
        input_arg = args.input or Path(C5_FINAL_INPUT_PATH)
        json_path = json_arg if json_arg.is_absolute() else root / json_arg
        markdown_path = markdown_arg if markdown_arg.is_absolute() else root / markdown_arg
        input_path = input_arg if input_arg.is_absolute() else root / input_arg
        print(  # noqa: T201 - CLI emits its machine-readable receipt on stdout.
            json.dumps(
                build_c5(root, json_path, markdown_path, input_path), ensure_ascii=False, indent=2
            )
        )
        return
    if args.mode in {"c3", "c3-final", "c4-final"}:
        c4_mode = args.mode == "c4-final"
        final_mode = args.mode in {"c3-final", "c4-final"}
        default_json = (
            C4_FINAL_OUTPUT_JSON
            if c4_mode
            else C3_FINAL_OUTPUT_JSON
            if final_mode
            else C3_OUTPUT_JSON
        )
        default_markdown = (
            C4_FINAL_OUTPUT_MARKDOWN
            if c4_mode
            else C3_FINAL_OUTPUT_MARKDOWN
            if final_mode
            else C3_OUTPUT_MARKDOWN
        )
        default_input = (
            C4_FINAL_INPUT_PATH if c4_mode else C3_FINAL_INPUT_PATH if final_mode else C3_INPUT_PATH
        )
        json_arg = args.json or Path(default_json)
        markdown_arg = args.markdown or Path(default_markdown)
        input_arg = args.input or Path(default_input)
        json_path = json_arg if json_arg.is_absolute() else root / json_arg
        markdown_path = markdown_arg if markdown_arg.is_absolute() else root / markdown_arg
        input_path = input_arg if input_arg.is_absolute() else root / input_arg
        print(  # noqa: T201 - CLI emits its machine-readable receipt on stdout.
            json.dumps(
                build_c3(root, json_path, markdown_path, input_path), ensure_ascii=False, indent=2
            )
        )
        return
    json_arg = args.json or Path(
        "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/C/C54-final-20261006-v10.json"
    )
    markdown_arg = args.markdown or Path(
        "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/C/C54-final-20261006-v10.md"
    )
    json_path = json_arg if json_arg.is_absolute() else root / json_arg
    markdown_path = markdown_arg if markdown_arg.is_absolute() else root / markdown_arg
    print(  # noqa: T201 - CLI emits its machine-readable receipt on stdout.
        json.dumps(build(root, json_path, markdown_path), ensure_ascii=False, indent=2)
    )


if __name__ == "__main__":
    main()
