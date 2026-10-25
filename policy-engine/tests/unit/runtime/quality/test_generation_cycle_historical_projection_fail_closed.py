from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, Field, computed_field, model_serializer

from polisyos.core.artifacts import ArtifactID, ArtifactRef
from polisyos.core.canon import CanonSpec, from_canonical_bytes, to_canonical_bytes
from polisyos.core.contracts.value_outer_set import DataTrust, ValueOuterSet
from polisyos.runtime.quality import generation_cycle as generation

_FIXTURE_NAME = "generation_cycle_controller_v3.json.fixture"
_FIXTURE_SHA256 = "dba1d1ff6598ac7c7705e2d46fc085e42e6d1f4651e14ab5c16af57f848ea02c"


def _fixture_path() -> Path:
    adjacent = Path(__file__).resolve().parent / "fixtures" / _FIXTURE_NAME
    if adjacent.is_file():
        return adjacent
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "policy-engine/tests/unit/runtime/quality/fixtures" / _FIXTURE_NAME
        if candidate.is_file():
            return candidate
    raise AssertionError("pinned historical fixture is unavailable")


def _v3_fixture() -> tuple[bytes, dict[str, Any]]:
    raw = _fixture_path().read_bytes()
    assert hashlib.sha256(raw).hexdigest() == _FIXTURE_SHA256
    payload = from_canonical_bytes(raw)
    assert isinstance(payload, dict)
    return raw, payload


def _artifact_ref(kind: str, char: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=ArtifactID.from_sha256_hex(char * 64),
        kind=kind,
        media_type="application/json",
    )


def test_pinned_v3_history_projection_remains_byte_exact() -> None:
    raw, payload = _v3_fixture()
    parsed = generation.GenerationCycleRun.model_validate(payload)
    projected = generation._historical_generation_cycle_run_projection(parsed)
    assert to_canonical_bytes(projected, CanonSpec(forbid_floats=False)) == raw
    assert generation.validate_generation_cycle_run_history(payload) == ()


def test_v3_history_refuses_nondefault_current_nested_artifact_field() -> None:
    _raw, payload = _v3_fixture()
    parsed = generation.GenerationCycleRun.model_validate(payload)
    simulation = parsed.cycles[0].simulation.model_copy(
        update={
            "candidate_simulation_n4_source_ref": _artifact_ref(
                "runtime.quality.n4_candidate_scenario_source", "a"
            ),
            "candidate_simulation_context_job_ref": _artifact_ref(
                "runtime.quality.cycle_substrate_context_job", "b"
            ),
            "candidate_simulation_n5_input_ref": _artifact_ref(
                "runtime.quality.candidate_simulation_n5_input", "c"
            ),
            "candidate_simulation_profile_config_ref": (
                "runtime-config:candidate-simulation/fixture@sha256:" + "d" * 64
            ),
            "candidate_simulation_profile_selection_ref": "sha256:" + "e" * 64,
        }
    )
    assert "candidate_simulation_context_job_ref" in simulation.model_fields_set
    cycle = parsed.cycles[0].model_copy(update={"simulation": simulation})
    supplied = parsed.model_copy(update={"cycles": (cycle, *parsed.cycles[1:])})
    wire = supplied.model_dump(mode="json")
    assert (
        wire["cycles"][0]["simulation"]["candidate_simulation_context_job_ref"]["kind"]
        == "runtime.quality.cycle_substrate_context_job"
    )

    issues = generation.validate_generation_cycle_run_history(wire)
    assert len(issues) == 1
    assert issues[0]["code"] == "generation_cycle_historical_projection_invalid"
    assert "generation_cycle_history_field_unrepresentable_in_epoch" in issues[0]["error"]


class _ProjectionChild(BaseModel):
    legacy_value: str
    enabled: bool = True
    retry_limit: int = 1
    label: str = "configured"
    tags: tuple[str, ...] = Field(default_factory=tuple)


class _ProjectionEnvelope(BaseModel):
    historical_child: _ProjectionChild
    historical_marker: str


