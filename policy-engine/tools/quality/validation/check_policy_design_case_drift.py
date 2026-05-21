#!/usr/bin/env python3
"""Audit initial Policy Design Case drift guards."""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence

from tools.lib.fs import atomic_write_text
from tools.lib.imports import ensure_repo_import_roots

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

SCHEMA_VERSION = "policyos.policy_design_case.drift.v1"
TOOL_NAME = "quality.validation.check-policy-design-case-drift"
DEFAULT_SDD = Path("docs/system-design-decisions/policy-design-best-in-class-operating-model.md")
DEFAULT_OUTPUT = Path("_build/policy-design-case/drift/policy_design_case_drift.json")
DEFAULT_TEXT_OUTPUT = Path("_build/policy-design-case/drift/policy_design_case_drift.txt")
DEFAULT_SCAN_PATHS = (Path("src/polisyos"),)

ALLOWED_CLASSIFICATIONS = frozenset(
    {"wire-existing", "extend-existing", "consolidate-existing", "build-new"}
)
REUSE_CRITICAL_SURFACES = (
    "runtime/quality",
    "data_forge",
    "scholar",
    "foundry",
    "scientist",
    "ir/analytics",
    "berl",
    "ddm",
    "core/audit",
    "core/governance",
    "core/contracts",
)
RUNTIME_QUALITY_AUTHORITY_PATH = Path("src/polisyos/runtime/quality/assurance_case.py")
PARALLEL_AUTHORITY_WORDS = ("authority", "profile", "ledger", "case")
AUTHORITY_PROFILE_TAXONOMY_OWNER_PATHS = frozenset(
    {
        Path("src/polisyos/core/contracts/control.py"),
        Path("src/polisyos/core/governance/profiles.py"),
        Path("src/polisyos/runtime/quality/effective_mode.py"),
    }
)
AUTHORITY_PROFILE_TAXONOMY_NAMES = frozenset(
    {
        "EXECUTION_PROFILE_ORDER",
        "POLICY_AUTHORITY_PROFILES",
        "POLICY_AUTHORITY_LEVELS",
        "POLICY_AUTHORITY_TO_EXECUTION_PROFILE",
        "POLICY_AUTHORITY_TO_FALLBACK_PROFILE",
        "POLICY_AUTHORITY_TO_VALIDATION_PROFILE",
        "POLICY_AUTHORITY_LEVEL_TO_VALIDATION",
        "SUPPORTED_EXECUTION_PROFILES",
    }
)
AUTHORITY_PROFILE_VALUE_TOKENS = frozenset({"research", "governed", "production"})


@dataclass(frozen=True)
class DriftViolation:
    code: str
    path: str
    line: int
    message: str
    target_capability: str | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": self.code,
            "path": self.path,
            "line": self.line,
            "message": self.message,
        }
        if self.target_capability is not None:
            payload["target_capability"] = self.target_capability
        return payload


