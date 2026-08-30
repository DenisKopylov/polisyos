from __future__ import annotations

import tomllib
from pathlib import Path

from tools.quality.lint import lint_imports

REPO_ROOT = Path(__file__).resolve().parents[3]
POLICY_PATH = REPO_ROOT / "architecture" / "imports" / "policy.toml"
BOUNDARIES_PATH = REPO_ROOT / "architecture" / "packages" / "boundaries.toml"
SOURCE_ROOT = REPO_ROOT / "src" / "polisyos"


def _read_toml(path: Path) -> dict[str, object]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _root(module: str) -> str:
    prefix = "polisyos."
    assert module.startswith(prefix)
    return module.removeprefix(prefix).split(".", 1)[0]


def test_import_authority_contracts_declare_distinct_canonical_roles() -> None:
    policy = _read_toml(POLICY_PATH)
    boundaries = _read_toml(BOUNDARIES_PATH)

    policy_contract = policy["policy"]
    boundary_contract = boundaries["package_boundaries"]
    assert isinstance(policy_contract, dict)
    assert isinstance(boundary_contract, dict)
    assert policy_contract["contract_role"] == "enforced_direction_matrix"
    assert boundary_contract["contract_role"] == "ownership_and_narrowing_register"

    boundary_ref = policy_contract["package_boundaries"]
    assert isinstance(boundary_ref, str)
    assert (POLICY_PATH.parent / boundary_ref).resolve() == BOUNDARIES_PATH.resolve()


def test_every_direction_root_exists_and_has_package_governance_disposition() -> None:
    policy = _read_toml(POLICY_PATH)
    boundaries = _read_toml(BOUNDARIES_PATH)

    internal = policy["internal"]
    assert isinstance(internal, dict)
    allow = internal["allow"]
    assert isinstance(allow, dict)
    matrix_roots = set(allow)
    nonexistent = sorted(root for root in matrix_roots if not (SOURCE_ROOT / root).is_dir())
    assert nonexistent == []

    packages = boundaries["package"]
    assert isinstance(packages, list)
    governed = {
        _root(entry["module"])
        for entry in packages
        if isinstance(entry, dict)
        and isinstance(entry.get("module"), str)
        and entry["module"].count(".") == 1
        and isinstance(entry.get("owner"), str)
        and entry["owner"].startswith("team-")
    }
    ungoverned_rows = boundaries["deliberately_ungoverned_root"]
    assert isinstance(ungoverned_rows, list)
    ungoverned = {
        entry["root"]
        for entry in ungoverned_rows
        if isinstance(entry, dict)
        and isinstance(entry.get("root"), str)
        and isinstance(entry.get("reason"), str)
        and entry["reason"].strip()
    }
    assert sorted(matrix_roots - governed - ungoverned) == []
    assert governed.isdisjoint(ungoverned)


def test_five_remaining_narrowings_have_one_canonical_form() -> None:
    config = lint_imports.read_policy(POLICY_PATH)

    assert config.internal_narrowings == {
        ("fabric", "data_forge"): ("polisyos.data_forge.read_api",),
        ("foundry", "data_forge"): ("polisyos.data_forge.read_api",),
        ("ir", "data_forge"): ("polisyos.data_forge.read_api",),
        ("lex", "data_forge"): ("polisyos.data_forge.read_api",),
        ("scientist", "data_forge"): ("polisyos.data_forge.read_api",),
    }
