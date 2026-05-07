"""Local dev-scan declaration for the example Lex NormPack provider."""

from .provider import minimum_wage_normpack_component

__polisyos_components__ = [minimum_wage_normpack_component]

__all__ = ["__polisyos_components__"]
