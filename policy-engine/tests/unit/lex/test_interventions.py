from __future__ import annotations

from decimal import Decimal

import pytest

import polisyos.lex.intervention_artifacts as intervention_artifacts_module
import polisyos.lex.interventions as interventions_module
from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.governance.selector_expr import SelectorPredicate
from polisyos.ir.model_layer.types import SelectorOperator
from polisyos.ir.observation.bundles import StrategicResponseSpec
from polisyos.ir.observation.contracts import (
    IdentificationMode,
    StrategicResponseChannel,
)
from polisyos.lex import (
    InterventionKnobSpec,
    LexInterventionCompiler,
    LexProvisionDirective,
    StrategicResponseRegistryEntry,
    StrategicResponseSpecRegistry,
    TemporalInterventionSequencer,
)


def _selector() -> SelectorPredicate:
    return SelectorPredicate(
        field="region_code",
        operator=SelectorOperator.EQUALS,
        value="UA-30",
    )


def test_compiled_intervention_old_lex_module_paths_are_not_hidden_shims() -> None:
    assert not hasattr(interventions_module, "CompiledLexIntervention")
    assert not hasattr(intervention_artifacts_module, "CompiledLexIntervention")


def test_lex_intervention_compiler_maps_provision_ref_to_knob_and_parameter() -> None:
    compiler = LexInterventionCompiler()

    compiled = compiler.compile(
        LexProvisionDirective(
            provision_ref="ua.procurement.thresholds.art12",
            intervention_id="proc_threshold_change",
            intervention_kind="procurement_threshold_change",
            target=_selector(),
            schedule=ScheduleSpec(start_step=1, duration_steps=2),
            params={"threshold": Decimal("500000")},
            knobs=[
                InterventionKnobSpec(
                    param_id="proc_threshold_knob",
                    param_path="params.threshold",
                    default_value=Decimal("500000"),
                    min_value=Decimal("100000"),
                    max_value=Decimal("1000000"),
                )
            ],
            identification_mode=IdentificationMode.INTERFERENCE_AWARE,
            strategic_response_expected=True,
            transmission_channels=[
                StrategicResponseChannel.PROCUREMENT_CHANNEL,
                StrategicResponseChannel.COMPLIANCE_CHANNEL,
            ],
        )
    )

    assert compiled.intervention.lex_provision_ref == "ua.procurement.thresholds.art12"
    assert compiled.intervention.identification_mode is IdentificationMode.INTERFERENCE_AWARE
    assert compiled.intervention.transmission_channels == [
        StrategicResponseChannel.PROCUREMENT_CHANNEL,
        StrategicResponseChannel.COMPLIANCE_CHANNEL,
    ]
    assert compiled.parameters[0].param_id == "proc_threshold_knob"
    assert compiled.parameters[0].param_path == "params.threshold"
    assert compiled.metadata["provision_ref"] == "ua.procurement.thresholds.art12"
    assert compiled.metadata["knob_ids"] == ["proc_threshold_knob"]


def test_lex_intervention_compiler_rejects_unknown_param_path() -> None:
    compiler = LexInterventionCompiler()

    with pytest.raises(
        ValueError,
        match="references unknown intervention param",
    ):
        compiler.compile(
            LexProvisionDirective(
                provision_ref="ua.procurement.thresholds.art12",
                intervention_id="proc_threshold_change",
                intervention_kind="procurement_threshold_change",
                target=_selector(),
                schedule=ScheduleSpec(start_step=1, duration_steps=2),
                params={"threshold": Decimal("500000")},
                knobs=[
                    InterventionKnobSpec(
                        param_id="proc_threshold_knob",
                        param_path="params.missing_threshold",
                        default_value=Decimal("500000"),
                    )
                ],
            )
        )