def _synthetic_historical_schema() -> dict[str, dict[str, dict[str, object]]]:
    child_owner = f"{_ProjectionChild.__module__}.{_ProjectionChild.__qualname__}"
    envelope_owner = f"{_ProjectionEnvelope.__module__}.{_ProjectionEnvelope.__qualname__}"
    return {
        "probe": {
            child_owner: {
                "declared_fields": ["legacy_value"],
                "excluded_fields": [],
                "opaque_fields": [],
                "typed_model_edges": {},
                "field_vocabulary": {},
                "wire_fields": ["legacy_value"],
                "computed_fields": [],
            },
            envelope_owner: {
                "declared_fields": ["historical_child", "historical_marker"],
                "excluded_fields": [],
                "opaque_fields": [],
                "typed_model_edges": {
                    "historical_child": [[[], child_owner]],
                },
                "field_vocabulary": {},
                "wire_fields": ["historical_child", "historical_marker"],
                "computed_fields": [],
            },
        }
    }


def test_nested_current_only_defaults_remain_omittable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        generation,
        "FROZEN_N6_HISTORY_SCHEMA",
        _synthetic_historical_schema(),
    )
    child = _ProjectionChild(
        legacy_value="old",
        enabled=True,
        retry_limit=1,
        label="configured",
        tags=(),
    )
    envelope = _ProjectionEnvelope(
        historical_child=child,
        historical_marker="root",
    )
    wire = envelope.model_dump(mode="json")
    projected = generation._historical_generation_cycle_field_tree(
        envelope,
        wire,
        version="probe",
    )
    assert projected == {
        "historical_child": {"legacy_value": "old"},
        "historical_marker": "root",
    }


@pytest.mark.parametrize(
    "current_child",
    [
        pytest.param(
            _ProjectionChild(legacy_value="old", enabled=False),
            id="false",
        ),
        pytest.param(
            _ProjectionChild(legacy_value="old", retry_limit=0),
            id="zero",
        ),
        pytest.param(
            _ProjectionChild(legacy_value="old", label=""),
            id="empty-string",
        ),
    ],
)
def test_nested_current_only_falsey_nondefaults_refuse(
    monkeypatch: pytest.MonkeyPatch,
    current_child: _ProjectionChild,
) -> None:
    monkeypatch.setattr(
        generation,
        "FROZEN_N6_HISTORY_SCHEMA",
        _synthetic_historical_schema(),
    )
    envelope = _ProjectionEnvelope(
        historical_child=current_child,
        historical_marker="root",
    )
    with pytest.raises(
        ValueError,
        match="generation_cycle_history_field_unrepresentable_in_epoch",
    ):
        generation._historical_generation_cycle_field_tree(
            envelope,
            envelope.model_dump(mode="json"),
            version="probe",
        )


class _UnclassifiedComputedChild(BaseModel):
    legacy_value: str

    @computed_field
    @property
    def current_only_digest_view(self) -> str:
        return "derived:non-default"


class _UnclassifiedSerializerChild(BaseModel):
    legacy_value: str

    @model_serializer(mode="plain")
    def _serialize_with_unclassified_extra(self) -> dict[str, str]:
        return {
            "legacy_value": self.legacy_value,
            "current_only_digest_view": "derived:non-default",
        }


def _synthetic_child_history_schema(
    model: type[BaseModel],
) -> dict[str, dict[str, dict[str, object]]]:
    owner = f"{model.__module__}.{model.__qualname__}"
    return {
        "probe": {
            owner: {
                "declared_fields": ["legacy_value"],
                "excluded_fields": [],
                "opaque_fields": [],
                "typed_model_edges": {},
                "field_vocabulary": {},
                "wire_fields": ["legacy_value"],
                "computed_fields": [],
            }
        }
    }