def build_policy_design_case_drift_payload(
    *,
    repo_root: Path = REPO_ROOT,
    scan_paths: Sequence[Path] | None = None,
    sdd_path: Path | None = DEFAULT_SDD,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    paths = list(DEFAULT_SCAN_PATHS if scan_paths is None else scan_paths)
    violations: list[DriftViolation] = []
    scanned: list[str] = []

    capability_map = _load_capability_map(repo_root=repo_root, sdd_path=sdd_path)
    violations.extend(capability_map["violations"])

    for raw_path in paths:
        expanded = _expand_scan_path(repo_root, raw_path)
        if not expanded and scan_paths is None:
            violations.append(
                DriftViolation(
                    code="pdc_scan_path_missing",
                    path=raw_path.as_posix(),
                    line=1,
                    message="Policy Design Case drift scan path does not exist.",
                )
            )
            continue
        for path in expanded:
            file_paths = (
                sorted(item for item in path.rglob("*.py") if item.is_file())
                if path.is_dir()
                else [path]
            )
            for file_path in file_paths:
                if file_path.suffix != ".py":
                    continue
                file_rel = _rel(file_path, repo_root)
                scanned.append(file_rel)
                violations.extend(_parallel_case_authority_violations(file_path, repo_root))
                violations.extend(_second_profile_taxonomy_violations(file_path, repo_root))

    parallel_violations = [
        violation for violation in violations if violation.code == "pdc_parallel_case_authority"
    ]
    profile_taxonomy_violations = [
        violation
        for violation in violations
        if violation.code == "pdc_second_authority_profile_taxonomy"
    ]
    reuse_violations = [
        violation for violation in violations if violation.code.startswith("pdc_")
        and violation.code != "pdc_parallel_case_authority"
    ]
    runtime_quality_authority_paths = []
    runtime_quality_authority = repo_root / RUNTIME_QUALITY_AUTHORITY_PATH
    if runtime_quality_authority.is_file():
        runtime_quality_authority_paths.append(_rel(runtime_quality_authority, repo_root))

    status = "fail" if violations else "pass"
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "status": status,
        "repo_root": str(repo_root),
        "scan_paths": sorted(scanned),
        "runtime_quality_authority_paths": runtime_quality_authority_paths,
        "capability_map": {
            "source": capability_map["source"],
            "target_capability_count": len(capability_map["entries"]),
            "entries": capability_map["entries"],
        },
        "reuse_violation_count": len(reuse_violations),
        "parallel_case_authority_violation_count": len(parallel_violations),
        "profile_taxonomy_violation_count": len(profile_taxonomy_violations),
        "violations": [violation.as_dict() for violation in violations],
    }


def dump_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def render_text(payload: dict[str, Any]) -> str:
    lines = [
        f"{TOOL_NAME}: {payload['status']}",
        (
            "capabilities={capability_count} reuse_violations={reuse_violation_count} "
            "parallel_case_authority={parallel_case_authority_violation_count}"
        ).format(
            capability_count=payload["capability_map"]["target_capability_count"],
            **payload,
        ),
    ]
    for violation in payload.get("violations", []):
        if isinstance(violation, dict):
            lines.append("[fail] {path}:{line} {code}: {message}".format(**violation))
    return "\n".join(lines) + "\n"


def _load_capability_map(
    *, repo_root: Path, sdd_path: Path | None
) -> dict[str, Any]:
    if sdd_path is None:
        return {"source": None, "entries": [], "violations": []}
    resolved = _resolve(repo_root, sdd_path)
    try:
        text = resolved.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {
            "source": _rel(resolved, repo_root),
            "entries": [],
            "violations": [
                DriftViolation(
                    code="pdc_capability_map_missing",
                    path=_rel(resolved, repo_root),
                    line=1,
                    message="Policy Design Case SDD capability realization map is missing.",
                )
            ],
        }
    entries = _parse_capability_map(text)
    violations = _capability_map_violations(entries, path=_rel(resolved, repo_root))
    return {"source": _rel(resolved, repo_root), "entries": entries, "violations": violations}


def _parse_capability_map(text: str) -> list[dict[str, Any]]:
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.strip().startswith("| Target capability | Existing owner or surface | Status |"):
            start = index + 2
            break
    if start is None:
        return []

    entries: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines[start:], start=start + 1):
        stripped = line.strip()
        if not stripped.startswith("|"):
            break
        cells = _split_markdown_row(stripped)
        if len(cells) < 4:
            continue
        status_cell = _strip_markdown(cells[2])
        classifications = _classifications(status_cell)
        entries.append(
            {
                "target_capability": _strip_markdown(cells[0]),
                "existing_owner_or_surface": _strip_markdown(cells[1]),
                "status": status_cell,
                "classifications": classifications,
                "design_implication": _strip_markdown(cells[3]),
                "line": line_number,
            }
        )
    return entries


