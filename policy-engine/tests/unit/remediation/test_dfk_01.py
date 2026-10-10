from __future__ import annotations

import gzip
import hashlib
import importlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import polisyos.data_forge as data_forge
import polisyos.data_forge.kernel.schemas as canonical_schemas
from polisyos.data_forge.errors import SchemaCompatibilityError
from polisyos.data_forge.kernel.schemas import (
    CompatibilityMode,
    SchemaChangeKind,
    SchemaEvolutionRule,
    SchemaMigrationPlan,
    SchemaMigrationRegistry,
    SchemaRegistry,
    SchemaVersion,
    assert_schema_evolution_compatible,
    evaluate_schema_evolution,
)
from polisyos.data_forge.kernel.schemas.evolution import (
    SchemaEvolutionRule as EvolutionSchemaEvolutionRule,
)
from polisyos.data_forge.kernel.schemas.migrations import (
    SchemaMigrationPlan as MigrationSchemaMigrationPlan,
)
from polisyos.data_forge.kernel.schemas.migrations import (
    SchemaMigrationRegistry as MigrationSchemaMigrationRegistry,
)
from polisyos.data_forge.kernel.schemas.registry import (
    CompatibilityMode as RegistryCompatibilityMode,
)
from polisyos.data_forge.kernel.schemas.registry import SchemaRegistry as RegistrySchemaRegistry
from polisyos.data_forge.kernel.schemas.registry import SchemaVersion as RegistrySchemaVersion


def test_dfk_01_canonical_schema_exports_preserve_registry_identity() -> None:
    """The canonical Data Forge schema package remains the working owner."""
    assert canonical_schemas.CompatibilityMode is CompatibilityMode
    assert canonical_schemas.SchemaRegistry is SchemaRegistry
    assert canonical_schemas.SchemaVersion is SchemaVersion
    assert CompatibilityMode is RegistryCompatibilityMode
    assert SchemaRegistry is RegistrySchemaRegistry
    assert SchemaVersion is RegistrySchemaVersion
    assert SchemaEvolutionRule is EvolutionSchemaEvolutionRule
    assert SchemaMigrationPlan is MigrationSchemaMigrationPlan
    assert SchemaMigrationRegistry is MigrationSchemaMigrationRegistry
    assert data_forge.CompatibilityMode is CompatibilityMode
    assert data_forge.SchemaRegistry is SchemaRegistry
    assert data_forge.SchemaVersion is SchemaVersion


def test_dfk_01_canonical_registry_evolution_and_migration_behave() -> None:
    """Registry, evolution, and migration behavior survive legacy-surface retirement."""
    schema_id = "dfk.canonical"
    previous = SchemaVersion(
        schema_id=schema_id,
        version="1.0.0",
        compat_mode=CompatibilityMode.BACKWARD,
        json_schema={
            "type": "object",
            "properties": {"id": {"type": "string"}},
            "required": ["id"],
        },
    )
    candidate = SchemaVersion(
        schema_id=schema_id,
        version="2.0.0",
        compat_mode=CompatibilityMode.FULL,
        json_schema={
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "title": {"type": "string"},
            },
            "required": ["id", "title"],
        },
    )

    registry = SchemaRegistry()
    assert registry.register(previous) is previous
    assert registry.register(candidate) is candidate
    assert registry.get(schema_id, "1.0.0") is previous
    assert registry.latest(schema_id) is candidate
    assert registry.list_versions(schema_id) == (previous, candidate)

    breaking = evaluate_schema_evolution(previous, candidate)
    assert breaking.compatible is False
    assert breaking.changes[0].change_kind is SchemaChangeKind.ADD_REQUIRED_FIELD
    with pytest.raises(SchemaCompatibilityError):
        assert_schema_evolution_compatible(previous, candidate)

    rule = SchemaEvolutionRule(
        schema_id=schema_id,
        from_version="1.0.0",
        to_version="2.0.0",
        change_kind=SchemaChangeKind.ADD_REQUIRED_FIELD,
        rationale="the migration supplies title for existing payloads",
    )
    allowed = assert_schema_evolution_compatible(previous, candidate, rules=(rule,))
    assert allowed.compatible is True

    migrations = SchemaMigrationRegistry()
    plan = SchemaMigrationPlan(
        schema_id=schema_id,
        from_version="1.0.0",
        to_version="2.0.0",
        migration_id="dfk.add_title",
    )
    migrations.register(
        plan,
        lambda payload: {**payload, "title": "untitled"},
    )

    assert migrations.plan_path(
        schema_id=schema_id,
        from_version="1.0.0",
        to_version="2.0.0",
    ) == (plan,)
    assert migrations.apply(
        {"id": "record-1"},
        schema_id=schema_id,
        from_version="1.0.0",
        to_version="2.0.0",
    ) == {"id": "record-1", "title": "untitled"}


@pytest.mark.parametrize(
    "legacy_module",
    [
        "polisyos.data_forge.kernel.pipeline.schemas",
        "polisyos.data_forge.kernel.schemas.codegen",
        "polisyos.foundry.domain.schema",
    ],
)
def test_dfk_01_compatibility_pending_surfaces_remain_importable(legacy_module: str) -> None:
    """Keep unresolved public FQNs until census and an owner decision are complete."""
    module = importlib.import_module(legacy_module)
    assert module.__name__ == legacy_module


def test_dfk_01_compatibility_pending_surfaces_preserve_current_identity() -> None:
    """Pending surfaces retain their public and canonical identities for compatibility."""
    pipeline_schemas = importlib.import_module("polisyos.data_forge.kernel.pipeline.schemas")
    assert pipeline_schemas.CompatibilityMode is CompatibilityMode
    assert pipeline_schemas.SchemaRegistry is SchemaRegistry
    assert pipeline_schemas.SchemaVersion is SchemaVersion

    codegen = importlib.import_module("polisyos.data_forge.kernel.schemas.codegen")
    generated_schema_module = codegen.GeneratedSchemaModule
    assert generated_schema_module.__module__ == "polisyos.data_forge.kernel.schemas.codegen"
    assert set(generated_schema_module.model_fields) == {
        "module_name",
        "schema_id",
        "schema_version",
    }

    foundry_schema = importlib.import_module("polisyos.foundry.domain.schema")
    assert foundry_schema.AgentType.__module__ == "polisyos.foundry.domain.schema"
    assert foundry_schema.RegionProfile.__module__ == "polisyos.foundry.domain.schema"
    assert foundry_schema.SimulationConfig.__module__ == "polisyos.foundry.domain.schema"
    assert set(foundry_schema.RegionProfile.model_fields) == {
        "region_id",
        "avg_income",
        "unemployment_rate",
        "tech_level",
    }
    assert set(foundry_schema.SimulationConfig.model_fields) == {
        "n_agents",
        "n_steps",
        "seed",
    }


def test_dfk_01_mechanisms_tombstone_is_not_importable() -> None:
    """The confirmed empty mechanisms tombstone remains an absence contract."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("polisyos.foundry.domain.mechanisms")


REPO_ROOT = Path(__file__).resolve().parents[3]


def _init_census_repository(root: Path, files: dict[str, str | bytes]) -> None:
    """Create a small Git-visible repository for the census CLI's input contract."""
    subprocess.run(["git", "init", "--quiet"], cwd=root, check=True)
    subprocess.run(
        ["git", "config", "user.email", "dfk-test@example.invalid"], cwd=root, check=True
    )
    subprocess.run(["git", "config", "user.name", "DFK test"], cwd=root, check=True)
    for relative_path, content in files.items():
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
    subprocess.run(["git", "add", "--all"], cwd=root, check=True)
    subprocess.run(["git", "commit", "--quiet", "-m", "census fixture"], cwd=root, check=True)


def _run_census(
    root: Path, *, output_format: str = "text"
) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
    """Invoke the real census command and decode its JSON evidence receipt."""
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.cli",
            "validation",
            "schema-fqn-census",
            "--output-format",
            output_format,
            "--repo-root",
            str(root),
        ],
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHONPATH": os.pathsep.join((str(REPO_ROOT), str(REPO_ROOT / "src")))},
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.stdout.strip(), completed.stderr
    return completed, json.loads(completed.stdout)


