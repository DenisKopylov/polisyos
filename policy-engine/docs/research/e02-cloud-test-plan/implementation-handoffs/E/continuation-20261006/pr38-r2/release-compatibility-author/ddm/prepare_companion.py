#!/usr/bin/env python3
"""Prepare the G53 DDM release companion without editing the repository."""

import ast
import copy
import difflib
import hashlib
import json
import runpy
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path


def _resolve_executable(name: str) -> str:
    "Resolve an admitted executable and refuse an unavailable program before invocation."
    resolved = shutil.which(name)
    if resolved is None:
        raise RuntimeError(f"required utility executable unavailable: {name}")
    return str(Path(resolved).resolve())


def _write_stdout(*values: object, flush: bool = False) -> None:
    "Emit the existing CLI text and optionally flush without logging side effects."
    sys.stdout.write(" ".join(str(value) for value in values) + "\n")
    if flush:
        sys.stdout.flush()


REPO = Path("/workspace/e02-E-continuation-20261006")
ROOT = Path(__file__).parent
BASE = "a2677935015e8a0e7f2dfd5412b671e13fb3175a"
TARGET = "policy-engine/release-fragments/unreleased/2026-10-06-e02-ddm-source-binding.toml"


def _admit_git_object_arguments(arguments: tuple[str, ...]) -> None:
    """Keep object reads from interpreting record refs as Git options.

    Named/abbreviated refs remain available to retired source-pinned replay
    scripts; live packet admissions separately require full immutable SHAs.
    """
    if not arguments or arguments[0] not in {"show", "rev-parse"}:
        return
    safe_information_flags = {"--show-toplevel", "--git-dir", "--git-common-dir"}
    for value in arguments[1:]:
        if not isinstance(value, str) or not value or "\0" in value:
            raise ValueError("Git object argument must be a nonempty string")
        if value.startswith("-"):
            if arguments[0] == "rev-parse" and value in safe_information_flags:
                continue
            raise ValueError("Git object reference must never be an option")
        if ":" in value:
            _, relative = value.split(":", 1)
            path = Path(relative)
            if (
                not path.parts
                or path.is_absolute()
                or ".." in path.parts
                or path.as_posix() != relative
                or "\0" in relative
            ):
                raise ValueError("Git object path must be repository relative")


def git(*args: object) -> object:
    _admit_git_object_arguments(args)
    return subprocess.check_output([_resolve_executable("git"), "-C", str(REPO), *args])  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit


