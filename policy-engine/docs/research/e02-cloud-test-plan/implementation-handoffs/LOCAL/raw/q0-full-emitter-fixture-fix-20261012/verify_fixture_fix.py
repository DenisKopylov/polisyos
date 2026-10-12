#!/usr/bin/env python3
"""Verify a zero-fuzz virtual repair of the registered emitter self-check fixture.

This tool applies the proposed source delta in memory only. It never writes the
canonical emitter, proposal ledger, receipt, index, or tracked source tree.
"""
from __future__ import annotations

import argparse
import collections
import contextlib
import copy
import difflib
import hashlib
import importlib.util
import io
import json
import subprocess
import sys
import types
from pathlib import Path
from typing import Any

LEASE_REL = Path(
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/"
    "q0-full-emitter-fixture-fix-20261012"
)
DECLARATION_REL = LEASE_REL / "preimage-declaration.json"
PATCH_REL = LEASE_REL / "fixture_patch.diff"
ENV_REL = LEASE_REL / "synthetic-environment.json"
CHECKS_REL = LEASE_REL / "checks"
NEGATIVE_REL = CHECKS_REL / "negative-controls.json"
MANIFEST_REL = CHECKS_REL / "full-manifest.json"
PROPERTY_GAP_DECL_REL = LEASE_REL / "property-gap-inventory-preimage-declaration.json"
PROPERTY_GAP_INVENTORY_REL = CHECKS_REL / "full-occurrence-property-gap-inventory.json"
EMITTER_REL = Path(
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/emit_proposals.py"
)
REPORT_DIR_REL = Path(
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/"
    "q0-full-occurrence-report-author-20261011"
)
REPORT_RUNNER_REL = REPORT_DIR_REL / "virtual_emitter.py"
REPORT_PACKET_REL = REPORT_DIR_REL / "proposal-decision-packet.json"
REPORT_CONTROLS_REL = REPORT_DIR_REL / "controls.json"
REPORT_MANIFEST_REL = REPORT_DIR_REL / "full-manifest.json"
OLD_REPORT_CHECKPOINT = {
    "commit": "00c200c2ec33786a80dd41209eca46a2539dac5c",
    "tree": "5ba74fcb78e28d61be21f3208ee7a4b42665b6fe",
    "branch": "codex/e02-unified-local-20261009",
}
INITIAL_SOURCE = {
    "branch": "codex/e02-unified-local-20261009",
    "head": "d24fdfc9d79ea109b4aa102cc6856a3cd8985583",
    "tree": "d9f977e7bd6c568f4a0e3f83195d9241a3e68f9a",
}
ROOT_ADVANCE = {
    "commit": "b16a69e6f8cae05ed4f97ae8654822810319c062",
    "tree": "8e92cd8ab1d8bff5d49bb5f099b1fadda3492696",
    "parent": "d24fdfc9d79ea109b4aa102cc6856a3cd8985583",
    "paths": [
        ("A", "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/linux-profile/raw/sitecustomize.py"),
        ("M", "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/installed-wave-recipe.md"),
        ("A", "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw/q2-freeze-input-audit-v2-20261011.py"),
        ("M", "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw/run.py"),
        ("A", "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw/supplemental-manifest.json"),
        ("A", "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw/supplemental_run.py"),
        ("A", "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw/test_timeout_driver.py"),
        ("M", "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw/timeout_driver.py"),
    ],
    "ordered_status_path_sha256": "7613ed8dbbf3c9859aaed6e89053ceab3d1060806840960c3a09fe17232afbcc",
    "file_type_denominator": {"json": 1, "md": 1, "py": 6},
}
PREVIOUS_RECEIPT_SHA256 = "8432c6cf416a55fb497c3068b0d2e39ab42a91467b13a852ad5d14ad2bcedcbc"
PREVIOUS_SCRIPT_SHA256 = "dcf5fd5823c1190f949d5c9afa5b28f44b2ec763971626d0e7e482eea1470778"


def repo_root() -> Path:
    """Find the repository root from this packet's path."""
    for parent in Path(__file__).resolve().parents:
        if (parent / "AGENTS.md").is_file() and (parent / "policy-engine").is_dir():
            return parent
    raise RuntimeError("repository root not found")


def sha256(data: bytes) -> str:
    """Return lowercase SHA-256 for exact bytes."""
    return hashlib.sha256(data).hexdigest()


