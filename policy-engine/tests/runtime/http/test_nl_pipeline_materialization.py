from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from polisyos.runtime.http.services.control import ControlPlaneService


class _FakeMetric:
    def model_dump(self, mode: str = "json") -> dict[str, Any]:
        return {"metric": "macro.gdp", "value": 1.0}


class _FakeRetrievalService:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    def resolve(self, request: Any) -> Any:
        return SimpleNamespace(
            fetch_plans=[{"id": "plan-1"}],
            telemetry={
                "lane_used": "fastlane",
                "metadata_docs_fetched": 1,
                "local_index_size_bytes": 10,
                "local_index_docs_total": 1,
                "candidates_filtered": 0,
                "phases": [],
            },
            mode="hybrid",
        )

    def execute_fetch_plans(
        self,
        plans: list[dict[str, Any]],
        persist_payload: bool = False,
        allow_fallback: bool = True,
    ) -> Any:
        return SimpleNamespace(
            previews=[SimpleNamespace(preview=SimpleNamespace(coverage_ok=True))],
            fallback_triggered_count=0,
            promoted_count=1,
            data_context=SimpleNamespace(
                metrics=[_FakeMetric()],
                metadata_docs_fetched=1,
                index_docs_total=1,
                index_size_bytes=10,
            ),
        )


def test_nl_pipeline_materializes_data_snapshot_without_data_source(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def _capture_state(payload: dict[str, Any]) -> None:
        captured["payload"] = payload

    monkeypatch.setattr("polisyos.fabric.retrieval.RetrievalService", _FakeRetrievalService)
    monkeypatch.setattr("polisyos.scientist.api.run_experiment", _capture_state)

    ControlPlaneService._execute_nl_pipeline(
        run_id="R_nl_materialize",
        nl_request="test request",
        context={},
        domain_hint="fiscal",
        data_source=None,
        max_iterations=1,
        llm_models=[],
        max_parallel_models=1,
        run_budget_usd=None,
        per_model_budget_usd=None,
        checkpoint_policy="strict",
        execution_plan_ref=None,
        execution_plan_payload=None,
        stop_criteria_payload={},
        governance_constraints_payload=[],
        expected_outputs_payload=[],
    )

    payload = captured["payload"]
    inputs = payload["inputs"]
    assert "data_snapshot_ref" in inputs
    assert "input_bindings_ref" in inputs
    assert "registry_bundle_ref" in inputs
