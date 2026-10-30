"""Behavioral tests for the operationally selected migration route."""

from __future__ import annotations

import concurrent.futures
import json
import sys
import threading
from pathlib import Path
from typing import Any

import pytest

from tools.ops_runners.migrations import contracts, migrate

pytestmark = pytest.mark.unit
PRODUCT_ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("artifact", ["policy_ir", "dataset_manifest", "run_manifest"])
def test_cli_executes_contract_selected_callable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, artifact: str
) -> None:
    """The executable route follows a changed binding, including its selected arguments."""
    from polisyos.fabric.identity import migrations as fabric_migrations
    from polisyos.ir import migrations as ir_migrations
    from polisyos.runtime import manifest_migrations

    modules = {
        "policy_ir": ir_migrations,
        "dataset_manifest": fabric_migrations,
        "run_manifest": manifest_migrations,
    }
    module = modules[artifact]
    calls: list[tuple[dict[str, object], tuple[object, ...], dict[str, object]]] = []

    def selected(data: dict[str, object], *args: object, **kwargs: object) -> dict[str, object]:
        calls.append((dict(data), args, kwargs))
        return {**data, "selected_route": artifact}

    monkeypatch.setattr(module, "e02_selected_test_callable", selected, raising=False)
    original_load = contracts.load_contract

    def changed_contract(root: Path | None = None) -> dict[str, Any]:
        value = original_load(root)
        for item in value["helper_binding"]:
            if item["artifact"] == artifact:
                item["implementation"] = f"{module.__name__}.e02_selected_test_callable"
        return value

    monkeypatch.setattr(contracts, "load_contract", changed_contract)
    input_path, output_path = tmp_path / "source.json", tmp_path / "result.json"
    input_path.write_text(json.dumps({"schema_version": "0.9", "value": "input"}))
    assert migrate.main([artifact, str(input_path), str(output_path)]) == 0
    result = json.loads(output_path.read_text())
    assert result["selected_route"] == artifact
    assert len(calls) == 1
    if artifact == "run_manifest":
        assert calls[0][2]["manifest_path"] == input_path
    if artifact == "dataset_manifest":
        assert result["schema_version"] == "1.0"


@pytest.mark.parametrize(
    "implementation",
    [
        "no.such.module.migrate",
        "polisyos.fabric.identity.migrations.absent_converter",
        "polisyos.fabric.identity.migrations.MANIFEST_CURRENT_VERSION",
        "not-a-qualified-path",
    ],
)
def test_broken_implementation_fails_before_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, implementation: str
) -> None:
    """A missing, invalid or non-callable selected binding cannot write an output."""
    original_load = contracts.load_contract

    def changed_contract(root: Path | None = None) -> dict[str, Any]:
        value = original_load(root)
        for item in value["helper_binding"]:
            if item["artifact"] == "dataset_manifest":
                item["implementation"] = implementation
        return value

    monkeypatch.setattr(contracts, "load_contract", changed_contract)
    source, output = tmp_path / "input.json", tmp_path / "output.json"
    source.write_text('{"schema_version":"0.9"}')
    output.write_text("old output\n")
    with pytest.raises(ValueError, match="implementation"):
        migrate.main(["dataset_manifest", str(source), str(output)])
    assert output.read_text() == "old output\n"


