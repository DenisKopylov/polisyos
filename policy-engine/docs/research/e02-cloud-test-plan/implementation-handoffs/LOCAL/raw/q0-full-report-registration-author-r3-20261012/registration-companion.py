#!/usr/bin/env python3
"""Virtual source candidate for a replayable, non-adjudicative E02 full report.

The registered companion is intentionally small: it composes the existing
canonical proposal emitter with the source-qualified full-occurrence builder
and the R2 whole-object consumer projection. It emits author/review evidence
only. A source-bound run requires every input and tool to be committed and
byte-identical to the selected HEAD; a final source freeze, candidate result,
semantic alignment, and G decision remain separate.
"""
from __future__ import annotations

import argparse
import collections
import copy
import hashlib
import importlib.util
import json
import re
import stat
import subprocess
import sys
import types
from pathlib import Path
from typing import Any


LOCAL = Path(
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL"
)
REGISTERED_TOOL = LOCAL / "emit_full_occurrence_proposals.py"
REPORT_BUILDER = LOCAL / "raw/q0-full-occurrence-report-author-20261011/virtual_emitter.py"
R1_PROJECTION = LOCAL / "raw/q0-whole-criterion-owner-binding-author-r1-20261012/virtual_projection.py"
R2_PROJECTION = LOCAL / "raw/q0-whole-criterion-owner-binding-author-r2-20261012/virtual_projection.py"
R1_DECLARATION = LOCAL / "raw/q0-whole-criterion-owner-binding-author-r1-20261012/preimage-declaration.json"
R2_DECLARATION = LOCAL / "raw/q0-whole-criterion-owner-binding-author-r2-20261012/preimage-declaration.json"
R2_DECISION_PACKET = LOCAL / "raw/q0-whole-criterion-owner-binding-author-r2-20261012/binding-decision-packet.json"
CANONICAL_EMITTER = LOCAL / "emit_proposals.py"
IDENTITY_HELPER = LOCAL / "raw/full-id-occurrence-identity-repair-r1-20261011/occurrence_identity.py"
OWNER_DRAFT = LOCAL / "crosswalk/occurrence-evaluations-draft.json"
ROOT_RECONCILIATION = LOCAL / "raw/q0-six-independent-reviews-identity-reconciliation-r152-20261012/reconciliation.json"

REPORT_INPUTS = (
    Path("policy-engine/docs/research/e02-cloud-test-plan/closure-decisions/coverage.json"),
    Path("policy-engine/docs/research/e02-cloud-test-plan/integration/connected-closeout-plan-2026-10-08/README.md"),
    Path("policy-engine/docs/research/e02-cloud-test-plan/integration/connected-closeout-plan-2026-10-08/tasks.json"),
    Path("policy-engine/docs/research/e02-cloud-test-plan/integration/connected-closeout-plan-2026-10-08/findings.json"),
    Path("policy-engine/docs/research/e02-cloud-test-plan/integration/connected-closeout-plan-2026-10-08/inputs.json"),
    Path("policy-engine/docs/research/e02-cloud-test-plan/execution-prompts/unified-local-2026-10-09/TASKS.json"),
    CANONICAL_EMITTER,
    IDENTITY_HELPER,
    LOCAL / "raw/build_final_author_proposal_report.py",
    OWNER_DRAFT,
    LOCAL / "crosswalk/full-id-prefreeze-current-proposal-intake-20261011-v1.json",
    LOCAL / "raw/full-id-evidence-intake-r9-20261011/full-id-evidence-intake.json",
    LOCAL / "crosswalk/full-id-current-source-readiness-1ab7d354-20261011.json",
    LOCAL / "crosswalk/final-author-proposal-report-readiness.md",
    LOCAL / "crosswalk/full-id-current-draft-readiness.md",
    LOCAL / "crosswalk/full-id-canonical-validation-r1-20261011.md",
    LOCAL / "crosswalk/full-id-evidence-intake-r9-20261011.md",
)

