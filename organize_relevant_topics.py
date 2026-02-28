#!/usr/bin/env python3
"""Theme-based ordering for relevant OpenAlex topics.

This script does not remove rows. It:
1) classifies each topic into one of 3 high-level blocks,
2) assigns a thematic sub-block,
3) sorts topics by block/sub-block/works_count,
4) overwrites input CSV with sorted rows (same 5 original columns),
5) writes an annotated CSV and a summary CSV.
"""

from __future__ import annotations

import argparse
import csv
import re
from collections import Counter, defaultdict
from pathlib import Path


ORIG_FIELDS = ["id", "display_name", "description", "works_count", "cited_by_count"]


COUNTRY_TERMS = [
    "american",
    "european",
    "african",
    "asian",
    "latin american",
    "canadian",
    "chinese",
    "brazilian",
    "german",
    "dutch",
    "polish",
    "vietnamese",
    "hungarian",
    "french",
    "italian",
    "spanish",
    "russian",
    "balkan",
    "middle eastern",
    "australian",
    "pacific",
    "eurasian",
    "uk",
    "us",
    "ukrain",
    "serbia",
    "tunisia",
    "nordic",
    "iberian",
    "philippine",
    "indonesia",
    "austria",
    "swiss",
    "portuguese",
]
COUNTRY_PAT = "|".join(re.escape(x) for x in COUNTRY_TERMS)


# "regulation" is intentionally omitted from core to avoid biology false positives.
CORE_NAME_PATTERNS = [
    r"\bpolicy\b",
    r"\bpolicies\b",
    r"\bgovernance\b",
    r"\bpublic administration\b",
    r"\bgovernment\b",
    r"\blaw\b",
    r"\blegal\b",
    r"\bconstitutional\b",
    r"\bpolitical science\b",
    r"\bdemocracy\b",
    r"\bpublic policy\b",
    r"\bpublic economics\b",
    r"\bfiscal\b",
    r"\bmonetary\b",
    r"\btax\w*\b",
    r"\beconometrics\b",
    r"\bcausal\b",
    r"\bpolicy evaluation\b",
    r"\bpolicy analysis\b",
    r"\bdecision making\b",
    r"\bwelfare state\b",
    r"\binstitution\w*\b",
    r"\bgovern\w+\b",
]
CORE_DESC_PATTERNS = CORE_NAME_PATTERNS + [
    r"\badministrative\b",
    r"\bjurisprudence\b",
    r"\bstate capacity\b",
    r"\bpolicy instrument\b",
    r"\bregulatory policy\b",
    r"\blegal regulation\b",
    r"\bregulatory framework\b",
    r"\bregulatory agency\b",
]

DOMAIN_NAME_PATTERNS = [
    r"\bhealth\w*\b",
    r"\bmedical\b",
    r"\bnursing\b",
    r"\bdisease\b",
    r"\bepidemiolog\w*\b",
    r"\beducation\b",
    r"\bschool\b",
    r"\buniversity\b",
    r"\bhousing\b",
    r"\burban\b",
    r"\btransport\w*\b",
    r"\binfrastructure\b",
    r"\bagricultur\w*\b",
    r"\bfood\b",
    r"\brural\b",
    r"\benergy\b",
    r"\bclimate\b",
    r"\benvironment\w*\b",
    r"\bdisaster\b",
    r"\bmigration\b",
    r"\bimmigration\b",
    r"\bemployment\b",
    r"\blabor\b",
    r"\bcrime\b",
    r"\bcriminal\b",
    r"\bjustice\b",
    r"\binsurance\b",
    r"\bfinance\b",
    r"\bbanking\b",
    r"\bentrepreneur\w*\b",
    r"\bmarket\b",
    r"\btrade\b",
    r"\bindustr\w*\b",
    r"\btechnology\b",
    r"\bdigital\b",
    r"\binnovation\b",
    r"\bpoverty\b",
    r"\binequality\b",
    r"\bpublic health\b",
    r"\bmental health\b",
]
DOMAIN_DESC_PATTERNS = DOMAIN_NAME_PATTERNS

