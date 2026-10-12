#!/usr/bin/env python3
"""Build a virtual Q0 projection integrity repair over the frozen R1 inputs.

The runner reuses the registered proposal producer and the existing local report
consumer in memory. It pins the owner draft's actual local bytes and compares the
complete per-occurrence whole_property object with a fresh producer projection.
It writes only the declared ignored R2 artifacts; tracked source, index, and
history remain untouched.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

sys.dont_write_bytecode = True

ROOT_MARKER = "AGENTS.md"
LEASE = Path(
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/"
    "q0-whole-criterion-owner-binding-author-r2-20261012"
)
DECLARATION = LEASE / "preimage-declaration.json"
RUNNER = LEASE / "virtual_projection.py"
PATCH = LEASE / "virtual-projection.patch"
DECISION = LEASE / "binding-decision-packet.json"
CONTROL_SPEC = LEASE / "controls.json"
NEGATIVE_RESULTS = LEASE / "checks/negative-controls.json"
SUMMARY = LEASE / "checks/summary.json"
STDOUT_RECEIPT = LEASE / "checks/projection-self-check.stdout.txt"
STDERR_RECEIPT = LEASE / "checks/projection-self-check.stderr.txt"

R1_LEASE = Path(
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/"
    "q0-whole-criterion-owner-binding-author-r1-20261012"
)
R1_RUNNER = R1_LEASE / "virtual_projection.py"
R1_DECLARATION = R1_LEASE / "preimage-declaration.json"
R1_REVIEW = Path(
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/reviews/"
    "q0-whole-criterion-owner-binding-independent-r1-20261012.md"
)
R1_PROBES = Path(
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/"
    "q0-whole-criterion-owner-binding-independent-r1-20261012/mutation-probes.json"
)
OWNER_DRAFT = Path(
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/"
    "crosswalk/occurrence-evaluations-draft.json"
)
REPORT_BUILDER = Path(
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/"
    "q0-full-occurrence-report-author-20261011/virtual_emitter.py"
)

R2_SCHEMA = "policyos.e02.q0_whole_criterion_owner_binding_preimage_declaration.r2.v1"
SOURCE_BINDING_QUALIFICATION = (
    "SHA-256 and filesystem mode identify current local bytes only; no Git object, "
    "commit, capsule, producer authority, or positive criterion alignment is claimed"
)


def repo_root() -> Path:
    """Find the repository root from the leased local runner."""
    for parent in Path(__file__).resolve().parents:
        if (parent / ROOT_MARKER).is_file() and (parent / "policy-engine").is_dir():
            return parent
    raise RuntimeError("repository root not found")


def sha256(data: bytes) -> str:
    """Return a lowercase SHA-256 digest."""
    return hashlib.sha256(data).hexdigest()


def stable_json(value: Any) -> bytes:
    """Serialize a deterministic local artifact."""
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def require(condition: bool, message: str) -> None:
    """Fail closed with one actionable diagnostic."""
    if not condition:
        raise ValueError(message)


def read_json(root: Path, path: Path) -> dict[str, Any]:
    """Read a JSON object from a repository-relative path."""
    value = json.loads((root / path).read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"expected JSON object at {path.as_posix()}")
    return value


def git_text(root: Path, *args: str) -> str:
    """Run a read-only Git query."""
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def owner_source_binding(root: Path, declaration: dict[str, Any]) -> dict[str, Any]:
    """Read and content-bind the owner draft without inventing Git provenance."""
    expected = declaration["owner_input_source"]
    path = root / OWNER_DRAFT
    metadata = path.lstat()
    require(stat.S_ISREG(metadata.st_mode), "owner draft is not a regular local file")
    raw = path.read_bytes()
    mode = stat.S_IMODE(metadata.st_mode)
    require(len(raw) == expected["bytes"], "owner draft byte-count drift")
    require(sha256(raw) == expected["sha256"], "owner draft SHA-256 drift")
    require(f"{mode:04o}" == expected["filesystem_mode_octal"], "owner draft filesystem mode drift")

    relative = OWNER_DRAFT.as_posix()
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", relative],
        cwd=root,
        capture_output=True,
        check=False,
    )
    require(
        tracked.returncode == 1 and not tracked.stdout,
        "owner draft is no longer the declared untracked local input",
    )
    would_be_blob = subprocess.run(
        ["git", "hash-object", "--stdin"],
        cwd=root,
        input=raw,
        capture_output=True,
        check=True,
    ).stdout.decode("ascii").strip()
    object_lookup = subprocess.run(
        ["git", "cat-file", "-e", f"{would_be_blob}^{{blob}}"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    require(object_lookup.returncode != 0, "owner draft unexpectedly resolves to a Git blob object")
    binding = {
        "path": relative,
        "bytes": len(raw),
        "sha256": sha256(raw),
        "filesystem_mode_octal": f"{mode:04o}",
        "git_tree_mode": None,
        "tracked_path": False,
        "would_be_blob_object_present": False,
        "local_availability": "available_local_readback_only_untracked",
        "source_commit": None,
        "qualification": SOURCE_BINDING_QUALIFICATION,
    }
    require(binding == expected, "owner draft availability/source identity differs from preimage declaration")
    return binding


def observe_source_lineage(root: Path, declaration: dict[str, Any]) -> dict[str, Any]:
    """Record a descendant source advance only after checking its input intersection."""
    observed = declaration["observed_source"]
    branch = git_text(root, "symbolic-ref", "--short", "HEAD")
    require(branch == observed["branch"], "attached source branch changed")
    base = observed["head"]
    head = git_text(root, "rev-parse", "HEAD")
    tree = git_text(root, "rev-parse", "HEAD^{tree}")
    if head == base:
        require(tree == observed["tree"], "declared source tree no longer matches HEAD")
        return {
            "branch": branch,
            "base_head": base,
            "head": head,
            "tree": tree,
            "committed_paths_after_base": 0,
            "input_intersection": [],
        }
    require(
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", base, head],
            cwd=root,
            check=False,
        ).returncode
        == 0,
        "current source is not a descendant of the declared source checkpoint",
    )
    delta = subprocess.check_output(
        ["git", "diff", "--name-status", "--no-renames", base, head, "--"],
        cwd=root,
        text=True,
    )
    rows = [tuple(line.split("\t", 1)) for line in delta.splitlines()]
    changed = {path for _, path in rows}
    inputs = {row["path"] for row in declaration["source_preimages"]}
    intersection = sorted(changed & inputs)
    require(not intersection, f"descendant source commit intersects declared report inputs: {intersection}")
    return {
        "branch": branch,
        "base_head": base,
        "head": head,
        "tree": tree,
        "committed_paths_after_base": len(rows),
        "input_intersection": intersection,
        "ordered_status_path_sha256": sha256("".join(f"{s}\t{p}\n" for s, p in rows).encode()),
        "qualification": "complete committed delta checked; source-bound inputs remain byte-identical",
    }


def verify_preimages(root: Path, declaration: dict[str, Any]) -> dict[str, Any]:
    """Verify all declared source preimages plus owner local-file availability."""
    require(declaration.get("schema") == R2_SCHEMA, "unexpected R2 preimage-declaration schema")
    require(
        declaration.get("status") == "PREIMAGES_VERIFIED_ALL_R2_TARGETS_ABSENT_BEFORE_PROJECTION",
        "R2 preimage declaration is not the frozen preimplementation record",
    )
    for item in declaration["source_preimages"]:
        raw = (root / item["path"]).read_bytes()
        require(len(raw) == item["bytes"], f"declared source byte-count drift: {item['path']}")
        require(sha256(raw) == item["sha256"], f"declared source SHA-256 drift: {item['path']}")
    immutable_r1 = declaration["immutable_r1"]
    for item in immutable_r1["artifacts"]:
        raw = (root / item["path"]).read_bytes()
        require(len(raw) == item["bytes"], f"frozen R1 artifact byte-count drift: {item['path']}")
        require(sha256(raw) == item["sha256"], f"frozen R1 artifact SHA-256 drift: {item['path']}")
    r1_decl_raw = (root / R1_DECLARATION).read_bytes()
    require(sha256(r1_decl_raw) == immutable_r1["preimage_declaration_sha256"], "frozen R1 declaration drift")
    owner_binding = owner_source_binding(root, declaration)
    lineage = observe_source_lineage(root, declaration)
    return {"owner_input_source": owner_binding, "source_lineage": lineage}


def import_path(name: str, path: Path) -> Any:
    """Import a source-bound local runner by exact path."""
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def r2_consumer_overlay(base: Any, original_overlay: Callable[[bytes], bytes], source: bytes, owner_binding: dict[str, Any]) -> bytes:
    """Extend the actual local consumer with full-object recomputation and source binding."""
    patched = original_overlay(source)
    text = patched.decode("utf-8")
    require(text.count("import subprocess\n") == 1, "consumer subprocess import anchor is not unique")
    text = text.replace("import subprocess\n", "import subprocess\nimport stat\n", 1)
    build_validate_anchor = "    validate_packet(packet, coverage_keys)\n    return packet, declaration, coverage_keys, identity\n"
    require(text.count(build_validate_anchor) == 1, "packet emission validation anchor is not unique")
    text = text.replace(
        build_validate_anchor,
        "    packet[\"owner_input_source_binding\"] = owner_input_source_binding()\n"
        + build_validate_anchor,
        1,
    )
    old_validator = '''def validate_packet(packet: dict[str, Any], expected_keys: list[tuple[str, str, str]]) -> None:
    """Validate base ledger invariants and source-bound owner/criterion separation."""
    _validate_packet_base(packet, expected_keys)
    validate_criterion_owner_projection(packet, expected_keys)
'''
    require(text.count(old_validator) == 1, "R1 owner/criterion validator anchor is not unique")
    owner_literal = repr(owner_binding)
    new_validator = f'''OWNER_SOURCE_BINDING_PREIMAGE = {owner_literal}
_R2_OWNER_RECOMPUTE_IN_PROGRESS = False
_R2_EXPECTED_OWNER_PROJECTION_CACHE: dict[tuple[str, str, str], dict[tuple[str, str, str], dict[str, Any]]] = {{}}


def owner_input_source_binding() -> dict[str, Any]:
    """Bind the local draft's bytes/mode while refusing fake Git provenance."""
    root = repo_root()
    path = root / DRAFT_REL
    metadata = path.lstat()
    require(stat.S_ISREG(metadata.st_mode), "owner draft is not a regular local file")
    raw = path.read_bytes()
    mode = stat.S_IMODE(metadata.st_mode)
    require(len(raw) == OWNER_SOURCE_BINDING_PREIMAGE["bytes"], "owner draft byte-count drift")
    require(hashlib.sha256(raw).hexdigest() == OWNER_SOURCE_BINDING_PREIMAGE["sha256"], "owner draft SHA-256 drift")
    require(f"{{mode:04o}}" == OWNER_SOURCE_BINDING_PREIMAGE["filesystem_mode_octal"], "owner draft filesystem mode drift")
    relative = DRAFT_REL.as_posix()
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", relative],
        cwd=root, capture_output=True, check=False,
    )
    require(tracked.returncode == 1 and not tracked.stdout, "owner draft tracked/untracked status drift")
    would_be_blob = subprocess.run(
        ["git", "hash-object", "--stdin"], cwd=root, input=raw,
        capture_output=True, check=True,
    ).stdout.decode("ascii").strip()
    object_lookup = subprocess.run(
        ["git", "cat-file", "-e", would_be_blob + "^{{blob}}"],
        cwd=root, capture_output=True, check=False,
    )
    require(object_lookup.returncode != 0, "owner draft unexpectedly resolves to a Git blob object")
    result = {{
        "path": relative,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "filesystem_mode_octal": f"{{mode:04o}}",
        "git_tree_mode": None,
        "tracked_path": False,
        "would_be_blob_object_present": False,
        "local_availability": "available_local_readback_only_untracked",
        "source_commit": None,
        "qualification": {SOURCE_BINDING_QUALIFICATION!r},
    }}
    require(result == OWNER_SOURCE_BINDING_PREIMAGE, "owner draft binding differs from the declared local-only identity")
    return result