def test_dfk_01_census_binds_imports_strings_dynamic_loaders_and_exclusions(
    tmp_path: Path,
) -> None:
    """The census reports exact local evidence and keeps ignored inputs outside its verdict."""
    files = {
        ".gitignore": "ignored/\n",
        "src/polisyos/foundry/domain/schema.py": "class RegionProfile: ...\n",
        "src/polisyos/foundry/domain/caller.py": (
            "from .schema import RegionProfile\n"
            "from importlib import import_module as load_module\n"
            "def load_unknown(name):\n"
            "    return load_module(name)\n"
            "def load_schema():\n"
            '    return load_module("polisyos.foundry.domain.schema")\n'
        ),
        "src/polisyos/data_forge/kernel/schemas/codegen.py": ("class GeneratedSchemaModule: ...\n"),
        "src/polisyos/data_forge/kernel/pipeline/schemas/__init__.py": (
            "from polisyos.data_forge.kernel.schemas import SchemaRegistry\n"
        ),
        "configs/legacy.json": (
            '{"module": "polisyos.foundry.domain.schema", '
            '"resource": "foundry/domain/schema.py", "symbol": "RegionProfile"}\n'
        ),
    }
    _init_census_repository(tmp_path, files)
    untracked = tmp_path / "generated" / "descriptor.json"
    untracked.parent.mkdir(parents=True)
    untracked.write_text(
        '{"module": "polisyos.data_forge.kernel.schemas.codegen"}\n', encoding="utf-8"
    )
    ignored = tmp_path / "ignored" / "outside.json"
    ignored.parent.mkdir()
    ignored.write_text('{"module": "polisyos.foundry.domain.mechanisms"}\n', encoding="utf-8")

    completed, receipt = _run_census(tmp_path)

    assert completed.returncode == 0
    assert receipt["schema"] == "polisyos.schema_fqn_census.v2"
    selection = receipt["selection"]
    assert selection["tracked_path_count"] == len(files)
    assert selection["untracked_paths"] == ["generated/descriptor.json"]
    assert selection["ignored_paths"] == ["ignored/outside.json"]
    assert any(
        item["class"] == "unselected_ignored_inputs" and item["status"] == "present"
        for item in receipt["unresolved_by_construction"]
    )

    matches = receipt["matches"]
    assert any(
        hit["target"] == "polisyos.foundry.domain.schema"
        and hit["path"] == "src/polisyos/foundry/domain/caller.py"
        and hit["evidence_kind"] == "relative_import"
        for hit in matches
    )
    assert any(
        hit["target"] == "polisyos.foundry.domain.schema"
        and hit["path"] == "configs/legacy.json"
        and hit["evidence_kind"] == "serialized_or_text_reference"
        for hit in matches
    )
    assert any(
        hit["target"] == "polisyos.foundry.domain.schema"
        and hit["path"] == "configs/legacy.json"
        and hit["evidence_kind"] == "resource_path_reference"
        for hit in matches
    )
    assert any(
        hit["target"] == "polisyos.data_forge.kernel.schemas.codegen"
        and hit["path"] == "generated/descriptor.json"
        for hit in matches
    )
    assert not any(hit["path"] == "ignored/outside.json" for hit in matches)

    dynamic_sites = receipt["dynamic_loader_sites"]
    assert any(
        site["path"] == "src/polisyos/foundry/domain/caller.py"
        and site["status"] == "unresolved_nonliteral_target"
        for site in dynamic_sites
    )
    assert any(
        site["literal_target"] == "polisyos.foundry.domain.schema"
        and site["status"] == "literal_target"
        for site in dynamic_sites
    )
    assert receipt["read_receipt"]["complete_verdict"] is True
    assert receipt["package_artifacts"]["wheel"] == "UNRUN"
    assert receipt["package_artifacts"]["sdist"] == "UNRUN"
    read_paths = {
        item["path"]
        for item in receipt["read_receipt"]["inputs"]
        if item["operation"] == "read_bytes" and item["status"] == "read"
    }
    assert read_paths == set(files) | {"generated/descriptor.json"}


def test_dfk_01_census_resolves_importfrom_package_children_and_removal(
    tmp_path: Path,
) -> None:
    """Package and module ImportFrom forms expose exact child-module candidates."""
    package_init = "src/polisyos/data_forge/kernel/schemas/__init__.py"
    nested_caller = "src/polisyos/data_forge/kernel/schemas/subpackage/caller.py"
    schema_package_init = "src/polisyos/foundry/domain/__init__.py"
    files = {
        package_init: (
            "from .codegen import GeneratedSchemaModule\n"
            "from . import codegen as relative_codegen\n"
            "from polisyos.data_forge.kernel.schemas import codegen as absolute_codegen\n"
        ),
        "src/polisyos/data_forge/kernel/schemas/codegen.py": ("class GeneratedSchemaModule: ...\n"),
        "src/polisyos/data_forge/kernel/schemas/subpackage/__init__.py": "",
        nested_caller: (
            "from .. import codegen as parent_codegen\n"
            "from ..codegen import GeneratedSchemaModule as parent_symbol\n"
        ),
        schema_package_init: "from . import schema as schema_module\n",
        "src/polisyos/foundry/domain/schema.py": "class RegionProfile: ...\n",
    }
    _init_census_repository(tmp_path, files)

    completed, receipt = _run_census(tmp_path)

    assert completed.returncode == 0
    imports = [
        hit
        for hit in receipt["matches"]
        if hit["evidence_kind"]
        in {
            "absolute_import",
            "relative_import",
            "absolute_import_child_candidate",
            "relative_import_child_candidate",
        }
    ]
    actual = {
        (
            hit["target"],
            hit["path"],
            hit["line"],
            hit["evidence_kind"],
            hit["matched_value"],
        )
        for hit in imports
    }
    child_candidates = [hit for hit in imports if hit["evidence_kind"].endswith("_child_candidate")]
    assert child_candidates
    assert {hit["resolution"] for hit in child_candidates} == {"child_module_or_package_attribute"}
    assert actual == {
        (
            "polisyos.data_forge.kernel.schemas.codegen",
            package_init,
            1,
            "relative_import",
            "polisyos.data_forge.kernel.schemas.codegen",
        ),
        (
            "polisyos.data_forge.kernel.schemas.codegen",
            package_init,
            2,
            "relative_import_child_candidate",
            "polisyos.data_forge.kernel.schemas.codegen",
        ),
        (
            "polisyos.data_forge.kernel.schemas.codegen",
            package_init,
            3,
            "absolute_import_child_candidate",
            "polisyos.data_forge.kernel.schemas.codegen",
        ),
        (
            "polisyos.data_forge.kernel.schemas.codegen",
            nested_caller,
            1,
            "relative_import_child_candidate",
            "polisyos.data_forge.kernel.schemas.codegen",
        ),
        (
            "polisyos.data_forge.kernel.schemas.codegen",
            nested_caller,
            2,
            "relative_import",
            "polisyos.data_forge.kernel.schemas.codegen",
        ),
        (
            "polisyos.foundry.domain.schema",
            schema_package_init,
            1,
            "relative_import_child_candidate",
            "polisyos.foundry.domain.schema",
        ),
    }

    (tmp_path / package_init).write_text("from math import sqrt\n", encoding="utf-8")
    (tmp_path / nested_caller).write_text("from math import floor\n", encoding="utf-8")
    (tmp_path / schema_package_init).write_text("from math import ceil\n", encoding="utf-8")
    corrupted, corrupted_receipt = _run_census(tmp_path)

    assert corrupted.returncode == 0
    assert not any(
        hit["evidence_kind"]
        in {
            "absolute_import",
            "relative_import",
            "absolute_import_child_candidate",
            "relative_import_child_candidate",
        }
        for hit in corrupted_receipt["matches"]
    )