def test_frozen_value_outer_set_computed_width_keeps_v3_wire_omission() -> None:
    value = ValueOuterSet(
        representation="scenario_set",
        identification_status="partial",
        assumption_status="externally_supported",
        data_trust=DataTrust(
            tier="unit",
            trust_cap=1.0,
            trust_multiplier=1.0,
            authority_ref="unit:value-trust",
        ),
        world_model_record_ref="world-model:unit",
        epoch="2026-10-22",
        representation_status="certified",
    )
    payload = value.model_dump(mode="json")
    assert payload["width"] == []

    projected = generation._historical_generation_cycle_field_tree(
        value,
        payload,
        version="v3",
    )

    expected = {
        "representation": "scenario_set",
        "identification_status": "partial",
        "assumption_status": "externally_supported",
        "data_trust": {
            "tier": "unit",
            "trust_cap": 1.0,
            "trust_multiplier": 1.0,
            "authority_ref": "unit:value-trust",
        },
        "world_model_record_ref": "world-model:unit",
        "epoch": "2026-10-22",
        "representation_status": "certified",
    }
    canonical_spec = CanonSpec(forbid_floats=False)
    assert projected == expected
    assert to_canonical_bytes(projected, canonical_spec) == to_canonical_bytes(
        expected,
        canonical_spec,
    )


@pytest.mark.parametrize(
    ("model", "child"),
    [
        pytest.param(
            _UnclassifiedComputedChild,
            _UnclassifiedComputedChild(legacy_value="old"),
            id="current-computed-extra",
        ),
        pytest.param(
            _UnclassifiedSerializerChild,
            _UnclassifiedSerializerChild(legacy_value="old"),
            id="custom-serializer-extra",
        ),
    ],
)
def test_unclassified_emitted_payload_keys_refuse(
    monkeypatch: pytest.MonkeyPatch,
    model: type[BaseModel],
    child: BaseModel,
) -> None:
    monkeypatch.setattr(
        generation,
        "FROZEN_N6_HISTORY_SCHEMA",
        _synthetic_child_history_schema(model),
    )
    payload = child.model_dump(mode="json")
    assert payload["current_only_digest_view"] == "derived:non-default"

    with pytest.raises(
        ValueError,
        match="generation_cycle_history_emitted_field_unrepresentable_in_epoch",
    ):
        generation._historical_generation_cycle_field_tree(
            child,
            payload,
            version="probe",
        )


class _FrozenExcludedChild(BaseModel):
    legacy_value: str
    excluded_value: str = "current-only"


def test_frozen_excluded_declared_field_remains_omittable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = f"{_FrozenExcludedChild.__module__}.{_FrozenExcludedChild.__qualname__}"
    monkeypatch.setattr(
        generation,
        "FROZEN_N6_HISTORY_SCHEMA",
        {
            "probe": {
                owner: {
                    "declared_fields": ["legacy_value", "excluded_value"],
                    "excluded_fields": ["excluded_value"],
                    "opaque_fields": [],
                    "typed_model_edges": {},
                    "field_vocabulary": {},
                    "wire_fields": ["legacy_value"],
                    "computed_fields": [],
                }
            }
        },
    )
    child = _FrozenExcludedChild(
        legacy_value="old",
        excluded_value="preserve-the-frozen-exclusion",
    )
    payload = child.model_dump(mode="json")

    assert generation._historical_generation_cycle_field_tree(
        child,
        payload,
        version="probe",
    ) == {"legacy_value": "old"}


class _DefaultPreservingSerializerChild(BaseModel):
    legacy_value: str
    current_only: str = ""

    @model_serializer(mode="plain")
    def _serialize_plain(self) -> dict[str, str]:
        return {
            "legacy_value": self.legacy_value,
            "current_only": self.current_only,
        }


class _DerivedDefaultSerializerChild(BaseModel):
    legacy_value: str
    current_only: str = ""

    @model_serializer(mode="plain")
    def _serialize_plain(self) -> dict[str, str]:
        return {
            "legacy_value": self.legacy_value,
            "current_only": "derived-nondefault",
        }


class _AliasTupleDefaultChild(BaseModel):
    legacy_value: str
    current_items: tuple[str, ...] = Field(
        default_factory=tuple,
        alias="currentItems",
        serialization_alias="currentItemsWire",
    )