def _capability_map_violations(
    entries: Sequence[dict[str, Any]], *, path: str
) -> list[DriftViolation]:
    violations: list[DriftViolation] = []
    if not entries:
        violations.append(
            DriftViolation(
                code="pdc_capability_map_empty",
                path=path,
                line=1,
                message="Capability Realization Map must contain target capability rows.",
            )
        )
        return violations

    for entry in entries:
        target = str(entry["target_capability"])
        classifications = set(entry["classifications"])
        line = int(entry["line"])
        if not classifications:
            violations.append(
                DriftViolation(
                    code="pdc_reuse_classification_missing",
                    path=path,
                    line=line,
                    message="Capability map row must declare a reuse classification.",
                    target_capability=target,
                )
            )
            continue
        invalid = classifications - ALLOWED_CLASSIFICATIONS
        if invalid:
            violations.append(
                DriftViolation(
                    code="pdc_reuse_classification_invalid",
                    path=path,
                    line=line,
                    message=f"Unsupported reuse classification: {', '.join(sorted(invalid))}.",
                    target_capability=target,
                )
            )
        if "build-new" in classifications and _overlaps_reuse_critical_surface(entry):
            violations.append(
                DriftViolation(
                    code="pdc_build_new_reuse_evidence_missing",
                    path=path,
                    line=line,
                    message=(
                        "build-new overlaps a protected existing owner and needs rejected-reuse "
                        "evidence before Phase 1.5 drift can pass."
                    ),
                    target_capability=target,
                )
            )
    return violations


def _parallel_case_authority_violations(path: Path, repo_root: Path) -> list[DriftViolation]:
    file_rel = _rel(path, repo_root)
    if file_rel.startswith("src/polisyos/runtime/quality/"):
        return []
    text = path.read_text(encoding="utf-8")
    if "policy_design_case" not in text and "PolicyDesignCase" not in text:
        return []
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return [
            DriftViolation(
                code="pdc_scan_python_syntax_error",
                path=file_rel,
                line=exc.lineno or 1,
                message=f"Could not parse Policy Design Case drift source: {exc.msg}",
            )
        ]

    violations: list[DriftViolation] = []
    for node in ast.walk(tree):
        if isinstance(
            node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
        ) and _looks_like_parallel_policy_design_case_authority(node.name):
            violations.append(
                DriftViolation(
                    code="pdc_parallel_case_authority",
                    path=file_rel,
                    line=getattr(node, "lineno", 1),
                    message=(
                        "Policy Design Case authority/profile/ledger code must extend "
                        "src/polisyos/runtime/quality/assurance_case.py instead of "
                        "creating a parallel case authority."
                    ),
                )
            )
    return violations


def _second_profile_taxonomy_violations(path: Path, repo_root: Path) -> list[DriftViolation]:
    file_rel = _rel(path, repo_root)
    if Path(file_rel) in AUTHORITY_PROFILE_TAXONOMY_OWNER_PATHS:
        return []
    text = path.read_text(encoding="utf-8")
    if (
        "AUTHORITY_PROFILE" not in text
        and "AUTHORITY_LEVEL" not in text
        and "EXECUTION_PROFILE_ORDER" not in text
    ):
        return []
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return [
            DriftViolation(
                code="pdc_scan_python_syntax_error",
                path=file_rel,
                line=exc.lineno or 1,
                message=f"Could not parse Policy Design Case drift source: {exc.msg}",
            )
        ]

    violations: list[DriftViolation] = []
    for node in ast.walk(tree):
        assigned_names = _assigned_names(node)
        duplicate_names = sorted(
            assigned_names & AUTHORITY_PROFILE_TAXONOMY_NAMES
            or {
                name
                for name in assigned_names
                if _looks_like_authority_profile_taxonomy_name(name)
                and _contains_policy_authority_values(node)
            }
        )
        for name in duplicate_names:
            violations.append(
                DriftViolation(
                    code="pdc_second_authority_profile_taxonomy",
                    path=file_rel,
                    line=getattr(node, "lineno", 1),
                    message=(
                        f"{name} must be imported from core/contracts/control.py or "
                        "mapped through core/governance/profiles.py and "
                        "runtime/quality/effective_mode.py, not redefined."
                    ),
                )
            )
    return violations


