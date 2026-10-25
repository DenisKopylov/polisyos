from __future__ import annotations

from pathlib import Path

import pytest

from polisyos.core.artifacts import ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.ir.analytics.causal import CausalMethod
from polisyos.ir.analytics.evidence_bundle import load_causal_evidence_bundle
from polisyos.ir.analytics.hte import (
    HTEResult,
    HTEResultRef,
    load_hte_result,
    persist_hte_result,
)
from polisyos.ir.analytics.ncm import NCMSpec, load_ncm_spec, persist_ncm_spec
from polisyos.ir.analytics.simulation_proof_bridge import (
    SimulationCertificationStatus,
    build_simulation_proof_bridge_artifacts,
    load_simulation_calibration_receipt,
    load_simulation_proof_bridge,
)
from polisyos.ir.model_layer.canon import CanonSpec, CanonViolation


def _small_hte_result() -> HTEResult:
    return HTEResult.from_estimates(
        method=CausalMethod.CAUSAL_FOREST,
        ate=0.25,
        ate_ci_lower=0.1,
        ate_ci_upper=0.4,
        cate_values=[0.1, 0.2, 0.3],
        n_treated=1,
        n_control=2,
    )


def test_hte_owner_round_trip_reopens_cas_and_refuses_tuple_and_profile_drift(
    tmp_path: Path,
) -> None:
    cas_path = tmp_path / "hte-owner-cas"
    cas = FileSystemCAS(cas_path)
    writer = ensure_ir_artifact_store(cas)
    result = _small_hte_result()

    ref = persist_hte_result(writer, result)
    fresh_reader = ensure_ir_artifact_store(FileSystemCAS(cas_path))

    loaded = load_hte_result(fresh_reader, ref)

    assert type(loaded) is HTEResult
    assert loaded == result
    assert ref.manifest_profile_sha256 is not None

    class CountingWriter:
        def __init__(self, inner: object) -> None:
            self.inner = inner
            self.put_calls = 0

        def __getattr__(self, name: str) -> object:
            return getattr(self.inner, name)

        def put_json(self, *args: object, **kwargs: object) -> object:
            self.put_calls += 1
            return self.inner.put_json(*args, **kwargs)

    counted_writer = CountingWriter(writer)
    with pytest.raises(
        CanonViolation,
        match="ir_owned_artifact_write_override_unregistered",
    ):
        persist_hte_result(counted_writer, result, schema_version="9.9")
    assert counted_writer.put_calls == 0

    wrong_profile_ref = cas.put_json(
        result.model_dump(mode="json"),
        PutOptions(
            kind="ir.hte_result",
            media_type="application/json",
            schema=SchemaInfo(name="ir.hte_result", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False, exclude_none=False),
    )
    wrong_profile = HTEResultRef.model_validate(wrong_profile_ref.model_dump(mode="json"))
    with pytest.raises(CanonViolation, match="ir_owned_artifact_profile_refused"):
        load_hte_result(fresh_reader, wrong_profile)


def test_ncm_owner_round_trip_reopens_cas(tmp_path: Path) -> None:
    cas_path = tmp_path / "ncm-owner-cas"
    writer = ensure_ir_artifact_store(FileSystemCAS(cas_path))
    spec = NCMSpec()

    ref = persist_ncm_spec(writer, spec)
    fresh_reader = ensure_ir_artifact_store(FileSystemCAS(cas_path))

    loaded = load_ncm_spec(fresh_reader, ref)

    assert type(loaded) is NCMSpec
    assert loaded == spec
    assert ref.manifest_profile_sha256 is not None


def test_simulation_owner_chain_reopens_cas_with_limited_statuses(tmp_path: Path) -> None:
    cas_path = tmp_path / "simulation-owner-cas"
    cas = FileSystemCAS(cas_path)
    simulation_ref = cas.put_json(
        {"schema_version": "1.3", "notes": []},
        PutOptions(
            kind="foundry.simulation_result",
            media_type="application/json",
            schema=SchemaInfo(name="foundry.simulation_result", version="1.3"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    metrics_ref = cas.put_json(
        {"values": {"loss": "1.0"}},
        PutOptions(
            kind="foundry.metrics",
            media_type="application/json",
            schema=SchemaInfo(name="foundry.metrics", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    writer = ensure_ir_artifact_store(cas)

    output = build_simulation_proof_bridge_artifacts(
        writer,
        run_id="R_runtime_owner_fresh_consumer",
        simulation_result_ref=simulation_ref,
        metrics_ref=metrics_ref,
    )
    fresh_reader = ensure_ir_artifact_store(FileSystemCAS(cas_path))

    receipt = load_simulation_calibration_receipt(
        fresh_reader,
        output.calibration_receipt_ref,
    )
    bridge = load_simulation_proof_bridge(fresh_reader, output.bridge_ref)
    evidence = load_causal_evidence_bundle(fresh_reader, bridge.evidence_bundle_ref)

    assert receipt.accepted is False
    assert receipt.source == "default_unverified"
    assert bridge.certification_status is SimulationCertificationStatus.SCENARIO
    assert bridge.proof_status == "non_identified"
    assert bridge.calibration_status == "unverified"
    assert evidence.twin_network_result_ref is None