def test_lex_intervention_compiler_rejects_inverted_bounds() -> None:
    compiler = LexInterventionCompiler()

    with pytest.raises(ValueError, match="inverted bounds"):
        compiler.compile(
            LexProvisionDirective(
                provision_ref="ua.procurement.thresholds.art12",
                intervention_id="proc_threshold_change",
                intervention_kind="procurement_threshold_change",
                target=_selector(),
                schedule=ScheduleSpec(start_step=1, duration_steps=2),
                params={"threshold": Decimal("500000")},
                knobs=[
                    InterventionKnobSpec(
                        param_id="proc_threshold_knob",
                        param_path="params.threshold",
                        default_value=Decimal("500000"),
                        min_value=Decimal("1000000"),
                        max_value=Decimal("100000"),
                    )
                ],
            )
        )


def test_lex_provision_directive_requires_channels_when_strategic_response_expected() -> None:
    with pytest.raises(ValueError, match="transmission_channels are required"):
        LexProvisionDirective(
            provision_ref="ua.procurement.thresholds.art12",
            intervention_id="proc_threshold_change",
            intervention_kind="procurement_threshold_change",
            target=_selector(),
            schedule=ScheduleSpec(start_step=1, duration_steps=2),
            strategic_response_expected=True,
        )


def test_temporal_intervention_sequencer_rejects_unknown_override_param() -> None:
    compiler = LexInterventionCompiler()
    compiled = compiler.compile(
        LexProvisionDirective(
            provision_ref="ua.procurement.thresholds.art12",
            intervention_id="proc_threshold_change",
            intervention_kind="procurement_threshold_change",
            target=_selector(),
            schedule=ScheduleSpec(start_step=1, duration_steps=2),
            params={"threshold": Decimal("500000")},
            knobs=[
                InterventionKnobSpec(
                    param_id="proc_threshold_knob",
                    param_path="params.threshold",
                    default_value=Decimal("500000"),
                )
            ],
        )
    )
    sequencer = TemporalInterventionSequencer()

    with pytest.raises(ValueError, match="unknown parameter_overrides"):
        sequencer.compile_sequence(
            sequence_id="ua_proc_sequence",
            dynamic_intervention_id="dynamic_proc_threshold",
            compiled_interventions=[compiled],
            steps=[
                {
                    "effective_date": "2022-01",
                    "intervention_id": "proc_threshold_change",
                    "parameter_overrides": {"unknown_param": Decimal("1")},
                }
            ],
        )


def test_strategic_response_spec_registry_returns_channels_and_hook_config() -> None:
    registry = StrategicResponseSpecRegistry(
        [
            StrategicResponseRegistryEntry(
                spec=StrategicResponseSpec(
                    intervention_kind="procurement_threshold_change",
                    channels=[StrategicResponseChannel.PROCUREMENT_CHANNEL],
                ),
                expected_response_type="equilibrium_shift",
                hook_config={"solver": "stackelberg_exact"},
            )
        ]
    )

    entry = registry.require("procurement_threshold_change")

    assert registry.channels_for("procurement_threshold_change") == (
        StrategicResponseChannel.PROCUREMENT_CHANNEL,
    )
    assert entry.expected_response_type == "equilibrium_shift"
    assert entry.hook_config == {"solver": "stackelberg_exact"}
    assert registry.hook_fqn_for("procurement_threshold_change") == entry.spec.hook_fqn
    assert (
        registry.expected_response_type_for("procurement_threshold_change") == "equilibrium_shift"
    )
    assert registry.strategic_required_for("procurement_threshold_change") is True
    bundle = registry.bundle()
    assert bundle.expectations[0].intervention_kind == "procurement_threshold_change"
    round_trip = StrategicResponseSpecRegistry.from_bundle(bundle)
    assert round_trip.channels_for("procurement_threshold_change") == (
        StrategicResponseChannel.PROCUREMENT_CHANNEL,
    )


def test_strategic_response_spec_registry_rejects_duplicate_intervention_kind() -> None:
    entry = StrategicResponseRegistryEntry(
        spec=StrategicResponseSpec(
            intervention_kind="procurement_threshold_change",
            channels=[StrategicResponseChannel.PROCUREMENT_CHANNEL],
        )
    )

    with pytest.raises(ValueError, match="duplicate strategic response spec"):
        StrategicResponseSpecRegistry([entry, entry])
