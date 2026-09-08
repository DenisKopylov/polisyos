"""Reconcile immutable-base OpenAPI evidence; never assign inherited by totals."""

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
BASE = ROOT / "_build/gy-gaps/m1/openapi-base-replay/checkout"
BASE_PRODUCT = BASE / "policy-engine"
IGNORED = {
    ".git", ".cache", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".venv",
    "__pycache__", "_build", "_cache", "node_modules", "production_data",
}
LINKS = {".venv", "node_modules", "packages/runtime-api-client/node_modules", "apps/runtime-dashboard/node_modules"}


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT.parent), *args])


def copied_inputs(root):
    result = set()
    for parent, directories, files in os.walk(root, followlinks=False):
        descend = []
        for name in directories:
            if name in IGNORED:
                continue
            path = Path(parent) / name
            if path.is_symlink():
                result.add(path.relative_to(root).as_posix())
            else:
                descend.append(name)
        directories[:] = descend
        result.update(
            (Path(parent) / name).relative_to(root).as_posix()
            for name in files if name not in IGNORED
        )
    result.update(link for link in LINKS if (root / link).exists())
    return result


def independent_copied_inputs(root):
    names = []
    for name in sorted(IGNORED):
        if names:
            names.append("-o")
        names.extend(("-name", name))
    command = ["find", str(root), "(", *names, ")", "-prune", "-o", "(", "-type", "f", "-o", "-type", "l", ")", "-print0"]
    paths = subprocess.check_output(command).decode().split("\0")
    result = {Path(path).relative_to(root).as_posix() for path in paths if path}
    result.update(link for link in LINKS if (root / link).exists())
    return result


def finding_identities(receipt):
    identities = set()
    escape_paths = set()
    unknown = []
    for line in receipt["stdout"].splitlines():
        if not line.startswith("- "):
            continue
        if line.startswith("- runtime-openapi-snapshot output probe changed paths"):
            members = line.split("scratch root: ", 1)[1].removesuffix(".").split(", ")
            escape_paths.update(members)
            identities.update(
                ("output_probe_worktree_escape", "runtime-openapi-snapshot", path)
                for path in members
            )
        elif line.startswith("- runtime-openapi-snapshot generated output schemas/runtime_api_v1.openapi.json does not match "):
            identities.add(("generated_output_freshness_mismatch", "runtime-openapi-snapshot", "schemas/runtime_api_v1.openapi.json"))
        else:
            unknown.append(line)
    assert not unknown, unknown
    return identities, escape_paths


def identity_correction():
    old_path = ROOT / "_build/gy-gaps/m1/openapi-p41-reconciliation-final.json"
    output_path = ROOT / "_build/gy-gaps/m1/openapi-p41-identity-correction.json"
    prior_receipt = json.loads((old_path if old_path.exists() else output_path).read_text())
    prior = json.loads(prior_receipt["stdout"])
    removed = {
        "baseline_finding_identities", "lane_finding_identities", "added_finding_identities",
        "lost_finding_identities", "shared_escape_path_witnesses",
        "baseline_only_escape_path_witnesses", "lane_only_escape_path_witnesses",
    }
    report = {key: value for key, value in prior.items() if key not in removed}
    baseline = json.loads((ROOT / "_build/gy-gaps/m1/architecture-base-43580c80b.json").read_text())
    lane = json.loads((ROOT / "_build/gy-gaps/m1/architecture-final.json").read_text())
    before, _ = finding_identities(baseline)
    after, _ = finding_identities(lane)

    def independent_count(receipt):
        return sum(
            len(re.findall(r"(?:isolated-source|policy-engine)/[^, ]+", line))
            if "output probe changed paths" in line else 1
            for line in receipt["stdout"].splitlines() if line.startswith("- ")
        )

    assert len(before) == independent_count(baseline)
    assert len(after) == independent_count(lane)
    report.update({
        "identity_format": "(failure_kind, family_id, exact_affected_path); failure_kind distinguishes scratch escape from the explicit generated-output mismatch message",
        "shared_finding_identities": sorted(before & after),
        "base_only_finding_identities_lost_relative_to_lane": sorted(before - after),
        "lane_only_finding_identities_added_relative_to_base": sorted(after - before),
        "base_finding_identity_count": len(before),
        "base_independent_message_member_count": independent_count(baseline),
        "lane_finding_identity_count": len(after),
        "lane_independent_message_member_count": independent_count(lane),
        "denominator_measurement_started_utc": prior.get("denominator_measurement_started_utc", prior_receipt["started_utc"]),
        "correction": "The previous comparison incorrectly grouped every escape path into one family-level identity. Each path now has its own identity; the collateral base-only paths are reported as lost relative to the lane, not silently grouped.",
        "deciding_reason": "The CAS blob escape, its manifest escape, and schema mismatch reproduce at the immutable lane base. Four collateral escape paths exist only in the base replay because the disposable copy inherited outer Git discovery during concurrent edits. Input intersection remains nonzero, so P41 attribution stays not_established.",
    })
    print(json.dumps(report, indent=2))


