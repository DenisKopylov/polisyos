import pytest
from pydantic import ValidationError

from polisyos.ir.contract import PolicyRequestIR, TargetSelector
from polisyos.ir.types import TranslatableString
from polisyos.ir.validation import build_validation_report


def minimal_ir_payload() -> dict:
    return {
        "project_name": {"en": "Test", "ua": "Test"},
        "schema_version": "1.0",
        "generated_at": "2024-01-01T00:00:00",
        "generator": {"name": "policy-engine", "version": "0.1.0"},
        "currency": "USD",
        "time_unit": "year",
        "price_base_year": 2024,
        "simulation_params": {"scope_years": 1, "time_frequency": "M"},
        "scenarios": {
            "random_seed": 7,
            "shocks": [],
            "timeline": {"start_year": 2024, "end_year": 2024},
        },
        "entities": [
            {"id": "root", "entity_type": "agent", "name": {"en": "Root", "ua": "Root"}}
        ],
        "interventions": [
            {
                "id": "sub",
                "name": {"en": "Sub", "ua": "Sub"},
                "target_selector": {
                    "all_of": [{"field": "id", "operator": "==", "value": "root"}]
                },
                "mechanism_type": "tax_subsidy",
                "parameters": {"rate": 0.1},
            }
        ],
        "objectives": [],
    }


def test_required_fields_enforced() -> None:
    payload = minimal_ir_payload()
    payload.pop("generated_at")
    with pytest.raises(ValidationError):
        PolicyRequestIR.model_validate(payload)


def test_selector_text_cannot_replace_ast() -> None:
    with pytest.raises(ValidationError):
        TargetSelector.model_validate({"selector_text": "sector == 'IT'"})


def test_translatable_string_aliases_lowercase_dump() -> None:
    value = TranslatableString.model_validate({"En": "Hello", "Ua": "Hi"})
    dumped = value.model_dump()
    assert "En" not in dumped
    assert "Ua" not in dumped
    assert dumped["en"] == "Hello"
    assert dumped["ua"] == "Hi"


def test_validation_report_has_summary_and_diff() -> None:
    payload = minimal_ir_payload()
    payload.pop("schema_version")
    with pytest.raises(ValidationError) as excinfo:
        PolicyRequestIR.model_validate(payload)
    report = build_validation_report(excinfo.value, before=payload, after=payload)
    assert report.error_summary
    assert report.diff_before_after is not None
    assert report.issues


def test_target_selector_requires_conditions() -> None:
    with pytest.raises(ValidationError):
        TargetSelector.model_validate({})


def test_entity_topology_rejects_cycle() -> None:
    payload = minimal_ir_payload()
    payload["entities"] = [
        {"id": "a", "entity_type": "agent", "name": {"en": "A", "ua": "A"}, "parent_id": "b"},
        {"id": "b", "entity_type": "agent", "name": {"en": "B", "ua": "B"}, "parent_id": "a"},
    ]
    with pytest.raises(ValidationError):
        PolicyRequestIR.model_validate(payload)


def test_entity_topology_requires_existing_parent() -> None:
    payload = minimal_ir_payload()
    payload["entities"] = [
        {
            "id": "child",
            "entity_type": "agent",
            "name": {"en": "Child", "ua": "Child"},
            "parent_id": "missing",
        }
    ]
    with pytest.raises(ValidationError):
        PolicyRequestIR.model_validate(payload)

