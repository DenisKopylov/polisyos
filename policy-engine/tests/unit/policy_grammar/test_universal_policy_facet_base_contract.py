"""Public grammar facet contracts stay closed at the generic and specialized surfaces."""

from enum import Enum
from typing import Literal, get_args, get_origin

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

import polisyos.core.contracts as public_contracts
from polisyos.core.contracts.runtime import (
    UniversalPolicyFacetBase,
    UniversalPolicyFacetName,
    UniversalPolicyFacets,
)


def _grounding(facet_name: str) -> dict[str, object]:
    return {
        "facet_name": facet_name,
        "concept_spine_refs": ["concept"],
        "source_vocabulary_refs": ["vocabulary"],
        "derivation_rule_ref": "rule",
    }


def _schema_values(schema: dict[str, object]) -> tuple[object, ...]:
    if "const" in schema:
        return (schema["const"],)
    return tuple(schema.get("enum", ()))


def _representative_value(annotation: object) -> object:
    if get_origin(annotation) is Literal:
        return get_args(annotation)[0]
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return next(iter(annotation))
    raise AssertionError(f"Unsupported facet value annotation: {annotation!r}")


def test_thirteen_public_facet_grammar_exports_remain_available() -> None:
    specialized_names = {
        field.annotation.__name__ for field in UniversalPolicyFacets.model_fields.values()
    }
    public_names = specialized_names | {"UniversalPolicyFacetName", "UniversalPolicyFacets"}
    assert len(public_names) == 13
    assert public_names <= set(public_contracts.__all__)


def test_public_facet_base_accepts_the_complete_declared_name_algebra() -> None:
    declared_names = get_args(UniversalPolicyFacetName)
    assert len(declared_names) == 11
    assert set(UniversalPolicyFacets.model_fields) == set(declared_names)

    for facet_name in declared_names:
        model = UniversalPolicyFacetBase.model_validate(_grounding(facet_name))
        assert model.facet_name == facet_name


def test_public_facet_base_rejects_names_outside_the_declared_algebra() -> None:
    with pytest.raises(ValidationError):
        UniversalPolicyFacetBase.model_validate(_grounding("outside_declared_facet_algebra"))


def test_public_facet_base_json_schema_rejects_names_outside_the_algebra() -> None:
    schema = UniversalPolicyFacetBase.model_json_schema()
    name_schema = schema["properties"]["facet_name"]
    assert set(name_schema.get("enum", ())) == set(get_args(UniversalPolicyFacetName))
    validator = Draft202012Validator(schema)
    for facet_name in get_args(UniversalPolicyFacetName):
        assert validator.is_valid(_grounding(facet_name))
    assert not validator.is_valid(_grounding("outside_declared_facet_algebra"))


def test_all_specialized_facet_names_remain_positive_and_schema_constrained() -> None:
    declared_names = set(get_args(UniversalPolicyFacetName))
    assert set(UniversalPolicyFacets.model_fields) == declared_names

    for facet_name, field in UniversalPolicyFacets.model_fields.items():
        model_type = field.annotation
        model = model_type.model_validate(
            {
                **_grounding(facet_name),
                "value": _representative_value(model_type.model_fields["value"].annotation),
            }
        )
        assert model.facet_name == facet_name
        assert _schema_values(model_type.model_json_schema()["properties"]["facet_name"]) == (
            facet_name,
        )
        assert model_type.model_validate_json(model.model_dump_json()).facet_name == facet_name
