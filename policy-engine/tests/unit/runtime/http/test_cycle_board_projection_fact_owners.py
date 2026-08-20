from __future__ import annotations

import json
from hashlib import sha256
from importlib import import_module
from typing import Any

import pytest

from polisyos.runtime.http.services.cycle_board_projection import (
    HistoricalDispositionError,
    load_ds4_realized_disposition,
    parse_ds4_realized_disposition,
)
from polisyos.runtime.http.services.governed_projections import (
    DepthNCycleBoardPayload,
    _project_depth_n,
)
from tests.unit.runtime.http.test_cycle_board_projection_service import (
    N10_ORDER,
    REPO_ROOT,
    _component_packets,
    _service,
)


def _recomputed_owner_truth(source: dict[str, Any]) -> dict[str, tuple[str, tuple[str, ...]]]:
    validator = import_module(
        "tools.quality.validation.check_layer3_gy_depth_n_universality_contract"
    )
    from polisyos.pdc import SearchTerminalState
    from polisyos.runtime.quality.acquisition_planner import AcquisitionPlannerReport
    from polisyos.runtime.quality.generation_cycle import (
        CandidateGroundingObservation,
        ValuePortObservation,
    )

    runs = source["domain_runs"]
    assert frozenset(runs) == frozenset(N10_ORDER)
    assert tuple(validator.PLAIN_LANGUAGE_PROOF_REQUESTS) == N10_ORDER
    expected = {}
    for role in validator.PLAIN_LANGUAGE_PROOF_REQUESTS:
        run = runs[role]
        terminal = SearchTerminalState.model_validate(run["terminal"])
        grounding = CandidateGroundingObservation.model_validate(
            run["stage_trace"]["grounding"]["owner_observation"]
        )
        value = ValuePortObservation.model_validate(
            run["stage_trace"]["value"]["owner_observation"]
        )
        planner = AcquisitionPlannerReport.model_validate(
            terminal.costed_plan["canonical_planner_report"]
        )
        witness = validator._domain_evidence_witness(
            selected_candidate_ref=run["stage_trace"]["grounding"]["selected_candidate_ref"],
            design_problem_ref=run["design_problem_ref"],
            grounding=grounding,
            value=value,
            terminal=terminal,
            planner_report=planner,
        )
        expected[role] = (witness["kind"], tuple(terminal.blocking_obligations))
    return expected


def _assert_rows_equal_owner(rows: tuple[Any, ...], expected: dict[str, Any]) -> None:
    assert tuple(expected) == N10_ORDER
    owner_rows = tuple(row for row in rows if row.cohort == "n10_capstone")
    assert tuple(row.domain_role for row in owner_rows) == N10_ORDER
    actual = {
        row.domain_role: (
            row.structural_evidence_class.value,
            tuple(row.weakest_links.value),
        )
        for row in rows
        if row.domain_role in expected
    }
    assert actual == expected


def test_cycle_board_claims_equal_live_owner_recomputation_and_detect_corruption() -> None:
    source = json.loads(
        (
            REPO_ROOT
            / "architecture/policy_design_case/layer3_gy_depth_n_universality_contract.json"
        ).read_text(encoding="utf-8")
    )
    packets = _component_packets(
        depth=DepthNCycleBoardPayload.model_validate(_project_depth_n(source)),
    )
    service, _, _ = _service(packets=packets)
    packet = service.get()
    expected = _recomputed_owner_truth(source)

    _assert_rows_equal_owner(packet.payload.rows, expected)

    rows = list(packet.payload.rows)
    target_index = next(i for i, row in enumerate(rows) if row.domain_role in expected)
    target = rows[target_index]
    other_class = next(
        value[0] for value in expected.values() if value[0] != expected[target.domain_role][0]
    )
    rows[target_index] = target.model_copy(
        update={
            "structural_evidence_class": target.structural_evidence_class.model_copy(
                update={"value": other_class}
            )
        }
    )
    with pytest.raises(AssertionError):
        _assert_rows_equal_owner(tuple(rows), expected)

    rows = list(packet.payload.rows)
    target_index = next(
        i
        for i, row in enumerate(rows)
        if row.domain_role in expected and len(expected[row.domain_role][1]) > 1
    )
    target = rows[target_index]
    rows[target_index] = target.model_copy(
        update={
            "weakest_links": target.weakest_links.model_copy(
                update={"value": tuple(reversed(target.weakest_links.value))}
            )
        }
    )
    with pytest.raises(AssertionError):
        _assert_rows_equal_owner(tuple(rows), expected)


def test_ds4_disposition_is_derived_from_complete_historical_owner_table() -> None:
    source_path = (
        REPO_ROOT / "docs/plans/active/atlas-slices/DS4-status-grammar-rebinding-closure.md"
    )
    source_text = source_path.read_text(encoding="utf-8")
    disposition = load_ds4_realized_disposition(REPO_ROOT)
    service, _, _ = _service()

    assert sum(disposition.counts.values()) == disposition.denominator
    assert disposition.source_class == "historical_ds4_component_disposition"
    assert disposition.source_content_hash == f"sha256:{sha256(source_text.encode()).hexdigest()}"
    assert service.get().payload.realized_ds4_disposition == disposition

    with pytest.raises(HistoricalDispositionError):
        parse_ds4_realized_disposition(
            source_text.replace("22 package, 2 rebind", "23 package, 2 rebind", 1),
            source_ref=str(source_path.relative_to(REPO_ROOT)),
        )
    with pytest.raises(HistoricalDispositionError):
        parse_ds4_realized_disposition(
            source_text.replace("| quantity | 5 | C06-C08 | 5 rebind |", "", 1),
            source_ref=str(source_path.relative_to(REPO_ROOT)),
        )