def test_concurrent_dataset_commands_keep_own_selected_converter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Concurrent commands consume their own selected edge, without changing the registry."""
    from polisyos.common.migrations import base as common_migrations
    from polisyos.common.migrations import migrate_artifact, register_migration
    from polisyos.fabric.identity import migrations as fabric_migrations

    selected_thread = threading.local()
    barrier = threading.Barrier(2, timeout=10)
    original_load = contracts.load_contract
    original_migrate = migrate.migrate_common_artifact

    def converter_a(data: dict[str, object]) -> dict[str, object]:
        return {**data, "selected_route": "A"}

    def converter_b(data: dict[str, object]) -> dict[str, object]:
        return {**data, "selected_route": "B"}

    def registry_converter(data: dict[str, object]) -> dict[str, object]:
        return {**data, "selected_route": "registry"}

    monkeypatch.setattr(fabric_migrations, "e02_test_a", converter_a, raising=False)
    monkeypatch.setattr(fabric_migrations, "e02_test_b", converter_b, raising=False)

    def selected_contract(root: Path | None = None) -> dict[str, Any]:
        value = original_load(root)
        for item in value["helper_binding"]:
            if item["artifact"] == "dataset_manifest":
                item["implementation"] = (
                    f"polisyos.fabric.identity.migrations.e02_test_{selected_thread.name}"
                )
        return value

    def interleaved(*args: Any, **kwargs: Any) -> dict[str, object]:
        barrier.wait()
        return original_migrate(*args, **kwargs)

    monkeypatch.setattr(contracts, "load_contract", selected_contract)
    monkeypatch.setattr(migrate, "migrate_common_artifact", interleaved)
    isolated_registry = {key: dict(edges) for key, edges in common_migrations._MIGRATIONS.items()}
    monkeypatch.setattr(common_migrations, "_MIGRATIONS", isolated_registry)
    register_migration("dataset_manifest", "0.9", "1.0")(registry_converter)

    def run(label: str) -> dict[str, object]:
        selected_thread.name = label
        source, output = tmp_path / f"{label}-in.json", tmp_path / f"{label}-out.json"
        source.write_text('{"schema_version":"0.9"}')
        assert migrate.main(["dataset_manifest", str(source), str(output)]) == 0
        return json.loads(output.read_text())

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        first, second = executor.submit(run, "a"), executor.submit(run, "b")
        assert first.result()["selected_route"] == "A"
        assert second.result()["selected_route"] == "B"
    assert (
        migrate_artifact({"schema_version": "0.9"}, "dataset_manifest", "1.0")["selected_route"]
        == "registry"
    )


def test_installed_layout_resolves_contract_without_adding_checkout_imports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Installed modules may use checkout contracts without importing checkout code."""
    installed_file = (
        tmp_path / "site-packages" / "tools" / "ops_runners" / "migrations" / "migrate.py"
    )
    monkeypatch.chdir(PRODUCT_ROOT)
    paths_before = list(sys.path)
    root, source = migrate._resolve_migration_roots(installed_file)
    assert (root, source) == (PRODUCT_ROOT, PRODUCT_ROOT / "src")
    assert sys.path == paths_before
    monkeypatch.setattr(contracts, "__file__", installed_file.with_name("contracts.py"))
    binding = contracts.validate_helper_binding("dataset_manifest")
    assert binding.implementation.endswith("migrate_manifest_0_9_to_1_0")
    assert sys.path == paths_before


