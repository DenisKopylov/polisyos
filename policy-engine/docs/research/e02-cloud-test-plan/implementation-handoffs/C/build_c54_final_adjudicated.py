from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
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


def criterion_cell(row: dict) -> str:
    return "<br>".join(
        f"{item['criterion_id']} {item['document_ref']} L{item['line_span']} "
        f"`{item['criterion_sha256']}`"
        for item in row["criterion_refs"]
    )


def derive_c3_evidence_state(
    finding_id: str,
    source_family: str,
    c3_input: dict,
    verified_current_families: set[str],
) -> str:
    """Classify evidence from scope and verified receipts, never state labels."""
    override = c3_input.get("row_overrides", {}).get(finding_id, {})
    refresh_scope = c3_input.get("family_refresh_states", {})
    if source_family in verified_current_families:
        return "fresh_source_handoff_reviewed"
    if source_family in refresh_scope and source_family != "default":
        return "c3_source_refresh_pending"
    if override.get("code_outcome") and override.get("evidence_refs"):
        return "criterion_binding_corrected"
    return "c2_frozen_evidence_carried_forward"


def c3_evidence_state_note(state: str, source_family: str) -> str:
    """Render a state explanation from the evidence classification."""
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


def render_c3_markdown(cut: dict, c2_cut: dict, c3_input: dict) -> str:
    final_mode = cut.get("final_verdicts_assigned") is True
    counts = cut["c2_root_verdict_counts_derived_from_all_54_rows"]
    state_counts = cut["current_evaluation_state_counts_derived_from_all_54_rows"]
    lines = [
        (
            "# C54 C3 current-root adjudication"
            if final_mode
            else "# C54 C3 current-evidence census"
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
                "This is a source-evidence crosswalk, not a C3 verdict. It keeps historical "
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
            else f"C3 evidence-crosswalk states: {state_counts}."
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
                "Remaining verification | Deciding evidence | Next owner |"
            )
            if final_mode
            else (
                "| ID | Bundles / original criteria | Historical status | G formal status / "
                "capability | Canonical G owner | C source family | C2 frozen verdict | "
                "C3 evidence state and current "
                "code outcome | Remaining mechanism / verification / input / decision | "
                "Evidence refs |"
            )
        ),
        (
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"
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
        g = row["g_current"]
        source_family = row["source_family"]
        if final_mode:
            final_verdict = row["current_root_verdict"]
            current_refs = []
            if current["evidence_ref_source_pointer"]:
                current_refs.append(f"C2:{current['evidence_ref_source_pointer']}")
            current_refs.extend(refs)
            cells = [
                row["id"],
                f"{markdown_cell(row['bundles'])}<br>{criterion_cell(row)}",
                markdown_cell(hist),
                markdown_cell(g["formal_status"]),
                markdown_cell(f"{g['capability_label'] or '—'}<br>{g['canonical_source_owner']}"),
                markdown_cell(source_family),
                markdown_cell(f"{c2verdict['value']} ({c2verdict['status']})"),
                markdown_cell(current["evidence_basis"]),
                markdown_cell(current["code_outcome"]),
                f"**{final_verdict['value'].upper()}** — {markdown_cell(final_verdict['reason'])}",
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

    current_source_families = cut.get("current_source_family_refs", {})
    if final_mode and current_source_families:
        lines.extend(
            [
                "",
                "## Current source-family pins",
                "",
                "Fresh C3 source refs are shown separately from the frozen C2 source-family map.",
                "",
                "| Family | Branch | Head | Tree | Handoff receipt |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for family, ref in sorted(current_source_families.items()):
            lines.append(
                "| "
                + " | ".join(
                    [
                        family,
                        markdown_cell(ref.get("branch", "—")),
                        f"`{markdown_cell(ref.get('head', '—'))}`",
                        f"`{markdown_cell(ref.get('tree', '—'))}`",
                        markdown_cell(ref.get("handoff_path_at_sha256", "—")),
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
                f"C3 typed input: `{cut['c3_input']['path']}@sha256:{cut['c3_input']['sha256']}`."
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
                "at its original locator. The current C3 receipt index binds a repository "
                "companion with the same SHA-256 and size; this does not rewrite the C2 history."
            ),
            "",
            "| Receipt | Historical status | Historical C2 locator | Current C3 path at SHA-256 | "
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
                if row["current_evaluation"]["state"] == "c3_source_refresh_pending"
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
                "A C3 source refresh remains pending for "
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
                    "not new C3 PASS evidence."
                ),
                (
                    f"{corrected_rows} row(s) have corrected criterion/evidence bindings. "
                    "No C3 verdict is assigned."
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
            "fresh_source_handoff_reviewed": "fresh_source_handoff_reviewed",
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
        missing = override.get(
            "missing_inputs_or_skipped_backend", c2_row["missing_inputs_or_skipped_backend"]
        )
        remaining = override.get("remaining_verification", c2_row["remaining_verification"])
        next_owner = override.get("next_owner", c2_row["next_owner"])
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
        row["current_root_verdict"] = {
            "value": value,
            "status": "final_root_adjudication",
            "basis": derived_basis,
            "reason": reason,
            "reason_source_pointer": reason_pointer,
        }
        counts[value] += 1

    pending_states = {
        "c3_source_refresh_pending",
        "not_reassessed_in_C3",
        "source_refresh_pending",
    }
    if any(row["current_evaluation"]["state"] in pending_states for row in cut["rows"]):
        raise RuntimeError("final C3 table cannot carry a pending current-evaluation state")

    cut["schema"] = C3_FINAL_CUT_SCHEMA
    cut["artifact"] = "C54 C3 current root-adjudicated criterion evaluation"
    cut["status"] = "c3_current_root_adjudicated"
    cut["final_verdicts_assigned"] = True
    cut["current_root_verdict_counts_derived_from_all_54_rows"] = dict(sorted(counts.items()))
    cut["current_evaluation_state_counts_derived_from_all_54_rows"] = dict(
        sorted(Counter(row["current_evaluation"]["state"] for row in cut["rows"]).items())
    )
    cut["current_source_family_refs"] = verified_current_families
    cut["root_adjudication_authority"] = c3_input.get("root_adjudication_authority", "root")
    cut["root_adjudication_scope"] = (
        "All 54 allocated C findings evaluated against their original hash-bound criteria. "
        "Historical status and G formal status remain separate."
    )
    return cut


def git_bytes(root: Path, spec: str) -> bytes:
    return subprocess.check_output(  # noqa: S603 - trusted Git command with argv; shell disabled.
        ["git", "show", spec],  # noqa: S607 - trusted Git executable resolved by PATH.
        cwd=root,
    )


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


def verify_current_source_family_refs(root: Path, c2_cut: dict, c3_input: dict) -> dict:
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
    }
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
        if handoff_path.is_absolute() or ".." in handoff_path.parts:
            raise RuntimeError(f"source-family handoff path escapes the repository: {family}")
        handoff_spec = f"{handoff_commit}:{handoff_path.as_posix()}"
        handoff_raw = git_bytes(root, handoff_spec)
        handoff_blob = git(root, "rev-parse", handoff_spec)
        if sha256(handoff_raw) != ref["handoff_sha256"] or handoff_blob != ref["handoff_git_blob"]:
            raise RuntimeError(f"source-family handoff bytes/blob mismatch: {family}")
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

        verified[family] = {
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
        }
    return verified


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
        raw = (root / relative_path).read_bytes()
        digest = sha256(raw)
        if digest != binding["sha256"] or len(raw) != binding["size_bytes"]:
            raise RuntimeError(f"portable receipt byte identity mismatch: {receipt_id}")
        blob = git(root, "hash-object", "--", relative_path.as_posix())
        if len(blob) != 40 or any(character not in "0123456789abcdef" for character in blob):
            raise RuntimeError(f"portable receipt Git blob ID is malformed: {receipt_id}")
        result.append(
            {
                "receipt_id": receipt_id,
                "historical_path_at_sha256": source_receipt["path_at_sha256"],
                "historical_source_status": "verification_missing",
                "path_at_sha256": f"{relative_path.as_posix()}@sha256:{digest}",
                "git_blob": blob,
                "size_bytes": len(raw),
                "current_content_status": "verified_by_sha256_and_size",
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
    final_mode = c3_schema == C3_FINAL_INPUT_SCHEMA
    if c3_schema not in {
        "policyos.e02.c54.c3.current-evaluation-input.v2",
        C3_FINAL_INPUT_SCHEMA,
    }:
        raise RuntimeError("C3 current-evaluation input schema mismatch")

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
    verified_current_families = verify_current_source_family_refs(root, c2_cut, c3_input)
    if final_mode:
        required_refresh_families = set(c3_input["family_refresh_states"]) - {"default"}
        missing_refresh_families = required_refresh_families - set(verified_current_families)
        if missing_refresh_families:
            raise RuntimeError(
                "final C3 input lacks verified source handoffs for refresh families: "
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
        raise RuntimeError(f"C3 denominator changed: {denominator}")

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
    family_states = c3_input["family_refresh_states"]
    overrides = c3_input["row_overrides"]
    row_ids = set(c2_rows)
    if not set(overrides).issubset(row_ids):
        raise RuntimeError("C3 input contains an unknown row override")

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
            finding_id, source_family, c3_input, set(verified_current_families)
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

        remaining = override.get(
            "remaining_work",
            {
                "mechanism": {
                    "status": "not_reassessed_in_C3",
                    "note_ref": "status_semantics/c3_current_evaluation",
                },
                "verification": {
                    "status": "source_refresh_pending"
                    if state == "c3_source_refresh_pending"
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
            "state_note": c3_evidence_state_note(state, source_family),
            "state_note_source_pointer": (
                f"/current_source_family_refs/{source_family}"
                if source_family in verified_current_families
                else (
                    f"/row_overrides/{finding_id}"
                    if state == "criterion_binding_corrected"
                    else f"/family_refresh_states/{family_state_key}"
                )
            ),
            "code_outcome": code_outcome,
            "code_outcome_source_pointer": code_outcome_source_pointer,
            "evidence_refs": evidence_refs,
            "evidence_ref_source_pointer": evidence_ref_source_pointer,
            "source_family": source_family,
            "source_family_ref_key": source_family,
            "remaining_work": override.get("remaining_work", remaining),
            "tree_path_checks": override.get("git_tree_path_checks", []),
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
                "g_current": {
                    "unit": g["unit"],
                    "formal_status": g["closure_now"],
                    "capability_label": g.get("capability_label") or "",
                    "canonical_source_owner": owner["source_closure_owner"],
                    "source_owner_bundle_ids": owner["source_bundle_ids"].split(";"),
                    "primary_bundle": g["primary_bundle"],
                    "companion_bundles": list(g["companion_bundles"]),
                },
                "current_evaluation": current,
            }
        )

    if any(row["g_current"]["formal_status"] != "not_adjudicated" for row in rows):
        raise RuntimeError(
            "unexpected G formal disposition; C3 input requires root review before "
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
    cut = {
        "schema": "policyos.e02.c54.c3.current-evidence-census.v2",
        "artifact": "C54 C3 current-evidence census; no C3 verdict assigned",
        "status": "c3_current_evidence_crosswalk_not_adjudication",
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
        "bundle_crosswalk": bundle_crosswalk,
        "historical_local_only_receipts": historical_local_only,
        "portable_receipt_index": portable_index,
        "criterion_document_index": c2_cut["criterion_document_index"],
        "c3_input": {
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
            "C3_explicit_receipt_pointer_count": sum(
                len(ref["json_pointers"])
                for row in rows
                for ref in row["current_evaluation"]["evidence_refs"]
            ),
            "tree_path_query_count": sum(
                len(row["current_evaluation"]["tree_path_checks"]) for row in rows
            ),
        },
        "rows": rows,
    }
    if final_mode:
        cut = apply_c3_root_adjudications(cut, c2_cut, c3_input, verified_current_families)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(cut, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_c3_markdown(cut, c2_cut, c3_input), encoding="utf-8")
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
    parser.add_argument("--mode", choices=("c2", "c3", "c3-final"), default="c2")
    parser.add_argument("--input", type=Path, default=None)
    parser.add_argument("--json", type=Path, default=None)
    parser.add_argument("--markdown", type=Path, default=None)
    args = parser.parse_args()
    root = (
        args.repo_root.resolve()
        if args.repo_root
        else Path(git(Path.cwd(), "rev-parse", "--show-toplevel"))
    )
    if args.mode in {"c3", "c3-final"}:
        final_mode = args.mode == "c3-final"
        json_arg = args.json or Path(C3_FINAL_OUTPUT_JSON if final_mode else C3_OUTPUT_JSON)
        markdown_arg = args.markdown or Path(
            C3_FINAL_OUTPUT_MARKDOWN if final_mode else C3_OUTPUT_MARKDOWN
        )
        input_arg = args.input or Path(C3_FINAL_INPUT_PATH if final_mode else C3_INPUT_PATH)
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
