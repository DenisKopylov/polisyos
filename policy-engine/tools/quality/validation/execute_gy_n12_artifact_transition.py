#!/usr/bin/env python3
"""Measure and guard the bounded GY-N12 artifact transition.

The tool owns no deployment closure, policy admission, writer appointment, or
governed artifact.  It imports the confidence-ledger owner's closure, writes
candidate bytes only below an explicit scratch directory, and applies an
already-declared batch through a durable armed/final/fallback transaction.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import tomllib
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Final

MEASUREMENT_SCHEMA: Final = "polisyos.gy-n12.artifact-transition-measurement.v1"
CANDIDATE_SCHEMA: Final = "polisyos.gy-n12.artifact-transition-candidates.v1"
DECLARATION_SCHEMA: Final = "polisyos.gy-n12.artifact-transition-declaration.v1"
ARMED_SCHEMA: Final = "polisyos.gy-n12.artifact-transition-armed.v1"
FINAL_SCHEMA: Final = "polisyos.gy-n12.artifact-transition-final.v1"
FALLBACK_SCHEMA: Final = "polisyos.gy-n12.artifact-transition-fallback.v1"
READBACK_SCHEMA: Final = "polisyos.gy-n12.artifact-transition-readback.v1"

EPOCH_TARGET: Final = "architecture/policy_design_case/layer3_gy_epoch_chronology_contract.json"
REGISTRY_TARGET: Final = "architecture/generated_artifacts.toml"
REFERENCE_TARGET: Final = "docs/reference/generated-artifacts.md"

_INHERITED_PRICE_INPUTS: Final[dict[str, int | float]] = {
    "leaf_count": 5_387,
    "protected_preimage_count": 911,
    "protected_bytes": 47_532_401,
    "cold_cpu_core_seconds": 1_220.234,
}

# There is deliberately no production constructor for this permit.  The only
# production write edge therefore remains fail-closed until an institutional
# writer authority is appointed; unit tests use the identity solely to exercise
# rollback mechanics without laundering that appointment into repository code.
_UNIT_TEST_WRITER_AUTHORITY: Final = object()

# A content-bound DependencyProfileEnvironmentReceipt is candidate instance
# evidence, not an owner admission.  No production repository currently
# retains the independent marker bytes needed to promote it.  Changing this
# state requires the Foundry owner path, never a chronology-local convention.
_N8_ENVIRONMENT_RECEIPT_ADMISSION_STATE: Final = "not_established"

_DEPENDENCY_DISCRIMINANT_CONSUMER_IDENTITIES: Final = (
    "layer3_gy_value_gate_contract.validate_foundry_dependency_discriminant",
    "layer3_gy_second_domain_pack.read_foundry_dependency_discriminant",
    "layer3_gy_epoch_chronology_contract.read_foundry_dependency_discriminant",
)


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()


def _digest_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def with_receipt_hash(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return one canonical receipt whose hash excludes only itself."""

    result = {str(key): value for key, value in payload.items() if key != "receipt_sha256"}
    result["receipt_sha256"] = _digest_bytes(_canonical_bytes(result))
    return result


def verify_receipt(payload: Mapping[str, Any]) -> bool:
    """Recompute one receipt identity without trusting its declaration."""

    observed = payload.get("receipt_sha256")
    return isinstance(observed, str) and observed == with_receipt_hash(payload)["receipt_sha256"]


def _json_transport(value: object) -> object:
    """Convert a strict model value to its JSON transport shape."""

    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


def _dependency_result_field(result: object, field: str) -> object:
    if isinstance(result, Mapping):
        aliases = {
            "content_ref": "dependency_discriminant_content_ref",
            "discriminant_ref": "dependency_discriminant_ref",
            "status": "dependency_environment_status",
            "first_case": "dependency_environment_first_case",
        }
        return result.get(aliases[field], result.get(field))
    value = getattr(result, field, None)
    if value is None and field == "discriminant_ref":
        value = getattr(getattr(result, "profile_discriminant", None), field, None)
    return value


def dependency_discriminant_consumer_fields(result: object) -> dict[str, Any]:
    """Project one consumer's content binding and non-decisive ambient case."""

    return {
        "dependency_discriminant_content_ref": _dependency_result_field(
            result, "content_ref"
        ),
        "dependency_discriminant_ref": _json_transport(
            _dependency_result_field(result, "discriminant_ref")
        ),
        "dependency_environment_status": _dependency_result_field(result, "status"),
        "dependency_environment_first_case": _json_transport(
            _dependency_result_field(result, "first_case")
        ),
    }


def reconcile_dependency_discriminant_consumers(
    results: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Require the exact three consumers to bind the same non-null companion bytes."""

    if len(results) != len(_DEPENDENCY_DISCRIMINANT_CONSUMER_IDENTITIES):
        raise ValueError("readback_dependency_discriminant_binding_mismatch")
    by_identity = {str(result.get("consumer") or ""): result for result in results}
    if len(by_identity) != len(results) or set(by_identity) != set(
        _DEPENDENCY_DISCRIMINANT_CONSUMER_IDENTITIES
    ):
        raise ValueError("readback_dependency_discriminant_binding_mismatch")
    projected = tuple(
        {
            "consumer": identity,
            **dependency_discriminant_consumer_fields(by_identity[identity]),
        }
        for identity in _DEPENDENCY_DISCRIMINANT_CONSUMER_IDENTITIES
    )
    bindings = {
        _canonical_bytes(
            {
                "content_ref": row["dependency_discriminant_content_ref"],
                "discriminant_ref": row["dependency_discriminant_ref"],
            }
        )
        for row in projected
        if row["dependency_discriminant_content_ref"] is not None
        and row["dependency_discriminant_ref"] is not None
    }
    if len(bindings) != 1 or len(projected) != sum(
        row["dependency_discriminant_content_ref"] is not None
        and row["dependency_discriminant_ref"] is not None
        for row in projected
    ):
        raise ValueError("readback_dependency_discriminant_binding_mismatch")
    first = projected[0]
    return {
        "decision_role": "ambient_non_decisive",
        "content_ref": first["dependency_discriminant_content_ref"],
        "discriminant_ref": first["dependency_discriminant_ref"],
        "ambient_cases": [
            {
                "consumer": row["consumer"],
                "status": row["dependency_environment_status"],
                "first_case": row["dependency_environment_first_case"],
            }
            for row in projected
        ],
    }


def _read_receipt(path: Path, *, schema: str | None = None) -> dict[str, Any]:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"transition_receipt_unreadable:{path}") from exc
    if not isinstance(value, dict) or not verify_receipt(value):
        raise ValueError(f"transition_receipt_invalid:{path}")
    if schema is not None and value.get("schema_version") != schema:
        raise ValueError(f"transition_receipt_schema_mismatch:{path}")
    return value


def _write_exclusive(path: Path, payload: Mapping[str, Any]) -> None:
    """Publish one durable receipt atomically without replacing prior evidence."""

    path.parent.mkdir(parents=True, exist_ok=True)
    data = _canonical_bytes(payload) + b"\n"
    descriptor, temporary_raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_raw)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
        _fsync_directory(path.parent)
    finally:
        if temporary.exists():
            temporary.unlink()


def _fsync_directory(directory: Path) -> None:
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _git(repo_root: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and result.returncode != 0:
        raise ValueError("git_command_failed:" + " ".join(args) + ":" + result.stderr.strip())
    return result.stdout.strip()


def _git_blob(repo_root: Path, revision: str, relative: str) -> bytes:
    """Read exact committed bytes at one product-relative coordinate."""

    full_name = f"{_product_prefix(repo_root)}{relative}"
    result = subprocess.run(
        ["git", "show", f"{revision}:{full_name}"],
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(f"git_blob_unreadable:{relative}")
    return result.stdout


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _product_prefix(repo_root: Path) -> str:
    """Return Git's root-relative prefix for the product checkout."""

    return _git(repo_root, "rev-parse", "--show-prefix")


def _product_relative_git_path(repo_root: Path, raw: str) -> str:
    """Normalize one Git-reported path into the product-root coordinate."""

    return _strip_product_prefix(raw, prefix=_product_prefix(repo_root))


def _product_relative_git_paths(repo_root: Path, raw: str) -> set[str]:
    """Normalize one newline-delimited Git path set to product coordinates."""

    prefix = _product_prefix(repo_root)
    return {_strip_product_prefix(value, prefix=prefix) for value in raw.splitlines() if value}


def _strip_product_prefix(raw: str, *, prefix: str) -> str:
    """Strip one already-measured product prefix from a Git path."""

    if prefix:
        if not raw.startswith(prefix):
            raise ValueError(f"git_path_outside_product:{raw}")
        raw = raw[len(prefix) :]
    if not raw:
        raise ValueError("git_path_empty")
    return raw


def resolve_relative(root: Path, relative: Path) -> Path:
    """Resolve a repository-relative path without permitting an escape."""

    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise ValueError(f"unsafe_relative_path:{relative}")
    base = root.resolve()
    candidate = base.joinpath(relative)
    current = base
    for component in relative.parts:
        current = current / component
        if current.is_symlink() and not current.resolve().is_relative_to(base):
            raise ValueError(f"relative_path_symlink_escape:{relative}")
    resolved_parent = candidate.parent.resolve()
    if not resolved_parent.is_relative_to(base):
        raise ValueError(f"relative_path_symlink_escape:{relative}")
    return candidate


def path_state(root: Path, relative: Path) -> dict[str, Any]:
    """Snapshot one present or absent path by exact bytes."""

    path = resolve_relative(root, relative)
    if not path.exists():
        return {"path": relative.as_posix(), "kind": "absent"}
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"protected_path_not_regular:{relative}")
    payload = path.read_bytes()
    return {
        "path": relative.as_posix(),
        "kind": "present",
        "sha256": _digest_bytes(payload),
        "byte_size": len(payload),
    }


