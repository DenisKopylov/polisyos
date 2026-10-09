from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods.catalog.causal import ci_backends


def _counter_type():
    counter_type = getattr(ci_backends, "BootstrapExecutionCounter", None)
    assert counter_type is not None, "the bootstrap loop must expose an actual-work counter"
    return counter_type


def test_bootstrap_interval_reports_completed_replicates_without_changing_result() -> None:
    values = np.asarray([1.0, 2.0, 4.0, 8.0])
    expected = ci_backends.bootstrap_mean_interval(values, seed=71, draws=7)
    counter = _counter_type()(requested_draw_count=7)

    actual = ci_backends.bootstrap_mean_interval(values, seed=71, draws=7, work_counter=counter)

    assert actual == expected
    assert counter.snapshot().model_dump(mode="json") == {
        "schema_version": "1.0",
        "work_unit": "bootstrap_replicate",
        "requested_draw_count": 7,
        "attempted_draw_count": 7,
        "completed_draw_count": 7,
        "failed_draw_count": 0,
        "unattempted_draw_count": 0,
        "draw_execution_status": "complete",
    }


def test_bootstrap_early_return_reports_requested_but_unattempted_draws() -> None:
    counter = _counter_type()(requested_draw_count=5)

    assert ci_backends.bootstrap_mean_interval(
        np.asarray([3.0]), seed=4, draws=5, work_counter=counter
    ) == (
        3.0,
        3.0,
    )
    assert counter.snapshot().draw_execution_status == "not_started"
    assert counter.snapshot().requested_draw_count == 5
    assert counter.snapshot().attempted_draw_count == 0
    assert counter.snapshot().completed_draw_count == 0
    assert counter.snapshot().failed_draw_count == 0
    assert counter.snapshot().unattempted_draw_count == 5


def test_bootstrap_failure_counts_failed_and_unattempted_draws(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FailingRng:
        def __init__(self) -> None:
            self.calls = 0

        def choice(self, values: np.ndarray, *, size: int, replace: bool) -> np.ndarray:
            del size, replace
            self.calls += 1
            if self.calls == 2:
                raise ArithmeticError("injected draw failure")
            return values

    rng = _FailingRng()
    monkeypatch.setattr(
        "polisyos.foundry.methods.catalog.causal.ci_backends.np.random.default_rng",
        lambda seed: rng,
    )
    counter = _counter_type()(requested_draw_count=5)

    with pytest.raises(ArithmeticError, match="injected draw failure"):
        ci_backends.bootstrap_mean_interval(
            np.asarray([1.0, 2.0]),
            seed=5,
            draws=5,
            work_counter=counter,
        )

    actual = counter.snapshot()
    assert actual.draw_execution_status == "partial"
    assert actual.attempted_draw_count == 2
    assert actual.completed_draw_count == 1
    assert actual.failed_draw_count == 1
    assert actual.unattempted_draw_count == 3


@pytest.mark.parametrize(
    "counts",
    [
        {"attempted_draw_count": 2, "completed_draw_count": 1, "failed_draw_count": 0},
        {"attempted_draw_count": 1, "completed_draw_count": 1, "failed_draw_count": 0},
    ],
)
def test_bootstrap_work_contract_rejects_inconsistent_or_fake_count_totals(
    counts: dict[str, int],
) -> None:
    work_type = getattr(ci_backends, "BootstrapExecutionWork", None)
    assert work_type is not None, "bootstrap counts must have a typed contract"

    with pytest.raises(ValueError):
        work_type(
            requested_draw_count=2,
            attempted_draw_count=counts["attempted_draw_count"],
            completed_draw_count=counts["completed_draw_count"],
            failed_draw_count=counts["failed_draw_count"],
            unattempted_draw_count=0,
            draw_execution_status="complete",
        )
