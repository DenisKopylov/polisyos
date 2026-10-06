from __future__ import annotations

import argparse
import gzip
import hashlib
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
SOURCE_DRAFT_RAW_CAPTURE = "policy-engine/.tmp/e02-C2/raw/census/C54-final-reviewcut-20261006-v8.json"
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


ROOT_VERDICTS = {
    "closed": {
        *(f"B{i}" for i in range(138, 146)),
        "B17", "B81", "B82", "B84", "B85", "B86", "B88",
        "LA-008", "LA-009", "LA-010", "LA-011", "LA-012", "LA-013",
        "LA-022", "LA-030", "LA-031", "LA-043", "LA-044", "LA-047",
        "LA-048", "LA-049", "B146", "B147",
    },
    "limited": {
        "B79", "LA-006", "LA-034", "LA-038", "LA-039", "LA-041",
        "LA-042", "LA-050", "LA-024",
    },
    "held": {
        "B80", "B83", "LA-005", "LA-018", "LA-021", "LA-023", "LA-025",
        "LA-026", "LA-027", "LA-028", "LA-029", "LA-032", "LA-036", "LA-040",
    },
}

ING_OUTCOMES = {
    "B79": (
        "The served batch_incremental route injects the exact persisted hint into the real REST request, "
        "and its since filter persists the independently expected rows. Promotion of that tenant cursor "
        "still lacks a source-confirmed evidence-content binder."
    ),
    "B80": (
        "Per-source storage and fail/retry behavior are exercised; unverified source progress is not promoted. "
        "The confirmed-cursor writer remains fail-closed until owner evidence content-binds dataset and ingestion_run_id."
    ),
    "B81": (
        "Failure, reopen, and retry compare exact raw source bytes, ordered row IDs, durable frontier, and cursor; "
        "the returned checkpoint reference resolves to the committed full payload."
    ),
    "B82": (
        "COUNT, TUMBLING, SESSION, and SLIDING checkpoints restore pending state; schema/window/key/TTL mismatch "
        "refuses before rewind or poll and preserves the predecessor CAS and cursor."
    ),
    "B83": (
        "The persisted UTC ingestion horizon is 86,400 seconds, composite primitive keys and source/partition "
        "isolation are exercised, and live-key overflow refuses before eviction. The connector does not supply "
        "source-owned event/version identity; synthesized _message_id is not that authority."
    ),
    "B84": (
        "Retained-state, input-row/serialized-byte, and output-reference budgets are checked before publication; "
        "lower-cap restore refuses before flush, write, rewind, poll, or frontier advance and preserves its predecessor. "
        "This makes no RSS, pre-return connector-allocation, or staged-spill claim; a real spill reader is absent."
    ),
    "B85": (
        "Every persisted window contributor ArtifactRef matches the independent source-row-to-chunk map across "
        "trigger, flush, and restart, and all exact chunk bytes are read back."
    ),
    "B86": (
        "Required, optional, missing, null, type, and finite row membership produces identical accepted IDs, keyed "
        "quarantine reasons, and accepted-data digest at batch sizes 1, 2, and 8."
    ),
    "B88": (
        "Served replay opens the retained exact owned CAS request/response artifact; missing or corrupt artifacts "
        "refuse without native connector egress from both repository and product working directories. Scope is the "
        "retained source-card replay profile."
    ),
}


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


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


def criterion_cell(row: dict) -> str:
    return "<br>".join(
        f"{item['criterion_id']} {item['document_ref']} L{item['line_span']} "
        f"`{item['criterion_sha256']}`"
        for item in row["criterion_refs"]
    )


def receipt_cell(row: dict) -> str:
    return "<br>".join(
        f"{ref['receipt_id']} " + (", ".join(ref["json_pointers"]) if ref["json_pointers"] else "(whole-file SHA)")
        for ref in row["deciding_receipts"]
    )


