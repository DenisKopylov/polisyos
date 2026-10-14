"""Build the existing controlled same-candidate source chain for dashboard witnesses."""

from __future__ import annotations

from pathlib import Path

import pytest


def build_same_candidate_history_fixture(
    *,
    fixture_root: Path,
    cas_root: Path,
    tenant_id: str,
    cell_id: str,
) -> dict[str, str]:
    """Build the existing source-owned producer chain and return its run identity.

    The integration producer creates and verifies signed test-only authority, runs the
    ordinary request/worker path, persists source lineage, and confirms a fresh GET. Its
    output is reused by the local browser fixture; no production issuer/currentness claim is
    inferred from the test signature.
    """
    from tests._helpers.controlled_candidate_profile import ControlledCandidateGateway
    from tests.integration.core_runtime import test_acquisition_authority_served as producer

    fixture_root.mkdir(parents=True, exist_ok=True)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(producer, "TENANT", tenant_id)
    monkeypatch.setattr(producer, "CELL", cell_id)
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_BASE_URL", "")
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_API_KEY", "sk-synthetic-local-gateway-key")
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_MAX_RETRIES", "0")
    monkeypatch.setenv("POLISYOS_LLM_CACHE_TTL_S", "0")
    monkeypatch.setenv("POLISYOS_LLM_CACHE_MAXSIZE", "0")
    monkeypatch.setenv("POLISYOS_LLM_PROMPT_SANITIZER", "false")
    monkeypatch.setenv("POLISYOS_CONTROL_SQLITE_PATH", str(fixture_root / "control.sqlite3"))
    try:
        with ControlledCandidateGateway() as gateway:
            monkeypatch.setenv("POLISYOS_LLM_GATEWAY_BASE_URL", gateway.base_url)
            result = producer._produce_served_acquisition_history(
                fixture_root,
                monkeypatch,
                gateway,
                fixture_cas_root=cas_root,
                stop_after_fresh_get=True,
            )
    finally:
        monkeypatch.undo()
    if not isinstance(result, dict) or not result.get("run_id") or not result.get("candidate_id"):
        raise RuntimeError("same_candidate_history_fixture_producer_unavailable")
    return result