def main():
    entries = [row for row in git("ls-tree", "--full-tree", "-r", "-z", "43580c80b").split(b"\0") if row]
    tracked = set()
    mismatch = []
    for entry in entries:
        meta, path_bytes = entry.split(b"\t", 1)
        mode, kind, identity = meta.decode().split()
        if kind != "blob":
            continue
        path = path_bytes.decode()
        tracked.add(path)
        file = BASE / path
        raw = os.readlink(file).encode() if mode == "120000" else file.read_bytes()
        actual = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        if actual != identity:
            mismatch.append(path)
    base_inputs = copied_inputs(BASE_PRODUCT)
    current_inputs = copied_inputs(ROOT)
    base_independent = {
        path.removeprefix("policy-engine/") for path in tracked
        if path.startswith("policy-engine/")
        and not IGNORED.intersection(Path(path).parts)
    }
    current_git = {
        path.removeprefix("policy-engine/") for path in git("ls-files", "--cached", "--others", "--exclude-standard").decode().splitlines()
        if path.startswith("policy-engine/")
        and not IGNORED.intersection(Path(path).parts)
    }
    changed = set(git("diff", "--name-only", "43580c80b").decode().splitlines())
    changed.update(git("ls-files", "--others", "--exclude-standard").decode().splitlines())
    changed = {path.removeprefix("policy-engine/") for path in changed if path.startswith("policy-engine/")}
    final = json.loads((ROOT / "_build/gy-gaps/m1/architecture-final.json").read_text())
    baseline = json.loads((ROOT / "_build/gy-gaps/m1/architecture-base-43580c80b.json").read_text())
    before_ids, before_escapes = finding_identities(baseline)
    after_ids, after_escapes = finding_identities(final)
    http = {path for path in current_inputs if path.startswith("src/polisyos/runtime/http/")}
    http_independent = {
        path.relative_to(ROOT).as_posix() for path in (ROOT / "src/polisyos/runtime/http").rglob("*")
        if (path.is_file() or path.is_symlink()) and not IGNORED.intersection(path.relative_to(ROOT).parts)
    }
    assert not mismatch
    assert base_inputs - LINKS == base_independent
    current_independent = independent_copied_inputs(ROOT)
    assert current_inputs == current_independent
    assert http == http_independent
    report = {
        "base": "43580c80b",
        "source_blob_count": len(tracked),
        "post_replay_source_mismatches": mismatch,
        "exact_gate_command_equal": final["command"] == baseline["command"],
        "base_returncode": baseline["returncode"],
        "lane_returncode": final["returncode"],
        "baseline_finding_identities": sorted(before_ids),
        "lane_finding_identities": sorted(after_ids),
        "added_finding_identities": sorted(after_ids - before_ids),
        "lost_finding_identities": sorted(before_ids - after_ids),
        "shared_escape_path_witnesses": sorted(before_escapes & after_escapes),
        "baseline_only_escape_path_witnesses": sorted(before_escapes - after_escapes),
        "lane_only_escape_path_witnesses": sorted(after_escapes - before_escapes),
        "denominator_definition": "Complete isolated copied-source file/symlink population actually hashed by the output-escape checker; wider than OpenAPI semantic imports. Exact ignored names derive from guardrails._copy_isolated_probe_source, with station links restored. Union of immutable base and current lane.",
        "base_input_count": len(base_inputs),
        "base_independent_tracked_count": len(base_independent),
        "base_station_link_count": len(base_inputs & LINKS),
        "current_input_count": len(current_inputs),
        "current_independent_git_count": len(current_git),
        "current_independent_filesystem_count": len(current_independent),
        "copied_station_members_ignored_by_git": sorted(current_inputs - LINKS - current_git),
        "current_station_link_count": len(current_inputs & LINKS),
        "complete_union_input_count": len(base_inputs | current_inputs),
        "changed_path_count": len(changed),
        "changed_input_intersection": sorted(changed & (base_inputs | current_inputs)),
        "declared_runtime_http_count": len(http),
        "independent_runtime_http_count": len(http_independent),
        "changed_runtime_http_intersection": sorted(changed & http),
        "attribution": "not_established",
        "deciding_reason": "Both OpenAPI finding identities reproduce at the immutable lane base, but the full input denominator intersects lane changes. The disposable copy also inherited outer git discovery, adding concurrent consumer edits to the base escape witnesses. This is preexisting reproduction, not an inherited/disjoint finding.",
        "owner": "architecture/generated_artifacts.toml family runtime-openapi-snapshot; tools.devx.architecture.guardrails._run_required_generated_artifact_checks",
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    identity_correction() if "--identity-correction" in sys.argv else main()