def test_unrepresented_model_serializer_value_must_match_typed_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    child = _DerivedDefaultSerializerChild(legacy_value="old")
    monkeypatch.setattr(
        generation,
        "FROZEN_N6_HISTORY_SCHEMA",
        _synthetic_child_history_schema(type(child)),
    )
    payload = child.model_dump(mode="json")
    assert payload["current_only"] == "derived-nondefault"
    with pytest.raises(
        ValueError,
        match="generation_cycle_history_field_unrepresentable_in_epoch",
    ):
        generation._historical_generation_cycle_field_tree(
            child,
            payload,
            version="probe",
        )


def test_unrepresented_model_serializer_matching_default_remains_omittable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    child = _DefaultPreservingSerializerChild(legacy_value="old")
    monkeypatch.setattr(
        generation,
        "FROZEN_N6_HISTORY_SCHEMA",
        _synthetic_child_history_schema(type(child)),
    )
    payload = child.model_dump(mode="json")
    assert payload["current_only"] == ""
    projected = generation._historical_generation_cycle_field_tree(
        child,
        payload,
        version="probe",
    )
    assert projected == {"legacy_value": "old"}


def test_unrepresented_alias_tuple_default_uses_json_wire_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    child = _AliasTupleDefaultChild(legacy_value="old")
    monkeypatch.setattr(
        generation,
        "FROZEN_N6_HISTORY_SCHEMA",
        _synthetic_child_history_schema(type(child)),
    )
    payload = child.model_dump(mode="json", by_alias=True)
    assert payload == {"legacy_value": "old", "currentItemsWire": []}
    projected = generation._historical_generation_cycle_field_tree(
        child,
        payload,
        version="probe",
    )
    assert projected == {"legacy_value": "old"}

    python_payload = child.model_dump(mode="python", by_alias=True)
    assert python_payload == {"legacy_value": "old", "currentItemsWire": ()}
    python_projected = generation._historical_generation_cycle_field_tree(
        child,
        python_payload,
        version="probe",
        serialization_mode="python",
    )
    assert python_projected == {"legacy_value": "old"}


def _source_limited_v4_run() -> generation.GenerationCycleRun:
    _raw, v3_payload = _v3_fixture()
    historic = generation.GenerationCycleRun.model_validate(v3_payload)
    return historic.model_copy(
        update={
            "schema_version": "policyos.runtime.generation_cycle_controller.v4",
            "source_preservation_receipt": None,
            "source_custody_limitation": generation.GenerationSourceCustodyLimitation(),
        }
    )


def test_source_limited_v4_serializer_preserves_frozen_wire_and_omits_defaults() -> None:
    _raw, v3_payload = _v3_fixture()
    run = _source_limited_v4_run()
    actual = run.model_dump(mode="json")
    expected = dict(v3_payload)
    expected["schema_version"] = "policyos.runtime.generation_cycle_controller.v4"
    expected["source_preservation_receipt"] = None
    expected["source_custody_limitation"] = run.source_custody_limitation.model_dump(mode="json")
    assert to_canonical_bytes(actual, CanonSpec(forbid_floats=False)) == to_canonical_bytes(
        expected,
        CanonSpec(forbid_floats=False),
    )
    assert generation.validate_generation_cycle_run_history(actual) == ()

    python_actual = run.model_dump(mode="python")
    assert python_actual["schema_version"] == "policyos.runtime.generation_cycle_controller.v4"
    assert python_actual["run_id"] == run.run_id
    assert python_actual["terminal_denominator"] == run.terminal_denominator
    assert isinstance(python_actual["terminal_denominator"], tuple)
    assert isinstance(python_actual["cycles"], tuple)
    assert python_actual["source_preservation_receipt"] is None
    assert python_actual["source_custody_limitation"] == run.source_custody_limitation.model_dump(
        mode="python"
    )


