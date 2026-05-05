from __future__ import annotations

from polisyos_tests_runtime_http_conftest import build_runtime_api_env


def test_mobility_estimate_route_persists_report_and_serves_related_endpoints(tmp_path) -> None:
    env = build_runtime_api_env(
        tmp_path,
        include_test_client=True,
        app_kwargs={"allow_unscoped_artifacts": True},
    )
    client = env["client"]

    response = client.post(
        "/api/v1/mobility/estimate",
        json={
            "mode": "attrition_adjusted",
            "n_classes": 2,
            "origin_classes": [0, 0, 0, 0, 1, 1, 1, 1],
            "destination_classes": [0, 0, None, None, 1, 1, None, None],
            "retention_indicators": [1, 1, 0, 0, 1, 1, 0, 0],
            "attrition_features": [[0.0], [0.0], [1.0], [1.0], [0.0], [0.0], [1.0], [1.0]],
            "retention_probabilities": [1.0, 1.0, 0.5, 0.5, 1.0, 1.0, 0.5, 0.5],
            "estimator": "ipcw",
            "compute_bounds": True,
            "persist_artifact": True,
        },
    )
    assert response.status_code == 200

    payload = response.json()
    report = payload["report"]
    report_ref = payload["mobility_report_ref"]
    bounds_ref = payload["bounds_bundle_ref"]

    assert report["analysis_type"] == "transition_matrix_attrition_adjusted"
    assert report_ref["artifact_id"].startswith("sha256:")
    assert bounds_ref["artifact_id"].startswith("sha256:")

    artifact_id = report_ref["artifact_id"]

    report_response = client.get(f"/api/v1/mobility/reports/{artifact_id}")
    assert report_response.status_code == 200
    assert report_response.json()["report"]["analysis_type"] == report["analysis_type"]

    bounds_response = client.get(f"/api/v1/mobility/reports/{artifact_id}/bounds")
    assert bounds_response.status_code == 200
    bounds_payload = bounds_response.json()
    assert bounds_payload["mobility_report_ref"]["artifact_id"] == artifact_id
    assert bounds_payload["bounds_bundle_ref"]["artifact_id"] == bounds_ref["artifact_id"]
    assert bounds_payload["summary_bounds"]["immobility_rate"] == [0.5, 1.0]

    diagnostics_response = client.get(f"/api/v1/mobility/reports/{artifact_id}/diagnostics")
    assert diagnostics_response.status_code == 200
    diagnostics_payload = diagnostics_response.json()["diagnostics"]
    assert diagnostics_payload["observed_full_cases"] == 4
    assert diagnostics_payload["observed_retention_rate"] == 0.5


def test_mobility_bounds_route_returns_transport_bounds_payload(tmp_path) -> None:
    env = build_runtime_api_env(
        tmp_path,
        include_test_client=True,
        app_kwargs={"allow_unscoped_artifacts": True},
    )
    client = env["client"]

    response = client.post(
        "/api/v1/mobility/bounds",
        json={
            "observed_joint_matrix": [[0.25, 0.0], [0.0, 0.25]],
            "row_marginals": [0.5, 0.5],
            "column_marginals": [0.5, 0.5],
            "headline_metric": "upward_rate",
            "persist_artifact": True,
        },
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["bounds_bundle_ref"]["artifact_id"].startswith("sha256:")
    assert payload["cell_bounds"]["0,0"] == [0.25, 0.5]
    assert payload["summary_bounds"]["upward_rate"] == [0.0, 0.25]
    assert payload["summary_bounds"]["immobility_rate"] == [0.5, 1.0]
