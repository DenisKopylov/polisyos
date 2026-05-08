from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from _helpers.artifacts import put_json_artifact
from polisyos.core.contracts.foundry import LoweredConstraint
from polisyos.fabric.world import (
    append_world_segment_index,
    emit_attr_fact,
    validate_world_facts,
    write_world_fact_segment,
)
from polisyos.foundry.validation.constraints_engine import check_constraints
from polisyos.ir.kernel.merge_rules import MergeRuleRef
from polisyos.ir.kernel.slots import SlotKind, SlotRegistry, SlotScope, SlotSpec, SlotValueType
from polisyos.ir.kernel.units import UnitRef
from polisyos.ir.loading.fact_log import FactProvenance
from polisyos.ir.loading.norm_pack import NormPack, NormRule, RuleType
from polisyos.lex.factlog import load_world_facts

pytestmark = pytest.mark.integration

TESTS_ROOT = Path(__file__).resolve().parents[2]


def test_lex_normpack_factlog_rows_lower_into_foundry_constraint_input(
    tmp_path,
    store,
) -> None:
    golden = json.loads((TESTS_ROOT / "_golden" / "contract" / "golden_records.json").read_text())
    assert golden["world_ids"]["claim_dataset"].startswith("claim.sha256_")

    norm_pack = NormPack(
        pack_id="normpack.speed_limit.ua",
        jurisdiction="UA",
        norms=[
            NormRule(
                norm_id="norm.speed_limit.ua",
                rule_type=RuleType.OBLIGATION,
                description="Urban road policy must keep configured speed at or below 50 km/h.",
                backend_metadata={
                    "slot_id": "roads.max_speed_kmh",
                    "operator": "<=",
                    "expected": "50",
                    "unit_id": "kmh",
                },
            )
        ],
    )
    norm_pack_ref = put_json_artifact(
        store,
        norm_pack.model_dump(mode="json"),
        kind="lex.norm_pack",
        schema_version="1.0",
    )
    rule = norm_pack.norms[0]
    metadata = rule.backend_metadata
    provenance = FactProvenance(
        source_id="lex.normpack",
        license="public",
        raw_hash=str(norm_pack_ref.artifact_id),
        ingestion_run_id=norm_pack.pack_id,
    )
    facts = [
        emit_attr_fact(
            subject_id=norm_pack.pack_id,
            predicate_id="lex.normpack.artifact_ref",
            object_value=str(norm_pack_ref.artifact_id),
            provenance=provenance,
        ),
        emit_attr_fact(
            subject_id=rule.norm_id,
            predicate_id="lex.normpack.pack_id",
            object_value=norm_pack.pack_id,
            provenance=provenance,
        ),
        emit_attr_fact(
            subject_id=rule.norm_id,
            predicate_id="lex.constraint.slot_id",
            object_value=str(metadata["slot_id"]),
            provenance=provenance,
        ),
        emit_attr_fact(
            subject_id=rule.norm_id,
            predicate_id="lex.constraint.operator",
            object_value=str(metadata["operator"]),
            provenance=provenance,
        ),
        emit_attr_fact(
            subject_id=rule.norm_id,
            predicate_id="lex.constraint.expected",
            object_value=str(metadata["expected"]),
            provenance=provenance,
        ),
        emit_attr_fact(
            subject_id=rule.norm_id,
            predicate_id="lex.constraint.unit_id",
            object_value=str(metadata["unit_id"]),
            provenance=provenance,
        ),
    ]
    validate_world_facts(facts)
    fact_log_root = tmp_path / "fact_log"
    manifest = write_world_fact_segment(
        facts,
        fact_log_root=fact_log_root,
        segment_name="lex_normpack_constraints",
    )
    append_world_segment_index(manifest, fact_log_root=fact_log_root)

    loaded = load_world_facts(
        fact_log_root,
        columns=["subject_id", "predicate_id", "object_value", "provenance"],
    )
    rule_rows = loaded[loaded["subject_id"] == rule.norm_id]
    fact_values = dict(zip(rule_rows["predicate_id"], rule_rows["object_value"], strict=True))
    constraint = LoweredConstraint(
        constraint_id=f"constraint.{rule.norm_id}",
        severity="hard",
        slot_id=fact_values["lex.constraint.slot_id"],
        operator=fact_values["lex.constraint.operator"],
        expected=fact_values["lex.constraint.expected"],
        unit_id=fact_values["lex.constraint.unit_id"],
    )
    slots = SlotRegistry(
        slots={
            "roads.max_speed_kmh": SlotSpec(
                slot_id="roads.max_speed_kmh",
                scope=SlotScope.GLOBAL,
                value_type=SlotValueType.DECIMAL,
                unit=UnitRef(unit_id="kmh"),
                kind=SlotKind.PARAMETER,
                merge_rule=MergeRuleRef(rule_id="override"),
                state_path="roads.max_speed_kmh",
            )
        }
    )
    state = SimpleNamespace(roads=SimpleNamespace(max_speed_kmh=45))

    report = check_constraints(constraints=[constraint], slot_registry=slots, state=state)

    assert report.ok is True
    assert report.total_constraints == 1
    assert report.violations[0].violated is False
    assert report.violations[0].expected == "50"
    assert "lex.constraint.expected" in set(loaded["predicate_id"])
