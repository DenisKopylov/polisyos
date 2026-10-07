"""SCM version/catalog custody, with explicit legacy and genuine worker profiles."""

import json
import os
from pathlib import Path

import numpy as np
import pytest

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.foundry import causal_worker_execution_context, validate_source_bound_gcm_spec
from polisyos.foundry.methods.catalog.causal import _dowhy_worker as worker_bridge
from polisyos.foundry.methods.catalog.causal.gcm_fit import HybridSCMFit
from polisyos.foundry.methods.catalog.causal.protocols import SCMFitData
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
from polisyos.ir.analytics.structural_causal_model import (
    StructuralCausalModelSpec,
    load_structural_causal_model_spec,
    persist_structural_causal_model_spec,
)
from polisyos.ir.migrations.base import CompatibilityMode, negotiate_schema_version
from polisyos.ir.registry.refs import StructuralCausalModelSpecRef
from polisyos.ir.schemas.catalog import inspect_ir_schema


def _root_graph():
    return CausalGraphModel(graph_type=GraphType.DAG, nodes=["X"], edges=[])


def test_current_scm_default_and_real_catalog_advertise_same_version():
    model = StructuralCausalModelSpec(graph=_root_graph(), fit_method="manual")
    entry = inspect_ir_schema("StructuralCausalModelSpec")
    assert model.schema_version == entry.schema_version == "1.1"
    assert entry.compat_mode == CompatibilityMode.BACKWARD.value
    assert entry.compat_readable_versions == ("1.0",)
    decision = negotiate_schema_version("structural_causal_model_spec", "1.0", "1.1")
    assert decision.can_read and not decision.migration_required
    assert not negotiate_schema_version("structural_causal_model_spec", "1.1", "1.0").can_read


def test_current_scm_generated_snapshot_and_manifest_match_catalog():
    root = Path(__file__).resolve().parents[3]
    snapshot = json.loads(
        (root / "schemas/snapshots/ir/structural_causal_model_spec.schema.json").read_text()
    )
    manifest = json.loads((root / "schemas/snapshots/ir/_manifest.json").read_text())
    assert snapshot["properties"]["schema_version"]["default"] == "1.1"
    assert manifest["models"]["structural_causal_model_spec"]["schema_version"] == "1.1"


@pytest.mark.parametrize("explicit_version", [True, False])
def test_actual_legacy_manifest_preserves_version_without_worker_authority(
    tmp_path, explicit_version
):
    store = FileSystemCAS(tmp_path)
    payload = StructuralCausalModelSpec(
        schema_version="1.0", graph=_root_graph(), fit_method="manual"
    ).model_dump(mode="json")
    if not explicit_version:
        payload.pop("schema_version")
    raw = store.put_json(
        payload,
        PutOptions(
            kind="ir.structural_causal_model_spec",
            media_type="application/json",
            schema=SchemaInfo(name="ir.structural_causal_model_spec", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    ref = StructuralCausalModelSpecRef.model_validate(raw.model_dump(mode="json"))
    loaded = load_structural_causal_model_spec(FileSystemCAS(tmp_path), ref)
    assert loaded.schema_version == "1.0"
    assert (
        loaded.fit_method == "manual"
        and loaded.fit_provenance is None
        and loaded.training_rows is None
    )
    rewritten = persist_structural_causal_model_spec(store, loaded)
    assert store.get_manifest(rewritten.artifact_id).artifact_schema.version == "1.0"
    assert load_structural_causal_model_spec(FileSystemCAS(tmp_path), rewritten) == loaded


def test_current_default_gcm_cannot_inherit_legacy_missing_worker_marker():
    with pytest.raises(
        ValueError, match="selected GCM fit requires training rows and observed worker provenance"
    ):
        StructuralCausalModelSpec(graph=_root_graph(), fit_method="gcm", fitted=True)


def test_new_manual_model_cas_envelope_uses_current_version(tmp_path):
    store = FileSystemCAS(tmp_path)
    model = StructuralCausalModelSpec(graph=_root_graph(), fit_method="manual")
    ref = persist_structural_causal_model_spec(store, model)
    assert store.get_manifest(ref.artifact_id).artifact_schema.version == "1.1"
    loaded = load_structural_causal_model_spec(FileSystemCAS(tmp_path), ref)
    assert loaded == model and loaded.fit_provenance is None


def test_actual_selected_gcm_producer_manifest_and_fresh_reader(monkeypatch, tmp_path):
    interpreter = Path(
        os.environ.get(
            "POLISYOS_DOWHY_WORKER_PYTHON",
            str(worker_bridge._worker_directory() / ".venv/bin/python"),
        )
    )
    assert interpreter.is_file(), "Genuine locked worker absent: no backend PASS"
    monkeypatch.setenv("POLISYOS_DOWHY_WORKER_PYTHON", str(interpreter))
    rng = np.random.default_rng(20261006)
    x = rng.normal(size=64)
    y = 2 * x + rng.normal(scale=0.2, size=64)
    state = SCMFitData(
        data=np.column_stack([x, y]),
        column_names=["X", "Y"],
        graph=CausalGraphModel(
            graph_type=GraphType.DAG, nodes=["X", "Y"], edges=[CausalEdge(src="X", dst="Y")]
        ),
        metadata={"input_scope": "known_synthetic_dgp", "sampling_unit": "iid_observation_row"},
    )
    store = FileSystemCAS(tmp_path)
    source = store.put_json(
        state.model_dump(mode="json"),
        PutOptions(
            kind="tests.SCMFitData",
            media_type="application/json",
            schema=SchemaInfo(name="tests.SCMFitData", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    with causal_worker_execution_context(store=store, source_ref=source):
        output = HybridSCMFit.pure_step(state, {"__seed__": 41})
    model = output["scm_spec"]
    assert (
        model.schema_version
        == inspect_ir_schema("StructuralCausalModelSpec").schema_version
        == "1.1"
    )
    assert model.fit_method == "gcm" and model.fit_provenance.versions["dowhy"] == "0.14"
    assert model.fit_provenance.worker_response["result"]["fit_function"] == "dowhy.gcm.fit"
    expected = np.linalg.lstsq(np.column_stack([np.ones(64), x]), y, rcond=None)[0]
    assert model.mechanisms[1].family_params["coefficients"]["X"] == pytest.approx(
        expected[1], abs=1e-12
    )
    ref = persist_structural_causal_model_spec(store, model)
    assert store.get_manifest(ref.artifact_id).artifact_schema.version == "1.1"
    fresh_store = FileSystemCAS(tmp_path)
    loaded = load_structural_causal_model_spec(fresh_store, ref)
    validate_source_bound_gcm_spec(loaded, fresh_store)
    assert loaded.model_dump(mode="json") == model.model_dump(mode="json")