REVIEW_INPUTS = (
    (
        "review_bucket0_195",
        LOCAL / "reviews/q0-original-criterion-bucket0-independent-r1-20261012/independent-bucket0-review.json",
        "rows",
        65,
        "4e6b6ff56f6c24e7192939844d4124fb74a9e2c8cbe652a06c4a607a716254fc",
    ),
    (
        "review_bucket1_195",
        LOCAL / "reviews/q0-original-criterion-bucket1-independent-r1-20261012/bucket1-independent-review.json",
        "occurrences",
        65,
        "acbe9d3db1d0a8fe45c78f5688f695c0996c65d22cb788d1b401baad64405d4c",
    ),
    (
        "review_bucket2_195",
        LOCAL / "reviews/q0-original-criterion-bucket2-independent-r1-20261012/independent-bucket2-review.json",
        "rows",
        65,
        "2402e5a81c0c8b5df98623b43e8867f00df113ad334995fa3e7247fb0700305b",
    ),
    (
        "review_complement_bucket0_96",
        LOCAL / "reviews/q0-original-criterion-complement-bucket0-independent-r1-20261012/review.json",
        "rows",
        32,
        "a96c8c44df23d60b5c66ed5ea17b381615f0a7e2b839aa04e57f3d7dcaeac126",
    ),
    (
        "review_complement_bucket1_96",
        LOCAL / "reviews/q0-original-criterion-complement-bucket1-independent-r1-20261012/complement-bucket1-independent-review.json",
        "occurrences",
        32,
        "f5acf8ea7f3a37b0ec339ae993115d220deeb6cf91c2b84a1331163505e46b64",
    ),
    (
        "review_complement_bucket2_96",
        LOCAL / "reviews/q0-original-criterion-complement-bucket2-independent-r1-20261012/32-row-independent-review.json",
        "rows",
        32,
        "66dac818822ea9509657f797b40171069eb4cdd1474247b21b0f279dde930193",
    ),
)

ROOT_RECONCILIATION_SHA256 = "2159cf9492b938e7d0a75b3af21a5ed4812b70c74d7a217a4159b8eb51ab0fcb"
REVIEW_PROJECTION_REF = (
    LOCAL / "reviews/q0-whole-criterion-owner-binding-independent-r1-20261012.md",
    "9bce4024c717a967410cbe6be1f278088ccf8ab579de4bcefc8bdb99d86098b8",
)


class RegistrationError(ValueError):
    """Raised when the source registration or full report is not replayable."""


def sha256(raw: bytes) -> str:
    """Return the SHA-256 of exact bytes."""
    return hashlib.sha256(raw).hexdigest()


def stable_json(value: Any) -> bytes:
    """Serialize deterministic UTF-8 JSON without copying source prose."""
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def require(condition: bool, message: str) -> None:
    """Raise a narrow fail-closed diagnostic when an invariant is false."""
    if not condition:
        raise RegistrationError(message)


def run_git(root: Path, *args: str, input_bytes: bytes | None = None) -> bytes:
    """Run one Git read and return stdout, preserving stderr on failure."""
    result = subprocess.run(
        ["git", *args], cwd=root, input=input_bytes, capture_output=True, check=False
    )
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise RegistrationError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout


def repo_root() -> Path:
    """Locate the repository containing this source companion."""
    for parent in Path(__file__).resolve().parents:
        if (parent / "AGENTS.md").is_file() and (parent / "policy-engine").is_dir():
            return parent
    raise RegistrationError("repository root not found")


