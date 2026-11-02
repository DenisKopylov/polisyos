"""Captured demographic identities reach real readers and a native aging consumer.

The reused producer fixture selects the supported local diagnostic server
configuration and bypasses only the independent Part-A qualification predicate.
The producer, verified stage/CAS readers, member integrity, NumPy and Foundry
consumer are real; source facts and the calibration prerequisite remain synthetic.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from polisyos.core.artifacts import FileSystemCAS
from polisyos.data_forge.domains.ukraine.demography import (
    load_demography_artifacts,
    load_donor_pool,
    load_reconciled_targets,
    load_transition_priors,
)
from polisyos.data_forge.domains.ukraine.demography.source_inventory import (
    InventorySourceRequest,
    SourceFact,
    SourceResolutionRefusalError,
    SourceSemanticClaims,
)
from polisyos.data_forge.domains.ukraine.models import StageId
from polisyos.data_forge.domains.ukraine.static_aging import build_static_aging_state
from polisyos.data_forge.read_api.ukraine import load_verified_stage_artifacts
from tests.unit.data_forge.domains.ukraine.test_demography_source_inventory import (
    _claims,
    _make_candidate,
)


def _captured_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    state_ids: list[str] | None = None,
    member_overrides: dict[str, dict[str, object]] | None = None,
    source_claims: SourceSemanticClaims | None = None,
) -> InventorySourceRequest:
    manifest, root, store = _make_candidate(
        tmp_path,
        monkeypatch,
        state_ids=state_ids,
        member_overrides=member_overrides,
        source_claims=source_claims,
    )
    # A fresh actual reader opens the selected stage output from the existing CAS.
    fresh_store = FileSystemCAS(store.root)
    receipt = load_verified_stage_artifacts(
        manifest,
        store=fresh_store,
        allowed_root=root,
        expected_stage=StageId.DEMOGRAPHY_SOURCE_INVENTORY.value,
        required_outputs=("inventory.json",),
    )
    return InventorySourceRequest(kind="inventory", stage_receipt=receipt, store=fresh_store)


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ([2**53 + 1, 1.0], [2**53 + 1, 1]),
        ([2**63 - 1, 1.0], [2**63 - 1, 1]),
        ([-(2**63), -1.0], [-(2**63), -1]),
    ],
)
def test_captured_raw_json_and_candidate_readers_preserve_mixed_record_ids(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    values: list[object],
    expected: list[int],
) -> None:
    source = _captured_source(
        tmp_path, monkeypatch, member_overrides={"donor": {"donor_record_index": values}}
    )
    donors = load_donor_pool(source=source)
    assert donors["donor_record_index"] == values
    aggregate = load_demography_artifacts(source=source)
    assert aggregate.donor_record_index.tolist() == expected
    state = build_static_aging_state(
        base_weights=[10.0, 20.0], origin_state_index=[0, 1], artifacts=aggregate
    )
    assert state["donor_record_index"].tolist() == expected


@pytest.mark.parametrize(
    ("field", "values"),
    [
        ("donor_state_index", [0.9, 1]),
        ("donor_record_index", [1001.9, 1002]),
        ("donor_record_index", [2**63, 1.0]),
    ],
)
def test_captured_candidate_invalid_ids_refuse_all_public_routes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str, values: list[object]
) -> None:
    source = _captured_source(tmp_path, monkeypatch, member_overrides={"donor": {field: values}})
    for reader in (
        load_reconciled_targets,
        load_transition_priors,
        load_donor_pool,
        load_demography_artifacts,
    ):
        with pytest.raises(SourceResolutionRefusalError) as raised:
            reader(source=source)
        assert raised.value.code == "demography_bundle_invalid"


@pytest.mark.parametrize("role", ["priors", "donor"])
def test_captured_candidate_role_conflict_refuses_without_target_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, role: str
) -> None:
    source = _captured_source(
        tmp_path,
        monkeypatch,
        member_overrides={role: {"target_state_totals": [900.0, 800.0]}},
    )
    for reader in (load_reconciled_targets, load_demography_artifacts):
        with pytest.raises(SourceResolutionRefusalError) as raised:
            reader(source=source)
        assert raised.value.code == "demography_role_conflict"


def test_three_state_captured_candidate_reaches_native_foundry_without_authority_promotion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polisyos.foundry.methods.catalog.simulation.demography import (
        StaticAgingSimulationEstimator,
    )

    ids = ["north", "middle", "south"]
    claims = _claims(ids)
    claims.facts["source_owner_id"] = SourceFact(value=None, provenance="not_established")
    source = _captured_source(
        tmp_path,
        monkeypatch,
        state_ids=ids,
        source_claims=claims,
        member_overrides={
            "targets": {
                "target_state_totals": [30.0, 20.0, 50.0],
                "entrant_state_totals": [1.0, 1.0, 1.0],
                "metadata": {"shared": "targets", "targets_note": {"values": ["t"]}},
            },
            "priors": {
                "transition_prior_matrix": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
                "allowed_transition_mask": [
                    [True, False, False],
                    [False, True, False],
                    [False, False, True],
                ],
                "metadata": {"shared": "priors", "priors_note": {"values": ["p"]}},
            },
            "donor": {
                "donor_weights": [0.25, 0.75, 0.5],
                "donor_state_index": [0, 1, 2],
                "donor_record_index": [2**53 + 1, -1002, 1003],
                "metadata": {"shared": "donor", "donor_note": {"values": ["d"]}},
            },
        },
    )
    targets = load_reconciled_targets(source=source)
    priors = load_transition_priors(source=source)
    donors = load_donor_pool(source=source)
    artifacts = load_demography_artifacts(source=source)
    assert targets["state_ids"] == ids == artifacts.state_ids
    assert (
        targets["target_state_totals"]
        == artifacts.target_state_totals.tolist()
        == [30.0, 20.0, 50.0]
    )
    assert priors["transition_prior_matrix"] == np.eye(3).tolist()
    assert donors["donor_record_index"] == [2**53 + 1, -1002, 1003]
    before_evidence = artifacts.source_evidence.model_dump(mode="json")
    assert before_evidence["source_claims"]["facts"]["source_owner_id"] == {
        "value": None,
        "provenance": "not_established",
    }
    assert before_evidence["source_fact_provenance"] == "consumer_asserted"
    assert before_evidence["source_currentness_provenance"] == "not_established"
    assert before_evidence["member_content_binding_provenance"] == "recomputed"
    state = build_static_aging_state(
        base_weights=[29.0, 19.0, 49.0],
        origin_state_index=[0, 1, 2],
        artifacts=artifacts,
        microsim_calibration_report={
            "decision": "pass",
            "can_run_microsim": True,
            "compatibility_status": "compatible",
        },
    )
    result = StaticAgingSimulationEstimator.pure_step(state, {})["result"]
    assert np.allclose(result.aged_state_totals, [30.0, 20.0, 50.0])
    assert result.entrant_record_index.tolist() == [2**53 + 1, -1002, 1003]
    assert result.entrant_state_index.tolist() == [0, 1, 2]
    assert np.allclose(result.entrant_weights, [1.0, 1.0, 1.0])
    assert result.diagnostics["demography_source_evidence"] == before_evidence
    assert result.diagnostics["demography_source_evidence"]["source_status"] == "candidate_only"
    for role in ("targets", "priors", "donor"):
        assert artifacts.metadata["demography_role_metadata"][role]["shared"] == role
    exported = targets.evidence
    assert exported.source_claims is not None
    exported.source_claims.facts["source_owner_id"] = SourceFact(
        value="caller-only", provenance="consumer_asserted"
    )
    state["donor_record_index"][0] = 999
    assert (
        load_demography_artifacts(source=source).source_evidence.model_dump(mode="json")
        == before_evidence
    )
    fresh_state = build_static_aging_state(
        base_weights=[29.0, 19.0, 49.0], origin_state_index=[0, 1, 2], artifacts=artifacts
    )
    assert fresh_state["donor_record_index"].tolist() == [2**53 + 1, -1002, 1003]