def read_json(root: Path, relative: str | Path) -> dict[str, Any]:
    """Read one JSON object."""
    value = json.loads((root / relative).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {relative}")
    return value


def stable_json(value: Any) -> bytes:
    """Serialize exact stable UTF-8 JSON."""
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def require(condition: bool, message: str) -> None:
    """Fail with a specific verification diagnostic."""
    if not condition:
        raise ValueError(message)


def verify_bound_bytes(data: bytes, expected: dict[str, Any], label: str) -> None:
    """Apply the exact byte-count and SHA-256 preimage gate to supplied bytes."""
    require(len(data) == expected["bytes"], f"{label} byte count differs from its declared preimage")
    require(sha256(data) == expected["sha256"], f"{label} SHA-256 differs from its declared preimage")


def git_text(root: Path, *args: str) -> str:
    """Run one read-only Git query and decode its result."""
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def source_identity(root: Path) -> dict[str, str]:
    """Return current committed source identity."""
    return {"commit": git_text(root, "rev-parse", "HEAD"), "tree": git_text(root, "rev-parse", "HEAD^{tree}")}


def source_delta(root: Path, base: str, head: str) -> tuple[list[tuple[str, str]], dict[str, int], str]:
    """Recompute a complete, no-renames committed path denominator."""
    text = subprocess.check_output(
        ["git", "diff", "--name-status", "--no-renames", base, head, "--"],
        cwd=root,
        text=True,
    )
    rows = [tuple(line.split("\t", 1)) for line in text.splitlines()]
    counts: collections.Counter[str] = collections.Counter()
    for _, path in rows:
        name = Path(path).name.lower()
        suffix = "json.gz" if name.endswith(".json.gz") else Path(name).suffix.removeprefix(".")
        counts[suffix or "extensionless"] += 1
    digest = sha256("".join(f"{status}\t{path}\n" for status, path in rows).encode())
    return rows, dict(sorted(counts.items())), digest


def verify_root_advance(root: Path, declared: dict[str, Any]) -> dict[str, Any]:
    """Accept only the observed direct, non-intersecting Q2 source advance."""
    branch = git_text(root, "symbolic-ref", "--short", "HEAD")
    current = source_identity(root)
    require(branch == INITIAL_SOURCE["branch"], "branch changed from declared source branch")
    expected = declared["observed_source"]
    require(
        {key: expected.get(key) for key in ("branch", "head", "tree")} == INITIAL_SOURCE,
        "initial d24 preimage checkpoint was rewritten",
    )
    if current == {"commit": INITIAL_SOURCE["head"], "tree": INITIAL_SOURCE["tree"]}:
        rows, types, digest = source_delta(root, INITIAL_SOURCE["head"], INITIAL_SOURCE["head"])
        return {"branch": branch, "head": current["commit"], "tree": current["tree"], "base": INITIAL_SOURCE["head"], "changed_paths": 0, "file_type_denominator": types, "ordered_status_path_sha256": digest, "declared_input_intersection": []}
    require(current == {"commit": ROOT_ADVANCE["commit"], "tree": ROOT_ADVANCE["tree"]}, "HEAD moved beyond the declared d24 checkpoint and verified root advance")
    require(git_text(root, "rev-parse", "HEAD^") == ROOT_ADVANCE["parent"], "root source advance is not the declared direct child")
    rows, types, digest = source_delta(root, INITIAL_SOURCE["head"], current["commit"])
    require(rows == ROOT_ADVANCE["paths"], "the complete d24-to-current committed delta differs from the verified root advance")
    require(types == ROOT_ADVANCE["file_type_denominator"], "d24-to-current file-type denominator changed")
    require(digest == ROOT_ADVANCE["ordered_status_path_sha256"], "d24-to-current ordered status/path digest changed")
    input_paths = {item["path"] for item in declared["source_preimages"]}
    intersection = sorted(input_paths & {path for _, path in rows})
    require(not intersection, f"root advance intersects declared Q0 source preimages: {intersection}")
    return {
        "branch": branch,
        "base": INITIAL_SOURCE["head"],
        "head": current["commit"],
        "tree": current["tree"],
        "parent": ROOT_ADVANCE["parent"],
        "changed_paths": len(rows),
        "file_type_denominator": types,
        "ordered_status_path_sha256": digest,
        "complete_paths": [{"status": status, "path": path} for status, path in rows],
        "declared_input_intersection": intersection,
        "interpretation": "Verified root Q2 source-availability commit; preserve the original d24 report checkpoint and record this descendant delta. No declared Q0 source preimage changed. This is not the final/global candidate source freeze.",
    }


def declaration(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Verify declared input bytes and the allowed source checkpoint movement."""
    value = read_json(root, DECLARATION_REL)
    require(value.get("status") == "PREIMAGES_VERIFIED_TARGETS_ABSENT_BEFORE_VIRTUAL_PATCH", "preimage declaration status changed")
    for item in value["source_preimages"]:
        data = (root / item["path"]).read_bytes()
        verify_bound_bytes(data, item, f"source preimage {item['path']}")
    emitter = root / EMITTER_REL
    data = emitter.read_bytes()
    expected = value["canonical_emitter"]
    verify_bound_bytes(data, expected, "canonical emitter")
    advance = verify_root_advance(root, value)
    return value, advance


def fixture_environment(candidate: dict[str, str]) -> bytes:
    """Return bound synthetic validator-shape metadata, never runtime evidence."""
    value = {
        "schema": "policyos.e02.self_check_backend_environment_fixture.v1",
        "purpose": "validator-shape-only; not an executed backend or candidate evidence",
        "authority": "none",
        "candidate_source": candidate,
    }
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def replacement_blocks(env_digest: str, candidate: dict[str, str], *, include_profile: bool = True, include_cwd: bool = True, extra_profile_field: bool = False, corrupt_candidate: bool = False) -> tuple[bytes | None, bytes, bytes | None, bytes]:
    """Render the exact old/new synthetic fixture blocks required by the schema."""
    old_profile = b'        "backend_profile": {"status": "named"},'
    if include_profile:
        ref_candidate = {"commit": "0" * 40, "tree": candidate["tree"]} if corrupt_candidate else candidate
        profile: dict[str, Any] = {
            "backend_id": "self-check-backend",
            "profile_id": "self-check-profile",
            "environment_sha256": env_digest,
            "environment_manifest_ref": {
                "storage": "ignored_local_raw",
                "path": (LEASE_REL / ENV_REL.name).as_posix(),
                "sha256": env_digest,
                "candidate_source": ref_candidate,
                "availability": "available_local_readback",
            },
        }
        if extra_profile_field:
            profile["unexpected_status"] = "named"
        serialized = json.dumps(profile, ensure_ascii=False, indent=4)
        inner_lines = serialized.splitlines()[1:-1]
        body = "\n".join("        " + line for line in inner_lines)
        new_profile = ("        \"backend_profile\": {\n" + body + "\n        },").encode()
    else:
        new_profile = old_profile

    old_command = (
        b'                "argv": ["python", "-m", "pytest"],\n'
        b'                "status": "PASS",'
    )
    command_lines = [b'                "argv": ["python", "-m", "pytest"],']
    if include_cwd:
        command_lines.append(b'                "cwd": "policy-engine",')
    command_lines.append(b'                "status": "PASS",')
    new_command = b"\n".join(command_lines)
    return old_profile if include_profile else None, new_profile, old_command if include_cwd else None, new_command


def build_overlay(source: bytes, env_digest: str, candidate: dict[str, str], **options: Any) -> bytes:
    """Apply each source replacement exactly once; any drift fails closed."""
    old_profile, new_profile, old_command, new_command = replacement_blocks(env_digest, candidate, **options)
    changed = source
    if old_profile is not None:
        count = changed.count(old_profile)
        require(count == 1, f"backend_profile fixture preimage count is {count}, expected 1")
        changed = changed.replace(old_profile, new_profile, 1)
    if old_command is not None:
        count = changed.count(old_command)
        require(count == 1, f"command fixture preimage count is {count}, expected 1")
        changed = changed.replace(old_command, new_command, 1)
    return changed


def unified_patch(before: bytes, after: bytes) -> bytes:
    """Produce a small exact-context patch with source blob identities."""
    diff = "".join(difflib.unified_diff(
        before.decode("utf-8").splitlines(keepends=True),
        after.decode("utf-8").splitlines(keepends=True),
        fromfile=f"a/{EMITTER_REL.as_posix()}",
        tofile=f"b/{EMITTER_REL.as_posix()}",
        n=3,
    ))
    def git_blob(data: bytes) -> str:
        return subprocess.check_output(["git", "hash-object", "--stdin"], input=data).decode().strip()
    prefix = f"diff --git a/{EMITTER_REL.as_posix()} b/{EMITTER_REL.as_posix()}\nindex {git_blob(before)}..{git_blob(after)} 100644\n"
    return (prefix + diff).encode()


def apply_check(root: Path, patch: bytes) -> tuple[int, bytes, bytes]:
    """Run Git's non-mutating strict patch checker (zero fuzz)."""
    result = subprocess.run(["git", "apply", "--check", "--verbose"], cwd=root, input=patch, capture_output=True, check=False)
    return result.returncode, result.stdout, result.stderr


def run_cli(root: Path, args: list[str]) -> tuple[int, bytes, bytes, list[str]]:
    """Run an exact source-bound CLI and capture complete stdout/stderr."""
    argv = ["python3", "-B", *args]
    result = subprocess.run(argv, cwd=root, capture_output=True, check=False)
    return result.returncode, result.stdout, result.stderr, argv


def run_in_memory(root: Path, source: bytes, args: list[str]) -> tuple[int, bytes, bytes, str | None]:
    """Invoke the registered emitter main against a supplied in-memory source."""
    name = f"_e02_fixture_overlay_{sha256(source)[:12]}"
    module = types.ModuleType(name)
    module.__file__ = str((root / EMITTER_REL).resolve())
    module.__package__ = None
    sys.modules[name] = module
    exec(compile(source.decode("utf-8"), module.__file__, "exec"), module.__dict__)
    saved_argv = sys.argv
    stdout, stderr = io.StringIO(), io.StringIO()
    try:
        sys.argv = [module.__file__, *args]
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = module.main()
        return int(code or 0), stdout.getvalue().encode(), stderr.getvalue().encode(), None
    except SystemExit as exc:
        return int(exc.code or 0), stdout.getvalue().encode(), stderr.getvalue().encode(), None
    except Exception as exc:
        return 1, stdout.getvalue().encode(), stderr.getvalue().encode(), f"{type(exc).__name__}: {exc}"
    finally:
        sys.argv = saved_argv


def report_rebuild_check(root: Path) -> tuple[dict[str, Any], bytes]:
    """Rebuild all 291 rows from the registered producer and exact helper, without writing."""
    runner_path = root / REPORT_RUNNER_REL
    spec = importlib.util.spec_from_file_location("e02_q0_full_report_rebuild", runner_path)
    require(spec is not None and spec.loader is not None, "cannot import the actual full report emitter")
    report = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = report
    spec.loader.exec_module(report)
    current_packet, _, expected_keys, identity = report.build_packet()
    persisted = report.read_json(root, report.PACKET_REL)
    prior_checkpoint = copy.deepcopy(persisted["source_checkpoint"])
    normalized = copy.deepcopy(current_packet)
    normalized["source_checkpoint"] = prior_checkpoint
    current_checkpoint = {
        "branch": current_packet["source_checkpoint"]["branch"],
        **copy.deepcopy(current_packet["source_checkpoint"]["source_freeze_candidate_source"]),
    }
    checkpoint_bindings = 0
    for current_finding, prior_finding in zip(normalized["findings"], persisted["findings"]):
        require(len(current_finding["occurrences"]) == len(prior_finding["occurrences"]), "finding occurrence quantity changed during rebuild")
        for current_occurrence, prior_occurrence in zip(current_finding["occurrences"], prior_finding["occurrences"]):
            current_boundary = current_occurrence["candidate_evaluation"]["boundary"]
            prior_boundary = prior_occurrence["candidate_evaluation"]["boundary"]
            require(current_boundary.get("report_checkpoint") == current_checkpoint, "an occurrence checkpoint is not bound to the current report input")
            prior_checkpoint_binding = prior_boundary.get("report_checkpoint")
            require(isinstance(prior_checkpoint_binding, dict), "persisted occurrence report checkpoint is missing")
            current_boundary["report_checkpoint"] = copy.deepcopy(prior_checkpoint_binding)
            checkpoint_bindings += 1
    require(normalized == persisted, "current Q0 source inputs change report content beyond the recorded checkpoint bindings")
    report.validate_packet(persisted, expected_keys)
    controls = report.run_negative_controls(persisted, expected_keys, identity)
    saved_controls = report.read_json(root, report.CONTROLS_REL)
    require(controls == saved_controls, "full report negative controls differ from a fresh run")
    rows = report.packet_occurrence_rows(persisted)
    require(len(rows) == 291, "full report does not preserve 291 occurrence rows")
    with_next = sum(
        isinstance(row.get("next_check", {}).get("after_final_source_freeze"), dict)
        and isinstance(row.get("next_check", {}).get("owner_exact_next_check"), dict)
        for row in rows
    )
    require(with_next == 291, "some occurrence lacks its individual criterion-specific next check")
    owner_refs = [
        row["next_check"]["owner_exact_next_check"].get("owner_specific_ref", {}).get("owner_packet_ref")
        for row in rows
    ]
    require(sum(isinstance(ref, str) and bool(ref) for ref in owner_refs) == 290, "expected 290 source-owner next-check bindings")
    require(len({ref for ref in owner_refs if isinstance(ref, str) and ref}) == 290, "owner next-check refs are not occurrence-distinct")
    historical_command_rows = [
        row for row in rows
        if "command_after_final_freeze" in row["next_check"]["owner_exact_next_check"]
    ]
    require(
        len(historical_command_rows) == 1
        and historical_command_rows[0]["identity"]["finding_id"] == "B198"
        and historical_command_rows[0]["next_check"]["owner_exact_next_check"].get("expected_discriminator"),
        "the unique preserved B198 command-specific next check changed",
    )
    whole_property_records = sum(
        isinstance(row.get("whole_property"), dict)
        and isinstance(row["whole_property"].get("original_acceptance_boundary"), dict)
        and bool(row["whole_property"].get("remaining_quantity_or_dependency"))
        for row in rows
    )
    owner_property_counts: collections.Counter[str] = collections.Counter()
    for row in rows:
        current = row.get("whole_property", {}).get("bounded_mechanism_or_path", {})
        if current.get("property"):
            owner_property_counts["property"] += 1
        elif current.get("property_title_or_boundary"):
            owner_property_counts["property_title_or_boundary"] += 1
        elif current.get("bounded_property"):
            owner_property_counts["bounded_property"] += 1
        elif current.get("D45_runtime_property"):
            owner_property_counts["D45_runtime_property_not_substituted_for_original_criterion"] += 1
        else:
            owner_property_counts["property_not_established_by_owner_row"] += 1
    require(whole_property_records == 291, "some occurrence lacks a whole-property boundary/dependency record")
    require(sum(owner_property_counts.values()) == 291, "property-source classification does not cover every occurrence")
    require(owner_property_counts == collections.Counter({
        "property": 96,
        "property_title_or_boundary": 59,
        "bounded_property": 36,
        "D45_runtime_property_not_substituted_for_original_criterion": 46,
        "property_not_established_by_owner_row": 54,
    }), "whole-property source-field composition changed")
    no_criterion_copy = all(row.get("original_criterion_source", {}).get("criterion_text_copied") is False for row in rows)
    require(no_criterion_copy, "original criterion text was copied into the packet")
    readiness_metadata = all(
        row.get("source_qualified_readiness", {}).get("qualification")
        == "prior source-readiness snapshot; its candidate checkpoint is not this report checkpoint"
        and row.get("source_qualified_readiness", {}).get("source_candidate_evaluation") == "UNRUN"
        for row in rows
    )
    require(readiness_metadata, "prior readiness checkpoint is missing its non-current/UNRUN qualification")
    output = {
        "status": "PASS",
        "method": "registered emitter load_sources/build_ledger/validate_ledger plus generic occurrence_identity helper; all rebuilt in memory; persisted draft retained at its original provisional d24 checkpoint",
        "current_rebuild_checkpoint": current_packet["source_checkpoint"],
        "persisted_report_checkpoint": prior_checkpoint,
        "source_checkpoint_delta_only": True,
        "occurrence_checkpoint_bindings_normalized": checkpoint_bindings,
        "finding_ids": current_packet["denominator"]["finding_ids"],
        "occurrences": len(rows),
        "unique_full_keys": len(set(expected_keys)),
        "candidate_states": current_packet["status_summary"]["candidate_evaluation_by_occurrence"],
        "formal_closure_ids": current_packet["authority_boundary"]["formal_closure_ids"],
        "route_assignments": current_packet["denominator"]["distinct_task_assignment_refs"],
        "expanded_occurrence_route_refs": current_packet["denominator"]["expanded_occurrence_route_refs"],
        "per_occurrence_next_checks": with_next,
        "distinct_owner_next_check_refs": 290,
        "preserved_B198_command_specific_next_check": True,
        "whole_property_boundary_and_dependency_records": whole_property_records,
        "owner_property_source_field_counts": dict(sorted(owner_property_counts.items())),
        "property_source_qualification": "Property-bearing owner fields remain source assessments, not candidate adjudications. D45 runtime property is not substituted for the original occurrence. Rows without an eligible owner property field remain not established.",
        "criteria_text_copied": not no_criterion_copy,
        "prior_readiness_artifact_checkpoint_accepted_as_current_source": False,
        "negative_control_count": len(controls["negative_controls"]),
        "negative_controls": controls,
        "historical_full_report_check": {
            "path": (REPORT_DIR_REL / "checks/virtual-emitter-check.stdout.txt").as_posix(),
            "qualification": "previous fresh --check at the pinned d24 report checkpoint; not replayed as if it were the b16 final source freeze",
        },
    }
    return output, stable_json(output)


def build_property_gap_inventory(
    root: Path,
    packet: dict[str, Any],
    candidate: dict[str, str],
) -> tuple[dict[str, Any], bytes]:
    """Build row-level source references for missing owner property fields."""
    declared = read_json(root, PROPERTY_GAP_DECL_REL)
    require(declared.get("status") == "SOURCE_AND_ABSENT_TARGET_PREIMAGES_VERIFIED_BEFORE_INVENTORY_GENERATION", "property-gap preimage declaration status changed")
    for item in declared["source_preimages"]:
        data = (root / item["path"]).read_bytes()
        require(len(data) == item["bytes"] and sha256(data) == item["sha256"], f"property-gap source preimage changed: {item['path']}")
    require(declared["current_committed_source"]["head"] == candidate["commit"], "property-gap current source checkpoint changed")
    packet_bytes = (root / REPORT_PACKET_REL).read_bytes()
    packet_sha = sha256(packet_bytes)
    rows: list[dict[str, Any]] = []
    owner_property_present = 0
    for finding_index, finding in enumerate(packet["findings"]):
        for occurrence_index, occurrence in enumerate(finding["occurrences"]):
            whole = occurrence.get("whole_property") or {}
            if whole.get("owner_assessed_property") not in (None, ""):
                owner_property_present += 1
                continue
            row_index = len(rows)
            row_pointer = f"#/findings/{finding_index}/occurrences/{occurrence_index}"
            source = occurrence["original_criterion_source"]
            identity = occurrence["identity"]
            current = whole.get("bounded_mechanism_or_path") or {}
            owner_refs = whole.get("property_review_refs") or {}
            next_check = occurrence.get("next_check") or {}
            field_refs = {
                key: f"{row_pointer}/whole_property/bounded_mechanism_or_path/{key}"
                for key in sorted(current)
            }
            draft_pointer = owner_refs.get("draft_occurrence")
            require(isinstance(draft_pointer, str) and "#/occurrences/" in draft_pointer, f"draft occurrence reference is missing for {identity['finding_id']}")
            assessment = {
                "report_whole_property_record_ref": f"{row_pointer}/whole_property",
                "owner_explicit_property_field_present": False,
                "original_whole_criterion_defined_by_source_span": bool(
                    source.get("path")
                    and source.get("git_blob")
                    and source.get("criterion_sha256")
                    and source.get("lines_1_based_inclusive")
                ),
                "original_criterion_semantic_summary": "deferred to independent row-level source review; criterion text is not copied here",
                "owner_assessment_source_refs": {
                    "draft_occurrence": draft_pointer,
                    "owner_assessment_row": owner_refs.get("owner_assessment_row"),
                    "owner_packet_refs": owner_refs.get("owner_packet_refs"),
                    "readiness_row": owner_refs.get("readiness_row"),
                },
                "bounded_mechanism_source_ref": f"{draft_pointer}/technical_assessment/current_mechanism_or_bounded_path",
                "current_mechanism_field_refs": field_refs,
                "producer_ref": field_refs.get("producer"),
                "artifact_ref": field_refs.get("artifact"),
                "bridge_ref": field_refs.get("bridge"),
                "consumer_ref": field_refs.get("consumer") or field_refs.get("actual_consumer") or field_refs.get("current_route"),
                "candidate_limit_ref": field_refs.get("candidate_limit"),
                "candidate_limit_field_present": "candidate_limit" in field_refs,
                "non_substituting_property_boundary_refs": {
                    key: field_refs[key]
                    for key in ("property_title_or_boundary", "bounded_property")
                    if key in field_refs
                },
                "remaining_quantity_or_dependency_ref": f"{row_pointer}/whole_property/remaining_quantity_or_dependency",
                "next_check_refs": {
                    "after_final_source_freeze": f"{row_pointer}/next_check/after_final_source_freeze",
                    "owner_exact_next_check": f"{row_pointer}/next_check/owner_exact_next_check",
                },
                "candidate_evaluation": occurrence["candidate_evaluation"].get("state"),
                "formal_G_status": occurrence["history_and_authority"].get("formal_G_status"),
                "authority_qualification": "owner property field absence does not make the original criterion undefined; no owner field is fabricated and no candidate or G state is promoted",
            }
            rows.append(
                {
                    "row_index": row_index,
                    "review_bucket": row_index % 3,
                    "report_occurrence_ref": row_pointer,
                    "full_occurrence_identity": {
                        key: identity[key]
                        for key in ("finding_id", "occurrence_pointer", "criterion_sha256")
                    },
                    "coverage_pointer": identity["occurrence_pointer"],
                    "original_criterion_source_span": {
                        "path": source["path"],
                        "source_commit": source["source_commit"],
                        "git_blob": source["git_blob"],
                        "lines_1_based_inclusive": source["lines_1_based_inclusive"],
                        "criterion_sha256": source["criterion_sha256"],
                        "coverage_pointer": source["source_pointer"],
                    },
                    "owner_property_assessment": assessment,
                }
            )
    require(owner_property_present == 96 and len(rows) == 195, "optional owner property-field counts changed")
    buckets = [sum(row["review_bucket"] == bucket for row in rows) for bucket in range(3)]
    require(buckets == [65, 65, 65], "deterministic three-way property review partition changed")
    for row in rows:
        assessment = row["owner_property_assessment"]
        require(assessment["original_whole_criterion_defined_by_source_span"] is True, "original criterion source span is incomplete")
        require(assessment["candidate_evaluation"] == "UNRUN" and assessment["formal_G_status"] == "not_adjudicated", "property gap inventory promoted authority")
    inventory = {
        "schema": "policyos.e02.q0_full_occurrence_property_gap_inventory.v1",
        "status": "OPEN_SOURCE_REVIEW_REQUIRED_PROPERTY_FIELD_NOT_EQUIVALENT_TO_CRITERION_DEFINITION",
        "report_source": {
            "path": REPORT_PACKET_REL.as_posix(),
            "sha256": packet_sha,
            "bytes": len(packet_bytes),
            "persisted_report_checkpoint": packet["source_checkpoint"],
            "candidate_evaluation": "all UNRUN",
            "formal_closure_ids": packet["authority_boundary"]["formal_closure_ids"],
        },
        "current_source_rebuild_context": {
            "branch": INITIAL_SOURCE["branch"],
            "head": candidate["commit"],
            "tree": candidate["tree"],
            "qualification": "known descendant report-input checkpoint; not final source freeze; report row checkpoint metadata differs from persisted report only at top-level and per-occurrence report_checkpoint bindings",
        },
        "denominator": {
            "unique_finding_ids": packet["denominator"]["finding_ids"],
            "full_occurrence_count": packet["denominator"]["canonical_occurrences"],
            "owner_assessed_property_present_rows": owner_property_present,
            "missing_optional_owner_property_field_rows": len(rows),
            "route_assignments": packet["denominator"]["distinct_task_assignment_refs"],
            "expanded_occurrence_route_refs": packet["denominator"]["expanded_occurrence_route_refs"],
        },
        "interpretation": {
            "original_criterion_defined": "Each row retains the exact coverage pointer, source path/blob/span and criterion SHA; these 195 source criteria are defined by those source spans. The optional owner-assessment property field is absent, which is a distinct fact. Reviewers must summarize only what the original criterion and existing owner chain support, then state verification as not established or partial with its actual boundary.",
            "do_not_infer": "Do not infer the original whole criterion is undefined, do not backfill an owner property from an unrelated runtime property, do not convert route text into evidence, and do not promote UNRUN or formal closure.",
            "D45_runtime_property": "For rows whose source assessment has a D45_runtime_property field, this is a linked reference only; where the assessment states it must not substitute for the original criterion, preserve that boundary.",
            "criteria_text_copied": False,
        },
        "partition": {
            "method": "stable persisted report row order after filtering missing owner property, zero-based row index modulo 3",
            "bucket_sizes": buckets,
            "buckets": {
                "0": "review rows with row_index % 3 == 0",
                "1": "review rows with row_index % 3 == 1",
                "2": "review rows with row_index % 3 == 2",
            },
        },
        "rows": rows,
    }
    payload = stable_json(inventory)
    actual = (root / PROPERTY_GAP_INVENTORY_REL).read_bytes()
    require(actual == payload, "property-gap inventory differs from a fresh source-bound recomputation")
    return inventory, payload


def command_paths() -> dict[str, Path]:
    """Return all output log paths declared before this packet was written."""
    names = ("baseline-check", "baseline-self-check", "patched-self-check", "post-patch-canonical-check", "occurrence-report-check", "patch-check")
    return {f"{name}.{stream}": CHECKS_REL / f"{name}.{stream}.txt" for name in names for stream in ("stdout", "stderr")}


def make_outputs(root: Path, declared: dict[str, Any], advance: dict[str, Any]) -> tuple[dict[Path, bytes], dict[str, Any]]:
    """Recompute patch, full self-check, source checks, and the report overlay."""
    emitter_path = root / EMITTER_REL
    source = emitter_path.read_bytes()
    candidate = source_identity(root)
    env = fixture_environment(candidate)
    env_digest = sha256(env)
    patched = build_overlay(source, env_digest, candidate)
    patch = unified_patch(source, patched)
    patch_code, patch_out, patch_err = apply_check(root, patch)
    require(patch_code == 0, f"zero-fuzz patch check failed: {patch_err.decode(errors='replace')}")

    code_check, out_check, err_check, argv_check = run_cli(root, [EMITTER_REL.as_posix(), "--check"])
    require(code_check != 0 and b"committed descendant changes frozen candidate source" in err_check,
            "registered old-checkpoint report no longer fails closed on source freshness")
    code_baseline, out_baseline, err_baseline, argv_baseline = run_cli(root, [EMITTER_REL.as_posix(), "--provisional-review", "--self-check"])
    require(code_baseline != 0 and b"command needs a working directory" in err_baseline,
            "unmodified self-check did not reproduce its missing-cwd fixture defect")

    code_fixed, out_fixed, err_fixed, fixed_error = run_in_memory(root, patched, ["--provisional-review", "--self-check"])
    require(code_fixed == 0 and fixed_error is None and not err_fixed,
            f"patched full self-check failed: {fixed_error or err_fixed.decode(errors='replace')}")
    proof = json.loads(out_fixed.decode("utf-8"))
    require(proof.get("mode") == "self_check" and proof.get("finding_ids") == 282 and proof.get("occurrences") == 291,
            "patched full self-check denominator changed")
    require(proof.get("unrun_occurrences") == 291 and proof.get("formal_closure_ids") == [],
            "patched full self-check promoted candidate or G state")
    require(proof.get("count_preserving_mutations_rejected") == 11 and proof.get("typed_slice_handoff_probe_accepted") is True,
            "corrected full fixture did not complete the registered semantic controls")

    cwd_only = build_overlay(source, env_digest, candidate, include_profile=False, include_cwd=True)
    code_cwd, _, _, cwd_error = run_in_memory(root, cwd_only, ["--provisional-review", "--self-check"])
    require(code_cwd != 0 and cwd_error and "backend_profile fields are incomplete or unknown" in cwd_error,
            "cwd-only control did not reject the incomplete typed backend profile")
    extra_profile = build_overlay(source, env_digest, candidate, extra_profile_field=True)
    code_extra, _, _, extra_error = run_in_memory(root, extra_profile, ["--provisional-review", "--self-check"])
    require(code_extra != 0 and extra_error and "backend_profile fields are incomplete or unknown" in extra_error,
            "unknown backend profile field was accepted")
    foreign_ref = build_overlay(source, env_digest, candidate, corrupt_candidate=True)
    code_foreign, _, _, foreign_error = run_in_memory(root, foreign_ref, ["--provisional-review", "--self-check"])
    require(code_foreign != 0 and foreign_error and "differs from the frozen candidate source" in foreign_error,
            "foreign candidate backend ref was accepted")

    bad_context = patch.replace(b"backend_profile", b"backend_PROFiLE", 1)
    bad_patch_code, _, bad_patch_err = apply_check(root, bad_context)
    require(bad_patch_code != 0, "zero-fuzz patch checker accepted corrupted context")
    drifted_fixture = source.replace(b'"status": "named"', b'"status": "namex"', 1)
    drift_rejected = False
    try:
        build_overlay(drifted_fixture, env_digest, candidate)
    except ValueError as exc:
        drift_rejected = "fixture preimage count" in str(exc)
    require(drift_rejected, "exact fixture preimage drift was not rejected")
    mutated_source = source + b"\n"
    mutated_source_sha = sha256(mutated_source)
    source_mutation_rejected = False
    source_mutation_diagnostic = None
    try:
        verify_bound_bytes(mutated_source, declared["canonical_emitter"], "mutated canonical emitter")
    except ValueError as exc:
        source_mutation_rejected = True
        source_mutation_diagnostic = str(exc)
    require(source_mutation_rejected, "source byte drift was not rejected by the exact preimage gate")

    code_post, out_post, err_post, argv_post = run_cli(root, [EMITTER_REL.as_posix(), "--check"])
    require(code_post == code_check and out_post == out_check and err_post == err_check,
            "virtual self-check fixture patch changed the canonical old-report freshness result")

    report_summary, report_stdout = report_rebuild_check(root)
    property_gap, property_gap_bytes = build_property_gap_inventory(
        root,
        read_json(root, REPORT_PACKET_REL),
        candidate,
    )
    advance_types, advance_rows, advance_digest = advance["file_type_denominator"], advance["changed_paths"], advance["ordered_status_path_sha256"]
    freeze_rows, freeze_types, freeze_digest = source_delta(root, OLD_REPORT_CHECKPOINT["commit"], candidate["commit"])
    require(any(path == "policy-engine/.gitignore" for _, path in freeze_rows), "known old provisional source delta no longer includes .gitignore")

    paths = command_paths()
    outputs: dict[Path, bytes] = {
        PATCH_REL: patch,
        ENV_REL: env,
        paths["baseline-check.stdout"]: out_check,
        paths["baseline-check.stderr"]: err_check,
        paths["baseline-self-check.stdout"]: out_baseline,
        paths["baseline-self-check.stderr"]: err_baseline,
        paths["patched-self-check.stdout"]: out_fixed,
        paths["patched-self-check.stderr"]: err_fixed,
        paths["post-patch-canonical-check.stdout"]: out_post,
        paths["post-patch-canonical-check.stderr"]: err_post,
        paths["occurrence-report-check.stdout"]: report_stdout,
        paths["occurrence-report-check.stderr"]: b"",
        paths["patch-check.stdout"]: patch_out,
        paths["patch-check.stderr"]: patch_err,
        PROPERTY_GAP_INVENTORY_REL: property_gap_bytes,
    }
    p40 = {
        "classification": "SAME_CLASS_DEEPER",
        "class": "typed synthetic slice-handoff fixture omits schema-required command/backend-profile fields",
        "repair_scope": "join the actual required field quantity for one fixture: command cwd plus all exact backend_profile fields; no one-leaf waiver/default or validator relaxation",
        "no_crosswalk_test_edit": True,
        "no_gitignore_edit": True,
    }
    negative = {
        "schema": "policyos.e02.q0_full_emitter_fixture_fix_controls.v1",
        "status": "PASS",
        "correction_scope": "virtual source overlay only; canonical emitter and registered report files remain unchanged",
        "p40": p40,
        "root_source_advance": advance,
        "source_freshness_overlay": {
            "old_report_checkpoint": OLD_REPORT_CHECKPOINT,
            "current_committed_candidate": candidate,
            "complete_changed_paths": len(freeze_rows),
            "file_type_denominator": freeze_types,
            "ordered_status_path_sha256": freeze_digest,
            "first_rejected_path": "policy-engine/.gitignore",
            "result": "RED_EXPECTED_OLD_PROVISIONAL_SOURCE_FREEZE",
            "P41": "not_established; no inherited claim without exact slice-base and full input-denominator zero-intersection proof",
        },
        "fixture": {
            "canonical_emitter_preimage_sha256": declared["canonical_emitter"]["sha256"],
            "exact_unmodified_self_check": {"result": "REJECTED_AS_REQUIRED", "exit_code": code_baseline, "diagnostic": "command needs a working directory"},
            "full_fixture_overlay": {"result": "PASS", "exit_code": code_fixed, "finding_ids": proof["finding_ids"], "occurrences": proof["occurrences"], "unrun_occurrences": proof["unrun_occurrences"], "formal_closure_ids": proof["formal_closure_ids"], "count_preserving_mutations_rejected": proof["count_preserving_mutations_rejected"]},
            "negative_controls": [
                {"name":"cwd_only_backend_profile_incomplete","result":"REJECTED_AS_REQUIRED","diagnostic":cwd_error},
                {"name":"backend_profile_extra_field","result":"REJECTED_AS_REQUIRED","diagnostic":extra_error},
                {"name":"foreign_candidate_environment_ref","result":"REJECTED_AS_REQUIRED","diagnostic":foreign_error},
                {"name":"corrupt_patch_context_zero_fuzz","result":"REJECTED_AS_REQUIRED","diagnostic":bad_patch_err.decode(errors="replace").splitlines()[0] if bad_patch_err else "git apply rejected corrupted patch"},
                {"name":"source_preimage_byte_drift","result":"REJECTED_AS_REQUIRED","mutated_sha256":mutated_source_sha,"declared_sha256":declared["canonical_emitter"]["sha256"],"diagnostic":source_mutation_diagnostic},
                {"name":"fixture_replacement_preimage_drift","result":"REJECTED_AS_REQUIRED"},
            ],
        },
        "full_occurrence_report_rebuild": report_summary,
        "property_gap_inventory": {
            "path": PROPERTY_GAP_INVENTORY_REL.as_posix(),
            "schema": property_gap["schema"],
            "sha256": sha256(property_gap_bytes),
            "missing_owner_property_field_rows": property_gap["denominator"]["missing_optional_owner_property_field_rows"],
            "bucket_sizes": property_gap["partition"]["bucket_sizes"],
            "original_criteria_defined_by_exact_source_span": True,
            "criterion_text_copied": False,
        },
        "command_results": [
            {"name":"registered-old-report-check","argv":argv_check,"exit_code":code_check,"stdout_bytes":len(out_check),"stdout_sha256":sha256(out_check),"stderr_bytes":len(err_check),"stderr_sha256":sha256(err_check)},
            {"name":"registered-unmodified-self-check","argv":argv_baseline,"exit_code":code_baseline,"stdout_bytes":len(out_baseline),"stdout_sha256":sha256(out_baseline),"stderr_bytes":len(err_baseline),"stderr_sha256":sha256(err_baseline)},
            {"name":"registered-self-check-with-in-memory-fixture-patch","argv":["python3","-B",EMITTER_REL.as_posix(),"--provisional-review","--self-check","(in-memory source overlay)"],"exit_code":code_fixed,"stdout_bytes":len(out_fixed),"stdout_sha256":sha256(out_fixed),"stderr_bytes":len(err_fixed),"stderr_sha256":sha256(err_fixed)},
            {"name":"git-apply-strict-zero-fuzz-check","argv":["git","apply","--check","--verbose"],"exit_code":patch_code,"stdout_bytes":len(patch_out),"stdout_sha256":sha256(patch_out),"stderr_bytes":len(patch_err),"stderr_sha256":sha256(patch_err)},
            {"name":"post-patch-registered-old-report-check","argv":argv_post,"exit_code":code_post,"stdout_bytes":len(out_post),"stdout_sha256":sha256(out_post),"stderr_bytes":len(err_post),"stderr_sha256":sha256(err_post)},
            {"name":"full-occurrence-current-input-rebuild","argv":[REPORT_RUNNER_REL.as_posix(),"build_packet + validate_packet + exact identity helper + six negative controls (in-memory)"],"exit_code":0,"stdout_bytes":len(report_stdout),"stdout_sha256":sha256(report_stdout),"stderr_bytes":0,"stderr_sha256":sha256(b"")},
        ],
        "source_qualification": {
            "current_root_source_advance_intersection_with_declared_Q0_preimages": 0,
            "persisted_packet_checkpoint_is_prior_d24_only": True,
            "prior_readiness_artifact_metadata_accepted_as_current_source": False,
            "root_global_freeze_and_fresh_generation_required": True,
            "candidate_evaluation": "291 UNRUN",
            "formal_G": "not_adjudicated",
            "formal_closure_ids": [],
        },
    }
    outputs[NEGATIVE_REL] = stable_json(negative)

    commands = negative["command_results"]
    static_artifacts = [
        DECLARATION_REL,
        PROPERTY_GAP_DECL_REL,
        Path(__file__).resolve().relative_to(root),
    ]
    artifact_entries = []
    artifact_bytes: dict[Path, bytes] = dict(outputs)
    for relative in static_artifacts:
        data = (root / relative).read_bytes()
        artifact_bytes[relative] = data
    for relative, data in sorted(artifact_bytes.items(), key=lambda pair: pair[0].as_posix()):
        artifact_entries.append({"path":relative.as_posix(),"bytes":len(data),"sha256":sha256(data)})

    manifest = {
        "schema":"policyos.e02.q0_full_emitter_fixture_fix_manifest.v1",
        "status":"VIRTUAL_PATCH_AND_FULL_SELF_CHECK_VERIFIED_SOURCE_FREEZE_STILL_PROVISIONAL",
        "receipt_revision": 2,
        "supersedes_previous_local_receipt": {
            "manifest_sha256": PREVIOUS_RECEIPT_SHA256,
            "reason": "P38 correction: the source-byte drift control now invokes the exact byte-count/SHA preimage gate with mutated bytes instead of only demonstrating SHA sensitivity.",
        },
        "initial_source_checkpoint": declared["observed_source"],
        "verified_root_source_advance": advance,
        "current_committed_source": {"branch":INITIAL_SOURCE["branch"],**candidate},
        "canonical_emitter_preimage": declared["canonical_emitter"],
        "identity_helper": declared["generic_identity_helper"],
        "full_occurrence_report": {
            "packet_path":REPORT_PACKET_REL.as_posix(),
            "packet_sha256":"93c0ddd918e8d95502a2fdd4d85802065b3d9fdb75bd2d6f608bcd6080f28c0e",
            "report_builder_recomputed_against_current_Q0_inputs":True,
            "persisted_checkpoint_preserved":OLD_REPORT_CHECKPOINT,
            "current_checkpoint":candidate,
            "occurrence_checkpoint_bindings_normalized":291,
            "occurrences":291,
            "candidate_states":"all UNRUN",
            "formal_closure_ids":[],
            "criteria_text_copied":False,
            "per_occurrence_next_checks":291,
            "distinct_owner_next_check_refs":290,
            "preserved_B198_command_specific_next_check":True,
            "whole_property_boundary_and_dependency_records":291,
            "owner_property_source_field_counts":{"property":96,"property_title_or_boundary":59,"bounded_property":36,"D45_runtime_property_not_substituted_for_original_criterion":46,"property_not_established_by_owner_row":54},
            "property_source_qualification":"Owner property fields remain source assessments, not candidate adjudications; D45 runtime property is not substituted for the original occurrence; 54 rows provide no eligible property field.",
            "expanded_occurrence_route_refs":331,
            "identity_helper_multiset_and_negative_controls":"PASS",
        },
        "property_gap_inventory": {
            "path": PROPERTY_GAP_INVENTORY_REL.as_posix(),
            "schema": property_gap["schema"],
            "sha256": sha256(property_gap_bytes),
            "rows": property_gap["denominator"]["missing_optional_owner_property_field_rows"],
            "bucket_sizes": property_gap["partition"]["bucket_sizes"],
            "original_criteria_defined_by_exact_source_span": True,
            "criterion_text_copied": False,
        },
        "source_readiness_snapshot":{"role":"prior artifact checkpoint metadata only","accepted_as_current_source_or_candidate_evidence":False,"candidate_evaluation":"UNRUN","final_source_freeze":"not_established; root global freeze and fresh report generation remain required"},
        "patch":{"path":PATCH_REL.as_posix(),"sha256":sha256(patch),"bytes":len(patch),"changed_file_count":1,"changed_fields":["synthetic command cwd","backend_profile.backend_id","backend_profile.profile_id","backend_profile.environment_sha256","backend_profile.environment_manifest_ref"],"apply_check":"git apply --check --verbose passed; patch not applied to source"},
        "synthetic_environment_fixture":{"path":ENV_REL.as_posix(),"sha256":env_digest,"bytes":len(env),"qualification":"content-bound control fixture; not an executed backend manifest or candidate evidence"},
        "source_freshness":{"old_registered_check":"RED_EXPECTED_OLD_PROVISIONAL_SOURCE_FREEZE","complete_committed_delta_paths":len(freeze_rows),"file_type_denominator":freeze_types,"ordered_status_path_sha256":freeze_digest,"first_rejected_path":"policy-engine/.gitignore","P41":"not_established"},
        "P40":p40,
        "commands":commands,
        "artifacts":artifact_entries,
        "manifest_self_reference":"omitted by construction",
    }
    manifest_bytes = stable_json(manifest)
    outputs[MANIFEST_REL] = manifest_bytes
    return outputs, {"status":"PASS","patch_sha256":sha256(patch),"patched_self_check":"PASS","old_source_freeze_check":"RED_EXPECTED_AND_REPRODUCED","full_current_input_occurrence_report":"PASS","root_source_advance_intersection":len(advance["declared_input_intersection"]),"negative_controls":6,"manifest_sha256":sha256(manifest_bytes),"manifest_artifacts":len(artifact_entries)}


def main() -> int:
    """Emit once or run a read-only complete drift check."""
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--emit", action="store_true")
    group.add_argument("--check", action="store_true")
    group.add_argument("--refresh-local-receipt", action="store_true")
    args = parser.parse_args()
    root = repo_root()
    declared, advance = declaration(root)
    outputs, summary = make_outputs(root, declared, advance)
    if args.emit:
        require(not (root / PATCH_REL).exists(), "patch output already exists; use --check or a new lease")
        require(not (root / ENV_REL).exists(), "synthetic environment output already exists; use --check or a new lease")
        existing_check_files = {
            path.relative_to(root)
            for path in (root / CHECKS_REL).rglob("*")
            if path.is_file()
        }
        require(
            existing_check_files == {PROPERTY_GAP_INVENTORY_REL},
            "only the separately declared property-gap inventory may preexist in checks/",
        )
        for relative, data in outputs.items():
            path = root / relative
            if relative == PROPERTY_GAP_INVENTORY_REL:
                require(path.is_file() and path.read_bytes() == data, "predeclared property-gap inventory changed")
                continue
            require(not path.exists(), f"output already exists: {relative}")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    elif args.refresh_local_receipt:
        previous_manifest_path = root / MANIFEST_REL
        previous_manifest_bytes = previous_manifest_path.read_bytes()
        require(
            sha256(previous_manifest_bytes) == PREVIOUS_RECEIPT_SHA256,
            "local receipt refresh requires the exact previously verified manifest",
        )
        previous_manifest = json.loads(previous_manifest_bytes)
        previous_entries = {entry["path"]: entry for entry in previous_manifest["artifacts"]}
        script_relative = Path(__file__).resolve().relative_to(root).as_posix()
        require(
            previous_entries.get(script_relative, {}).get("sha256") == PREVIOUS_SCRIPT_SHA256,
            "previous manifest does not bind the expected verifier preimage",
        )
        for relative_text, entry in previous_entries.items():
            if relative_text == script_relative:
                continue
            path = root / relative_text
            data = path.read_bytes()
            require(len(data) == entry["bytes"] and sha256(data) == entry["sha256"], f"previous receipt artifact changed before refresh: {relative_text}")
        checks_dir = root / CHECKS_REL
        actual_check_files = {
            path.relative_to(root)
            for path in checks_dir.rglob("*")
            if path.is_file()
        }
        expected_check_files = {relative for relative in outputs if relative.is_relative_to(CHECKS_REL)}
        require(actual_check_files == expected_check_files, "local receipt refresh found an undeclared checks/ file")
        for relative, expected in outputs.items():
            path = root / relative
            if relative in {NEGATIVE_REL, MANIFEST_REL}:
                path.write_bytes(expected)
            else:
                require(path.is_file() and path.read_bytes() == expected, f"refresh would alter non-receipt evidence: {relative}")
    else:
        for relative, expected in outputs.items():
            path = root / relative
            require(path.is_file(), f"output missing: {relative}")
            actual = path.read_bytes()
            require(actual == expected, f"output drift: {relative}")
    mode = "emit" if args.emit else "refresh-local-receipt" if args.refresh_local_receipt else "check"
    print(json.dumps({"status":"PASS","mode":mode,**summary}, ensure_ascii=False, indent=2))  # noqa: T201 -- local verification output.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
