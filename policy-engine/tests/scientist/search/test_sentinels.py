from __future__ import annotations

from polisyos.scientist.search.controller import SearchConfig, SearchController
from polisyos.scientist.search.funnel.orchestrator import FunnelOrchestrator
from polisyos.scientist.search.objective import CompositeObjective, GDPGrowthObjective
from polisyos.scientist.search.sentinels import (
    SENTINEL_METADATA_KEY,
    SentinelCandidate,
    SentinelInjector,
    SentinelKind,
    SentinelSet,
)
from polisyos.scientist.search.stopping import MaxIterations


def test_sentinel_injector_batch_cadence_is_deterministic() -> None:
    sentinel_set = SentinelSet(
        set_id="s1",
        suite_id="bench",
        sentinels=[
            SentinelCandidate(
                sentinel_id="sentinel-a",
                kind=SentinelKind.CALIBRATION,
                candidate={"semantic": {"interventions": [], "objectives": []}},
            ),
            SentinelCandidate(
                sentinel_id="sentinel-b",
                kind=SentinelKind.REGRESSION,
                candidate={"semantic": {"interventions": [], "objectives": []}},
            ),
        ],
        injection_rate=2,
    )
    injector = SentinelInjector(sentinel_set)
    batch = injector.inject_batch(
        [{"candidate": 1}, {"candidate": 2}, {"candidate": 3}, {"candidate": 4}, {"candidate": 5}]
    )

    sentinel_ids = [
        item[SENTINEL_METADATA_KEY]["sentinel_id"]
        for item in batch
        if SENTINEL_METADATA_KEY in item
    ]
    assert sentinel_ids == ["sentinel-a", "sentinel-b"]


def test_orchestrator_submit_extracts_sentinel_metadata() -> None:
    sentinel_set = SentinelSet(
        set_id="s1",
        suite_id="bench",
        sentinels=[
            SentinelCandidate(
                sentinel_id="sentinel-a",
                kind=SentinelKind.CALIBRATION,
                candidate={"semantic": {"interventions": [], "objectives": []}},
            )
        ],
        injection_rate=1,
    )
    injector = SentinelInjector(sentinel_set)
    injected = injector.inject_batch([{"candidate": 1}])
    sentinel_candidate = injected[-1]

    ticket = FunnelOrchestrator([]).submit(sentinel_candidate, {})
    assert ticket.context["is_sentinel"] is True
    assert ticket.context["sentinel_id"] == "sentinel-a"


def test_search_controller_excludes_sentinels_from_history() -> None:
    sentinel_set = SentinelSet(
        set_id="s1",
        suite_id="bench",
        sentinels=[
            SentinelCandidate(
                sentinel_id="sentinel-a",
                kind=SentinelKind.CALIBRATION,
                candidate={
                    "x": 99,
                    "semantic": {
                        "interventions": [{"type": "sentinel"}],
                        "objectives": [{"name": "gdp"}],
                    },
                },
            )
        ],
        injection_rate=1,
    )

    class Generator:
        def __init__(self):
            self._value = 0

        def generate(self, history, current_best, context):
            self._value += 1
            return {
                "x": float(self._value),
                "semantic": {
                    "interventions": [{"type": "tax_reform"}],
                    "objectives": [{"name": "gdp"}],
                },
            }

    wrapped = SentinelInjector(sentinel_set).wrap_candidate_generator(Generator())

    controller = SearchController(
        config=SearchConfig(
            stopping=MaxIterations(3),
            objective=CompositeObjective([GDPGrowthObjective()]),
        ),
        candidate_generator=wrapped,
        stage_a_evaluator=lambda candidate, context: (0.0, True),
        stage_b_evaluator=lambda candidate, context: {
            "simulation_results": {"gdp_change": candidate.get("x", 0.0)},
            "feedback": {"verdict": "APPROVE"},
        },
    )

    result = controller.run({"user_request": "sentinel exclusion"})
    assert len(result.history) == 3
    assert result.telemetry["sentinel_evaluations"] == 1
