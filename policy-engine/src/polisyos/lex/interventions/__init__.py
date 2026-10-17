"""Lazy Lex intervention facade over compiler, sequencing, registry, and artifact owners."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

__all__ = [
    "HierarchicalPolicySearchPlan",
    "InterventionKnobDictionaryEntry",
    "InterventionKnobSpec",
    "LexInterventionCompiler",
    "LexInterventionMapEntry",
    "LexPolicyBundleInput",
    "LexProvisionDirective",
    "LexProvisionMappingRegistry",
    "ProvisionProgramCrosswalkEntry",
    "StrategicResponseRegistryEntry",
    "StrategicResponseSpecRegistry",
    "TemporalInterventionSequencer",
    "TemporalInterventionStepInput",
    "load_intervention_knob_dictionary_entries",
    "load_lex_intervention_map_entries",
    "load_provision_program_crosswalk_entries",
]

_EXPORTS: dict[str, tuple[str, str]] = {
    "HierarchicalPolicySearchPlan": ("strategic_response", "HierarchicalPolicySearchPlan"),
    "StrategicResponseRegistryEntry": ("strategic_response", "StrategicResponseRegistryEntry"),
    "StrategicResponseSpecRegistry": ("strategic_response", "StrategicResponseSpecRegistry"),
    "InterventionKnobSpec": ("compiler", "InterventionKnobSpec"),
    "LexInterventionCompiler": ("compiler", "LexInterventionCompiler"),
    "LexProvisionDirective": ("compiler", "LexProvisionDirective"),
    "TemporalInterventionSequencer": ("sequencing", "TemporalInterventionSequencer"),
    "TemporalInterventionStepInput": ("sequencing", "TemporalInterventionStepInput"),
    "InterventionKnobDictionaryEntry": ("artifacts", "InterventionKnobDictionaryEntry"),
    "LexInterventionMapEntry": ("artifacts", "LexInterventionMapEntry"),
    "LexPolicyBundleInput": ("artifacts", "LexPolicyBundleInput"),
    "LexProvisionMappingRegistry": ("artifacts", "LexProvisionMappingRegistry"),
    "ProvisionProgramCrosswalkEntry": ("artifacts", "ProvisionProgramCrosswalkEntry"),
    "load_intervention_knob_dictionary_entries": (
        "artifacts",
        "load_intervention_knob_dictionary_entries",
    ),
    "load_lex_intervention_map_entries": ("artifacts", "load_lex_intervention_map_entries"),
    "load_provision_program_crosswalk_entries": (
        "artifacts",
        "load_provision_program_crosswalk_entries",
    ),
}

if TYPE_CHECKING:
    from .artifacts import (
        InterventionKnobDictionaryEntry as InterventionKnobDictionaryEntry,
    )
    from .artifacts import (
        LexInterventionMapEntry as LexInterventionMapEntry,
    )
    from .artifacts import (
        LexPolicyBundleInput as LexPolicyBundleInput,
    )
    from .artifacts import (
        LexProvisionMappingRegistry as LexProvisionMappingRegistry,
    )
    from .artifacts import (
        ProvisionProgramCrosswalkEntry as ProvisionProgramCrosswalkEntry,
    )
    from .artifacts import (
        load_intervention_knob_dictionary_entries as load_intervention_knob_dictionary_entries,
    )
    from .artifacts import (
        load_lex_intervention_map_entries as load_lex_intervention_map_entries,
    )
    from .artifacts import (
        load_provision_program_crosswalk_entries as load_provision_program_crosswalk_entries,
    )
    from .compiler import (
        InterventionKnobSpec as InterventionKnobSpec,
    )
    from .compiler import (
        LexInterventionCompiler as LexInterventionCompiler,
    )
    from .compiler import (
        LexProvisionDirective as LexProvisionDirective,
    )
    from .sequencing import (
        TemporalInterventionSequencer as TemporalInterventionSequencer,
    )
    from .sequencing import (
        TemporalInterventionStepInput as TemporalInterventionStepInput,
    )
    from .strategic_response import (
        HierarchicalPolicySearchPlan as HierarchicalPolicySearchPlan,
    )
    from .strategic_response import (
        StrategicResponseRegistryEntry as StrategicResponseRegistryEntry,
    )
    from .strategic_response import (
        StrategicResponseSpecRegistry as StrategicResponseSpecRegistry,
    )


def __getattr__(name: str) -> object:
    """Load one Lex intervention symbol on demand."""
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute = target
    module = importlib.import_module(f"{__name__}.{module_name}")
    value = getattr(module, attribute)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Return loaded names and the supported package exports."""
    return sorted(set(globals()) | set(__all__))