def _validate_packet_r1(packet: dict[str, Any], expected_keys: list[tuple[str, str, str]]) -> None:
    """Retain R1's source identity and fail-closed alignment checks."""
    _validate_packet_base(packet, expected_keys)
    validate_criterion_owner_projection(packet, expected_keys)


def compare_complete_owner_projection(
    row: dict[str, Any], expected_whole_property: dict[str, Any], index: int
) -> None:
    """Compare the complete emitted occurrence subobject with fresh source output."""
    require(
        row.get("whole_property") == expected_whole_property,
        f"complete owner-derived whole_property differs from fresh source recomputation at occurrence {{index}}",
    )


def _fresh_owner_projection_map(
    expected_keys: list[tuple[str, str, str]],
) -> dict[tuple[str, str, str], dict[str, Any]]:
    """Rebuild the report through the same source-bound producer/consumer path."""
    global _R2_OWNER_RECOMPUTE_IN_PROGRESS
    root = repo_root()
    packet, _, computed_keys, _ = build_packet()
    require(computed_keys == expected_keys, "fresh report occurrence order changed during whole-projection recompute")
    rows = packet_occurrence_rows(packet)
    require(len(rows) == len(expected_keys) == 291, "fresh report denominator changed during whole-projection recompute")
    result: dict[tuple[str, str, str], dict[str, Any]] = {{}}
    for index, row in enumerate(rows):
        identity = row["identity"]
        key = (identity["finding_id"], identity["occurrence_pointer"], identity["criterion_sha256"])
        require(key not in result, f"fresh report repeats a complete occurrence identity at {{index}}")
        whole = row.get("whole_property")
        require(isinstance(whole, dict), f"fresh report whole_property is not an object at {{index}}")
        result[key] = copy.deepcopy(whole)
    require(len(result) == 291, "fresh report lost an occurrence during whole-projection recompute")
    return result