def render_markdown(cut: dict) -> str:
    counts = cut["final_verdict_counts_derived_from_all_54_rows"]
    lines = [
        "# C54 final criterion-backed adjudication",
        "",
        "This table records the root-adjudicated candidate verdict for every C finding. Historical status is kept in a separate column and is not projected into the new verdict.",
        "",
        f"Source snapshot: `{cut['snapshot']['commit']}` / tree `{cut['snapshot']['tree']}`. Baseline: `{cut['base']['commit']}` / tree `{cut['base']['tree']}`.",
        "",
        f"Pinned full denominator: {cut['coverage_denominator_derived_from_pinned_coverage_json']['all_bundles']} bundles, {cut['coverage_denominator_derived_from_pinned_coverage_json']['all_findings']} findings, and {cut['coverage_denominator_derived_from_pinned_coverage_json']['canonical_criterion_occurrences']} canonical criterion occurrences. C allocation: {cut['coverage_denominator_derived_from_pinned_coverage_json']['C_bundles']} bundles, {cut['coverage_denominator_derived_from_pinned_coverage_json']['C_findings']} findings, and {cut['coverage_denominator_derived_from_pinned_coverage_json']['C_hash_bound_criteria']} hash-bound criterion occurrences.",
        "",
        f"Root verdicts derived from all 54 rows: {counts['closed']} closed, {counts['limited']} limited, {counts['held']} held.",
        "",
        cut["baseline_use_limit"],
        "",
        "| ID | Bundles / hash-bound criteria | Historical status | Capability label | Code outcome | Root final verdict and reason | Missing input / skipped backend | Remaining verification | Deciding receipts | Next owner |",
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

    lines.extend([
        "",
        "## Criterion document index",
        "",
        "Every criterion occurrence above binds the pinned source document, inclusive line span, and SHA-256 of those exact source lines.",
        "",
        "| Ref | Path | Git blob | Source commit |",
        "| --- | --- | --- | --- |",
    ])
    for document_ref, item in cut["criterion_document_index"].items():
        lines.append(f"| {document_ref} | `{item['path']}` | `{item['git_blob']}` | `{item.get('source_commit', cut['base']['commit'])}` |")

    lines.extend([
        "",
        "## Receipt index",
        "",
        "The row references above resolve through this exact path/SHA index. JSON pointers are RFC 6901 and were checked against the cited bytes.",
        "",
        "| Receipt | Path at SHA-256 | Bytes | Git identity | Role |",
        "| --- | --- | ---: | --- | --- |",
    ])
    for receipt_id, item in cut["receipt_index"].items():
        git_identity = " / ".join(str(item[k]) for k in ("branch", "head", "tree") if item.get(k)) or "local copied receipt; bytes pinned by SHA-256"
        lines.append(
            f"| {receipt_id} | `{item['path_at_sha256']}` | {item['size_bytes']} | `{markdown_cell(git_identity)}` | {markdown_cell(item['role'])} |"
        )

    lines.extend([
        "",
        "## Source DAG and scope",
        "",
        f"Source-DAG review: {markdown_cell(cut['source_dag_review']['decision'])}. It checks Git ancestry, source identity, and ownership; semantic closure is not inferred. Receipt IDs: {', '.join(cut['source_dag_review']['receipt_ids'])}.",
        "",
        "Late LA-039 installed evidence is bound by the `R210` evidence manifest and its nested file hashes. The script's source digest is post-run-only; the recorded filesystem mtime precedes launch by 39.667 ms, but no cryptographic prelaunch/in-run digest exists. The scope is synthetic fixtures on the installed CAT 8dfa profile, not production corpus or model authority.",
        "",
    ])
    inputs = cut["input_receipts"]
    lines.extend([
        "## Canonical reproduction inputs",
        "",
        f"Reviewed v8 input: `{inputs['reviewed_source_archive_path_at_sha256']}`; uncompressed SHA-256 `{inputs['reviewed_source_uncompressed_sha256']}`.",
        f"Exact historical inventory: `{inputs['inventory_tsv_path_at_sha256']}`. The raw capture locator is retained separately as provenance: `{inputs['inventory_raw_capture_path_at_sha256']}`.",
        "",
    ])
    return "\n".join(lines)


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
    final_values = {finding_id: verdict for verdict, ids in ROOT_VERDICTS.items() for finding_id in ids}
    if set(source_values) != set(final_values) or source_values != final_values:
        raise RuntimeError("root-approved full-set disposition differs from the reviewed input rows")

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
        "role": "late LA-039 installed producer/reader evidence manifest with nested file SHA and size bindings",
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
                "basis": "complete criterion_backed_result field in the final ING source handoff and its listed deciding receipts",
            }
        if finding_id == "LA-013":
            row["missing_inputs_or_skipped_backend"] = (
                "No required input is missing for the bounded packaging and workspace-map criteria. "
                "Actual host dependency setup and external source history were not tested and remain outside this evidence scope."
            )
            row["remaining_verification"] = (
                "The final HYG source/archive evidence and independent bounded audit pass the exact archive/member/source-byte "
                "and five-root workspace-map checks. Actual host dependency setup and external source history are outside this evidence scope."
            )
        if finding_id == "LA-023":
            row["code_outcome"] = (
                "The installed one-call CPU PPO path writes the expected result through tenant CAS and the runtime consumer. "
                "Separate zero-gradient refusal and initialize-reset controls pass. This does not establish cross-call typed "
                "continuation; Product-owner public .train scope and historical TrainingResult compatibility remain unresolved."
            )
            row["code_outcome_evidence"] = {
                "mode": "authored_criterion_summary_cited_by_deciding_receipts",
                "basis": "latest PLG source handoff, installed evidence, and root-approved bounded one-call scope",
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
                "Fresh installed CAT 8dfa probes exercise Academic's two-row producer through a complete 4D generation and "
                "ScholarKnowledgeStore readback, and Catalog's one-row graph/embedding producer through DatasetCatalogStore. "
                "Readers return the expected fixture IDs; removing a selected native index or deleting the contributing source row "
                "returns no result with markers retained. Native hnswlib is 0.8.0. The encoder is a fixture, not production weights."
            )
            row["code_outcome_evidence"] = {
                "mode": "authored_criterion_summary_cited_by_deciding_receipts",
                "basis": "late installed composition receipt, exact command/output, probe source-copy binding, and CAT/DFI source handoffs",
            }
            row["remaining_verification"] = (
                "The fresh installed fixture producer-to-reader path and native-index/source-row removal controls pass. "
                "Production corpus membership, immutable encoder/tokenizer/weight provenance, external source history, and "
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
            reason = f"Closed for the bounded, hash-bound criterion scope. The cited evidence shows: {code_outcome}"
        elif value == "limited":
            reason = f"Limited to the demonstrated criterion scope. Evidence: {code_outcome} Remaining boundary: {remaining}"
        else:
            reason = f"Held because {missing} Available candidate evidence is bounded as follows: {code_outcome}"
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
        "scope": "All 54 allocated C findings, evaluated against their original hash-bound criteria; historical status remains separate.",
        "counts": dict(sorted(counts.items())),
    }
    cut.pop("mandatory_pending_topics", None)
    cut["snapshot"] = {"branch": branch, "commit": head, "tree": tree}
    cut["audit_adjustments"].append(
        "Root assigned final criterion-scoped verdicts across all 54 rows after reading the complete table; all historical fields were preserved separately."
    )
    cut["audit_adjustments"].append(
        "LA-039 includes fresh installed CAT 8dfa Academic/Catalog producer-to-reader evidence and marker-kept-live native-index/source-row removals; fixture scope and post-run-only script hash grade remain explicit."
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
    parser.add_argument("--json", type=Path, default=Path("policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/C/C54-final-20261006-v10.json"))
    parser.add_argument("--markdown", type=Path, default=Path("policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/C/C54-final-20261006-v10.md"))
    args = parser.parse_args()
    root = args.repo_root.resolve() if args.repo_root else Path(git(Path.cwd(), "rev-parse", "--show-toplevel"))
    json_path = args.json if args.json.is_absolute() else root / args.json
    markdown_path = args.markdown if args.markdown.is_absolute() else root / args.markdown
    print(json.dumps(build(root, json_path, markdown_path), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