def test_dfk_01_census_observes_module_and_package_source_variants(
    tmp_path: Path,
) -> None:
    """The census sees both module files and restored package trees as source candidates."""
    package_init = "src/polisyos/foundry/domain/mechanisms/__init__.py"
    module_file = "src/polisyos/foundry/domain/schema.py"
    codegen_package_init = "src/polisyos/data_forge/kernel/schemas/codegen/__init__.py"
    pipeline_package_init = "src/polisyos/data_forge/kernel/pipeline/schemas/__init__.py"
    config_path = "configs/mechanism-resource.toml"
    files = {
        "src/polisyos/__init__.py": "",
        "src/polisyos/foundry/__init__.py": "",
        "src/polisyos/foundry/domain/__init__.py": "",
        "src/polisyos/data_forge/kernel/schemas/__init__.py": "",
        "src/polisyos/data_forge/kernel/pipeline/__init__.py": "",
        codegen_package_init: "class GeneratedSchemaModule: ...\n",
        "src/polisyos/data_forge/kernel/schemas/codegen/resources/schema.json": (
            '{"type": "object"}\n'
        ),
        pipeline_package_init: "from polisyos.data_forge.kernel.schemas import SchemaRegistry\n",
        module_file: "class RegionProfile: ...\n",
        package_init: "class LegacyMechanismPackage: ...\n",
        "src/polisyos/foundry/domain/mechanisms/README.md": "restored package resource\n",
        config_path: (
            'module = "polisyos.foundry.domain.mechanisms"\n'
            'resource = "polisyos/foundry/domain/mechanisms/__init__.py"\n'
            'placeholder = "polisyos/data_forge/kernel/schemas/codegen/__init__.py"\n'
        ),
    }
    _init_census_repository(tmp_path, files)

    completed, receipt = _run_census(tmp_path)

    assert completed.returncode == 0
    assert receipt["schema"] == "polisyos.schema_fqn_census.v2"
    targets = {item["fqn"]: item for item in receipt["targets"]}
    foundry_schema_sources = targets["polisyos.foundry.domain.schema"]["source_candidates"]
    foundry_mechanisms_sources = targets["polisyos.foundry.domain.mechanisms"]["source_candidates"]
    assert foundry_schema_sources == [
        {
            "kind": "module_file",
            "relative_path": "foundry/domain/schema.py",
            "observed_paths": [module_file],
        },
        {
            "kind": "package_initializer",
            "relative_path": "foundry/domain/schema/__init__.py",
            "observed_paths": [],
        },
        {
            "kind": "package_resource_tree",
            "relative_path": "foundry/domain/schema/",
            "observed_paths": [],
        },
    ]
    assert foundry_mechanisms_sources == [
        {
            "kind": "module_file",
            "relative_path": "foundry/domain/mechanisms.py",
            "observed_paths": [],
        },
        {
            "kind": "package_initializer",
            "relative_path": "foundry/domain/mechanisms/__init__.py",
            "observed_paths": [package_init],
        },
        {
            "kind": "package_resource_tree",
            "relative_path": "foundry/domain/mechanisms/",
            "observed_paths": [
                "src/polisyos/foundry/domain/mechanisms/README.md",
                package_init,
            ],
        },
    ]
    codegen_sources = targets["polisyos.data_forge.kernel.schemas.codegen"]["source_candidates"]
    assert codegen_sources[0]["observed_paths"] == []
    assert codegen_sources[1]["observed_paths"] == [codegen_package_init]
    assert codegen_sources[2]["observed_paths"] == [
        codegen_package_init,
        "src/polisyos/data_forge/kernel/schemas/codegen/resources/schema.json",
    ]
    pipeline_sources = targets["polisyos.data_forge.kernel.pipeline.schemas"]["source_candidates"]
    assert pipeline_sources[1]["observed_paths"] == [pipeline_package_init]
    assert pipeline_sources[2]["observed_paths"] == [pipeline_package_init]
    assert any(
        hit["target"] == "polisyos.foundry.domain.mechanisms"
        and hit["path"] == config_path
        and hit["evidence_kind"] == "resource_path_reference"
        for hit in receipt["matches"]
    )
    assert any(
        hit["target"] == "polisyos.data_forge.kernel.schemas.codegen"
        and hit["path"] == config_path
        and hit["evidence_kind"] == "resource_path_reference"
        for hit in receipt["matches"]
    )

    negative_import_probe = subprocess.run(
        [
            sys.executable,
            "-c",
            "import importlib, pytest\n"
            "with pytest.raises(ModuleNotFoundError) as error:\n"
            "    importlib.import_module('polisyos.foundry.domain.mechanisms')\n"
            "assert error.value.name == 'polisyos.foundry.domain.mechanisms'\n",
        ],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(tmp_path / "src")},
        capture_output=True,
        text=True,
        check=False,
    )
    assert negative_import_probe.returncode == 1
    assert "DID NOT RAISE" in negative_import_probe.stderr

    missing_initializer = tmp_path / package_init
    preserved_initializer = missing_initializer.with_name(f"{missing_initializer.name}.preserved")
    initializer_bytes = missing_initializer.read_bytes()
    missing_initializer.rename(preserved_initializer)
    assert not missing_initializer.exists()
    assert preserved_initializer.read_bytes() == initializer_bytes
    missing, missing_receipt = _run_census(tmp_path)
    assert missing.returncode == 2
    assert missing_receipt["result"] == "partial_unreadable_input"
    missing_sources = {
        item["kind"]: item["observed_paths"]
        for item in {target["fqn"]: target for target in missing_receipt["targets"]}[
            "polisyos.foundry.domain.mechanisms"
        ]["source_candidates"]
    }
    assert missing_sources["package_initializer"] == []


def test_dfk_01_census_selects_repository_text_resource_and_config_types(
    tmp_path: Path,
) -> None:
    """The census includes tracked text formats beyond Python and common manifests."""
    files = {
        ".env.example": "LEGACY_MODULE=polisyos.foundry.domain.mechanisms\n",
        "owners.tsv": "finding\tfqn\nLA-027\tpolisyos.data_forge.kernel.pipeline.schemas\n",
        "policy.rego": 'package fixtures\nmodule := "polisyos.data_forge.kernel.schemas.codegen"\n',
        "runtime.log": "loaded polisyos.foundry.domain.schema\n",
        "styles.css": "/* resource foundry/domain/schema.py */\n",
        "template.tmpl": "module: polisyos.data_forge.kernel.schemas.codegen\n",
        "template.tpl": "module: polisyos.foundry.domain.schema\n",
        "change.patch": "+polisyos.foundry.domain.mechanisms\n",
        "query.cypher": "// polisyos.data_forge.kernel.pipeline.schemas\n",
        "sample.fixture": '{"module": "polisyos.foundry.domain.mechanisms"}\n',
        "snapshot.blob": '{"module": "polisyos.foundry.domain.schema"}\n',
        "Dockerfile.reproducible": "FROM python:3.14\n",
        "receipt.sha256": "0123456789abcdef  file\n",
        ".nvmrc": "22\n",
        ".yamllint": "extends: default\n",
        ".prettierignore": "dist\n",
        "LICENSE": "fixture license\n",
        "docs/OWNER": "maintained by the fixture\n",
        "docs/.gitkeep": "",
    }
    _init_census_repository(tmp_path, files)

    completed, receipt = _run_census(tmp_path)

    assert completed.returncode == 0
    selected_paths = set(receipt["selection"]["selected_paths"])
    assert set(files).issubset(selected_paths)
    matches = receipt["matches"]
    expected = {
        ".env.example": "polisyos.foundry.domain.mechanisms",
        "owners.tsv": "polisyos.data_forge.kernel.pipeline.schemas",
        "policy.rego": "polisyos.data_forge.kernel.schemas.codegen",
        "runtime.log": "polisyos.foundry.domain.schema",
        "styles.css": "polisyos.foundry.domain.schema",
        "template.tmpl": "polisyos.data_forge.kernel.schemas.codegen",
        "template.tpl": "polisyos.foundry.domain.schema",
        "change.patch": "polisyos.foundry.domain.mechanisms",
        "query.cypher": "polisyos.data_forge.kernel.pipeline.schemas",
        "sample.fixture": "polisyos.foundry.domain.mechanisms",
        "snapshot.blob": "polisyos.foundry.domain.schema",
    }
    for path, target in expected.items():
        assert any(hit["path"] == path and hit["target"] == target for hit in matches)
    assert any(
        hit["path"] == "styles.css" and hit["evidence_kind"] == "resource_path_reference"
        for hit in matches
    )
    read_paths = {
        item["path"]
        for item in receipt["read_receipt"]["inputs"]
        if item["operation"] == "read_bytes" and item["status"] == "read"
    }
    assert read_paths == set(files)


def test_dfk_01_census_does_not_turn_missing_tracked_input_into_zero(
    tmp_path: Path,
) -> None:
    """A tracked path that cannot be read keeps the census partial and names the path."""
    files = {"src/polisyos/foundry/domain/schema.py": "class RegionProfile: ...\n"}
    _init_census_repository(tmp_path, files)
    (tmp_path / "src/polisyos/foundry/domain/schema.py").unlink()

    completed, receipt = _run_census(tmp_path)

    assert completed.returncode == 2
    assert receipt["read_receipt"]["complete_verdict"] is False
    assert receipt["unreadable_paths"] == ["src/polisyos/foundry/domain/schema.py"]
    assert receipt["result"] == "partial_unreadable_input"


