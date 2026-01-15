import pytest
from pydantic import ValidationError

from polisyos.ir.surface import PolicySurfaceIR
from polisyos.ir.types import SelectorOperator
from polisyos.ir.types import TranslatableString
from polisyos.ir.validation import build_validation_report


def minimal_ir_payload() -> dict:
    return {
        "schema_version": "2.0",
        "semantic": {
            "context_snapshot_ref": "sha256:" + "0" * 64,
            "interventions": [],
            "objectives": [],
            "constraints": [],
        },
    }


def test_required_fields_enforced() -> None:
    payload = minimal_ir_payload()
    payload["semantic"].pop("context_snapshot_ref")
    with pytest.raises(ValidationError):
        PolicySurfaceIR.model_validate(payload)


def test_translatable_string_aliases_lowercase_dump() -> None:
    value = TranslatableString.model_validate({"En": "Hello", "Ua": "Hi"})
    dumped = value.model_dump()
    assert "En" not in dumped
    assert "Ua" not in dumped
    assert dumped["en"] == "Hello"
    assert dumped["ua"] == "Hi"


def test_validation_report_has_summary_and_diff() -> None:
    payload = minimal_ir_payload()
    payload.pop("semantic")
    with pytest.raises(ValidationError) as excinfo:
        PolicySurfaceIR.model_validate(payload)
    report = build_validation_report(excinfo.value, before=payload, after=payload)
    assert report.error_summary
    assert report.diff_before_after is not None
    assert report.issues


def test_selector_requires_list_for_in() -> None:
    with pytest.raises(ValidationError):
        PolicySurfaceIR.model_validate(
            {
                "schema_version": "2.0",
                "semantic": {
                    "context_snapshot_ref": "sha256:" + "0" * 64,
                    "interventions": [
                        {
                            "intervention_id": "sub",
                            "kind": "tax_subsidy",
                            "target": {
                                "kind": "predicate",
                                "field": "id",
                                "operator": SelectorOperator.IN,
                                "value": "all",
                            },
                            "schedule": {"start_step": 0, "duration_steps": 1},
                            "params": {"rate": "0.1"},
                        }
                    ],
                },
            }
        )


def test_schedule_requires_end_or_duration() -> None:
    with pytest.raises(ValidationError):
        PolicySurfaceIR.model_validate(
            {
                "schema_version": "2.0",
                "semantic": {
                    "context_snapshot_ref": "sha256:" + "0" * 64,
                    "interventions": [
                        {
                            "intervention_id": "sub",
                            "kind": "tax_subsidy",
                            "target": {
                                "kind": "predicate",
                                "field": "id",
                                "operator": SelectorOperator.EQUALS,
                                "value": "all",
                            },
                            "schedule": {"start_step": 0},
                            "params": {"rate": "0.1"},
                        }
                    ],
                },
            }
        )