def tree_entry(root: Path, commit: str, rel: Path) -> tuple[str, str] | None:
    """Return the HEAD mode and blob for one exact path, if present."""
    raw = subprocess.run(
        ["git", "ls-tree", "-z", commit, "--", rel.as_posix()],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if raw.returncode:
        raise RegistrationError(f"git ls-tree failed for {rel.as_posix()}")
    if not raw.stdout:
        return None
    metadata, path = raw.stdout.rstrip(b"\0").split(b"\t", 1)
    mode, kind, oid = metadata.decode("ascii").split()
    require(kind == "blob" and path.decode("utf-8") == rel.as_posix(), f"unexpected HEAD entry for {rel.as_posix()}")
    return mode, oid


def source_file_record(root: Path, commit: str, rel: Path, *, strict: bool) -> dict[str, Any]:
    """Bind one regular source file to exact current HEAD bytes and mode."""
    path = root / rel
    require(path.exists() and not path.is_symlink() and path.is_file(), f"required source file missing or not regular: {rel.as_posix()}")
    raw = path.read_bytes()
    mode = f"{stat.S_IMODE(path.stat().st_mode):04o}"
    entry = tree_entry(root, commit, rel)
    if entry is None:
        require(not strict, f"source is not present in committed HEAD: {rel.as_posix()}")
        return {
            "path": rel.as_posix(),
            "bytes": len(raw),
            "sha256": sha256(raw),
            "filesystem_mode_octal": mode,
            "git_tree_mode": None,
            "git_blob": None,
            "source_commit": None,
            "availability": "local_readback_only_untracked",
        }
    git_mode, blob = entry
    head_raw = run_git(root, "show", f"{commit}:{rel.as_posix()}")
    diff = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", rel.as_posix()], cwd=root, check=False)
    exact = head_raw == raw and git_mode == ("100755" if mode == "0755" else "100644") and diff.returncode == 0
    require(exact or not strict, f"worktree/index bytes or mode differ from committed HEAD: {rel.as_posix()}")
    return {
        "path": rel.as_posix(),
        "bytes": len(raw),
        "sha256": sha256(raw),
        "filesystem_mode_octal": mode,
        "git_tree_mode": git_mode,
        "git_blob": blob,
        "source_commit": commit,
        "availability": "committed_HEAD_exact_bytes_and_mode" if exact else "local_readback_only_dirty_against_HEAD",
    }


def source_snapshot(root: Path, *, strict: bool) -> dict[str, Any]:
    """Read the complete report-input, review, and generator-source set."""
    branch = run_git(root, "symbolic-ref", "--short", "HEAD").decode().strip()
    commit = run_git(root, "rev-parse", "HEAD").decode().strip()
    tree = run_git(root, "rev-parse", "HEAD^{tree}").decode().strip()
    tool_paths = (
        CANONICAL_EMITTER,
        IDENTITY_HELPER,
        REPORT_BUILDER,
        R1_PROJECTION,
        R2_PROJECTION,
        R1_DECLARATION,
        R2_DECLARATION,
        R2_DECISION_PACKET,
    )
    registered_tool_paths = (REGISTERED_TOOL,) if strict or (root / REGISTERED_TOOL).exists() else ()
    all_paths = tuple(dict.fromkeys((*REPORT_INPUTS, *(row[1] for row in REVIEW_INPUTS), ROOT_RECONCILIATION, REVIEW_PROJECTION_REF[0], *tool_paths, *registered_tool_paths)))
    files = [source_file_record(root, commit, rel, strict=strict) for rel in all_paths]
    by_path = {row["path"]: row for row in files}
    for label, rel, rows_key, expected_count, expected_sha in REVIEW_INPUTS:
        row = by_path[rel.as_posix()]
        require(row["sha256"] == expected_sha, f"independent review bytes changed: {label}")
        document = json.loads((root / rel).read_text(encoding="utf-8"))
        rows = document.get(rows_key)
        require(isinstance(rows, list) and len(rows) == expected_count, f"review row denominator changed: {label}")
    reconciliation = by_path[ROOT_RECONCILIATION.as_posix()]
    require(reconciliation["sha256"] == ROOT_RECONCILIATION_SHA256, "root independent-review reconciliation bytes changed")
    projection_review = by_path[REVIEW_PROJECTION_REF[0].as_posix()]
    require(projection_review["sha256"] == REVIEW_PROJECTION_REF[1], "whole-criterion projection review bytes changed")
    r2_decision = by_path[R2_DECISION_PACKET.as_posix()]
    require(r2_decision["sha256"] == "ea9558b1556f4b1ab3d63c25b28009fa1829bb4d5c0bba4a89ac957f2375803f", "R2 decision packet bytes changed")
    return {
        "branch": branch,
        "commit": commit,
        "tree": tree,
        "status": "committed_source_snapshot_not_final_freeze" if strict else "local_readback_only_prototype_snapshot",
        "files": files,
        "report_input_count": len(REPORT_INPUTS),
        "independent_review_refs": len(REVIEW_INPUTS),
        "full_review_occurrences": sum(row[3] for row in REVIEW_INPUTS),
        "root_reconciliation_ref": {
            "path": ROOT_RECONCILIATION.as_posix(),
            "sha256": reconciliation["sha256"],
            "availability": reconciliation["availability"],
        },
    }


def import_path(name: str, path: Path) -> Any:
    """Load an existing local tool by exact source path."""
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RegistrationError(f"cannot import source tool: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def owner_binding_from_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Extract the committed owner-draft identity without implying alignment."""
    row = next(item for item in snapshot["files"] if item["path"] == OWNER_DRAFT.as_posix())
    committed = row["availability"] == "committed_HEAD_exact_bytes_and_mode"
    return {
        "path": row["path"],
        "bytes": row["bytes"],
        "sha256": row["sha256"],
        "filesystem_mode_octal": row["filesystem_mode_octal"],
        "git_tree_mode": row["git_tree_mode"],
        "git_blob": row["git_blob"],
        "tracked_path": committed,
        "would_be_blob_object_present": committed,
        "local_availability": "committed_exact_head" if committed else "available_local_readback_only_untracked",
        "source_commit": row["source_commit"],
        "qualification": "Exact path bytes and mode only; owner scope and original whole criterion remain distinct; this binding grants no authority or semantic alignment.",
    }


def committed_owner_function() -> str:
    """Return the consumer-side owner binding recomputation used after commit."""
    return '''def owner_input_source_binding() -> dict[str, Any]:
    """Recompute committed owner draft bytes, mode, blob, and source commit."""
    return _r3_owner_source_binding()

'''


def patch_owner_binding_runtime(source: bytes, *, committed: bool) -> bytes:
    """Adapt the R2 consumer's local-only draft check for a committed source run."""
    if not committed:
        return source
    text = source.decode("utf-8")
    pattern = re.compile(r"def owner_input_source_binding\(\) -> dict\[str, Any\]:\n.*?(?=def _validate_packet_r1\()", re.DOTALL)
    updated, count = pattern.subn(committed_owner_function(), text, count=1)
    require(count == 1, "R2 owner-binding consumer anchor changed; source review required")
    return updated.encode("utf-8")


def occurrence_keys(packet: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Return every occurrence identity without collapsing repeated finding IDs."""
    return [
        (
            row["identity"]["finding_id"],
            row["identity"]["occurrence_pointer"],
            row["identity"]["criterion_sha256"],
        )
        for finding in packet["findings"]
        for row in finding["occurrences"]
    ]


def independent_review_keys(root: Path) -> list[tuple[str, str, str]]:
    """Walk the six independent review artifacts' full occurrence identities."""
    keys: list[tuple[str, str, str]] = []
    for _, rel, rows_key, expected_count, _ in REVIEW_INPUTS:
        document = json.loads((root / rel).read_text(encoding="utf-8"))
        rows = document[rows_key]
        require(len(rows) == expected_count, f"review denominator changed: {rel.as_posix()}")
        for row in rows:
            identity = row.get("full_occurrence_identity") or row.get("identity") or row
            keys.append((identity["finding_id"], identity["occurrence_pointer"], identity["criterion_sha256"]))
    return keys


def run_complete_projection_controls(
    base: Any,
    builder: Any,
    packet: dict[str, Any],
    expected_keys: list[tuple[str, str, str]],
    owner_binding: dict[str, Any],
    source_index: dict[tuple[str, str, str], dict[str, Any]],
    draft: dict[str, Any],
) -> dict[str, Any]:
    """Exercise the source-bound comparator, including keep-markers probes."""
    original_controls = base.run_alignment_controls(
        packet, draft, base.DRAFT, source_index, builder.validate_packet, expected_keys
    )
    require(original_controls.get("status") == "PASS", "original criterion/owner binding controls failed")
    comparator = builder.validate_packet._r2_complete_owner_projection
    cache = builder.validate_packet._r2_expected_owner_projection_cache
    require(len(cache) == 1, "consumer did not recompute one complete current projection")
    expected_by_key = next(iter(cache.values()))
    rows = [row for finding in packet["findings"] for row in finding["occurrences"]]
    require(len(rows) == len(expected_keys) == 291, "full projection control denominator changed")
    sibling_fields = ("proxy_divergence", "readout", "remaining_quantity_or_dependency")
    per_row: list[dict[str, Any]] = []
    counts: dict[str, dict[str, int]] = {field: {"corrupt": 0, "remove": 0} for field in sibling_fields}
    for index, (row, key) in enumerate(zip(rows, expected_keys, strict=True)):
        field = sibling_fields[index % len(sibling_fields)]
        operation = "corrupt" if index % 2 == 0 else "remove"
        mutated = copy.deepcopy(row)
        if operation == "corrupt":
            mutated["whole_property"][field] = {"mutation": "keep all status markers"}
        else:
            del mutated["whole_property"][field]
        try:
            comparator(mutated, expected_by_key[key], index)
        except (AssertionError, KeyError, TypeError, ValueError) as exc:
            require("complete owner-derived whole_property differs" in str(exc), f"wrong rejection at occurrence {index}")
            result = "REJECTED_AS_REQUIRED"
        else:
            raise RegistrationError(f"consumer accepted whole-object sibling mutation at occurrence {index}")
        counts[field][operation] += 1
        per_row.append({"identity": {"finding_id": key[0], "occurrence_pointer": key[1], "criterion_sha256": key[2]}, "field": field, "operation": operation, "result": result})

    actual_consumer: list[dict[str, Any]] = []
    diagnostic = {row["identity"]["finding_id"]: i for i, row in enumerate(rows) if row["identity"]["finding_id"] in {"LA-033", "B26"}}
    require(set(diagnostic) == {"LA-033", "B26"}, "source-qualified diagnostic occurrences are missing")
    for finding_id in ("LA-033", "B26"):
        index = diagnostic[finding_id]
        key = expected_keys[index]
        for field in sibling_fields:
            for operation in ("corrupt", "remove"):
                mutated_packet = copy.deepcopy(packet)
                mutated_row = [row for finding in mutated_packet["findings"] for row in finding["occurrences"]][index]
                if operation == "corrupt":
                    mutated_row["whole_property"][field] = {"mutation": "keep all status markers"}
                else:
                    del mutated_row["whole_property"][field]
                control = base.expect_packet_rejection(f"registered_consumer_{finding_id}_{field}_{operation}", mutated_packet, expected_keys, builder.validate_packet)
                require("complete owner-derived whole_property differs" in control["reason"], f"actual consumer did not reject {finding_id}/{field}/{operation}")
                actual_consumer.append({"finding_id": finding_id, "field": field, "operation": operation, **control})

    binding_mutations = (
        ("remove_owner_source_binding", None),
        ("owner_source_sha256", {"sha256": "0" * 64}),
        ("owner_source_mode", {"filesystem_mode_octal": "0600"}),
        ("owner_source_blob", {"git_blob": "0" * 40}),
        ("owner_source_commit", {"source_commit": "0" * 40}),
        ("owner_source_availability", {"local_availability": "available_local_readback_only_untracked" if owner_binding["tracked_path"] else "committed_exact_head"}),
        ("owner_source_tracked_marker", {"tracked_path": not owner_binding["tracked_path"]}),
    )
    binding_results: list[dict[str, Any]] = []
    for label, replacement in binding_mutations:
        mutated_packet = copy.deepcopy(packet)
        if replacement is None:
            mutated_packet.pop("owner_input_source_binding", None)
        else:
            mutated_packet["owner_input_source_binding"].update(replacement)
        result = base.expect_packet_rejection(label, mutated_packet, expected_keys, builder.validate_packet)
        require("owner draft source binding differs from current" in result["reason"], f"owner source mutation was not rejected: {label}")
        binding_results.append({"name": label, **result})

    return {
        "schema": "policyos.e02.q0_registered_full_report_controls.r3.v1",
        "status": "PASS",
        "property": "The actual consumer recomputes the source-derived packet and rejects any changed or missing whole_property member for each complete occurrence identity.",
        "comparison": "generic complete-object equality over all current source-derived whole_property fields; no allowlist of only the tested fields",
        "canonical_occurrences": len(rows),
        "unique_full_occurrence_identities": len(set(expected_keys)),
        "review_rows": len(independent_review_keys(repo_root())),
        "whole_criterion_qualification_controls": original_controls,
        "all_row_sibling_controls": {"counts": counts, "rows": per_row, "status": "291/291 corrupt-or-remove rejected by the consumer comparator"},
        "actual_consumer_controls": actual_consumer,
        "owner_source_binding_controls": binding_results,
    }


def add_registration_metadata(
    packet: dict[str, Any], snapshot: dict[str, Any], owner_binding: dict[str, Any],
    controls: dict[str, Any], root: Path,
) -> None:
    """Bind current source and review refs while preserving non-authority states."""
    packet["source_checkpoint"] = {
        "branch": snapshot["branch"],
        "head": snapshot["commit"],
        "tree": snapshot["tree"],
        "source_freeze_status": "provisional_current_source_readback_not_final_freeze",
        "source_freeze_candidate_source": None,
        "qualification": "Current committed input/tool snapshot only; final candidate freeze and evaluation remain separate.",
    }
    packet["previous_provisional_report_checkpoint"] = {
        "report": (LOCAL / "raw/q0-full-occurrence-report-author-20261011/proposal-decision-packet.json").as_posix(),
        "sha256": "93c0ddd918e8d95502a2fdd4d85802065b3d9fdb75bd2d6f608bcd6080f28c0e",
        "head": "d24fdfc9d79ea109b4aa102cc6856a3cd8985583",
        "tree": "d9f977e7bd6c568f4a0e3f83195d9241a3e68f9a",
        "role": "prior provisional report origin only; never treated as current candidate source",
    }
    review_refs = []
    for label, rel, rows_key, expected_count, expected_sha in REVIEW_INPUTS:
        document = json.loads((root / rel).read_text(encoding="utf-8"))
        review_refs.append({
            "review_id": label,
            "path": rel.as_posix(),
            "sha256": expected_sha,
            "pointer": f"#/{rows_key}",
            "occurrence_rows": len(document[rows_key]),
            "qualification": "independent criterion review reference; not an outcome, closure, or alignment authority",
        })
    require(sum(row["occurrence_rows"] for row in review_refs) == 291, "six independent review denominators do not sum to 291")
    packet["independent_review_refs"] = review_refs
    packet["registration"] = {
        "producer": REGISTERED_TOOL.as_posix(),
        "canonical_producer_reused": CANONICAL_EMITTER.as_posix(),
        "full_occurrence_builder": REPORT_BUILDER.as_posix(),
        "whole_property_consumer_projection": R2_PROJECTION.as_posix(),
        "source_snapshot": snapshot,
        "owner_input_source_binding": owner_binding,
        "controls_status": controls["status"],
        "candidate_evaluation": "UNRUN for all 291 occurrences",
        "criterion_owner_alignment": "not_established for all 291 occurrences; scoped owner assertion remains separate",
        "formal_G": "not_adjudicated",
        "formal_closure_ids": [],
        "source_author_history": "198 historical source-author-closed IDs and B198 remain historical context; no current closure is inferred",
        "qualification": "source-registered author report only; no runtime/product capability, candidate result, semantic alignment, or formal closure claim",
    }
    # The packet's original per-occurrence next-check text, evidence references,
    # criteria hashes, task routes, historical statuses and closure fields stay
    # intact. Only the top-level current report source binding is refreshed.
    rows = [row for finding in packet["findings"] for row in finding["occurrences"]]
    require(len(rows) == 291, "registration metadata changed the occurrence denominator")
    require(all(row["candidate_evaluation"]["state"] == "UNRUN" for row in rows), "a candidate row was promoted from source metadata")
    require(all(row["whole_property"]["owner_assessed_property"] is None for row in rows), "owner scope leaked into whole-property authority")
    require(all(row["whole_property"]["criterion_owner_alignment"]["status"] == "not_established" for row in rows), "alignment was promoted from source metadata")
    require(packet["authority_boundary"]["formal_G"] == "not_adjudicated" and packet["authority_boundary"]["formal_closure_ids"] == [], "formal G state changed")


def build_registered_report(root: Path, *, strict: bool) -> tuple[bytes, bytes, dict[str, Any]]:
    """Build the full packet through the existing emitter and R2 consumer."""
    snapshot = source_snapshot(root, strict=strict)
    r1 = import_path("q0_registered_r1_projection", root / R1_PROJECTION)
    r2 = import_path("q0_registered_r2_projection", root / R2_PROJECTION)
    r2_declaration = r2.read_json(root, r2.DECLARATION)
    owner_binding = owner_binding_from_snapshot(snapshot)
    if not owner_binding["tracked_path"]:
        owner_binding = r2.owner_source_binding(root, r2_declaration)
    canonical_overlay, _fixture = r1.compose_fixture_emitter(root)
    source = (root / REPORT_BUILDER).read_bytes()
    patched = r2.r2_consumer_overlay(r1, r1.projection_overlay, source, owner_binding)
    patched = patch_owner_binding_runtime(
        patched, committed=owner_binding["tracked_path"]
    )
    builder = types.ModuleType("q0_registered_full_report_consumer")
    builder.__file__ = str((root / REPORT_BUILDER).resolve())
    exec(compile(patched.decode("utf-8"), builder.__file__, "exec"), builder.__dict__)
    original_import = builder.import_module

    def import_with_canonical(name: str, path: Path) -> Any:
        if name == "e02_registered_emit_proposals":
            return canonical_overlay
        return original_import(name, path)

    builder.import_module = import_with_canonical
    builder._r3_owner_source_binding = lambda: owner_binding
    packet, _source_declaration, expected_keys, identity = builder.build_packet()
    builder.validate_packet(packet, expected_keys)
    full_identity_controls = builder.run_negative_controls(packet, expected_keys, identity)
    require(full_identity_controls.get("status") == "PASS", "full occurrence identity/authority controls failed")
    require(len(expected_keys) == 291 and len(set(expected_keys)) == 291, "full occurrence identity denominator changed")
    require(len(packet["findings"]) == 282, "full finding ID denominator changed")
    require(collections.Counter(expected_keys) == collections.Counter(occurrence_keys(packet)), "source/report occurrence identity multiset differs")
    review_keys = independent_review_keys(root)
    require(len(review_keys) == 291 and len(set(review_keys)) == 291, "independent review identity denominator changed")
    require(collections.Counter(expected_keys) == collections.Counter(review_keys), "six independent review identities do not cover the full report identity multiset")
    require(packet["denominator"]["distinct_task_assignment_refs"] == 319, "task assignment reference denominator changed")
    require(packet["denominator"]["expanded_occurrence_route_refs"] == 331, "expanded route denominator changed")
    require(packet["authority_boundary"]["formal_closure_ids"] == [] and packet["authority_boundary"]["formal_G"] == "not_adjudicated", "formal closure state changed")
    require(packet["B198_preservation"]["finding_id"] == "B198" and packet["B198_preservation"]["formal_closure"] is False, "B198 historical boundary changed")
    declaration = r1.read_json(root, r1.DECLARATION)
    coverage = r1.read_json(root, r1.COVERAGE)
    historical_source_commit = declaration["criterion_owner_example"]["original_criterion"]["source_commit"]
    source_index, _source_audit = r1.coverage_source_index(root, coverage, historical_source_commit)
    draft = r1.read_json(root, r1.DRAFT)
    controls = run_complete_projection_controls(
        r1, builder, packet, expected_keys, owner_binding, source_index, draft
    )
    controls["full_occurrence_identity_controls"] = {
        "status": full_identity_controls["status"],
        "negative_control_count": len(full_identity_controls["negative_controls"]),
        "property": full_identity_controls["property"],
    }
    packet["registration_decision_ref"] = {
        "path": (R2_PROJECTION.parent / "binding-decision-packet.json").as_posix(),
        "sha256": "ea9558b1556f4b1ab3d63c25b28009fa1829bb4d5c0bba4a89ac957f2375803f",
        "role": "R2 source-qualified consumer decision; historical checkpoint only, not current freeze or authority",
    }
    add_registration_metadata(packet, snapshot, owner_binding, controls, root)
    builder.validate_packet(packet, expected_keys)
    controls_bytes = stable_json(controls)
    packet["registration_controls_ref"] = {
        "schema": controls["schema"],
        "sha256": sha256(controls_bytes),
        "qualification": "paired control output from this exact regeneration; no source text copied",
    }
    report_bytes = stable_json(packet)
    receipt = {
        "schema": "policyos.e02.q0_full_report_registration_self_check.r3.v1",
        "status": "PASS",
        "scope": "source-qualified local author report, no candidate execution, semantic alignment, runtime result, or formal G adjudication",
        "source_commit": snapshot["commit"],
        "source_tree": snapshot["tree"],
        "source_snapshot_status": snapshot["status"],
        "report_bytes": len(report_bytes),
        "report_sha256": sha256(report_bytes),
        "controls_bytes": len(controls_bytes),
        "controls_sha256": sha256(controls_bytes),
        "finding_ids": 282,
        "canonical_occurrences": 291,
        "independent_review_occurrences": 291,
        "distinct_task_assignment_refs": 319,
        "expanded_occurrence_routes": 331,
        "historical_source_author_closed_ids": 198,
        "B198": "historical context preserved; candidate UNRUN; formal closure false",
        "candidate_states": {"UNRUN": 291},
        "owner_assessed_property_non_null": 0,
        "criterion_owner_alignment": "not_established for all 291 occurrences",
        "formal_G": "not_adjudicated",
        "formal_closure_ids": [],
        "whole_projection_controls": controls["all_row_sibling_controls"]["status"],
        "actual_consumer_controls": len(controls["actual_consumer_controls"]),
        "source_snapshot_file_count": len(snapshot["files"]),
        "qualification": "current source readback only; not a root-approved final freeze",
    }
    return report_bytes, controls_bytes, receipt


def main(argv: list[str] | None = None) -> int:
    """Emit or check a source-bound full occurrence report and controls."""
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--emit", action="store_true", help="write new report and controls files")
    modes.add_argument("--check", action="store_true", help="recompute and byte-check report and controls")
    modes.add_argument("--self-check", action="store_true", help="run virtual local controls without claiming committed source")
    parser.add_argument("--output", type=Path, help="new report file inside LOCAL/crosswalk")
    parser.add_argument("--controls-output", type=Path, help="new controls file inside LOCAL/crosswalk")
    args = parser.parse_args(argv)
    root = repo_root()
    if args.self_check:
        report, controls, receipt = build_registered_report(root, strict=False)
        require(json.loads(report)["registration"]["source_snapshot"]["status"] == "local_readback_only_prototype_snapshot", "virtual self-check overstated source registration")
        print(json.dumps(receipt, ensure_ascii=False, indent=2))
        return 0
    require(args.output is not None and args.controls_output is not None, "--output and --controls-output are required")
    paths = (args.output, args.controls_output)
    absolute: list[Path] = []
    for relative in paths:
        require(not relative.is_absolute(), "output paths must be repository-relative")
        full = root / relative
        require(full.parent.is_dir() and not full.parent.is_symlink(), f"output parent must exist and not be a symlink: {relative}")
        try:
            full.parent.resolve(strict=True).relative_to((root / LOCAL / "crosswalk").resolve(strict=True))
        except (OSError, ValueError) as exc:
            raise RegistrationError("report outputs must be inside LOCAL/crosswalk") from exc
        absolute.append(full)
    require(absolute[0] != absolute[1], "report and controls output paths must differ")
    report, controls, receipt = build_registered_report(root, strict=True)
    expected = {absolute[0]: report, absolute[1]: controls}
    if args.emit:
        require(all(not path.exists() and not path.is_symlink() for path in expected), "emit refuses to overwrite existing report files")
        for path, raw in expected.items():
            path.write_bytes(raw)
    for path, raw in expected.items():
        require(path.is_file() and not path.is_symlink() and path.read_bytes() == raw, f"generated report byte drift: {path.relative_to(root)}")
    receipt["artifact_readback"] = [
        {"path": path.relative_to(root).as_posix(), "bytes": len(raw), "sha256": sha256(raw)}
        for path, raw in expected.items()
    ]
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