def denominator_hash(states: Sequence[Mapping[str, Any]]) -> str:
    """Bind one sorted, duplicate-free protected denominator."""

    normalized = sorted(
        ({str(key): value for key, value in row.items()} for row in states),
        key=lambda row: str(row.get("path")),
    )
    names = [str(row.get("path")) for row in normalized]
    if len(names) != len(set(names)):
        raise ValueError("protected_denominator_duplicate")
    return _digest_bytes(_canonical_bytes(normalized))


def _snapshot_matches(root: Path, expected: Mapping[str, Any]) -> bool:
    return path_state(root, Path(str(expected["path"]))) == dict(expected)


def _changed_paths(
    repo_root: Path, implementation_base: str, source_freeze: str
) -> list[dict[str, str]]:
    raw = _git(
        repo_root,
        "diff",
        "--name-status",
        "--find-renames=100%",
        implementation_base,
        source_freeze,
        "--",
        ".",
    )
    rows: list[dict[str, str]] = []
    for line in raw.splitlines():
        if not line:
            continue
        fields = line.split("\t")
        status = fields[0]
        if status.startswith(("R", "C")):
            if len(fields) != 3:
                raise ValueError("changed_path_record_invalid")
            rows.append(
                {
                    "path": _product_relative_git_path(repo_root, fields[1]),
                    "status": "D",
                }
            )
            rows.append(
                {
                    "path": _product_relative_git_path(repo_root, fields[2]),
                    "status": "A",
                }
            )
        elif len(fields) == 2:
            rows.append(
                {
                    "path": _product_relative_git_path(repo_root, fields[1]),
                    "status": status[0],
                }
            )
        else:
            raise ValueError("changed_path_record_invalid")
    return sorted(rows, key=lambda row: (row["path"], row["status"]))


def _tracked_policy_artifacts(repo_root: Path) -> tuple[Path, ...]:
    raw = _git(
        repo_root,
        "ls-files",
        "-z",
        "--full-name",
        "--",
        "architecture/policy_design_case",
        REGISTRY_TARGET,
        REFERENCE_TARGET,
    )
    prefix = _product_prefix(repo_root)
    return tuple(
        Path(_strip_product_prefix(value, prefix=prefix)) for value in raw.split("\0") if value
    )


def _declared_generated_outputs(repo_root: Path) -> tuple[Path, ...]:
    """Enumerate every generated output declared by the canonical registry."""

    registry = tomllib.loads((repo_root / REGISTRY_TARGET).read_text(encoding="utf-8"))
    families = registry.get("family", [])
    if not isinstance(families, list):
        raise ValueError("generated_artifact_family_denominator_invalid")
    tracked_raw = _git(repo_root, "ls-files", "-z", "--full-name")
    prefix = _product_prefix(repo_root)
    tracked = {
        _strip_product_prefix(value, prefix=prefix) for value in tracked_raw.split("\0") if value
    }
    outputs: set[Path] = set()
    for family in families:
        if not isinstance(family, dict) or not isinstance(family.get("outputs"), list):
            raise ValueError("generated_artifact_family_row_invalid")
        for raw in family["outputs"]:
            if not isinstance(raw, str):
                raise ValueError("generated_artifact_output_invalid")
            relative = Path(raw)
            if relative.is_absolute() or ".." in relative.parts:
                continue
            if relative.as_posix() in tracked:
                resolve_relative(repo_root, relative)
                outputs.add(relative)
    return tuple(sorted(outputs, key=Path.as_posix))


def _tool_sources() -> tuple[Path, ...]:
    return (
        Path("tools/quality/validation/execute_gy_n12_artifact_transition.py"),
        Path("tools/quality/validation/check_layer3_gy_epoch_chronology_contract.py"),
        Path("tools/quality/validation/check_layer3_gy_value_gate_contract.py"),
        Path("tools/quality/validation/check_layer3_gy_second_domain_pack.py"),
    )


def _potential_targets() -> tuple[Path, ...]:
    from tools.quality.validation import check_layer3_gy_second_domain_pack as n10a
    from tools.quality.validation import check_layer3_gy_value_gate_contract as n8

    return tuple(
        sorted(
            {
                Path(n8.OUTPUT_PATH),
                *(Path(value) for value in n10a.ARTIFACT_OUTPUTS),
                Path(EPOCH_TARGET),
                Path(REGISTRY_TARGET),
                Path(REFERENCE_TARGET),
            },
            key=Path.as_posix,
        )
    )


def _affected_families(changed: set[str], intersection: Sequence[str]) -> list[str]:
    families: set[str] = set()
    if "tools/quality/validation/check_layer3_gy_value_gate_contract.py" in changed:
        families.add("n8")
    if "tools/quality/validation/check_layer3_gy_second_domain_pack.py" in changed:
        families.add("n10a")
    if any(
        value in changed
        for value in (
            "tools/quality/validation/check_layer3_gy_epoch_chronology_contract.py",
            "src/polisyos/runtime/quality/semantic_epoch.py",
            "src/polisyos/runtime/quality/epoch_validity_cascade.py",
        )
    ):
        families.add("epoch")
    if intersection:
        families.add("deployment")
    return sorted(families)


def _measure_dependency_discriminant(repo_root: Path) -> dict[str, Any]:
    """Measure the shared companion without granting its diagnostic authority."""

    try:
        from tools.quality.validation import check_layer3_gy_second_domain_pack as n10a

        result = n10a.read_foundry_dependency_discriminant(repo_root=repo_root)
    except Exception:
        return {
            "decision_role": "ambient_non_decisive",
            "content_ref": None,
            "discriminant_ref": None,
            "status": "not_established",
            "first_case": None,
        }
    fields = dependency_discriminant_consumer_fields(result)
    return {
        "decision_role": "ambient_non_decisive",
        "content_ref": fields["dependency_discriminant_content_ref"],
        "discriminant_ref": fields["dependency_discriminant_ref"],
        "status": fields["dependency_environment_status"],
        "first_case": fields["dependency_environment_first_case"],
    }


