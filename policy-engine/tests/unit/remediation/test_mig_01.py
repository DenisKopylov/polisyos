"""Behavioral witnesses for the canonical migration CLI and Trinity boundary.

The canonical executor and registered command share one validated behavior.
A current schema version is not evidence that a payload passed Trinity
validation: the no-op path must still validate the complete bundle.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from polisyos.ir.loading.loaders import PolicyLoadError, load_policy, load_trinity_bundle
from polisyos.ir.migrations import migrate_policy_ir
from polisyos.ir.trinity import TrinityBundle
from tools.cli import main as tools_cli_main
from tools.lib import fs
from tools.ops_runners.migrations.migrate import main as canonical_main

pytestmark = pytest.mark.unit

ZERO_REF = "sha256:" + "0" * 64
PRODUCT_ROOT = Path(__file__).parents[3]


def _write_atomic(kind: str, path: Path) -> bytes:
    if kind == "text":
        fs.atomic_write_text(path, "new café\n")
        return "new café\n".encode()
    fs.atomic_write_bytes(path, b"new\x00bytes\n")
    return b"new\x00bytes\n"


@pytest.mark.parametrize("kind", ["text", "bytes"])
@pytest.mark.parametrize("failure_stage", ["write", "flush", "fsync", "replace"])
def test_atomic_output_fault_preserves_destination_and_cleans_only_its_temp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    failure_stage: str,
) -> None:
    """A real created file remains cleanup-owned before the first risky I/O."""
    source = tmp_path / "input.json"
    source.write_bytes(b"source is unchanged\n")
    output = tmp_path / "output.json"
    output.write_bytes(b"previous output\n")
    foreign = tmp_path / ".output.foreign.tmp"
    foreign.write_bytes(b"foreign bytes\n")
    primary = OSError(f"controlled {failure_stage} failure")
    temporary_paths: list[Path] = []
    original_temporary = fs.tempfile.NamedTemporaryFile

    class FaultingFile:
        def __init__(self, handle):
            self.handle = handle
            self.name = handle.name

        def write(self, data):
            if failure_stage == "write":
                self.handle.write(data[:1])
                raise primary
            return self.handle.write(data)

        def flush(self):
            self.handle.flush()
            if failure_stage == "flush":
                raise primary

        def fileno(self):
            return self.handle.fileno()

    @contextmanager
    def temporary(*args, **kwargs):
        with original_temporary(*args, **kwargs) as handle:
            temporary_paths.append(Path(handle.name))
            yield FaultingFile(handle)

    def fail(*args, **kwargs):
        del args, kwargs
        raise primary

    monkeypatch.setattr(fs.tempfile, "NamedTemporaryFile", temporary)
    if failure_stage in {"fsync", "replace"}:
        monkeypatch.setattr(fs.os, failure_stage, fail)
    with pytest.raises(OSError) as failure:
        _write_atomic(kind, output)
    assert failure.value is primary
    assert len(temporary_paths) == 1
    assert not temporary_paths[0].exists()
    assert output.read_bytes() == b"previous output\n"
    assert source.read_bytes() == b"source is unchanged\n"
    assert foreign.read_bytes() == b"foreign bytes\n"
    assert set(tmp_path.glob("*.tmp")) == {foreign}


@pytest.mark.parametrize("kind", ["text", "bytes"])
def test_atomic_cleanup_denial_preserves_original_error_and_names_residual_temp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
) -> None:
    """An OS cleanup refusal is diagnostic evidence on the primary write error."""
    output = tmp_path / "output.json"
    output.write_bytes(b"previous output\n")
    primary = OSError("controlled fsync failure")
    cleanup = PermissionError("controlled cleanup denial")
    original_unlink = Path.unlink

    def fail_fsync(descriptor):
        del descriptor
        raise primary

    def deny_owned_temp(path, *args, **kwargs):
        if path.parent == tmp_path and path.name.startswith(".output.") and path.suffix == ".tmp":
            raise cleanup
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(fs.os, "fsync", fail_fsync)
    monkeypatch.setattr(Path, "unlink", deny_owned_temp)
    with pytest.raises(OSError) as failure:
        _write_atomic(kind, output)
    assert failure.value is primary
    residual = list(tmp_path.glob(".output.*.tmp"))
    assert len(residual) == 1
    notes = getattr(primary, "__notes__", ())
    assert any(str(residual[0]) in note and str(cleanup) in note for note in notes)
    assert output.read_bytes() == b"previous output\n"


@pytest.mark.parametrize("kind", ["text", "bytes"])
@pytest.mark.parametrize("replacement_kind", ["file", "symlink"])
def test_atomic_cleanup_retains_foreign_replacement_at_owned_temporary_name(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    replacement_kind: str,
) -> None:
    """A still-open temporary descriptor does not confer ownership of a new leaf."""
    source = tmp_path / "input.json"
    source.write_bytes(b"unchanged input\n")
    output = tmp_path / "output.json"
    output.write_bytes(b"previous output\n")
    foreign_target = tmp_path / "foreign-target.json"
    foreign_target.write_bytes(b"foreign replacement bytes\n")
    original_temporary = fs.tempfile.NamedTemporaryFile
    primary = OSError("controlled write failure after temporary name replacement")
    replacements: list[Path] = []

    class ReplacingFile:
        def __init__(self, handle):
            self.handle = handle
            self.name = handle.name

        def write(self, data):
            self.handle.write(data[:1])
            owned_identity = fs.os.fstat(self.handle.fileno())
            replacement = Path(self.name)
            replacement.unlink()
            if replacement_kind == "file":
                replacement.write_bytes(b"foreign replacement bytes\n")
            else:
                replacement.symlink_to(foreign_target)
            # The actual original file remains open, preventing inode reuse.
            assert fs.os.fstat(self.handle.fileno()).st_ino == owned_identity.st_ino
            assert replacement.lstat().st_ino != owned_identity.st_ino
            replacements.append(replacement)
            raise primary

        def flush(self):
            self.handle.flush()

        def fileno(self):
            return self.handle.fileno()

    @contextmanager
    def temporary(*args, **kwargs):
        with original_temporary(*args, **kwargs) as handle:
            yield ReplacingFile(handle)

    monkeypatch.setattr(fs.tempfile, "NamedTemporaryFile", temporary)
    with pytest.raises(OSError) as failure:
        _write_atomic(kind, output)
    assert failure.value is primary
    assert len(replacements) == 1
    replacement = replacements[0]
    if replacement_kind == "symlink":
        assert replacement.is_symlink()
        assert replacement.readlink() == foreign_target
    else:
        assert replacement.is_file() and not replacement.is_symlink()
    assert replacement.read_bytes() == b"foreign replacement bytes\n"
    assert foreign_target.read_bytes() == b"foreign replacement bytes\n"
    assert source.read_bytes() == b"unchanged input\n"
    assert output.read_bytes() == b"previous output\n"
    assert any(
        str(replacement) in note and "ownership" in note
        for note in getattr(primary, "__notes__", ())
    )


@pytest.mark.parametrize("kind", ["text", "bytes"])
def test_reported_error_after_actual_replace_does_not_promise_rollback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
) -> None:
    """A failure reported after publication retains the newly published bytes."""
    output = tmp_path / "output.json"
    output.write_bytes(b"previous output\n")
    original_replace = fs.os.replace
    primary = OSError("controlled post-replace failure")

    def publish_then_fail(source, target):
        original_replace(source, target)
        raise primary

    monkeypatch.setattr(fs.os, "replace", publish_then_fail)
    with pytest.raises(OSError) as failure:
        _write_atomic(kind, output)
    assert failure.value is primary
    assert output.read_bytes() == ("new café\n".encode() if kind == "text" else b"new\x00bytes\n")
    assert list(tmp_path.glob(".output.*.tmp")) == []


def test_json_serialization_failure_precedes_temporary_output(tmp_path: Path) -> None:
    """The existing JSON helper never creates an output for failed rendering."""
    output = tmp_path / "output.json"
    output.write_bytes(b"previous output\n")
    primary = ValueError("controlled JSON rendering failure")

    class Unserializable:
        def __str__(self):
            raise primary

    with pytest.raises(ValueError) as failure:
        fs.atomic_write_json(output, {"value": Unserializable()})
    assert failure.value is primary
    assert output.read_bytes() == b"previous output\n"
    assert list(tmp_path.glob(".output.*.tmp")) == []


@pytest.mark.parametrize("kind", ["text", "bytes"])
def test_atomic_helpers_keep_real_secure_output_root_ownership(
    tmp_path: Path,
    kind: str,
) -> None:
    """The scoped native owner writes its own leaf and refuses external output."""
    owned = tmp_path / "owned"
    owned.mkdir()
    external = tmp_path / "external.json"
    external.write_bytes(b"foreign output\n")
    output = owned / "output.json"
    with fs.SecureOutputRoot(owned) as root, fs.bind_secure_output_root(root):
        expected = _write_atomic(kind, output)
        assert output.read_bytes() == expected
        assert fs.active_secure_output_root() is root
        with pytest.raises(ValueError):
            _write_atomic(kind, external)
    assert external.read_bytes() == b"foreign output\n"
    assert list(owned.glob("*.tmp")) == []


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

    assert migrated is payload
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


def test_current_helper_matrix_preserves_identity_normalized_dump_and_tuple() -> None:
    """No-op identity, model identity and normalized conversion remain distinct."""
    from polisyos.ir.migrations.policy_ir import migrate_policy_ir_identity
    from polisyos.ir.migrations.trinity_migration import split_to_bundle

    payload = _canonical_trinity_payload()
    bundle = TrinityBundle.model_validate(payload)
    assert split_to_bundle(bundle) is bundle
    assert load_policy(bundle) is bundle
    loaded, report = load_trinity_bundle(bundle)
    assert loaded is bundle
    assert report is None
    assert migrate_policy_ir(payload) is payload
    normalized = migrate_policy_ir_identity(payload)
    assert normalized == bundle.model_dump(mode="python")
    assert normalized is not payload


def test_shape_valid_later_version_loader_is_not_migration_admission() -> None:
    """The general shape loader cannot authorize a prohibited migration version."""
    payload = _canonical_trinity_payload()
    payload["schema_version"] = "2.0"
    bundle, report = load_trinity_bundle(payload)
    assert bundle.schema_version == "2.0"
    assert report is None
    with pytest.raises(ValueError, match="Legacy non-Trinity payloads"):
        migrate_policy_ir(payload, "1.0")


@pytest.mark.parametrize("failure_kind", ["json", "yaml", "utf8"])
def test_native_cli_preserves_distinct_parse_errors_and_existing_output(
    tmp_path: Path,
    failure_kind: str,
) -> None:
    """The canonical parser keeps its actual error ABI without writing a result."""
    if failure_kind == "json":
        payload, suffix, expected_type = b"{", ".json", json.JSONDecodeError
    elif failure_kind == "yaml":
        yaml = pytest.importorskip("yaml")
        payload, suffix, expected_type = b"problem_frame: [\n", ".yaml", yaml.parser.ParserError
    else:
        payload, suffix, expected_type = b"\xff", ".json", UnicodeDecodeError
    source = tmp_path / ("source" + suffix)
    source.write_bytes(payload)
    output = tmp_path / ("output" + suffix)
    output.write_bytes(b"old output\n")
    with pytest.raises(expected_type) as failure:
        canonical_main(["policy_ir", str(source), str(output)])
    assert type(failure.value) is expected_type
    assert source.read_bytes() == payload
    assert output.read_bytes() == b"old output\n"
    assert list(tmp_path.glob("*.tmp")) == []


def test_public_loader_preserves_parser_errors_and_wraps_invalid_utf8() -> None:
    """Parser failures differ from the loader's explicit UTF-8 policy failure."""
    yaml = pytest.importorskip("yaml")
    with pytest.raises(json.JSONDecodeError):
        load_policy("{", fmt="json")
    with pytest.raises(yaml.parser.ParserError):
        load_policy("problem_frame: [\n", fmt="yaml")
    with pytest.raises(PolicyLoadError, match="UTF-8 decodable") as failure:
        load_policy(b"\xff", fmt="json")
    assert isinstance(failure.value.__cause__, UnicodeDecodeError)


