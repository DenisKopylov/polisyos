"""Distinguish selected compiler writer conformity from historical content reads."""

from __future__ import annotations

from pathlib import Path

import pytest

from polisyos.core import artifacts
from polisyos.data_requirement import DataRequirementCompiler
from polisyos.runtime.quality.acquisition_planner import (
    persist_and_verify_data_requirement_compilation_report,
    validate_persisted_data_requirement_compilation_report,
)
from polisyos.runtime.quality.capability_resolver import RequirementToCapabilityResolver
from tests.unit.data_requirement.test_compiler import _declared_source_scenario


def _persisted_report(tmp_path: Path):
    report = DataRequirementCompiler(
        capability_resolver=RequirementToCapabilityResolver.governed_fixture(),
        require_capability_index=True,
    ).compile_for_scenario(
        _declared_source_scenario("labor.unemployment_rate", "total_labor_force")
    )
    store = artifacts.FileSystemCAS(tmp_path / "cas").for_tenant(
        "tenant-compiler", cell_id="cell-compiler"
    )
    binding = persist_and_verify_data_requirement_compilation_report(
        store, report, expected_scenario_id=report.scenario_id
    )
    return store, report, binding


def test_current_writer_profile_and_explicit_historical_content_read(tmp_path: Path) -> None:
    store, report, binding = _persisted_report(tmp_path)
    assert binding.compiler_report_ref.manifest_profile_sha256 is not None
    assert (
        validate_persisted_data_requirement_compilation_report(
            store, binding, expected_report=report, require_selected_writer_profile=True
        )
        == ()
    )
    historical = binding.model_copy(
        update={
            "compiler_report_ref": binding.compiler_report_ref.model_copy(
                update={"manifest_profile_sha256": None}
            )
        }
    )
    assert validate_persisted_data_requirement_compilation_report(store, historical) == ()
    assert validate_persisted_data_requirement_compilation_report(
        store, historical, require_selected_writer_profile=True
    ) == ({"code": "n7_compiler_report_selected_writer_profile_missing"},)


@pytest.mark.parametrize("field", ["producer", "env", "inputs", "canon"])
def test_same_bytes_selected_foreign_profile_does_not_satisfy_current_writer(
    tmp_path: Path, field: str
) -> None:
    store, report, binding = _persisted_report(tmp_path)
    ref = binding.compiler_report_ref
    manifest = store.get_manifest(ref)
    raw = store.get_bytes(ref)
    options = {
        "kind": manifest.kind,
        "media_type": manifest.media_type,
        "schema": manifest.artifact_schema,
        "producer": manifest.producer,
        "env": manifest.env,
        "inputs": manifest.inputs,
        "canon": manifest.canon,
        "governance": manifest.governance,
        "tenant_context": manifest.tenant_context,
        "same_input_closure": manifest.same_input_closure,
        "authority": manifest.authority,
        "warnings": manifest.warnings,
    }
    if field == "producer":
        options[field] = artifacts.ProducerInfo(component="foreign.compiler", version="1")
    elif field == "env":
        options[field] = artifacts.EnvInfo(
            python="foreign-python", platform="foreign-platform", deps_lock_hash="foreign-lock"
        )
    elif field == "inputs":
        upstream = store.put_json(
            {"test_owned_unrelated_input": True},
            artifacts.PutOptions(kind="fixture.unrelated_input", media_type="application/json"),
            return_selected_profile=True,
        )
        options[field] = [artifacts.input_ref_from_artifact_ref(upstream, role="foreign-input")]
    else:
        assert raw.isascii()
        options[field] = manifest.canon.model_copy(
            update={"ensure_ascii": not manifest.canon.ensure_ascii}
        )
    sibling = store.put_bytes(raw, artifacts.PutOptions(**options), return_selected_profile=True)
    assert sibling.artifact_id == ref.artifact_id
    assert sibling.manifest_profile_sha256 != ref.manifest_profile_sha256
    assert store.get_bytes(sibling) == raw
    foreign = binding.model_copy(update={"compiler_report_ref": sibling})
    # The old mode promises typed content/digest, not complete writer conformity.
    assert (
        validate_persisted_data_requirement_compilation_report(
            store, foreign, expected_report=report
        )
        == ()
    )
    assert validate_persisted_data_requirement_compilation_report(
        store, foreign, expected_report=report, require_selected_writer_profile=True
    ) == ({"code": "n7_compiler_report_selected_writer_profile_mismatch"},)
