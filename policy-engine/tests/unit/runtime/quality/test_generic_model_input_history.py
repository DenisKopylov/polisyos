"""Recorded call normalization and real immutable-event intake for history.

The component basis below declares unavailable source custody. It establishes
only the selected CAS/event boundary; the served A/B/C scenario proves complete
numerical history replay and separation from present provider admission.
"""

from __future__ import annotations

import hashlib
import sqlite3
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from polisyos.core import artifacts
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.quality import acquisition_evaluation as owner
from polisyos.runtime.quality.authority_reconciliation import AuthorityReconciliationError
from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
from polisyos.runtime.quality.n5_execution_basis import (
    exact_n5_content_bytes,
    exact_n5_content_hash,
)


def _step(step: int, content: bytes) -> Any:
    return SimpleNamespace(
        step=step,
        calls=(
            SimpleNamespace(
                plan_index=2, node_id="scheduled-node", callable_receiver_hex=content.hex()
            ),
        ),
    )


def test_recorded_call_content_reconciles_every_physical_unit_without_live_code() -> None:
    first = exact_n5_content_bytes({"recorded_callable": "old-provider-a", "parameter": 3})
    second = exact_n5_content_bytes({"recorded_callable": "old-provider-a", "parameter": 4})
    observed = SimpleNamespace(
        numerical_intent_profile=owner.GENERIC_NUMERICAL_INTENT_PROFILE,
        steps=(_step(1, second), _step(0, first), _step(0, first)),
    )

    assert owner._recorded_generic_model_input_calls(observed) == (
        (2, "scheduled-node", 0, first),
        (2, "scheduled-node", 1, second),
    )
    graft = SimpleNamespace(
        numerical_intent_profile=owner.GENERIC_NUMERICAL_INTENT_PROFILE,
        steps=(_step(0, first), _step(0, second)),
    )
    with pytest.raises(ValueError, match="history_call_census_mismatch"):
        owner._recorded_generic_model_input_calls(graft)


@pytest.mark.parametrize("content", [b"not JSON", b' {"mapping":[]}', b"{}\n"])
def test_recorded_call_requires_the_original_canonical_wire(content: bytes) -> None:
    with pytest.raises(ValueError, match="n5_content_wire_invalid"):
        owner._recorded_generic_model_input_calls(
            SimpleNamespace(
                numerical_intent_profile=owner.GENERIC_NUMERICAL_INTENT_PROFILE,
                steps=(_step(0, content),),
            )
        )


def _component_basis(store: Any) -> owner.GenericModelInputEvaluationBasisV1:
    def component_ref(kind: str) -> artifacts.ArtifactRef:
        return store.put_json(
            {"component_only": kind, "source_authority": "not_established"},
            artifacts.ArtifactWriteOptions(kind=kind, media_type="application/json"),
            return_selected_profile=True,
        )

    encoded = exact_n5_content_bytes({"source_custody": "not_established"})
    payload = {
        "schema_version": "GenericModelInputEvaluationBasis@1.0",
        "authority_purpose": "candidate_evaluation_retention_only",
        "comparison_profile": "generic_program_graph_declared_numerical_v2",
        "basis_role": "blocked",
        "tenant_id": "tenant-history",
        "cell_id": "cell-history",
        "run_id": "component-history-run",
        "source_job_id": "component-source",
        "action_job_id": "component-action",
        "route_id": "sha256:" + "1" * 64,
        "design_problem_ref": "sha256:" + "2" * 64,
        "design_problem_basis_ref": "sha256:" + "3" * 64,
        "candidate_id": "component-candidate",
        "input_ref": component_ref("runtime.quality.generic_cycle_simulation_n5_input").model_dump(
            mode="json"
        ),
        "semantic_successor_ref": component_ref(
            "runtime.quality.model_input_successor_selection"
        ).model_dump(mode="json"),
        "bound_state_snapshot_ref": component_ref("foundry.state_snapshot").model_dump(mode="json"),
        "evaluation": None,
        "prospective_basis_ref": None,
        "comparison_decision_ref": None,
        "predicate_provenance": "not_established",
        "reason_codes": ["component_source_not_established"],
        "limitations": ["synthetic_component_only"],
        "closure_residuals": list(owner.CANDIDATE_N5_CLOSURE_RESIDUALS_V2),
        "observed_admission": False,
        "publication_authority": False,
        "numerical_intent_hex": encoded.hex(),
        "numerical_intent_sha256": "sha256:" + hashlib.sha256(encoded).hexdigest(),
    }
    return owner.GenericModelInputEvaluationBasisV1.model_validate(
        {**payload, "content_hash": exact_n5_content_hash(payload)}
    )


def test_history_intake_cannot_replace_the_selected_profile_or_drop_its_event(
    tmp_path: Path,
) -> None:
    from tests.unit.runtime.quality.test_candidate_experiment_reuse_occurrence import (
        _write_profile_variant,
    )

    database_path = tmp_path / "control.sqlite3"
    with (
        tenant_scope(None, tenant_id="tenant-history", cell_id="cell-history"),
        closing(ControlPlaneStore(backend="sqlite", sqlite_path=database_path)) as control,
    ):
        store = artifacts.FileSystemCAS(tmp_path / "cas")
        events = RuntimeDiagnosticEventLog(store=control, artifact_store=store)
        basis = _component_basis(store)
        ref = owner.persist_acquisition_evaluation_artifact(
            store=store, event_log=events, record=basis
        )
        assert (
            owner.read_acquisition_evaluation_artifact(
                store=store, event_log=events, ref=ref, record_type=type(basis)
            )
            == basis
        )
        foreign = _write_profile_variant(
            store, ref, producer=artifacts.ProducerInfo(component="foreign.producer", version="1")
        )
        assert foreign.artifact_id == ref.artifact_id
        assert foreign.manifest_profile_sha256 != ref.manifest_profile_sha256
        with pytest.raises(ValueError, match="artifact_owner_mismatch"):
            owner.replay_generic_model_input_basis_for_history(
                store=store,
                event_log=events,
                origin=None,
                basis_ref=foreign,
                evaluation_context=None,
            )
        with sqlite3.connect(database_path) as connection:
            removed = connection.execute(
                "DELETE FROM control_diagnostic_events WHERE event_id = ?",
                (owner._generic_model_input_evaluation_event_id(basis),),
            ).rowcount
        assert removed == 1
        with pytest.raises(AuthorityReconciliationError) as refused:
            owner.replay_generic_model_input_basis_for_history(
                store=store,
                event_log=events,
                origin=None,
                basis_ref=ref,
                evaluation_context=None,
            )
        assert refused.value.code == "authority_orphan_cas"
        assert refused.value.details == {
            "event_id": owner._generic_model_input_evaluation_event_id(basis),
            "record_count": 0,
        }
