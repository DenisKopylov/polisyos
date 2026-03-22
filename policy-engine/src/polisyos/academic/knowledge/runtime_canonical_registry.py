"""Demand-first canonical registry for PolicyOS academic runtime needs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class RuntimeCanonicalEntry:
    canonical_name: str
    aliases: tuple[str, ...]
    need_types: tuple[str, ...] = ("parameter", "causal_edge", "scholar_query", "context")
    workflow_impacts: tuple[str, ...] = (
        "resolve_parameters",
        "literature_prior",
        "cross_graph",
        "scholar",
    )


RUNTIME_CANONICAL_REGISTRY_VERSION: Final[str] = "2026-03-21-runtime-demand-v2"

RUNTIME_CANONICAL_REGISTRY: Final[dict[str, RuntimeCanonicalEntry]] = {
    "tax_revenue": RuntimeCanonicalEntry(
        canonical_name="tax_revenue",
        aliases=("tax revenue", "fiscal revenue", "government tax revenue", "taxation level"),
    ),
    "public_investment": RuntimeCanonicalEntry(
        canonical_name="public_investment",
        aliases=("public investment", "government capital spending", "public capital investment"),
    ),
    "finance.commitment_savings_access": RuntimeCanonicalEntry(
        canonical_name="finance.commitment_savings_access",
        aliases=(
            "access_to_commitment_savings",
            "access_to_commitment_savings_product",
            "commitment savings access",
            "commitment savings product",
        ),
    ),
    "governance.female_decision_making_power": RuntimeCanonicalEntry(
        canonical_name="governance.female_decision_making_power",
        aliases=(
            "female_decision_making_power",
            "female decision making power",
            "women's decision making power",
            "womens decision making power",
        ),
    ),
    "education.early_childhood_education": RuntimeCanonicalEntry(
        canonical_name="education.early_childhood_education",
        aliases=("early_childhood_education", "early childhood education", "preschool attendance"),
    ),
    "social.preferences": RuntimeCanonicalEntry(
        canonical_name="social.preferences",
        aliases=("social preferences", "prosocial preferences"),
    ),
    "health.handwashing_campaign": RuntimeCanonicalEntry(
        canonical_name="health.handwashing_campaign",
        aliases=("handwashing campaign", "hygiene promotion campaign", "hand washing campaign"),
    ),
    "health.diarrhea_incidence": RuntimeCanonicalEntry(
        canonical_name="health.diarrhea_incidence",
        aliases=("diarrhea incidence", "diarrhoea incidence", "diarrheal incidence"),
    ),
    "agriculture.organic_mineral_fertilizer_system": RuntimeCanonicalEntry(
        canonical_name="agriculture.organic_mineral_fertilizer_system",
        aliases=("organic_mineral_fertilizer_system", "organic mineral fertilizer system", "integrated fertilizer system"),
    ),
    "agriculture.winter_wheat_yield": RuntimeCanonicalEntry(
        canonical_name="agriculture.winter_wheat_yield",
        aliases=("winter_wheat_yield", "winter wheat yield", "wheat yield"),
    ),
    "climate.drought_resilient_irrigation": RuntimeCanonicalEntry(
        canonical_name="climate.drought_resilient_irrigation",
        aliases=("drought_resilient_irrigation", "drought resilient irrigation"),
    ),
    "agriculture.crop_yield": RuntimeCanonicalEntry(
        canonical_name="agriculture.crop_yield",
        aliases=("crop_yield", "crop yield", "agricultural yield"),
    ),
    "economic.gdp_growth": RuntimeCanonicalEntry(
        canonical_name="economic.gdp_growth",
        aliases=("gdp_growth", "economic growth", "output growth", "gross domestic product growth"),
    ),
    "labor.unemployment_rate": RuntimeCanonicalEntry(
        canonical_name="labor.unemployment_rate",
        aliases=("unemployment_rate", "unemployment", "joblessness"),
    ),
    "education.teacher_coaching": RuntimeCanonicalEntry(
        canonical_name="education.teacher_coaching",
        aliases=(
            "teacher coaching",
            "teacher_coaching_program",
            "teacher coaching program",
            "coached teacher",
            "fully coached teacher",
            "having a fully coached teacher for three years",
        ),
    ),
    "education.learning_outcomes": RuntimeCanonicalEntry(
        canonical_name="education.learning_outcomes",
        aliases=(
            "student_learning",
            "student learning",
            "learning outcomes",
            "student achievement",
            "test scores",
        ),
    ),
    "education.teacher_skills": RuntimeCanonicalEntry(
        canonical_name="education.teacher_skills",
        aliases=(
            "teachers_pedagogical_skills",
            "teacher skills",
            "teacher pedagogical skills",
            "pedagogical skills",
        ),
    ),
    "energy.electricity_reliability": RuntimeCanonicalEntry(
        canonical_name="energy.electricity_reliability",
        aliases=("electricity reliability", "power reliability", "grid reliability"),
    ),
    "economic.firm_productivity": RuntimeCanonicalEntry(
        canonical_name="economic.firm_productivity",
        aliases=("firm productivity", "enterprise productivity", "business productivity"),
    ),
    "urban.mass_transit_access": RuntimeCanonicalEntry(
        canonical_name="urban.mass_transit_access",
        aliases=("mass transit access", "transit access", "public transport access"),
    ),
    "labor.formal_employment": RuntimeCanonicalEntry(
        canonical_name="labor.formal_employment",
        aliases=("formal employment", "formal sector employment"),
    ),
    "social.cash_transfer_program": RuntimeCanonicalEntry(
        canonical_name="social.cash_transfer_program",
        aliases=("cash transfer program", "cash transfer", "transfer program"),
    ),
    "economic.household_consumption": RuntimeCanonicalEntry(
        canonical_name="economic.household_consumption",
        aliases=("household consumption", "household spending", "consumption smoothing"),
    ),
    "governance.state_capacity_reform": RuntimeCanonicalEntry(
        canonical_name="governance.state_capacity_reform",
        aliases=("state capacity reform", "administrative capacity reform"),
    ),
    "governance.tax_compliance": RuntimeCanonicalEntry(
        canonical_name="governance.tax_compliance",
        aliases=("tax compliance", "tax payment compliance"),
    ),
    "governance.rule_of_law": RuntimeCanonicalEntry(
        canonical_name="governance.rule_of_law",
        aliases=("rule_of_law", "rule of law"),
    ),
    "economic.firm_investment": RuntimeCanonicalEntry(
        canonical_name="economic.firm_investment",
        aliases=("firm investment", "business investment"),
    ),
    "urban.housing_security": RuntimeCanonicalEntry(
        canonical_name="urban.housing_security",
        aliases=("housing security", "secure housing", "tenure security"),
    ),
    "social.subjective_wellbeing": RuntimeCanonicalEntry(
        canonical_name="social.subjective_wellbeing",
        aliases=("subjective wellbeing", "subjective well-being", "wellbeing"),
    ),
    "labor.minimum_wage": RuntimeCanonicalEntry(
        canonical_name="labor.minimum_wage",
        aliases=("minimum wage",),
    ),
    "labor.employment_rate": RuntimeCanonicalEntry(
        canonical_name="labor.employment_rate",
        aliases=("employment rate", "employment"),
    ),
    "governance.procurement_digitization": RuntimeCanonicalEntry(
        canonical_name="governance.procurement_digitization",
        aliases=("procurement digitization", "e-procurement", "public procurement digitization"),
    ),
    "governance.procurement_compliance": RuntimeCanonicalEntry(
        canonical_name="governance.procurement_compliance",
        aliases=("procurement compliance", "public procurement compliance"),
    ),
    "digital.infrastructure_quality": RuntimeCanonicalEntry(
        canonical_name="digital.infrastructure_quality",
        aliases=("digital infrastructure quality", "digital infrastructure", "internet quality", "broadband quality"),
    ),
    "governance.anticorruption_enforcement": RuntimeCanonicalEntry(
        canonical_name="governance.anticorruption_enforcement",
        aliases=("anticorruption enforcement", "anti-corruption enforcement"),
    ),
    "governance.procurement_integrity": RuntimeCanonicalEntry(
        canonical_name="governance.procurement_integrity",
        aliases=("procurement integrity", "public procurement integrity"),
    ),
    "finance.bank_branch_closures": RuntimeCanonicalEntry(
        canonical_name="finance.bank_branch_closures",
        aliases=("bank_branch_closings", "bank branch closings", "bank branch closures"),
    ),
    "finance.small_business_lending": RuntimeCanonicalEntry(
        canonical_name="finance.small_business_lending",
        aliases=("local_small_business_lending", "small business lending"),
    ),
    "labor.manufacturing_employment": RuntimeCanonicalEntry(
        canonical_name="labor.manufacturing_employment",
        aliases=("manufacturing_employment", "manufacturing employment"),
    ),
    "trade.tariff_exposure": RuntimeCanonicalEntry(
        canonical_name="trade.tariff_exposure",
        aliases=("tariff_exposure", "tariff exposure"),
    ),
    # ── Macroeconomics ───────────────────────────────────────────────
    "economic.inflation": RuntimeCanonicalEntry(
        canonical_name="economic.inflation",
        aliases=("inflation", "inflation rate", "consumer price inflation", "cpi inflation"),
    ),
    "economic.fiscal_balance": RuntimeCanonicalEntry(
        canonical_name="economic.fiscal_balance",
        aliases=("fiscal balance", "budget balance", "fiscal deficit", "budget deficit", "fiscal surplus"),
    ),
    "economic.government_spending": RuntimeCanonicalEntry(
        canonical_name="economic.government_spending",
        aliases=("government spending", "government expenditure", "public expenditure", "public spending", "fiscal expenditure"),
    ),
    "economic.public_debt": RuntimeCanonicalEntry(
        canonical_name="economic.public_debt",
        aliases=("public debt", "government debt", "sovereign debt", "national debt"),
    ),
    "economic.trade_balance": RuntimeCanonicalEntry(
        canonical_name="economic.trade_balance",
        aliases=("trade balance", "net exports", "trade surplus", "trade deficit", "current account"),
    ),
    "economic.exchange_rate": RuntimeCanonicalEntry(
        canonical_name="economic.exchange_rate",
        aliases=("exchange rate", "real exchange rate", "nominal exchange rate", "currency value"),
    ),
    "economic.interest_rate": RuntimeCanonicalEntry(
        canonical_name="economic.interest_rate",
        aliases=("interest rate", "policy rate", "central bank rate", "lending rate"),
    ),
    "economic.credit_growth": RuntimeCanonicalEntry(
        canonical_name="economic.credit_growth",
        aliases=("credit growth", "domestic credit growth", "private credit growth", "credit expansion"),
    ),
    "economic.investment_rate": RuntimeCanonicalEntry(
        canonical_name="economic.investment_rate",
        aliases=("investment rate", "gross capital formation", "investment to gdp", "capital investment rate"),
    ),
    "economic.productivity": RuntimeCanonicalEntry(
        canonical_name="economic.productivity",
        aliases=("productivity", "total factor productivity", "tfp", "labor productivity", "labour productivity"),
    ),
    "economic.savings_rate": RuntimeCanonicalEntry(
        canonical_name="economic.savings_rate",
        aliases=("savings rate", "gross savings rate", "domestic savings", "national savings"),
    ),
    "economic.poverty_rate": RuntimeCanonicalEntry(
        canonical_name="economic.poverty_rate",
        aliases=("poverty rate", "poverty headcount", "poverty incidence", "poverty level"),
    ),
    "economic.inequality": RuntimeCanonicalEntry(
        canonical_name="economic.inequality",
        aliases=("inequality", "income inequality", "economic inequality", "wealth inequality"),
    ),
    "economic.gini_coefficient": RuntimeCanonicalEntry(
        canonical_name="economic.gini_coefficient",
        aliases=("gini coefficient", "gini index", "gini"),
    ),
    "economic.gdp_per_capita": RuntimeCanonicalEntry(
        canonical_name="economic.gdp_per_capita",
        aliases=("gdp per capita", "income per capita", "per capita income", "per capita gdp"),
    ),
    "economic.industrial_output": RuntimeCanonicalEntry(
        canonical_name="economic.industrial_output",
        aliases=("industrial output", "manufacturing output", "industrial production", "industrial value added"),
    ),
    "economic.fdi_inflows": RuntimeCanonicalEntry(
        canonical_name="economic.fdi_inflows",
        aliases=("fdi inflows", "foreign direct investment", "fdi", "foreign investment inflows"),
    ),
    "economic.remittances": RuntimeCanonicalEntry(
        canonical_name="economic.remittances",
        aliases=("remittances", "worker remittances", "diaspora remittances", "personal remittances"),
    ),
    "economic.informal_economy_share": RuntimeCanonicalEntry(
        canonical_name="economic.informal_economy_share",
        aliases=("informal economy share", "informal sector share", "shadow economy", "informality rate"),
    ),
    "economic.fiscal_multiplier": RuntimeCanonicalEntry(
        canonical_name="economic.fiscal_multiplier",
        aliases=("fiscal multiplier", "spending multiplier", "government spending multiplier"),
    ),
    "economic.debt_to_gdp": RuntimeCanonicalEntry(
        canonical_name="economic.debt_to_gdp",
        aliases=("debt to gdp", "debt to gdp ratio", "debt-to-gdp", "public debt ratio"),
    ),
    "economic.current_account_balance": RuntimeCanonicalEntry(
        canonical_name="economic.current_account_balance",
        aliases=("current account balance", "current account", "external balance"),
    ),
    "economic.real_wage": RuntimeCanonicalEntry(
        canonical_name="economic.real_wage",
        aliases=("real wage", "real wages", "real wage growth", "wage level"),
    ),
    "economic.consumer_price_index": RuntimeCanonicalEntry(
        canonical_name="economic.consumer_price_index",
        aliases=("consumer price index", "cpi", "price level", "price index"),
    ),
    "economic.purchasing_power": RuntimeCanonicalEntry(
        canonical_name="economic.purchasing_power",
        aliases=("purchasing power", "purchasing power parity", "ppp", "real purchasing power"),
    ),
    # ── Governance ───────────────────────────────────────────────────
    "governance.institutional_quality": RuntimeCanonicalEntry(
        canonical_name="governance.institutional_quality",
        aliases=("institutional quality", "institutional strength", "quality of institutions"),
    ),
    "governance.corruption_level": RuntimeCanonicalEntry(
        canonical_name="governance.corruption_level",
        aliases=("corruption level", "corruption", "corruption perception", "corruption index", "cpi corruption"),
    ),
    "governance.public_trust": RuntimeCanonicalEntry(
        canonical_name="governance.public_trust",
        aliases=("public trust", "trust in government", "institutional trust", "political trust"),
    ),
    "governance.judicial_independence": RuntimeCanonicalEntry(
        canonical_name="governance.judicial_independence",
        aliases=("judicial independence", "judiciary independence", "court independence"),
    ),
    "governance.decentralization": RuntimeCanonicalEntry(
        canonical_name="governance.decentralization",
        aliases=("decentralization", "fiscal decentralization", "political decentralization", "decentralisation"),
    ),
    "governance.regulatory_quality": RuntimeCanonicalEntry(
        canonical_name="governance.regulatory_quality",
        aliases=("regulatory quality", "regulatory environment", "regulation quality", "business regulation"),
    ),
    "governance.government_effectiveness": RuntimeCanonicalEntry(
        canonical_name="governance.government_effectiveness",
        aliases=("government effectiveness", "public sector effectiveness", "bureaucratic effectiveness"),
    ),
    "governance.political_stability": RuntimeCanonicalEntry(
        canonical_name="governance.political_stability",
        aliases=("political stability", "political instability", "regime stability"),
    ),
    "governance.voice_accountability": RuntimeCanonicalEntry(
        canonical_name="governance.voice_accountability",
        aliases=("voice and accountability", "democratic accountability", "political voice"),
    ),
    "governance.control_of_corruption": RuntimeCanonicalEntry(
        canonical_name="governance.control_of_corruption",
        aliases=("control of corruption", "anticorruption", "anti-corruption"),
    ),
    "governance.e_government": RuntimeCanonicalEntry(
        canonical_name="governance.e_government",
        aliases=("e-government", "e government", "digital government", "electronic government"),
    ),
    "governance.civil_service_quality": RuntimeCanonicalEntry(
        canonical_name="governance.civil_service_quality",
        aliases=("civil service quality", "public administration quality", "bureaucratic quality"),
    ),
    "governance.fiscal_transparency": RuntimeCanonicalEntry(
        canonical_name="governance.fiscal_transparency",
        aliases=("fiscal transparency", "budget transparency", "open budget"),
    ),
    "governance.public_procurement_efficiency": RuntimeCanonicalEntry(
        canonical_name="governance.public_procurement_efficiency",
        aliases=("public procurement efficiency", "procurement efficiency", "government procurement"),
    ),
    "governance.property_rights": RuntimeCanonicalEntry(
        canonical_name="governance.property_rights",
        aliases=("property rights", "property rights protection", "land rights"),
    ),
    "governance.contract_enforcement": RuntimeCanonicalEntry(
        canonical_name="governance.contract_enforcement",
        aliases=("contract enforcement", "enforcing contracts", "legal enforcement"),
    ),
    "governance.legislative_effectiveness": RuntimeCanonicalEntry(
        canonical_name="governance.legislative_effectiveness",
        aliases=("legislative effectiveness", "parliament effectiveness", "legislative quality"),
    ),
    "governance.local_governance_quality": RuntimeCanonicalEntry(
        canonical_name="governance.local_governance_quality",
        aliases=("local governance quality", "subnational governance", "municipal governance"),
    ),
    # ── Health ───────────────────────────────────────────────────────
    "health.infant_mortality": RuntimeCanonicalEntry(
        canonical_name="health.infant_mortality",
        aliases=("infant mortality", "infant mortality rate", "neonatal mortality", "child mortality"),
    ),
    "health.life_expectancy": RuntimeCanonicalEntry(
        canonical_name="health.life_expectancy",
        aliases=("life expectancy", "life expectancy at birth", "longevity"),
    ),
    "health.vaccination_coverage": RuntimeCanonicalEntry(
        canonical_name="health.vaccination_coverage",
        aliases=("vaccination coverage", "immunization coverage", "vaccine coverage", "immunization rate"),
    ),
    "health.maternal_mortality": RuntimeCanonicalEntry(
        canonical_name="health.maternal_mortality",
        aliases=("maternal mortality", "maternal mortality ratio", "maternal death rate"),
    ),
    "health.malaria_incidence": RuntimeCanonicalEntry(
        canonical_name="health.malaria_incidence",
        aliases=("malaria incidence", "malaria prevalence", "malaria cases"),
    ),
    "health.hiv_prevalence": RuntimeCanonicalEntry(
        canonical_name="health.hiv_prevalence",
        aliases=("hiv prevalence", "hiv/aids prevalence", "hiv incidence"),
    ),
    "health.healthcare_spending": RuntimeCanonicalEntry(
        canonical_name="health.healthcare_spending",
        aliases=("healthcare spending", "health expenditure", "health spending", "healthcare expenditure"),
    ),
    "health.hospital_beds": RuntimeCanonicalEntry(
        canonical_name="health.hospital_beds",
        aliases=("hospital beds", "hospital beds per capita", "hospital bed density"),
    ),
    "health.out_of_pocket_spending": RuntimeCanonicalEntry(
        canonical_name="health.out_of_pocket_spending",
        aliases=("out of pocket spending", "out-of-pocket health expenditure", "oop spending"),
    ),
    "health.child_stunting": RuntimeCanonicalEntry(
        canonical_name="health.child_stunting",
        aliases=("child stunting", "stunting prevalence", "childhood stunting", "malnutrition stunting"),
    ),
    "health.noncommunicable_disease_mortality": RuntimeCanonicalEntry(
        canonical_name="health.noncommunicable_disease_mortality",
        aliases=("ncd mortality", "noncommunicable disease mortality", "chronic disease mortality"),
    ),
    "health.universal_health_coverage": RuntimeCanonicalEntry(
        canonical_name="health.universal_health_coverage",
        aliases=("universal health coverage", "uhc", "health coverage index"),
    ),
    "health.physician_density": RuntimeCanonicalEntry(
        canonical_name="health.physician_density",
        aliases=("physician density", "doctors per capita", "physician per population"),
    ),
    "health.clean_water_access": RuntimeCanonicalEntry(
        canonical_name="health.clean_water_access",
        aliases=("clean water access", "safe water access", "improved water source", "drinking water access"),
    ),
    # ── Education ────────────────────────────────────────────────────
    "education.enrollment_rate": RuntimeCanonicalEntry(
        canonical_name="education.enrollment_rate",
        aliases=("enrollment rate", "enrolment rate", "school enrollment", "net enrollment rate", "gross enrollment"),
    ),
    "education.literacy_rate": RuntimeCanonicalEntry(
        canonical_name="education.literacy_rate",
        aliases=("literacy rate", "adult literacy", "literacy"),
    ),
    "education.school_quality": RuntimeCanonicalEntry(
        canonical_name="education.school_quality",
        aliases=("school quality", "education quality", "school effectiveness"),
    ),
    "education.education_spending": RuntimeCanonicalEntry(
        canonical_name="education.education_spending",
        aliases=("education spending", "education expenditure", "public education spending"),
    ),
    "education.dropout_rate": RuntimeCanonicalEntry(
        canonical_name="education.dropout_rate",
        aliases=("dropout rate", "school dropout", "drop-out rate", "educational attrition"),
    ),
    "education.tertiary_enrollment": RuntimeCanonicalEntry(
        canonical_name="education.tertiary_enrollment",
        aliases=("tertiary enrollment", "university enrollment", "higher education enrollment"),
    ),
    "education.stem_graduates": RuntimeCanonicalEntry(
        canonical_name="education.stem_graduates",
        aliases=("stem graduates", "science graduates", "engineering graduates"),
    ),
    "education.class_size": RuntimeCanonicalEntry(
        canonical_name="education.class_size",
        aliases=("class size", "pupil teacher ratio", "student teacher ratio"),
    ),
    "education.gender_parity_index": RuntimeCanonicalEntry(
        canonical_name="education.gender_parity_index",
        aliases=("gender parity index", "educational gender parity", "gpi education"),
    ),
    "education.years_of_schooling": RuntimeCanonicalEntry(
        canonical_name="education.years_of_schooling",
        aliases=("years of schooling", "mean years of schooling", "expected years of schooling", "educational attainment"),
    ),
    "education.vocational_training": RuntimeCanonicalEntry(
        canonical_name="education.vocational_training",
        aliases=("vocational training", "technical education", "skills training", "tvet"),
    ),
    "education.preschool_enrollment": RuntimeCanonicalEntry(
        canonical_name="education.preschool_enrollment",
        aliases=("preschool enrollment", "pre-primary enrollment", "preprimary enrollment"),
    ),
    "education.digital_literacy": RuntimeCanonicalEntry(
        canonical_name="education.digital_literacy",
        aliases=("digital literacy", "digital skills", "ict literacy", "computer literacy"),
    ),
    # ── Labor ────────────────────────────────────────────────────────
    "labor.informality_rate": RuntimeCanonicalEntry(
        canonical_name="labor.informality_rate",
        aliases=("informality rate", "informal employment rate", "informal labor share"),
    ),
    "labor.wage_growth": RuntimeCanonicalEntry(
        canonical_name="labor.wage_growth",
        aliases=("wage growth", "nominal wage growth", "real wage growth", "earnings growth"),
    ),
    "labor.labor_force_participation": RuntimeCanonicalEntry(
        canonical_name="labor.labor_force_participation",
        aliases=("labor force participation", "labour force participation", "lfpr", "workforce participation"),
    ),
    "labor.youth_unemployment": RuntimeCanonicalEntry(
        canonical_name="labor.youth_unemployment",
        aliases=("youth unemployment", "youth joblessness", "young adult unemployment"),
    ),
    "labor.gender_wage_gap": RuntimeCanonicalEntry(
        canonical_name="labor.gender_wage_gap",
        aliases=("gender wage gap", "gender pay gap", "wage gender gap", "pay equity"),
    ),
    "labor.working_poverty": RuntimeCanonicalEntry(
        canonical_name="labor.working_poverty",
        aliases=("working poverty", "in-work poverty", "working poor"),
    ),
    "labor.labor_productivity": RuntimeCanonicalEntry(
        canonical_name="labor.labor_productivity",
        aliases=("labor productivity", "labour productivity", "worker productivity", "output per worker"),
    ),
    "labor.job_creation": RuntimeCanonicalEntry(
        canonical_name="labor.job_creation",
        aliases=("job creation", "employment creation", "new jobs", "net job creation"),
    ),
    "labor.skills_gap": RuntimeCanonicalEntry(
        canonical_name="labor.skills_gap",
        aliases=("skills gap", "skills mismatch", "labor skills shortage"),
    ),
    "labor.union_density": RuntimeCanonicalEntry(
        canonical_name="labor.union_density",
        aliases=("union density", "trade union density", "unionization rate"),
    ),
    "labor.long_term_unemployment": RuntimeCanonicalEntry(
        canonical_name="labor.long_term_unemployment",
        aliases=("long term unemployment", "long-term unemployment", "structural unemployment"),
    ),
    "labor.underemployment": RuntimeCanonicalEntry(
        canonical_name="labor.underemployment",
        aliases=("underemployment", "underemployment rate", "time-related underemployment"),
    ),
    # ── Agriculture ──────────────────────────────────────────────────
    "agriculture.food_security": RuntimeCanonicalEntry(
        canonical_name="agriculture.food_security",
        aliases=("food security", "food insecurity", "food security index", "hunger"),
    ),
    "agriculture.land_productivity": RuntimeCanonicalEntry(
        canonical_name="agriculture.land_productivity",
        aliases=("land productivity", "agricultural land productivity", "yield per hectare"),
    ),
    "agriculture.irrigation_coverage": RuntimeCanonicalEntry(
        canonical_name="agriculture.irrigation_coverage",
        aliases=("irrigation coverage", "irrigated area", "irrigation access"),
    ),
    "agriculture.fertilizer_use": RuntimeCanonicalEntry(
        canonical_name="agriculture.fertilizer_use",
        aliases=("fertilizer use", "fertilizer consumption", "fertilizer application"),
    ),
    "agriculture.food_price_index": RuntimeCanonicalEntry(
        canonical_name="agriculture.food_price_index",
        aliases=("food price index", "food prices", "food price inflation"),
    ),
    "agriculture.smallholder_income": RuntimeCanonicalEntry(
        canonical_name="agriculture.smallholder_income",
        aliases=("smallholder income", "small farmer income", "smallholder revenue"),
    ),
    "agriculture.post_harvest_losses": RuntimeCanonicalEntry(
        canonical_name="agriculture.post_harvest_losses",
        aliases=("post harvest losses", "post-harvest losses", "food loss"),
    ),
    "agriculture.agricultural_subsidy": RuntimeCanonicalEntry(
        canonical_name="agriculture.agricultural_subsidy",
        aliases=("agricultural subsidy", "farm subsidy", "agricultural support"),
    ),
    # ── Climate & Energy ─────────────────────────────────────────────
    "climate.carbon_emissions": RuntimeCanonicalEntry(
        canonical_name="climate.carbon_emissions",
        aliases=("carbon emissions", "co2 emissions", "greenhouse gas emissions", "ghg emissions", "carbon dioxide emissions"),
    ),
    "climate.renewable_energy_share": RuntimeCanonicalEntry(
        canonical_name="climate.renewable_energy_share",
        aliases=("renewable energy share", "renewables share", "clean energy share"),
    ),
    "climate.deforestation_rate": RuntimeCanonicalEntry(
        canonical_name="climate.deforestation_rate",
        aliases=("deforestation rate", "forest loss", "tree cover loss", "deforestation"),
    ),
    "climate.climate_adaptation_spending": RuntimeCanonicalEntry(
        canonical_name="climate.climate_adaptation_spending",
        aliases=("climate adaptation spending", "adaptation finance", "climate adaptation investment"),
    ),
    "climate.air_quality_index": RuntimeCanonicalEntry(
        canonical_name="climate.air_quality_index",
        aliases=("air quality index", "air quality", "pm2.5 concentration", "air pollution", "particulate matter"),
    ),
    "climate.water_stress": RuntimeCanonicalEntry(
        canonical_name="climate.water_stress",
        aliases=("water stress", "water scarcity", "water availability"),
    ),
    "climate.disaster_resilience": RuntimeCanonicalEntry(
        canonical_name="climate.disaster_resilience",
        aliases=("disaster resilience", "disaster risk reduction", "disaster preparedness"),
    ),
    "climate.green_investment": RuntimeCanonicalEntry(
        canonical_name="climate.green_investment",
        aliases=("green investment", "climate investment", "green finance", "sustainable investment"),
    ),
    "energy.electricity_access": RuntimeCanonicalEntry(
        canonical_name="energy.electricity_access",
        aliases=("electricity access", "electrification rate", "power access", "energy access"),
    ),
    "energy.energy_intensity": RuntimeCanonicalEntry(
        canonical_name="energy.energy_intensity",
        aliases=("energy intensity", "energy consumption per gdp", "energy efficiency"),
    ),
    "energy.fossil_fuel_subsidy": RuntimeCanonicalEntry(
        canonical_name="energy.fossil_fuel_subsidy",
        aliases=("fossil fuel subsidy", "fuel subsidy", "energy subsidy"),
    ),
    "energy.energy_poverty": RuntimeCanonicalEntry(
        canonical_name="energy.energy_poverty",
        aliases=("energy poverty", "fuel poverty", "energy affordability"),
    ),
    "energy.clean_cooking_access": RuntimeCanonicalEntry(
        canonical_name="energy.clean_cooking_access",
        aliases=("clean cooking access", "clean fuel access", "improved cooking fuel"),
    ),
    # ── Urban & Infrastructure ───────────────────────────────────────
    "urban.urbanization_rate": RuntimeCanonicalEntry(
        canonical_name="urban.urbanization_rate",
        aliases=("urbanization rate", "urban population share", "urbanisation rate"),
    ),
    "urban.slum_population": RuntimeCanonicalEntry(
        canonical_name="urban.slum_population",
        aliases=("slum population", "informal settlement population", "slum dwellers"),
    ),
    "urban.affordable_housing": RuntimeCanonicalEntry(
        canonical_name="urban.affordable_housing",
        aliases=("affordable housing", "housing affordability", "social housing"),
    ),
    "urban.public_transport_coverage": RuntimeCanonicalEntry(
        canonical_name="urban.public_transport_coverage",
        aliases=("public transport coverage", "public transit coverage", "transit coverage"),
    ),
    "urban.waste_management": RuntimeCanonicalEntry(
        canonical_name="urban.waste_management",
        aliases=("waste management", "solid waste management", "waste collection"),
    ),
    "urban.green_space": RuntimeCanonicalEntry(
        canonical_name="urban.green_space",
        aliases=("green space", "urban green space", "parks and green areas"),
    ),
    "infrastructure.road_quality": RuntimeCanonicalEntry(
        canonical_name="infrastructure.road_quality",
        aliases=("road quality", "road infrastructure", "paved roads"),
    ),
    "infrastructure.internet_penetration": RuntimeCanonicalEntry(
        canonical_name="infrastructure.internet_penetration",
        aliases=("internet penetration", "internet access", "internet users", "broadband penetration"),
    ),
    "infrastructure.mobile_coverage": RuntimeCanonicalEntry(
        canonical_name="infrastructure.mobile_coverage",
        aliases=("mobile coverage", "mobile network coverage", "cellular coverage"),
    ),
    "infrastructure.logistics_performance": RuntimeCanonicalEntry(
        canonical_name="infrastructure.logistics_performance",
        aliases=("logistics performance", "logistics performance index", "lpi", "trade logistics"),
    ),
    # ── Social & Demographics ────────────────────────────────────────
    "social.poverty_headcount": RuntimeCanonicalEntry(
        canonical_name="social.poverty_headcount",
        aliases=("poverty headcount", "poverty headcount ratio", "extreme poverty rate"),
    ),
    "social.social_mobility": RuntimeCanonicalEntry(
        canonical_name="social.social_mobility",
        aliases=("social mobility", "intergenerational mobility", "economic mobility"),
    ),
    "social.social_protection_coverage": RuntimeCanonicalEntry(
        canonical_name="social.social_protection_coverage",
        aliases=("social protection coverage", "social safety net coverage", "social insurance coverage"),
    ),
    "social.income_inequality": RuntimeCanonicalEntry(
        canonical_name="social.income_inequality",
        aliases=("income inequality", "income distribution", "income disparity"),
    ),
    "social.food_insecurity": RuntimeCanonicalEntry(
        canonical_name="social.food_insecurity",
        aliases=("food insecurity", "food deprivation", "hunger prevalence"),
    ),
    "social.child_labor": RuntimeCanonicalEntry(
        canonical_name="social.child_labor",
        aliases=("child labor", "child labour", "child work"),
    ),
    "social.gender_equality_index": RuntimeCanonicalEntry(
        canonical_name="social.gender_equality_index",
        aliases=("gender equality index", "gender equality", "gender development index"),
    ),
    "social.human_development_index": RuntimeCanonicalEntry(
        canonical_name="social.human_development_index",
        aliases=("human development index", "hdi", "human development"),
    ),
    "social.trust_in_institutions": RuntimeCanonicalEntry(
        canonical_name="social.trust_in_institutions",
        aliases=("trust in institutions", "institutional trust", "political trust"),
    ),
    "social.civic_participation": RuntimeCanonicalEntry(
        canonical_name="social.civic_participation",
        aliases=("civic participation", "civic engagement", "voter turnout", "political participation"),
    ),
    "demographic.fertility_rate": RuntimeCanonicalEntry(
        canonical_name="demographic.fertility_rate",
        aliases=("fertility rate", "total fertility rate", "birth rate", "tfr"),
    ),
    "demographic.dependency_ratio": RuntimeCanonicalEntry(
        canonical_name="demographic.dependency_ratio",
        aliases=("dependency ratio", "age dependency ratio", "old-age dependency ratio"),
    ),
    "demographic.migration_rate": RuntimeCanonicalEntry(
        canonical_name="demographic.migration_rate",
        aliases=("migration rate", "net migration", "immigration rate", "emigration rate"),
    ),
    "demographic.median_age": RuntimeCanonicalEntry(
        canonical_name="demographic.median_age",
        aliases=("median age", "population median age"),
    ),
    "demographic.population_growth": RuntimeCanonicalEntry(
        canonical_name="demographic.population_growth",
        aliases=("population growth", "population growth rate"),
    ),
    # ── Trade ────────────────────────────────────────────────────────
    "trade.trade_openness": RuntimeCanonicalEntry(
        canonical_name="trade.trade_openness",
        aliases=("trade openness", "trade to gdp ratio", "trade integration", "trade share"),
    ),
    "trade.tariff_rate": RuntimeCanonicalEntry(
        canonical_name="trade.tariff_rate",
        aliases=("tariff rate", "import tariff", "average tariff", "customs duty"),
    ),
    "trade.export_diversification": RuntimeCanonicalEntry(
        canonical_name="trade.export_diversification",
        aliases=("export diversification", "export concentration", "export variety"),
    ),
    "trade.terms_of_trade": RuntimeCanonicalEntry(
        canonical_name="trade.terms_of_trade",
        aliases=("terms of trade", "trade terms", "commodity terms of trade"),
    ),
    "trade.non_tariff_barriers": RuntimeCanonicalEntry(
        canonical_name="trade.non_tariff_barriers",
        aliases=("non tariff barriers", "non-tariff barriers", "ntbs", "technical barriers to trade"),
    ),
    # ── Digital ──────────────────────────────────────────────────────
    "digital.digital_adoption": RuntimeCanonicalEntry(
        canonical_name="digital.digital_adoption",
        aliases=("digital adoption", "digital adoption index", "digitalization"),
    ),
    "digital.broadband_penetration": RuntimeCanonicalEntry(
        canonical_name="digital.broadband_penetration",
        aliases=("broadband penetration", "broadband access", "broadband subscribers"),
    ),
    "digital.e_commerce_share": RuntimeCanonicalEntry(
        canonical_name="digital.e_commerce_share",
        aliases=("e-commerce share", "e commerce share", "online commerce share"),
    ),
    "digital.digital_skills": RuntimeCanonicalEntry(
        canonical_name="digital.digital_skills",
        aliases=("digital skills", "ict skills", "digital competence"),
    ),
    "digital.cybersecurity_readiness": RuntimeCanonicalEntry(
        canonical_name="digital.cybersecurity_readiness",
        aliases=("cybersecurity readiness", "cyber security", "cybersecurity index"),
    ),
    # ── Finance ──────────────────────────────────────────────────────
    "finance.financial_inclusion": RuntimeCanonicalEntry(
        canonical_name="finance.financial_inclusion",
        aliases=("financial inclusion", "financial access", "bank account ownership", "account penetration"),
    ),
    "finance.microfinance_access": RuntimeCanonicalEntry(
        canonical_name="finance.microfinance_access",
        aliases=("microfinance access", "microcredit access", "microfinance penetration"),
    ),
    "finance.insurance_penetration": RuntimeCanonicalEntry(
        canonical_name="finance.insurance_penetration",
        aliases=("insurance penetration", "insurance coverage", "insurance density"),
    ),
    "finance.banking_sector_stability": RuntimeCanonicalEntry(
        canonical_name="finance.banking_sector_stability",
        aliases=("banking sector stability", "financial stability", "bank stability", "npl ratio"),
    ),
    "finance.mobile_money": RuntimeCanonicalEntry(
        canonical_name="finance.mobile_money",
        aliases=("mobile money", "mobile payments", "mobile financial services"),
    ),
    # ── Environment ──────────────────────────────────────────────────
    "environment.biodiversity_index": RuntimeCanonicalEntry(
        canonical_name="environment.biodiversity_index",
        aliases=("biodiversity index", "biodiversity", "species richness", "biodiversity loss"),
    ),
    "environment.forest_cover": RuntimeCanonicalEntry(
        canonical_name="environment.forest_cover",
        aliases=("forest cover", "forest area", "forest coverage", "forested area"),
    ),
    "environment.soil_quality": RuntimeCanonicalEntry(
        canonical_name="environment.soil_quality",
        aliases=("soil quality", "soil health", "soil fertility", "soil degradation"),
    ),
    "environment.marine_protected_area": RuntimeCanonicalEntry(
        canonical_name="environment.marine_protected_area",
        aliases=("marine protected area", "ocean protection", "marine conservation"),
    ),
    # ── Conflict & Security ──────────────────────────────────────────
    "security.conflict_intensity": RuntimeCanonicalEntry(
        canonical_name="security.conflict_intensity",
        aliases=("conflict intensity", "armed conflict", "conflict incidence", "violence intensity"),
    ),
    "security.homicide_rate": RuntimeCanonicalEntry(
        canonical_name="security.homicide_rate",
        aliases=("homicide rate", "murder rate", "intentional homicides"),
    ),
    "security.displacement": RuntimeCanonicalEntry(
        canonical_name="security.displacement",
        aliases=("displacement", "internally displaced persons", "refugees", "forced displacement"),
    ),
    "security.peacebuilding": RuntimeCanonicalEntry(
        canonical_name="security.peacebuilding",
        aliases=("peacebuilding", "peace building", "post-conflict reconstruction"),
    ),
}


def runtime_canonical_entries() -> dict[str, RuntimeCanonicalEntry]:
    return dict(RUNTIME_CANONICAL_REGISTRY)


def runtime_canonical_names() -> set[str]:
    return set(RUNTIME_CANONICAL_REGISTRY)


def runtime_approved_synonyms() -> dict[str, str]:
    synonyms: dict[str, str] = {}
    for canonical_name, entry in RUNTIME_CANONICAL_REGISTRY.items():
        synonyms.setdefault(canonical_name.strip().lower(), canonical_name)
        synonyms.setdefault(canonical_name.replace(".", " ").replace("_", " ").strip().lower(), canonical_name)
        for alias in entry.aliases:
            clean_alias = str(alias or "").strip().lower()
            if clean_alias:
                synonyms.setdefault(clean_alias, canonical_name)
    return synonyms


__all__ = [
    "RUNTIME_CANONICAL_REGISTRY",
    "RUNTIME_CANONICAL_REGISTRY_VERSION",
    "RuntimeCanonicalEntry",
    "runtime_approved_synonyms",
    "runtime_canonical_entries",
    "runtime_canonical_names",
]