def test_dfk_01_census_rejects_selected_symlink_outside_admitted_root(
    tmp_path: Path,
) -> None:
    """A selected Git path cannot cause the census to read bytes outside its root."""
    files = {"configs/linked.json": '{"module": "placeholder"}\n'}
    census_root = tmp_path / "repo"
    census_root.mkdir()
    _init_census_repository(census_root, files)
    outside = tmp_path / "dfk_external_schema_fqn.json"
    outside.write_text('{"module": "polisyos.foundry.domain.schema"}\n', encoding="utf-8")
    linked = census_root / "configs/linked.json"
    linked.unlink()
    linked.symlink_to(outside)

    completed, receipt = _run_census(census_root)

    assert completed.returncode == 2
    assert receipt["result"] == "partial_unsupported_or_ambiguous"
    assert receipt["read_receipt"]["complete_verdict"] is False
    assert receipt["rejected_outside_root_paths"] == ["configs/linked.json"]
    assert receipt["unsupported_or_ambiguous_inputs"] == [
        {
            "path": "configs/linked.json",
            "class": "symlink_escapes_admitted_root",
            "detail": "The selected path resolves outside the census root and was not read.",
        }
    ]
    assert not any(hit["path"] == "configs/linked.json" for hit in receipt["matches"])


def test_dfk_01_census_digest_changes_when_a_selected_input_changes(tmp_path: Path) -> None:
    """The receipt binds working-tree bytes rather than a remembered path list."""
    files = {"configs/legacy.json": '{"module": "polisyos.foundry.domain.schema"}\n'}
    _init_census_repository(tmp_path, files)
    first_command, first = _run_census(tmp_path)
    config_path = tmp_path / "configs/legacy.json"
    config_path.write_text('{"module": "polisyos.data_forge.kernel.schemas.codegen"}\n')

    second_command, second = _run_census(tmp_path)

    assert first_command.returncode == second_command.returncode == 0

    def digest(receipt: dict[str, object]) -> str:
        inputs = receipt["read_receipt"]["inputs"]
        return next(
            item["sha256"]
            for item in inputs
            if item["path"] == "configs/legacy.json" and item["operation"] == "read_bytes"
        )

    assert digest(first) != digest(second)
    assert "configs/legacy.json" in second["selection"]["working_tree_changes"]
    assert not any(
        hit["target"] == "polisyos.foundry.domain.schema" and hit["path"] == "configs/legacy.json"
        for hit in second["matches"]
    )
    assert any(
        hit["target"] == "polisyos.data_forge.kernel.schemas.codegen"
        and hit["path"] == "configs/legacy.json"
        for hit in second["matches"]
    )


def test_dfk_01_census_normalizes_git_status_paths_from_nested_product_root(
    tmp_path: Path,
) -> None:
    """A product-root census maps Git's repository-prefixed status paths back to its root."""
    files = {"policy-engine/configs/legacy.json": '{"module": "old"}\n'}
    _init_census_repository(tmp_path, files)
    product_root = tmp_path / "policy-engine"
    (product_root / "configs/legacy.json").write_text('{"module": "new"}\n', encoding="utf-8")

    completed, receipt = _run_census(product_root)

    assert completed.returncode == 0
    assert receipt["selection"]["working_tree_changes"] == ["configs/legacy.json"]


def _changed_git_paths_oracle(root: Path) -> set[str]:
    """Derive changed names using independent index/worktree diff operations."""
    commands = (
        ["git", "diff", "--relative", "--name-only", "--no-renames", "-z", "--", "."],
        ["git", "diff", "--cached", "--relative", "--name-only", "--no-renames", "-z", "--", "."],
        ["git", "ls-files", "--others", "--exclude-standard", "-z", "--", "."],
    )
    paths: set[str] = set()
    for command in commands:
        output = subprocess.run(command, cwd=root, capture_output=True, check=True).stdout
        paths.update(os.fsdecode(name) for name in output.split(b"\0") if name)
    return paths


@pytest.mark.parametrize("status_mode", ["staged", "unstaged", "added_then_modified"])
@pytest.mark.parametrize("product_directory", ["", "policy-engine"])
def test_dfk_01_census_preserves_two_ordinary_git_status_records(
    tmp_path: Path, status_mode: str, product_directory: str
) -> None:
    """Each non-rename Git record contributes its own unquoted path."""
    prefix = f"{product_directory}/" if product_directory else ""
    relative_names = ("configs/01 path.json", "configs/02\nпуть.json")
    files = {f"{prefix}{name}": "{}\n" for name in relative_names}
    initial_files = (
        {f"{prefix}base.json": "{}\n"} if status_mode == "added_then_modified" else files
    )
    if product_directory:
        initial_files = {**initial_files, "outside.json": "{}\n"}
    _init_census_repository(tmp_path, initial_files)
    if status_mode == "added_then_modified":
        for name, content in files.items():
            path = tmp_path / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        subprocess.run(["git", "add", "--all"], cwd=tmp_path, check=True)
    for name in files:
        (tmp_path / name).write_text(
            '{"module": "polisyos.foundry.domain.schema"}\n', encoding="utf-8"
        )
    if status_mode == "staged":
        subprocess.run(["git", "add", "--all"], cwd=tmp_path, check=True)
    product_root = tmp_path / product_directory if product_directory else tmp_path
    if product_directory:
        (tmp_path / "outside.json").write_text('{"outside": true}\n', encoding="utf-8")

    completed, receipt = _run_census(product_root)

    assert completed.returncode == 0
    assert receipt["selection"]["working_tree_changes"] == sorted(relative_names)
    assert set(receipt["selection"]["working_tree_changes"]) == _changed_git_paths_oracle(
        product_root
    )
    selected_names = set(relative_names)
    if status_mode == "added_then_modified":
        selected_names.add("base.json")
    assert set(receipt["selection"]["selected_paths"]) == selected_names
    assert receipt["scanned_denominator"]["successful_byte_reads"] == len(selected_names)
    assert receipt["read_receipt"]["complete_verdict"] is True
    assert {hit["path"] for hit in receipt["matches"]} == set(relative_names)


@pytest.mark.parametrize("product_directory", ["", "policy-engine"])
@pytest.mark.parametrize("modify_destination", [False, True])
def test_dfk_01_census_preserves_both_rename_paths_and_next_record(
    tmp_path: Path, product_directory: str, modify_destination: bool
) -> None:
    """A real rename consumes exactly its source path, retaining the next record."""
    from tools.quality.validation.schema_fqn_census import _git_status_paths

    prefix = f"{product_directory}/" if product_directory else ""
    source_name = "configs/01 old.json"
    destination_name = "configs/02\nnew.json"
    sibling_name = "configs/03 sibling.json"
    files = {
        f"{prefix}{source_name}": '{"module": "polisyos.foundry.domain.schema"}\n',
        f"{prefix}{sibling_name}": "{}\n",
    }
    if product_directory:
        files = {**files, "outside.json": "{}\n"}
    _init_census_repository(tmp_path, files)
    subprocess.run(["git", "config", "status.renames", "true"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "mv", "--", f"{prefix}{source_name}", f"{prefix}{destination_name}"],
        cwd=tmp_path,
        check=True,
    )
    (tmp_path / f"{prefix}{sibling_name}").write_text(
        '{"module": "polisyos.data_forge.kernel.schemas.codegen"}\n', encoding="utf-8"
    )
    product_root = tmp_path / product_directory if product_directory else tmp_path
    if modify_destination:
        with (product_root / destination_name).open("a", encoding="utf-8") as stream:
            stream.write("\n")
    if product_directory:
        (tmp_path / "outside.json").write_text('{"outside": true}\n', encoding="utf-8")

    raw_status = subprocess.run(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    ).stdout
    expected_status = b"RM" if modify_destination else b"R "
    expected_rename = (
        expected_status
        + b" "
        + os.fsencode(prefix + destination_name)
        + b"\0"
        + os.fsencode(prefix + source_name)
        + b"\0"
    )
    assert expected_rename in raw_status

    changed_paths, status_receipt = _git_status_paths(product_root)
    completed, receipt = _run_census(product_root)

    assert status_receipt["returncode"] == status_receipt["prefix_returncode"] == 0
    assert changed_paths == sorted([source_name, destination_name, sibling_name])
    assert set(changed_paths) == _changed_git_paths_oracle(product_root)
    assert completed.returncode == 0
    assert receipt["selection"]["working_tree_changes"] == sorted([destination_name, sibling_name])
    assert set(receipt["selection"]["working_tree_changes"]) == (
        _changed_git_paths_oracle(product_root) & set(receipt["selection"]["selected_paths"])
    )
    assert set(receipt["selection"]["selected_paths"]) == {destination_name, sibling_name}
    assert receipt["scanned_denominator"]["successful_byte_reads"] == 2
    assert not any(hit["path"] == source_name for hit in receipt["matches"])
    assert {hit["path"] for hit in receipt["matches"]} == {destination_name, sibling_name}


