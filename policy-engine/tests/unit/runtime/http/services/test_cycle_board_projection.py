from __future__ import annotations

from types import SimpleNamespace

from polisyos.core.trace.record import RunTerminality
from polisyos.runtime.http.services.cycle_board_projection import _lifecycle_binding


class _RunIndex:
    def __init__(self, summary: object) -> None:
        self.summary = summary
        self.requested: list[str] = []

    def get_run(self, run_id: str):
        self.requested.append(run_id)
        return SimpleNamespace(summary=self.summary)


def test_lifecycle_terminality_requires_the_exact_run_identity_and_enum() -> None:
    requested_run_id = "run-requested"
    invalid_summaries = (
        SimpleNamespace(
            run_id="run-sibling",
            run_terminality=RunTerminality.TERMINAL,
        ),
        SimpleNamespace(
            run_id=requested_run_id,
            run_terminality="terminal",
        ),
    )

    for summary in invalid_summaries:
        index = _RunIndex(summary)
        fact, source = _lifecycle_binding(index, requested_run_id)

        assert index.requested == [requested_run_id]
        assert fact.availability == "not_established"
        assert "value" not in fact.model_dump()
        assert source.availability == "not_established"

    exact_index = _RunIndex(
        SimpleNamespace(
            run_id=requested_run_id,
            run_terminality=RunTerminality.TERMINAL,
        )
    )
    exact_fact, _source = _lifecycle_binding(exact_index, requested_run_id)

    assert exact_fact.availability == "available"
    assert exact_fact.value is RunTerminality.TERMINAL