CONTEXT_NAME_PATTERNS = [
    r"\bhistory\b",
    r"\bhistorical\b",
    r"\bculture\b",
    r"\bcultural\b",
    r"\bheritage\b",
    r"\bidentity\b",
    r"\bsociolog\w*\b",
    r"\banthropolog\w*\b",
    r"\bethnograph\w*\b",
    r"\bregional studies\b",
    r"\barea studies\b",
    rf"\b({COUNTRY_PAT})\b",
]
CONTEXT_DESC_PATTERNS = CONTEXT_NAME_PATTERNS + [
    r"\bcolonial\b",
    r"\bpostcolonial\b",
    r"\bnationalism\b",
    r"\bminorit\w*\b",
    r"\bindigenous\b",
    r"\bcivilization\b",
    r"\bmemory studies\b",
]


def _compile(patterns: list[str]) -> list[re.Pattern[str]]:
    return [re.compile(p, re.IGNORECASE) for p in patterns]


CORE_NAME_RE = _compile(CORE_NAME_PATTERNS)
CORE_DESC_RE = _compile(CORE_DESC_PATTERNS)
DOMAIN_NAME_RE = _compile(DOMAIN_NAME_PATTERNS)
DOMAIN_DESC_RE = _compile(DOMAIN_DESC_PATTERNS)
CONTEXT_NAME_RE = _compile(CONTEXT_NAME_PATTERNS)
CONTEXT_DESC_RE = _compile(CONTEXT_DESC_PATTERNS)

CONTEXT_ANCHOR_RE = re.compile(
    rf"\b(history|historical|culture|cultural|heritage|identity|regional studies|area studies|{COUNTRY_PAT})\b",
    re.IGNORECASE,
)
CORE_ANCHOR_RE = re.compile(
    r"\b(policy|policies|governance|public administration|law|legal|political science|constitutional|fiscal|monetary|tax|econometrics|policy evaluation|policy analysis|causal)\b",
    re.IGNORECASE,
)
HISTORICAL_ANCHOR_RE = re.compile(r"\b(history|historical)\b", re.IGNORECASE)
CULTURAL_ANCHOR_RE = re.compile(
    r"\b(cultural|heritage|identity|classical|ancient|colonial|postcolonial|sociological?)\b",
    re.IGNORECASE,
)


SUB_ORDERS = {
    "01_policy_core": {
        "governance_law_regulation": 1,
        "macro_fiscal_monetary_policy": 2,
        "social_labor_welfare_policy": 3,
        "policy_methods_and_evaluation": 4,
        "international_and_public_institutions": 5,
        "core_general": 9,
    },
    "02_domain_policy_knowledge": {
        "health_and_healthcare": 1,
        "education_and_human_capital": 2,
        "economy_finance_business": 3,
        "labor_migration_social_development": 4,
        "climate_energy_environment": 5,
        "agriculture_food_rural": 6,
        "urban_housing_transport": 7,
        "technology_industry_digital": 8,
        "justice_security_disaster_risk": 9,
        "international_development_and_trade": 10,
        "domain_general": 99,
    },
    "03_context_sociocultural": {
        "country_region_profiles": 1,
        "historical_political_context": 2,
        "sociocultural_identity_values": 3,
        "comparative_area_studies": 4,
        "context_general": 99,
    },
}

BLOCK_ORDER = {
    "01_policy_core": 1,
    "02_domain_policy_knowledge": 2,
    "03_context_sociocultural": 3,
}


def count_hits(regexes: list[re.Pattern[str]], text: str) -> int:
    return sum(len(r.findall(text)) for r in regexes)


