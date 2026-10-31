"""Operational migration contract loader for migration helper CLIs."""

from __future__ import annotations

import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any

from tools.lib.imports import repo_root_from

CONTRACT_PATH = Path("ops/migrations/migration-contracts.toml")


def _workspace_layout(root: Path) -> bool:
    return (root / "pyproject.toml").is_file() and all(
        (root / name).is_dir() for name in ("tools", "src")
    )


def resolve_contract_root(
    repo_root: Path | None = None, *, module_path: str | Path | None = None
) -> Path:
    """Find the contract workspace from source ancestry or installed runner CWD.

    An explicitly supplied root must itself have the expected layout. This is
    layout discovery, not authentication of the workspace or installed code.
    """
    if repo_root is not None:
        root = Path(repo_root).expanduser().resolve()
        if not _workspace_layout(root):
            raise ValueError(f"Invalid migration workspace layout: {root}")
        return root

    for start in (Path(module_path or __file__), Path.cwd()):
        try:
            root = repo_root_from(start)
        except ValueError:
            continue
        if _workspace_layout(root):
            return root
    raise ValueError("No existing migration workspace could be resolved")


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
    root = resolve_contract_root(repo_root)
    path = root / CONTRACT_PATH
    if not path.exists():
        raise FileNotFoundError(f"missing migration contract: {path}")
    return tomllib.loads(path.read_text(encoding="utf-8"))


def helper_binding_for(artifact: str, repo_root: Path | None = None) -> HelperBinding:
    """Return the declared helper binding for an artifact."""
    return _binding_from_contract(artifact, load_contract(repo_root))


def _binding_from_contract(artifact: str, contract: dict[str, Any]) -> HelperBinding:
    matches = [raw for raw in contract.get("helper_binding", []) if raw.get("artifact") == artifact]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one helper_binding for migration artifact: {artifact}")
    raw = matches[0]
    return HelperBinding(
        artifact=str(raw["artifact"]),
        cli=str(raw["cli"]),
        migration_class=str(raw["migration_class"]),
        implementation=str(raw["implementation"]),
        contract_path=str(raw["contract_path"]),
        release_gate=str(raw["release_gate"]),
    )


def validate_helper_binding(artifact: str, repo_root: Path | None = None) -> HelperBinding:
    """Fail closed if a helper artifact is not backed by a live ops contract."""
    root = resolve_contract_root(repo_root)
    contract = load_contract(root)
    binding = _binding_from_contract(artifact, contract)
    classes = [
        item
        for item in contract.get("migration_class", [])
        if item.get("id") == binding.migration_class
    ]
    if len(classes) != 1:
        raise ValueError(
            f"helper_binding for {artifact!r} requires exactly one migration class "
            f"{binding.migration_class!r}"
        )
    migration_class = classes[0]

    contract_path = (root / binding.contract_path).resolve()
    if not contract_path.is_relative_to(root):
        raise ValueError(f"helper_binding for {artifact!r} escapes the migration workspace")
    if not contract_path.exists():
        raise FileNotFoundError(
            f"helper_binding for {artifact!r} references missing contract path: "
            f"{binding.contract_path}"
        )

    class_path = (root / str(migration_class["target_path"])).resolve()
    if class_path != contract_path:
        raise ValueError(
            f"helper_binding for {artifact!r} points to {binding.contract_path!r}, "
            f"but migration class {binding.migration_class!r} targets "
            f"{migration_class['target_path']!r}"
        )
    return binding


def resolve_helper_implementation(binding: HelperBinding) -> Callable[..., Any]:
    """Resolve the declared artifact migration implementation to a callable."""
    module_name, separator, attribute_name = binding.implementation.rpartition(".")
    if not separator or not module_name or not attribute_name:
        raise ValueError(f"Invalid migration implementation: {binding.implementation!r}")
    try:
        module = import_module(module_name)
        implementation = getattr(module, attribute_name)
    except (ImportError, AttributeError) as exc:
        raise ValueError(
            f"Cannot resolve migration implementation {binding.implementation!r}"
        ) from exc
    if not callable(implementation):
        raise ValueError(f"Migration implementation is not callable: {binding.implementation!r}")
    return implementation


__all__ = [
    "CONTRACT_PATH",
    "HelperBinding",
    "helper_binding_for",
    "load_contract",
    "resolve_contract_root",
    "resolve_helper_implementation",
    "validate_helper_binding",
]
