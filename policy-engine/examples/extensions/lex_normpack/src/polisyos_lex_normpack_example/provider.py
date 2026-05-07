"""Example provider exposed through `polisyos.lex_normpacks`."""

from __future__ import annotations

from dataclasses import dataclass

from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.ir.norm_pack import NormPack, NormRule, RuleType


class MinimumWageNormPackProvider:
    """Static NormPack provider for a tiny example jurisdiction."""

    provider_id = "example.minimum_wage"

    def get_static_norm_pack(
        self,
        cas: object,
        *,
        jurisdiction: str,
        domain: str | None,
        as_of: str,
    ) -> NormPack:
        del cas
        return NormPack(
            pack_id="normpack.example.minimum_wage",
            jurisdiction=jurisdiction,
            effective_date=as_of,
            norms=[
                NormRule(
                    norm_id="norm.example.minimum_wage.floor",
                    rule_type=RuleType.OBLIGATION,
                    description="Covered wages must meet the example floor.",
                    notes=[f"domain={domain or 'general'}"],
                )
            ],
            metadata={"provider": self.provider_id},
        )


@dataclass(frozen=True)
class LexNormPackExampleComponent:
    """Component provider for the example NormPack provider."""

    metadata: ComponentMetadata

    def create(self) -> MinimumWageNormPackProvider:
        return MinimumWageNormPackProvider()


minimum_wage_normpack_component = LexNormPackExampleComponent(
    metadata=ComponentMetadata(
        component_id=ComponentId.parse("example.lex_normpack.minimum_wage@1.0.0"),
        kind=ComponentKind.NORM_PACK_PROVIDER,
        abi_targets={"ir_abi": "1.0", "world_abi": "1.0"},
        domains=["labor"],
        jurisdictions=["EX"],
        tags=["external-example", "lex"],
        capabilities=Capability.NORM_PACK_PROVIDER,
        deps=[],
        display_name="Example Minimum Wage NormPack",
        description="Offline Lex NormPack provider example for extension authors.",
        provides=["normpack.example.minimum_wage"],
    )
)

__all__ = [
    "LexNormPackExampleComponent",
    "MinimumWageNormPackProvider",
    "minimum_wage_normpack_component",
]