def classify_block(name: str, desc: str) -> tuple[str, int, int, int]:
    core = 4 * count_hits(CORE_NAME_RE, name) + count_hits(CORE_DESC_RE, desc)
    domain = 4 * count_hits(DOMAIN_NAME_RE, name) + count_hits(DOMAIN_DESC_RE, desc)
    context = 4 * count_hits(CONTEXT_NAME_RE, name) + count_hits(CONTEXT_DESC_RE, desc)

    # Strong context override for historical/cultural/regional profiles.
    if HISTORICAL_ANCHOR_RE.search(name) and CULTURAL_ANCHOR_RE.search(name):
        return "03_context_sociocultural", core, domain, context
    if CONTEXT_ANCHOR_RE.search(name) and not CORE_ANCHOR_RE.search(name) and context + 1 >= domain:
        return "03_context_sociocultural", core, domain, context

    # Core policy/institutions/law layer.
    if core >= 6 and core >= domain - 1:
        return "01_policy_core", core, domain, context
    if CORE_ANCHOR_RE.search(name) and not HISTORICAL_ANCHOR_RE.search(name):
        return "01_policy_core", core, domain, context

    # Context when it is clearly dominant.
    if context >= 8 and context >= domain + 1:
        return "03_context_sociocultural", core, domain, context

    return "02_domain_policy_knowledge", core, domain, context


def classify_subblock(block: str, name: str, desc: str) -> str:
    text = f"{name} {desc}".lower()

    if block == "01_policy_core":
        if re.search(r"\b(law|legal|constitutional|regulation|regulatory|judicial|antitrust|jurisprudence)\b", text):
            return "governance_law_regulation"
        if re.search(r"\b(fiscal|monetary|tax|public economics|macroeconom|economic growth|inflation|public finance)\b", text):
            return "macro_fiscal_monetary_policy"
        if re.search(r"\b(welfare|social policy|labor market|employment|inequality|poverty|redistribution|social protection)\b", text):
            return "social_labor_welfare_policy"
        if re.search(r"\b(policy evaluation|policy analysis|causal|econometrics|decision making|system dynamics|impact assessment)\b", text):
            return "policy_methods_and_evaluation"
        if re.search(r"\b(governance|public administration|government|democracy|institution|public sector|eu|international law)\b", text):
            return "international_and_public_institutions"
        return "core_general"

    if block == "02_domain_policy_knowledge":
        if re.search(r"\b(health|healthcare|medical|nursing|disease|public health|mental health|rehabilitation|epidemiolog|hospital|bioethics)\b", text):
            return "health_and_healthcare"
        if re.search(r"\b(education|school|university|teaching|learning|higher education|curriculum|literacy)\b", text):
            return "education_and_human_capital"
        if re.search(r"\b(finance|banking|corporate|market|investment|insurance|entrepreneur|productivity|accounting|business)\b", text):
            return "economy_finance_business"
        if re.search(r"\b(migration|immigration|refugee|labor|employment|social development|family policy|welfare|inequality|poverty)\b", text):
            return "labor_migration_social_development"
        if re.search(r"\b(climate|energy|environment|carbon|emission|sustainability|renewable|pollution|biodiversity)\b", text):
            return "climate_energy_environment"
        if re.search(r"\b(agricultur|food|rural|farm|livestock|fisher|soil|crop)\b", text):
            return "agriculture_food_rural"
        if re.search(r"\b(urban|housing|transport|mobility|infrastructure|city|neighborhood|spatial planning)\b", text):
            return "urban_housing_transport"
        if re.search(r"\b(technology|digital|ai|artificial intelligence|blockchain|sensor|manufacturing|industrial|simulation|optimization|wireless)\b", text):
            return "technology_industry_digital"
        if re.search(r"\b(criminal|crime|justice|disaster|risk|safety|security|resilience|emergency)\b", text):
            return "justice_security_disaster_risk"
        if re.search(r"\b(trade|globalization|international development|aid|competitiveness|fdi|arbitration)\b", text):
            return "international_development_and_trade"
        return "domain_general"

    if re.search(rf"\b({COUNTRY_PAT}|country|countries|regional)\b", text):
        return "country_region_profiles"
    if re.search(r"\b(history|historical|ancient|colonial|postcolonial|revolution|memory)\b", text):
        return "historical_political_context"
    if re.search(r"\b(cultural|culture|heritage|identity|ethnic|religion|societal|community|values)\b", text):
        return "sociocultural_identity_values"
    if re.search(r"\b(area studies|comparative|civilization|cross-cultural)\b", text):
        return "comparative_area_studies"
    return "context_general"


