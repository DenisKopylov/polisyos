from __future__ import annotations

import numpy as np
import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.catalog.spatial.protocols import SpatialResult
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.foundry.methods.spatial import (
    AccessibilityData,
    GravityFlowData,
    SpatialData,
    ensure_spatial_methods_registered,
)
from polisyos.ir.analytics.interference import (
    MAUPInvarianceCertificate,
    MAUPPartitionCheck,
    SpatialHodgeDiagnostics,
    SpatialHodgeScaleProfile,
)
from polisyos.ir.analytics.dependence_structure import load_dependence_structure


@pytest.fixture(autouse=True)
def _reset_globals():
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    yield
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()


def _spatial_state() -> SpatialData:
    rng = np.random.default_rng(151)
    coords = np.array([[0.0, 0.0], [0.0, 1.0], [1.0, 0.0], [1.0, 1.0], [0.5, 0.2], [0.2, 0.8]])
    weights = np.array(
        [
            [0, 1, 1, 0, 1, 0],
            [1, 0, 0, 1, 0, 1],
            [1, 0, 0, 1, 1, 0],
            [0, 1, 1, 0, 0, 1],
            [1, 0, 1, 0, 0, 1],
            [0, 1, 0, 1, 1, 0],
        ],
        dtype=float,
    )
    features = np.column_stack([np.ones(6), rng.normal(size=6), rng.normal(size=6)])
    values = 0.5 + features @ np.array([0.2, 1.1, -0.7]) + rng.normal(scale=0.05, size=6)
    return SpatialData(coordinates=coords, values=values, features=features, weights_matrix=weights)


def test_spatial_registration_and_core_methods_run() -> None:
    pytest.importorskip("scipy")
    pytest.importorskip("statsmodels")

    ensure_spatial_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    signatures = [sig for sig in registry.query() if sig.namespace.startswith("spatial.")]
    assert {sig.name for sig in signatures} == {
        "moran_i",
        "gwr",
        "spatial_durbin",
        "gravity_model",
        "accessibility_index",
        "gaussian_process_kriging",
        "idw",
        "slx",
        "sarar",
        "two_step_fca",
        "smsm",
        "maup_profile",
        "zone_balance",
    }

    state = _spatial_state()
    for fqn in (
        "spatial.autocorrelation.moran_i@1.0.0",
        "spatial.regression.gwr@1.0.0",
        "spatial.regression.spatial_durbin@1.0.0",
    ):
        method_cls = registry.get(fqn)
        result = dispatcher.dispatch(
            method_class=method_cls,
            signature=method_cls.signature,
            state=state,
            params={},
            seed=153,
        )
        assert result.output["result"].method_name


def test_gravity_model_and_accessibility_index_run() -> None:
    pytest.importorskip("scipy")
    pytest.importorskip("statsmodels")

    ensure_spatial_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()

    gravity_cls = registry.get("spatial.flows.gravity_model@1.0.0")
    gravity_result = dispatcher.dispatch(
        method_class=gravity_cls,
        signature=gravity_cls.signature,
        state=GravityFlowData(
            origin_coords=np.array([[0.0, 0.0], [0.0, 1.0], [1.0, 0.0], [1.0, 1.0]]),
            destination_coords=np.array([[0.0, 0.5], [1.0, 0.5], [0.5, 0.0], [0.5, 1.0]]),
            origin_mass=np.array([10.0, 20.0, 15.0, 18.0]),
            destination_mass=np.array([12.0, 18.0, 17.0, 13.0]),
            observed_flows=np.array(
                [
                    [0.5, 5.0, 7.0, 4.0],
                    [4.0, 0.7, 6.0, 3.0],
                    [8.0, 5.0, 0.6, 2.0],
                    [3.0, 4.0, 5.0, 0.8],
                ]
            ),
        ),
        params={},
        seed=157,
    )
    assert "distance_decay" in gravity_result.output["result"].statistics

    access_cls = registry.get("spatial.accessibility.accessibility_index@1.0.0")
    access_result = dispatcher.dispatch(
        method_class=access_cls,
        signature=access_cls.signature,
        state=AccessibilityData(
            origin_coords=np.array([[0.0, 0.0], [0.0, 1.0], [1.0, 0.0], [1.0, 1.0]]),
            destination_coords=np.array([[0.0, 0.5], [1.0, 0.5], [0.5, 0.0], [0.5, 1.0]]),
            opportunity_mass=np.array([100.0, 120.0, 80.0, 95.0]),
            travel_cost_matrix=np.array(
                [
                    [5.0, 8.0, 12.0, 6.0],
                    [7.0, 4.0, 10.0, 5.0],
                    [11.0, 9.0, 3.0, 7.0],
                    [6.0, 5.0, 7.0, 4.0],
                ]
            ),
        ),
        params={"decay": 1.2},
        seed=159,
    )
    assert np.asarray(access_result.output["scores"], dtype=float).shape == (4,)


