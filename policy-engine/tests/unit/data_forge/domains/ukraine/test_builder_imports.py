"""Native import and post-return validation contracts for Ukraine builders."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import asdict, fields
from pathlib import Path

import pytest


def test_contract_import_defers_siblings_until_explicit_facade_access() -> None:
    script = r"""
import importlib
import json
import sys

prefix = "polisyos.data_forge.domains.ukraine.builders"
contracts = importlib.import_module(prefix + ".contracts")
unrelated = ["sources", "demography", "bindings_validation", "common"]
loaded = [name for name in unrelated if prefix + "." + name in sys.modules]
assert loaded == [], loaded
builders = importlib.import_module(prefix)
assert builders.StageBuildResult is contracts.StageBuildResult
assert [name for name in unrelated if prefix + "." + name in sys.modules] == []
registry = builders.STAGE_BUILDERS
from polisyos.data_forge.domains.ukraine.models import StageId
expected = {
    StageId.D0_P0: ("sources", "build_d0_p0_stage"),
    StageId.D1: ("sources", "build_d1_stage"),
    StageId.D2: ("sources", "build_d2_stage"),
    StageId.D3: ("demography", "build_d3_stage"),
    StageId.D4: ("governance_handoff", "build_d4_stage"),
    StageId.D5: ("release", "build_d5_stage"),
    StageId.DEMOGRAPHY_SOURCE_INVENTORY: (
        "demography_inventory", "build_demography_source_inventory_stage"
    ),
}
assert set(registry) == set(expected)
for stage_id, (module_name, function_name) in expected.items():
    canonical = getattr(importlib.import_module(prefix + "." + module_name), function_name)
    assert registry[stage_id] is canonical
    assert getattr(builders, function_name) is canonical
assert builders.STAGE_BUILDERS is registry
calibration = importlib.import_module(prefix + ".calibration")
handoff = importlib.import_module(prefix + ".governance_handoff")
assert calibration.build_d4_stage is handoff.build_d4_stage is builders.build_d4_stage
from tools.ops_runners.ukraine_data import build_edr_identity_seed_candidates as seed_tool
for name in (
    "_ensure_agent_numeric_columns", "_extract_unresolved_identity_rows", "_link_participants",
    "_load_source_frame", "_read_parquet_frame", "_resolve_agent_lookup",
    "_select_procurement_frame", "_write_frame", "_write_json",
):
    assert getattr(seed_tool, name) is getattr(builders, name)
print(json.dumps({"deferred": unrelated, "activated_stages": len(registry)}))
"""
    result = subprocess.run(
        [sys.executable, "-B", "-c", script],
        capture_output=True,
        text=True,
        env=dict(os.environ),
        check=False,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout.splitlines()[-1])["activated_stages"] == 7


def test_stage_result_preserves_positional_fields_and_independent_defaults(tmp_path: Path) -> None:
    from polisyos.data_forge.domains.ukraine.builders.contracts import StageBuildResult

    outputs, findings, warnings, metrics, manifest_paths = {}, [], [], {}, [tmp_path / "out"]
    result = StageBuildResult(outputs, findings, warnings, metrics, manifest_paths)
    assert [field.name for field in fields(result)][:5] == [
        "outputs",
        "findings",
        "warnings",
        "metrics",
        "manifest_paths",
    ]
    assert result.manifest_paths is manifest_paths
    assert asdict(result)["inputs"] == []
    result.inputs.append("invalid after construction")
    assert StageBuildResult().inputs == []
    with pytest.raises(TypeError, match="ArtifactRecord"):
        result.validate_inputs()


@pytest.mark.parametrize(
    "mutation",
    ["bad_type", "bad_hash", "wrong_digest", "wrong_size", "duplicate", "overlap", "missing"],
)
def test_orchestrator_revalidates_returned_input_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    from polisyos.data_forge.domains.ukraine import orchestrator as owner
    from polisyos.data_forge.domains.ukraine.builders.contracts import StageBuildResult
    from polisyos.data_forge.domains.ukraine.manifests import (
        ArtifactRecord,
        BuildRunManifest,
        load_manifest,
    )
    from polisyos.data_forge.domains.ukraine.models import StageId, build_default_pipeline_config

    input_path = tmp_path / "source.json"
    input_path.write_bytes(b'{"source": 1}')
    output_path = tmp_path / "derived.json"
    output_path.write_bytes(b'{"derived": 1}')
    record = ArtifactRecord.from_path(input_path)
    result = StageBuildResult(outputs={"derived": ArtifactRecord.from_path(output_path)})
    if mutation == "bad_type":
        returned_inputs = [object()]
    elif mutation == "bad_hash":
        returned_inputs = [record.model_copy(update={"sha256": "invalid"})]
    elif mutation == "wrong_digest":
        returned_inputs = [record.model_copy(update={"sha256": "f" * 64})]
    elif mutation == "wrong_size":
        returned_inputs = [record.model_copy(update={"size_bytes": record.size_bytes + 1})]
    elif mutation == "duplicate":
        returned_inputs = [record, record.model_copy()]
    elif mutation == "overlap":
        returned_inputs = [ArtifactRecord.from_path(output_path)]
    else:
        returned_inputs = [record.model_copy(update={"path": str(tmp_path / "missing.json")})]
    # Mutate only after the producer's result constructor has run.
    result.inputs.extend(returned_inputs)
    monkeypatch.setitem(owner.STAGE_BUILDERS, StageId.D4, lambda _config: result)
    config = build_default_pipeline_config(root=tmp_path / "build")
    orchestrator = owner.UkraineDataOrchestrator(config)
    summary = orchestrator._run_stage_with_tracking(StageId.D4, inputs=[])
    assert summary.status == "failed"
    assert summary.manifest.outputs == []
    assert summary.manifest.errors
    persisted = load_manifest(orchestrator.stage_manifest_path(StageId.D4), BuildRunManifest)
    assert persisted.status == "failed" and persisted.outputs == []


def test_orchestrator_accepts_actual_content_bound_builder_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polisyos.data_forge.domains.ukraine import orchestrator as owner
    from polisyos.data_forge.domains.ukraine.builders.contracts import StageBuildResult
    from polisyos.data_forge.domains.ukraine.manifests import ArtifactRecord
    from polisyos.data_forge.domains.ukraine.models import StageId, build_default_pipeline_config

    input_path, output_path = tmp_path / "source.json", tmp_path / "derived.json"
    input_path.write_bytes(b'{"source": 1}')
    output_path.write_bytes(b'{"derived": 1}')
    record = ArtifactRecord.from_path(input_path)
    result = StageBuildResult(
        outputs={"derived": ArtifactRecord.from_path(output_path)}, inputs=[record]
    )
    monkeypatch.setitem(owner.STAGE_BUILDERS, StageId.D4, lambda _config: result)
    orchestrator = owner.UkraineDataOrchestrator(
        build_default_pipeline_config(root=tmp_path / "build")
    )
    summary = orchestrator._run_stage_with_tracking(StageId.D4, inputs=[])
    assert summary.status == "completed"
    assert summary.manifest.inputs == [record]
    assert summary.manifest.outputs == [result.outputs["derived"]]
