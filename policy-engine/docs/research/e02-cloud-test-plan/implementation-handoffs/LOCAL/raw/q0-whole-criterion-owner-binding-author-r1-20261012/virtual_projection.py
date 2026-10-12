#!/usr/bin/env python3
"""Run a source-bound virtual repair of the Q0 owner-property projection.

The runner composes the already-declared synthetic emitter fixture in memory,
then patches only the read-only local report projection. It never writes the
registered emitter, source crosswalks, historical packet, or candidate results.
"""
from __future__ import annotations

import argparse
import collections
import copy
import difflib
import hashlib
import importlib.util
import json
import subprocess
import sys
import types
from pathlib import Path
from typing import Any, Callable


ROOT_SEARCH_MARKER = "AGENTS.md"
LEASE = Path(
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/"
    "q0-whole-criterion-owner-binding-author-r1-20261012"
)
DECLARATION = LEASE / "preimage-declaration.json"
PATCH = LEASE / "virtual-projection.patch"
DECISION = LEASE / "binding-decision-packet.json"
CONTROL_SPEC = LEASE / "controls.json"
NEGATIVE_RESULTS = LEASE / "checks/negative-controls.json"
SUMMARY = LEASE / "checks/summary.json"
STDOUT_RECEIPT = LEASE / "checks/projection-self-check.stdout.txt"
STDERR_RECEIPT = LEASE / "checks/projection-self-check.stderr.txt"

EMITTER = Path(
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/emit_proposals.py"
)
IDENTITY = Path(
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/"
    "full-id-occurrence-identity-repair-r1-20261011/occurrence_identity.py"
)
REPORT_BUILDER = Path(
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/"
    "q0-full-occurrence-report-author-20261011/virtual_emitter.py"
)
OLD_PACKET = REPORT_BUILDER.parent / "proposal-decision-packet.json"
DRAFT = Path(
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/"
    "crosswalk/occurrence-evaluations-draft.json"
)
COVERAGE = Path(
    "policy-engine/docs/research/e02-cloud-test-plan/closure-decisions/coverage.json"
)
FIXTURE_VERIFIER = Path(
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/"
    "q0-full-emitter-fixture-fix-20261012/verify_fixture_fix.py"
)
FIXTURE_PATCH = FIXTURE_VERIFIER.with_name("fixture_patch.diff")
FIXTURE_ENVIRONMENT = FIXTURE_VERIFIER.with_name("synthetic-environment.json")

OLD_OWNER_PROPERTY_LINE = '                "owner_assessed_property": current.get("property"),'
NEW_OWNER_PROPERTY_BLOCK = '''                "owner_assessed_property": None,
                "owner_scoped_assessment_ref": {
                    "source_path": DRAFT_REL.as_posix(),
                    "occurrence_pointer": f"#/occurrences/{row_index}",
                    "assessment_pointer": (
                        f"#/occurrences/{row_index}/technical_assessment/"
                        "current_mechanism_or_bounded_path"
                    ),
                    "property_field_pointer": (
                        f"#/occurrences/{row_index}/technical_assessment/"
                        "current_mechanism_or_bounded_path/property"
                        if current.get("property") is not None
                        else None
                    ),
                    "owner_assessment_row_pointer": technical.get(
                        "owner_assessment_row_pointer"
                    ),
                    "owner_source_refs_pointer": (
                        f"#/occurrences/{row_index}/technical_assessment/owner_source_refs"
                    ),
                },
                "criterion_owner_alignment": {
                    "status": "not_established",
                    "basis": "not_established",
                    "admitted_as_original_whole_property": False,
                    "criterion_ref": {
                        "finding_id": finding_id,
                        "coverage_occurrence_pointer": pointer,
                        "criterion_sha256": digest,
                        "source_path": source_span["path"],
                        "source_commit": source_span["source_commit"],
                        "source_blob": source_span["git_blob"],
                        "lines_1_based_inclusive": source_span[
                            "lines_1_based_inclusive"
                        ],
                    },
                    "owner_scoped_assertion_ref": {
                        "source_path": DRAFT_REL.as_posix(),
                        "pointer": (
                            f"#/occurrences/{row_index}/technical_assessment/"
                            "current_mechanism_or_bounded_path"
                        ),
                        "assessment_row_pointer": technical.get(
                            "owner_assessment_row_pointer"
                        ),
                        "owner_source_refs_pointer": (
                            f"#/occurrences/{row_index}/technical_assessment/owner_source_refs"
                        ),
                    },
                    "required_basis": (
                        "source-qualified independent semantic comparison bound to this exact "
                        "criterion identity and owner assertion"
                    ),
                    "authority_effect": "none",
                },'''

