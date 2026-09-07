"""Schema-derived complete subject binding at both publication consumers."""

from __future__ import annotations

import json
from copy import deepcopy

import duckdb
import pytest

from polisyos.data_forge.domains.academic.batch.admitted_claim_adjudications import (
    load_verified_claim_adjudication_rows,
)
from polisyos.data_forge.domains.academic.batch.config import AcademicBatchConfig
from polisyos.data_forge.domains.academic.batch.conflict_resolve import run_conflict_resolve
from polisyos.data_forge.domains.academic.batch.graph_builder import build_graph
from polisyos.ir.analytics.literature import ClaimAdjudicationInputItem
from tests.unit.data_forge.domains.academic.batch import (
    test_admitted_claim_adjudication_consumers as fixtures,
)


def _alternative(schema, current, definitions):
    if "$ref" in schema:
        return _alternative(definitions[schema["$ref"].rsplit("/", 1)[-1]], current, definitions)
    if "anyOf" in schema:
        for option in schema["anyOf"]:
            if option.get("type") != "null":
                value = _alternative(option, current, definitions)
                if value != current:
                    return value
    if "enum" in schema:
        return next(value for value in schema["enum"] if value != current)
    kind = schema.get("type")
    if kind == "string":
        return str(current or "review") + " changed"
    if kind == "boolean":
        return not current
    if kind in {"number", "integer"}:
        return 0 if current != 0 else 1
    if kind == "array":
        return [] if current else [_alternative(schema["items"], None, definitions)]
    if kind == "object":
        previous = current or {}
        return {
            key: _alternative(value, previous.get(key), definitions)
            for key, value in schema.get("properties", {}).items()
            if key in schema.get("required", [])
        }
    raise AssertionError((schema, current))


def test_every_current_input_field_is_required_and_content_bound(tmp_path):
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")
    _, _, verifier = fixtures._receipt(config, publishable=True)
    rows = load_verified_claim_adjudication_rows(config, verifier=verifier)
    original = fixtures._current_subject()
    assert rows.for_current_subject(original)["publishable_edge"] is True
    schema = ClaimAdjudicationInputItem.model_json_schema()
    tested = []
    for name, field_schema in schema["properties"].items():
        missing = {key: value for key, value in original.items() if key != name}
        try:
            projection = rows.for_current_subject(missing)
        except ValueError:
            projection = None
        assert projection is None, (name, "missing", projection)
        changed = deepcopy(original)
        changed[name] = _alternative(field_schema, original[name], schema.get("$defs", {}))
        # Each changed field is still a legal current input, not a malformed-schema strawman.
        changed = ClaimAdjudicationInputItem.model_validate(changed).model_dump(mode="json")
        assert changed != original, name
        try:
            projection = rows.for_current_subject(changed)
        except ValueError:
            projection = None
        assert projection is None, (name, "changed", projection)
        tested.append(name)
    assert set(tested) == set(ClaimAdjudicationInputItem.model_fields)


@pytest.mark.parametrize("consumer", ["graph", "conflict"])
@pytest.mark.parametrize(
    "changed", ["matching", "openalex_id", "cause_variable", "direction", "scope_conditions"]
)
def test_full_subject_reaches_both_consumers_without_borrowed_grades(tmp_path, consumer, changed):
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")
    _, _, verifier = fixtures._receipt(config, publishable=True)
    rows = load_verified_claim_adjudication_rows(config, verifier=verifier)
    original = fixtures._current_subject()
    current = deepcopy(original)
    if changed != "matching":
        schema = ClaimAdjudicationInputItem.model_json_schema()
        current[changed] = _alternative(
            schema["properties"][changed], current[changed], schema.get("$defs", {})
        )
        current = ClaimAdjudicationInputItem.model_validate(current).model_dump(mode="json")
    try:
        if consumer == "graph":
            record = fixtures._work_record()
            transport = record.causal_claims[0]
            occurrence = {**transport.occurrence, **current}
            occurrence.pop("source_basis")
            occurrence.pop("design_family_hint")
            occurrence["cause"] = current["cause_variable"]
            occurrence["effect"] = current["effect_variable"]
            occurrence["claim_type"] = current["claim_type_hint"]
            vocabulary = transport.vocabulary.model_copy(
                update={
                    "cause": current["cause_variable"],
                    "effect": current["effect_variable"],
                    "direction": current["direction"],
                }
            )
            record = record.model_copy(
                update={
                    "id": current["openalex_id"],
                    "causal_claims": [
                        transport.model_copy(
                            update={"occurrence": occurrence, "vocabulary": vocabulary}
                        )
                    ],
                }
            )
            build_graph(
                records=iter([record]), db_path=config.db_path, admitted_claim_adjudications=rows
            )
            with duckdb.connect(str(config.db_path), read_only=True) as database:
                published = database.execute("select count(*) from ac_causal_claims").fetchone()[0]
        else:
            fixtures._write_jsonl(config.raw_claim_candidates_final_path, [current])
            run_conflict_resolve(config, verifier=verifier)
            published = sum(
                json.loads(line)["publishable_claims"]
                for line in config.claim_sets_path.read_text().splitlines()
            )
    except ValueError:
        assert changed != "matching"
        return
    assert published == (1 if changed == "matching" else 0)
