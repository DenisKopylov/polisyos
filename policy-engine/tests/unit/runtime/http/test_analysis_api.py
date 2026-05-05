from __future__ import annotations

from polisyos_tests_runtime_http_conftest import build_runtime_api_env


def test_attractor_analysis_route_persists_and_loads_result(tmp_path) -> None:
    env = build_runtime_api_env(
        tmp_path,
        include_test_client=True,
        app_kwargs={"allow_unscoped_artifacts": True},
    )
    client = env["client"]

    response = client.post(
        "/api/v1/analysis/attractors",
        json={
            "variable_ids": ["income", "wealth"],
            "trajectory": [[1.0, 2.0] for _ in range(12)],
            "tolerance": 1.0e-8,
            "rtol": 0.0,
            "persist_artifact": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["analysis_result"]["attractors"][0]["kind"] == "fixed_point"
    result_ref = payload["analysis_result_ref"]
    assert result_ref["artifact_id"].startswith("sha256:")

    loaded = client.get(f"/api/v1/analysis/{result_ref['artifact_id']}")
    assert loaded.status_code == 200
    assert loaded.json()["state_projection"]["variables"] == ["income", "wealth"]


def test_attractor_analysis_route_builds_basin_map_for_ensemble(tmp_path) -> None:
    env = build_runtime_api_env(
        tmp_path,
        include_test_client=True,
        app_kwargs={"allow_unscoped_artifacts": True},
    )
    client = env["client"]

    response = client.post(
        "/api/v1/analysis/attractors",
        json={
            "variable_ids": ["x"],
            "trajectories": [
                [[0.0] for _ in range(10)],
                [[1.0] for _ in range(10)],
                [[1.0] for _ in range(10)],
            ],
            "initial_states": [{"x": 0.0}, {"x": 0.5}, {"x": 0.9}],
            "seeds": [1, 2, 3],
            "tolerance": 1.0e-8,
            "rtol": 0.0,
            "persist_artifact": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    refs = {item["role"]: item["ref"] for item in payload["derived_refs"]}
    assert set(refs) == {"attractor_analysis_result", "basin_map"}
    assert len(payload["analysis_result"]["attractors"]) == 2

    basin_response = client.get(
        "/api/v1/analysis/"
        f"{refs['attractor_analysis_result']['artifact_id']}/basin/"
        f"{refs['basin_map']['artifact_id']}"
    )
    assert basin_response.status_code == 200
    basin_payload = basin_response.json()
    assert basin_payload["basin_measure_estimates"] == {"A1": 1 / 3, "A2": 2 / 3}
    assert [sample["attractor_id"] for sample in basin_payload["samples"]] == [
        "A1",
        "A2",
        "A2",
    ]


def test_continuation_branch_route_persists_and_loads_sidecar(tmp_path) -> None:
    env = build_runtime_api_env(
        tmp_path,
        include_test_client=True,
        app_kwargs={"allow_unscoped_artifacts": True},
    )
    client = env["client"]

    response = client.post(
        "/api/v1/analysis/continuation",
        json={
            "branch_id": "branch_1",
            "analysis_id": "analysis_1",
            "branch_kind": "equilibrium",
            "parameters": ["beta"],
            "points": [
                {
                    "point_id": "p1",
                    "parameter_values": {"beta": 0.1},
                    "state": {"infected": 0.0},
                }
            ],
        },
    )

    assert response.status_code == 200
    branch_ref = response.json()
    assert branch_ref["artifact_id"].startswith("sha256:")

    loaded = client.get(f"/api/v1/analysis/analysis_1/branch/{branch_ref['artifact_id']}")
    assert loaded.status_code == 200
    assert loaded.json()["branch_kind"] == "equilibrium"
