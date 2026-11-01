"""Explicit state input contracts preserve presence, nullability and legacy specs."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.scientist.orchestration.engine.protocol import (
    InputAwareNodeSpec,
    NodeInputRule,
    NodeSpec,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_merge import _MISSING, _get_path


def _metadata() -> ComponentMetadata:
    return ComponentMetadata(
        component_id=ComponentId.parse("scientist.input_contract_test@1.0.0"),
        kind=ComponentKind.SCIENTIST_NODE,
        abi_targets={"world_abi": "1.x"},
        display_name="Input contract test",
        description="Finite state-read requirements",
        capabilities=Capability.SCIENTIST_NODE,
    )


def test_ordinary_node_spec_retains_its_original_payload() -> None:
    ordinary = NodeSpec(metadata=_metadata(), state_reads=["params.value"])
    expected = {
        "metadata": ordinary.metadata.model_dump(mode="python"),
        "state_reads": ["params.value"],
        "state_writes": [],
        "produces": [],
    }
    assert ordinary.model_dump(mode="python") == expected
    assert NodeSpec.model_validate(expected).model_dump(mode="python") == expected


def test_input_contract_is_explicit_and_survives_spec_roundtrip() -> None:
    rules = (
        NodeInputRule(path="inputs.external"),
        NodeInputRule(path="params.optional", availability="optional", allow_null=True),
    )
    spec = InputAwareNodeSpec(
        metadata=_metadata(),
        state_reads=[rule.path for rule in rules],
        input_rules=rules,
    )
    assert InputAwareNodeSpec.model_validate(spec.model_dump(mode="python")) == spec
    assert spec.input_rules[0].availability == "required"
    assert spec.input_rules[1].allow_null


@pytest.mark.parametrize(
    ("reads", "rules", "message"),
    [
        (["params.value"], (), "input_contract_population_mismatch"),
        ([], (NodeInputRule(path="params.value"),), "input_contract_population_mismatch"),
        (
            ["params.value"],
            (NodeInputRule(path="params.value"), NodeInputRule(path="params.value")),
            "input_contract_duplicate_path",
        ),
        (
            ["params.value", "params.value"],
            (NodeInputRule(path="params.value"),),
            "input_contract_duplicate_path",
        ),
    ],
)
def test_input_contract_cannot_omit_or_contradict_a_declared_read(reads, rules, message) -> None:
    with pytest.raises(ValidationError, match=message):
        InputAwareNodeSpec(metadata=_metadata(), state_reads=reads, input_rules=rules)


@pytest.mark.parametrize(
    "path", ["", ".params.value", "params..value", "params.value.", "unknown.x"]
)
def test_input_contract_refuses_unsupported_paths(path: str) -> None:
    with pytest.raises(ValidationError):
        NodeInputRule(path=path)


def test_finite_accessor_preserves_missing_null_zero_false_and_container_identity() -> None:
    state = ExperimentState(
        run_id="R_input_grammar",
        params={
            "rows": [{"value": 0}, {"value": False}, {"value": None}],
            "keys": {"0": "zero", "00": "double-zero"},
        },
    )
    assert _get_path(state, ("params", "rows", "0", "value")) == 0
    assert type(_get_path(state, ("params", "rows", "0", "value"))) is int
    assert _get_path(state, ("params", "rows", "1", "value")) is False
    assert _get_path(state, ("params", "rows", "2", "value")) is None
    assert _get_path(state, ("params", "rows", "3", "value")) is _MISSING
    assert _get_path(state, ("params", "keys", "0")) == "zero"
    assert _get_path(state, ("params", "keys", "00")) == "double-zero"