@pytest.mark.parametrize("product_directory", ["", "policy-engine"])
def test_dfk_01_census_reports_clean_real_git_input(tmp_path: Path, product_directory: str) -> None:
    """Clean status leaves all declared selected files in the read denominator."""
    prefix = f"{product_directory}/" if product_directory else ""
    files = {
        f"{prefix}configs/01 path.json": "{}\n",
        f"{prefix}configs/02\nnext.json": "{}\n",
    }
    _init_census_repository(tmp_path, files)
    product_root = tmp_path / product_directory if product_directory else tmp_path

    completed, receipt = _run_census(product_root)

    assert completed.returncode == 0
    assert receipt["selection"]["working_tree_changes"] == []
    assert _changed_git_paths_oracle(product_root) == set()
    assert set(receipt["selection"]["selected_paths"]) == {
        name.removeprefix(prefix) for name in files
    }
    assert receipt["scanned_denominator"]["successful_byte_reads"] == len(files)
    assert receipt["read_receipt"]["complete_verdict"] is True


@pytest.mark.parametrize("product_directory", ["", "policy-engine"])
def test_dfk_01_census_preserves_both_copy_paths_and_next_record(
    tmp_path: Path, product_directory: str
) -> None:
    """A real copy consumes its source path and retains ordinary records after it."""
    from tools.quality.validation.schema_fqn_census import _git_status_paths

    prefix = f"{product_directory}/" if product_directory else ""
    source_name = "configs/01 source.json"
    destination_name = "configs/02\nкопия.json"
    sibling_name = "configs/03 sibling.json"
    source_content = (
        json.dumps(
            {
                "module": "polisyos.foundry.domain.schema",
                "values": [f"value-{index}" for index in range(100)],
            },
            indent=2,
        )
        + "\n"
    )
    files = {
        f"{prefix}{source_name}": source_content,
        f"{prefix}{sibling_name}": "{}\n",
    }
    if product_directory:
        files["outside.json"] = "{}\n"
    _init_census_repository(tmp_path, files)
    subprocess.run(["git", "config", "status.renames", "copies"], cwd=tmp_path, check=True)
    (tmp_path / f"{prefix}{destination_name}").write_text(source_content, encoding="utf-8")
    (tmp_path / f"{prefix}{source_name}").write_text(source_content + "\n", encoding="utf-8")
    (tmp_path / f"{prefix}{sibling_name}").write_text(
        '{"module": "polisyos.data_forge.kernel.schemas.codegen"}\n', encoding="utf-8"
    )
    subprocess.run(["git", "add", "--all"], cwd=tmp_path, check=True)
    product_root = tmp_path / product_directory if product_directory else tmp_path
    if product_directory:
        (tmp_path / "outside.json").write_text('{"outside": true}\n', encoding="utf-8")

    raw_status = subprocess.run(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    ).stdout
    expected_copy = (
        b"C  "
        + os.fsencode(prefix + destination_name)
        + b"\0"
        + os.fsencode(prefix + source_name)
        + b"\0"
    )
    assert expected_copy in raw_status

    changed_paths, status_receipt = _git_status_paths(product_root)
    completed, receipt = _run_census(product_root)
    expected_paths = {source_name, destination_name, sibling_name}

    assert status_receipt["returncode"] == status_receipt["prefix_returncode"] == 0
    assert set(changed_paths) == expected_paths == _changed_git_paths_oracle(product_root)
    assert completed.returncode == 0
    assert set(receipt["selection"]["working_tree_changes"]) == expected_paths
    assert set(receipt["selection"]["selected_paths"]) == expected_paths
    assert receipt["scanned_denominator"]["successful_byte_reads"] == len(expected_paths)
    assert {hit["path"] for hit in receipt["matches"]} == expected_paths


@pytest.mark.parametrize("product_directory", ["", "policy-engine"])
@pytest.mark.parametrize("operation", ["rename", "copy"])
def test_dfk_01_census_preserves_unstaged_two_path_intent_to_add(
    tmp_path: Path, product_directory: str, operation: str
) -> None:
    """An unstaged rename retains its missing tracked source as an unreadable input."""
    from tools.quality.validation.schema_fqn_census import _git_status_paths

    prefix = f"{product_directory}/" if product_directory else ""
    source_name = "configs/01 original\nфайл.txt"
    destination_name = "configs/02 copy space.txt"
    sibling_name = "configs/03 ordinary.txt"
    source_content = "".join(f"{index:04}: fixture discrimination line\n" for index in range(200))
    files = {f"{prefix}{source_name}": source_content, f"{prefix}{sibling_name}": "ordinary\n"}
    if product_directory:
        files["outside.txt"] = "outside\n"
    _init_census_repository(tmp_path, files)
    subprocess.run(["git", "config", "status.renames", "copies"], cwd=tmp_path, check=True)
    product_root = tmp_path / product_directory if product_directory else tmp_path
    source = product_root / source_name
    destination = product_root / destination_name
    if operation == "rename":
        source.rename(destination)
    else:
        destination.write_text(source_content, encoding="utf-8")
        source.write_text(source_content.replace("0000:", "edit:", 1), encoding="utf-8")
    (product_root / sibling_name).write_text("changed ordinary\n", encoding="utf-8")
    subprocess.run(["git", "add", "-N", "--", prefix + destination_name], cwd=tmp_path, check=True)
    if product_directory:
        (tmp_path / "outside.txt").write_text("changed outside\n", encoding="utf-8")
    raw_status = subprocess.run(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    ).stdout
    expected_status = b" R " if operation == "rename" else b" C "
    assert (
        expected_status
        + os.fsencode(prefix + destination_name)
        + b"\0"
        + os.fsencode(prefix + source_name)
        + b"\0"
    ) in raw_status
    changed_paths, status_receipt = _git_status_paths(product_root)
    expected_paths = {source_name, destination_name, sibling_name}
    assert status_receipt["returncode"] == status_receipt["prefix_returncode"] == 0
    assert set(changed_paths) == expected_paths == _changed_git_paths_oracle(product_root)
    completed, receipt = _run_census(product_root)
    assert set(receipt["selection"]["selected_paths"]) == expected_paths
    assert set(receipt["selection"]["working_tree_changes"]) == expected_paths
    if operation == "rename":
        assert completed.returncode == 2
        assert receipt["result"] == "partial_unreadable_input"
        assert receipt["unreadable_paths"] == [source_name]
        assert receipt["read_receipt"]["complete_verdict"] is False
        assert receipt["scanned_denominator"]["successful_byte_reads"] == 2
    else:
        assert completed.returncode == 0
        assert receipt["unreadable_paths"] == []
        assert receipt["scanned_denominator"]["successful_byte_reads"] == 3


@pytest.mark.parametrize("output_format", ["text", "json"])
def test_dfk_01_census_is_discovered_and_invoked_through_public_cli(
    tmp_path: Path, output_format: str
) -> None:
    """The registered command emits its complete JSON receipt in either boundary mode."""
    from tools.lib.runner import ToolStatus
    from tools.registry import TOOL_SPECS_BY_KEY

    spec = TOOL_SPECS_BY_KEY[("validation", "schema-fqn-census")]
    assert spec.module == "tools.quality.validation.schema_fqn_census"
    assert spec.callable_name == "main"
    assert spec.status is ToolStatus.ACTIVE
    _init_census_repository(
        tmp_path, {"inside.json": '{"module":"polisyos.foundry.domain.schema"}\n'}
    )
    completed, receipt = _run_census(tmp_path, output_format=output_format)
    assert completed.returncode == 0, completed.stderr
    assert receipt["selection"]["selected_paths"] == ["inside.json"]
    assert receipt["scanned_denominator"]["read_paths"] == ["inside.json"]
    assert receipt["read_receipt"]["complete_verdict"] is True
    assert receipt["interpretation_boundary"]["not_a_retirement_authorization"] is True
    assert {hit["path"] for hit in receipt["matches"]} == {"inside.json"}
    assert all("selected for retirement" not in target["role"] for target in receipt["targets"])


