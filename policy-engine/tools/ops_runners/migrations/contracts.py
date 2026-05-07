"""Operational migration contract loader for migration helper CLIs."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.lib.imports import repo_root_from

CONTRACT_PATH = Path("ops/migrations/migration-contracts.toml")


@dataclass(frozen=True)
class HelperBinding:
    """Binding between an operator helper artifact and an ops migration class."""

    artifact: str
    cli: str
    migration_class: str
    implementation: str
    contract_path: str
    release_gate: str


def load_contract(repo_root: Path | None = None) -> dict[str, Any]:
    """Load the operational migration contract."""
    root = repo_root or repo_root_from(__file__)
    path = root / CONTRACT_PATH
    if not path.exists():
        raise FileNotFoundError(f"missing migration contract: {path}")
    return tomllib.loads(path.read_text(encoding="utf-8"))


def helper_binding_for(artifact: str, repo_root: Path | None = None) -> HelperBinding:
    """Return the declared helper binding for an artifact."""
    contract = load_contract(repo_root)
    for raw in contract.get("helper_binding", []):
        if raw.get("artifact") == artifact:
            return HelperBinding(
                artifact=str(raw["artifact"]),
                cli=str(raw["cli"]),
                migration_class=str(raw["migration_class"]),
                implementation=str(raw["implementation"]),
                contract_path=str(raw["contract_path"]),
                release_gate=str(raw["release_gate"]),
            )
    raise ValueError(f"no helper_binding for migration artifact: {artifact}")


def validate_helper_binding(artifact: str, repo_root: Path | None = None) -> HelperBinding:
    """Fail closed if a helper artifact is not backed by a live ops contract."""
    root = repo_root or repo_root_from(__file__)
    contract = load_contract(root)
    classes = {item["id"]: item for item in contract.get("migration_class", [])}
    binding = helper_binding_for(artifact, root)
    migration_class = classes.get(binding.migration_class)
    if migration_class is None:
        raise ValueError(
            f"helper_binding for {artifact!r} references unknown migration class "
            f"{binding.migration_class!r}"
        )

    contract_path = root / binding.contract_path
    if not contract_path.exists():
        raise FileNotFoundError(
            f"helper_binding for {artifact!r} references missing contract path: "
            f"{binding.contract_path}"
        )

    class_path = root / str(migration_class["target_path"])
    if class_path != contract_path:
        raise ValueError(
            f"helper_binding for {artifact!r} points to {binding.contract_path!r}, "
            f"but migration class {binding.migration_class!r} targets "
            f"{migration_class['target_path']!r}"
        )
    return binding


__all__ = [
    "CONTRACT_PATH",
    "HelperBinding",
    "helper_binding_for",
    "load_contract",
    "validate_helper_binding",
]
