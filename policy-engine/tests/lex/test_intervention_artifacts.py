from __future__ import annotations

from pathlib import Path

import pytest

from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.governance.selector_expr import SelectorPredicate
from polisyos.ir.observation.contracts import StrategicResponseChannel
from polisyos.ir.types import SelectorOperator
from polisyos.lex import LexInterventionCompiler, LexProvisionMappingRegistry
from polisyos.lex.intervention_artifacts import (
    load_intervention_knob_dictionary_entries,
    load_lex_intervention_map_entries,
    load_provision_program_crosswalk_entries,
)

_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "lex" / "c6a"


def _selector() -> SelectorPredicate:
    return SelectorPredicate(
        field="region_code",
        operator=SelectorOperator.EQUALS,
        value="UA-30",
    )


def _registry() -> LexProvisionMappingRegistry:
    return LexProvisionMappingRegistry.from_artifacts(
        intervention_map_path=_FIXTURE_DIR / "lex_intervention_map.json",
        knob_dictionary_path=_FIXTURE_DIR / "intervention_knob_dictionary.json",
        crosswalk_path=_FIXTURE_DIR / "provision_to_program_crosswalk.parquet",
    )


def test_artifact_loaders_read_c6a_fixture_payloads() -> None:
    intervention_map = load_lex_intervention_map_entries(
        _FIXTURE_DIR / "lex_intervention_map.json"
    )
    knob_dictionary = load_intervention_knob_dictionary_entries(
        _FIXTURE_DIR / "intervention_knob_dictionary.json"
    )
    crosswalk = load_provision_program_crosswalk_entries(
        _FIXTURE_DIR / "provision_to_program_crosswalk.parquet"
    )

    assert intervention_map[0].provision_ref == "ua.procurement.thresholds.art12"
    assert intervention_map[0].knob_ids == ["proc_threshold_knob"]
    assert knob_dictionary[0].param_path == "params.threshold"
    assert crosswalk[0].program_id == "ua_public_procurement_program"


def test_registry_resolve_builds_directive_from_fixture_artifacts() -> None:
    registry = _registry()

    directive = registry.resolve(
        "ua.procurement.thresholds.art12",
        intervention_id="proc_threshold_change",
        target=_selector(),
        schedule=ScheduleSpec(start_step=1, duration_steps=2),
    )

    assert directive.intervention_kind == "procurement_threshold_change"
    assert directive.params["threshold"] == 500000
    assert directive.knobs[0].param_id == "proc_threshold_knob"
    assert directive.metadata["program_id"] == "ua_public_procurement_program"
    assert directive.metadata["program_name"] == "UA Public Procurement Program"
    assert set(directive.target_region_ids) == {"UA-30", "UA-32"}
    assert set(directive.target_sector_ids) == {"public_procurement", "compliance_monitoring"}
    assert directive.transmission_channels == [
        StrategicResponseChannel.PROCUREMENT_CHANNEL,
        StrategicResponseChannel.COMPLIANCE_CHANNEL,
    ]


def test_registry_rejects_duplicate_map_and_dictionary_entries() -> None:
    intervention_map = load_lex_intervention_map_entries(
        _FIXTURE_DIR / "lex_intervention_map.json"
    )
    knob_dictionary = load_intervention_knob_dictionary_entries(
        _FIXTURE_DIR / "intervention_knob_dictionary.json"
    )

    with pytest.raises(ValueError, match="duplicate intervention mapping"):
        LexProvisionMappingRegistry(intervention_map_entries=[intervention_map[0], intervention_map[0]])

    with pytest.raises(ValueError, match="duplicate knob dictionary entry"):
        LexProvisionMappingRegistry(knob_dictionary_entries=[knob_dictionary[0], knob_dictionary[0]])


def test_registry_rejects_unknown_knob_override() -> None:
    registry = _registry()

    with pytest.raises(KeyError, match="unknown knob_value_overrides"):
        registry.resolve(
            "ua.procurement.thresholds.art12",
            intervention_id="proc_threshold_change",
            target=_selector(),
            schedule=ScheduleSpec(start_step=1, duration_steps=2),
            knob_value_overrides={"unknown_knob": 123},
        )


def test_compile_from_mapping_produces_valid_intervention_bundle() -> None:
    compiler = LexInterventionCompiler()
    registry = _registry()

    compiled = compiler.compile_from_mapping(
        registry,
        "ua.procurement.thresholds.art12",
        intervention_id="proc_threshold_change",
        target=_selector(),
        schedule=ScheduleSpec(start_step=1, duration_steps=2),
    )

    assert compiled.intervention.kind == "procurement_threshold_change"
    assert compiled.intervention.params["threshold"] == 500000
    assert compiled.parameters[0].param_id == "proc_threshold_knob"
    assert compiled.metadata["program_id"] == "ua_public_procurement_program"
    assert compiled.metadata["knob_ids"] == ["proc_threshold_knob"]


def test_compile_from_mapping_rejects_strategic_conflict() -> None:
    compiler = LexInterventionCompiler()
    registry = _registry()

    with pytest.raises(ValueError, match="conflicts with registry mapping"):
        compiler.compile_from_mapping(
            registry,
            "ua.procurement.thresholds.art12",
            intervention_id="proc_threshold_change",
            target=_selector(),
            schedule=ScheduleSpec(start_step=1, duration_steps=2),
            strategic_response_expected=False,
        )