def test_spatial_methods_emit_areal_dependence_ref(tmp_path) -> None:
    pytest.importorskip("scipy")
    pytest.importorskip("statsmodels")

    ensure_spatial_methods_registered()
    registry = MethodRegistry.get_instance()
    store = FileSystemCAS(tmp_path / "cas")

    moran_cls = registry.get("spatial.autocorrelation.moran_i@1.0.0")
    result = moran_cls.pure_step(_spatial_state(), {"artifact_store": store})

    dependence_ref = result["result"].dependence_ref
    assert dependence_ref is not None
    loaded = load_dependence_structure(store, dependence_ref)
    assert loaded.regime == "areal"
    assert loaded.source_method == "spatial.autocorrelation.moran_i"


def test_advanced_spatial_methods_run() -> None:
    ensure_spatial_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()

    kriging_cls = registry.get("spatial.interpolation.gaussian_process_kriging@1.0.0")
    kriging_result = dispatcher.dispatch(
        method_class=kriging_cls,
        signature=kriging_cls.signature,
        state={
            "coordinates": np.array(
                [[0.0, 0.0], [0.0, 1.0], [1.0, 0.0], [1.0, 1.0], [0.5, 0.4]],
                dtype=float,
            ),
            "values": np.array([1.0, 1.8, 2.1, 2.9, 1.7], dtype=float),
            "prediction_coords": np.array([[0.2, 0.2], [0.8, 0.8], [0.5, 0.7]], dtype=float),
        },
        params={"length_scale": 0.7, "noise_level": 0.02},
        seed=163,
    )
    assert np.asarray(kriging_result.output["result"].fitted_values, dtype=float).shape == (3,)
    assert np.asarray(kriging_result.output["result"].scores, dtype=float).shape == (3,)

    idw_cls = registry.get("spatial.interpolation.idw@1.0.0")
    idw_result = dispatcher.dispatch(
        method_class=idw_cls,
        signature=idw_cls.signature,
        state={
            "coordinates": np.array(
                [[0.0, 0.0], [0.0, 1.0], [1.0, 0.0], [1.0, 1.0], [0.5, 0.4]],
                dtype=float,
            ),
            "values": np.array([1.0, 1.8, 2.1, 2.9, 1.7], dtype=float),
            "prediction_coords": np.array([[0.2, 0.2], [0.8, 0.8], [0.5, 0.7]], dtype=float),
        },
        params={"power": 1.8},
        seed=164,
    )
    assert np.asarray(idw_result.output["result"].fitted_values, dtype=float).shape == (3,)
    assert np.asarray(idw_result.output["result"].scores, dtype=float).shape == (3,)

    slx_cls = registry.get("spatial.panel.slx@1.0.0")
    slx_result = dispatcher.dispatch(
        method_class=slx_cls,
        signature=slx_cls.signature,
        state={
            "coordinates": np.array(
                [[0.0, 0.0], [0.0, 1.0], [1.0, 0.0], [0.0, 0.0], [0.0, 1.0], [1.0, 0.0]],
                dtype=float,
            ),
            "values": np.array([2.0, 3.0, 4.0, 2.4, 3.4, 4.8], dtype=float),
            "features": np.array(
                [
                    [1.0, 0.2],
                    [0.7, 0.6],
                    [1.2, 0.1],
                    [1.1, 0.25],
                    [0.8, 0.7],
                    [1.4, 0.2],
                ],
                dtype=float,
            ),
            "unit_ids": np.array(["u0", "u1", "u2", "u0", "u1", "u2"]),
            "time_ids": np.array([0, 0, 0, 1, 1, 1]),
        },
        params={},
        seed=167,
    )
    assert slx_result.output["result"].method_name == "slx"
    assert slx_result.output["result"].statistics["spillover_effect_norm"] >= 0.0

    sarar_cls = registry.get("spatial.panel.sarar@1.0.0")
    sarar_result = dispatcher.dispatch(
        method_class=sarar_cls,
        signature=sarar_cls.signature,
        state={
            "coordinates": np.array(
                [[0.0, 0.0], [0.0, 1.0], [1.0, 0.0], [0.0, 0.0], [0.0, 1.0], [1.0, 0.0]],
                dtype=float,
            ),
            "values": np.array([2.0, 3.0, 4.0, 2.4, 3.4, 4.8], dtype=float),
            "features": np.array(
                [
                    [1.0, 0.2],
                    [0.7, 0.6],
                    [1.2, 0.1],
                    [1.1, 0.25],
                    [0.8, 0.7],
                    [1.4, 0.2],
                ],
                dtype=float,
            ),
            "unit_ids": np.array(["u0", "u1", "u2", "u0", "u1", "u2"]),
            "time_ids": np.array([0, 0, 0, 1, 1, 1]),
        },
        params={"max_iter": 5},
        seed=169,
    )
    assert sarar_result.output["result"].method_name == "sarar"
    assert abs(float(sarar_result.output["result"].statistics["rho"])) <= 0.95
    assert abs(float(sarar_result.output["result"].statistics["lambda"])) <= 0.95

    fca_cls = registry.get("spatial.accessibility.two_step_fca@1.0.0")
    fca_result = dispatcher.dispatch(
        method_class=fca_cls,
        signature=fca_cls.signature,
        state={
            "origin_coords": np.array([[0.0, 0.0], [0.0, 1.0], [1.0, 0.5]], dtype=float),
            "destination_coords": np.array([[0.1, 0.2], [0.9, 0.6]], dtype=float),
            "opportunity_mass": np.array([120.0, 80.0], dtype=float),
            "demand_mass": np.array([60.0, 45.0, 50.0], dtype=float),
        },
        params={"catchment_threshold": 1.2, "distance_decay": 0.2},
        seed=173,
    )
    assert np.asarray(fca_result.output["result"].scores, dtype=float).shape == (3,)

    smsm_cls = registry.get("spatial.microsim.smsm@1.0.0")
    smsm_result = dispatcher.dispatch(
        method_class=smsm_cls,
        signature=smsm_cls.signature,
        state={
            "sample_features": np.array(
                [
                    [1.0, 0.0, 1.0],
                    [0.0, 1.0, 1.0],
                    [1.0, 1.0, 0.0],
                    [0.5, 0.2, 0.1],
                ],
                dtype=float,
            ),
            "area_constraints": np.array([[30.0, 18.0, 20.0], [22.0, 25.0, 15.0]], dtype=float),
            "area_coordinates": np.array([[0.0, 0.0], [1.0, 1.0]], dtype=float),
        },
        params={"max_iter": 18},
        seed=179,
    )
    assert np.asarray(smsm_result.output["result"].scores, dtype=float).shape == (2, 4)

    zone_cls = registry.get("spatial.design.zone_balance@1.0.0")
    zone_result = dispatcher.dispatch(
        method_class=zone_cls,
        signature=zone_cls.signature,
        state={
            "coordinates": np.array(
                [[0.0, 0.0], [0.2, 0.9], [0.8, 0.1], [1.0, 1.0], [0.5, 0.4]],
                dtype=float,
            ),
            "values": np.array([10.0, 12.0, 9.0, 15.0, 11.0], dtype=float),
        },
        params={"n_zones": 2, "max_iter": 10},
        seed=181,
    )
    assert np.asarray(zone_result.output["result"].scores, dtype=float).shape == (5,)

    maup_cls = registry.get("spatial.design.maup_profile@1.0.0")
    maup_result = dispatcher.dispatch(
        method_class=maup_cls,
        signature=maup_cls.signature,
        state={
            "coordinates": np.array(
                [[0.0, 0.0], [0.2, 0.9], [0.8, 0.1], [1.0, 1.0], [0.5, 0.4], [0.7, 0.8]],
                dtype=float,
            ),
            "values": np.array([10.0, 12.0, 9.0, 15.0, 11.0, 13.0], dtype=float),
        },
        params={"min_zones": 2, "max_zones": 4, "n_restarts": 3},
        seed=183,
    )
    assert maup_result.output["result"].method_name == "maup_profile"
    assert np.asarray(maup_result.output["result"].scores, dtype=float).shape == (3, 4)


