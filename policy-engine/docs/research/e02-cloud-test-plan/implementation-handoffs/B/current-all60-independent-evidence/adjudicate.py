"""Compact the historical proposal without changing its sixty decisions.

Detailed derived inventories remain at the historical Git cut. The current receipt
keeps nonrecomputable decisions, counts, and source/check indices.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

HISTORICAL = "136457fc27968ebbfba795eb13fe28f6de7dad20"
PREFIX = "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/B/"
EVIDENCE = PREFIX + "current-all60-independent-evidence/"
RECEIPT = PREFIX + "current-all60-independent-adjudication.json"
CARDS = "policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/"


def git(*args: str) -> bytes:
    # Fixed Git executable and immutable repository metadata arguments; no shell.
    return subprocess.check_output(["/usr/local/bin/git", *args])  # noqa: S603


def source_blob(ref: str, path: str) -> bytes:
    return git("show", f"{ref}:{path}")


def identity(ref: str, path: str) -> dict:
    raw = source_blob(ref, path)
    return {
        "git_sha": ref,
        "path": path,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def main() -> None:
    head = git("rev-parse", "HEAD").decode().strip()
    old = json.loads(source_blob(HISTORICAL, RECEIPT))
    catalog = json.loads(source_blob(HISTORICAL, EVIDENCE + "evidence-catalog.json"))
    denominator = json.loads(source_blob(HISTORICAL, EVIDENCE + "denominator.json"))
    used = sorted(
        {(c["catalog_key"], c["index"]) for r in old["findings"] for c in r["deciding_checks"]}
    )
    receipt_index = {}
    for key, record in catalog["receipts"].items():
        current = identity(record["git_sha"], record["path"])
        if current["sha256"] != record["sha256"] or current["bytes"] != record["bytes"]:
            raise ValueError("Historical receipt identity changed")
        receipt_index[key] = current
    source_shas = sorted(
        {catalog["receipts"][key]["checks"][index]["target_sha"] for key, index in used}
    )
    source_ids = {sha: f"s{i}" for i, sha in enumerate(source_shas)}
    sources = {
        source_ids[sha]: {
            "sha": sha,
            "tree": git("rev-parse", sha + "^{tree}").decode().strip(),
        }
        for sha in source_shas
    }
    check_index = {}
    for key, index in used:
        check = catalog["receipts"][key]["checks"][index]
        check_index[f"{key}:{index}"] = {
            "receipt": key,
            "pointer": check["receipt_pointer"],
            "source": source_ids[check["target_sha"]],
            "outcome": check["outcome"],
        }
    decision_keys = [
        "finding_id",
        "bundle_id",
        "criterion",
        "technical_property_proposal",
        "finding_status_proposal",
        "actual_distinguishing_observation",
        "remaining_consumer_or_contract",
        "next_owner",
    ]
    rows = []
    for original in old["findings"]:
        row = {key: original[key] for key in decision_keys}
        criterion = original["canonical_criterion"]
        row["canonical_criterion"] = {
            key: criterion[key] for key in ("line_begin", "line_end", "source_block_sha256")
        }
        row["deciding_checks"] = [
            f"{c['catalog_key']}:{c['index']}" for c in original["deciding_checks"]
        ]
        rows.append(row)
        if any(row[key] != original[key] for key in decision_keys):
            raise ValueError("A nonrecomputable decision changed")
    if len(rows) != 60 or len({row["finding_id"] for row in rows}) != 60:
        raise ValueError("The sixty finding denominator changed")
    if len({row["bundle_id"] for row in rows}) != 25 or len(check_index) != 127:
        raise ValueError("Bundle or deciding-check denominator changed")
    copied = [
        "reviewer",
        "root_source_sha",
        "root_source_tree",
        "root_source_qualification",
        "newer_exact_owner_source_refs",
        "denominators",
        "finding_status_proposal_counts",
        "technical_property_proposal_counts",
        "formal_closure_authority",
        "closure_ids",
        "metadata_audit",
        "status_semantics",
        "nonblocking_scope_boundaries",
        "property",
        "predicate_basis",
        "capability_state_or_finding_state",
        "limitations_and_next_owner",
    ]
    output = {key: old[key] for key in copied}
    output["metadata_audit"] = {
        "source_cut": HISTORICAL,
        "original_detailed_intake": old["metadata_audit"],
        "current_compaction": (
            "Preserves60 semantic decisions, resolves127 unique check references, and "
            "rechecks26 original receipt identities. Historical runtime/output-byte checks "
            "remain bound to their original sources; this is not a fresh product verification."
        ),
    }
    output.update(
        {
            "schema": "policyos.e02.implementation_handoff.v1",
            "unit": "B",
            "slice": "current-all60-independent-adjudication-compact",
            "independent_schema": "polisyos.e02.B.current-all60-independent-adjudication.v2",
            "slice_base_sha": HISTORICAL,
            "implementation_commits": [head],
            "candidate_tree_sha": git("rev-parse", head + "^{tree}").decode().strip(),
            "branch": "codex/e02-B-current-durability",
            "pull_request": old["pull_request"],
            "changed_paths": git("diff", "--name-only", HISTORICAL, head).decode().splitlines(),
            "bundle_ids": old["bundle_ids"],
            "baseline_cells": [],
            "mode": "Forward-only metadata compaction; no new runtime/source/test verification.",
            "decision_source_cut": identity(HISTORICAL, RECEIPT),
            "derived_audit_source_cut": {
                "git_sha": HISTORICAL,
                "evidence_directory": EVIDENCE,
                "files": ["denominator.json", "evidence-catalog.json"],
                "meaning": "Historical derivable audit, not retained again in the current tree.",
            },
            "canonical_source_basis": {
                "git_sha": "69780761ae091d8fcc6ab8778c7f5f7227eeef0b",
                "card_path_template": CARDS + "bundles/{bundle_id}.md",
                "criterion_locator": "Per finding SOURCE_BEGIN/SOURCE_END block, lines and hash.",
            },
            "baseline_source_basis": {
                "git_sha": old["root_source_sha"],
                "plan_directory": "policy-engine/docs/research/e02-cloud-test-plan/",
                "allocation": "execution-organization/{finding,bundle}-owners.tsv",
                "finding_cell_join": "full-run/finding-routes.json",
                "source_environment_inputs": "results/{cells.tsv,events.jsonl,sources.json}",
                "meaning": "Navigation only; no baseline PASS attests a new source.",
            },
            "scripts": [
                identity(head, EVIDENCE + name)
                for name in ("denominator.py", "audit_evidence.py", "adjudicate.py")
            ],
            "requested_baseline_query": identity(head, EVIDENCE + "requested-failures-query.json"),
            "receipt_index": receipt_index,
            "execution_source_index": sources,
            "check_index": check_index,
            "check_basis": {
                "command_environment_input_output": (
                    "Resolve each check through receipt_index[receipt].git_sha:path#pointer. "
                    "That immutable original check and its committed wrapper/test/probe artifacts "
                    "provide actual command, environment, input/overlay and complete output bytes."
                ),
                "missing_inline_input": (
                    "Retain the original top-level input_closure or bound wrapper argv/test-source "
                    "identity; do not synthesize production/backend authority. "
                    "Detailed reconciliation is available at the historical audit cut "
                    "and reproducible by audit_evidence.py."
                ),
                "artifact_authority": (
                    "Existing original Git objects retain all moderate deciding "
                    "outputs and hashes. "
                    "No duplicated logs or artifact inventory is published by this compaction."
                ),
            },
            "all_rows_qualification": {
                "technical_scope": old["findings"][0]["technical_scope"],
                "closure_applied": False,
                "root_joint_source_acceptance": "pending",
                "closure_reason": old["findings"][0]["closure_reason"],
            },
            "compaction_verification": {
                "nonrecomputable_decisions_preserved": 60,
                "unique_deciding_checks": 127,
                "repeated_old_check_entries": 241,
                "original_receipt_identities_verified": 26,
                "original_derived_inventories_preserved_at": HISTORICAL,
            },
            "findings": rows,
            "checks": [
                {
                    "command": [sys.executable, EVIDENCE + "adjudicate.py"],
                    "target_sha": head,
                    "environment": {
                        "cwd": str(Path.cwd()),
                        "python": sys.version,
                        "execution_kind": "Git/stdlib metadata reconciliation only",
                    },
                    "input_closure": {
                        "decision_cut": HISTORICAL,
                        "original_receipts": 26,
                        "root_source_cut": old["root_source_sha"],
                    },
                    "outcome": "PASS",
                    "output": (
                        "60 decisions preserved; 25 bundles; 127 unique checks; 26 receipt hashes."
                    ),
                }
            ],
        }
    )
    if (
        dict(Counter(r["finding_status_proposal"] for r in rows))
        != old["finding_status_proposal_counts"]
    ):
        raise ValueError("Proposal counts changed")
    if denominator["counts"] != old["denominators"] or output["closure_ids"]:
        raise ValueError("Historical allocation or no-closure qualification changed")
    Path(RECEIPT).write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    sys.stdout.write(json.dumps(output["compaction_verification"]) + "\n")


if __name__ == "__main__":
    main()
