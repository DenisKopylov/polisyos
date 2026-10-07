from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

import jax.numpy as jnp
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
from polisyos.foundry.agent_sim.executor import PureExecutor
from polisyos.foundry.agent_sim.mechanisms import TaxationMechanism
from polisyos.foundry.agent_sim.state import GlobalState

REPO_ROOT = Path(__file__).resolve().parents[3]
CENSUS_SCRIPT = REPO_ROOT / "tools/quality/validation/schema_fqn_census.py"


def _init_census_repository(root: Path, files: dict[str, str]) -> None:
    """Create a small Git-visible repository for the census CLI's input contract."""
    subprocess.run(["git", "init", "--quiet"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "dfk-test@example.invalid"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "DFK test"], cwd=root, check=True)
    for relative_path, content in files.items():
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    subprocess.run(["git", "add", "--all"], cwd=root, check=True)
    subprocess.run(["git", "commit", "--quiet", "-m", "census fixture"], cwd=root, check=True)


def _run_census(root: Path) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
    """Invoke the real census command and decode its JSON evidence receipt."""
    completed = subprocess.run(
        [sys.executable, str(CENSUS_SCRIPT), "--repo-root", str(root)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.stdout.strip(), completed.stderr
    return completed, json.loads(completed.stdout)


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


def test_dfk_01_pipeline_schema_alias_preserves_canonical_identity() -> None:
    """The compatibility alias re-exports the canonical schema objects unchanged."""
    pipeline_schemas = importlib.import_module("polisyos.data_forge.kernel.pipeline.schemas")
    assert pipeline_schemas.CompatibilityMode is CompatibilityMode
    assert pipeline_schemas.SchemaRegistry is SchemaRegistry
    assert pipeline_schemas.SchemaVersion is SchemaVersion


@pytest.mark.parametrize(
    ("retired_module", "package_name", "resource_names", "source_paths"),
    [
        (
            "polisyos.foundry.domain.schema",
            "polisyos.foundry.domain",
            ("schema.py", "schema"),
            (
                REPO_ROOT / "src/polisyos/foundry/domain/schema.py",
                REPO_ROOT / "src/polisyos/foundry/domain/schema/__init__.py",
            ),
        ),
        (
            "polisyos.data_forge.kernel.schemas.codegen",
            "polisyos.data_forge.kernel.schemas",
            ("codegen.py", "codegen"),
            (
                REPO_ROOT / "src/polisyos/data_forge/kernel/schemas/codegen.py",
                REPO_ROOT / "src/polisyos/data_forge/kernel/schemas/codegen/__init__.py",
            ),
        ),
    ],
)
def test_dfk_01_retired_schema_fqns_and_resources_are_absent(
    retired_module: str,
    package_name: str,
    resource_names: tuple[str, str],
    source_paths: tuple[Path, Path],
) -> None:
    """Retired compatibility modules stay absent at import, package, and source levels."""
    from importlib import resources

    with pytest.raises(ModuleNotFoundError) as error:
        importlib.import_module(retired_module)
    assert error.value.name == retired_module

    package = importlib.import_module(package_name)
    for resource_name in resource_names:
        resource = resources.files(package).joinpath(resource_name)
        assert not resource.exists()
        assert not resource.is_dir()
    assert all(not source_path.exists() for source_path in source_paths)


def test_dfk_01_foundry_plugin_simulation_config_remains_canonical() -> None:
    """The real Foundry plugin configuration API remains available at its owner path."""
    from dataclasses import is_dataclass

    plugin_api = importlib.import_module("polisyos.foundry.plugins.api")
    simulation_config = plugin_api.SimulationConfig

    assert simulation_config.__module__ == "polisyos.foundry.plugins.api"
    assert is_dataclass(simulation_config)
    assert simulation_config(n_steps=3).n_steps == 3


def test_dfk_01_mechanisms_tombstone_is_not_importable() -> None:
    """The exact banned FQN and source-package resource remain absent."""
    from importlib import resources

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("polisyos.foundry.domain.mechanisms")

    package = importlib.import_module("polisyos.foundry.domain")
    resource = resources.files(package).joinpath("mechanisms")
    assert not resource.exists()
    assert not resource.is_dir()
    assert not resource.joinpath("__init__.py").is_file()

    source_path = REPO_ROOT / "src/polisyos/foundry/domain/mechanisms"
    assert not source_path.exists()


def test_dfk_01_canonical_foundry_mechanism_registry_resolves_and_dispatches() -> None:
    """The full runtime-ID fixture resolves at the canonical runner and emits its patch."""
    from polisyos.foundry._registry import MECHANISM_REGISTRY, get_mechanism_descriptor
    from polisyos.foundry.contracts.state import GlobalState as RuntimeGlobalState
    from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
    from polisyos.foundry.methods.catalog import ensure_all_methods_registered
    from polisyos.foundry.methods.registry import MethodRegistry

    expected = {
        "adaptive_agent": (
            "mechanism.runtime.adaptive_agent@1.0.0",
            "polisyos.foundry.agent_sim.agents:AdaptiveAgentMechanism",
        ),
        "income_tax": (
            "mechanism.runtime.income_tax@1.0.0",
            "polisyos.foundry.execute.mechanisms:IncomeTax",
        ),
        "labor_market": (
            "mechanism.runtime.labor_market@1.0.0",
            "polisyos.foundry.execute.mechanisms:LaborMarketMechanism",
        ),
        "queue": (
            "mechanism.runtime.queue@1.0.0",
            "polisyos.foundry.execute.queue:QueueMechanism",
        ),
        "tax_subsidy": (
            "mechanism.runtime.tax_subsidy@1.0.0",
            "polisyos.foundry.execute.mechanisms:TaxSubsidy",
        ),
    }
    ensure_all_methods_registered()
    assert set(MECHANISM_REGISTRY) == set(expected)

    method_registry = MethodRegistry.get_instance()
    for mechanism_id, (method_fqn, class_path) in expected.items():
        descriptor = get_mechanism_descriptor(mechanism_id)
        assert descriptor.mechanism_type == mechanism_id
        assert descriptor.method_fqn == method_fqn
        assert descriptor.mechanism_class_path == class_path
        resolved_class = descriptor.mechanism_class
        module_name, class_name = class_path.split(":")
        expected_class = getattr(importlib.import_module(module_name), class_name)
        assert resolved_class is expected_class

        method_class = method_registry.get(method_fqn)
        assert method_class.runtime_mechanism_type == mechanism_id
        assert method_class.runtime_mechanism_class_path == class_path

    state = RuntimeGlobalState.empty(3, 2)
    agents = state.agents.replace(
        income=jnp.asarray([100.0, 100.0, 100.0], dtype=jnp.float32),
        reported_income=jnp.asarray([100.0, 100.0, 100.0], dtype=jnp.float32),
        active=jnp.asarray([True, True, False]),
    )
    state = state.replace(agents=agents)
    income_tax_method = method_registry.get(expected["income_tax"][0])
    result = MethodDispatcher.get_instance().dispatch(
        method_class=income_tax_method,
        signature=income_tax_method.signature,
        state=state,
        params={"rate": 0.2},
        seed=11,
    )

    delta = result.output["result"]["patches"]["agents.income"][0]["delta"]
    assert delta == pytest.approx([-20.0, -20.0, 0.0])
    assert result.output["result"]["mechanism_type"] == "income_tax"


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
        "src/polisyos/data_forge/kernel/schemas/codegen.py": (
            "class GeneratedSchemaModule: ...\n"
        ),
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
    ignored.write_text(
        '{"module": "polisyos.foundry.domain.mechanisms"}\n', encoding="utf-8"
    )

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
        "src/polisyos/data_forge/kernel/schemas/codegen.py": (
            "class GeneratedSchemaModule: ...\n"
        ),
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
        if hit["evidence_kind"] in {
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
    child_candidates = [
        hit for hit in imports if hit["evidence_kind"].endswith("_child_candidate")
    ]
    assert child_candidates
    assert {
        hit["resolution"] for hit in child_candidates
    } == {"child_module_or_package_attribute"}
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
    codegen_package_init = (
        "src/polisyos/data_forge/kernel/schemas/codegen/__init__.py"
    )
    pipeline_package_init = (
        "src/polisyos/data_forge/kernel/pipeline/schemas/__init__.py"
    )
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
    codegen_sources = targets["polisyos.data_forge.kernel.schemas.codegen"][
        "source_candidates"
    ]
    assert codegen_sources[0]["observed_paths"] == []
    assert codegen_sources[1]["observed_paths"] == [codegen_package_init]
    assert codegen_sources[2]["observed_paths"] == [
        codegen_package_init,
        "src/polisyos/data_forge/kernel/schemas/codegen/resources/schema.json",
    ]
    pipeline_sources = targets["polisyos.data_forge.kernel.pipeline.schemas"][
        "source_candidates"
    ]
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
    preserved_initializer = missing_initializer.with_name(
        f"{missing_initializer.name}.preserved"
    )
    initializer_bytes = missing_initializer.read_bytes()
    missing_initializer.rename(preserved_initializer)
    assert not missing_initializer.exists()
    assert preserved_initializer.read_bytes() == initializer_bytes
    missing, missing_receipt = _run_census(tmp_path)
    assert missing.returncode == 2
    assert missing_receipt["result"] == "partial_unreadable_input"
    missing_sources = {
        item["kind"]: item["observed_paths"]
        for item in {
            target["fqn"]: target for target in missing_receipt["targets"]
        }["polisyos.foundry.domain.mechanisms"]["source_candidates"]
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
    outside.write_text(
        '{"module": "polisyos.foundry.domain.schema"}\n', encoding="utf-8"
    )
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
        hit["target"] == "polisyos.foundry.domain.schema"
        and hit["path"] == "configs/legacy.json"
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


def test_dfk_01_real_foundry_runner_executes_canonical_mechanism() -> None:
    """PureExecutor consumes the canonical taxation mechanism and returns its state effect."""
    state = GlobalState.empty(n_agents=2, seed=42, max_agents=2)
    state = state.replace(
        agents=state.agents.replace(income=jnp.asarray([100.0, 200.0], dtype=jnp.float32)),
        policy=state.policy.replace(tax_rate=jnp.asarray(0.1, dtype=jnp.float32)),
    )
    runner = PureExecutor([TaxationMechanism(progressive_factor=0.0)])

    final_state, metrics = runner.run(state, n_steps=1)

    assert final_state.agents.income[:2].tolist() == pytest.approx([90.0, 180.0])
    assert float(metrics["taxation/total_tax_collected"][0]) == pytest.approx(30.0)
    assert int(final_state.time_step) == 1
