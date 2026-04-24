from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from polisyos_tests_runtime_http_conftest import build_runtime_api_env


def _inline_payload() -> dict[str, object]:
    return {
        "areas": [
            {
                "area_id": f"area_{idx}",
                "direct_estimate": value,
                "direct_variance": 0.15,
                "policy_indicator": 1.0 if idx >= 4 else 0.0,
                "covariates": {"trend": float(idx) / 7.0},
            }
            for idx, value in enumerate([0.8, 1.0, 1.2, 1.4, 2.8, 3.0, 3.2, 3.4], start=0)
        ],
        "edges": [
            {
                "src_area_id": f"area_{idx}",
                "dst_area_id": f"area_{idx + 1}",
                "weight": 1.0,
                "adjacency_type": "contiguity",
                "frontier_flag": idx == 3,
                "frontier_type": "policy",
                "frontier_source": "fixture",
            }
            for idx in range(7)
        ],
        "metadata": {
            "frontier_semantics": "declared_policy_frontier",
            "transportability_required": False,
        },
        "lambda_spatial": 20.0,
        "component_ridge": 1e-4,
        "persist_artifacts": True,
        "governance_profile": "strict",
    }


def _write_bundle(bundle_dir: Path) -> None:
    bundle_dir.mkdir(parents=True, exist_ok=True)
    areas = pd.DataFrame(
        [
            {
                "area_id": f"area_{idx}",
                "direct_estimate": value,
                "direct_variance": 0.15,
                "policy_indicator": 1.0 if idx >= 4 else 0.0,
                "trend": float(idx) / 7.0,
            }
            for idx, value in enumerate([0.8, 1.0, 1.2, 1.4, 2.8, 3.0, 3.2, 3.4], start=0)
        ]
    )
    edges = pd.DataFrame(
        [
            {
                "src_area_id": f"area_{idx}",
                "dst_area_id": f"area_{idx + 1}",
                "weight": 1.0,
                "adjacency_type": "contiguity",
                "frontier_flag": idx == 3,
                "frontier_type": "policy",
                "frontier_source": "fixture_bundle",
            }
            for idx in range(7)
        ]
    )
    exposure = pd.DataFrame(
        [
            {
                "area_id": f"area_{idx}",
                "treatment": 1.0 if idx >= 4 else 0.0,
                "spillover_exposure": value,
                "exposure_mapping_version": "v1",
            }
            for idx, value in enumerate([0.0, 0.1, 0.3, 0.7, 0.7, 0.3, 0.1, 0.0], start=0)
        ]
    )
    metadata = {
        "frontier_semantics": "declared_policy_frontier",
        "spillover_term_allowed": True,
        "transportability_required": True,
        "graph_id": "bundle_graph",
    }
    areas.to_parquet(bundle_dir / "areas.parquet", index=False)
    edges.to_parquet(bundle_dir / "edges.parquet", index=False)
    exposure.to_parquet(bundle_dir / "exposure.parquet", index=False)
    (bundle_dir / "metadata.json").write_text(json.dumps(metadata) + "\n", encoding="utf-8")


def test_causal_frontier_route_accepts_inline_payload(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    response = client.post(
        "/api/v1/control/analytics/sae/causal-frontier",
        json=_inline_payload(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["method_name"] == "survey.estimation.causal_frontier_fay_herriot"
    assert len(body["estimates"]) == 8
    assert body["diagnostics"]["frontier_edges_active"] == 1
    assert body["diagnostics"]["component_count"] == 2
    assert body["artifact_refs"]["dependence_ref"] is not None
    assert body["artifact_refs"]["quality_certificate_ref"] is not None
    assert body["artifact_refs"]["sae_estimates_ref"] is not None
    assert body["governance_artifact"]["leakage_verdict"]["status"] in {"pass", "warning"}


def test_causal_frontier_route_loads_bundle_and_writes_outputs(tmp_path) -> None:
    env = build_runtime_api_env(tmp_path / "runtime_env", include_test_client=True)
    client = env["client"]
    bundle_dir = tmp_path / "input_bundle"
    output_dir = tmp_path / "output_bundle"
    _write_bundle(bundle_dir)

    response = client.post(
        "/api/v1/control/analytics/sae/causal-frontier",
        json={
            "bundle_dir": str(bundle_dir),
            "output_dir": str(output_dir),
            "covariate_columns": ["trend"],
            "lambda_spatial": 12.0,
            "component_ridge": 1e-4,
            "calibration_reps": 8,
            "calibration_seed": 7,
            "persist_artifacts": False,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["diagnostics"]["calibration_quantiles"]["method"] == "permutation_null"
    assert body["governance_artifact"]["transportability_required"] is True
    assert Path(body["output_bundle"]["sae_estimates"]).exists()
    assert Path(body["output_bundle"]["causal_diagnostics"]).exists()
    assert Path(body["output_bundle"]["governance_artifact"]).exists()

    estimates = pd.read_parquet(output_dir / "sae_estimates.parquet")
    assert list(estimates.columns) == [
        "area_id",
        "theta_mean",
        "theta_sd",
        "mse",
        "component_id",
        "borrow_strength_neighbors",
    ]
    assert len(estimates) == 8
