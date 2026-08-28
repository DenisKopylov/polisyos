from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

import polisyos.foundry.data_plane as data_plane
from polisyos.ir.observation.bundles import (
    DYNAMIC_TREATMENT_TARGET,
    ContractCompatibilityTarget,
)


def _dynamic_payload() -> dict[str, Any]:
    return {
        "outcome": [float(index) for index in range(10)],
        "treatment_sequence": [[0, 1] for _ in range(10)],
        "covariate_sequence": [[[0.0], [1.0]] for _ in range(10)],
        "time_ids": ["baseline", "treated"],
        "variable_names": ["covariate"],
        "treatment_name": "A",
        "outcome_name": "Y",
        "behavior_policy_probs": None,
        "metadata": {"source": "neutral_ir_payload"},
    }


def _materialize(
    target: ContractCompatibilityTarget,
    payload: Mapping[str, Any],
) -> Any:
    materialize = getattr(data_plane, "materialize_method_contract", None)
    assert callable(materialize), "Foundry data plane must own method-contract materialization"
    return materialize(contract_target=target, contract_payload=payload)


def test_materialize_method_contract_round_trips_deterministically() -> None:
    first = _materialize(DYNAMIC_TREATMENT_TARGET, _dynamic_payload())
    canonical_payload = first.model_dump(mode="json")

    second = _materialize(DYNAMIC_TREATMENT_TARGET, canonical_payload)

    assert type(first).__name__ == "DynamicTreatmentData"
    assert second.model_dump(mode="json") == canonical_payload


def test_materialize_method_contract_rejects_unknown_contract_family() -> None:
    unknown_target = ContractCompatibilityTarget(
        contract_id="foundry.unknown.payload.v1",
        contract_fqn="polisyos.foundry.methods.catalog.unknown.UnknownData",
    )

    with pytest.raises(ValueError, match="unsupported method contract"):
        _materialize(unknown_target, {"value": 1})


def test_materialize_method_contract_rejects_mismatched_fqn() -> None:
    mismatched_target = DYNAMIC_TREATMENT_TARGET.model_copy(
        update={"contract_fqn": "polisyos.foundry.methods.catalog.causal.protocols.OtherData"}
    )

    with pytest.raises(ValueError, match="contract target mismatch"):
        _materialize(mismatched_target, _dynamic_payload())


def test_materialize_method_contract_rejects_malformed_known_payload() -> None:
    malformed_payload = _dynamic_payload()
    malformed_payload["outcome"] = [1.0]

    with pytest.raises(ValueError, match="invalid payload"):
        _materialize(DYNAMIC_TREATMENT_TARGET, malformed_payload)
