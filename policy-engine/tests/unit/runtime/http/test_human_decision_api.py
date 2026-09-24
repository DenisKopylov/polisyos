"""Red-first HTTP witnesses for the run-bound DS9 surface."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock

import pytest

from polisyos.runtime.http.dependencies import get_optional_human_decision_service
from polisyos.runtime.http.services.human_decision_contracts import (
    HumanDecisionExposureSurface,
    HumanDecisionGateReason,
    HumanDecisionGateResponse,
    HumanDecisionGateResult,
)


@pytest.fixture(autouse=True)
def _isolated_catalog_input(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Provision the normal runtime fixture's persisted catalog before startup."""
    from dataclasses import replace

    from polisyos.data_forge.read_api import catalog as catalog_api
    from polisyos.runtime.quality import substrate_registry

    catalog_root = tmp_path / "retrieval-catalog"
    catalog_api.build_slice0_fixture_catalog_graph(catalog_root).close()
    original = substrate_registry.default_substrate_catalog_paths
    startup_root = Path.cwd().resolve()
    monkeypatch.setattr(
        substrate_registry,
        "default_substrate_catalog_paths",
        lambda root: (
            replace(original(root), l1_dcat_path=catalog_root / "catalog.duckdb")
            if Path(root).resolve() == startup_root
            else original(root)
        ),
    )


def test_human_decision_missing_producer_is_typed_not_a_missing_route(
    runtime_api_env,
) -> None:
    response = runtime_api_env["client"].get(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}/human-decision-gate",
        params={"source_kind": "production_approval"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "producer_missing"
    assert payload["run_id"] == runtime_api_env["core_run_id"]
    assert payload["source_kind"] == "production_approval"


def test_production_gate_get_binds_source_ref_as_the_exact_basis_ref(
    runtime_api_env,
    monkeypatch,
) -> None:
    reason = HumanDecisionGateReason(
        code="DS9-DECISION-PRODUCER-MISSING",
        message="The signed production basis producer is unavailable.",
        status="producer_missing",
    )
    resolved_at = datetime(2026, 8, 24, 12, tzinfo=UTC)
    service = Mock()
    service.resolve_gate.return_value = HumanDecisionGateResult(
        status="producer_missing",
        reasons=(reason,),
        source_kind="production_approval",
        tenant_id="tenant-a",
        run_id=runtime_api_env["core_run_id"],
        decision_request_ref=None,
        resolved_at=resolved_at,
        verifier_epoch="route-bridge-test",
    )

    def gate_response(gate_input, *, bound_permission):
        del bound_permission
        return HumanDecisionGateResponse(
            status="producer_missing",
            reasons=(reason,),
            reason_codes=(reason.code,),
            source_kind="production_approval",
            source_ref=gate_input.source_ref,
            tenant_id=gate_input.tenant_id,
            run_id=gate_input.run_id,
            decision_request_ref=None,
            exposure=HumanDecisionExposureSurface(
                required_artifact_digests=(),
                completed_artifact_digests=(),
            ),
            resolved_at=resolved_at,
            verifier_epoch="route-bridge-test",
        )

    service.resolve_gate_response.side_effect = gate_response
    monkeypatch.setitem(
        runtime_api_env["app"].dependency_overrides,
        get_optional_human_decision_service,
        lambda: service,
    )
    basis_ref = "sha256:" + "4" * 64
    response = runtime_api_env["client"].get(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}/human-decision-gate",
        params={
            "source_kind": "production_approval",
            "source_ref": basis_ref,
            "basis_digest": basis_ref,
        },
    )

    assert response.status_code == 200, response.text
    gate_input = service.resolve_gate.call_args.args[0]
    assert {
        gate_input.source_ref,
        gate_input.basis_ref,
        gate_input.basis_digest,
    } == {basis_ref}
