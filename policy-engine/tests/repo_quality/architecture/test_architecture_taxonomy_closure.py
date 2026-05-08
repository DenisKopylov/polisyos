from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
ARCHITECTURE_ROOT = REPO_ROOT / "architecture"

EXPECTED_REHOMED_CONTRACTS = {
    "architecture/gates/compatibility_release.toml",
    "architecture/gates/operability_release_supply_chain.toml",
    "architecture/gates/package_import.toml",
    "architecture/gates/repository_sota.toml",
    "architecture/gates/structure_remediation.toml",
    "architecture/imports/contracts.toml",
    "architecture/imports/dynamic.toml",
    "architecture/packages/boundaries.toml",
    "architecture/packages/layout.toml",
    "architecture/public_surface/contract.toml",
    "architecture/tests/ratchets.toml",
    "architecture/tests/topology.toml",
    "architecture/baselines/ops.toml",
    "architecture/exceptions/complexity.toml",
    "architecture/exceptions/docs_freshness.toml",
    "architecture/exceptions/guardrails.toml",
    "architecture/policies/cross_cutting_concerns.toml",
    "architecture/policies/data.toml",
    "architecture/policies/directory_contracts.toml",
    "architecture/policies/directory_health.toml",
    "architecture/tooling/static_analysis_overrides.toml",
}

STALE_REHOMED_CONTRACTS = {
    "architecture/compatibility_release_gates.toml",
    "architecture/operability_release_supply_chain_gates.toml",
    "architecture/package_import_gates.toml",
    "architecture/repository_sota_gates.toml",
    "architecture/structure_remediation_gates.toml",
    "architecture/import_contracts.toml",
    "architecture/dynamic_imports.toml",
    "architecture/package_boundaries.toml",
    "architecture/package_layout.toml",
    "architecture/public_surface.toml",
    "architecture/test_ratchets.toml",
    "architecture/test_topology.toml",
    "architecture/ops_baselines.toml",
    "architecture/complexity_exceptions.toml",
    "architecture/docs_freshness_exceptions.toml",
    "architecture/guardrail_exceptions.toml",
    "architecture/cross_cutting_concerns.toml",
    "architecture/data_policy.toml",
    "architecture/directory_contracts.toml",
    "architecture/directory_health.toml",
    "architecture/static_analysis_overrides.toml",
}

STALE_GATE_SOURCE_CONTRACTS = {
    "architecture/compatibility_release_gates.toml",
    "architecture/operability_release_supply_chain_gates.toml",
    "architecture/package_import_gates.toml",
    "architecture/repository_sota_gates.toml",
    "architecture/structure_remediation_gates.toml",
}


def test_phase6_1_root_toml_count_is_below_post_merge_baseline() -> None:
    index = _read_toml(ARCHITECTURE_ROOT / "index.toml")
    baseline = index["architecture_index"]["root_toml_post_merge_baseline"]
    root_tomls = sorted(ARCHITECTURE_ROOT.glob("*.toml"))

    assert len(root_tomls) < baseline, [path.name for path in root_tomls]


def test_phase6_1_rehomed_contracts_exist_only_under_taxonomy_dirs() -> None:
    for relative_path in EXPECTED_REHOMED_CONTRACTS:
        assert (REPO_ROOT / relative_path).exists(), relative_path
    for relative_path in STALE_REHOMED_CONTRACTS:
        assert not (REPO_ROOT / relative_path).exists(), relative_path


def test_phase6_1_top_level_prefixes_require_indexed_exceptions() -> None:
    index = _read_toml(ARCHITECTURE_ROOT / "index.toml")
    exceptions = {
        item["path"]: item
        for item in (
            *index.get("top_level_contract", []),
            *index.get("top_level_exception", []),
        )
    }

    for domain in index.get("taxonomy_domain", []):
        directory = REPO_ROOT / domain["directory"]
        assert directory.is_dir(), domain["id"]
        for path in sorted(ARCHITECTURE_ROOT.glob("*.toml")):
            relative_path = path.relative_to(REPO_ROOT).as_posix()
            if not _matches_any_prefix(path.stem, domain.get("top_level_prefixes", [])):
                continue
            exception = exceptions.get(relative_path)
            assert exception is not None, (domain["id"], relative_path)
            assert exception["domain"] == domain["id"], relative_path
            assert exception.get("canonical_root_contract") is True, relative_path
            assert exception.get("reason"), relative_path


def test_phase6_1_gate_index_maps_every_gate_id_to_contract_and_command() -> None:
    readme = REPO_ROOT / "architecture/gates/README.md"
    index_path = REPO_ROOT / "architecture/gates/index.toml"
    gates_index = _read_toml(index_path)
    indexed = {
        (entry["source_contract"], entry["id"]): entry for entry in gates_index.get("gate", [])
    }

    assert readme.is_file()
    assert gates_index["gates_index"]["status"] == "active"

    source_contracts = {entry["source_contract"] for entry in gates_index.get("gate_contract", [])}
    for relative_path in source_contracts:
        assert relative_path.startswith("architecture/gates/"), relative_path
        assert (REPO_ROOT / relative_path).is_file(), relative_path

    gate_ids: set[tuple[str, str]] = set()
    for relative_path in source_contracts:
        contract = _read_toml(REPO_ROOT / relative_path)
        gate_ids.update((relative_path, gate_id) for gate_id in _ids_from_table(contract, "gate"))
        gate_ids.update(
            (relative_path, gate_id) for gate_id in _ids_from_table(contract, "promotion_check")
        )

    assert gate_ids
    assert gate_ids <= set(indexed), sorted(gate_ids - set(indexed))

    for source_contract, gate_id in gate_ids:
        entry = indexed[(source_contract, gate_id)]
        assert entry["command"], (source_contract, gate_id)


def test_phase6_1_gate_sources_do_not_reference_stale_root_paths() -> None:
    search_roots = [
        REPO_ROOT / "architecture",
        REPO_ROOT / "tests/repo_quality",
        REPO_ROOT / "tools",
    ]
    checked_files = [
        path
        for root in search_roots
        for path in root.rglob("*")
        if path.suffix in {".md", ".py", ".toml", ".yaml", ".yml"}
    ]

    for path in checked_files:
        if path == Path(__file__):
            continue
        text = path.read_text(encoding="utf-8")
        for stale_path in STALE_GATE_SOURCE_CONTRACTS:
            assert stale_path not in text, (stale_path, path.relative_to(REPO_ROOT).as_posix())


def _read_toml(path: Path) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _matches_any_prefix(stem: str, prefixes: list[str]) -> bool:
    return any(stem == prefix or stem.startswith(f"{prefix}_") for prefix in prefixes)


def _ids_from_table(contract: dict[str, Any], table_name: str) -> set[str]:
    return {
        str(entry.get("id", "")).strip()
        for entry in contract.get(table_name, [])
        if str(entry.get("id", "")).strip()
    }
