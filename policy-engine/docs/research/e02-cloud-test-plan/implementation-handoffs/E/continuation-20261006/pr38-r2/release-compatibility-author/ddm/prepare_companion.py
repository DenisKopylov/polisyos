#!/usr/bin/env python3
"""Prepare the G53 DDM release companion without editing the repository."""

import ast
import copy
import difflib
import hashlib
import json
from pathlib import Path
import runpy
import subprocess
import sys
import tomllib

REPO = Path("/workspace/e02-E-continuation-20261006")
ROOT = Path(__file__).parent
BASE = "a2677935015e8a0e7f2dfd5412b671e13fb3175a"
TARGET = (
    "policy-engine/release-fragments/unreleased/2026-10-06-e02-ddm-source-binding.toml"
)


def git(*args):
    return subprocess.check_output(["git", "-C", str(REPO), *args])


def record(data):
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def main():
    evidence_paths = [
        TARGET,
        "policy-engine/docs/research/e02-cloud-test-plan/integration/reviews/E-r2-owner-actions-2026-10-06.md",
        "policy-engine/architecture/gates/compatibility_release.toml",
        "policy-engine/ops/release/release-fragment-policy.toml",
        "policy-engine/release-fragments/template.toml",
        "policy-engine/release-fragments/unreleased/2026-09-21-mig-02-manifest-path-rewrite.toml",
        "policy-engine/tools/ops_runners/release/check_compatibility_release_gates.py",
        "policy-engine/src/polisyos/ddm/integration/model_registry_gate.md",
        "policy-engine/src/polisyos/ddm/integration/model_registry_record.schema.json",
        "policy-engine/src/polisyos/ddm/integration/model_registry_record.v1.schema.json",
        "policy-engine/src/polisyos/ddm/__init__.py",
        "policy-engine/architecture/public_surface/contract.toml",
        "policy-engine/architecture/public_surface/inventory.json",
    ]
    refs = []
    payloads = {}
    for path in evidence_paths:
        data = git("show", BASE + ":" + path)
        payloads[path] = data
        refs.append(
            {
                "source_sha": BASE,
                "path": path,
                "git_blob": git("rev-parse", BASE + ":" + path).decode().strip(),
                **record(data),
            }
        )
    original = payloads[TARGET].decode()
    candidate = original.replace('owner = "E"', 'owner = "team-scientist"', 1)
    candidate = candidate.replace(
        'evidence = ["tests/unit/remediation/test_ddm_02.py", "tests/unit/ddm/test_full_acceptance.py"]',
        'evidence = ["tests/unit/remediation/test_ddm_02.py", "tests/unit/ddm/test_full_acceptance.py", "tests/unit/ddm/test_registry_schema_compatibility.py", "src/polisyos/ddm/integration/model_registry_gate.md"]',
        1,
    )
    candidate = candidate.replace(
        'change_class = "internal"', 'change_class = "persisted-artifact-format"', 1
    )
    candidate += """migration_docs = ["src/polisyos/ddm/integration/model_registry_gate.md"]

[[compatibility_change]]
id = "ddm-registry-record-v2-reader-migration"
change_class = "persisted-artifact-format"
impact = "compatible_with_migration"
surface = "internal: polisyos.ddm persisted ModelRegistryReadinessRecord v1/v2; existing 17-export facade unchanged"
owner = "team-scientist"
version_owner = "team-scientist"
deprecation_window = "Historical unversioned v1 records remain readable; upgrade served readers before v2 emission. No v1 removal date is declared."
release_note = "DDM preserves original strict v1 bytes/schema identity and introduces distinct v2 registry records. New v2 output requires an upgraded reader; prerelease enriched records require explicit migration and fresh source rebind. Reading or migration does not grant promotion authority."
generated_client_compatibility = "not_applicable"
migration_docs = ["src/polisyos/ddm/integration/model_registry_gate.md"]
runbook_docs = []
"""
    assert candidate != original
    assert (REPO / TARGET).read_bytes() == payloads[TARGET]
    patch = "".join(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            candidate.splitlines(keepends=True),
            fromfile="a/" + TARGET,
            tofile="b/" + TARGET,
        )
    )
    (ROOT / "ddm-source-binding.original.toml").write_text(original)
    (ROOT / "ddm-source-binding.proposed.toml").write_text(candidate)
    (ROOT / "ddm-release-companion.patch").write_text(patch)
    parsed = tomllib.loads(candidate)
    policy = tomllib.loads(
        payloads["policy-engine/architecture/gates/compatibility_release.toml"].decode()
    )
    parser_path = (
        "policy-engine/tools/ops_runners/release/check_compatibility_release_gates.py"
    )
    assert (REPO / parser_path).read_bytes() == payloads[parser_path]
    sys.path.insert(0, str(REPO / "policy-engine"))
    parser = runpy.run_path(str(REPO / parser_path))
    validate = parser["_validate_fragments"]
    parsed["__path__"] = TARGET.removeprefix("policy-engine/")
    errors, findings = validate(
        REPO / "policy-engine", policy, [parsed], breaking_classes=()
    )
    assert not errors, [e.as_dict() for e in errors]
    assert not findings, [f.as_dict() for f in findings]
    negatives = []
    for field in ["owner", "version_owner"]:
        bad = copy.deepcopy(parsed)
        del bad["compatibility_change"][0][field]
        errors, _ = validate(REPO / "policy-engine", policy, [bad], breaking_classes=())
        assert any("missing `" + field + "`" in e.message for e in errors)
        negatives.append(
            {
                "control": "missing_structured_" + field,
                "state": "REJECTED",
                "errors": [e.as_dict() for e in errors],
            }
        )
    schema = json.loads(
        payloads[
            "policy-engine/src/polisyos/ddm/integration/model_registry_record.schema.json"
        ]
    )
    legacy = json.loads(
        payloads[
            "policy-engine/src/polisyos/ddm/integration/model_registry_record.v1.schema.json"
        ]
    )
    facade = ast.parse(payloads["policy-engine/src/polisyos/ddm/__init__.py"])
    exports = next(
        ast.literal_eval(node.value)
        for node in facade.body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets)
    )
    inventory = json.loads(
        payloads["policy-engine/architecture/public_surface/inventory.json"]
    )
    package = next(p for p in inventory["packages"] if p["module"] == "polisyos.ddm")
    assert (
        package["classification"] == "internal" and package["owner"] == "team-scientist"
    )
    assert len(exports) == package["export_count"] == 17
    assert exports == package["exports"]
    subprocess.run(
        [
            "git",
            "-C",
            str(REPO),
            "apply",
            "--check",
            str(ROOT / "ddm-release-companion.patch"),
        ],
        check=True,
    )
    assert (REPO / TARGET).read_bytes() == payloads[TARGET]
    result = {
        "schema": "policyos.e02.ddm-release-companion-packet.v1",
        "prepared_by": "/root/ddm_r2 (DDM author; not an independent code review)",
        "base_sha": BASE,
        "base_tree": git("rev-parse", BASE + "^{tree}").decode().strip(),
        "canonical_decision_source": evidence_paths[1] + "@" + BASE,
        "canonical_release_note_owner": "team-scientist",
        "canonical_version_owner": "team-scientist",
        "target": TARGET,
        "footprint": [TARGET],
        "patch": {
            "path": str(ROOT / "ddm-release-companion.patch"),
            **record(patch.encode()),
        },
        "proposed_fragment": {
            "path": str(ROOT / "ddm-source-binding.proposed.toml"),
            **record(candidate.encode()),
        },
        "source_inputs": refs,
        "classification": {
            "wire_change_class": "persisted-artifact-format",
            "impact": "compatible_with_migration",
            "facade_classification": "internal",
            "facade_exports_unchanged": 17,
        },
        "version_profile_evidence": {
            "legacy_schema_id": legacy["$id"],
            "current_schema_id": schema["$id"],
            "distinct_schema_id": legacy["$id"] != schema["$id"],
            "current_required_version": schema["properties"]["schema_version"],
            "old_strict_reader_direction": "New v2 output incompatible with old strict reader; G53 and existing exact independent DDM receipt, not newly rerun here",
            "migration": "Upgrade served readers before v2 emission; preserve historical v1 bytes; explicit prerelease enriched migration and exact fresh source rebind; no wire downgrade or authority inferred",
            "deprecation": "No v1 removal date manufactured; original v1 reader/replay remains supported as historical non-gating projection",
        },
        "metadata_checks": {
            "tomllib_parse": "PASS",
            "actual_release_parser_structured_row": "PASS",
            "actual_parser_contract_errors": [],
            "negative_controls": negatives,
            "git_apply_check": "PASS",
            "repository_target_unchanged": True,
        },
        "acceptance_scope": "Applicable metadata patch packet only, not independent acceptance of authored DDM code or finding closure",
        "remaining_owner": "Root sole release-file writer applies/reconciles, independent backtest peer reviews metadata; team-scientist owns reader rollout and version profile",
        "finding_boundaries": "LA-054/055 feed/currentness/signoff/deployment authority not established; LA-056 individual team-scientist API owner decision remains separate",
        "new_numeric_checks": False,
        "repository_or_git_mutations": False,
        "cleanup_candidates": [],
    }
    (ROOT / "packet.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
