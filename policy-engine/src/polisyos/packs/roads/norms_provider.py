from __future__ import annotations

from dataclasses import dataclass

from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.ir.norm_pack import NormPack, NormRef, NormRule, RuleType


@dataclass(frozen=True)
class RoadsStaticNormPackProvider:
    provider_id: str = "roads.normpack.static_provider"
    jurisdictions: tuple[str, ...] = ("ua",)
    domains: tuple[str, ...] = ("roads",)

    def get_static_norm_pack(
        self,
        cas,
        *,
        jurisdiction: str,
        domain: str | None,
        as_of: str,
    ) -> NormPack:
        jurisdiction_norm = jurisdiction.strip().casefold()
        domain_norm = domain.strip().casefold() if isinstance(domain, str) and domain else "roads"
        pack_id = f"normpack.roads.static.{jurisdiction_norm}"

        rules = [
            NormRule(
                norm_id="roads.static.speed_limit",
                provision_refs=[
                    NormRef(
                        provision_id="roads.static.speed_limit",
                        source_document="roads.static",
                    )
                ],
                rule_type=RuleType.OBLIGATION,
                description="Maximum allowed speed in urban area",
                backend_metadata={
                    "predicate_id": "roads.speed_limit_kmh",
                    "operator": "<=",
                    "value_text": "50",
                    "value_decimal": "50",
                    "unit_id": "roads.kmh",
                    "extractor_id": "lex.norm_extractor.regex_v1@1.0.0",
                },
            ),
            NormRule(
                norm_id="roads.static.lane_width",
                provision_refs=[
                    NormRef(
                        provision_id="roads.static.lane_width",
                        source_document="roads.static",
                    )
                ],
                rule_type=RuleType.OBLIGATION,
                description="Minimum lane width",
                backend_metadata={
                    "predicate_id": "roads.lane_width_min_m",
                    "operator": ">=",
                    "value_text": "3.5",
                    "value_decimal": "3.5",
                    "unit_id": "m",
                    "extractor_id": "lex.norm_extractor.regex_v1@1.0.0",
                },
            ),
        ]

        return NormPack(
            pack_id=pack_id,
            jurisdiction=jurisdiction_norm,
            effective_date=as_of,
            norms=rules,
            metadata={
                "provider_id": self.provider_id,
                "domain": domain_norm,
                "source": "roads.static_provider",
            },
        )


@dataclass(frozen=True)
class _StaticComponent:
    metadata: ComponentMetadata
    provider: RoadsStaticNormPackProvider

    def create(self) -> RoadsStaticNormPackProvider:
        return self.provider


roads_norms_provider_component = _StaticComponent(
    metadata=ComponentMetadata(
        component_id=ComponentId.parse("roads.normpack.static_provider@1.0.0"),
        kind=ComponentKind.NORM_PACK_PROVIDER,
        abi_targets={"ir_abi": "1.x", "world_abi": "1.x"},
        domains=["roads"],
        jurisdictions=["ua"],
        tags=["pack:roads", "normpack", "static"],
        capabilities=Capability.NORM_PACK_PROVIDER | Capability.CAS_WRITE,
        deps=[],
        display_name="Roads Static NormPack Provider",
        description="Provides static roads norm packs for UA demos.",
    ),
    provider=RoadsStaticNormPackProvider(),
)


__all__ = ["roads_norms_provider_component", "RoadsStaticNormPackProvider"]
