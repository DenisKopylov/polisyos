from __future__ import annotations

import json
from typing import Any

import pytest
from polisyos.ir.canon import CanonViolation, from_canonical_bytes
from polisyos.ir.governance.selector_expr import SelectorExpr
from polisyos.ir.migrations.base import migrate_artifact, register_migration
from polisyos.ir.world.ids import claim_id_from_payload
from pydantic import TypeAdapter, ValidationError

try:
    from hypothesis import HealthCheck, given, settings
    from hypothesis import strategies as st
except ImportError:  # pragma: no cover - optional dependency
    pytest.skip("hypothesis not installed", allow_module_level=True)


@register_migration("phase3_fuzz_artifact", "1.0", "1.1")
def _phase3_fuzz_migration(data: dict[str, Any]) -> dict[str, Any]:
    payload = dict(data)
    payload.pop("schema_version", None)
    payload["migrated"] = True
    return payload


_SELECTOR_ADAPTER = TypeAdapter(SelectorExpr)
_CANONICAL_TYPES = {"datetime", "date", "decimal", "bytes", "float"}
_HEALTH_CHECKS = [HealthCheck.too_slow]

_JSON_SCALAR = (
    st.none()
    | st.booleans()
    | st.integers(min_value=-100, max_value=100)
    | st.text(min_size=1, max_size=12)
)
_JSON_VALUE = st.recursive(
    _JSON_SCALAR,
    lambda children: st.lists(children, max_size=4)
    | st.dictionaries(st.text(min_size=1, max_size=8), children, max_size=4),
    max_leaves=10,
)

_WORLD_VALUE = st.recursive(
    _JSON_SCALAR,
    lambda children: st.lists(children, max_size=3)
    | st.dictionaries(st.text(min_size=1, max_size=6), children, max_size=3),
    max_leaves=8,
)

_FIELD_SEGMENT = st.text(
    alphabet=st.characters(
        whitelist_categories=("Ll", "Lu", "Nd"),
        whitelist_characters=("_",),
    ),
    min_size=1,
    max_size=8,
)
_SELECTOR_FIELD = st.lists(_FIELD_SEGMENT, min_size=1, max_size=3).map(".".join)
_DEEP_SELECTOR_FIELD = st.lists(_FIELD_SEGMENT, min_size=9, max_size=12).map(".".join)
_SELECTOR_SCALAR = st.one_of(
    st.text(min_size=1, max_size=8),
    st.integers(min_value=-10, max_value=10),
    st.booleans(),
)
_NUMERIC_SELECTOR = st.integers(min_value=-10, max_value=10)

_VALID_PREDICATE = st.one_of(
    st.builds(
        lambda field, value: {
            "kind": "predicate",
            "field": field,
            "operator": "==",
            "value": value,
        },
        _SELECTOR_FIELD,
        _SELECTOR_SCALAR,
    ),
    st.builds(
        lambda field, value: {
            "kind": "predicate",
            "field": field,
            "operator": ">=",
            "value": value,
        },
        _SELECTOR_FIELD,
        _NUMERIC_SELECTOR,
    ),
    st.builds(
        lambda field, values: {
            "kind": "predicate",
            "field": field,
            "operator": "in",
            "value": values,
        },
        _SELECTOR_FIELD,
        st.lists(_SELECTOR_SCALAR, min_size=1, max_size=4, unique=True),
    ),
    st.builds(
        lambda field, bounds: {
            "kind": "predicate",
            "field": field,
            "operator": "between",
            "value": [min(bounds), max(bounds)],
        },
        _SELECTOR_FIELD,
        st.tuples(_NUMERIC_SELECTOR, _NUMERIC_SELECTOR),
    ),
)

_VALID_SELECTOR = st.recursive(
    _VALID_PREDICATE,
    lambda children: st.one_of(
        st.builds(
            lambda clauses: {"kind": "all_of", "clauses": clauses},
            st.lists(children, min_size=1, max_size=3),
        ),
        st.builds(
            lambda clauses: {"kind": "any_of", "clauses": clauses},
            st.lists(children, min_size=1, max_size=3),
        ),
        st.builds(
            lambda clause: {"kind": "not", "clause": clause},
            children,
        ),
        st.builds(
            lambda collection_field, clause: {
                "kind": "quantifier",
                "quantifier": "exists",
                "collection_field": collection_field,
                "clause": clause,
            },
            _SELECTOR_FIELD,
            children,
        ),
        st.builds(
            lambda collection_field, threshold, clause: {
                "kind": "quantifier",
                "quantifier": "at_least",
                "collection_field": collection_field,
                "threshold": threshold,
                "clause": clause,
            },
            _SELECTOR_FIELD,
            st.integers(min_value=0, max_value=3),
            children,
        ),
        st.builds(
            lambda collection_field, value, where: {
                "kind": "aggregate",
                "aggregation": "count",
                "collection_field": collection_field,
                "operator": ">=",
                "value": value,
                **({"where": where} if where is not None else {}),
            },
            _SELECTOR_FIELD,
            st.integers(min_value=0, max_value=3),
            st.one_of(st.none(), children),
        ),
        st.builds(
            lambda clause, upper_bound: {
                "kind": "temporal",
                "temporal_operator": "eventually_within",
                "clause": clause,
                "upper_bound": upper_bound,
                "clock_field": "time.step",
            },
            children,
            st.integers(min_value=0, max_value=4),
        ),
    ),
    max_leaves=12,
)

