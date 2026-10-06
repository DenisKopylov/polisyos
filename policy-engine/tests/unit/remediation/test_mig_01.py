"""Test-first witnesses for the canonical migration CLI and Trinity boundary.

The tests keep the compatibility surface visible while MIG-01 moves the root
entrypoint onto ``tools.ops_runners.migrations.migrate``.  In particular, a
current schema version is not evidence that a payload passed Trinity
validation: the no-op path must still validate the complete bundle.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from pydantic import ValidationError

from polisyos.ir.loading.loaders import PolicyLoadError, load_policy, load_trinity_bundle
from polisyos.ir.migrations import migrate_policy_ir
from polisyos.ir.trinity import TrinityBundle
from tools.lib.imports import RepositoryRootUnavailableError
from tools.ops_runners.migrations.migrate import main as canonical_main

pytestmark = pytest.mark.unit

ZERO_REF = "sha256:" + "0" * 64
PRODUCT_ROOT = Path(__file__).parents[3]
ROOT_ENTRYPOINT = PRODUCT_ROOT / "migrate.py"


def _canonical_trinity_payload() -> dict[str, Any]:
    """Return a complete, independently specified Trinity payload."""
    return {
        "schema_version": "1.0",
        "problem_frame": {
            "schema_version": "1.0",
            "problem_id": "pf_mig01",
            "domain": "custom",
            "objectives": [],
            "kpis": [],
            "success_criteria": [],
            "hard_constraints": [],
            "soft_constraints": [],
            "stakeholders": [],
            "labels": [],
            "notes": [],
        },
        "policy_spec": {
            "schema_version": "1.0",
            "policy_id": "ps_mig01",
            "interventions": [],
            "mechanism_bindings": [],
            "parameters": [],
            "labels": [],
            "notes": [],
        },
        "model_spec": {
            "schema_version": "1.0",
            "model_id": "ms_mig01",
            "data_snapshot_ref": ZERO_REF,
            "registry_bundle_ref": None,
            "assumptions": [],
            "labels": [],
            "notes": [],
        },
    }


def _load_root_entrypoint() -> ModuleType:
    """Load the historical root script without executing its ``__main__`` block."""
    spec = importlib.util.spec_from_file_location(
        "polisyos_legacy_migrate_entrypoint", ROOT_ENTRYPOINT
    )
    if spec is None or spec.loader is None:
        raise AssertionError(f"could not load root entrypoint: {ROOT_ENTRYPOINT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(("suffix", "fmt"), [(".json", "json"), (".yaml", "yaml")])
@pytest.mark.parametrize("explicit_target", [False, True])
def test_canonical_cli_accepts_json_and_yaml_full_trinity(
    tmp_path: Path,
    suffix: str,
    fmt: str,
    explicit_target: bool,
) -> None:
    """A valid Trinity payload survives default and explicit current targets."""
    payload = _canonical_trinity_payload()
    if fmt == "json":
        source = json.dumps(payload)
    else:
        yaml = pytest.importorskip("yaml")
        source = yaml.safe_dump(payload, sort_keys=False)

    input_path = tmp_path / f"input{suffix}"
    output_path = tmp_path / f"output{suffix}"
    input_path.write_text(source, encoding="utf-8")
    output_path.write_text("old output\n", encoding="utf-8")

    argv = ["policy_ir", str(input_path), str(output_path)]
    if explicit_target:
        argv.extend(["--to", "1.0"])

    assert canonical_main(argv) == 0
    if fmt == "json":
        observed = json.loads(output_path.read_text(encoding="utf-8"))
    else:
        observed = yaml.safe_load(output_path.read_text(encoding="utf-8"))
    assert observed == payload
    assert input_path.read_text(encoding="utf-8") == source
    assert not list(tmp_path.glob(f".{output_path.stem}.*.tmp"))


def test_canonical_cli_persists_a_trinity_bundle_accepted_by_its_owner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The public command validates before write and leaves strict readable bytes."""
    payload = _canonical_trinity_payload()
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    input_path.write_text(json.dumps(payload), encoding="utf-8")
    output_path.write_text("sentinel\n", encoding="utf-8")

    import polisyos.ir.migrations as ir_migrations

    migration_calls: list[tuple[dict[str, Any], str | None]] = []
    original_migration = ir_migrations.migrate_policy_ir

    def observed_migration(
        data: dict[str, Any],
        target_version: str | None = None,
    ) -> dict[str, Any]:
        migration_calls.append((data, target_version))
        return original_migration(data, target_version)

    monkeypatch.setattr(ir_migrations, "migrate_policy_ir", observed_migration)

    calls: list[dict[str, Any]] = []
    original = TrinityBundle.model_validate

    def observed_validator(
        cls: type[TrinityBundle],
        value: Any,
        *args: Any,
        **kwargs: Any,
    ) -> TrinityBundle:
        calls.append(value)
        return original(value, *args, **kwargs)

    monkeypatch.setattr(TrinityBundle, "model_validate", classmethod(observed_validator))

    assert canonical_main(["policy_ir", str(input_path), str(output_path)]) == 0

    assert migration_calls == [(payload, "1.0")]
    assert calls == [payload]
    persisted = TrinityBundle.model_validate_json(output_path.read_bytes())
    assert persisted.model_dump(mode="json", exclude_unset=True) == payload
    assert input_path.read_bytes() == json.dumps(payload).encode("utf-8")


