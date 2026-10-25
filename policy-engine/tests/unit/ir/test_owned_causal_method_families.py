from __future__ import annotations

import pytest
from pydantic import BaseModel

from polisyos.core.artifacts import ensure_ir_artifact_store
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.interference import (
    InteractionComplex,
    InterferenceCertificate,
    MAUPInvarianceCertificate,
    SpatialHodgeDiagnostics,
    load_interaction_complex,
    persist_interaction_complex,
    persist_interference_certificate,
    persist_maup_invariance_certificate,
    persist_spatial_hodge_diagnostics,
)
from polisyos.ir.analytics.interventions import (
    InterventionCertificate,
    InterventionQuery,
    persist_intervention_certificate,
    persist_intervention_query,
)
from polisyos.ir.analytics.invariance import (
    RegimeShiftIdentificationCertificate,
    persist_regime_shift_identification_certificate,
)
from polisyos.ir.analytics.latent_bridge_synthesis import (
    LatentBridgeHypothesis,
    persist_latent_bridge_hypothesis,
)
from polisyos.ir.analytics.local_independence import (
    LocalIndependenceWeightingCertificate,
    persist_local_independence_weighting_certificate,
)
from polisyos.ir.model_layer.canon import CanonViolation
from polisyos.ir.registry.refs import ArtifactRefModel


class _CountingFileSystemCAS(FileSystemCAS):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.put_count = 0

    def put_bytes(self, data, opts, *, return_selected_profile=False):
        self.put_count += 1
        return super().put_bytes(
            data,
            opts,
            return_selected_profile=return_selected_profile,
        )


def _interaction_complex() -> InteractionComplex:
    return InteractionComplex(
        nodes=("A", "Y"),
        hyperedges=(("A", "Y"),),
        exposure_operator_ref=ArtifactRefModel(
            artifact_id="sha256:" + "a" * 64,
            kind="ir.interference_exposure_operator",
            media_type="application/json",
        ),
        reduction_policy="pairwise_projection",
    )


def test_owner_persist_round_trip_uses_fresh_typed_reader(tmp_path) -> None:
    store = _CountingFileSystemCAS(tmp_path / "cas")
    ref = persist_interaction_complex(ensure_ir_artifact_store(store), _interaction_complex())

    fresh = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))
    assert load_interaction_complex(fresh, ref) == _interaction_complex()
    assert store.put_count == 1


@pytest.mark.parametrize(
    ("schema_name", "schema_version"),
    [("", "1.0"), ("ir.interaction_complex", "99.0")],
)
def test_invalid_write_override_refuses_before_cas_mutation(
    tmp_path, schema_name: str, schema_version: str
) -> None:
    store = _CountingFileSystemCAS(tmp_path / "cas")

    with pytest.raises(CanonViolation):
        persist_interaction_complex(
            ensure_ir_artifact_store(store),
            _interaction_complex(),
            schema_name=schema_name,
            schema_version=schema_version,
        )

    assert store.put_count == 0


@pytest.mark.parametrize(
    ("persist", "model_type"),
    [
        (persist_interaction_complex, InteractionComplex),
        (persist_interference_certificate, InterferenceCertificate),
        (persist_maup_invariance_certificate, MAUPInvarianceCertificate),
        (persist_spatial_hodge_diagnostics, SpatialHodgeDiagnostics),
        (persist_intervention_query, InterventionQuery),
        (persist_intervention_certificate, InterventionCertificate),
        (persist_regime_shift_identification_certificate, RegimeShiftIdentificationCertificate),
        (persist_latent_bridge_hypothesis, LatentBridgeHypothesis),
        (persist_local_independence_weighting_certificate, LocalIndependenceWeightingCertificate),
    ],
    ids=[
        "interaction-complex",
        "interference-certificate",
        "maup-certificate",
        "spatial-hodge",
        "intervention-query",
        "intervention-certificate",
        "regime-shift",
        "latent-bridge",
        "local-independence",
    ],
)
@pytest.mark.parametrize(
    ("override", "reason"),
    [
        ({"schema_name": ""}, "ir_owned_artifact_write_override_invalid"),
        ({"schema_version": "99.0"}, "ir_owned_artifact_write_override_unregistered"),
    ],
    ids=["empty-name", "unknown-version"],
)
def test_all_public_schema_override_writers_refuse_before_cas_mutation(
    tmp_path, persist, model_type: type[BaseModel], override: dict[str, str], reason: str
) -> None:
    store = _CountingFileSystemCAS(tmp_path / "cas")

    with pytest.raises(CanonViolation, match=f"^{reason}$"):
        persist(
            ensure_ir_artifact_store(store),
            model_type.model_construct(),
            **override,
        )

    assert store.put_count == 0