def test_dfk_01_cli_json_escapes_surrogate_filename_without_changing_value(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A filesystem-decoded surrogate remains valid JSON at the CLI boundary."""
    from tools.quality.validation import schema_fqn_census

    path = "bad_\udcff.json"
    monkeypatch.setattr(
        schema_fqn_census,
        "collect_census",
        lambda _root: ({"selection": {"selected_paths": [path]}}, 0),
    )

    assert schema_fqn_census.main(["--repo-root", "."]) == 0
    output = capsys.readouterr().out
    assert output.isascii()
    assert json.loads(output)["selection"]["selected_paths"] == [path]


def test_dfk_01_census_decodes_valid_junit_and_manifested_source_snapshot(
    tmp_path: Path,
) -> None:
    """Only typed archive records authorize the two supported source normalizations."""
    report_path = "reports/historical.junit.xml"
    excerpt_preimage_path = "docs/research/evidence/packet/acceptance-preimage.py"
    excerpt_path = "docs/research/evidence/packet/acceptance-postimage.py"
    report = (
        b"<testsuites><testsuite name='history'><system-out>"
        b"polisyos.foundry.domain.schema"
        b"</system-out></testsuite></testsuites>"
    )
    compressed_report = gzip.compress(report, mtime=0)
    excerpt = (
        b"    # archived source excerpt\n"
        b"    from polisyos.foundry.domain import schema\n"
        b"\n"
        b"    def refer_to_schema():\n"
        b"        return schema.RegionProfile\n"
    )
    excerpt_sha256 = hashlib.sha256(excerpt).hexdigest()
    excerpt_preimage = (
        b"    # archived source preimage\n"
        b"    from polisyos.foundry.domain import schema\n"
        b"\n"
        b"    def refer_to_schema():\n"
        b"        return schema.RegionProfile\n"
    )
    excerpt_preimage_sha256 = hashlib.sha256(excerpt_preimage).hexdigest()
    legacy_excerpt_path = "docs/research/evidence/legacy/acceptance-preimage.py"
    legacy_postimage_path = "docs/research/evidence/legacy/acceptance-postimage.py"
    legacy_excerpt = (
        b"    # original archived source excerpt\n"
        b"    from polisyos.foundry.domain import schema\n"
        b"\n"
        b"    def refer_to_schema():\n"
        b"        return schema.RegionProfile\n"
    )
    legacy_excerpt_sha256 = hashlib.sha256(legacy_excerpt).hexdigest()
    legacy_postimage = (
        b"    # original archived postimage source excerpt\n"
        b"    from polisyos.foundry.domain import schema\n"
        b"\n"
        b"    def refer_to_schema():\n"
        b"        return schema.RegionProfile\n"
    )
    legacy_postimage_sha256 = hashlib.sha256(legacy_postimage).hexdigest()
    manifest_path = "docs/research/evidence/packet/removal-manifest.json"
    legacy_manifest_path = "docs/research/evidence/legacy/acceptance-removal.json"
    removal_manifest = {
        "schema": "ORCH04-B114-matched-property-removal-v1",
        "changes": [
            {
                "method": "acceptance",
                "preimage": "/archive/packet/acceptance-preimage.py",
                "preimage_sha256": excerpt_preimage_sha256,
                "postimage": "/archive/packet/acceptance-postimage.py",
                "postimage_sha256": excerpt_sha256,
            }
        ],
    }
    manifest_bytes = json.dumps(removal_manifest).encode("utf-8")
    legacy_manifest = {
        "preimage_sha256": legacy_excerpt_sha256,
        "postimage_sha256": legacy_postimage_sha256,
        "actual_accepted": 0,
        "positive_expected_accepted": 8,
        "semantic_expected_failure": "accepted count differs",
        "source_files_changed": False,
        "qualification": "archived source-pair discriminator",
    }
    legacy_manifest_bytes = json.dumps(legacy_manifest).encode("utf-8")
    report_artifact_index = {
        "schema": "orch04.C11.B114.evidence-index.v1",
        "artifacts": [
            {
                "path": f"{tmp_path.name}/{excerpt_preimage_path}",
                "original_path": "/archive/packet/acceptance-preimage.py",
                "sha256": excerpt_preimage_sha256,
                "bytes": len(excerpt_preimage),
            },
            {
                "path": f"{tmp_path.name}/{excerpt_path}",
                "original_path": "/archive/packet/acceptance-postimage.py",
                "sha256": excerpt_sha256,
                "bytes": len(excerpt),
            },
            {
                "path": f"{tmp_path.name}/{manifest_path}",
                "original_path": "/archive/packet/removal-manifest.json",
                "sha256": hashlib.sha256(manifest_bytes).hexdigest(),
                "bytes": len(manifest_bytes),
            },
            {
                "path": f"{tmp_path.name}/{legacy_excerpt_path}",
                "original_path": "/archive/legacy/acceptance-preimage.py",
                "sha256": legacy_excerpt_sha256,
                "bytes": len(legacy_excerpt),
            },
            {
                "path": f"{tmp_path.name}/{legacy_postimage_path}",
                "original_path": "/archive/legacy/acceptance-postimage.py",
                "sha256": legacy_postimage_sha256,
                "bytes": len(legacy_postimage),
            },
            {
                "path": f"{tmp_path.name}/{legacy_manifest_path}",
                "original_path": "/archive/legacy/acceptance-removal.json",
                "sha256": hashlib.sha256(legacy_manifest_bytes).hexdigest(),
                "bytes": len(legacy_manifest_bytes),
            },
        ],
    }
    files: dict[str, str | bytes] = {
        "src/polisyos/foundry/domain/schema.py": "class RegionProfile: ...\n",
        report_path: compressed_report,
        excerpt_preimage_path: excerpt_preimage,
        excerpt_path: excerpt,
        legacy_excerpt_path: legacy_excerpt,
        legacy_postimage_path: legacy_postimage,
        "docs/research/evidence/artifact-index.json": json.dumps(report_artifact_index),
        manifest_path: manifest_bytes.decode("utf-8"),
        legacy_manifest_path: legacy_manifest_bytes.decode("utf-8"),
    }
    _init_census_repository(tmp_path, files)

    completed, receipt = _run_census(tmp_path)

    assert completed.returncode == 0, completed.stderr
    assert receipt["result"] == "complete_for_selected_local_text_inputs"
    assert any(
        hit["path"] == report_path
        and hit["evidence_kind"] == "serialized_or_text_reference"
        for hit in receipt["matches"]
    )
    excerpt_import = next(
        hit
        for hit in receipt["matches"]
        if hit["path"] == excerpt_path
        and hit["target"] == "polisyos.foundry.domain.schema"
    )
    assert excerpt_import["line"] == 2
    legacy_import = next(
        hit
        for hit in receipt["matches"]
        if hit["path"] == legacy_excerpt_path
        and hit["target"] == "polisyos.foundry.domain.schema"
    )
    assert legacy_import["line"] == 2
    assert receipt["source_normalizations"]["gzip_text_inputs"] == [
        {
            "path": report_path,
            "compression": "gzip",
            "raw_byte_count": len(compressed_report),
            "raw_sha256": hashlib.sha256(compressed_report).hexdigest(),
            "decoded_byte_count": len(report),
            "decoded_sha256": hashlib.sha256(report).hexdigest(),
        }
    ]
    normalization = receipt["source_normalizations"][
        "indented_evidence_python_excerpts"
    ]
    assert len(normalization) == 4
    normalization_by_path = {item["path"]: item for item in normalization}
    assert set(normalization_by_path) == {
        excerpt_preimage_path,
        excerpt_path,
        legacy_excerpt_path,
        legacy_postimage_path,
    }
    assert normalization_by_path[excerpt_path] == {
        "path": excerpt_path,
        "normalization": "textwrap.dedent",
        "reason": "content-bound archived source-pair record",
        "line_count": 5,
        "line_numbers_preserved": True,
        "column_offsets_preserved": False,
        "source_type": "content_bound_archived_source_snapshot",
        "pair_format": "ORCH04-B114-matched-property-removal-v1",
        "source_role": "postimage",
        "source_sha256": excerpt_sha256,
        "pair_members": [
            {
                "role": "preimage",
                "path": excerpt_preimage_path,
                "original_path": "/archive/packet/acceptance-preimage.py",
                "sha256": excerpt_preimage_sha256,
            },
            {
                "role": "postimage",
                "path": excerpt_path,
                "original_path": "/archive/packet/acceptance-postimage.py",
                "sha256": excerpt_sha256,
            },
        ],
        "source_manifest_path": manifest_path,
        "source_manifest_original_path": "/archive/packet/removal-manifest.json",
        "source_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "artifact_index_path": "docs/research/evidence/artifact-index.json",
        "artifact_index_sha256": hashlib.sha256(
            json.dumps(report_artifact_index).encode("utf-8")
        ).hexdigest(),
    }
    legacy_normalization = normalization_by_path[legacy_excerpt_path]
    assert legacy_normalization["source_role"] == "preimage"
    assert legacy_normalization["pair_format"] == "legacy-b114-paired-hash-record"
    assert legacy_normalization["source_sha256"] == legacy_excerpt_sha256
    assert legacy_normalization["pair_members"] == [
        {
            "role": "preimage",
            "path": legacy_excerpt_path,
            "original_path": "/archive/legacy/acceptance-preimage.py",
            "sha256": legacy_excerpt_sha256,
        },
        {
            "role": "postimage",
            "path": legacy_postimage_path,
            "original_path": "/archive/legacy/acceptance-postimage.py",
            "sha256": legacy_postimage_sha256,
        },
    ]
    assert legacy_normalization["source_manifest_path"] == legacy_manifest_path
    assert legacy_normalization["source_manifest_original_path"] == (
        "/archive/legacy/acceptance-removal.json"
    )
    assert (
        legacy_normalization["source_manifest_sha256"]
        == hashlib.sha256(legacy_manifest_bytes).hexdigest()
    )
    assert legacy_normalization["artifact_index_path"] == (
        "docs/research/evidence/artifact-index.json"
    )
    assert legacy_normalization["line_numbers_preserved"] is True
    assert legacy_normalization["column_offsets_preserved"] is False
    read_paths = {
        item["path"]
        for item in receipt["read_receipt"]["inputs"]
        if item.get("operation") == "read_bytes" and item.get("status") == "read"
    }
    assert read_paths == set(receipt["selection"]["selected_paths"])
    assert receipt["read_receipt"]["complete_verdict"] is True


def test_dfk_01_census_rejects_untyped_compressed_and_python_archive_inputs(
    tmp_path: Path,
) -> None:
    """Compression and path markers cannot make malformed or runtime source complete."""
    runtime_source_path = "src/polisyos/evidence/broken.preimage.py"
    runtime_postimage_path = "src/polisyos/evidence/broken.postimage.py"
    runtime_source = "    from polisyos.foundry.domain import schema\n"
    runtime_source_sha256 = hashlib.sha256(runtime_source.encode("utf-8")).hexdigest()
    runtime_postimage = "    from polisyos.foundry.domain import schema\n"
    runtime_postimage_sha256 = hashlib.sha256(
        runtime_postimage.encode("utf-8")
    ).hexdigest()
    runtime_manifest_path = "src/polisyos/evidence/removal-manifest.json"
    runtime_manifest = {
        "schema": "ORCH04-B114-matched-property-removal-v1",
        "changes": [
            {
                "preimage": "/archive/broken.preimage.py",
                "preimage_sha256": runtime_source_sha256,
                "postimage": "/archive/broken.postimage.py",
                "postimage_sha256": runtime_postimage_sha256,
            }
        ],
    }
    runtime_manifest_bytes = json.dumps(runtime_manifest).encode("utf-8")
    runtime_index = {
        "schema": "orch04.C11.B114.evidence-index.v1",
        "artifacts": [
            {
                "path": f"{tmp_path.name}/{runtime_source_path}",
                "sha256": runtime_source_sha256,
                "bytes": len(runtime_source.encode("utf-8")),
                "original_path": "/archive/broken.preimage.py",
            },
            {
                "path": f"{tmp_path.name}/{runtime_postimage_path}",
                "sha256": runtime_postimage_sha256,
                "bytes": len(runtime_postimage.encode("utf-8")),
                "original_path": "/archive/broken.postimage.py",
            },
            {
                "path": f"{tmp_path.name}/{runtime_manifest_path}",
                "sha256": hashlib.sha256(runtime_manifest_bytes).hexdigest(),
                "bytes": len(runtime_manifest_bytes),
                "original_path": "/archive/broken/removal-manifest.json",
            },
        ],
    }
    stale_source_path = "docs/research/evidence/packet/stale.preimage.py"
    stale_source = "    from polisyos.foundry.domain import schema\n"
    stale_source_sha256 = hashlib.sha256(stale_source.encode("utf-8")).hexdigest()
    stale_manifest_path = "docs/research/evidence/packet/removal-manifest.json"
    stale_manifest = {
        "schema": "ORCH04-B114-matched-property-removal-v1",
        "changes": [
            {
                "preimage": "/archive/stale.preimage.py",
                "preimage_sha256": "0" * 64,
                "postimage": "/archive/stale.postimage.py",
                "postimage_sha256": "1" * 64,
            }
        ],
    }
    stale_manifest_bytes = json.dumps(stale_manifest).encode("utf-8")
    document_index = {
        "schema": "orch04.C11.B114.evidence-index.v1",
        "artifacts": [
            {
                "path": f"{tmp_path.name}/{stale_source_path}",
                "sha256": stale_source_sha256,
                "bytes": len(stale_source.encode("utf-8")),
            },
            {
                "path": f"{tmp_path.name}/{stale_manifest_path}",
                "sha256": hashlib.sha256(stale_manifest_bytes).hexdigest(),
                "bytes": len(stale_manifest_bytes),
            },
        ],
    }
    files: dict[str, str | bytes] = {
        "reports/corrupt.junit.xml": b"\x1f\x8bnot-a-gzip-stream",
        "reports/malformed.junit.xml": gzip.compress(
            b"<testsuites><testsuite>", mtime=0
        ),
        "reports/non-utf8.junit.xml": gzip.compress(b"\xff", mtime=0),
        "reports/non-junit.junit.xml": gzip.compress(b"<not-junit/>", mtime=0),
        "reports/compressed.xml": gzip.compress(b"<testsuites/>", mtime=0),
        runtime_source_path: runtime_source,
        runtime_postimage_path: runtime_postimage,
        "src/polisyos/evidence/artifact-index.json": json.dumps(runtime_index),
        runtime_manifest_path: runtime_manifest_bytes.decode("utf-8"),
        stale_source_path: stale_source,
        stale_manifest_path: stale_manifest_bytes.decode("utf-8"),
        "src/polisyos/foundry/domain/broken.py": "    def broken(:\n",
    }
    pair_cases = {}

    def add_versioned_pair_control(
        name: str,
        *,
        schema: str,
        include_postimage: bool,
        corrupt_postimage: bool = False,
    ) -> None:
        directory = f"docs/research/evidence/{name}"
        preimage_path = f"{directory}/sample.preimage.py"
        postimage_path = f"{directory}/sample.postimage.py"
        manifest_path = f"{directory}/removal-manifest.json"
        preimage = b"    from polisyos.foundry.domain import schema\n"
        expected_postimage = b"    from polisyos.foundry.domain import schema\n"
        actual_postimage = (
            b"    from polisyos.foundry.domain import schemb\n"
            if corrupt_postimage
            else expected_postimage
        )
        manifest = {
            "schema": schema,
            "changes": [
                {
                    "method": "sample",
                    "preimage": f"/archive/{name}/sample.preimage.py",
                    "preimage_sha256": hashlib.sha256(preimage).hexdigest(),
                    "postimage": f"/archive/{name}/sample.postimage.py",
                    "postimage_sha256": hashlib.sha256(expected_postimage).hexdigest(),
                }
            ],
        }
        manifest_bytes = json.dumps(manifest).encode("utf-8")
        files[preimage_path] = preimage
        if include_postimage:
            files[postimage_path] = actual_postimage
        files[manifest_path] = manifest_bytes.decode("utf-8")
        document_index["artifacts"].extend(
            [
                {
                    "path": f"{tmp_path.name}/{preimage_path}",
                    "sha256": hashlib.sha256(preimage).hexdigest(),
                    "bytes": len(preimage),
                    "original_path": f"/archive/{name}/sample.preimage.py",
                },
                {
                    "path": f"{tmp_path.name}/{postimage_path}",
                    "sha256": hashlib.sha256(expected_postimage).hexdigest(),
                    "bytes": len(expected_postimage),
                    "original_path": f"/archive/{name}/sample.postimage.py",
                },
                {
                    "path": f"{tmp_path.name}/{manifest_path}",
                    "original_path": f"/archive/{name}/removal-manifest.json",
                    "sha256": hashlib.sha256(manifest_bytes).hexdigest(),
                    "bytes": len(manifest_bytes),
                },
            ]
        )
        pair_cases[name] = {
            "preimage_path": preimage_path,
            "preimage_sha256": hashlib.sha256(preimage).hexdigest(),
            "postimage_path": postimage_path,
            "postimage_sha256": hashlib.sha256(expected_postimage).hexdigest(),
            "manifest_path": manifest_path,
            "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
            "preimage_original_path": f"/archive/{name}/sample.preimage.py",
            "postimage_original_path": f"/archive/{name}/sample.postimage.py",
            "manifest_original_path": f"/archive/{name}/removal-manifest.json",
            "include_postimage": include_postimage,
            "corrupt_postimage": corrupt_postimage,
            "actual_postimage": actual_postimage,
        }

    add_versioned_pair_control(
        "missing-mate",
        schema="ORCH04-B114-matched-property-removal-v1",
        include_postimage=False,
    )
    add_versioned_pair_control(
        "corrupt-mate",
        schema="ORCH04-B114-matched-property-removal-v1",
        include_postimage=True,
        corrupt_postimage=True,
    )
    add_versioned_pair_control(
        "unknown-schema",
        schema="ORCH04-B114-matched-property-removal-v999",
        include_postimage=True,
    )
    files["docs/research/evidence/artifact-index.json"] = json.dumps(document_index)
    artifact_entries = {entry["path"]: entry for entry in document_index["artifacts"]}
    for case in pair_cases.values():
        current_entry = artifact_entries[f"{tmp_path.name}/{case['preimage_path']}"]
        mate_entry = artifact_entries[f"{tmp_path.name}/{case['postimage_path']}"]
        manifest_entry = artifact_entries[f"{tmp_path.name}/{case['manifest_path']}"]
        assert current_entry["sha256"] == case["preimage_sha256"]
        assert current_entry["original_path"] == case["preimage_original_path"]
        assert mate_entry["sha256"] == case["postimage_sha256"]
        assert mate_entry["original_path"] == case["postimage_original_path"]
        assert manifest_entry["sha256"] == case["manifest_sha256"]
        assert manifest_entry["original_path"] == case["manifest_original_path"]
    corrupt_case = pair_cases["corrupt-mate"]
    assert (
        hashlib.sha256(corrupt_case["actual_postimage"]).hexdigest()
        != (corrupt_case["postimage_sha256"])
    )
    _init_census_repository(tmp_path, files)

    completed, receipt = _run_census(tmp_path)

    assert completed.returncode == 2
    assert receipt["result"] == "partial_unsupported_or_ambiguous"
    unsupported = receipt["unsupported_or_ambiguous_inputs"]
    assert any(
        item["path"] == "reports/corrupt.junit.xml"
        and item["class"] == "invalid_gzip_text"
        for item in unsupported
    )
    assert any(
        item["path"] == "reports/malformed.junit.xml"
        and item["class"] == "invalid_compressed_junit_xml"
        for item in unsupported
    )
    assert any(
        item["path"] == "reports/non-utf8.junit.xml"
        and item["class"] == "invalid_compressed_junit_xml"
        for item in unsupported
    )
    assert any(
        item["path"] == "reports/non-junit.junit.xml"
        and item["class"] == "invalid_compressed_junit_xml"
        for item in unsupported
    )
    assert any(
        item["path"] == "reports/compressed.xml"
        and item["class"] == "compressed_text_wrong_suffix"
        for item in unsupported
    )
    syntax_details = [
        item["detail"]
        for item in unsupported
        if item["class"] == "unsupported_syntax_or_ast"
    ]
    assert any(runtime_source_path in detail for detail in syntax_details)
    assert any(runtime_postimage_path in detail for detail in syntax_details)
    assert any(stale_source_path in detail for detail in syntax_details)
    for case in pair_cases.values():
        assert any(case["preimage_path"] in detail for detail in syntax_details)
    selected_paths = set(receipt["selection"]["selected_paths"])
    assert pair_cases["missing-mate"]["postimage_path"] not in selected_paths
    assert pair_cases["corrupt-mate"]["postimage_path"] in selected_paths
    read_paths = {
        item["path"]
        for item in receipt["read_receipt"]["inputs"]
        if item.get("operation") == "read_bytes" and item.get("status") == "read"
    }
    assert read_paths == selected_paths
    assert pair_cases["missing-mate"]["postimage_path"] not in read_paths
    assert pair_cases["corrupt-mate"]["postimage_path"] in read_paths
    assert any(
        "src/polisyos/foundry/domain/broken.py" in detail for detail in syntax_details
    )
    assert receipt["source_normalizations"]["gzip_text_inputs"] == []
    assert receipt["source_normalizations"]["indented_evidence_python_excerpts"] == []


def test_dfk_01_census_rejects_gzip_junit_above_expansion_limit(
    tmp_path: Path,
) -> None:
    """Oversized gzip input stays partial while a bounded JUnit report is consumed."""
    from tools.quality.validation import schema_fqn_census

    maximum = schema_fqn_census._MAX_GZIP_TEXT_BYTES
    assert maximum == 64 * 1024 * 1024
    prefix, suffix = b"<testsuites>", b"</testsuites>"
    remaining = maximum + 1 - len(prefix) - len(suffix)
    compressed_overflow = io.BytesIO()
    chunk = b" " * (64 * 1024)
    with gzip.GzipFile(fileobj=compressed_overflow, mode="wb", mtime=0) as stream:
        stream.write(prefix)
        while remaining:
            piece = chunk[: min(len(chunk), remaining)]
            stream.write(piece)
            remaining -= len(piece)
        stream.write(suffix)
    overflow_bytes = compressed_overflow.getvalue()
    assert len(overflow_bytes) < 1024 * 1024

    within_limit_path = "reports/within-limit.junit.xml"
    overflow_path = "reports/above-limit.junit.xml"
    decoded_report = (
        b"<testsuites><testsuite><system-out>"
        b"polisyos.foundry.domain.schema"
        b"</system-out></testsuite></testsuites>"
    )
    within_limit_bytes = gzip.compress(decoded_report, mtime=0)
    files: dict[str, str | bytes] = {
        overflow_path: overflow_bytes,
        within_limit_path: within_limit_bytes,
    }
    _init_census_repository(tmp_path, files)

    completed, receipt = _run_census(tmp_path)

    assert completed.returncode == 2
    assert receipt["result"] == "partial_unsupported_or_ambiguous"
    assert receipt["selection"]["selected_paths"] == sorted(files)
    overflow_findings = [
        item for item in receipt["unsupported_or_ambiguous_inputs"] if item["path"] == overflow_path
    ]
    assert len(overflow_findings) == 1
    assert overflow_findings[0]["class"] == "gzip_text_expansion_limit"
    assert "67108864 bytes" in overflow_findings[0]["detail"]

    read_inputs = {
        item["path"]: item
        for item in receipt["read_receipt"]["inputs"]
        if item.get("operation") == "read_bytes" and item.get("status") == "read"
    }
    assert set(read_inputs) == set(files)
    assert read_inputs[overflow_path]["bytes"] == len(overflow_bytes)
    assert read_inputs[overflow_path]["sha256"] == hashlib.sha256(overflow_bytes).hexdigest()
    assert read_inputs[within_limit_path]["bytes"] == len(within_limit_bytes)
    assert (
        read_inputs[within_limit_path]["sha256"] == hashlib.sha256(within_limit_bytes).hexdigest()
    )
    assert receipt["read_receipt"]["complete_verdict"] is True
    assert receipt["scanned_denominator"]["successful_byte_reads"] == len(files)

    expected_normalization = {
        "path": within_limit_path,
        "compression": "gzip",
        "raw_byte_count": len(within_limit_bytes),
        "raw_sha256": hashlib.sha256(within_limit_bytes).hexdigest(),
        "decoded_byte_count": len(decoded_report),
        "decoded_sha256": hashlib.sha256(decoded_report).hexdigest(),
    }
    assert receipt["source_normalizations"]["gzip_text_inputs"] == [expected_normalization]
    assert overflow_path not in {
        item["path"] for item in receipt["source_normalizations"]["gzip_text_inputs"]
    }
    assert receipt["source_normalizations"]["indented_evidence_python_excerpts"] == []
    assert any(
        hit["path"] == within_limit_path
        and hit["target"] == "polisyos.foundry.domain.schema"
        and hit["evidence_kind"] == "serialized_or_text_reference"
        for hit in receipt["matches"]
    )
