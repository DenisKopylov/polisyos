"""Independent byte/ID and selected-reader controls for versioned numeric artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef, CanonInfo, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.foundry.methods.artifacts import (
    ChainArtifact,
    DeviceInfo,
    ExecutionEvidence,
    MethodTiming,
    SlotBindingRecord,
    load_compiled_chain,
    load_execution_evidence,
    store_chain_artifact,
    store_execution_evidence,
)

PROFILE = "core-canon-0.2.0-finite-floats-legacy-null-v1"
SPEC = CanonSpec(version="0.2.0", forbid_floats=False, exclude_none=True)


def _json_bytes(payload):
    # Independent JSON literal projection: does not call producer/Core canonical helpers.
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _empty_chain(**kwargs):
    return ChainArtifact(
        chain_id=UUID(int=1),
        chain_hash="c" * 32,
        topology_hash="d" * 32,
        method_fqns=(),
        method_artifact_ids=(),
        nodes=(),
        bindings=(),
        execution_order=(),
        warnings=(),
        composed_at=datetime(2026, 1, 1, tzinfo=UTC),
        **kwargs,
    )


def _evidence():
    start = datetime(2026, 1, 1, tzinfo=UTC)
    return ExecutionEvidence(
        execution_id=UUID(int=1),
        chain_artifact_id="a" * 64,
        input_state_hash="input",
        input_params_hash="params",
        output_state_hash="output",
        started_at=start,
        completed_at=start + timedelta(seconds=1.25),
        method_timings=(MethodTiming("test.method@1.0.0", "node", 0.5),),
        device_info=DeviceInfo("cpu", 1, "float64", "test-jax", "test-jaxlib", backend="numpy"),
    )


def test_valid_nonnumeric_legacy_bytes_and_id_match_independent_golden():
    expected = _json_bytes(
        {
            "schema_version": "1.0.0",
            "chain_hash": "c" * 32,
            "topology_hash": "d" * 32,
            "method_fqns": [],
            "method_artifact_ids": [],
            "nodes": [],
            "bindings": [],
            "execution_order": [],
            "warnings": [],
        }
    )
    record = _empty_chain()
    assert record.to_canonical_bytes() == expected
    assert record.artifact_id == hashlib.sha256(expected).hexdigest()
    assert record.schema_version == "1.0.0"
    restored = ChainArtifact.from_canonical_bytes(expected)
    assert restored.to_canonical_bytes() == expected
    assert restored.artifact_id == hashlib.sha256(expected).hexdigest()


def test_numeric_evidence_matches_independent_golden():
    expected = _json_bytes(
        {
            "schema_version": "1.1.0",
            "canonical_profile": PROFILE,
            "execution_id": str(UUID(int=1)),
            "chain_artifact_id": "a" * 64,
            "input_state_hash": "input",
            "input_params_hash": "params",
            "output_state_hash": "output",
            "input_state_artifact_ids": [],
            "output_state_artifact_ids": [],
            "started_at": "2026-01-01T00:00:00+00:00",
            "completed_at": "2026-01-01T00:00:01.250000+00:00",
            "duration_seconds": {"_type": "float", "repr": "1.25"},
            "method_timings": [
                {
                    "method_fqn": "test.method@1.0.0",
                    "node_id": "node",
                    "duration_seconds": {"_type": "float", "repr": "0.5"},
                }
            ],
            "device_info": {
                "platform": "cpu",
                "device_count": 1,
                "precision": "float64",
                "jax_version": "test-jax",
                "jaxlib_version": "test-jaxlib",
                "backend": "numpy",
                "library_versions": {},
                "solver_name": "",
                "solver_version": "",
            },
            "params_artifact_id": None,
            "rng_artifact_id": None,
            "rng_key_used": None,
            "error_message": None,
            "success": True,
        }
    )
    record = _evidence()
    assert record.to_canonical_bytes() == expected
    assert record.artifact_id == hashlib.sha256(expected).hexdigest()
    assert ExecutionEvidence.from_canonical_bytes(expected).to_canonical_bytes() == expected
    assert record.to_manifest().canon == CanonInfo.from_spec(SPEC)


def test_selected_evidence_cas_is_read_by_fresh_process(tmp_path, record_property):
    cas = FileSystemCAS(tmp_path)
    record = _evidence()
    selected = store_execution_evidence(cas, record, return_selected_profile=True)
    manifest = FileSystemCAS(tmp_path).get_manifest(selected)
    assert manifest.artifact_schema.version == "1.1.0"
    assert manifest.canon == record.to_manifest().canon == CanonInfo.from_spec(SPEC)
    assert (
        load_execution_evidence(FileSystemCAS(tmp_path), selected).artifact_id == record.artifact_id
    )
    program = """import sys
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.artifacts import load_execution_evidence
record=load_execution_evidence(FileSystemCAS(sys.argv[1]),ArtifactRef.model_validate_json(sys.argv[2]))
assert record.duration_seconds==1.25 and record.method_timings[0].duration_seconds==0.5
print("E02_EVIDENCE="+record.artifact_id)
"""
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-B", "-c", program, str(tmp_path), selected.model_dump_json()],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        check=False,
    )
    record_property("fresh_reader_stdout", result.stdout)
    record_property("fresh_reader_stderr", result.stderr)
    assert result.returncode == 0, result.stderr
    assert "E02_EVIDENCE=" + record.artifact_id in result.stdout


def test_numeric_recipe_only_chain_uses_new_profile_and_cannot_be_executed(tmp_path):
    record = replace(
        _empty_chain(),
        bindings=(SlotBindingRecord("source", "x", "target", "y", conversion_factor=0.5),),
    )
    payload = json.loads(record.to_canonical_bytes())
    assert payload["schema_version"] == "1.1.0" and payload["canonical_profile"] == PROFILE
    assert payload["bindings"][0]["conversion_factor"] == {"_type": "float", "repr": "0.5"}
    assert (
        ChainArtifact.from_canonical_bytes(record.to_canonical_bytes()).artifact_id
        == record.artifact_id
    )
    cas = FileSystemCAS(tmp_path)
    selected = store_chain_artifact(cas, record, return_selected_profile=True)
    assert (
        cas.get_manifest(selected).canon == record.to_manifest().canon == CanonInfo.from_spec(SPEC)
    )
    with pytest.raises(ValueError):
        load_compiled_chain(cas, selected)


def test_old_numeric_alias_bytes_remain_immutable_inspection_only(tmp_path):
    payload = json.loads(_empty_chain().to_canonical_bytes())
    payload["bindings"] = [
        {
            "source_method": "source",
            "source_slot": "x",
            "target_method": "target",
            "target_slot": "y",
            "conversion_factor": {"_type": "float_hex", "value": "0x1.0000000000000p-1"},
            "requires_fx_rate": False,
        }
    ]
    original = _json_bytes(payload)
    cas = FileSystemCAS(tmp_path)
    selected = cas.put_bytes(
        original,
        PutOptions(
            kind="foundry.chain_artifact",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.foundry.chain_artifact", version="1.0.0"),
        ),
        return_selected_profile=True,
    )
    assert cas.get_bytes(selected) == original
    assert selected.artifact_id.hex == hashlib.sha256(original).hexdigest()
    with pytest.raises(ValueError):
        ChainArtifact.from_canonical_bytes(original)
    with pytest.raises(ValueError, match="historical_chain"):
        load_compiled_chain(cas, selected)
    assert FileSystemCAS(tmp_path).get_bytes(selected) == original


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf"), "0.5", True, 10**400])
def test_nonnumeric_and_nonfinite_measurements_refuse_at_artifact_owner(value):
    with pytest.raises(ValueError, match="finite_real"):
        replace(_evidence(), method_timings=(MethodTiming("test.method", "n", value),))
    with pytest.raises(ValueError, match="finite_real"):
        replace(
            _empty_chain(),
            bindings=(SlotBindingRecord("s", "x", "t", "y", conversion_factor=value),),
        )


@pytest.mark.parametrize(
    "mutation", ["profile", "schema", "duration", "numeric-string", "alias", "unknown"]
)
def test_corrupt_evidence_bytes_refuse(mutation):
    payload = json.loads(_evidence().to_canonical_bytes())
    if mutation == "profile":
        payload["canonical_profile"] = "unavailable"
    elif mutation == "schema":
        payload["schema_version"] = "1.0.0"
    elif mutation == "duration":
        payload["duration_seconds"] = {"_type": "float", "repr": "999"}
    elif mutation == "numeric-string":
        payload["method_timings"][0]["duration_seconds"] = "0.5"
    elif mutation == "alias":
        payload["method_timings"][0]["duration_seconds"] = {
            "_type": "float_hex",
            "value": "0x1.0000000000000p-1",
        }
    else:
        payload["unexpected"] = True
    with pytest.raises(ValueError):
        ExecutionEvidence.from_canonical_bytes(_json_bytes(payload))


def test_selected_evidence_profile_drift_and_unselected_ref_refuse(tmp_path):
    record = _evidence()
    cas = FileSystemCAS(tmp_path)
    selected = cas.put_bytes(
        record.to_canonical_bytes(),
        PutOptions(
            kind="foundry.execution_evidence",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.foundry.execution_evidence", version="1.1.0"),
            canon=CanonInfo.from_spec(
                CanonSpec(version="0.2.0", forbid_floats=False, exclude_none=False)
            ),
        ),
        return_selected_profile=True,
    )
    with pytest.raises(ValueError, match="profile_mismatch"):
        load_execution_evidence(cas, selected)
    unselected = ArtifactRef(
        artifact_id=selected.artifact_id, kind=selected.kind, media_type=selected.media_type
    )
    with pytest.raises(ValueError, match="profile_required"):
        load_execution_evidence(cas, unselected)


def test_evidence_snapshots_mutable_library_versions():
    versions = {"numpy": "original"}
    record = replace(
        _evidence(), device_info=replace(_evidence().device_info, library_versions=versions)
    )
    before = record.to_canonical_bytes()
    versions["numpy"] = "changed"
    assert record.to_canonical_bytes() == before
    with pytest.raises(TypeError):
        record.device_info.library_versions["numpy"] = "changed"


@pytest.mark.parametrize(
    "field,value",
    [
        ("device_count", "not-an-int"),
        ("device_count", True),
        ("platform", 10),
        ("library_versions", {"numpy": 123}),
    ],
)
def test_wrongly_typed_device_fields_refuse(field, value):
    payload = json.loads(_evidence().to_canonical_bytes())
    payload["device_info"][field] = value
    with pytest.raises(ValueError):
        ExecutionEvidence.from_canonical_bytes(_json_bytes(payload))


@pytest.mark.parametrize("field,value", [("method_fqn", 123), ("node_id", 123)])
def test_wrongly_typed_timing_fields_refuse(field, value):
    payload = json.loads(_evidence().to_canonical_bytes())
    payload["method_timings"][0][field] = value
    with pytest.raises(ValueError):
        ExecutionEvidence.from_canonical_bytes(_json_bytes(payload))


def test_selected_evidence_missing_provenance_edges_refuse(tmp_path):
    record = _evidence()
    cas = FileSystemCAS(tmp_path)
    selected = cas.put_bytes(
        record.to_canonical_bytes(),
        PutOptions(
            kind="foundry.execution_evidence",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.foundry.execution_evidence", version="1.1.0"),
            canon=CanonInfo.from_spec(SPEC),
            inputs=[],
        ),
        return_selected_profile=True,
    )
    with pytest.raises(ValueError, match="input_lineage_mismatch"):
        load_execution_evidence(cas, selected)


class MutableFloat(float):
    def __new__(cls):
        instance = super().__new__(cls, 0.5)
        instance.current = 0.5
        return instance

    def __float__(self):
        return self.current


def test_numeric_artifacts_snapshot_mutable_real_subclasses():
    number = MutableFloat()
    evidence = replace(_evidence(), method_timings=(MethodTiming("method", "n", number, number),))
    chain = replace(
        _empty_chain(), bindings=(SlotBindingRecord("s", "x", "t", "y", conversion_factor=number),)
    )
    before = evidence.to_canonical_bytes(), chain.to_canonical_bytes()
    identities = evidence.artifact_id, chain.artifact_id
    number.current = 999.0
    assert (evidence.to_canonical_bytes(), chain.to_canonical_bytes()) == before
    assert (evidence.artifact_id, chain.artifact_id) == identities
    assert evidence.method_timings[0].duration_seconds == chain.bindings[0].conversion_factor == 0.5