def test_unanchored_or_malformed_workspace_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A fake sentinel layout or outside CWD does not silently become a workspace."""
    monkeypatch.setattr(contracts, "__file__", tmp_path / "site-packages" / "contracts.py")
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="workspace"):
        contracts.validate_helper_binding("dataset_manifest")
    (tmp_path / "pyproject.toml").mkdir()
    (tmp_path / "tools").mkdir()
    (tmp_path / "src").mkdir()
    with pytest.raises(ValueError, match="workspace"):
        contracts.validate_helper_binding("dataset_manifest", tmp_path)


@pytest.mark.parametrize("duplicate", ["helper_binding", "migration_class"])
def test_ambiguous_contract_refuses_before_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, duplicate: str
) -> None:
    """A duplicated selected binding or class cannot be resolved by list order."""
    original_load = contracts.load_contract

    def changed_contract(root: Path | None = None) -> dict[str, Any]:
        value = original_load(root)
        key = "artifact" if duplicate == "helper_binding" else "id"
        wanted = "dataset_manifest" if duplicate == "helper_binding" else "api_schemas"
        item = next(item for item in value[duplicate] if item[key] == wanted)
        value[duplicate].append(dict(item))
        return value

    monkeypatch.setattr(contracts, "load_contract", changed_contract)
    source, output = tmp_path / "input.json", tmp_path / "output.json"
    source.write_text('{"schema_version":"0.9"}')
    output.write_text("old output\n")
    with pytest.raises(ValueError, match="exactly one"):
        migrate.main(["dataset_manifest", str(source), str(output)])
    assert output.read_text() == "old output\n"


def test_contract_target_cannot_escape_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Matching out-of-workspace target and contract paths do not admit a helper."""
    original_load = contracts.load_contract
    external = str(tmp_path.resolve())

    def changed_contract(root: Path | None = None) -> dict[str, Any]:
        value = original_load(root)
        for item in value["helper_binding"]:
            if item["artifact"] == "dataset_manifest":
                item["contract_path"] = external
        for item in value["migration_class"]:
            if item["id"] == "api_schemas":
                item["target_path"] = external
        return value

    monkeypatch.setattr(contracts, "load_contract", changed_contract)
    source, output = tmp_path / "input.json", tmp_path / "output.json"
    source.write_text('{"schema_version":"0.9"}')
    output.write_text("old output\n")
    with pytest.raises(ValueError, match="escapes"):
        migrate.main(["dataset_manifest", str(source), str(output)])
    assert output.read_text() == "old output\n"


def test_binding_and_class_use_same_contract_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A concurrent contract change cannot join a binding from another read."""
    original_load = contracts.load_contract
    reads = 0

    def single_read(root: Path | None = None) -> dict[str, Any]:
        nonlocal reads
        reads += 1
        if reads > 1:
            raise AssertionError("migration contract was read twice")
        return original_load(root)

    monkeypatch.setattr(contracts, "load_contract", single_read)
    source, output = tmp_path / "input.json", tmp_path / "output.json"
    source.write_text('{"schema_version":"0.9","datasetName":"baseline"}')
    assert migrate.main(["dataset_manifest", str(source), str(output)]) == 0
    assert json.loads(output.read_text())["dataset_name"] == "baseline"
    assert reads == 1


def test_source_contract_root_does_not_depend_on_current_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An anchored source runner selects its own workspace when called elsewhere."""
    monkeypatch.chdir(tmp_path)
    assert contracts.resolve_contract_root() == PRODUCT_ROOT
    assert contracts.validate_helper_binding("dataset_manifest").artifact == "dataset_manifest"


@pytest.mark.parametrize("artifact", ["policy_ir", "dataset_manifest", "run_manifest"])
def test_selected_converter_non_object_cannot_replace_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, artifact: str
) -> None:
    """Selected converters must return an object before output is published."""
    from polisyos.fabric.identity import migrations as fabric_migrations
    from polisyos.ir import migrations as ir_migrations
    from polisyos.runtime import manifest_migrations

    modules = {
        "policy_ir": ir_migrations,
        "dataset_manifest": fabric_migrations,
        "run_manifest": manifest_migrations,
    }
    module = modules[artifact]

    def invalid_output(*_args: object, **_kwargs: object) -> list[object]:
        return []

    monkeypatch.setattr(module, "e02_invalid_output", invalid_output, raising=False)
    original_load = contracts.load_contract

    def changed_contract(root: Path | None = None) -> dict[str, Any]:
        value = original_load(root)
        for item in value["helper_binding"]:
            if item["artifact"] == artifact:
                item["implementation"] = f"{module.__name__}.e02_invalid_output"
        return value

    monkeypatch.setattr(contracts, "load_contract", changed_contract)
    source, output = tmp_path / "input.json", tmp_path / "output.json"
    source.write_text('{"schema_version":"0.9"}')
    output.write_text("old output\n")
    with pytest.raises((ValueError, TypeError), match=r"dict|object"):
        migrate.main([artifact, str(source), str(output)])
    assert output.read_text() == "old output\n"