def test_current_version_migration_runs_the_real_trinity_validator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The policy-IR no-op path cannot silently bypass full Trinity validation."""
    payload = _canonical_trinity_payload()
    calls: list[dict[str, Any]] = []
    original = TrinityBundle.model_validate

    def observed_validator(
        cls: type[TrinityBundle], value: Any, *args: Any, **kwargs: Any
    ) -> TrinityBundle:
        calls.append(value)
        return original(value, *args, **kwargs)

    monkeypatch.setattr(TrinityBundle, "model_validate", classmethod(observed_validator))

    migrated = migrate_policy_ir(payload, "1.0")

    assert migrated == payload
    assert calls == [payload]


def test_current_version_incomplete_mapping_is_not_accepted_as_validated(tmp_path: Path) -> None:
    """A version field alone must not make an incomplete target a validated IR."""
    input_path = tmp_path / "incomplete.json"
    output_path = tmp_path / "output.json"
    input_path.write_text(json.dumps({"schema_version": "1.0"}), encoding="utf-8")
    output_path.write_text("sentinel\n", encoding="utf-8")

    with pytest.raises(ValidationError):
        canonical_main(["policy_ir", str(input_path), str(output_path)])

    assert output_path.read_text(encoding="utf-8") == "sentinel\n"


def test_canonical_cli_rejects_malformed_nested_payload_before_output_write(tmp_path: Path) -> None:
    """Malformed nested Trinity data fails closed and preserves the prior output."""
    payload = _canonical_trinity_payload()
    payload["model_spec"] = {"schema_version": "1.0", "model_id": "missing required ref"}
    input_path = tmp_path / "malformed.json"
    output_path = tmp_path / "output.json"
    input_path.write_text(json.dumps(payload), encoding="utf-8")
    output_path.write_text("sentinel\n", encoding="utf-8")

    with pytest.raises(ValidationError):
        canonical_main(["policy_ir", str(input_path), str(output_path)])

    assert output_path.read_text(encoding="utf-8") == "sentinel\n"


@pytest.mark.parametrize(
    ("payload", "target", "message"),
    [
        (
            {"schema_version": "1.0", "semantic": {"context_snapshot_ref": ZERO_REF}},
            "1.0",
            "Legacy non-Trinity payloads",
        ),
        (
            {"schema_version": "2.0", "semantic": {"context_snapshot_ref": ZERO_REF}},
            "1.0",
            "Legacy non-Trinity payloads",
        ),
        (_canonical_trinity_payload(), "2.0", "allow_major=True"),
    ],
)
def test_legacy_and_major_bump_inputs_keep_error_contract_and_output(
    tmp_path: Path,
    payload: dict[str, Any],
    target: str,
    message: str,
) -> None:
    """Legacy surfaces and unapproved major changes remain explicit failures."""
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    input_path.write_text(json.dumps(payload), encoding="utf-8")
    output_path.write_text("sentinel\n", encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        canonical_main(["policy_ir", str(input_path), str(output_path), "--to", target])

    assert output_path.read_text(encoding="utf-8") == "sentinel\n"


def test_cli_rejects_non_mapping_payload_without_touching_output(tmp_path: Path) -> None:
    """A JSON/YAML sequence is not a migration artifact object."""
    input_path = tmp_path / "list.json"
    output_path = tmp_path / "output.json"
    input_path.write_text("[]", encoding="utf-8")
    output_path.write_text("sentinel\n", encoding="utf-8")

    with pytest.raises(ValueError, match="migration input must be a JSON/YAML object"):
        canonical_main(["policy_ir", str(input_path), str(output_path)])

    assert output_path.read_text(encoding="utf-8") == "sentinel\n"


def test_dataset_manifest_conversion_remains_a_distinct_converted_path(tmp_path: Path) -> None:
    """The canonical CLI still performs real conversion for a supported old artifact."""
    payload = {
        "schema_version": "0.9",
        "datasetName": "baseline",
        "rawHash": "sha256:abc",
    }
    input_path = tmp_path / "manifest.json"
    output_path = tmp_path / "manifest-out.json"
    input_path.write_text(json.dumps(payload), encoding="utf-8")

    assert canonical_main(["dataset_manifest", str(input_path), str(output_path)]) == 0
    assert json.loads(output_path.read_text(encoding="utf-8")) == {
        "schema_version": "1.0",
        "dataset_name": "baseline",
        "raw_hash": "sha256:abc",
    }
    assert json.loads(input_path.read_text(encoding="utf-8")) == payload


def test_loader_keeps_tuple_report_and_auto_migrate_error_contracts() -> None:
    """Existing loader callers retain tuple/report, model, and error semantics."""
    payload = _canonical_trinity_payload()
    bundle, report = load_trinity_bundle(payload)
    assert isinstance(bundle, TrinityBundle)
    assert report is None
    assert load_policy(payload) is not None

    malformed = {"schema_version": "1.0"}
    with pytest.raises(PolicyLoadError, match="Payload is not a valid TrinityBundle"):
        load_policy(malformed, auto_migrate=True)
    with pytest.raises(PolicyLoadError, match="Unsupported policy payload"):
        load_policy(malformed, auto_migrate=False)


def test_root_entrypoint_delegates_to_the_canonical_executor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The historical root path forwards argv and return status to one runner."""
    canonical = importlib.import_module("tools.ops_runners.migrations.migrate")
    calls: list[list[str] | None] = []

    def fake_main(argv: list[str] | None = None) -> int:
        calls.append(argv)
        return 17

    monkeypatch.setattr(canonical, "main", fake_main)
    root = _load_root_entrypoint()
    argv = ["dataset_manifest", "input.json", "output.json"]

    assert root.main(argv) == 17
    assert calls == [argv]


