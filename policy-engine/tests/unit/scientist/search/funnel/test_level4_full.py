from __future__ import annotations

from polisyos.scientist.search.funnel.level4_full import Level4FullFidelity


class _StubWorkflowEngine:
    def run(self, initial_state: dict[str, object]) -> dict[str, object]:
        del initial_state
        return {
            "simulation_results": {
                "gdp_change": 1.5,
                "gov_balance": -0.2,
                "ate": 1.1,
                "bootstrap": {"ci_width": 0.3},
            },
            "feedback": {"verdict": "APPROVE"},
        }

    def step(self, state: dict[str, object]) -> tuple[dict[str, object], bool]:
        return state, True

    @property
    def current_phase(self) -> str:
        return "done"

    @property
    def current_node(self) -> str | None:
        return "stub"

    def reset(self) -> None:
        return None


def test_level4_full_emits_full_fidelity_stage_result() -> None:
    stage = Level4FullFidelity(workflow_engine=_StubWorkflowEngine())

    result = stage.evaluate({"candidate_id": "c1"}, {})

    assert result.stage_name == "funnel_L4_full"
    assert result.fidelity_level == 4
    assert result.is_promising is True
    assert result.objective_value < 0.0
    assert result.uncertainty_envelope.uncertainties