def build_measurement(
    *,
    repo_root: Path,
    implementation_base: str,
    source_freeze: str,
    deployment_paths: Sequence[Path],
    tool_sources: Sequence[Path],
    potential_targets: Sequence[Path],
) -> dict[str, Any]:
    """Derive the complete changed set and its owner deployment intersection."""

    root = repo_root.resolve()
    head = _git(root, "rev-parse", "HEAD")
    if head != source_freeze:
        raise ValueError("source_freeze_not_head")
    branch = _git(root, "symbolic-ref", "--short", "HEAD")
    if not branch:
        raise ValueError("source_branch_detached")
    if _git(root, "status", "--porcelain", "--untracked-files=all"):
        raise ValueError("transition_worktree_not_clean")
    if _git(root, "merge-base", implementation_base, source_freeze) != implementation_base:
        raise ValueError("implementation_base_not_ancestor")
    changed_rows = _changed_paths(root, implementation_base, source_freeze)
    changed = {row["path"] for row in changed_rows}
    normalized_deployment = tuple(
        sorted({resolve_relative(root, value).relative_to(root) for value in deployment_paths})
    )
    deployment_states = [path_state(root, value) for value in normalized_deployment]
    intersection = sorted(changed & {value.as_posix() for value in normalized_deployment})
    normalized_targets = tuple(
        sorted({resolve_relative(root, value).relative_to(root) for value in potential_targets})
    )
    protected_paths = tuple(
        sorted(
            set(_tracked_policy_artifacts(root))
            | set(_declared_generated_outputs(root))
            | set(normalized_targets),
            key=Path.as_posix,
        )
    )
    protected_states = [path_state(root, value) for value in protected_paths]
    tool_states = [path_state(root, value) for value in tool_sources]
    target_states = [path_state(root, value) for value in normalized_targets]
    measured_bytes = sum(
        int(row.get("byte_size", 0)) for row in protected_states if row.get("kind") == "present"
    )
    payload = {
        "schema_version": MEASUREMENT_SCHEMA,
        "implementation_base": implementation_base,
        "source_freeze": source_freeze,
        "source_tree": _git(root, "rev-parse", f"{source_freeze}^{{tree}}"),
        "attached_branch": branch,
        "changed_paths": changed_rows,
        "deployment_paths": deployment_states,
        "deployment_closure_sha256": denominator_hash(deployment_states),
        "deployment_intersection": intersection,
        "affected_families": _affected_families(changed, intersection),
        "dependency_discriminant_measurement": _measure_dependency_discriminant(root),
        "owner_predicates": {
            "foundry_adjudication": "not_established",
            "owner_enforced_runtime_subtree_cutoff": "not_established",
            "writer_authority": "not_established",
        },
        "tool_sources": tool_states,
        "potential_targets": target_states,
        "protected_paths": protected_states,
        "protected_denominator_sha256": denominator_hash(protected_states),
        "price_inputs": {
            "inherited": dict(_INHERITED_PRICE_INPUTS),
            "measured": {
                "changed_path_count": len(changed_rows),
                "deployment_path_count": len(normalized_deployment),
                "deployment_intersection_count": len(intersection),
                "protected_preimage_count": len(protected_states),
                "protected_bytes": measured_bytes,
            },
        },
    }
    return with_receipt_hash(payload)


def require_candidate_family_exactness(
    *,
    affected_families: Sequence[str],
    deployment_intersection: Sequence[str],
    rows: Sequence[Mapping[str, Any]],
) -> None:
    """Reject candidate batches whose family denominator was narrowed or widened."""

    observed = {str(row.get("family")) for row in rows}
    expected = set(affected_families)
    if not deployment_intersection and "deployment" in observed:
        raise ValueError("zero_intersection_requires_zero_deployment_reissue")
    if observed != expected:
        raise ValueError("candidate_family_denominator_mismatch")
    exact_targets = {
        "n8": set(),
        "n10a": set(),
        "epoch": {EPOCH_TARGET, REGISTRY_TARGET, REFERENCE_TARGET},
    }
    if "n8" in expected or "n10a" in expected:
        from tools.quality.validation import check_layer3_gy_second_domain_pack as n10a
        from tools.quality.validation import check_layer3_gy_value_gate_contract as n8

        exact_targets["n8"] = {n8.OUTPUT_PATH}
        exact_targets["n10a"] = set(n10a.ARTIFACT_OUTPUTS)
    for family in sorted(expected & exact_targets.keys()):
        observed_targets = {
            str(row.get("target_path")) for row in rows if str(row.get("family")) == family
        }
        if observed_targets != exact_targets[family]:
            raise ValueError(f"candidate_target_denominator_mismatch:{family}")


def _candidate_row(
    *, family: str, target: Path, candidate: Path, candidate_root: Path, repo_root: Path
) -> dict[str, Any]:
    if not candidate.is_file() or candidate.is_symlink():
        raise ValueError(f"candidate_output_missing:{candidate}")
    relative_candidate = candidate.resolve().relative_to(candidate_root.resolve())
    return {
        "family": family,
        "target_path": target.as_posix(),
        "candidate_relative_path": relative_candidate.as_posix(),
        "candidate_sha256": _digest_bytes(candidate.read_bytes()),
        "candidate_bytes": candidate.stat().st_size,
        "preimage": path_state(repo_root, target),
    }


def _validate_candidate_root(repo_root: Path, candidate_dir: Path) -> Path:
    expanded = candidate_dir.expanduser()
    if expanded.is_symlink():
        raise ValueError("candidate_directory_symlink")
    resolved = _require_external_path(
        repo_root,
        expanded,
        code="candidate_directory_inside_repository",
    )
    if expanded.exists():
        if not expanded.is_dir() or any(expanded.iterdir()):
            raise ValueError("candidate_directory_not_empty")
    else:
        expanded.mkdir(parents=True)
    return resolved


def _invoke_json(
    argv: Sequence[str],
    *,
    expected_validator: str,
    expected_mode: str,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    result = subprocess.run(
        list(argv),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=dict(env) if env is not None else None,
        check=False,
    )
    raw = result.stdout.strip()
    if not raw:
        raise ValueError("candidate_command_nonreceipt:" + " ".join(argv))
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("candidate_command_payload_invalid:" + " ".join(argv)) from exc
    if (
        result.returncode != 0
        or not isinstance(payload, dict)
        or not verify_receipt(payload)
        or payload.get("validator") != expected_validator
        or payload.get("mode") != expected_mode
        or payload.get("status") != "pass"
        or not isinstance(payload.get("issues"), list)
        or payload.get("issues")
    ):
        raise ValueError("candidate_command_failed:" + " ".join(argv))
    return payload


def _run_n8_origin_probe(
    *,
    interpreter: Path,
    environment_root: Path,
    environment_site: Path,
    tooling_site: Path,
) -> dict[str, Any]:
    """Interrogate the N8 interpreter under the plan's sanitized child environment."""

    script = r"""
import importlib.metadata as metadata
import json
from pathlib import Path
import sys

environment_root = Path(sys.argv[1]).resolve()
environment_site = Path(sys.argv[2]).resolve()
tooling_site = Path(sys.argv[3]).resolve()
resolved_sys_path = sorted(
    {
        str(Path(value or ".").resolve())
        for value in sys.path
    }
)
origins = []
escaped = []
for distribution in metadata.distributions(path=[str(environment_site)]):
    origin = Path(distribution.locate_file("")).resolve()
    row = {
        "name": distribution.metadata.get("Name") or "",
        "version": distribution.version or "",
        "origin": str(origin),
    }
    origins.append(row)
    if not origin.is_relative_to(environment_root):
        escaped.append(str(origin))
print(json.dumps({
    "interpreter_entry": sys.executable,
    "interpreter_realpath": str(Path(sys.executable).resolve()),
    "environment_site": str(environment_site),
    "tooling_site_present": str(tooling_site) in resolved_sys_path,
    "resolved_sys_path": resolved_sys_path,
    "distribution_count": len(origins),
    "distribution_origins": sorted(origins, key=lambda row: (row["name"], row["version"], row["origin"])),
    "escaped_distribution_origins": sorted(set(escaped)),
}, sort_keys=True, separators=(",", ":")))
"""
    completed = subprocess.run(
        (
            str(interpreter),
            "-S",
            "-c",
            script,
            str(environment_root),
            str(environment_site),
            str(tooling_site),
        ),
        cwd=environment_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "JAX_PLATFORMS": "cpu",
            "PYTHONHASHSEED": "0",
            "PYTHONNOUSERSITE": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PATH": f"{interpreter.parent}:/usr/bin:/bin",
            "PYTHONPATH": str(environment_site),
        },
        check=False,
    )
    lines = completed.stdout.splitlines()
    if completed.returncode != 0 or len(lines) != 1:
        raise ValueError("n8_environment_origin_probe_nonreceipt")
    try:
        payload = json.loads(lines[0])
    except json.JSONDecodeError as exc:
        raise ValueError("n8_environment_origin_probe_nonreceipt") from exc
    if not isinstance(payload, dict):
        raise ValueError("n8_environment_origin_probe_nonreceipt")
    return payload


