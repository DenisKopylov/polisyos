from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


def _schema_hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _write_snapshots(root: Path, module: str, models: list[dict]) -> None:
    module_dir = root / module
    module_dir.mkdir(parents=True, exist_ok=True)

    manifest_models: dict[str, dict] = {}
    for model in models:
        abi_key = model["abi_key"]
        schema = model["schema"]
        schema_file = model.get("schema_file", f"{abi_key}.schema.json")
        (module_dir / schema_file).write_text(
            json.dumps(schema, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )

        semantic_schema = {
            key: value
            for key, value in schema.items()
            if key not in {"title", "description", "$comment", "examples"}
        }

        manifest_models[abi_key] = {
            "fqn": model.get("fqn", f"tests.{abi_key}"),
            "schema_file": schema_file,
            "schema_version": model.get("schema_version", "1.0"),
            "priority": model.get("priority", "p0"),
            "compat_mode": model.get("compat_mode", "strict"),
            "version_field": model.get("version_field", "schema_version"),
            "aliases": model.get("aliases", []),
            "lifecycle": model.get("lifecycle", "active"),
            "sha256_full": _schema_hash(schema),
            "sha256_semantic": _schema_hash(semantic_schema),
        }

    manifest = {
        "generated_at": "2026-02-06T00:00:00+00:00",
        "generator_version": "1.0.0",
        "python_version": "3.11.0",
        "pydantic_version": "2.12.5",
        "module": module,
        "models": manifest_models,
        "content_hash": _schema_hash(manifest_models),
    }
    (module_dir / "_manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _run_abi_diff(tmp_path: Path, baseline: Path, current: Path) -> dict:
    report_path = tmp_path / "report.json"
    repo_root = Path(__file__).resolve().parents[2]
    script_candidates = (
        repo_root / "tools" / "diagnostics" / "abi_diff.py",
        repo_root / "tools" / "abi_diff.py",
    )
    script = next((candidate for candidate in script_candidates if candidate.exists()), None)
    if script is None:
        raise FileNotFoundError(
            "ABI diff script not found. Checked: "
            + ", ".join(str(candidate) for candidate in script_candidates)
        )
    subprocess.run(
        [
            sys.executable,
            str(script),
            "--baseline",
            str(baseline),
            "--current",
            str(current),
            "--output",
            str(report_path),
            "--format",
            "json",
        ],
        check=False,
        cwd=str(repo_root),
    )
    return json.loads(report_path.read_text("utf-8"))


def test_strict_optional_property_addition_is_breaking(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline"
    current = tmp_path / "current"

    base_schema = {
        "type": "object",
        "properties": {"a": {"type": "string"}},
        "required": ["a"],
        "additionalProperties": False,
    }
    curr_schema = {
        "type": "object",
        "properties": {"a": {"type": "string"}, "b": {"type": "string"}},
        "required": ["a"],
        "additionalProperties": False,
    }

    _write_snapshots(
        baseline,
        "ir",
        [{"abi_key": "claim", "schema": base_schema, "schema_version": "1.0", "compat_mode": "strict"}],
    )
    _write_snapshots(
        current,
        "ir",
        [{"abi_key": "claim", "schema": curr_schema, "schema_version": "1.0", "compat_mode": "strict"}],
    )

    report = _run_abi_diff(tmp_path, baseline, current)
    assert report["verdict"] == "FAIL"
    assert any(change["kind"] == "property_added" and change["breaking"] for change in report["changes"])


def test_tolerant_optional_property_addition_is_compatible(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline"
    current = tmp_path / "current"

    base_schema = {
        "type": "object",
        "properties": {"a": {"type": "string"}},
        "required": ["a"],
        "additionalProperties": True,
    }
    curr_schema = {
        "type": "object",
        "properties": {"a": {"type": "string"}, "b": {"type": "string"}},
        "required": ["a"],
        "additionalProperties": True,
    }

    _write_snapshots(
        baseline,
        "ir",
        [{"abi_key": "claim", "schema": base_schema, "schema_version": "1.0", "compat_mode": "tolerant"}],
    )
    _write_snapshots(
        current,
        "ir",
        [{"abi_key": "claim", "schema": curr_schema, "schema_version": "1.0", "compat_mode": "tolerant"}],
    )

    report = _run_abi_diff(tmp_path, baseline, current)
    assert report["verdict"] == "PASS"
    assert any(change["kind"] == "property_added" and not change["breaking"] for change in report["changes"])


def test_breaking_change_with_major_bump_is_warn(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline"
    current = tmp_path / "current"

    base_schema = {
        "type": "object",
        "properties": {"a": {"type": "string"}},
        "required": ["a"],
    }
    curr_schema = {
        "type": "object",
        "properties": {"a": {"type": "integer"}},
        "required": ["a"],
    }

    _write_snapshots(
        baseline,
        "ir",
        [{"abi_key": "claim", "schema": base_schema, "schema_version": "1.0", "compat_mode": "strict"}],
    )
    _write_snapshots(
        current,
        "ir",
        [{"abi_key": "claim", "schema": curr_schema, "schema_version": "2.0", "compat_mode": "strict"}],
    )

    report = _run_abi_diff(tmp_path, baseline, current)
    assert report["verdict"] == "WARN"
    assert report["version_errors"] == []


def test_alias_match_reports_model_renamed(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline"
    current = tmp_path / "current"

    schema = {
        "type": "object",
        "properties": {"a": {"type": "string"}},
        "required": ["a"],
    }

    _write_snapshots(
        baseline,
        "ir",
        [
            {
                "abi_key": "old_claim",
                "schema": schema,
                "schema_version": "1.0",
                "priority": "p1",
                "compat_mode": "strict",
            }
        ],
    )
    _write_snapshots(
        current,
        "ir",
        [
            {
                "abi_key": "new_claim",
                "schema": schema,
                "schema_version": "1.0",
                "priority": "p1",
                "compat_mode": "strict",
                "aliases": ["old_claim"],
            }
        ],
    )

    report = _run_abi_diff(tmp_path, baseline, current)
    assert any(change["kind"] == "model_renamed" for change in report["changes"])
