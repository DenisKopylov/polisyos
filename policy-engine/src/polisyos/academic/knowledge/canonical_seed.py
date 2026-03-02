"""Canonical variable seed dictionary for academic SKG extraction."""

from __future__ import annotations

from typing import Final

_DOMAIN_SUBFIELDS: dict[str, tuple[str, ...]] = {
    # Macroeconomics
    "gdp_growth": ("real", "nominal", "per_capita", "quarterly", "annual"),
    "inflation": ("cpi", "core", "ppi", "expected", "headline"),
    "fiscal_balance": ("overall", "primary", "structural", "cyclically_adjusted", "debt_ratio"),
    "government_spending": ("total", "capital", "social", "health", "education"),
    "tax_revenue": ("total", "income", "corporate", "vat", "property"),
    "public_debt": ("gross", "net", "external", "domestic", "short_term"),
    "trade_balance": ("goods", "services", "current_account", "exports", "imports"),
    "exchange_rate": ("real_effective", "nominal_effective", "usd_pair", "volatility", "misalignment"),
    "gdp_per_capita": ("ppp", "real", "nominal", "growth_rate", "usd_current"),
    "interest_rate": ("policy", "short_term", "long_term", "real", "spread"),
    "credit_growth": ("household", "corporate", "private", "bank", "non_bank"),
    "investment_rate": ("total", "public", "private", "infrastructure", "foreign"),
    "productivity": ("tfp", "labor", "capital", "sectoral", "manufacturing"),
    "consumption": ("private", "public", "durables", "services", "per_capita"),
    "savings_rate": ("household", "corporate", "public", "national", "net"),
    "unemployment_rate": ("total", "youth", "female", "long_term", "urban"),
    "labor_force_participation": ("total", "female", "youth", "prime_age", "elderly"),
    "wage_growth": ("real", "nominal", "median", "minimum_wage", "formal_sector"),
    "poverty_rate": ("national", "extreme", "urban", "rural", "multidimensional"),
    "inequality": ("gini", "top10_share", "bottom40_income", "wealth_gini", "palma_ratio"),
    "house_price": ("real", "nominal", "rent_ratio", "price_income_ratio", "volatility"),
    "industrial_output": ("manufacturing", "mining", "utilities", "construction", "capacity_utilization"),
    "business_cycle": ("recession_prob", "output_gap", "leading_index", "volatility", "duration"),
    "fiscal_multiplier": ("spending", "tax", "transfer", "infrastructure", "consumption"),
    "tax_elasticity": ("income_tax", "vat", "corporate_tax", "property_tax", "excise"),
    "sovereign_risk": ("spread", "rating", "default_prob", "market_stress", "debt_service"),

    # Institutions & governance
    "institutional_quality": ("rule_of_law", "regulatory_quality", "government_effectiveness", "voice_accountability", "control_of_corruption"),
    "state_capacity": ("fiscal", "bureaucratic", "administrative", "coercive", "service_delivery"),
    "corruption_level": ("petty", "grand", "procurement", "judicial", "political"),
    "public_trust": ("government", "parliament", "courts", "police", "civil_service"),
    "policy_stability": ("turnover", "volatility", "credibility", "consistency", "predictability"),
    "regulatory_burden": ("entry", "tax_compliance", "licensing", "trade_procedures", "labor_regulation"),
    "property_rights": ("enforcement", "registration", "dispute_resolution", "security", "informality"),
    "judicial_quality": ("independence", "efficiency", "backlog", "access", "fairness"),
    "democracy_quality": ("electoral_integrity", "pluralism", "participation", "civil_liberties", "accountability"),
    "decentralization": ("fiscal", "administrative", "political", "regional_autonomy", "local_revenue"),

    # Society and human capital
    "social_trust": ("interpersonal", "institutional", "bridging", "bonding", "generalized"),
    "cultural_cluster": ("wvs_wave", "traditional_values", "secular_rational", "survival_values", "self_expression"),
    "social_capital": ("civic_participation", "associations", "volunteering", "community_support", "collective_action"),
    "education_outcomes": ("enrollment", "completion", "learning_adjusted_years", "test_scores", "dropout"),
    "health_outcomes": ("life_expectancy", "infant_mortality", "maternal_mortality", "disease_burden", "healthy_life_expectancy"),
    "human_capital": ("index", "skills", "training", "adult_literacy", "digital_skills"),
    "demographics": ("population_growth", "dependency_ratio", "urbanization", "aging", "fertility"),
    "migration": ("net", "skilled", "refugee", "internal", "remittance_outflow"),
    "gender_equality": ("labor_gap", "wage_gap", "education_gap", "political_representation", "care_burden"),
    "crime_rate": ("violent", "property", "homicide", "organized", "recidivism"),
    "housing_quality": ("overcrowding", "sanitation", "affordability", "informal_housing", "utilities_access"),

    # Environment and energy
    "energy_mix": ("renewables_share", "fossil_share", "coal_share", "gas_share", "electricity_intensity"),
    "energy_price": ("electricity", "fuel", "gas", "subsidy_adjusted", "volatility"),
    "emissions": ("co2_total", "co2_per_capita", "methane", "energy_related", "industry_related"),
    "air_quality": ("pm25", "pm10", "ozone", "exposure", "mortality_risk"),
    "climate_risk": ("physical", "transition", "adaptation_capacity", "vulnerability", "resilience"),
    "natural_resources": ("rents", "dependence", "diversification", "extraction_intensity", "depletion"),
    "informal_economy_share": ("employment_based", "output_based", "shadow_gdp_pct", "sectoral", "urban_rural"),
    "water_stress": ("withdrawal_ratio", "scarcity", "quality", "infrastructure", "access"),
    "agricultural_productivity": ("yield", "input_efficiency", "irrigation", "technology_adoption", "climate_sensitivity"),
    "transport_infrastructure": ("road_quality", "rail_density", "port_efficiency", "logistics_performance", "maintenance"),
    "digital_infrastructure": ("broadband_penetration", "mobile_coverage", "speed", "affordability", "usage"),
}


def _humanize(token: str) -> str:
    return token.replace("_", " ")


def _build_seed() -> dict[str, dict[str, list[str]]]:
    seed: dict[str, dict[str, list[str]]] = {}
    for domain, children in _DOMAIN_SUBFIELDS.items():
        base_name = _humanize(domain)
        root_synonyms = [base_name, f"{base_name} indicator", f"{base_name} level"]
        if domain == "gdp_growth":
            root_synonyms.extend(["economic growth", "output growth"])
        entry: dict[str, list[str]] = {"_root": root_synonyms}
        for child in children:
            child_name = _humanize(child)
            entry[child] = [
                f"{base_name} {child_name}",
                f"{child_name} of {base_name}",
                f"{child_name} {base_name}",
            ]
        seed[domain] = entry
    return seed


CANONICAL_VARIABLES: Final[dict[str, dict[str, list[str]]]] = _build_seed()


def canonical_variable_count() -> int:
    total = 0
    for children in CANONICAL_VARIABLES.values():
        total += len(children)
    return total


if canonical_variable_count() < 200:
    raise RuntimeError("canonical seed must define at least 200 canonical variables")


__all__ = ["CANONICAL_VARIABLES", "canonical_variable_count"]
