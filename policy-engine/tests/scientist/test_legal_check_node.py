from __future__ import annotations

import logging
from unittest.mock import patch

from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.foundry import SimulationResultRef
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.engine.state_branching import branch_state as real_branch_state
from polisyos.scientist.nodes.builtins.governance.legal_check import LegalCheckNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_SIMULATION_RESULT_REF,
    INPUT_NORM_PACK_REF,
    INPUT_TRINITY_BUNDLE_REF,
    REPORT_LEGAL_REPORT_REF,
)


def test_legal_check_skips_when_legal_context_is_missing(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_legal_skip")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.legal"))

    trinity_ref = store.put_json(
        {"policy_spec": {"interventions": []}},
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version="1.0"),
        ),
    )
    simulation_result_ref = store.put_json(
        {"ok": True},
        PutOptions(kind="foundry.simulation_result", media_type="application/json"),
    )

    state = ExperimentState(
        run_id="R_legal_skip",
        inputs={INPUT_TRINITY_BUNDLE_REF: trinity_ref},
        artifacts_index={ARTIFACT_SIMULATION_RESULT_REF: simulation_result_ref},
    )

    outcome = LegalCheckNode().execute(ctx, state)

    assert outcome.status == "skip"
    assert outcome.error is None
    assert outcome.events
    assert outcome.events[0].message == "Legal check skipped: missing params.jurisdiction"
    assert outcome.events[0].attrs == {
        "skip_reason": "missing_jurisdiction",
        "required": "params.jurisdiction",
    }


def test_legal_check_records_degraded_event_when_report_grade_load_fails(
    tmp_path,
    monkeypatch,
) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_legal_degraded")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.legal.degraded"))

    trinity_ref = store.put_json(
        {"policy_spec": {"interventions": []}},
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version="1.0"),
        ),
    )
    simulation_result_ref = store.put_json(
        {"ok": True},
        PutOptions(kind="foundry.simulation_result", media_type="application/json"),
    )
    norm_pack_ref = store.put_json(
        {"jurisdiction": "ua"},
        PutOptions(kind="lex.norm_pack", media_type="application/json"),
    )
    missing_report_ref = ArtifactRef.model_validate(
        {
            "artifact_id": "sha256:" + ("f" * 64),
            "kind": "lex.legal_report",
            "media_type": "application/json",
        }
    )

    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.governance.legal_check.evaluate_legality",
        lambda **_: (missing_report_ref, []),
    )

    state = ExperimentState(
        run_id="R_legal_degraded",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_NORM_PACK_REF: norm_pack_ref,
        },
        artifacts_index={
            ARTIFACT_SIMULATION_RESULT_REF: SimulationResultRef(
                artifact_id=simulation_result_ref.artifact_id
            )
        },
        params={"jurisdiction": "UA", "as_of": "2026-01-01", "strict_legal": True},
    )

    outcome = LegalCheckNode().execute(ctx, state)

    assert outcome.status == "ok"
    degraded = [event for event in outcome.events if event.code == "legal_check.report_degraded"]
    assert degraded
    assert degraded[0].attrs["reason"] == "legal_report_grade_load_failed"


def test_legal_check_uses_branch_state_for_inputs_and_reports(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_legal_branch")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.legal.branch"))

    trinity_ref = store.put_json(
        {"policy_spec": {"interventions": []}},
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version="1.0"),
        ),
    )
    simulation_result_ref = store.put_json(
        {"ok": True},
        PutOptions(kind="foundry.simulation_result", media_type="application/json"),
    )
    legal_report_ref = store.put_json(
        {"summary": {"compliance_grade": "pass"}},
        PutOptions(kind="lex.legal_report", media_type="application/json"),
    )
    state = ExperimentState(
        run_id="R_legal_branch",
        inputs={INPUT_TRINITY_BUNDLE_REF: trinity_ref},
        artifacts_index={
            ARTIFACT_SIMULATION_RESULT_REF: SimulationResultRef(
                artifact_id=simulation_result_ref.artifact_id
            )
        },
        params={"jurisdiction": "UA", "as_of": "2026-01-01"},
    )
    observed: dict[str, tuple[str, ...]] = {}

    def _spy_branch(base_state, *, write_paths=()):
        observed["write_paths"] = tuple(write_paths)
        return real_branch_state(base_state, write_paths=write_paths)

    with (
        patch(
            "polisyos.scientist.nodes.builtins.governance.legal_check.branch_state",
            _spy_branch,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.governance.legal_check.evaluate_legality",
            lambda **_: (
                ArtifactRef.model_validate(
                    {
                        "artifact_id": str(legal_report_ref.artifact_id),
                        "kind": "lex.legal_report",
                        "media_type": "application/json",
                    }
                ),
                [],
            ),
        ),
    ):
        outcome = LegalCheckNode().execute(ctx, state)

    assert outcome.status == "ok"
    assert observed["write_paths"] == (
        "inputs.norm_pack_ref",
        "reports_index.legal_report_ref",
        "reports_index.change_proposal_ref",
    )
    assert INPUT_NORM_PACK_REF not in state.inputs
    assert REPORT_LEGAL_REPORT_REF not in state.reports_index
    assert INPUT_NORM_PACK_REF in outcome.state.inputs
    assert REPORT_LEGAL_REPORT_REF in outcome.state.reports_index