OLD_VALIDATE_RETURN = "    validate_packet(packet, coverage_keys)\n    return packet, declaration, coverage_keys, identity\n"
OLD_VALIDATE_DEF = "def validate_packet(packet: dict[str, Any], expected_keys: list[tuple[str, str, str]]) -> None:"
OLD_EXPECT_REJECTION_DEF = "def expect_rejection("
NEW_VALIDATE_RETURN = '''    packet["criterion_owner_alignment_mechanism"] = {
        "status": "not_established",
        "basis": "not_established",
        "positive_alignment_supported": False,
        "scope": "all 291 canonical occurrence rows",
        "admission_rule": (
            "No owner-scoped assertion or navigation route is admitted as the original "
            "whole criterion in this prototype."
        ),
        "authority_effect": "none",
    }
    validate_packet(packet, coverage_keys)
    return packet, declaration, coverage_keys, identity
'''
VIRTUAL_VALIDATOR_SOURCE = '''def validate_criterion_owner_projection(
    packet: dict[str, Any], expected_keys: list[tuple[str, str, str]]
) -> None:
    """Recompute criterion/owner scope from coverage, source bytes, and the draft."""
    root = repo_root()
    coverage = read_json(root, COVERAGE_REL)
    draft = read_json(root, DRAFT_REL)
    helper = import_module(
        "e02_owner_binding_projection_identity",
        root / IDENTITY_HELPER_REL,
    )
    coverage_keys = helper.coverage_occurrence_keys(coverage, COVERAGE_REL.as_posix())
    draft_keys = helper.draft_occurrence_keys(draft)
    helper.require_same_occurrence_multiset(expected_keys, coverage_keys, label="coverage source bindings")
    helper.require_same_occurrence_multiset(expected_keys, draft_keys, label="owner scoped assertions")
    require(len(set(expected_keys)) == len(expected_keys) == 291, "source identity denominator is not 291 unique occurrences")
    require(len(draft.get("occurrences", [])) == 291, "owner source denominator is not 291 occurrences")
    require(
        packet.get("criterion_owner_alignment_mechanism")
        == {
            "status": "not_established",
            "basis": "not_established",
            "positive_alignment_supported": False,
            "scope": "all 291 canonical occurrence rows",
            "admission_rule": (
                "No owner-scoped assertion or navigation route is admitted as the original "
                "whole criterion in this prototype."
            ),
            "authority_effect": "none",
        },
        "criterion-owner alignment mechanism is not the bounded fail-closed projection",
    )
    source_index = {}
    for finding_index, finding in enumerate(coverage["findings"]):
        for ref_index, criterion in enumerate(finding.get("criterion_refs", [])):
            pointer = f"{COVERAGE_REL.as_posix()}#/findings/{finding_index}/criterion_refs/{ref_index}"
            key = (finding["id"], pointer, criterion["sha256"])
            require(key not in source_index, "coverage repeats a complete occurrence identity")
            document = coverage["criterion_documents"][criterion["document"]]
            source_index[key] = (document, criterion, pointer)
    helper.require_same_occurrence_multiset(expected_keys, list(source_index), label="coverage criterion map")
    draft_by_key = dict(zip(draft_keys, draft["occurrences"], strict=True))
    require(len(draft_by_key) == 291, "owner draft contains duplicate full identities")
    rows = packet_occurrence_rows(packet)
    actual_keys = [
        (row["identity"]["finding_id"], row["identity"]["occurrence_pointer"], row["identity"]["criterion_sha256"])
        for row in rows
    ]
    helper.require_same_occurrence_multiset(expected_keys, actual_keys, label="qualified projection rows")
    require(len(rows) == 291, "qualified projection lost an occurrence")
    source_cache = {}
    worktree_blob_cache = {}
    source_commit_by_path = {}
    for index, (row, key) in enumerate(zip(rows, expected_keys, strict=True)):
        document, criterion, pointer = source_index[key]
        source = row["original_criterion_source"]
        source_path = document["path"]
        source_blob = document["blob"]
        lines = criterion["lines"]
        digest = criterion["sha256"]
        source_commit = source.get("source_commit")
        require(isinstance(source_commit, str) and source_commit, f"source commit missing at occurrence {index}")
        prior_commit = source_commit_by_path.setdefault(source_path, source_commit)
        require(prior_commit == source_commit, f"original source commit drift at occurrence {index}")
        cache_key = (source_commit, source_path)
        if cache_key not in source_cache:
            commit_blob = subprocess.check_output(
                ["git", "rev-parse", f"{source_commit}:{source_path}"], cwd=root, text=True
            ).strip()
            head_blob = subprocess.check_output(
                ["git", "rev-parse", f"HEAD:{source_path}"], cwd=root, text=True
            ).strip()
            current_bytes = (root / source_path).read_bytes()
            worktree_blob = subprocess.check_output(
                ["git", "hash-object", "--stdin"], cwd=root, input=current_bytes, text=False
            ).decode("ascii").strip()
            require(
                commit_blob == source_blob == head_blob == worktree_blob,
                f"source document bytes differ from the coverage blob at occurrence {index}",
            )
            source_cache[cache_key] = subprocess.check_output(
                ["git", "show", f"{source_commit}:{source_path}"], cwd=root
            )
            worktree_blob_cache[source_path] = worktree_blob
        source_lines = source_cache[cache_key].splitlines(keepends=True)
        require(1 <= lines[0] <= lines[1] <= len(source_lines), f"source span is out of bounds at occurrence {index}")
        require(
            sha256_bytes(b"".join(source_lines[lines[0] - 1 : lines[1]])) == digest,
            f"original criterion line-span hash differs from coverage at occurrence {index}",
        )
        expected_source = {
            "path": source_path,
            "source_commit": source_commit,
            "git_blob": source_blob,
            "lines_1_based_inclusive": lines,
            "criterion_sha256": digest,
            "current_worktree_span_sha256_matches_coverage": True,
            "source_pointer": pointer,
            "criterion_text_copied": False,
        }
        require(source == expected_source, f"original source reference drift at occurrence {index}")
        identity_key = row["identity"]
        require(
            (identity_key["finding_id"], identity_key["occurrence_pointer"], identity_key["criterion_sha256"]) == key,
            f"projected source identity drift at occurrence {index}",
        )
        draft_row = draft_by_key[key]
        technical = draft_row["technical_assessment"]
        current = technical["current_mechanism_or_bounded_path"]
        whole = row["whole_property"]
        require(whole.get("owner_assessed_property") is None, f"owner assertion admitted as whole property at occurrence {index}")
        require(whole.get("bounded_mechanism_or_path") == current, f"owner-scoped assertion changed at occurrence {index}")
        owner_pointer = f"#/occurrences/{draft_keys.index(key)}"
        expected_owner = {
            "source_path": DRAFT_REL.as_posix(),
            "occurrence_pointer": owner_pointer,
            "assessment_pointer": f"{owner_pointer}/technical_assessment/current_mechanism_or_bounded_path",
            "property_field_pointer": (
                f"{owner_pointer}/technical_assessment/current_mechanism_or_bounded_path/property"
                if current.get("property") is not None else None
            ),
            "owner_assessment_row_pointer": technical.get("owner_assessment_row_pointer"),
            "owner_source_refs_pointer": f"{owner_pointer}/technical_assessment/owner_source_refs",
        }
        require(whole.get("owner_scoped_assessment_ref") == expected_owner, f"owner scope pointer drift at occurrence {index}")
        expected_alignment = {
            "status": "not_established",
            "basis": "not_established",
            "admitted_as_original_whole_property": False,
            "criterion_ref": {
                "finding_id": key[0],
                "coverage_occurrence_pointer": pointer,
                "criterion_sha256": digest,
                "source_path": source_path,
                "source_commit": source_commit,
                "source_blob": source_blob,
                "lines_1_based_inclusive": lines,
            },
            "owner_scoped_assertion_ref": {
                "source_path": DRAFT_REL.as_posix(),
                "pointer": f"{owner_pointer}/technical_assessment/current_mechanism_or_bounded_path",
                "assessment_row_pointer": technical.get("owner_assessment_row_pointer"),
                "owner_source_refs_pointer": f"{owner_pointer}/technical_assessment/owner_source_refs",
            },
            "required_basis": "source-qualified independent semantic comparison bound to this exact criterion identity and owner assertion",
            "authority_effect": "none",
        }
        require(whole.get("criterion_owner_alignment") == expected_alignment, f"alignment status or binding drift at occurrence {index}")
        require(whole.get("original_acceptance_boundary") == draft_row.get("original_acceptance_boundary"), f"original criterion boundary drift at occurrence {index}")


def validate_packet(packet: dict[str, Any], expected_keys: list[tuple[str, str, str]]) -> None:
    """Validate base ledger invariants and source-bound owner/criterion separation."""
    _validate_packet_base(packet, expected_keys)
    validate_criterion_owner_projection(packet, expected_keys)


'''


def repo_root() -> Path:
    """Find the repository root from this local ignored lease."""
    for parent in Path(__file__).resolve().parents:
        if (parent / ROOT_SEARCH_MARKER).is_file() and (parent / "policy-engine").is_dir():
            return parent
    raise RuntimeError("repository root not found")


def sha256(data: bytes) -> str:
    """Return a lowercase SHA-256 digest."""
    return hashlib.sha256(data).hexdigest()


def stable_json(value: Any) -> bytes:
    """Serialize a local packet deterministically without copying source text."""
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def require(condition: bool, message: str) -> None:
    """Fail closed with one actionable diagnostic."""
    if not condition:
        raise ValueError(message)


def read_json(root: Path, path: str | Path) -> dict[str, Any]:
    """Read one JSON object from a repository-relative path."""
    value = json.loads((root / path).read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"expected JSON object: {path}")
    return value


def git_text(root: Path, *args: str) -> str:
    """Run a read-only Git query."""
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def import_path(name: str, path: Path) -> Any:
    """Import one pinned local module by exact path."""
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def verify_preimages(root: Path, declaration: dict[str, Any]) -> None:
    """Verify every declared report, source, and review preimage byte-for-byte."""
    require(
        declaration.get("schema")
        == "policyos.e02.q0_whole_criterion_owner_binding_preimage_declaration.v1",
        "unexpected preimage-declaration schema",
    )
    require(
        declaration.get("status")
        == "PREIMAGES_VERIFIED_ALL_NEW_TARGETS_ABSENT_BEFORE_VIRTUAL_PROJECTION",
        "preimage declaration is not the frozen preimplementation record",
    )
    for item in declaration.get("source_preimages", []):
        raw = (root / item["path"]).read_bytes()
        require(len(raw) == item["bytes"], f"source byte-count drift: {item['path']}")
        require(sha256(raw) == item["sha256"], f"source SHA-256 drift: {item['path']}")
    expected_emitter = declaration["canonical_emitter"]["sha256"]
    require(sha256((root / EMITTER).read_bytes()) == expected_emitter, "registered emitter preimage drift")
    require(
        sha256((root / REPORT_BUILDER).read_bytes())
        == declaration["existing_projection_preimage"]["sha256"],
        "read-only report-builder preimage drift",
    )
    require(
        sha256((root / OLD_PACKET).read_bytes())
        == declaration["immutable_prior_report"]["sha256"],
        "immutable prior report packet changed",
    )