def test_source_limited_v4_serializer_refuses_nondefault_current_fields_and_guard_remains() -> None:
    run = _source_limited_v4_run()
    simulation = run.cycles[0].simulation.model_copy(
        update={
            "candidate_simulation_context_job_ref": _artifact_ref(
                "runtime.quality.cycle_substrate_context_job",
                "f",
            )
        }
    )
    cycle = run.cycles[0].model_copy(update={"simulation": simulation})
    current = run.model_copy(update={"cycles": (cycle, *run.cycles[1:])})
    with pytest.raises(
        ValueError,
        match="generation_cycle_history_field_unrepresentable_in_epoch",
    ):
        current.model_dump(mode="json")
    with pytest.raises(
        ValueError,
        match="generation_cycle_history_field_unrepresentable_in_epoch",
    ):
        current.model_dump(mode="python")

    _raw, v3_payload = _v3_fixture()
    invalid_pre_v6 = dict(v3_payload)
    invalid_pre_v6["cycles"] = [dict(cycle) for cycle in v3_payload["cycles"]]
    invalid_pre_v6["cycles"][0]["simulation"] = dict(invalid_pre_v6["cycles"][0]["simulation"])
    invalid_pre_v6["cycles"][0]["simulation"].update(
        {
            "generic_n4_source_ref": _artifact_ref(
                "runtime.generation_source_handoff",
                "a",
            ).model_dump(mode="json"),
            "generic_context_job_ref": _artifact_ref(
                "runtime.quality.cycle_substrate_context_job",
                "f",
            ).model_dump(mode="json"),
            "generic_profile_ref": _artifact_ref(
                "runtime.quality.generic_cycle_simulation_profile",
                "b",
            ).model_dump(mode="json"),
            "generic_n5_input_ref": _artifact_ref(
                "runtime.quality.generic_cycle_simulation_n5_input",
                "c",
            ).model_dump(mode="json"),
            "generic_profile_selection_ref": "sha256:" + "e" * 64,
        }
    )
    with pytest.raises(
        ValueError,
        match="generation_cycle_pre_v6_cannot_carry_generic_simulation",
    ):
        generation.GenerationCycleRun.model_validate(invalid_pre_v6)


# R8: reconcile actual typed state even when serializer omits a current-only field.


class _SerializerHidingCurrentField(BaseModel):
    legacy_value: str
    current_only: int = 0

    @model_serializer(mode="plain")
    def _serialize_only_frozen_field(self) -> dict[str, str]:
        return {"legacy_value": self.legacy_value}


def _history_schema() -> dict[str, dict[str, dict[str, object]]]:
    owner = (
        f"{_SerializerHidingCurrentField.__module__}.{_SerializerHidingCurrentField.__qualname__}"
    )
    return {
        "probe": {
            owner: {
                "declared_fields": ["legacy_value"],
                "excluded_fields": [],
                "opaque_fields": [],
                "typed_model_edges": {},
                "field_vocabulary": {},
                "wire_fields": ["legacy_value"],
                "computed_fields": [],
            }
        }
    }


def test_implicit_default_is_omittable_even_when_model_serializer_hides_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(generation, "FROZEN_N6_HISTORY_SCHEMA", _history_schema())
    value = _SerializerHidingCurrentField(legacy_value="preserved")
    assert "current_only" not in value.model_fields_set
    payload = value.model_dump(mode="json")
    assert payload == {"legacy_value": "preserved"}

    projected = generation._historical_generation_cycle_field_tree(
        value,
        payload,
        version="probe",
    )

    assert projected == {"legacy_value": "preserved"}


def test_hidden_nondefault_current_state_refuses_when_fields_set_is_stale(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(generation, "FROZEN_N6_HISTORY_SCHEMA", _history_schema())
    value = _SerializerHidingCurrentField(legacy_value="preserved")
    assert "current_only" not in value.model_fields_set

    # Exercise the exact gap: the actual typed model state changes while the
    # serialized field set still says the new field was not supplied.
    object.__setattr__(value, "current_only", 1)
    assert value.current_only == 1
    assert "current_only" not in value.model_fields_set
    payload = value.model_dump(mode="json")
    assert payload == {"legacy_value": "preserved"}

    with pytest.raises(
        ValueError,
        match="generation_cycle_history_field_unrepresentable_in_epoch",
    ):
        generation._historical_generation_cycle_field_tree(
            value,
            payload,
            version="probe",
        )
