from __future__ import annotations

from polisyos.packs.roads.foundry_methods import roads_method_component
from polisyos.packs.roads.ir_fragments import roads_ir_fragment_component
from polisyos.packs.roads.lex_evaluators import lex_simple_evaluator_component
from polisyos.packs.roads.norms_provider import roads_norms_provider_component
from polisyos.packs.roads.scholar_extractors import (
    lex_norm_regex_extractor_component,
    roads_extractor_component,
)

__polisyos_components__ = [
    roads_ir_fragment_component,
    roads_method_component,
    roads_extractor_component,
    lex_norm_regex_extractor_component,
    lex_simple_evaluator_component,
    roads_norms_provider_component,
]

__all__ = ["__polisyos_components__"]