def test_spatial_result_accepts_typed_maup_and_hodge_fields() -> None:
    certificate = MAUPInvarianceCertificate(
        status="warn",
        estimand="spillover",
        effect_scale="mean_difference",
        micro_effect=0.42,
        partitions_tested=1,
        recommended_mode="micro_plus_safe_aggregate",
        near_invariance=True,
        partition_checks=(
            MAUPPartitionCheck(
                partition_id="district_v2",
                n_blocks=8,
                lumpability_residual=0.03,
                adjusted_p_value=0.61,
                ess_min=30.0,
            ),
        ),
    )
    diagnostics = SpatialHodgeDiagnostics(
        declared_scale_id="district",
        declared_zoning_id="admin_v1",
        aggregation_rule="mean",
        weight_spec="queen",
        exposure_mapping="kernel",
        zoning_hash="abc123",
        weight_hash="def456",
        aggregation_hash="ghi789",
        eta_grad=0.6,
        eta_curl=0.2,
        eta_harm=0.2,
        dominant_component="grad",
        profiles=(
            SpatialHodgeScaleProfile(
                scale_id="district",
                zoning_id="admin_v1",
                aggregation_rule="mean",
                weight_spec="queen",
                zoning_hash="abc123",
                weight_hash="def456",
                aggregation_hash="ghi789",
                n_zones=8,
                n_edges=12,
                total_energy=10.0,
                gradient_energy=6.0,
                curl_energy=2.0,
                harmonic_energy=2.0,
                eta_grad=0.6,
                eta_curl=0.2,
                eta_harm=0.2,
                dominant_component="grad",
            ),
        ),
    )

    result = SpatialResult(
        method_name="maup_profile",
        statistics={"instability": 0.12},
        maup_invariance_certificate=certificate,
        spatial_hodge_diagnostics=diagnostics,
    )

    assert result.maup_invariance_certificate is not None
    assert result.maup_invariance_certificate.status == "warn"
    assert result.spatial_hodge_diagnostics is not None
    assert result.spatial_hodge_diagnostics.declared_scale_id == "district"


def test_advanced_spatial_methods_emit_dependence_ref(tmp_path) -> None:
    ensure_spatial_methods_registered()
    registry = MethodRegistry.get_instance()
    store = FileSystemCAS(tmp_path / "cas")

    kriging_cls = registry.get("spatial.interpolation.gaussian_process_kriging@1.0.0")
    kriging_result = kriging_cls.pure_step(
        {
            "coordinates": np.array(
                [[0.0, 0.0], [0.0, 1.0], [1.0, 0.0], [1.0, 1.0], [0.5, 0.4]],
                dtype=float,
            ),
            "values": np.array([1.0, 1.8, 2.1, 2.9, 1.7], dtype=float),
            "prediction_coords": np.array([[0.2, 0.2], [0.8, 0.8]], dtype=float),
        },
        {"length_scale": 0.7, "noise_level": 0.02, "artifact_store": store},
    )

    dependence_ref = kriging_result["result"].dependence_ref
    assert dependence_ref is not None
    loaded = load_dependence_structure(store, dependence_ref)
    assert loaded.regime == "areal"
    assert loaded.source_method == "spatial.interpolation.gaussian_process_kriging"
