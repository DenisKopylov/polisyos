"""Native request equality is not inferred from Python float/model equality."""

from __future__ import annotations

import struct
from dataclasses import fields

import pytest
from pydantic.fields import FieldInfo

from polisyos.runtime.quality.candidate_simulation import (
    CandidateN5RequestValues,
    CandidateScenarioN5Config,
    prepare_candidate_n5_request_values,
)
from polisyos.runtime.quality.joint_simulation_horizon import HorizonSpec


def _config(zero: float) -> CandidateScenarioN5Config:
    return CandidateScenarioN5Config(
        budget_ref="budget://native-request-test",
        horizon=HorizonSpec(start=0, end=2),
        baseline_state={"target": zero, "outcome": 91.0},
        comparator_refs=("comparator://declared",),
        seed=7,
        replications=2,
    )


def test_native_request_preparation_covers_actual_source_fields_and_value_bits() -> None:
    config = _config(-0.0)
    prepared = prepare_candidate_n5_request_values(config)
    assert {field.name for field in fields(prepared)} == set(type(config).model_fields)
    assert set(dict(prepared.horizon)) == set(type(config.horizon).model_fields)
    assert prepared.horizon_spec == config.horizon
    for name, value in config.baseline_state.items():
        assert dict(prepared.baseline_state)[name] == struct.pack("!d", value)
        assert struct.pack("!d", prepared.baseline_values()[name]) == struct.pack("!d", value)
    for name in type(config).model_fields:
        if name not in {"horizon", "baseline_state"}:
            assert getattr(prepared, name) == getattr(config, name)
    positive = _config(0.0)
    assert config == positive  # cheap proxy's divergent boundary
    assert prepared != prepare_candidate_n5_request_values(positive)
    assert struct.pack("!d", prepared.baseline_values()["target"]) != struct.pack("!d", 0.0)
    assert isinstance(prepared, CandidateN5RequestValues)


def test_new_unclassified_request_field_cannot_silently_disappear(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config(0.0)
    changed = dict(CandidateScenarioN5Config.model_fields)
    changed["new_required_semantic_input"] = FieldInfo(annotation=str)
    with monkeypatch.context() as patch:
        patch.setattr(CandidateScenarioN5Config, "__pydantic_fields__", changed)
        with pytest.raises(ValueError, match="candidate_n5_request_schema_not_supported"):
            prepare_candidate_n5_request_values(config)