def test_installed_migration_resolves_checkout_contracts_without_importing_checkout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An installed migration runner finds checkout contracts without adding checkout imports."""
    migration = importlib.import_module("tools.ops_runners.migrations.migrate")
    installed_module = (
        tmp_path / "site-packages" / "tools" / "ops_runners" / "migrations" / "migrate.py"
    )
    monkeypatch.chdir(PRODUCT_ROOT)
    monkeypatch.setattr(sys, "path", ["sentinel"])

    repo_root, src_root = migration._resolve_migration_roots(installed_module)

    assert repo_root == PRODUCT_ROOT
    assert src_root == PRODUCT_ROOT / "src"
    assert sys.path == ["sentinel"]


def test_source_migration_still_bootstraps_its_checkout_import_roots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The source runner stays anchored to its checkout and keeps source imports available."""
    migration = importlib.import_module("tools.ops_runners.migrations.migrate")
    source_module = PRODUCT_ROOT / "tools" / "ops_runners" / "migrations" / "migrate.py"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "path", ["sentinel"])

    repo_root, src_root = migration._resolve_migration_roots(source_module)

    assert repo_root == PRODUCT_ROOT
    assert src_root == PRODUCT_ROOT / "src"
    assert sys.path == [str(src_root), str(repo_root), "sentinel"]


def test_venv_installed_migration_does_not_import_checkout_from_its_ancestry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A site-packages path inside a checkout is not mistaken for a source module."""
    migration = importlib.import_module("tools.ops_runners.migrations.migrate")
    installed_module = (
        PRODUCT_ROOT
        / ".venv/lib/python3.14/site-packages/tools/ops_runners/migrations/migrate.py"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "path", ["sentinel"])

    repo_root, src_root = migration._resolve_migration_roots(installed_module)

    assert repo_root == PRODUCT_ROOT
    assert src_root == PRODUCT_ROOT / "src"
    assert sys.path == ["sentinel"]


def test_installed_migration_requires_an_existing_checkout_for_contract_lookup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unanchored installed runner fails with the shared typed error outside a checkout."""
    migration = importlib.import_module("tools.ops_runners.migrations.migrate")
    installed_module = (
        tmp_path / "site-packages" / "tools" / "ops_runners" / "migrations" / "migrate.py"
    )
    monkeypatch.chdir(tmp_path)

    with pytest.raises(RepositoryRootUnavailableError):
        migration._resolve_migration_roots(installed_module)