def validate_n8_environment(
    *,
    n8_python: Path,
    environment_receipt: object,
    tooling_site: Path,
    origin_probe: Callable[..., Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Validate candidate environment evidence without promoting its authority."""

    from polisyos.foundry.methods.catalog.dependency_evidence import (
        DependencyEnvironmentMarkerStatement,
        DigestDomain,
        record_ref,
    )
    from polisyos.foundry.methods.catalog.dependency_profile import (
        DependencyProfileEnvironmentReceipt,
    )

    if not isinstance(environment_receipt, DependencyProfileEnvironmentReceipt):
        raise ValueError("n8_environment_receipt_not_established")
    try:
        reopened_receipt = DependencyProfileEnvironmentReceipt.model_validate_json(
            environment_receipt.model_dump_json()
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("n8_environment_receipt_not_established") from exc
    interpreter_entry = n8_python.expanduser().absolute()
    environment_root = interpreter_entry.parent.parent.resolve()
    if not interpreter_entry.is_file() or interpreter_entry.parent.name != "bin":
        raise ValueError("n8_interpreter_outside_appointed_environment")
    marker_path = environment_root / ".polisyos-foundry-authority-v1" / "environment-marker.json"
    try:
        marker_raw = marker_path.read_bytes()
        marker = DependencyEnvironmentMarkerStatement.model_validate_json(marker_raw)
    except (OSError, ValueError) as exc:
        raise ValueError("n8_environment_marker_not_established") from exc
    observed_marker_ref = record_ref(
        DigestDomain.ENVIRONMENT_MARKER,
        marker_raw,
        schema_version=marker.schema_version,
    )
    statement = reopened_receipt.statement
    if observed_marker_ref != statement.marker_ref:
        raise ValueError("n8_environment_marker_mismatch")
    if (
        marker.stable_closure != statement.stable_closure
        or marker.python_runtime_installation_ref != statement.python_runtime_installation_ref
        or marker.python_runtime_verification_ref != statement.python_runtime_verification_ref
        or marker.instance_content_set != statement.instance_content_set
    ):
        raise ValueError("n8_environment_marker_statement_mismatch")
    sites = tuple(environment_root.glob("lib/python*/site-packages"))
    if len(sites) != 1 or not sites[0].is_dir():
        raise ValueError("n8_environment_site_packages_missing")
    environment_site = sites[0].resolve()
    resolved_tooling_site = tooling_site.resolve()
    if not resolved_tooling_site.is_dir():
        raise ValueError("tooling_site_packages_missing")
    probe = (origin_probe or _run_n8_origin_probe)(
        interpreter=interpreter_entry,
        environment_root=environment_root,
        environment_site=environment_site,
        tooling_site=resolved_tooling_site,
    )
    if probe.get("environment_site") != str(environment_site):
        raise ValueError("n8_environment_site_probe_mismatch")
    if probe.get("tooling_site_present") is not False:
        raise ValueError("n8_tooling_site_leaked")
    origins = probe.get("distribution_origins")
    escaped = probe.get("escaped_distribution_origins")
    count = probe.get("distribution_count")
    if (
        not isinstance(origins, list)
        or not isinstance(escaped, list)
        or not isinstance(count, int)
        or count != len(origins)
    ):
        raise ValueError("n8_distribution_origin_probe_invalid")
    independently_escaped: list[str] = []
    for row in origins:
        if not isinstance(row, Mapping) or not isinstance(row.get("origin"), str):
            raise ValueError("n8_distribution_origin_probe_invalid")
        origin = Path(str(row["origin"])).resolve()
        if not origin.is_relative_to(environment_root):
            independently_escaped.append(str(origin))
    if escaped or independently_escaped:
        raise ValueError("n8_distribution_origin_escape")
    interpreter_realpath = interpreter_entry.resolve()
    if probe.get("interpreter_realpath") not in {None, str(interpreter_realpath)}:
        raise ValueError("n8_interpreter_probe_mismatch")
    return {
        "entry_path": str(interpreter_entry),
        "realpath": str(interpreter_realpath),
        "sha256": _digest_bytes(interpreter_realpath.read_bytes()),
        "environment_root": str(environment_root),
        "environment_site": str(environment_site),
        "tooling_site_present": False,
        "distribution_count": count,
        "distribution_origins": origins,
        "escaped_distribution_origins": [],
        "environment_receipt_ref": reopened_receipt.receipt_ref.model_dump(mode="json"),
        "environment_marker_ref": statement.marker_ref.model_dump(mode="json"),
    }


def build_candidates(
    *,
    repo_root: Path,
    measurement: Mapping[str, Any],
    candidate_dir: Path,
    n8_python: Path,
    n8_environment_receipt_path: Path,
) -> dict[str, Any]:
    """Build affected family candidates without writing a governed target."""

    if not verify_receipt(measurement) or measurement.get("schema_version") != MEASUREMENT_SCHEMA:
        raise ValueError("measurement_invalid")
    root = repo_root.resolve()
    if _git(root, "rev-parse", "HEAD") != measurement.get("source_freeze"):
        raise ValueError("source_freeze_drift")
    if _git(root, "rev-parse", "HEAD^{tree}") != measurement.get("source_tree"):
        raise ValueError("source_tree_drift")
    if _git(root, "status", "--porcelain", "--untracked-files=all"):
        raise ValueError("transition_worktree_not_clean")
    from polisyos.foundry.methods.catalog.dependency_profile import (
        DependencyProfileEnvironmentReceipt,
    )

    try:
        environment_receipt_raw = n8_environment_receipt_path.read_bytes()
        environment_receipt = DependencyProfileEnvironmentReceipt.model_validate_json(
            environment_receipt_raw
        )
    except (OSError, ValueError) as exc:
        raise ValueError("n8_environment_receipt_not_established") from exc
    if _N8_ENVIRONMENT_RECEIPT_ADMISSION_STATE != "established":
        raise ValueError("dependency_environment_receipt_not_established")
    candidate_root = _validate_candidate_root(root, candidate_dir)
    tooling_sites = tuple((root / ".venv").glob("lib/python*/site-packages"))
    if len(tooling_sites) != 1:
        raise ValueError("tooling_site_packages_missing")
    interpreter = validate_n8_environment(
        n8_python=n8_python,
        environment_receipt=environment_receipt,
        tooling_site=tooling_sites[0],
    )
    families = tuple(str(value) for value in measurement.get("affected_families", ()))
    if "epoch" in families:
        # The epoch payload candidate exists, but the generated-artifact owner
        # has no scratch builder for the registry/reference pair.  A partial
        # three-file family is not a candidate receipt.
        raise ValueError("epoch_generated_family_builder_not_established")
    rows: list[dict[str, Any]] = []
    process_receipts: list[dict[str, Any]] = []
    site = Path(str(interpreter["environment_site"]))
    child_env = {
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "JAX_PLATFORMS": "cpu",
        "PYTHONHASHSEED": "0",
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PATH": f"{n8_python.parent}:/usr/bin:/bin",
        "PYTHONPATH": f"{root / 'src'}:{root}:{site}",
    }
    if "n8" in families:
        from tools.quality.validation import check_layer3_gy_value_gate_contract as n8

        target = Path(n8.OUTPUT_PATH)
        candidate = candidate_root / target
        candidate.parent.mkdir(parents=True, exist_ok=True)
        report = _invoke_json(
            (
                str(n8_python),
                "-S",
                str(root / "tools/quality/validation/check_layer3_gy_value_gate_contract.py"),
                "--candidate-reissue-catalog-provenance",
                str(candidate),
                "--expected-source-freeze",
                str(measurement["source_freeze"]),
                "--output-format",
                "json",
            ),
            expected_validator=n8.VALIDATOR_ID,
            expected_mode="candidate-reissue-catalog-provenance",
            env=child_env,
        )
        process_receipts.append(report)
        rows.append(
            _candidate_row(
                family="n8",
                target=target,
                candidate=candidate,
                candidate_root=candidate_root,
                repo_root=root,
            )
        )
    if "n10a" in families:
        from tools.quality.validation import check_layer3_gy_second_domain_pack as n10a

        n10_root = candidate_root / "n10a"
        report = _invoke_json(
            (
                str(n8_python),
                "-S",
                str(root / "tools/quality/validation/check_layer3_gy_second_domain_pack.py"),
                "--repo-root",
                str(root),
                "--candidate-dir",
                str(n10_root),
                "--expected-source-freeze",
                str(measurement["source_freeze"]),
                "--output-format",
                "json",
            ),
            expected_validator=n10a.VALIDATOR_ID,
            expected_mode="candidate-dir",
            env=child_env,
        )
        process_receipts.append(report)
        if tuple(report.get("outputs", ())) != tuple(n10a.ARTIFACT_OUTPUTS):
            raise ValueError("n10a_candidate_output_denominator_mismatch")
        for target_raw in n10a.ARTIFACT_OUTPUTS:
            target = Path(target_raw)
            candidate = n10_root / target
            rows.append(
                _candidate_row(
                    family="n10a",
                    target=target,
                    candidate=candidate,
                    candidate_root=candidate_root,
                    repo_root=root,
                )
            )
    if "epoch" in families:
        from tools.quality.validation import check_layer3_gy_epoch_chronology_contract as epoch

        target = Path(EPOCH_TARGET)
        candidate = candidate_root / target
        candidate.parent.mkdir(parents=True, exist_ok=True)
        report = _invoke_json(
            (
                sys.executable,
                str(root / "tools/quality/validation/check_layer3_gy_epoch_chronology_contract.py"),
                "--rederive-audit",
                "--candidate-output",
                str(candidate),
                "--expected-source-freeze",
                str(measurement["source_freeze"]),
                "--output-format",
                "json",
            ),
            expected_validator=epoch.VALIDATOR_ID,
            expected_mode="rederive-audit",
        )
        process_receipts.append(report)
        rows.append(
            _candidate_row(
                family="epoch",
                target=target,
                candidate=candidate,
                candidate_root=candidate_root,
                repo_root=root,
            )
        )
    if "deployment" in families:
        raise ValueError("deployment_writer_authority_not_established")
    observed_families = tuple(sorted({str(row["family"]) for row in rows}))
    require_candidate_family_exactness(
        affected_families=families,
        deployment_intersection=tuple(measurement.get("deployment_intersection", ())),
        rows=rows,
    )
    payload = {
        "schema_version": CANDIDATE_SCHEMA,
        "measurement_sha256": measurement["receipt_sha256"],
        "n8_interpreter": interpreter,
        "n8_environment_receipt_sha256": _digest_bytes(environment_receipt_raw),
        "families": list(observed_families),
        "rows": rows,
        "process_receipts": process_receipts,
    }
    return with_receipt_hash(payload)


def build_declaration(
    *,
    measurement: Mapping[str, Any],
    candidate_receipt: Mapping[str, Any],
    expected_branch: str,
    expected_source_freeze: str,
    allowed_post_freeze_records: Sequence[Path],
) -> dict[str, Any]:
    """Bind a reviewed candidate set, refusing every unestablished owner gate."""

    if not verify_receipt(measurement) or measurement.get("schema_version") != MEASUREMENT_SCHEMA:
        raise ValueError("measurement_invalid")
    if (
        not verify_receipt(candidate_receipt)
        or candidate_receipt.get("schema_version") != CANDIDATE_SCHEMA
    ):
        raise ValueError("candidate_receipt_invalid")
    if candidate_receipt.get("measurement_sha256") != measurement.get("receipt_sha256"):
        raise ValueError("candidate_measurement_mismatch")
    if measurement.get("attached_branch") != expected_branch:
        raise ValueError("declaration_branch_mismatch")
    if measurement.get("source_freeze") != expected_source_freeze:
        raise ValueError("declaration_source_freeze_mismatch")
    predicates = measurement.get("owner_predicates")
    if not isinstance(predicates, dict):
        raise ValueError("owner_predicates_missing")
    for key in (
        "foundry_adjudication",
        "owner_enforced_runtime_subtree_cutoff",
        "writer_authority",
    ):
        if predicates.get(key) != "established":
            raise ValueError(f"{key}_not_established")
    records = tuple(Path(value) for value in allowed_post_freeze_records)
    if len(records) != 1:
        raise ValueError("declaration_record_denominator_invalid")
    normalized_records = [value.as_posix() for value in records]
    rows = candidate_receipt.get("rows")
    if not isinstance(rows, list):
        raise ValueError("candidate_rows_invalid")
    targets: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("candidate_row_invalid")
        targets.append(
            {
                "path": row["target_path"],
                "candidate_relative_path": row["candidate_relative_path"],
                "candidate_sha256": row["candidate_sha256"],
                "preimage": row["preimage"],
            }
        )
    names = [str(row["path"]) for row in targets]
    if len(names) != len(set(names)):
        raise ValueError("declaration_target_duplicate")
    target_names = set(names)
    protected = [
        row
        for row in measurement.get("protected_paths", ())
        if isinstance(row, dict) and row.get("path") not in target_names
    ]
    payload = {
        "schema_version": DECLARATION_SCHEMA,
        "measurement_sha256": measurement["receipt_sha256"],
        "candidate_receipt_sha256": candidate_receipt["receipt_sha256"],
        "expected_branch": expected_branch,
        "source_freeze": expected_source_freeze,
        "source_tree": measurement["source_tree"],
        "allowed_post_freeze_records": normalized_records,
        "targets": targets,
        "protected_paths": protected,
        "protected_denominator_sha256": measurement["protected_denominator_sha256"],
        "tool_sources": measurement.get("tool_sources", []),
        "owner_predicates": predicates,
    }
    return with_receipt_hash(payload)


def _snapshot_bytes(
    *, repo_root: Path, state_dir: Path, states: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    preimage_root = state_dir / "preimages"
    preimage_root.mkdir(parents=True, exist_ok=False)
    manifest: list[dict[str, Any]] = []
    for ordinal, state in enumerate(states):
        relative = Path(str(state["path"]))
        if not _snapshot_matches(repo_root, state):
            raise ValueError(f"protected_preimage_drift:{relative}")
        item = dict(state)
        if state.get("kind") == "present":
            source = resolve_relative(repo_root, relative)
            backup = preimage_root / f"{ordinal:06d}.blob"
            backup.write_bytes(source.read_bytes())
            with backup.open("rb") as handle:
                os.fsync(handle.fileno())
            item["backup"] = backup.relative_to(state_dir).as_posix()
        manifest.append(item)
    _fsync_directory(preimage_root)
    return manifest


def _atomic_replace(target: Path, payload: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_raw = tempfile.mkstemp(prefix=".gy-n12.", dir=target.parent)
    temporary = Path(temporary_raw)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        _fsync_directory(target.parent)
    finally:
        if temporary.exists():
            temporary.unlink()


def _restore_snapshot(
    repo_root: Path, state_dir: Path, manifest: Sequence[Mapping[str, Any]]
) -> None:
    for row in manifest:
        if row.get("kind") != "present":
            continue
        backup = resolve_relative(state_dir, Path(str(row["backup"])))
        if not backup.is_file() or backup.is_symlink():
            raise RuntimeError(f"fallback_backup_missing:{row['path']}")
        if _digest_bytes(backup.read_bytes()) != row.get("sha256"):
            raise RuntimeError(f"fallback_backup_mismatch:{row['path']}")
    for row in manifest:
        target = resolve_relative(repo_root, Path(str(row["path"])))
        if row.get("kind") == "absent":
            if target.exists():
                target.unlink()
                _fsync_directory(target.parent)
            continue
        backup = resolve_relative(state_dir, Path(str(row["backup"])))
        _atomic_replace(target, backup.read_bytes())
    for row in manifest:
        expected = {key: value for key, value in row.items() if key != "backup"}
        if not _snapshot_matches(repo_root, expected):
            raise RuntimeError(f"fallback_restore_mismatch:{row['path']}")


def _load_state_manifest(
    state_dir: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    armed = _read_receipt(state_dir / "armed.json", schema=ARMED_SCHEMA)
    manifest = armed.get("target_preimages")
    protected = armed.get("protected_paths")
    if not isinstance(manifest, list) or not all(isinstance(row, dict) for row in manifest):
        raise ValueError("armed_preimage_manifest_invalid")
    if not isinstance(protected, list) or not all(isinstance(row, dict) for row in protected):
        raise ValueError("armed_protected_manifest_invalid")
    return armed, manifest, protected


def _require_external_path(repo_root: Path, candidate: Path, *, code: str) -> Path:
    expanded = candidate.expanduser()
    resolved = expanded.resolve()
    git_root = Path(_git(repo_root, "rev-parse", "--show-toplevel")).resolve()
    if resolved.is_relative_to(git_root):
        raise ValueError(code)
    return resolved


def recover_armed_transition(*, repo_root: Path, state_dir: Path) -> dict[str, Any] | None:
    """Recover an armed transition before inspecting any new declaration."""

    armed_path = state_dir / "armed.json"
    if not armed_path.exists():
        return None
    armed, manifest, protected = _load_state_manifest(state_dir)
    for name, schema in (("final.json", FINAL_SCHEMA), ("fallback.json", FALLBACK_SCHEMA)):
        terminal_path = state_dir / name
        if not terminal_path.exists():
            continue
        terminal = _read_receipt(terminal_path, schema=schema)
        if terminal.get("armed_sha256") != armed.get("receipt_sha256"):
            raise ValueError("transition_terminal_armed_binding_mismatch")
        return None
    expected_branch = armed.get("expected_branch")
    expected_head = armed.get("expected_declaration_head")
    if not isinstance(expected_branch, str) or not isinstance(expected_head, str):
        raise ValueError("armed_execution_context_invalid")
    if _git(repo_root, "symbolic-ref", "--short", "HEAD") != expected_branch:
        raise ValueError("armed_recovery_branch_mismatch")
    if _git(repo_root, "rev-parse", "HEAD") != expected_head:
        raise ValueError("armed_recovery_head_mismatch")
    _restore_snapshot(repo_root, state_dir, manifest)
    for row in protected:
        if not _snapshot_matches(repo_root, row):
            raise RuntimeError(f"protected_path_changed_during_recovery:{row['path']}")
    fallback = with_receipt_hash(
        {
            "schema_version": FALLBACK_SCHEMA,
            "status": "fallback",
            "armed_sha256": armed["receipt_sha256"],
            "error": "recovered_armed_transition",
            "restored_target_denominator_sha256": denominator_hash(
                [{key: value for key, value in row.items() if key != "backup"} for row in manifest]
            ),
        }
    )
    _write_exclusive(state_dir / "fallback.json", fallback)
    return fallback


def apply_declaration(
    *,
    repo_root: Path,
    declaration: Mapping[str, Any],
    candidate_dir: Path,
    state_dir: Path,
    writer_authority: object | None = None,
    runtime_guard: Callable[[], None] | None = None,
    expected_branch: str | None = None,
    expected_declaration_head: str | None = None,
    fault_after_replacements: int | None = None,
) -> dict[str, Any]:
    """Apply one batch or restore every protected preimage before fallback."""

    candidate_dir = _require_external_path(
        repo_root, candidate_dir, code="candidate_directory_inside_repository"
    )
    state_dir = _require_external_path(
        repo_root, state_dir, code="state_directory_inside_repository"
    )
    if recover_armed_transition(repo_root=repo_root, state_dir=state_dir) is not None:
        raise RuntimeError("recovered_armed_transition")
    if (state_dir / "final.json").exists() or (state_dir / "fallback.json").exists():
        raise FileExistsError("transition_terminal_receipt_exists")
    if not expected_branch or not expected_declaration_head:
        raise ValueError("apply_execution_context_not_established")
    if not verify_receipt(declaration) or declaration.get("schema_version") != DECLARATION_SCHEMA:
        raise ValueError("declaration_invalid")
    predicates = declaration.get("owner_predicates")
    if not isinstance(predicates, dict) or any(
        predicates.get(key) != "established"
        for key in (
            "foundry_adjudication",
            "owner_enforced_runtime_subtree_cutoff",
            "writer_authority",
        )
    ):
        raise ValueError("artifact_writer_authority_not_established")
    if writer_authority is not _UNIT_TEST_WRITER_AUTHORITY:
        raise ValueError("artifact_writer_authority_not_established")

    rows = declaration.get("targets")
    protected = declaration.get("protected_paths", [])
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError("declaration_targets_invalid")
    if not isinstance(protected, list) or not all(isinstance(row, dict) for row in protected):
        raise ValueError("declaration_protected_paths_invalid")
    target_states = [dict(row["preimage"]) for row in rows]
    all_states = [*target_states, *(dict(row) for row in protected)]
    expected_denominator = declaration.get("protected_denominator_sha256")
    if denominator_hash(all_states) != expected_denominator:
        raise ValueError("declaration_protected_denominator_mismatch")
    candidates: list[tuple[Path, bytes, str]] = []
    candidate_root = candidate_dir.resolve()
    for row in rows:
        candidate = resolve_relative(candidate_root, Path(str(row["candidate_relative_path"])))
        if not candidate.is_file() or candidate.is_symlink():
            raise ValueError(f"candidate_missing:{candidate}")
        payload = candidate.read_bytes()
        if _digest_bytes(payload) != row.get("candidate_sha256"):
            raise ValueError(f"candidate_drift:{candidate}")
        target = resolve_relative(repo_root, Path(str(row["path"])))
        candidates.append((target, payload, str(row["candidate_sha256"])))
    state_dir.mkdir(parents=True, exist_ok=False)
    manifest = _snapshot_bytes(repo_root=repo_root, state_dir=state_dir, states=target_states)
    if runtime_guard is not None:
        runtime_guard()
    for row in protected:
        if not _snapshot_matches(repo_root, row):
            raise ValueError(f"protected_preimage_drift:{row['path']}")
    armed = with_receipt_hash(
        {
            "schema_version": ARMED_SCHEMA,
            "status": "armed",
            "declaration_sha256": declaration["receipt_sha256"],
            "expected_branch": expected_branch,
            "expected_declaration_head": expected_declaration_head,
            "target_preimages": manifest,
            "protected_paths": protected,
            "target_count": len(candidates),
        }
    )
    _write_exclusive(state_dir / "armed.json", armed)
    replaced = 0
    try:
        for target, payload, _expected_hash in candidates:
            if runtime_guard is not None:
                runtime_guard()
            for row in protected:
                if not _snapshot_matches(repo_root, row):
                    raise RuntimeError(f"protected_path_changed:{row['path']}")
            _atomic_replace(target, payload)
            replaced += 1
            if fault_after_replacements is not None and replaced >= fault_after_replacements:
                raise RuntimeError("injected_failure_after_replacement")
        for target, payload, expected_hash in candidates:
            if (
                _digest_bytes(target.read_bytes()) != expected_hash
                or target.read_bytes() != payload
            ):
                raise RuntimeError(f"candidate_readback_mismatch:{target}")
        for row in protected:
            if not _snapshot_matches(repo_root, row):
                raise RuntimeError(f"protected_path_changed:{row['path']}")
        if runtime_guard is not None:
            runtime_guard()
    except BaseException as exc:
        _restore_snapshot(repo_root, state_dir, manifest)
        fallback = with_receipt_hash(
            {
                "schema_version": FALLBACK_SCHEMA,
                "status": "fallback",
                "armed_sha256": armed["receipt_sha256"],
                "error": str(exc),
                "restored_target_denominator_sha256": denominator_hash(target_states),
            }
        )
        _write_exclusive(state_dir / "fallback.json", fallback)
        raise
    final = with_receipt_hash(
        {
            "schema_version": FINAL_SCHEMA,
            "status": "final",
            "armed_sha256": armed["receipt_sha256"],
            "declaration_sha256": declaration["receipt_sha256"],
            "declaration_head": expected_declaration_head,
            "target_sha256": {str(row["path"]): str(row["candidate_sha256"]) for row in rows},
            "protected_denominator_sha256": expected_denominator,
        }
    )
    _write_exclusive(state_dir / "final.json", final)
    return final


def _run_dependency_discriminant_consumers(
    *,
    repo_root: Path,
    expected_head: str,
) -> tuple[dict[str, Any], ...]:
    """Independently bind N8, N10a, and chronology to one committed companion."""

    from tools.quality.validation import check_layer3_gy_epoch_chronology_contract as epoch
    from tools.quality.validation import check_layer3_gy_second_domain_pack as n10a
    from tools.quality.validation import check_layer3_gy_value_gate_contract as n8

    try:
        companion_raw = _git_blob(
            repo_root,
            expected_head,
            n8.DEPENDENCY_DISCRIMINANT_OUTPUT_PATH,
        )
    except ValueError as exc:
        raise ValueError("readback_dependency_discriminant_binding_mismatch") from exc
    consumer_results = (
        (
            _DEPENDENCY_DISCRIMINANT_CONSUMER_IDENTITIES[0],
            n8.validate_foundry_dependency_discriminant(
                repo_root=repo_root,
                companion=companion_raw,
                diagnostic_verification=None,
            ),
        ),
        (
            _DEPENDENCY_DISCRIMINANT_CONSUMER_IDENTITIES[1],
            n10a.read_foundry_dependency_discriminant(
                repo_root=repo_root,
                companion=companion_raw,
                diagnostic_verification=None,
            ),
        ),
        (
            _DEPENDENCY_DISCRIMINANT_CONSUMER_IDENTITIES[2],
            epoch.read_foundry_dependency_discriminant(
                repo_root=repo_root,
                companion=companion_raw,
                diagnostic_verification=None,
            ),
        ),
    )
    return tuple(
        {
            "consumer": identity,
            **dependency_discriminant_consumer_fields(result),
        }
        for identity, result in consumer_results
    )


def _run_readback_consumers(
    *,
    repo_root: Path,
    expected_head: str,
    source_freeze: str,
    target_paths: Sequence[str],
) -> tuple[dict[str, Any], ...]:
    """Run each registered cheap consumer against the exact committed bytes."""

    from tools.quality.validation import check_layer3_gy_second_domain_pack as n10a
    from tools.quality.validation import check_layer3_gy_value_gate_contract as n8

    targets = set(target_paths)
    epoch_generated_family = {EPOCH_TARGET, REGISTRY_TARGET, REFERENCE_TARGET}
    present_epoch_generated = targets & epoch_generated_family
    if present_epoch_generated and present_epoch_generated != epoch_generated_family:
        raise ValueError("readback_epoch_generated_family_denominator_mismatch")
    known = {
        EPOCH_TARGET,
        REGISTRY_TARGET,
        REFERENCE_TARGET,
        n8.OUTPUT_PATH,
        *n10a.ARTIFACT_OUTPUTS,
    }
    unknown = sorted(targets - known)
    if unknown:
        raise ValueError("readback_consumer_unregistered:" + ",".join(unknown))
    results: list[dict[str, Any]] = []
    if EPOCH_TARGET in targets:
        from tools.quality.validation import check_layer3_gy_epoch_chronology_contract as epoch

        try:
            payload = json.loads(_git_blob(repo_root, expected_head, EPOCH_TARGET))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError("readback_epoch_payload_unreadable") from exc
        if not isinstance(payload, Mapping):
            raise ValueError("readback_epoch_payload_unreadable")
        issues = epoch.validate_payload(
            payload,
            repo_root=repo_root,
            expected_source_freeze=source_freeze,
        )
        row = {
            "target_path": EPOCH_TARGET,
            "consumer": "layer3_gy_epoch_chronology_contract.validate_payload",
            "status": "pass" if not issues else "fail",
            "issue_codes": sorted(str(issue.get("code")) for issue in issues),
        }
        results.append(row)

    if n8.OUTPUT_PATH in targets:
        try:
            payload = json.loads(_git_blob(repo_root, expected_head, n8.OUTPUT_PATH))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError("readback_n8_payload_unreadable") from exc
        if not isinstance(payload, Mapping):
            raise ValueError("readback_n8_payload_unreadable")
        result = n8.validate_payload_result(payload, expected_source_freeze=source_freeze)
        row = {
            "target_path": n8.OUTPUT_PATH,
            "consumer": "layer3_gy_value_gate_contract.validate_payload_result",
            "status": "pass" if not result.governing_issues else "fail",
            "issue_codes": sorted(str(issue.get("code")) for issue in result.governing_issues),
            "ambient_finding_count": len(result.ambient_findings),
        }
        results.append(row)

    n10_targets = set(n10a.ARTIFACT_OUTPUTS)
    present_n10 = targets & n10_targets
    if present_n10 and present_n10 != n10_targets:
        raise ValueError("readback_n10a_target_denominator_mismatch")
    if present_n10:
        bundle: dict[str, Any] = {}
        for relative, key, _hash_field, _mode in n10a._ARTIFACT_WRITE_SPECS:
            try:
                payload = json.loads(_git_blob(repo_root, expected_head, relative))
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise ValueError(f"readback_n10a_payload_unreadable:{relative}") from exc
            if not isinstance(payload, Mapping):
                raise ValueError(f"readback_n10a_payload_unreadable:{relative}")
            bundle[key] = payload
        issues = n10a.validate_bundle_payloads(
            bundle,
            repo_root,
            expected_source_freeze=source_freeze,
        )
        for relative in n10a.ARTIFACT_OUTPUTS:
            results.append(
                {
                    "target_path": relative,
                    "consumer": "layer3_gy_second_domain_pack.validate_bundle_payloads",
                    "status": "pass" if not issues else "fail",
                    "issue_codes": sorted(str(issue.get("code")) for issue in issues),
                }
            )

    generated_targets = {REGISTRY_TARGET, REFERENCE_TARGET}
    present_generated = targets & generated_targets
    if present_generated and present_generated != generated_targets:
        raise ValueError("readback_generated_reference_denominator_mismatch")
    if present_generated:
        from tools.devx.architecture import guardrails

        registry_raw = _git_blob(repo_root, expected_head, REGISTRY_TARGET)
        with tempfile.TemporaryDirectory(prefix="gy-n12-readback-registry-") as raw:
            registry_snapshot = Path(raw) / "generated_artifacts.toml"
            registry_snapshot.write_bytes(registry_raw)
            families = guardrails._parse_generated_artifacts(registry_snapshot)
        manifest_violations = guardrails._check_generated_artifact_manifest(families)
        expected_epoch_output = (guardrails.REPO_ROOT / EPOCH_TARGET).resolve()
        epoch_owners = [
            family
            for family in families
            if expected_epoch_output in {output.resolve() for output in family.outputs}
        ]
        expected_reference = guardrails.render_generated_artifacts_markdown(families).encode()
        observed_reference = _git_blob(repo_root, expected_head, REFERENCE_TARGET)
        issue_codes = [
            f"generated_artifact_manifest:{violation.detail or violation.check}"
            for violation in manifest_violations
        ]
        if len(epoch_owners) != 1:
            issue_codes.append("epoch_generated_family_owner_denominator_mismatch")
        if observed_reference != expected_reference:
            issue_codes.append("generated_artifact_reference_mismatch")
        status = "pass" if not issue_codes else "fail"
        for relative in (REGISTRY_TARGET, REFERENCE_TARGET):
            results.append(
                {
                    "target_path": relative,
                    "consumer": "architecture.guardrails.generated_artifact_reference",
                    "status": status,
                    "issue_codes": sorted(issue_codes),
                }
            )

    return tuple(sorted(results, key=lambda row: str(row["target_path"])))


def build_readback(
    *,
    repo_root: Path,
    declaration: Mapping[str, Any],
    final: Mapping[str, Any],
    expected_branch: str,
    expected_head: str,
    consumer_probe: Callable[..., Sequence[Mapping[str, Any]]] | None = None,
    dependency_consumer_probe: Callable[..., Sequence[Mapping[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Bind the artifact commit to the exact declared candidate byte set."""

    root = repo_root.resolve()
    if (
        not verify_receipt(declaration)
        or declaration.get("schema_version") != DECLARATION_SCHEMA
        or not verify_receipt(final)
        or final.get("schema_version") != FINAL_SCHEMA
        or final.get("status") != "final"
    ):
        raise ValueError("readback_receipt_invalid")
    if final.get("declaration_sha256") != declaration.get("receipt_sha256"):
        raise ValueError("readback_declaration_binding_mismatch")
    if declaration.get("expected_branch") != expected_branch:
        raise ValueError("readback_declaration_branch_binding_mismatch")
    if final.get("protected_denominator_sha256") != declaration.get("protected_denominator_sha256"):
        raise ValueError("readback_protected_denominator_mismatch")
    if _git(root, "symbolic-ref", "--short", "HEAD") != expected_branch:
        raise ValueError("readback_branch_mismatch")
    if _git(root, "rev-parse", "HEAD") != expected_head:
        raise ValueError("readback_head_mismatch")
    if _git(root, "status", "--porcelain", "--untracked-files=all"):
        raise ValueError("readback_worktree_not_clean")
    declaration_head = final.get("declaration_head")
    if not isinstance(declaration_head, str):
        raise ValueError("readback_declaration_head_missing")
    artifact_parent = _git(root, "rev-parse", f"{expected_head}^")
    if artifact_parent != declaration_head:
        raise ValueError("readback_artifact_parent_mismatch")
    expected_targets = sorted(str(row["path"]) for row in declaration.get("targets", ()))
    observed_targets = sorted(
        _product_relative_git_paths(
            root,
            _git(root, "diff-tree", "--no-commit-id", "--name-only", "-r", expected_head),
        )
    )
    if observed_targets != expected_targets:
        raise ValueError("readback_commit_delta_mismatch")
    expected_target_hashes = {
        str(row["path"]): str(row["candidate_sha256"]) for row in declaration.get("targets", ())
    }
    if final.get("target_sha256") != expected_target_hashes:
        raise ValueError("readback_final_target_map_mismatch")
    hashes: dict[str, str] = {}
    for row in declaration.get("targets", ()):
        relative = Path(str(row["path"]))
        observed = _digest_bytes(_git_blob(root, expected_head, relative.as_posix()))
        if observed != row.get("candidate_sha256"):
            raise ValueError(f"readback_target_mismatch:{relative}")
        hashes[relative.as_posix()] = observed
    source_freeze = declaration.get("source_freeze")
    if consumer_probe is None and not isinstance(source_freeze, str):
        raise ValueError("readback_source_freeze_missing")
    consumer_results = tuple(
        dict(row)
        for row in (consumer_probe or _run_readback_consumers)(
            repo_root=root,
            expected_head=expected_head,
            source_freeze=str(source_freeze or ""),
            target_paths=tuple(expected_targets),
        )
    )
    observed_consumer_targets = [str(row.get("target_path")) for row in consumer_results]
    if sorted(observed_consumer_targets) != expected_targets:
        raise ValueError("readback_consumer_denominator_mismatch")
    if any(row.get("status") != "pass" for row in consumer_results):
        raise ValueError("readback_consumer_rejected")
    dependency_consumer_results = tuple(
        dict(row)
        for row in (dependency_consumer_probe or _run_dependency_discriminant_consumers)(
            repo_root=root,
            expected_head=expected_head,
        )
    )
    discriminant_readback = reconcile_dependency_discriminant_consumers(
        dependency_consumer_results
    )
    return with_receipt_hash(
        {
            "schema_version": READBACK_SCHEMA,
            "status": "pass",
            "declaration_sha256": declaration["receipt_sha256"],
            "final_sha256": final["receipt_sha256"],
            "artifact_head": expected_head,
            "artifact_parent": artifact_parent,
            "artifact_tree": _git(root, "rev-parse", f"{expected_head}^{{tree}}"),
            "target_sha256": hashes,
            "consumer_results": list(consumer_results),
            "dependency_discriminant_readback": discriminant_readback,
        }
    )


def build_parser() -> argparse.ArgumentParser:
    """Return the exact five-command transition surface."""

    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    measure = subparsers.add_parser("measure")
    measure.add_argument("--implementation-base", required=True)
    measure.add_argument("--source-freeze", required=True)
    measure.add_argument("--output", type=Path, required=True)

    candidates = subparsers.add_parser("build-deployment-candidates")
    candidates.add_argument("--measurement", type=Path, required=True)
    candidates.add_argument("--candidate-dir", type=Path, required=True)
    candidates.add_argument("--n8-python", type=Path, required=True)
    candidates.add_argument("--n8-environment-receipt", type=Path, required=True)
    candidates.add_argument(
        "--n8-candidate-mode", choices=("candidate-reissue-catalog-provenance",), required=True
    )
    candidates.add_argument("--n10a-candidate-mode", choices=("candidate-dir",), required=True)
    candidates.add_argument("--epoch-candidate-mode", choices=("candidate-output",), required=True)
    candidates.add_argument("--output", type=Path, required=True)

    declare = subparsers.add_parser("declare")
    declare.add_argument("--measurement", type=Path, required=True)
    declare.add_argument("--candidate-receipt", type=Path, required=True)
    declare.add_argument("--expected-branch", required=True)
    declare.add_argument("--expected-source-freeze", required=True)
    declare.add_argument("--allowed-post-freeze-record", type=Path, action="append", required=True)
    declare.add_argument("--output", type=Path, required=True)

    apply_parser = subparsers.add_parser("apply")
    apply_parser.add_argument("--declaration", type=Path, required=True)
    apply_parser.add_argument("--candidate-dir", type=Path, required=True)
    apply_parser.add_argument("--expected-branch", required=True)
    apply_parser.add_argument("--expected-source-freeze", required=True)
    apply_parser.add_argument("--expected-declaration-head", required=True)
    apply_parser.add_argument("--state-dir", type=Path, required=True)

    readback = subparsers.add_parser("readback")
    readback.add_argument("--declaration", type=Path, required=True)
    readback.add_argument("--apply-receipt", type=Path, required=True)
    readback.add_argument("--expected-branch", required=True)
    readback.add_argument("--expected-head", required=True)
    readback.add_argument("--output", type=Path, required=True)
    return parser


def _write_output(path: Path, payload: Mapping[str, Any]) -> None:
    _write_exclusive(path, payload)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = _repo_root()
    try:
        output = getattr(args, "output", None)
        if output is not None:
            args.output = _require_external_path(
                root,
                output,
                code="output_path_inside_repository",
            )
        if args.command == "measure":
            from polisyos.runtime.quality.confidence_ledger import _deployment_relative_paths

            payload = build_measurement(
                repo_root=root,
                implementation_base=args.implementation_base,
                source_freeze=args.source_freeze,
                deployment_paths=_deployment_relative_paths(root),
                tool_sources=_tool_sources(),
                potential_targets=_potential_targets(),
            )
        elif args.command == "build-deployment-candidates":
            measurement = _read_receipt(args.measurement, schema=MEASUREMENT_SCHEMA)
            payload = build_candidates(
                repo_root=root,
                measurement=measurement,
                candidate_dir=args.candidate_dir,
                n8_python=args.n8_python,
                n8_environment_receipt_path=args.n8_environment_receipt,
            )
        elif args.command == "declare":
            measurement = _read_receipt(args.measurement, schema=MEASUREMENT_SCHEMA)
            candidate = _read_receipt(args.candidate_receipt, schema=CANDIDATE_SCHEMA)
            payload = build_declaration(
                measurement=measurement,
                candidate_receipt=candidate,
                expected_branch=args.expected_branch,
                expected_source_freeze=args.expected_source_freeze,
                allowed_post_freeze_records=tuple(args.allowed_post_freeze_record),
            )
        elif args.command == "apply":
            args.state_dir = _require_external_path(
                root,
                args.state_dir,
                code="state_directory_inside_repository",
            )
            recovered = recover_armed_transition(repo_root=root, state_dir=args.state_dir)
            if recovered is not None:
                raise RuntimeError("recovered_armed_transition")
            declaration = _read_receipt(args.declaration, schema=DECLARATION_SCHEMA)
            if declaration.get("expected_branch") != args.expected_branch:
                raise ValueError("apply_declaration_branch_binding_mismatch")
            if declaration.get("source_freeze") != args.expected_source_freeze:
                raise ValueError("apply_declaration_source_freeze_binding_mismatch")
            if _git(root, "symbolic-ref", "--short", "HEAD") != args.expected_branch:
                raise ValueError("apply_branch_mismatch")
            if _git(root, "rev-parse", "HEAD") != args.expected_declaration_head:
                raise ValueError("apply_declaration_head_mismatch")
            if (
                _git(root, "rev-parse", f"{args.expected_declaration_head}^")
                != args.expected_source_freeze
            ):
                raise ValueError("apply_declaration_not_direct_freeze_child")
            if _git(root, "status", "--porcelain", "--untracked-files=all"):
                raise ValueError("apply_worktree_not_clean")
            source_tree = _git(root, "rev-parse", f"{args.expected_source_freeze}^{{tree}}")
            if source_tree != declaration.get("source_tree"):
                raise ValueError("apply_source_tree_mismatch")
            for row in declaration.get("tool_sources", ()):
                if not isinstance(row, dict) or not _snapshot_matches(root, row):
                    raise ValueError("apply_tool_source_drift")
            changed = _product_relative_git_paths(
                root,
                _git(
                    root,
                    "diff",
                    "--name-only",
                    args.expected_source_freeze,
                    args.expected_declaration_head,
                    "--",
                ),
            )
            if changed != set(declaration.get("allowed_post_freeze_records", ())):
                raise ValueError("apply_source_declaration_relationship_invalid")
            records = declaration.get("allowed_post_freeze_records", ())
            if not isinstance(records, list) or len(records) != 1:
                raise ValueError("apply_declaration_record_denominator_invalid")
            if _git_blob(root, args.expected_declaration_head, str(records[0])) != (
                _canonical_bytes(declaration) + b"\n"
            ):
                raise ValueError("apply_declaration_record_content_mismatch")

            def runtime_guard() -> None:
                if _git(root, "symbolic-ref", "--short", "HEAD") != args.expected_branch:
                    raise RuntimeError("apply_branch_changed_during_write")
                if _git(root, "rev-parse", "HEAD") != args.expected_declaration_head:
                    raise RuntimeError("apply_head_changed_during_write")

            payload = apply_declaration(
                repo_root=root,
                declaration=declaration,
                candidate_dir=args.candidate_dir,
                state_dir=args.state_dir,
                runtime_guard=runtime_guard,
                expected_branch=args.expected_branch,
                expected_declaration_head=args.expected_declaration_head,
            )
        else:
            declaration = _read_receipt(args.declaration, schema=DECLARATION_SCHEMA)
            final = _read_receipt(args.apply_receipt, schema=FINAL_SCHEMA)
            payload = build_readback(
                repo_root=root,
                declaration=declaration,
                final=final,
                expected_branch=args.expected_branch,
                expected_head=args.expected_head,
            )
        if args.command not in {"apply"}:
            _write_output(args.output, payload)
        print(_canonical_bytes(payload).decode())
        return 0
    except (FileExistsError, OSError, RuntimeError, ValueError) as exc:
        payload = with_receipt_hash(
            {
                "schema_version": "polisyos.gy-n12.artifact-transition-nonreceipt.v1",
                "status": "not_established",
                "command": args.command,
                "issues": [{"code": str(exc).split(":", 1)[0], "detail": str(exc)}],
            }
        )
        print(_canonical_bytes(payload).decode())
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
