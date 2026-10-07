"""End-to-end history witnesses for the additive interaction-evidence epoch."""

from __future__ import annotations

import copy
import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from polisyos.core.security.tenant_context import tenant_scope
from polisyos.runtime.quality import generation_cycle as generation
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from tests.unit.remediation.test_emp_01 import _install_synthetic_baseline_profile
from tests.unit.runtime.quality.test_generation_cycle import (
    _owner_program_graph_n5_witness,
    _problem,
)


def _assert_history_parse_error(payload: dict[str, Any], code: str) -> None:
    """Require the ordinary history reader to preserve the typed refusal code."""

    issues = generation.validate_generation_cycle_run_history(payload)
    assert len(issues) == 1
    assert issues[0]["code"] == "generation_cycle_historical_projection_invalid"
    assert code in str(issues[0].get("error"))


@pytest.mark.asyncio
async def test_actual_default_n5_n8_interaction_history_is_versioned_and_replayable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Persist real default N5 output without widening the frozen v3/v4 epochs."""

    problem_seed = _problem("e02_actual_interaction_history").model_copy(
        update={"problem_statement": "Synthetic owner fixture; no policy claim."}
    )
    witness = _owner_program_graph_n5_witness(
        tmp_path / "n5",
        income_values=(1000.0, 2000.0),
        problem_seed=problem_seed,
    )
    try:
        outcome = witness.problem.outcome_of_interest.target_variable
        connection = _install_synthetic_baseline_profile(
            monkeypatch,
            tmp_path,
            outcome=outcome,
            row_count=1,
        )

        class _FixtureGenerationPort:
            async def __call__(self, _problem: Any, *, cycle_index: int) -> Any:
                assert cycle_index == 0
                candidate = witness.candidate
                return SimpleNamespace(
                    status="generated",
                    candidates=(candidate,),
                    surrogate_rankings=(
                        SimpleNamespace(
                            candidate_id=candidate.candidate_id,
                            score=0.9,
                            voi_estimate=10.0,
                        ),
                    ),
                    grounding_dispositions=(),
                )

        class _FixtureGroundingPort:
            def __call__(self, *, candidate: Any, **_kwargs: Any) -> Any:
                return generation.CandidateGroundingObservation(
                    candidate_id=str(candidate.candidate_id),
                    status="grounded_shadow",
                    grounding_score=0.8,
                    current_valid=False,
                    grounding_source="cgf_firewall",
                    grounding_disposition="synthetic_test_only",
                    report_ref="synthetic-fixture://e02/grounding",
                )

        class _FixturePromotionPort:
            def __call__(self, **_kwargs: Any) -> Any:
                return generation.PromotionPortObservation(
                    status="not_promoted",
                    reason="synthetic_e02_test_only",
                )

        controller = generation.GenerationCycleController(
            generation_port=_FixtureGenerationPort(),
            grounding_port=_FixtureGroundingPort(),
            promotion_port=_FixturePromotionPort(),
            repo_root=tmp_path,
            cycle_substrate_context=witness.context,
            artifact_store=witness.store,
            authority_scope="contract_testing",
        )
        assert isinstance(controller._simulation_port, generation.JointSimulationPort)
        assert isinstance(
            controller._value_port,
            generation._DefaultSimulationBoundFoundryValuePort,
        )

        with tenant_scope(None, tenant_id="tenant-e02-history", cell_id="cell-e02-history"):
            run = await controller.run(
                witness.problem,
                budget_state=BudgetState(
                    limits={"run": BudgetLimit(key="run", max_usd=Decimal("5.0"))}
                ),
                min_cycles=1,
                max_cycles=1,
            )

        assert run.schema_version == "policyos.runtime.generation_cycle_controller.v5"
        assert run.source_custody_limitation is None
        assert run.cycles[-1].simulation.status == "joint_simulated"
        result_ref = run.cycles[-1].simulation.simulation_result_ref
        assert result_ref is not None
        assert witness.store.verify(result_ref.artifact_id).ok
        assert run.value_port.status == "value_conditional"
        assert run.value_port.evaluation_mode == "simulate_only"
        assert run.value_port.decision_grade == "low"
        assert connection.calls == []

        expected_evidence = run.value_port.conditional_interaction_evidence
        assert expected_evidence is not None
        expected_wire = expected_evidence.model_dump(mode="json")
        assert run.cycles[-1].value_port.conditional_interaction_evidence == expected_evidence

        persisted_path = tmp_path / "generation-cycle-run.json"
        persisted_path.write_text(
            json.dumps(run.model_dump(mode="json"), sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        persisted = json.loads(persisted_path.read_text(encoding="utf-8"))
        restored = generation.GenerationCycleRun.from_persisted_payload(persisted)
        assert restored.model_dump(mode="json") == persisted
        restored_root_evidence = restored.value_port.conditional_interaction_evidence
        restored_cycle_evidence = restored.cycles[-1].value_port.conditional_interaction_evidence
        assert restored_root_evidence is not None
        assert restored_cycle_evidence is not None
        assert restored_root_evidence.model_dump(mode="json") == expected_wire
        assert restored_cycle_evidence.model_dump(mode="json") == expected_wire
        assert generation.validate_generation_cycle_run_history(persisted) == ()

        # Old owners remain frozen: non-null v5 fields cannot be re-labeled v3/v4.
        for version in ("v3", "v4"):
            legacy = copy.deepcopy(persisted)
            legacy["schema_version"] = f"policyos.runtime.generation_cycle_controller.{version}"
            if version == "v3":
                legacy.pop("source_custody_limitation", None)
            else:
                legacy["source_custody_limitation"] = (
                    generation.GenerationSourceCustodyLimitation().model_dump(mode="json")
                )
            with pytest.raises(
                ValueError,
                match="generation_cycle_interaction_evidence_requires_v5",
            ):
                generation.GenerationCycleRun.from_persisted_payload(legacy)
            _assert_history_parse_error(
                legacy,
                "generation_cycle_interaction_evidence_requires_v5",
            )

        # The limited v6 branch is serializer coverage only. The limitation is
        # supplied as its existing typed owner; this does not claim a limited
        # producer path ran or that source custody was established.
        limited = copy.deepcopy(persisted)
        limited["schema_version"] = "policyos.runtime.generation_cycle_controller.v6"
        limited["source_custody_limitation"] = (
            generation.GenerationSourceCustodyLimitation().model_dump(mode="json")
        )
        limited_run = generation.GenerationCycleRun.model_validate(limited)
        limited_wire = limited_run.model_dump(mode="json")
        limited_path = tmp_path / "generation-cycle-run-v6.json"
        limited_path.write_text(
            json.dumps(limited_wire, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        limited_persisted = json.loads(limited_path.read_text(encoding="utf-8"))
        restored_limited = generation.GenerationCycleRun.from_persisted_payload(limited_persisted)
        assert restored_limited.schema_version.endswith(".v6")
        assert restored_limited.source_custody_limitation == (
            generation.GenerationSourceCustodyLimitation()
        )
        limited_root_evidence = restored_limited.value_port.conditional_interaction_evidence
        limited_cycle_evidence = restored_limited.cycles[
            -1
        ].value_port.conditional_interaction_evidence
        assert limited_root_evidence is not None
        assert limited_cycle_evidence is not None
        assert limited_root_evidence.model_dump(mode="json") == expected_wire
        assert limited_cycle_evidence.model_dump(mode="json") == expected_wire
        assert generation.validate_generation_cycle_run_history(limited_persisted) == ()

        v5_with_limitation = copy.deepcopy(persisted)
        v5_with_limitation["source_custody_limitation"] = (
            generation.GenerationSourceCustodyLimitation().model_dump(mode="json")
        )
        with pytest.raises(ValueError, match="generation_cycle_source_limitation_requires_v4"):
            generation.GenerationCycleRun.from_persisted_payload(v5_with_limitation)

        missing_limited_owner = copy.deepcopy(limited_persisted)
        missing_limited_owner.pop("source_custody_limitation")
        with pytest.raises(ValueError):
            generation.GenerationCycleRun.from_persisted_payload(missing_limited_owner)

        missing_both = copy.deepcopy(persisted)
        missing_both["value_port"].pop("conditional_interaction_evidence")
        missing_both["cycles"][-1]["value_port"].pop("conditional_interaction_evidence")
        with pytest.raises(
            ValueError,
            match="generation_cycle_interaction_evidence_missing",
        ):
            generation.GenerationCycleRun.from_persisted_payload(missing_both)

        missing_cycles = copy.deepcopy(persisted)
        missing_cycles["cycles"] = []
        assert missing_cycles["value_port"]["conditional_interaction_evidence"] == expected_wire
        with pytest.raises(
            ValueError,
            match="generation_cycle_interaction_evidence_cycle_missing",
        ):
            generation.GenerationCycleRun.from_persisted_payload(missing_cycles)
        _assert_history_parse_error(
            missing_cycles,
            "generation_cycle_interaction_evidence_cycle_missing",
        )

        # Removing either duplicate projection is refused by the production
        # reader; it cannot silently lose the actual owner-issued result.
        for owner in ("root", "last_cycle"):
            one_sided = copy.deepcopy(persisted)
            if owner == "root":
                one_sided["value_port"].pop("conditional_interaction_evidence")
            else:
                one_sided["cycles"][-1]["value_port"].pop("conditional_interaction_evidence")
            with pytest.raises(
                ValueError,
                match="generation_cycle_interaction_evidence_projection_mismatch",
            ):
                generation.GenerationCycleRun.from_persisted_payload(one_sided)
            _assert_history_parse_error(
                one_sided,
                "generation_cycle_interaction_evidence_projection_mismatch",
            )

        fake_evidence = copy.deepcopy(persisted)
        fake_evidence["value_port"]["conditional_interaction_evidence"]["predicate_provenance"] = (
            "declared"
        )
        fake_evidence["cycles"][-1]["value_port"]["conditional_interaction_evidence"][
            "predicate_provenance"
        ] = "declared"
        with pytest.raises(ValidationError) as invalid_evidence:
            generation.GenerationCycleRun.from_persisted_payload(fake_evidence)
        errors = {
            error["loc"]: error["type"]
            for error in invalid_evidence.value.errors()
            if error["type"] == "literal_error"
        }
        assert set(errors) == {
            (
                "value_port",
                "conditional_interaction_evidence",
                "predicate_provenance",
            ),
            (
                "cycles",
                len(fake_evidence["cycles"]) - 1,
                "value_port",
                "conditional_interaction_evidence",
                "predicate_provenance",
            ),
        }
    finally:
        witness.store.close()
