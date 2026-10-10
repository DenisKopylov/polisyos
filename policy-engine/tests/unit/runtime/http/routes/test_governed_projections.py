from __future__ import annotations


def test_unknown_projection_id_never_returns_a_governed_packet(runtime_api_env) -> None:
    response = runtime_api_env["client"].get(
        "/api/v1/exports/governed-projections/acquisition-growth-v999"
    )

    assert response.status_code == 422
    assert "availability" not in response.json()
    assert "projection_id" in response.text
