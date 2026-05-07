from __future__ import annotations

import json
from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from pydantic import BaseModel

from polisyos.schemas.abi_models import ABIModelEntry, CompatMode, Lifecycle, Priority
from tools.quality.diagnostics import (
    abi_diff,
    check_perf_regression,
    gen_schema,
    visualize_provenance,
)


def _benchmark_payload(name: str, mean: float) -> dict[str, object]:
    return {
        "benchmarks": [
            {
                "name": name,
                "stats": {
                    "mean": mean,
                    "stddev": 0.0,
                    "min": mean,
                    "max": mean,
                    "rounds": 5,
                },
            }
        ]
    }


def test_perf_regression_emits_skipped_junit_for_non_overlapping_benchmarks(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    output = tmp_path / "perf.xml"
    baseline.write_text(json.dumps(_benchmark_payload("baseline_only", 0.1)), encoding="utf-8")
    current.write_text(json.dumps(_benchmark_payload("current_only", 0.2)), encoding="utf-8")

    exit_code = check_perf_regression.main(
        [
            "--baseline",
            str(baseline),
            "--current",
            str(current),
            "--output-format",
            "junit",
            "--output",
            str(output),
        ]
    )

    rendered = output.read_text(encoding="utf-8")
    assert exit_code == 0
    assert 'skipped="1"' in rendered
    assert "<skipped" in rendered


_PROP_NAME = st.from_regex(r"[a-z][a-z0-9_]{0,7}", fullmatch=True)
_JSON_SCHEMA_TYPE = st.sampled_from(["string", "integer", "number", "boolean"])


@given(props=st.dictionaries(_PROP_NAME, _JSON_SCHEMA_TYPE, min_size=1, max_size=4))
@settings(suppress_health_check=[HealthCheck.too_slow])
def test_abi_diff_matches_semantic_hash_renames(props: dict[str, str]) -> None:
    schema = {
        "type": "object",
        "properties": {name: {"type": type_name} for name, type_name in props.items()},
    }
    baseline_only = {
        "ir:old_name": abi_diff.ModelSnapshot(
            abi_key="old_name",
            module="ir",
            schema_path=Path("baseline.schema.json"),
            schema=schema,
            schema_version="1.0",
            priority="p1",
            compat_mode="strict",
            version_field="schema_version",
            aliases=(),
            lifecycle="active",
            sha256_full="old-full",
            sha256_semantic="same-semantic-hash",
        )
    }
    current_only = {
        "ir:new_name": abi_diff.ModelSnapshot(
            abi_key="new_name",
            module="ir",
            schema_path=Path("current.schema.json"),
            schema=schema,
            schema_version="2.0",
            priority="p1",
            compat_mode="strict",
            version_field="schema_version",
            aliases=(),
            lifecycle="active",
            sha256_full="new-full",
            sha256_semantic="same-semantic-hash",
        )
    }

    matches = abi_diff._match_renamed_models(
        baseline_only=baseline_only,
        current_only=current_only,
    )

    assert len(matches) == 1
    assert matches[0][0].abi_key == "old_name"
    assert matches[0][1].abi_key == "new_name"
    assert matches[0][2] == "semantic_hash"


def test_abi_diff_report_flags_breaking_change_without_major_bump() -> None:
    baseline = {
        "ir:model": abi_diff.ModelSnapshot(
            abi_key="model",
            module="ir",
            schema_path=Path("baseline.schema.json"),
            schema={
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "required": ["value"],
            },
            schema_version="1.0",
            priority="p0",
            compat_mode="strict",
            version_field="schema_version",
            aliases=(),
            lifecycle="active",
            sha256_full="baseline",
            sha256_semantic="baseline-semantic",
        )
    }
    current = {
        "ir:model": abi_diff.ModelSnapshot(
            abi_key="model",
            module="ir",
            schema_path=Path("current.schema.json"),
            schema={"type": "object", "properties": {}},
            schema_version="1.1",
            priority="p0",
            compat_mode="strict",
            version_field="schema_version",
            aliases=(),
            lifecycle="active",
            sha256_full="current",
            sha256_semantic="current-semantic",
        )
    }

    report = abi_diff._build_diff_report(baseline, current)
    payload = abi_diff._report_to_dict(report)

    assert report.verdict == "FAIL"
    assert payload["version_errors"]
    assert any(change["kind"] == "property_removed" for change in payload["changes"])


def test_gen_schema_process_module_writes_expected_snapshot_and_manifest(
    tmp_path: Path,
    monkeypatch,
) -> None:
    class DemoModel(BaseModel):
        schema_version: str = "1.0"
        value: int

    entry = ABIModelEntry(
        abi_key="demo_model",
        fqn="demo.models.DemoModel",
        module="ir",
        schema_file="demo_model.schema.json",
        priority=Priority.P1,
        compat_mode=CompatMode.STRICT,
        version_field="schema_version",
        lifecycle=Lifecycle.ACTIVE,
    )

    monkeypatch.setattr(gen_schema, "_resolve_class", lambda _fqn: DemoModel)
    errors: list[str] = []

    updated, manifest_entries = gen_schema._process_module(
        module="ir",
        entries=(entry,),
        output_dir=tmp_path,
        fmt="pretty",
        check=False,
        errors=errors,
    )

    schema_path = tmp_path / "ir" / "demo_model.schema.json"
    manifest_path = tmp_path / "ir" / "_manifest.json"
    expected_schema = gen_schema._json_dump(
        gen_schema._generate_model_schema(DemoModel), fmt="pretty"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert errors == []
    assert updated == 2
    assert manifest_entries["demo_model"]["schema_version"] == "1.0"
    assert schema_path.read_text(encoding="utf-8") == expected_schema
    assert manifest["models"]["demo_model"]["schema_file"] == "demo_model.schema.json"


def test_visualize_provenance_loads_package_and_detects_cycle(tmp_path: Path) -> None:
    package_dir = tmp_path / "audit-package"
    provenance_dir = package_dir / "provenance"
    provenance_dir.mkdir(parents=True)
    payload = {
        "entities": [{"entity_id": "entity-a"}],
        "activities": [{"activity_id": "activity-a"}],
        "agents": [],
        "edges": [
            {"source_id": "entity-a", "target_id": "activity-a", "relation": "wasDerivedFrom"},
            {"source_id": "activity-a", "target_id": "entity-a", "relation": "wasDerivedFrom"},
        ],
    }
    (provenance_dir / "prov.json").write_text(json.dumps(payload), encoding="utf-8")

    loaded = visualize_provenance.load_provenance_payload(
        source=None,
        cas_root=None,
        from_package=package_dir,
    )
    issues = visualize_provenance.verify_core_graph(loaded)

    assert visualize_provenance.detect_format(loaded, "auto") == "core-graph"
    assert loaded == payload
    assert any("CYCLE" in issue for issue in issues)