_INVALID_SELECTOR = st.one_of(
    st.builds(
        lambda field: {
            "kind": "predicate",
            "field": field,
            "operator": ">",
            "value": "not-a-number",
        },
        _SELECTOR_FIELD,
    ),
    st.builds(
        lambda field: {
            "kind": "predicate",
            "field": field,
            "operator": "in",
            "value": [],
        },
        _SELECTOR_FIELD,
    ),
    st.builds(
        lambda field: {
            "kind": "predicate",
            "field": field,
            "operator": "==",
            "value": [1, 2],
        },
        _SELECTOR_FIELD,
    ),
    st.builds(
        lambda field: {
            "kind": "predicate",
            "field": field,
            "operator": "between",
            "value": [1],
        },
        _SELECTOR_FIELD,
    ),
    st.builds(
        lambda clause: {
            "kind": "quantifier",
            "quantifier": "exists",
            "collection_field": "population.households",
            "threshold": 1,
            "clause": clause,
        },
        _VALID_PREDICATE,
    ),
    st.builds(
        lambda clause: {
            "kind": "temporal",
            "temporal_operator": "ever",
            "clause": clause,
            "upper_bound": 1,
        },
        _VALID_PREDICATE,
    ),
    st.builds(
        lambda field: {
            "kind": "predicate",
            "field": field,
            "operator": "==",
            "value": "x",
        },
        _DEEP_SELECTOR_FIELD,
    ),
)


def _deep_mapping(depth: int) -> dict[str, object]:
    root: dict[str, object] = {}
    current = root
    for idx in range(depth):
        child: dict[str, object] = {}
        current[f"k{idx}"] = child
        current = child
    return root


@settings(deadline=None, suppress_health_check=_HEALTH_CHECKS)
@given(
    unknown_type=st.text(min_size=1, max_size=12).filter(
        lambda value: value not in _CANONICAL_TYPES
    ),
    payload=_JSON_VALUE,
)
def test_canonical_deserialization_rejects_unknown_types_fuzz(
    unknown_type: str,
    payload: object,
) -> None:
    encoded = json.dumps({"_type": unknown_type, "value": payload}).encode("utf-8")

    with pytest.raises(CanonViolation, match="Unknown canonical _type"):
        from_canonical_bytes(encoded)


@settings(deadline=None, suppress_health_check=_HEALTH_CHECKS)
@given(depth=st.integers(min_value=5, max_value=24))
def test_canonical_deserialization_rejects_excessive_depth_fuzz(depth: int) -> None:
    encoded = json.dumps(_deep_mapping(depth)).encode("utf-8")

    with pytest.raises(CanonViolation, match="max_depth=4"):
        from_canonical_bytes(encoded, max_depth=4)


@settings(deadline=None, suppress_health_check=_HEALTH_CHECKS)
@given(payload=_VALID_SELECTOR)
def test_selector_ast_fuzz_accepts_valid_payloads(payload: dict[str, Any]) -> None:
    selector = _SELECTOR_ADAPTER.validate_python(payload)

    dumped = selector.model_dump(mode="json")
    assert dumped["kind"] == payload["kind"]


@settings(deadline=None, suppress_health_check=_HEALTH_CHECKS)
@given(payload=_INVALID_SELECTOR)
def test_selector_ast_fuzz_rejects_invalid_payloads(payload: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        _SELECTOR_ADAPTER.validate_python(payload)


@settings(deadline=None, suppress_health_check=_HEALTH_CHECKS)
@given(
    value_text=st.text(min_size=1, max_size=12),
    qualifiers=st.dictionaries(st.text(min_size=1, max_size=6), _WORLD_VALUE, max_size=4),
)
def test_world_ids_are_stable_across_mapping_order_fuzz(
    value_text: str,
    qualifiers: dict[str, object],
) -> None:
    ordered_payload = {
        "predicate_id": "pred.test",
        "subject_id": "entity.test",
        "value_text": value_text,
        "source_kind": "dataset",
        "source_artifacts": ["sha256:" + "a" * 64],
        "qualifiers": dict(qualifiers.items()),
    }
    reordered_payload = {
        **ordered_payload,
        "qualifiers": dict(reversed(list(qualifiers.items()))),
    }

    assert claim_id_from_payload(claim_payload=ordered_payload) == claim_id_from_payload(
        claim_payload=reordered_payload
    )


@settings(deadline=None, suppress_health_check=_HEALTH_CHECKS)
@given(
    schema_version=st.one_of(
        st.none(),
        st.sampled_from(["1.0", "1.1", "0.9", "2.0"]),
    ),
    payload=st.dictionaries(
        st.text(min_size=1, max_size=6).filter(lambda value: value != "schema_version"),
        _JSON_VALUE,
        max_size=4,
    ),
)
def test_migration_inputs_fail_closed_or_stamp_registered_target(
    schema_version: str | None,
    payload: dict[str, object],
) -> None:
    migration_payload = dict(payload)
    if schema_version is not None:
        migration_payload["schema_version"] = schema_version

    if schema_version is None:
        with pytest.raises(ValueError, match="Missing schema_version"):
            migrate_artifact(migration_payload, "phase3_fuzz_artifact", "1.1")
        return

    if schema_version == "1.0":
        migrated = migrate_artifact(migration_payload, "phase3_fuzz_artifact", "1.1")
        assert migrated["schema_version"] == "1.1"
        assert migrated["migrated"] is True
        return

    if schema_version == "1.1":
        assert migrate_artifact(migration_payload, "phase3_fuzz_artifact", "1.1") == (
            migration_payload
        )
        return

    with pytest.raises(ValueError, match="No migrat"):
        migrate_artifact(migration_payload, "phase3_fuzz_artifact", "1.1")