def source_lineage(root: Path, declaration: dict[str, Any]) -> dict[str, Any]:
    """Record a descendant source advance only when it misses every input path."""
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
            ["git", "merge-base", "--is-ancestor", base, head], cwd=root, check=False
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
    declared_inputs = {item["path"] for item in declaration["source_preimages"]}
    intersection = sorted(changed & declared_inputs)
    require(not intersection, f"descendant source commit intersects report inputs: {intersection}")
    return {
        "branch": branch,
        "base_head": base,
        "head": head,
        "tree": tree,
        "committed_paths_after_base": len(rows),
        "input_intersection": intersection,
        "ordered_status_path_sha256": sha256("".join(f"{s}\t{p}\n" for s, p in rows).encode()),
        "qualification": "complete committed delta checked; declared Q0/report preimages remain byte-identical",
    }


def projection_overlay(source: bytes) -> bytes:
    """Apply source-bound consumer and validator changes in memory only."""
    text = source.decode("utf-8")
    require(text.count("import sys\n") == 1, "consumer import anchor is not unique")
    text = text.replace("import sys\n", "import sys\nimport subprocess\n", 1)
    require(text.count(OLD_OWNER_PROPERTY_LINE) == 1, "owner property projection anchor is not unique")
    text = text.replace(OLD_OWNER_PROPERTY_LINE, NEW_OWNER_PROPERTY_BLOCK, 1)
    require(text.count(OLD_VALIDATE_RETURN) == 1, "packet validation/return anchor is not unique")
    text = text.replace(OLD_VALIDATE_RETURN, NEW_VALIDATE_RETURN, 1)
    require(text.count(OLD_VALIDATE_DEF) == 1, "base packet validator anchor is not unique")
    text = text.replace(OLD_VALIDATE_DEF, OLD_VALIDATE_DEF.replace("validate_packet", "_validate_packet_base"), 1)
    require(text.count(OLD_EXPECT_REJECTION_DEF) == 1, "negative-control validator insertion anchor is not unique")
    text = text.replace(OLD_EXPECT_REJECTION_DEF, VIRTUAL_VALIDATOR_SOURCE + OLD_EXPECT_REJECTION_DEF, 1)
    return text.encode("utf-8")


def unified_patch(path: Path, before: bytes, after: bytes) -> bytes:
    """Render a zero-fuzz review patch without applying it to its source."""
    old_lines = before.decode("utf-8").splitlines(keepends=True)
    new_lines = after.decode("utf-8").splitlines(keepends=True)
    diff = "".join(
        difflib.unified_diff(old_lines, new_lines, fromfile=f"a/{path.as_posix()}", tofile=f"b/{path.as_posix()}", n=3)
    )
    old_oid = subprocess.check_output(["git", "hash-object", "--stdin"], input=before).decode().strip()
    new_oid = subprocess.check_output(["git", "hash-object", "--stdin"], input=after).decode().strip()
    prefix = f"diff --git a/{path.as_posix()} b/{path.as_posix()}\nindex {old_oid}..{new_oid} 100644\n"
    return (prefix + diff).encode("utf-8")


def compose_fixture_emitter(root: Path) -> tuple[types.ModuleType, dict[str, Any]]:
    """Recreate the historical patch, then replay its shape at the current source."""
    fixture = import_path("q0_owner_binding_fixture_replay", root / FIXTURE_VERIFIER)
    canonical_bytes = (root / EMITTER).read_bytes()
    environment_raw = (root / FIXTURE_ENVIRONMENT).read_bytes()
    environment = json.loads(environment_raw)
    env_digest = sha256(environment_raw)
    candidate = environment["candidate_source"]
    overlay_bytes = fixture.build_overlay(canonical_bytes, env_digest, candidate)
    declared_patch = (root / FIXTURE_PATCH).read_bytes()
    require(
        fixture.unified_patch(canonical_bytes, overlay_bytes) == declared_patch,
        "existing fixture patch no longer composes exactly from its bound inputs",
    )
    apply_result = subprocess.run(
        ["git", "apply", "--check", "--verbose"],
        cwd=root,
        input=declared_patch,
        capture_output=True,
        check=False,
    )
    require(apply_result.returncode == 0, "existing fixture patch fails strict zero-fuzz check")

    # The historical environment is pinned to an earlier source checkpoint. Keep
    # that artifact immutable and run the same typed fixture at the current
    # committed checkpoint using an in-memory manifest. This avoids treating an
    # old candidate_source marker as current evidence while still exercising the
    # real registered emitter path.
    current_candidate = {
        "commit": git_text(root, "rev-parse", "HEAD"),
        "tree": git_text(root, "rev-parse", "HEAD^{tree}"),
    }
    current_environment = copy.deepcopy(environment)
    current_environment["candidate_source"] = current_candidate
    current_environment_raw = stable_json(current_environment)
    current_overlay = fixture.build_overlay(
        canonical_bytes, sha256(current_environment_raw), current_candidate
    )
    current_patch = fixture.unified_patch(canonical_bytes, current_overlay)
    current_patch_check = subprocess.run(
        ["git", "apply", "--check", "--verbose"],
        cwd=root,
        input=current_patch,
        capture_output=True,
        check=False,
    )
    require(current_patch_check.returncode == 0, "current synthetic fixture fails strict zero-fuzz check")
    exit_code, stdout, stderr, error = fixture.run_in_memory(
        root, current_overlay, ["--provisional-review", "--self-check"]
    )
    require(
        exit_code == 0 and error is None,
        f"current-source composed canonical self-check failed: {error or stderr.decode()[:300]}",
    )
    self_check = json.loads(stdout.decode("utf-8"))
    require(self_check.get("mode") == "self_check", "composed fixture run did not execute the registered self-check")
    require(self_check.get("candidate_evaluations_written") == 0, "fixture self-check wrote candidate evaluations")
    module = types.ModuleType("q0_canonical_emitter_fixture_overlay")
    module.__file__ = str((root / EMITTER).resolve())
    exec(compile(current_overlay.decode("utf-8"), module.__file__, "exec"), module.__dict__)
    return module, {
        "patch_path": FIXTURE_PATCH.as_posix(),
        "patch_sha256": sha256(declared_patch),
        "environment_path": FIXTURE_ENVIRONMENT.as_posix(),
        "environment_sha256": env_digest,
        "historical_environment_candidate_source": environment["candidate_source"],
        "historical_patch_exactly_reproduced": True,
        "historical_patch_strict_apply_check_exit_code": apply_result.returncode,
        "historical_patch_check_stdout": apply_result.stdout.decode("utf-8"),
        "historical_patch_check_stderr": apply_result.stderr.decode("utf-8"),
        "historical_fixture_self_check": "not_replayed_against_descendant_source; pinned source marker is historical",
        "current_source_candidate": current_candidate,
        "current_environment_virtual_sha256": sha256(current_environment_raw),
        "current_fixture_patch_virtual_sha256": sha256(current_patch),
        "current_virtual_emitter_sha256": sha256(current_overlay),
        "current_patch_strict_apply_check_exit_code": current_patch_check.returncode,
        "current_patch_check_stdout": current_patch_check.stdout.decode("utf-8"),
        "current_patch_check_stderr": current_patch_check.stderr.decode("utf-8"),
        "git_apply_check_exit_code": apply_result.returncode,
        "self_check_mode": self_check["mode"],
        "candidate_evaluations_written": self_check["candidate_evaluations_written"],
        "self_check_stdout": stdout.decode("utf-8"),
        "self_check_stderr": stderr.decode("utf-8"),
        "self_check_stdout_sha256": sha256(stdout),
        "self_check_stderr_sha256": sha256(stderr),
        "qualification": "synthetic validator-shape fixture only; no runtime/candidate evidence",
    }