def record(data: object) -> dict[str, object]:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def main() -> None:
    evidence_paths = [
        TARGET,
        (
            "policy-engine/docs/research/e02-cloud-test-plan/integration/"
            "reviews/E-r2-owner-actions-2026-10-06.md"
        ),
        "policy-engine/architecture/gates/compatibility_release.toml",
        "policy-engine/ops/release/release-fragment-policy.toml",
        "policy-engine/release-fragments/template.toml",
        ("policy-engine/release-fragments/unreleased/2026-09-21-mig-02-manifest-path-rewrite.toml"),
        ("policy-engine/tools/ops_runners/release/check_compatibility_release_gates.py"),
        "policy-engine/src/polisyos/ddm/integration/model_registry_gate.md",
        ("policy-engine/src/polisyos/ddm/integration/model_registry_record.schema.json"),
        ("policy-engine/src/polisyos/ddm/integration/model_registry_record.v1.schema.json"),
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
        (
            'evidence = ["tests/unit/remediation/test_ddm_02.py", "tests/'
            'unit/ddm/test_full_acceptance.py"]'
        ),
        (
            'evidence = ["tests/unit/remediation/test_ddm_02.py", "tests/'
            'unit/ddm/test_full_acceptance.py", "tests/unit/ddm/test_regi'
            'stry_schema_compatibility.py", "src/polisyos/ddm/integration'
            '/model_registry_gate.md"]'
        ),
        1,
    )
    candidate = candidate.replace(
        'change_class = "internal"', 'change_class = "persisted-artifact-format"', 1
    )
    candidate += (
        'migration_docs = ["src/polisyos/ddm/integration/model_regist'
        'ry_gate.md"]\n\n[[compatibility_change]]\nid = "ddm-registry-re'
        'cord-v2-reader-migration"\nchange_class = "persisted-artifact'
        '-format"\nimpact = "compatible_with_migration"\nsurface = "int'
        "ernal: polisyos.ddm persisted ModelRegistryReadinessRecord v"
        '1/v2; existing 17-export facade unchanged"\nowner = "team-sci'
        'entist"\nversion_owner = "team-scientist"\ndeprecation_window '
        '= "Historical unversioned v1 records remain readable; upgrad'
        "e served readers before v2 emission. No v1 removal date is d"
        'eclared."\nrelease_note = "DDM preserves original strict v1 b'
        "ytes/schema identity and introduces distinct v2 registry rec"
        "ords. New v2 output requires an upgraded reader; prerelease "
        "enriched records require explicit migration and fresh source"
        " rebind. Reading or migration does not grant promotion autho"
        'rity."\ngenerated_client_compatibility = "not_applicable"\nmig'
        'ration_docs = ["src/polisyos/ddm/integration/model_registry_'
        'gate.md"]\nrunbook_docs = []\n'
    )
    if not (candidate != original):
        raise AssertionError
    if not ((REPO / TARGET).read_bytes() == payloads[TARGET]):
        raise AssertionError
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
    parser_path = "policy-engine/tools/ops_runners/release/check_compatibility_release_gates.py"
    if not ((REPO / parser_path).read_bytes() == payloads[parser_path]):
        raise AssertionError
    sys.path.insert(0, str(REPO / "policy-engine"))
    parser = runpy.run_path(str(REPO / parser_path))
    validate = parser["_validate_fragments"]
    parsed["__path__"] = TARGET.removeprefix("policy-engine/")
    errors, findings = validate(REPO / "policy-engine", policy, [parsed], breaking_classes=())
    if errors:
        raise AssertionError([e.as_dict() for e in errors])
    if findings:
        raise AssertionError([f.as_dict() for f in findings])
    negatives = []
    for field in ["owner", "version_owner"]:
        bad = copy.deepcopy(parsed)
        del bad["compatibility_change"][0][field]
        errors, _ = validate(REPO / "policy-engine", policy, [bad], breaking_classes=())
        if not (any("missing `" + field + "`" in e.message for e in errors)):
            raise AssertionError
        negatives.append(
            {
                "control": "missing_structured_" + field,
                "state": "REJECTED",
                "errors": [e.as_dict() for e in errors],
            }
        )
    schema = json.loads(
        payloads[("policy-engine/src/polisyos/ddm/integration/model_registry_record.schema.json")]
    )
    legacy = json.loads(
        payloads[
            ("policy-engine/src/polisyos/ddm/integration/model_registry_record.v1.schema.json")
        ]
    )
    facade = ast.parse(payloads["policy-engine/src/polisyos/ddm/__init__.py"])
    exports = next(
        ast.literal_eval(node.value)
        for node in facade.body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets)
    )
    inventory = json.loads(payloads["policy-engine/architecture/public_surface/inventory.json"])
    package = next(p for p in inventory["packages"] if p["module"] == "polisyos.ddm")
    if not (package["classification"] == "internal" and package["owner"] == "team-scientist"):
        raise AssertionError
    if not (len(exports) == package["export_count"] == 17):
        raise AssertionError
    if not (exports == package["exports"]):
        raise AssertionError
    subprocess.run(  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
        [
            _resolve_executable("git"),
            "-C",
            str(REPO),
            "apply",
            "--check",
            str(ROOT / "ddm-release-companion.patch"),
        ],
        check=True,
    )
    if not ((REPO / TARGET).read_bytes() == payloads[TARGET]):
        raise AssertionError
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
            "old_strict_reader_direction": (
                "New v2 output incompatible with old stri"
                "ct reader; G53 and existing exact indepe"
                "ndent DDM receipt, not newly rerun here"
            ),
            "migration": (
                "Upgrade served readers before v2 emissio"
                "n; preserve historical v1 bytes; explici"
                "t prerelease enriched migration and exac"
                "t fresh source rebind; no wire downgrade"
                " or authority inferred"
            ),
            "deprecation": (
                "No v1 removal date manufactured; original v1 reader/replay r"
                "emains supported as historical non-gating projection"
            ),
        },
        "metadata_checks": {
            "tomllib_parse": "PASS",
            "actual_release_parser_structured_row": "PASS",
            "actual_parser_contract_errors": [],
            "negative_controls": negatives,
            "git_apply_check": "PASS",
            "repository_target_unchanged": True,
        },
        "acceptance_scope": (
            "Applicable metadata patch packet only, not independent accep"
            "tance of authored DDM code or finding closure"
        ),
        "remaining_owner": (
            "Root sole release-file writer applies/reconciles, independen"
            "t backtest peer reviews metadata; team-scientist owns reader"
            " rollout and version profile"
        ),
        "finding_boundaries": (
            "LA-054/055 feed/currentness/signoff/deployment authority not"
            " established; LA-056 individual team-scientist API owner dec"
            "ision remains separate"
        ),
        "new_numeric_checks": False,
        "repository_or_git_mutations": False,
        "cleanup_candidates": [],
    }
    (ROOT / "packet.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    _write_stdout(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
