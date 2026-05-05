#!/usr/bin/env python3
"""Filter OpenAlex topics down to policy-relevant rows."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path


def filter_topics(input_csv: Path, output_csv: Path) -> None:
    """Write rows whose topic name/description is relevant to PolisyOS domains."""
    positive_keywords = [
        r"\bpolicy\b",
        r"\bpolicies\b",
        r"\bgovernment\b",
        r"\bgovernance\b",
        r"\beconomics\b",
        r"\beconomic\b",
        r"\bmacroeconomics\b",
        r"\bmicroeconomics\b",
        r"\beconometrics\b",
        r"\beconomy\b",
        r"\btax\b",
        r"\btaxation\b",
        r"\bfiscal\b",
        r"\bmonetary\b",
        r"\blabor market\b",
        r"\bemployment\b",
        r"\bunemployment\b",
        r"\bwelfare\b",
        r"\bpoverty\b",
        r"\binequality\b",
        r"\bsocial justice\b",
        r"\bpublic administration\b",
        r"\blaw\b",
        r"\blegal\b",
        r"\bjurisprudence\b",
        r"\bjustice\b",
        r"\bconstitutional\b",
        r"\bpolitical\b",
        r"\bpolitics\b",
        r"\bdemocracy\b",
        r"\bsocial sciences\b",
        r"\bsociology\b",
        r"\bdemography\b",
        r"\bdemographics\b",
        r"\beducation\b",
        r"\bpedagogy\b",
        r"\bpublic health\b",
        r"\bhealthcare\b",
        r"\burban planning\b",
        r"\burban development\b",
        r"\btransportation\b",
        r"\binfrastructure\b",
        r"\bagriculture\b",
        r"\benergy policy\b",
        r"\bclimate change\b",
        r"\benvironmental policy\b",
        r"\bsustainability\b",
        r"\bhuman rights\b",
        r"\bpublic goods\b",
        r"\bcausal inference\b",
        r"\bcausality\b",
        r"\bsimulation\b",
        r"\bagent-based\b",
        r"\bmulti-agent\b",
        r"\bsocial dynamics\b",
        r"\btrade\b",
        r"\bglobalization\b",
        r"\bcriminology\b",
        r"\bcrime\b",
        r"\bmigration\b",
        r"\bimmigration\b",
        r"\brefugees\b",
        r"\burban studies\b",
        r"\bregulation\b",
        r"\bregulatory\b",
        r"\binstitutions\b",
        r"\bcivil society\b",
    ]
    negative_keywords = [
        r"\bphysics\b",
        r"\baerospace\b",
        r"\bastronomy\b",
        r"\bastrophysics\b",
        r"\bquantum\b",
        r"\bchemistry\b",
        r"\bbiology\b",
        r"\bmolecular\b",
        r"\bcellular\b",
        r"\bgenetics\b",
        r"\bgenomics\b",
        r"\bmicrobiology\b",
        r"\banimal nutrition\b",
        r"\bzoology\b",
        r"\bbotany\b",
        r"\bfluid dynamics\b",
        r"\bmaterials science\b",
        r"\bmetallurgy\b",
        r"\bphotonics\b",
        r"\boptics\b",
        r"\bmagnetic\b",
        r"\bcrystallography\b",
        r"\bsemiconductor\b",
        r"\bgastroenterology\b",
        r"\bdermatology\b",
        r"\bdentistry\b",
        r"\borthopedic\b",
        r"\bsurgery\b",
        r"\bclinical\b",
        r"\bpathology\b",
        r"\boncology\b",
        r"\bpaleontology\b",
        r"\barchaeology\b",
        r"\bmedieval\b",
        r"\bclassical antiquity\b",
        r"\bliterature\b",
        r"\bpoetry\b",
        r"\bmusicology\b",
        r"\bneurobiology\b",
        r"\bmicrobiome\b",
    ]

    pos_re = re.compile("|".join(positive_keywords), re.IGNORECASE)
    neg_re = re.compile("|".join(negative_keywords), re.IGNORECASE)
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    total_count = 0
    relevant_count = 0
    with (
        input_csv.open("r", encoding="utf-8", newline="") as infile,
        output_csv.open("w", encoding="utf-8", newline="") as outfile,
    ):
        reader = csv.DictReader(infile)
        if reader.fieldnames is None:
            raise ValueError(f"{input_csv} does not contain a CSV header")
        writer = csv.DictWriter(outfile, fieldnames=reader.fieldnames)
        writer.writeheader()

        for row in reader:
            total_count += 1
            text_to_search = f"{row.get('display_name', '')} {row.get('description', '')}"
            neg_matches = len(neg_re.findall(text_to_search))
            pos_matches = len(pos_re.findall(text_to_search))
            if pos_matches > 0 and pos_matches > neg_matches:
                writer.writerow(row)
                relevant_count += 1

    print(f"Filtering complete. Read {total_count} rows, found {relevant_count} relevant topics.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("topics.csv"))
    parser.add_argument("--output", type=Path, default=Path("relevant_topics.csv"))
    args = parser.parse_args(argv)
    try:
        filter_topics(args.input, args.output)
    except Exception as exc:
        print(f"Error filtering topics: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