def _looks_like_authority_profile_taxonomy_name(name: str) -> bool:
    normalized = name.casefold()
    return (
        "policy" in normalized
        and "authority" in normalized
        and any(token in normalized for token in ("profile", "profiles", "level", "levels"))
    )


def _contains_policy_authority_values(node: ast.AST) -> bool:
    values = {
        child.value.strip().casefold().replace("-", "_")
        for child in ast.walk(node)
        if isinstance(child, ast.Constant) and isinstance(child.value, str)
    }
    return len(values & AUTHORITY_PROFILE_VALUE_TOKENS) >= 2


def _assigned_names(node: ast.AST) -> set[str]:
    if isinstance(node, ast.Assign):
        return {name for target in node.targets for name in _target_names(target)}
    if isinstance(node, ast.AnnAssign):
        return set(_target_names(node.target))
    return set()


def _target_names(node: ast.AST) -> tuple[str, ...]:
    if isinstance(node, ast.Name):
        return (node.id,)
    if isinstance(node, ast.Tuple | ast.List):
        return tuple(name for item in node.elts for name in _target_names(item))
    return ()


def _looks_like_parallel_policy_design_case_authority(name: str) -> bool:
    normalized = name.casefold()
    compact = re.sub(r"[^a-z0-9]", "", normalized)
    has_case = "policy_design_case" in normalized or "policydesigncase" in compact
    has_authority_word = any(
        word in normalized or word in compact for word in PARALLEL_AUTHORITY_WORDS
    )
    return has_case and has_authority_word


def _overlaps_reuse_critical_surface(entry: dict[str, Any]) -> bool:
    text = " ".join(
        str(entry.get(key) or "")
        for key in (
            "target_capability",
            "existing_owner_or_surface",
            "design_implication",
        )
    ).casefold()
    normalized = text.replace("`", "").replace("\\", "/")
    if _has_rejected_reuse_evidence(normalized):
        return False
    return any(surface in normalized for surface in REUSE_CRITICAL_SURFACES)


def _has_rejected_reuse_evidence(text: str) -> bool:
    return any(
        marker in text
        for marker in (
            "rejected reuse",
            "rejected-reuse",
            "no canonical owner",
            "no tla",
            "no tla+",
            "no pluscal",
            "specific capability gap",
        )
    )


def _classifications(status_cell: str) -> list[str]:
    normalized = status_cell.replace("`", "")
    parts = re.split(r"\s*/\s*|\s*,\s*|\s+and\s+", normalized)
    return [part.strip() for part in parts if part.strip() in ALLOWED_CLASSIFICATIONS]


def _split_markdown_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _strip_markdown(value: str) -> str:
    return value.replace("`", "").replace("\\_", "_").strip()


def _resolve(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def _expand_scan_path(repo_root: Path, path: Path) -> list[Path]:
    raw = path.as_posix()
    if any(char in raw for char in "*?[]"):
        return sorted(repo_root.glob(raw))
    resolved = _resolve(repo_root, path)
    return [resolved] if resolved.exists() else []


def _rel(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--sdd", type=Path, default=DEFAULT_SDD)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--text-output", type=Path, default=DEFAULT_TEXT_OUTPUT)
    parser.add_argument("--output-format", choices=("text", "json"), default="text")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = args.repo_root.resolve()
    payload = build_policy_design_case_drift_payload(
        repo_root=repo_root,
        sdd_path=args.sdd,
    )
    atomic_write_text(_resolve(repo_root, args.json_output), dump_json(payload))
    atomic_write_text(_resolve(repo_root, args.text_output), render_text(payload))
    rendered = dump_json(payload) if args.output_format == "json" else render_text(payload)
    sys.stdout.write(rendered)
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