def validate_packet(packet: dict[str, Any], expected_keys: list[tuple[str, str, str]]) -> None:
    """Validate source identity, local input identity, and the whole projection."""
    global _R2_OWNER_RECOMPUTE_IN_PROGRESS
    _validate_packet_r1(packet, expected_keys)
    current_binding = owner_input_source_binding()
    require(
        packet.get("owner_input_source_binding") == current_binding,
        "owner draft source binding differs from current local readback",
    )
    if _R2_OWNER_RECOMPUTE_IN_PROGRESS:
        return
    root = repo_root()
    cache_key = (
        current_binding["sha256"],
        current_binding["filesystem_mode_octal"],
        subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
    )
    if cache_key not in _R2_EXPECTED_OWNER_PROJECTION_CACHE:
        _R2_OWNER_RECOMPUTE_IN_PROGRESS = True
        try:
            _R2_EXPECTED_OWNER_PROJECTION_CACHE[cache_key] = _fresh_owner_projection_map(expected_keys)
        finally:
            _R2_OWNER_RECOMPUTE_IN_PROGRESS = False
    expected_by_key = _R2_EXPECTED_OWNER_PROJECTION_CACHE[cache_key]
    rows = packet_occurrence_rows(packet)
    require(len(rows) == 291, "consumer whole-projection denominator changed")
    actual_keys: list[tuple[str, str, str]] = []
    for index, row in enumerate(rows):
        identity = row.get("identity", {{}})
        key = (identity.get("finding_id"), identity.get("occurrence_pointer"), identity.get("criterion_sha256"))
        actual_keys.append(key)
        require(key in expected_by_key, f"consumer row has no freshly projected source identity at {{index}}")
        compare_complete_owner_projection(row, expected_by_key[key], index)
    identity_helper = import_module("e02_registered_occurrence_identity_validation", repo_root() / IDENTITY_HELPER_REL)
    identity_helper.require_same_occurrence_multiset(expected_keys, actual_keys, label="full owner projection recompute")