@pytest.mark.parametrize("missing", ["contract", "target-directory"])
def test_missing_operational_contract_refuses_before_native_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    missing: str,
) -> None:
    """The actual contract resolver refuses a missing binding input before dump."""
    from tools.ops_runners.migrations import migrate as migration_module

    workspace = tmp_path / "contracts-workspace"
    workspace.mkdir()
    (workspace / "pyproject.toml").write_text("", encoding="utf-8")
    (workspace / "tools").mkdir()
    (workspace / "src").mkdir()
    if missing == "target-directory":
        contract = workspace / "ops/migrations/migration-contracts.toml"
        contract.parent.mkdir(parents=True)
        contract.write_bytes(
            (PRODUCT_ROOT / "ops/migrations/migration-contracts.toml").read_bytes()
        )
    source = tmp_path / "source.json"
    original = json.dumps(_canonical_trinity_payload()).encode()
    source.write_bytes(original)
    output = tmp_path / "output.json"
    output.write_bytes(b"old output\n")
    monkeypatch.setattr(migration_module, "REPO_ROOT", workspace)
    with pytest.raises(FileNotFoundError, match=r"missing (migration contract|contract path)"):
        canonical_main(["policy_ir", str(source), str(output)])
    assert source.read_bytes() == original
    assert output.read_bytes() == b"old output\n"
    assert list(tmp_path.glob("*.tmp")) == []