def exact_occurrence_keys(packet: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Return all full identities without collapsing repeated finding IDs."""
    return [
        (
            row["identity"]["finding_id"],
            row["identity"]["occurrence_pointer"],
            row["identity"]["criterion_sha256"],
        )
        for finding in packet["findings"]
        for row in finding["occurrences"]
    ]


def coverage_source_index(
    root: Path, coverage: dict[str, Any], source_commit: str
) -> tuple[dict[tuple[str, str, str], dict[str, Any]], dict[str, Any]]:
    """Recompute every original criterion binding from coverage and pinned source bytes."""
    findings = coverage.get("findings")
    documents = coverage.get("criterion_documents")
    require(isinstance(findings, list) and isinstance(documents, dict), "coverage source index is invalid")
    index: dict[tuple[str, str, str], dict[str, Any]] = {}
    source_file_types: collections.Counter[str] = collections.Counter()
    source_blobs: dict[str, str] = {}
    source_cache: dict[str, bytes] = {}
    for finding_index, finding in enumerate(findings):
        finding_id = finding.get("id")
        refs = finding.get("criterion_refs")
        require(isinstance(finding_id, str) and isinstance(refs, list), "coverage finding identity/refs are invalid")
        for ref_index, ref in enumerate(refs):
            document_key = ref.get("document")
            metadata = documents.get(document_key)
            require(isinstance(metadata, dict), f"coverage document metadata missing for occurrence {finding_index}/{ref_index}")
            source_path = metadata.get("path")
            source_blob = metadata.get("blob")
            lines = ref.get("lines")
            digest = ref.get("sha256")
            require(
                isinstance(source_path, str)
                and isinstance(source_blob, str)
                and isinstance(lines, list)
                and len(lines) == 2
                and all(isinstance(line, int) and not isinstance(line, bool) and line > 0 for line in lines)
                and lines[0] <= lines[1]
                and isinstance(digest, str)
                and len(digest) == 64,
                f"coverage criterion source fields are invalid at {finding_index}/{ref_index}",
            )
            require(
                all(character in "0123456789abcdef" for character in digest),
                f"coverage criterion hash is not lowercase SHA-256 at {finding_index}/{ref_index}",
            )
            pointer = f"{COVERAGE.as_posix()}#/findings/{finding_index}/criterion_refs/{ref_index}"
            key = (finding_id, pointer, digest)
            require(key not in index, f"coverage repeats a full occurrence identity: {key}")
            source_file_types[Path(source_path).suffix.lstrip(".") or "extensionless"] += 1
            source_blobs[source_path] = source_blob
            source_bytes = source_cache.get(source_path)
            if source_bytes is None:
                historical_blob = git_text(root, "rev-parse", f"{source_commit}:{source_path}")
                head_blob = git_text(root, "rev-parse", f"HEAD:{source_path}")
                current_bytes = (root / source_path).read_bytes()
                worktree_blob = subprocess.check_output(
                    ["git", "hash-object", "--stdin"], cwd=root, input=current_bytes
                ).decode("ascii").strip()
                require(
                    historical_blob == source_blob == head_blob == worktree_blob,
                    f"original source blob differs from coverage at {finding_id} {pointer}",
                )
                source_bytes = subprocess.check_output(
                    ["git", "show", f"{source_commit}:{source_path}"], cwd=root
                )
                source_cache[source_path] = source_bytes
            source_lines = source_bytes.splitlines(keepends=True)
            require(lines[1] <= len(source_lines), f"original criterion span exceeds its source at {finding_id}")
            span = b"".join(source_lines[lines[0] - 1 : lines[1]])
            require(sha256(span) == digest, f"original criterion span hash differs from coverage at {finding_id}")
            index[key] = {
                "finding_id": finding_id,
                "coverage_occurrence_pointer": pointer,
                "criterion_sha256": digest,
                "source_path": source_path,
                "source_commit": source_commit,
                "source_blob": source_blob,
                "lines_1_based_inclusive": lines,
                "source_pointer": pointer,
                "criterion_text_copied": False,
            }
    require(len(index) == 291, "coverage source index does not cover all 291 canonical occurrences")
    require(
        coverage.get("denominator", {}).get("findings") == 282
        and coverage.get("denominator", {}).get("canonical_source_block_occurrences") == 291,
        "coverage's declared denominator differs from the source walk",
    )
    source_document_types = collections.Counter(
        Path(path).suffix.lstrip(".") or "extensionless" for path in source_blobs
    )
    require(set(source_document_types) == {"md"} and len(source_blobs) == 2, "original source document inventory changed")
    return index, {
        "coverage_path": COVERAGE.as_posix(),
        "coverage_file_type_denominator": {"json": 1},
        "canonical_occurrences_walked": len(index),
        "distinct_finding_ids": len({key[0] for key in index}),
        "criterion_source_reference_file_type_denominator": dict(sorted(source_file_types.items())),
        "original_source_commit": source_commit,
        "original_source_documents": len(source_blobs),
        "source_document_file_type_denominator": dict(sorted(source_document_types.items())),
        "coverage_blobs_match_historical_head_and_worktree": True,
        "all_original_line_span_hashes_recomputed": True,
        "criterion_text_copied": False,
    }


def validate_alignment_row(
    row: dict[str, Any],
    index: int,
    draft_row: dict[str, Any],
    draft_path: Path,
    expected_source: dict[str, Any],
) -> None:
    """Check one emitted row against the exact original criterion and owner row."""
    identity = row.get("identity", {})
    source = row.get("original_criterion_source", {})
    whole = row.get("whole_property", {})
    alignment = whole.get("criterion_owner_alignment", {})
    current = draft_row.get("technical_assessment", {}).get("current_mechanism_or_bounded_path")
    technical = draft_row.get("technical_assessment", {})
    require(isinstance(current, dict), f"draft owner scope is missing at occurrence {index}")
    require(whole.get("owner_assessed_property") is None, f"owner assertion admitted as whole property at occurrence {index}")
    require(whole.get("bounded_mechanism_or_path") == current, f"owner-scoped assertion changed at occurrence {index}")
    prefix = f"{draft_path.as_posix()}#/occurrences/{index}"
    expected_owner_scope = {
        "source_path": draft_path.as_posix(),
        "occurrence_pointer": f"#/occurrences/{index}",
        "assessment_pointer": (
            f"#/occurrences/{index}/technical_assessment/"
            "current_mechanism_or_bounded_path"
        ),
        "property_field_pointer": (
            f"#/occurrences/{index}/technical_assessment/"
            "current_mechanism_or_bounded_path/property"
            if current.get("property") is not None
            else None
        ),
        "owner_assessment_row_pointer": technical.get("owner_assessment_row_pointer"),
        "owner_source_refs_pointer": (
            f"#/occurrences/{index}/technical_assessment/owner_source_refs"
        ),
    }
    require(whole.get("owner_scoped_assessment_ref") == expected_owner_scope, f"owner scope reference drift at occurrence {index}")
    source_pointer = source.get("source_pointer")
    for field in (
        "path",
        "source_commit",
        "git_blob",
        "lines_1_based_inclusive",
        "criterion_sha256",
        "source_pointer",
        "criterion_text_copied",
    ):
        require(
            source.get(field) == expected_source.get(
                "source_path" if field == "path" else "source_blob" if field == "git_blob" else field
            ),
            f"original criterion source binding drift at occurrence {index}: {field}",
        )
    require(
        source.get("current_worktree_span_sha256_matches_coverage") is True,
        f"original criterion current-source span is not verified at occurrence {index}",
    )
    criterion = {
        "finding_id": identity.get("finding_id"),
        "coverage_occurrence_pointer": expected_source["coverage_occurrence_pointer"],
        "criterion_sha256": expected_source["criterion_sha256"],
        "source_path": expected_source["source_path"],
        "source_commit": expected_source["source_commit"],
        "source_blob": expected_source["source_blob"],
        "lines_1_based_inclusive": expected_source["lines_1_based_inclusive"],
    }
    require(source_pointer == criterion["coverage_occurrence_pointer"], f"original criterion pointer drift at occurrence {index}")
    require(source.get("criterion_sha256") == identity.get("criterion_sha256"), f"original criterion hash drift at occurrence {index}")
    expected_alignment = {
        "status": "not_established",
        "basis": "not_established",
        "admitted_as_original_whole_property": False,
        "criterion_ref": criterion,
        "owner_scoped_assertion_ref": {
            "source_path": draft_path.as_posix(),
            "pointer": (
                f"#/occurrences/{index}/technical_assessment/"
                "current_mechanism_or_bounded_path"
            ),
            "assessment_row_pointer": technical.get("owner_assessment_row_pointer"),
            "owner_source_refs_pointer": (
                f"#/occurrences/{index}/technical_assessment/owner_source_refs"
            ),
        },
        "required_basis": (
            "source-qualified independent semantic comparison bound to this exact "
            "criterion identity and owner assertion"
        ),
        "authority_effect": "none",
    }
    require(alignment == expected_alignment, f"criterion-owner alignment is not source-bound/not_established at occurrence {index}")
    require(whole.get("original_acceptance_boundary") == draft_row.get("original_acceptance_boundary"), f"original acceptance boundary changed at occurrence {index}")
    require(prefix == whole.get("property_review_refs", {}).get("draft_occurrence"), f"draft occurrence reference drift at occurrence {index}")


def validate_projection(
    packet: dict[str, Any],
    expected_keys: list[tuple[str, str, str]],
    identity: Any,
    draft: dict[str, Any],
    draft_path: Path,
    source_index: dict[tuple[str, str, str], dict[str, Any]],
) -> None:
    """Validate the complete consumer projection, not merely field markers."""
    mechanism = packet.get("criterion_owner_alignment_mechanism")
    require(
        mechanism
        == {
            "status": "not_established",
            "basis": "not_established",
            "positive_alignment_supported": False,
            "scope": "all 291 canonical occurrence rows",
            "admission_rule": (
                "No owner-scoped assertion or navigation route is admitted as the original "
                "whole criterion in this prototype."
            ),
            "authority_effect": "none",
        },
        "whole-criterion alignment mechanism is not the fail-closed bounded prototype",
    )
    findings = packet.get("findings")
    require(isinstance(findings, list), "report findings must be an array")
    rows = [row for finding in findings for row in finding.get("occurrences", [])]
    require(len(findings) == 282 and len(rows) == 291, "full report denominator changed")
    actual_keys = exact_occurrence_keys(packet)
    identity.require_same_occurrence_multiset(expected_keys, actual_keys, label="owner-binding projection")
    identity.require_same_occurrence_multiset(expected_keys, list(source_index), label="coverage source index")
    draft_keys = identity.draft_occurrence_keys(draft)
    require(draft_keys == expected_keys, "draft row order differs from the full occurrence source order")
    require(len(draft["occurrences"]) == 291, "draft occurrence denominator changed")
    for index, row in enumerate(rows):
        key = (
            row["identity"]["finding_id"],
            row["identity"]["occurrence_pointer"],
            row["identity"]["criterion_sha256"],
        )
        validate_alignment_row(
            row, index, draft["occurrences"][index], draft_path, source_index[key]
        )
    require(packet.get("authority_boundary", {}).get("formal_G") == "not_adjudicated", "formal G changed")
    require(packet.get("authority_boundary", {}).get("formal_closure_ids") == [], "formal closure IDs changed")
    require(packet.get("authority_boundary", {}).get("source_freeze") == "provisional_source_checkpoint_not_frozen", "source freeze was promoted")
    require(packet.get("status_summary", {}).get("candidate_evaluation_by_occurrence") == {"UNRUN": 291}, "candidate states changed")


def expect_alignment_rejection(
    label: str,
    mutated_row: dict[str, Any],
    index: int,
    draft_row: dict[str, Any],
    draft_path: Path,
    expected_source: dict[str, Any],
) -> dict[str, str]:
    """Record one negative row probe only when the real row validator rejects it."""
    try:
        validate_alignment_row(mutated_row, index, draft_row, draft_path, expected_source)
    except (AssertionError, KeyError, TypeError, ValueError) as exc:
        return {"name": label, "result": "REJECTED_AS_REQUIRED", "reason": str(exc).splitlines()[0][:220]}
    raise ValueError(f"alignment validator accepted mutation: {label}")


def expect_packet_rejection(
    label: str,
    packet: dict[str, Any],
    expected_keys: list[tuple[str, str, str]],
    validator: Callable[[dict[str, Any], list[tuple[str, str, str]]], None],
) -> dict[str, str]:
    """Record one rejection by the virtual consumer's actual packet validator."""
    try:
        validator(packet, expected_keys)
    except (AssertionError, KeyError, TypeError, ValueError) as exc:
        return {"name": label, "result": "REJECTED_AS_REQUIRED", "reason": str(exc).splitlines()[0][:220]}
    raise ValueError(f"virtual consumer validator accepted mutation: {label}")


def run_alignment_controls(
    packet: dict[str, Any],
    draft: dict[str, Any],
    draft_path: Path,
    source_index: dict[tuple[str, str, str], dict[str, Any]],
    packet_validator: Callable[[dict[str, Any], list[tuple[str, str, str]]], None],
    expected_keys: list[tuple[str, str, str]],
) -> dict[str, Any]:
    """Falsify qualification markers on both examples and the complete 291-row set."""
    rows = [row for finding in packet["findings"] for row in finding["occurrences"]]
    draft_rows = draft["occurrences"]
    require(len(rows) == len(draft_rows) == 291, "negative-control denominator changed")
    controls: list[dict[str, Any]] = []
    for index, (row, draft_row) in enumerate(zip(rows, draft_rows, strict=True)):
        key = (
            row["identity"]["finding_id"],
            row["identity"]["occurrence_pointer"],
            row["identity"]["criterion_sha256"],
        )
        mutated = copy.deepcopy(row)
        current = draft_row["technical_assessment"]["current_mechanism_or_bounded_path"]
        # Keep status/basis/admission markers, but restore the old unqualified
        # owner value and remove the exact content binding that disambiguates it.
        mutated["whole_property"]["owner_assessed_property"] = (
            current.get("property") if current.get("property") is not None else "unqualified owner assertion"
        )
        alignment = mutated["whole_property"]["criterion_owner_alignment"]
        alignment.pop("criterion_ref", None)
        alignment.pop("owner_scoped_assertion_ref", None)
        controls.append(
            expect_alignment_rejection(
                "qualification_removed_markers_retained_all_291" if index == 0 else f"qualification_removed_markers_retained_row_{index}",
                mutated,
                index,
                draft_row,
                draft_path,
                source_index[key],
            )
        )
    require(len(controls) == 291, "complete row-level qualifier falsifier did not run")
    diagnostic_ids = {"LA-033", "B26"}
    rows_by_id = {
        row["identity"]["finding_id"]: (index, row, draft_rows[index])
        for index, row in enumerate(rows)
        if row["identity"]["finding_id"] in diagnostic_ids
    }
    require(set(rows_by_id) == diagnostic_ids, "two supplied P40 examples are not present")
    explicit_examples = []
    for finding_id in ("LA-033", "B26"):
        index, row, draft_row = rows_by_id[finding_id]
        mutated = copy.deepcopy(row)
        mutated_alignment = mutated["whole_property"]["criterion_owner_alignment"]
        mutated_alignment["status"] = "independently_reconciled"
        mutated_alignment["basis"] = "owner role refs present"
        mutated_alignment["admitted_as_original_whole_property"] = True
        explicit_examples.append(
            expect_alignment_rejection(
                f"self_labeled_alignment_without_independent_basis_{finding_id}",
                mutated,
                index,
                draft_row,
                draft_path,
                source_index[(row["identity"]["finding_id"], row["identity"]["occurrence_pointer"], row["identity"]["criterion_sha256"])],
            )
        )
    index, row, draft_row = rows_by_id["LA-033"]
    mutated = copy.deepcopy(row)
    mutated["whole_property"]["criterion_owner_alignment"]["criterion_ref"]["criterion_sha256"] = "0" * 64
    controls.append(
        expect_alignment_rejection(
            "criterion_hash_drift_with_markers_retained_LA-033",
            mutated,
            index,
            draft_row,
            draft_path,
            source_index[(row["identity"]["finding_id"], row["identity"]["occurrence_pointer"], row["identity"]["criterion_sha256"])],
        )
    )
    mutated = copy.deepcopy(row)
    mutated["whole_property"]["criterion_owner_alignment"]["owner_scoped_assertion_ref"]["pointer"] = "#/rows/0"
    controls.append(
        expect_alignment_rejection(
            "owner_scope_pointer_drift_with_markers_retained_LA-033",
            mutated,
            index,
            draft_row,
            draft_path,
            source_index[(row["identity"]["finding_id"], row["identity"]["occurrence_pointer"], row["identity"]["criterion_sha256"])],
        )
    )
    mutated = copy.deepcopy(row)
    wrong_path = "policy-engine/docs/plans/forged.md"
    source = mutated["original_criterion_source"]
    source["path"] = wrong_path
    source["git_blob"] = "0" * 40
    source["lines_1_based_inclusive"] = [1, 2]
    criterion_ref = mutated["whole_property"]["criterion_owner_alignment"]["criterion_ref"]
    criterion_ref["source_path"] = wrong_path
    criterion_ref["source_blob"] = "0" * 40
    criterion_ref["lines_1_based_inclusive"] = [1, 2]
    controls.append(
        expect_alignment_rejection(
            "original_source_span_drift_with_markers_retained_LA-033",
            mutated,
            index,
            draft_row,
            draft_path,
            source_index[(row["identity"]["finding_id"], row["identity"]["occurrence_pointer"], row["identity"]["criterion_sha256"])],
        )
    )
    actual_consumer_controls = []
    mutated_packet = copy.deepcopy(packet)
    mutated_rows = [row for finding in mutated_packet["findings"] for row in finding["occurrences"]]
    for index, (row, draft_row) in enumerate(zip(mutated_rows, draft_rows, strict=True)):
        current = draft_row["technical_assessment"]["current_mechanism_or_bounded_path"]
        row["whole_property"]["owner_assessed_property"] = (
            current.get("property") if current.get("property") is not None else "unqualified owner assertion"
        )
        alignment = row["whole_property"]["criterion_owner_alignment"]
        alignment.pop("criterion_ref", None)
        alignment.pop("owner_scoped_assertion_ref", None)
    actual_consumer_controls.append(
        {
            **expect_packet_rejection(
                "actual_consumer_all_291_qualification_removed_markers_retained",
                mutated_packet,
                expected_keys,
                packet_validator,
            ),
            "rows_mutated": 291,
        }
    )
    for finding_id in ("LA-033", "B26"):
        mutated_packet = copy.deepcopy(packet)
        matching_indices = [
            index for index, row in enumerate(rows)
            if row["identity"]["finding_id"] == finding_id
        ]
        require(bool(matching_indices), f"diagnostic finding has no occurrence: {finding_id}")
        for index in matching_indices:
            target_row = [
                row for finding in mutated_packet["findings"] for row in finding["occurrences"]
            ][index]
            alignment = target_row["whole_property"]["criterion_owner_alignment"]
            alignment["status"] = "independently_reconciled"
            alignment["basis"] = "owner role refs present"
            alignment["admitted_as_original_whole_property"] = True
        actual_consumer_controls.append(
            {
                **expect_packet_rejection(
                    f"actual_consumer_self_labeled_positive_{finding_id}",
                    mutated_packet,
                    expected_keys,
                    packet_validator,
                ),
                "rows_mutated": len(matching_indices),
            }
        )
    source_drift_packet = copy.deepcopy(packet)
    source_drift_rows = [
        row for finding in source_drift_packet["findings"] for row in finding["occurrences"]
    ]
    la033_index = rows_by_id["LA-033"][0]
    source_drift_row = source_drift_rows[la033_index]
    source_drift_row["original_criterion_source"]["path"] = "policy-engine/docs/plans/forged.md"
    source_drift_row["original_criterion_source"]["git_blob"] = "0" * 40
    source_drift_row["original_criterion_source"]["lines_1_based_inclusive"] = [1, 2]
    source_drift_criterion = source_drift_row["whole_property"]["criterion_owner_alignment"]["criterion_ref"]
    source_drift_criterion["source_path"] = "policy-engine/docs/plans/forged.md"
    source_drift_criterion["source_blob"] = "0" * 40
    source_drift_criterion["lines_1_based_inclusive"] = [1, 2]
    actual_consumer_controls.append(
        expect_packet_rejection(
            "actual_consumer_original_source_span_drift_with_markers_retained_LA-033",
            source_drift_packet,
            expected_keys,
            packet_validator,
        )
    )
    return {
        "schema": "policyos.e02.q0_whole_criterion_owner_binding_negative_controls.v1",
        "status": "PASS",
        "whole_291_row_qualifier_falsifier": {
            "rows_probed": len(rows),
            "rows_rejected": sum(item["result"] == "REJECTED_AS_REQUIRED" for item in controls[:291]),
            "method": "For each complete occurrence, remove exact criterion/owner bindings while retaining status markers and restore an unqualified owner value; the row validator must reject.",
        },
        "independent_diagnostic_examples": explicit_examples,
        "actual_consumer_validator_controls": actual_consumer_controls,
        "source_and_pointer_drift": controls[-3:],
        "controls": controls,
    }


def report_summary(
    packet: dict[str, Any],
    fixture: dict[str, Any],
    lineage: dict[str, Any],
    patch: bytes,
    patch_check: subprocess.CompletedProcess[bytes],
    source_audit: dict[str, Any],
) -> dict[str, Any]:
    """Return a small recomputable full-denominator receipt."""
    rows = [row for finding in packet["findings"] for row in finding["occurrences"]]
    routes = [
        route["assignment_pointer"]
        for row in rows
        for route in row["next_check"]["task_routes_navigation_only"]
    ]
    owner_fields: collections.Counter[str] = collections.Counter()
    for row in rows:
        current = row["whole_property"]["bounded_mechanism_or_path"]
        if current.get("property"):
            owner_fields["property"] += 1
        elif current.get("property_title_or_boundary"):
            owner_fields["property_title_or_boundary"] += 1
        elif current.get("bounded_property"):
            owner_fields["bounded_property"] += 1
        elif current.get("D45_runtime_property"):
            owner_fields["D45_runtime_property"] += 1
        else:
            owner_fields["owner_property_not_established"] += 1
    require(sum(owner_fields.values()) == 291, "owner assertion field census does not cover all occurrences")
    require(owner_fields == collections.Counter({
        "property": 96,
        "property_title_or_boundary": 59,
        "bounded_property": 36,
        "D45_runtime_property": 46,
        "owner_property_not_established": 54,
    }), "owner assertion field composition changed from its source-bound census")
    return {
        "status": "PASS",
        "mode": "self_check",
        "source_checkpoint": packet["source_checkpoint"],
        "source_lineage": lineage,
        "original_criterion_source_validation": source_audit,
        "fixture_overlay": fixture,
        "report_projection_patch": {
            "target": REPORT_BUILDER.as_posix(),
            "base_sha256": sha256((repo_root() / REPORT_BUILDER).read_bytes()),
            "virtual_sha256": sha256(projection_overlay((repo_root() / REPORT_BUILDER).read_bytes())),
            "patch_bytes": len(patch),
            "patch_sha256": sha256(patch),
            "strict_zero_fuzz_check": {
                "argv": ["git", "apply", "--check", "--verbose"],
                "exit_code": patch_check.returncode,
                "stdout": patch_check.stdout.decode("utf-8"),
                "stderr": patch_check.stderr.decode("utf-8"),
            },
            "applied_to_source": False,
        },
        "denominator": {
            "finding_ids": packet["denominator"]["finding_ids"],
            "occurrences": len(rows),
            "unique_full_occurrence_identities": len(set(exact_occurrence_keys(packet))),
            "owner_scoped_field_census": dict(sorted(owner_fields.items())),
            "distinct_task_assignment_refs": len(set(routes)),
            "expanded_occurrence_route_refs": len(routes),
        },
        "candidate_statuses": packet["status_summary"]["candidate_evaluation_by_occurrence"],
        "formal_closure_ids": packet["authority_boundary"]["formal_closure_ids"],
        "formal_G": packet["authority_boundary"]["formal_G"],
        "all_291_alignment_states": "not_established",
        "owner_assessed_property_non_null_rows": sum(
            row["whole_property"].get("owner_assessed_property") is not None for row in rows
        ),
        "historical_source_author_closed_ids": 198,
        "B198_preserved": packet["B198_preservation"]["formal_closure"] is False,
        "qualification": "virtual source-free report projection; not source freeze, runtime result, independent semantic adjudication, or formal closure",
    }


def decision_packet(summary: dict[str, Any], declaration: dict[str, Any]) -> dict[str, Any]:
    """Record the bounded repair decision, alternatives, and consequences."""
    examples = declaration["criterion_owner_example"]
    b26 = {
        "finding_id": "B26",
        "coverage_occurrence_pointer": "policy-engine/docs/research/e02-cloud-test-plan/closure-decisions/coverage.json#/findings/151/criterion_refs/0",
        "criterion_sha256": "5463d473d7e526f8ae3debc24fee9850889ed6c33dfbd4bcd44ae05dab8ea5a2",
        "original_source": {
            "path": "policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/B_r19_original.md",
            "source_commit": "198076863e143dea9f89f02734b13d50dae3eed5",
            "source_blob": "d800082eebfc12eaf647b0c0257c4f06e135d25a",
            "lines_1_based_inclusive": [517, 530],
        },
        "owner_scoped_assertion": {
            "draft_path": DRAFT.as_posix(),
            "draft_occurrence_pointer": "#/occurrences/151",
            "owner_assessment_row_pointer": "#/rows/21",
        },
        "provenance_qualification": "root-supplied second SAME_CLASS_DEEPER example; source/draft identity is bound by the input preimages, new complement review stream is not treated as frozen here",
    }
    la033 = {
        "finding_id": "LA-033",
        "coverage_occurrence_pointer": examples["original_criterion"]["coverage_occurrence_pointer"],
        "criterion_sha256": examples["original_criterion"]["criterion_sha256"],
        "original_source": {
            "path": examples["original_criterion"]["source_path"],
            "source_commit": examples["original_criterion"]["source_commit"],
            "source_blob": examples["original_criterion"]["source_blob"],
            "lines_1_based_inclusive": examples["original_criterion"]["lines_1_based_inclusive"],
        },
        "owner_scoped_assertion": {
            "draft_path": examples["owner_scoped_assertion"]["draft_path"],
            "draft_occurrence_pointer": examples["owner_scoped_assertion"]["draft_occurrence_pointer"],
            "property_pointer": examples["owner_scoped_assertion"]["scoped_property_pointer"],
            "owner_assessment_row_pointer": examples["owner_scoped_assertion"]["assessment_row_pointer"],
        },
        "independent_review_ref": {
            "path": "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/reviews/q0-original-criterion-complement-bucket1-independent-r1-20261012/complement-bucket1-independent-review.json",
            "sha256": "f5acf8ea7f3a37b0ec339ae993115d220deeb6cf91c2b84a1331163505e46b64",
            "qualification": "source-qualified review ref; this virtual repair does not convert review into authority closure or runtime evidence",
        },
    }
    return {
        "schema": "policyos.e02.q0_whole_criterion_owner_binding_decision_packet.v1",
        "status": "VIRTUAL_CONSUMER_PROJECTION_ONLY",
        "decision": "Keep the original criterion and owner-scoped assertion separate. Withhold `owner_assessed_property` as a whole-property claim until a source-qualified independent semantic binding is actually available; current prototype supports only not_established.",
        "pattern_pass": {
            "P40_bucket": "NEW_CLASS criterion↔owner scoped-property misbinding; B26 is SAME_CLASS_DEEPER, so repair the all-291 projection mechanism rather than patching LA-033 alone.",
            "relevant_register_ids": ["P32", "P36", "P37", "P38", "P40"],
            "existing_anti_pattern": "The report consumer copies the owner current_mechanism.property into the field named owner_assessed_property under whole_property without an independent criterion↔owner semantic binding.",
            "property": "The original source-qualified whole criterion for each occurrence remains distinct from a narrower owner-scoped mechanism/assertion.",
            "implementation": "The current consumer projected owner property field; the virtual repair emits it as null and retains the exact owner assertion pointer under a separate scoped reference, while binding original criterion identity/source.",
            "divergent_case": "LA-033: original LA_r09 criterion source span vs owner replay/PII-scan scoped assertion. B26: original B_r19 pairwise-vs-global criterion vs owner N5/CAS/fresh-N8 persistence chain.",
            "bounded_state": "all 291 criterion-owner alignments remain not_established; no positive or partial independent alignment is implemented in this prototype",
            "capability_state": "local review projection only; no public surface, runtime candidate execution, or formal adjudication",
        },
        "examples": {"LA-033": la033, "B26": b26},
        "alternatives": [
            {
                "name": "Minimal consumer projection qualification",
                "choice": "selected for virtual review",
                "impact": "Preserves both source sides and the owner mechanism, sets the direct whole-property field to null, and makes every row explicitly not_established until independent binding exists.",
                "compatibility": "Keeps the existing v1 field key but changes an unqualified owner string to null. Consumers that require a string must read the explicit scoped owner reference; no source/crosswalk schema or historical artifact changes.",
                "boundary": "No owner assertion, task route, field role, or self-label can produce an independently reconciled state.",
            },
            {
                "name": "Consolidate alignment admission into the registered emitter",
                "choice": "defer to root design/source-freeze decision",
                "impact": "Would move the crosswalk/whole-property admission contract into the canonical producer and require a typed independent-basis artifact, content-bound admission, and consumer/source-freeze integration.",
                "compatibility": "Broader migration of the registered ledger/report schema and validator; not required to safely render this provisional human-review artifact and no basis contract is established here.",
                "boundary": "A future consolidation must not treat owner role refs, text similarity, marker presence, or SHA-only adjacency as alignment proof.",
            },
            {
                "name": "Keep owner string and add a qualification marker",
                "choice": "rejected",
                "impact": "Leaves the old direct field consumable as a whole-property value and relies on readers to honor a neighboring marker.",
                "failure_class": "P32/P38 marker or proxy gate; fails remove-qualification/keep-markers falsifier.",
            },
        ],
        "preservation": {
            "source_author_closed_ids": 198,
            "B198_history_and_closure": "preserved unchanged; candidate remains UNRUN and formal closure remains false",
            "finding_ids": summary["denominator"]["finding_ids"],
            "occurrences": summary["denominator"]["occurrences"],
            "distinct_task_assignment_refs": summary["denominator"]["distinct_task_assignment_refs"],
            "expanded_occurrence_route_refs": summary["denominator"]["expanded_occurrence_route_refs"],
            "candidate_states": summary["candidate_statuses"],
            "formal_G": summary["formal_G"],
            "formal_closure_ids": summary["formal_closure_ids"],
        },
        "source_checkpoint": summary["source_checkpoint"],
        "original_criterion_source_validation": summary["original_criterion_source_validation"],
        "fixture_overlay": summary["fixture_overlay"],
        "virtual_patch": summary["report_projection_patch"],
        "limitations": [
            "The output is a provisional author/review projection, not a final source freeze or product capability claim.",
            "All 291 candidates remain UNRUN and all formal G states remain not_adjudicated.",
            "The prototype cannot admit positive or partial alignment; a proper source-qualified semantic basis and consumer contract remain a root design decision.",
            "No original criterion text is copied into this packet; source paths, spans, pointers, and hashes are retained.",
        ],
    }


def control_spec() -> dict[str, Any]:
    """Describe the property probes without duplicating their derived results."""
    return {
        "schema": "policyos.e02.q0_whole_criterion_owner_binding_controls.v1",
        "property": "An owner-scoped mechanism is not admitted as the original whole criterion absent an independently source-qualified semantic binding.",
        "consumer_under_test": REPORT_BUILDER.as_posix(),
        "producer_reused": EMITTER.as_posix(),
        "probe_plan": [
            "Walk all 291 original occurrence identities; preserve duplicate finding IDs as distinct (finding_id, coverage_pointer, criterion_sha256) rows.",
            "Bind each original criterion ref to its pinned source path, commit, blob, span, and hash; bind each owner assertion to its exact draft occurrence and source refs.",
            "Falsify all 291 rows by removing exact criterion/owner binding refs while keeping status markers and re-exposing the old owner field; all must reject.",
            "Falsify LA-033 and B26 self-labeled positive alignment; both must reject without a source-qualified independent basis.",
            "Mutate a criterion hash and owner pointer while markers remain; the source-bound validator must reject.",
            "Retain UNRUN, formal not_adjudicated, empty formal closure IDs, historical 198/ B198, and 319/331 route counters.",
        ],
        "decision_boundary": "This prototype has only a not_established outcome; it cannot admit any positive or partial alignment.",
    }


def generate(root: Path) -> dict[str, Any]:
    """Build and validate the virtual projection without writing source inputs."""
    declaration = read_json(root, DECLARATION)
    verify_preimages(root, declaration)
    lineage = source_lineage(root, declaration)
    coverage = read_json(root, COVERAGE)
    source_commit = declaration["criterion_owner_example"]["original_criterion"]["source_commit"]
    source_index, source_audit = coverage_source_index(root, coverage, source_commit)
    canonical_overlay, fixture_summary = compose_fixture_emitter(root)
    old_builder_bytes = (root / REPORT_BUILDER).read_bytes()
    patched_builder_bytes = projection_overlay(old_builder_bytes)
    patch_bytes = unified_patch(REPORT_BUILDER, old_builder_bytes, patched_builder_bytes)
    patch_check = subprocess.run(
        ["git", "apply", "--check", "--verbose"],
        cwd=root,
        input=patch_bytes,
        capture_output=True,
        check=False,
    )
    require(patch_check.returncode == 0, "report projection patch fails strict zero-fuzz check")

    builder = types.ModuleType("q0_whole_criterion_owner_projection")
    builder.__file__ = str((root / REPORT_BUILDER).resolve())
    exec(compile(patched_builder_bytes.decode("utf-8"), builder.__file__, "exec"), builder.__dict__)
    original_import = builder.import_module

    def import_with_fixture(name: str, path: Path) -> Any:
        if name == "e02_registered_emit_proposals":
            return canonical_overlay
        return original_import(name, path)

    builder.import_module = import_with_fixture
    composed_validator: Callable[..., Any] = builder.validate_packet
    draft = read_json(root, DRAFT)
    def combined_validator(packet: dict[str, Any], expected_keys: list[tuple[str, str, str]]) -> None:
        composed_validator(packet, expected_keys)
        bound_identity = sys.modules.get("e02_registered_occurrence_identity")
        require(bound_identity is not None, "registered report identity helper was not loaded")
        require(
            Path(bound_identity.__file__).resolve() == (root / IDENTITY).resolve()
            and sha256((root / IDENTITY).read_bytes())
            == declaration["identity_helper"]["sha256"],
            "report identity helper differs from the declared source-qualified helper",
        )
        validate_projection(packet, expected_keys, bound_identity, draft, DRAFT, source_index)

    builder.validate_packet = combined_validator
    packet, _, expected_keys, packet_identity = builder.build_packet()
    require(
        Path(packet_identity.__file__).resolve() == (root / IDENTITY).resolve()
        and sha256((root / IDENTITY).read_bytes())
        == declaration["identity_helper"]["sha256"],
        "report identity helper differs from the declared source-qualified helper",
    )
    identity = packet_identity
    # Re-run both validators over the emitted object and the immutable prior
    # packet so the only semantic change is the current virtual projection.
    combined_validator(packet, expected_keys)
    old_packet = read_json(root, OLD_PACKET)
    builder._validate_packet_base(old_packet, expected_keys)
    prior_checkpoint = old_packet["source_checkpoint"]
    require(prior_checkpoint.get("head") == "d24fdfc9d79ea109b4aa102cc6856a3cd8985583", "immutable prior report checkpoint changed")
    original_controls = builder.run_negative_controls(packet, expected_keys, packet_identity)
    require(original_controls.get("status") == "PASS", "existing full-occurrence identity/authority controls failed")
    alignment_controls = run_alignment_controls(
        packet, draft, DRAFT, source_index, combined_validator, expected_keys
    )
    summary = report_summary(
        packet, fixture_summary, lineage, patch_bytes, patch_check, source_audit
    )
    decisions = decision_packet(summary, declaration)
    controls = control_spec()
    controls["prior_full_occurrence_controls"] = {
        "status": original_controls["status"],
        "negative_control_count": len(original_controls["negative_controls"]),
        "property": original_controls["property"],
    }
    controls["whole_criterion_owner_controls"] = {
        "status": alignment_controls["status"],
        "all_291_qualification_removal_probes": alignment_controls["whole_291_row_qualifier_falsifier"],
        "diagnostic_examples": ["LA-033", "B26"],
        "source_and_pointer_drift_probes": [item["name"] for item in alignment_controls["source_and_pointer_drift"]],
    }
    outputs = {
        PATCH: patch_bytes,
        DECISION: stable_json(decisions),
        CONTROL_SPEC: stable_json(controls),
        NEGATIVE_RESULTS: stable_json(alignment_controls),
        SUMMARY: stable_json(summary),
    }
    return {
        "root": root,
        "declaration": declaration,
        "summary": summary,
        "decisions": decisions,
        "controls": controls,
        "negative_results": alignment_controls,
        "outputs": outputs,
    }


def artifact_bindings(root: Path, outputs: dict[Path, bytes]) -> list[dict[str, Any]]:
    """Summarize generated files after verifying their on-disk readback."""
    rows = []
    for rel, expected in outputs.items():
        actual = (root / rel).read_bytes()
        require(actual == expected, f"generated artifact readback differs: {rel.as_posix()}")
        rows.append({"path": rel.as_posix(), "bytes": len(actual), "sha256": sha256(actual)})
    return rows


def final_receipt(result: dict[str, Any], bindings: list[dict[str, Any]]) -> dict[str, Any]:
    """Create the complete compact command receipt stored as stdout."""
    receipt = copy.deepcopy(result["summary"])
    receipt["generated_artifacts"] = bindings
    receipt["readback"] = {"status": "PASS", "artifacts_rechecked": len(bindings)}
    return receipt


def main() -> int:
    """Emit the virtual review packet or verify every generated byte by readback."""
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--emit", action="store_true", help="write declared ignored local artifacts")
    modes.add_argument("--refresh", action="store_true", help="replace only outputs verified by the prior local receipt")
    modes.add_argument("--check", action="store_true", help="recompute and byte-check declared artifacts")
    args = parser.parse_args()
    root = repo_root()
    result = generate(root)
    outputs: dict[Path, bytes] = result["outputs"]

    if args.emit:
        for rel in outputs:
            path = root / rel
            require(not path.exists(), f"refusing to overwrite an existing artifact: {rel.as_posix()}")
        for rel, data in outputs.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    elif args.refresh:
        prior_receipt = read_json(root, STDOUT_RECEIPT)
        prior_rows = prior_receipt.get("generated_artifacts")
        require(
            prior_receipt.get("readback", {}).get("status") == "PASS"
            and isinstance(prior_rows, list),
            "refresh requires a prior successful artifact readback receipt",
        )
        prior_bindings = {row.get("path"): row for row in prior_rows if isinstance(row, dict)}
        require(
            set(prior_bindings) == {path.as_posix() for path in outputs},
            "refresh output path set differs from the prior receipt",
        )
        for rel in outputs:
            path = root / rel
            row = prior_bindings[rel.as_posix()]
            current = path.read_bytes()
            require(
                len(current) == row.get("bytes") and sha256(current) == row.get("sha256"),
                f"refresh refuses output drift: {rel.as_posix()}",
            )
        for rel, data in outputs.items():
            (root / rel).write_bytes(data)
    else:
        for rel, expected in outputs.items():
            actual = (root / rel).read_bytes()
            require(actual == expected, f"stored artifact differs from recomputed projection: {rel.as_posix()}")

    bindings = artifact_bindings(root, outputs)
    receipt = final_receipt(result, bindings)
    stdout_bytes = stable_json(receipt)
    stderr_bytes = b""
    if args.emit or args.refresh:
        (root / STDOUT_RECEIPT).write_bytes(stdout_bytes)
        (root / STDERR_RECEIPT).write_bytes(stderr_bytes)
    else:
        require((root / STDOUT_RECEIPT).read_bytes() == stdout_bytes, "stored deciding stdout differs from fresh --check")
        require((root / STDERR_RECEIPT).read_bytes() == stderr_bytes, "stored deciding stderr is not the empty success stream")
    sys.stdout.buffer.write(stdout_bytes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