validate_packet._r2_complete_owner_projection = compare_complete_owner_projection
validate_packet._r2_expected_owner_projection_cache = _R2_EXPECTED_OWNER_PROJECTION_CACHE
'''
    text = text.replace(old_validator, new_validator, 1)
    return text.encode("utf-8")


def packet_rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten findings without collapsing duplicate occurrence identities."""
    return [row for finding in packet.get("findings", []) for row in finding.get("occurrences", [])]


def find_r2_consumer(packet_validator: Callable[..., Any]) -> Callable[..., Any]:
    """Find the actual patched validator captured by the report build function."""
    for cell in packet_validator.__closure__ or ():
        candidate = cell.cell_contents
        if callable(candidate) and hasattr(candidate, "_r2_complete_owner_projection"):
            return candidate
    raise ValueError("combined report validator does not capture the patched full-projection consumer")


def run_r2_alignment_controls(
    base: Any,
    original: Callable[..., Any],
    packet: dict[str, Any],
    draft: dict[str, Any],
    draft_path: Path,
    source_index: dict[tuple[str, str, str], dict[str, Any]],
    packet_validator: Callable[[dict[str, Any], list[tuple[str, str, str]]], None],
    expected_keys: list[tuple[str, str, str]],
) -> dict[str, Any]:
    """Keep R1 controls and add whole-projection and owner-input falsifiers."""
    result = original(packet, draft, draft_path, source_index, packet_validator, expected_keys)
    require(result.get("status") == "PASS", "frozen R1 owner/criterion controls did not pass")
    consumer = find_r2_consumer(packet_validator)
    compare_row = consumer._r2_complete_owner_projection
    cache = consumer._r2_expected_owner_projection_cache
    require(len(cache) == 1, "actual report consumer did not build one source-bound expected projection")
    expected_by_key = next(iter(cache.values()))
    rows = packet_rows(packet)
    require(len(rows) == len(expected_keys) == 291, "whole-projection control denominator changed")
    siblings = ("proxy_divergence", "readout", "remaining_quantity_or_dependency")
    sentinel = {"r2_probe": "sibling projection altered"}
    per_occurrence: list[dict[str, Any]] = []
    field_counts: dict[str, dict[str, int]] = {name: {"corrupt": 0, "remove": 0} for name in siblings}
    for index, (row, key) in enumerate(zip(rows, expected_keys, strict=True)):
        field = siblings[index % len(siblings)]
        operation = "corrupt" if index % 2 == 0 else "remove"
        mutated = copy.deepcopy(row)
        if operation == "corrupt":
            mutated["whole_property"][field] = copy.deepcopy(sentinel)
        else:
            require(field in mutated["whole_property"], f"sibling field missing in source row at occurrence {index}")
            del mutated["whole_property"][field]
        try:
            compare_row(mutated, expected_by_key[key], index)
        except (AssertionError, KeyError, TypeError, ValueError) as exc:
            reason = str(exc).splitlines()[0][:220]
            require("complete owner-derived whole_property differs" in reason, f"row control failed for another reason at occurrence {index}: {reason}")
            outcome = "REJECTED_AS_REQUIRED"
        else:
            raise ValueError(f"full source recompute accepted sibling mutation at occurrence {index}")
        field_counts[field][operation] += 1
        per_occurrence.append({
            "identity": {"finding_id": key[0], "coverage_occurrence_pointer": key[1], "criterion_sha256": key[2]},
            "sibling_field": field,
            "operation": operation,
            "result": outcome,
            "reason": reason,
        })

    # Exercise every independently reviewed sibling escape at the real consumer.
    actual_consumer_mutations: list[dict[str, Any]] = []
    diagnostic = {row["identity"]["finding_id"]: i for i, row in enumerate(rows) if row["identity"]["finding_id"] in {"LA-033", "B26"}}
    require(set(diagnostic) == {"LA-033", "B26"}, "source-qualified diagnostic rows are missing")
    for finding_id in ("LA-033", "B26"):
        index = diagnostic[finding_id]
        key = expected_keys[index]
        for field in siblings:
            mutated_packet = copy.deepcopy(packet)
            mutated_row = packet_rows(mutated_packet)[index]
            mutated_row["whole_property"][field] = copy.deepcopy(sentinel)
            control = base.expect_packet_rejection(
                f"actual_consumer_{finding_id}_{field}_corrupt",
                mutated_packet,
                expected_keys,
                packet_validator,
            )
            require(
                "complete owner-derived whole_property differs" in control["reason"],
                f"actual consumer did not reject {finding_id}/{field} through generic full comparison",
            )
            actual_consumer_mutations.append({"finding_id": finding_id, "sibling_field": field, "operation": "corrupt", **control})
            removed_packet = copy.deepcopy(packet)
            removed_row = packet_rows(removed_packet)[index]
            del removed_row["whole_property"][field]
            control = base.expect_packet_rejection(
                f"actual_consumer_{finding_id}_{field}_remove",
                removed_packet,
                expected_keys,
                packet_validator,
            )
            require(
                "complete owner-derived whole_property differs" in control["reason"],
                f"actual consumer did not reject removal of {finding_id}/{field} through generic full comparison",
            )
            actual_consumer_mutations.append({"finding_id": finding_id, "sibling_field": field, "operation": "remove", **control})

    source_binding_mutations: list[dict[str, Any]] = []
    mutations = (
        ("remove_owner_input_binding", None),
        ("owner_input_sha256", {"sha256": "0" * 64}),
        ("owner_input_mode", {"filesystem_mode_octal": "0600"}),
        ("owner_input_local_availability", {"local_availability": "git_committed"}),
        ("owner_input_tracked_marker", {"tracked_path": True}),
    )
    for label, replacement in mutations:
        mutated_packet = copy.deepcopy(packet)
        if replacement is None:
            mutated_packet.pop("owner_input_source_binding", None)
        else:
            mutated_packet["owner_input_source_binding"].update(replacement)
        control = base.expect_packet_rejection(label, mutated_packet, expected_keys, packet_validator)
        require("owner draft source binding differs from current local readback" in control["reason"], f"actual consumer accepted owner binding mutation {label}")
        source_binding_mutations.append(control)

    result["whole_owner_projection_controls"] = {
        "status": "PASS",
        "property": "For each complete occurrence identity, every key and value in the emitted whole_property object must equal a fresh report build from the pinned source inputs.",
        "comparison": "generic equality over the entire per-occurrence whole_property object; no fixed sibling allowlist is used by the consumer validator",
        "all_291_row_sibling_controls": {
            "row_count": len(per_occurrence),
            "corruptions": sum(v["corrupt"] for v in field_counts.values()),
            "removals": sum(v["remove"] for v in field_counts.values()),
            "field_counts": field_counts,
            "result": "all rejected by the exact shared complete-object comparator used by the consumer",
            "per_occurrence": per_occurrence,
        },
        "actual_consumer_diagnostics": actual_consumer_mutations,
        "owner_source_binding_controls": source_binding_mutations,
        "source_input_scope": "owner bytes and filesystem mode are freshly read and checked on each consumer validation; local untracked availability is explicit and no Git object is claimed",
    }
    result["status"] = "PASS"
    return result


def configure_r1(base: Any, root: Path, declaration: dict[str, Any], owner_binding: dict[str, Any]) -> None:
    """Reuse frozen R1 computation while redirecting outputs to the new R2 lease."""
    base.LEASE = LEASE
    base.DECLARATION = R1_DECLARATION
    base.PATCH = PATCH
    base.DECISION = DECISION
    base.CONTROL_SPEC = CONTROL_SPEC
    base.NEGATIVE_RESULTS = NEGATIVE_RESULTS
    base.SUMMARY = SUMMARY
    base.STDOUT_RECEIPT = STDOUT_RECEIPT
    base.STDERR_RECEIPT = STDERR_RECEIPT
    original_overlay = base.projection_overlay
    base.projection_overlay = lambda source: r2_consumer_overlay(base, original_overlay, source, owner_binding)
    old_controls = base.run_alignment_controls
    base.run_alignment_controls = lambda packet, draft, draft_path, source_index, validator, keys: run_r2_alignment_controls(
        base, old_controls, packet, draft, draft_path, source_index, validator, keys
    )


def enrich_decision(
    decisions: dict[str, Any], summary: dict[str, Any], declaration: dict[str, Any], owner_binding: dict[str, Any]
) -> None:
    """Record the selected bounded repair, alternatives, and real source gaps."""
    decisions["r2_projection_integrity"] = {
        "review_disposition": "SAME_CLASS_DEEPER; close the complete-projection quantity rather than patching LA-033, B26, or three siblings individually.",
        "property": "The report consumer must render every whole_property member from its source-bound inputs without accepting packet-side corruption/removal; this is projection integrity only, not semantic alignment or runtime proof.",
        "implementation": "At the consumer boundary, rebuild the complete report through the registered proposal path from the pinned inputs, then compare the full whole_property object for each (finding_id, coverage pointer, criterion SHA-256). The source draft's local bytes, SHA-256, and filesystem mode are reread and bound before accepting a packet.",
        "actual_consumer_falsifier": "Every canonical row has a sibling corruption/removal probe through the shared whole-object comparator; LA-033 and B26 additionally exercise corrupt/remove for each reviewed sibling through the actual packet validator.",
        "source_identity": owner_binding,
        "semantic_alignment": "not_established for all 291 occurrences; owner_assessed_property stays null, no partial or positive alignment is produced, and the owner-scoped assertion remains a separate reference.",
        "capability_state": "virtual local report projection only; the local raw report builder is not a registered product consumer, and the untracked owner draft is not a replayable committed/capsule input",
        "decision": "Keep the minimal qualification at the actual local report consumer and widen its validator to full source recomputation. Do not consolidate into the registered emitter until owner input has durable identity and a typed integration contract; do not use a field-name/marker or SHA-adjacency proxy as semantic alignment.",
        "alternatives": [
            {"option": "Full local consumer recomputation and comparison (selected for this virtual repair)", "impact": "Catches drift or packet mutation anywhere in the complete owner-derived occurrence object while keeping authority status fail-closed.", "compatibility": "Preserves existing report shape and history; source owner assertion is still available via its scoped reference; candidate remains UNRUN."},
            {"option": "Consolidate into the registered canonical emitter", "impact": "Would make this a broader persisted producer/consumer contract and needs source-freeze integration.", "required_inputs": ["durable owner draft object/capsule with bytes, SHA-256, mode, provenance, producer/schema, source refs, and currentness", "registered report projection/validator and its consumer integration", "independent criterion-to-owner semantic basis before any positive admission"], "choice": "deferred; required for a replayable product capability, not asserted by this local prototype"},
            {"option": "Patch the three reported sibling fields or keep a qualification marker", "impact": "Rejected: sibling escapes are the same class and finite field patching/marker presence does not prove whole-object integrity.", "failure_class": "P32/P38/P40"}
        ],
        "minimal_ordinary_source_commit_or_capsule_inputs_for_root": {
            "owner_source": "Preserve the exact current owner draft path and content as a tracked commit/blob with tree mode, or an immutable capsule containing exact bytes and mode; include producer/schema/version, provenance, source refs, and source/currentness semantics. The current local digest is a readback pin only.",
            "report_consumer": "Promote the ignored local report builder and its complete validator as a normal versioned source artifact, bind it to the producer input manifest, and wire its consumer and behavioral test.",
            "alignment": "Keep criterion/owner alignment not_established until an independent source-qualified semantic comparison is available; owner references and projection hashes do not create this basis."
        },
        "source_checkpoint_ref": "#/source_checkpoint",
        "formal_authority": {"formal_G": "not_adjudicated", "formal_closure_ids": [], "candidate_states": {"UNRUN": 291}, "history_198_and_B198": "preserved unchanged"},
        "P37_predicate_classification": {
            "criterion_source_identity": "recomputed from the coverage occurrence and pinned historical source span/hash",
            "owner_local_file_bytes_and_mode": "recomputed from current local readback; durable source provenance not_established",
            "criterion_to_owner_semantic_alignment": "not_established",
            "owner assertion meaning/scope": "consumer_asserted in the local owner draft",
            "candidate execution and formal closure": "not_established / not_adjudicated"
        },
        "P38_boundary": {
            "property_checked": "complete consumer projection equals the fresh source-derived projection for each exact occurrence identity",
            "code_checks": "fresh full packet rebuild plus equality of each entire whole_property object; owner input file SHA/mode and untracked status are freshly checked",
            "divergent_semantic_case": "LA-033 original LA_r09 migration-compatibility criterion vs narrower owner replay/PII assertion; B26 original pairwise-vs-global additivity criterion vs owner persistence chain",
            "limit": "This prevents consumer-side projection divergence; a generator and its re-run could still share a semantic mapping error. No owner assertion is admitted as whole criterion, so that semantic alignment remains not_established."
        }
    }
    decisions["r2_projection_integrity"]["preimage_declaration"] = {
        "path": DECLARATION.as_posix(),
        "sha256": sha256((repo_root() / DECLARATION).read_bytes()),
    }


def generate(root: Path) -> dict[str, Any]:
    """Recompute R1 inputs and run the R2 full projection repair in memory."""
    declaration = read_json(root, DECLARATION)
    verified = verify_preimages(root, declaration)
    owner_binding = verified["owner_input_source"]
    base = import_path("q0_whole_criterion_owner_binding_r1_r2_base", root / R1_RUNNER)
    configure_r1(base, root, declaration, owner_binding)
    result = base.generate(root)
    result["summary"]["owner_input_source_binding"] = owner_binding
    result["summary"]["owner_source_availability"] = "available_local_readback_only_untracked; no Git object or source commit"
    whole_controls = result["negative_results"]["whole_owner_projection_controls"]
    all_rows = whole_controls["all_291_row_sibling_controls"]
    negative_bytes = stable_json(result["negative_results"])
    evidence_ref = {"path": NEGATIVE_RESULTS.as_posix(), "sha256": sha256(negative_bytes)}
    compact_whole_controls = {
        "status": "PASS",
        "actual_consumer": REPORT_BUILDER.as_posix(),
        "projection_comparison": "full whole_property object by complete occurrence identity after source recomputation",
        "all_291_rows": {
            "row_count": all_rows["row_count"],
            "corruptions": all_rows["corruptions"],
            "removals": all_rows["removals"],
            "field_counts": all_rows["field_counts"],
            "result": all_rows["result"],
            "evidence_ref": evidence_ref,
        },
        "actual_consumer_diagnostic_count": len(whole_controls["actual_consumer_diagnostics"]),
        "owner_input_binding_control_count": len(whole_controls["owner_source_binding_controls"]),
        "semantic_alignment": "not_established for all 291 rows",
    }
    result["summary"]["whole_owner_projection_verification"] = compact_whole_controls
    result["summary"]["source_lineage_r2"] = verified["source_lineage"]
    result["summary"]["r2_patch_sha256"] = sha256(result["outputs"][PATCH])
    result["decisions"]["source_checkpoint"] = result["summary"]["source_checkpoint"]
    enrich_decision(result["decisions"], result["summary"], declaration, owner_binding)
    result["controls"]["whole_owner_projection_controls"] = {
        **compact_whole_controls,
        "owner_input_source_binding_controls_ref": evidence_ref,
    }
    result["outputs"][DECISION] = stable_json(result["decisions"])
    result["outputs"][CONTROL_SPEC] = stable_json(result["controls"])
    result["outputs"][NEGATIVE_RESULTS] = stable_json(result["negative_results"])
    result["outputs"][SUMMARY] = stable_json(result["summary"])
    result["declaration"] = declaration
    result["owner_binding"] = owner_binding
    return result


def artifact_receipt(root: Path, outputs: dict[Path, bytes]) -> tuple[bytes, list[dict[str, Any]]]:
    """Bind the exact R2 runner and generated outputs without self-referential stdout."""
    rows = []
    runner_bytes = (root / RUNNER).read_bytes()
    rows.append({"path": RUNNER.as_posix(), "bytes": len(runner_bytes), "sha256": sha256(runner_bytes)})
    for path, raw in sorted(outputs.items(), key=lambda item: item[0].as_posix()):
        rows.append({"path": path.as_posix(), "bytes": len(raw), "sha256": sha256(raw)})
    receipt = {
        "schema": "policyos.e02.q0_whole_criterion_owner_binding_r2_self_check.v1",
        "status": "PASS",
        "scope": "virtual local projection integrity; no candidate/runtime or formal closure result",
        "finding_ids": 282,
        "canonical_occurrences": 291,
        "assignment_refs": 319,
        "expanded_routes": 331,
        "historical_source_author_closed_ids": 198,
        "B198": "preserved; candidate remains UNRUN; no formal closure",
        "candidate_states": {"UNRUN": 291},
        "formal_G": "not_adjudicated",
        "formal_closure_ids": [],
        "criterion_owner_alignment": "not_established for all 291 occurrences",
        "owner_input_source_binding": outputs_binding_summary(outputs),
        "generated_artifacts": rows,
        "source_checkpoint": "provisional; see binding-decision-packet.json and checks/summary.json",
        "readback": {
            "status": "PASS",
            "artifacts_rechecked": len(rows),
            "scope": "runner and five content artifacts; stdout/stderr are byte-checked after receipt serialization",
        },
    }
    return stable_json(receipt), rows


def outputs_binding_summary(outputs: dict[Path, bytes]) -> dict[str, Any]:
    """Return the owner input identity already embedded in the decision output."""
    decisions = json.loads(outputs[DECISION])
    return decisions["r2_projection_integrity"]["source_identity"]


def main() -> int:
    """Emit once or verify every declared R2 byte by recomputation/readback."""
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--emit", action="store_true", help="write the declared ignored local artifacts")
    modes.add_argument("--check", action="store_true", help="recompute and byte-check all generated artifacts")
    args = parser.parse_args()
    root = repo_root()
    result = generate(root)
    content_outputs = dict(result["outputs"])
    require(len(content_outputs) == 5, "R2 content artifact denominator changed")

    if args.emit:
        present = [path.as_posix() for path in content_outputs if (root / path).exists()]
        present.extend(path.as_posix() for path in (STDOUT_RECEIPT, STDERR_RECEIPT) if (root / path).exists())
        require(not present, f"R2 output target already exists; refusing overwrite: {present}")
        for path, raw in content_outputs.items():
            absolute = root / path
            absolute.parent.mkdir(parents=True, exist_ok=True)
            absolute.write_bytes(raw)
    for path, expected in content_outputs.items():
        actual = (root / path).read_bytes()
        require(actual == expected, f"R2 generated artifact drift: {path.as_posix()}")

    stdout, _ = artifact_receipt(root, content_outputs)
    receipt_outputs = {STDOUT_RECEIPT: stdout, STDERR_RECEIPT: b""}
    if args.emit:
        for path, raw in receipt_outputs.items():
            absolute = root / path
            absolute.parent.mkdir(parents=True, exist_ok=True)
            absolute.write_bytes(raw)
    for path, expected in receipt_outputs.items():
        actual = (root / path).read_bytes()
        require(actual == expected, f"R2 self-check receipt drift: {path.as_posix()}")

    outputs = {**content_outputs, **receipt_outputs}
    readback_rows = []
    for path, expected in sorted(outputs.items(), key=lambda item: item[0].as_posix()):
        actual = (root / path).read_bytes()
        require(actual == expected, f"R2 byte readback differs: {path.as_posix()}")
        readback_rows.append({"path": path.as_posix(), "bytes": len(actual), "sha256": sha256(actual)})
    require(len(readback_rows) == len(outputs) == 7, "R2 artifact readback denominator changed")
    print(json.dumps({
        "status": "PASS",
        "mode": "emit" if args.emit else "check",
        "generated_artifacts_read_back": len(readback_rows),
        "owner_input_source": result["owner_binding"],
        "source_lineage": result["summary"]["source_lineage_r2"],
        "sha256": {row["path"]: row["sha256"] for row in readback_rows},
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
