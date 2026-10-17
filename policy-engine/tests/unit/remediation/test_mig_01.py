"""Behavioral witnesses for the canonical migration CLI and Trinity boundary.

The canonical executor and registered command share one validated behavior.
A current schema version is not evidence that a payload passed Trinity
validation: the no-op path must still validate the complete bundle.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from polisyos.ir.loading.loaders import PolicyLoadError, load_policy, load_trinity_bundle
from polisyos.ir.migrations import migrate_policy_ir
from polisyos.ir.trinity import TrinityBundle
from tools.cli import main as tools_cli_main
from tools.ops_runners.migrations.migrate import main as canonical_main

pytestmark = pytest.mark.unit

ZERO_REF = "sha256:" + "0" * 64
PRODUCT_ROOT = Path(__file__).parents[3]


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


def test_registered_migration_command_runs_the_canonical_policy_ir_path(tmp_path: Path) -> None:
    """The public tools command writes the same fully validated Trinity artifact."""
    payload = _canonical_trinity_payload()
    source = tmp_path / "input.json"
    output = tmp_path / "output.json"
    original = json.dumps(payload)
    source.write_text(original, encoding="utf-8")

    exit_code = tools_cli_main(
        [
            "migrations",
            "migrate",
            "--skip-preflight",
            "--timing-log",
            str(tmp_path / "migration-timing.jsonl"),
            "policy_ir",
            str(source),
            str(output),
            "--to",
            "1.0",
        ]
    )

    assert exit_code == 0
    assert json.loads(output.read_text(encoding="utf-8")) == payload
    assert source.read_text(encoding="utf-8") == original