def to_int(value: str) -> int:
    try:
        return int(value)
    except Exception:
        return -1


def run(input_csv: Path, labeled_csv: Path, summary_csv: Path) -> None:
    rows = list(csv.DictReader(input_csv.open(newline="", encoding="utf-8")))
    labeled_rows: list[dict[str, str]] = []

    for row in rows:
        name = row.get("display_name", "")
        desc = row.get("description", "")
        block, s_core, s_domain, s_context = classify_block(name, desc)
        subblock = classify_subblock(block, name, desc)

        rec = dict(row)
        rec["policy_block"] = block
        rec["policy_subblock"] = subblock
        rec["score_core"] = str(s_core)
        rec["score_domain"] = str(s_domain)
        rec["score_context"] = str(s_context)
        labeled_rows.append(rec)

    labeled_rows.sort(
        key=lambda x: (
            BLOCK_ORDER.get(x["policy_block"], 99),
            SUB_ORDERS.get(x["policy_block"], {}).get(x["policy_subblock"], 999),
            -to_int(x.get("works_count", "")),
            x.get("display_name", "").lower(),
        )
    )

    # Overwrite original CSV with sorted records and original columns only.
    with input_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ORIG_FIELDS)
        writer.writeheader()
        for row in labeled_rows:
            writer.writerow({k: row.get(k, "") for k in ORIG_FIELDS})

    # Labeled output with block metadata.
    labeled_fields = ORIG_FIELDS + [
        "policy_block",
        "policy_subblock",
        "score_core",
        "score_domain",
        "score_context",
    ]
    with labeled_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=labeled_fields)
        writer.writeheader()
        writer.writerows(labeled_rows)

    # Summary by block/sub-block.
    summary_counts: dict[tuple[str, str], int] = defaultdict(int)
    for row in labeled_rows:
        summary_counts[(row["policy_block"], row["policy_subblock"])] += 1

    with summary_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["policy_block", "policy_subblock", "topics_count"])
        writer.writeheader()
        for block in ["01_policy_core", "02_domain_policy_knowledge", "03_context_sociocultural"]:
            items = sorted(
                ((sub, count) for (b, sub), count in summary_counts.items() if b == block),
                key=lambda x: SUB_ORDERS[block].get(x[0], 999),
            )
            for sub, count in items:
                writer.writerow(
                    {
                        "policy_block": block,
                        "policy_subblock": sub,
                        "topics_count": count,
                    }
                )

    # Per-block files for easier manual review.
    block_files = {
        "01_policy_core": "relevant_topics_block_policy_core.csv",
        "02_domain_policy_knowledge": "relevant_topics_block_domain_knowledge.csv",
        "03_context_sociocultural": "relevant_topics_block_context_sociocultural.csv",
    }
    for block, filename in block_files.items():
        block_rows = [row for row in labeled_rows if row["policy_block"] == block]
        out_path = input_csv.parent / filename
        with out_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=ORIG_FIELDS
                + ["policy_block", "policy_subblock", "score_core", "score_domain", "score_context"],
            )
            writer.writeheader()
            writer.writerows(block_rows)

    block_counts = Counter(row["policy_block"] for row in labeled_rows)
    print(f"rows_in={len(rows)} rows_out={len(labeled_rows)}")
    for block in ["01_policy_core", "02_domain_policy_knowledge", "03_context_sociocultural"]:
        print(f"{block}={block_counts[block]}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Organize relevant topics into thematic policy blocks.")
    parser.add_argument("--input", default="relevant_topics.csv", help="Input CSV path.")
    parser.add_argument("--labeled-output", default="relevant_topics_thematic.csv", help="Annotated output CSV path.")
    parser.add_argument("--summary-output", default="relevant_topics_thematic_summary.csv", help="Summary output CSV path.")
    args = parser.parse_args()

    run(Path(args.input), Path(args.labeled_output), Path(args.summary_output))


if __name__ == "__main__":
    main()
