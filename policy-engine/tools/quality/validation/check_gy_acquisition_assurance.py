"""Run the non-test GY-AS1 instrument against real AQ1 and a separate oracle."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import yaml

from polisyos.fabric.evidence.acquisition_assurance import (
    MUTANTS,
    data_availability_positive_control,
    decode_case_inputs,
    observation_wire,
    run_corpus,
)
from polisyos.fabric.evidence.non_data_acquisition import AcquisitionType

ROOT = Path(__file__).resolve().parents[3]
CORPUS = ROOT / "docs/reference/gy-acquisition-assurance-corpus.json"
ORACLE = ROOT / "tools/quality/validation/gy_acquisition_assurance_oracle.py"
EXPECTED = ROOT / "docs/reference/gy-acquisition-assurance-oracle.tsv"
CORPUS_SHA256 = "5ba11a2f0d80dca0fca8ff30f6544d01b79e7e0be412e0eb8d0c5498ea22ad13"
EXPECTED_SHA256 = "ed74752c6e965bc5aabc4c0f8cd6d111ccf4f227646d46433223307bc001a3e0"
WITNESSES = {
    MUTANTS[0]: ("rows.grounding_relation.1", "state", "row_inflation_false_close"),
    MUTANTS[1]: ("form.grounding_relation", "state", "form_without_proof_admitted"),
    MUTANTS[2]: ("provisional.grounding_relation", "reentry", "owner_reentry_bypassed"),
    MUTANTS[3]: ("happy.grounding_relation", "ceiling", "subset_use_refused"),
    MUTANTS[4]: ("provisional.grounding_relation", "terminal", "unproved_terminal"),
    MUTANTS[5]: ("happy.grounding_relation", "authority", "candidate_authority_escape"),
    MUTANTS[6]: ("rows.grounding_relation.0", "state", "missing_object_nonclosure_removed"),
}


def validate_corpus(path: Path = CORPUS) -> dict[str, Any]:
    """Reconcile full IDs/families with independent JSON and YAML parser stacks."""
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != CORPUS_SHA256:
        raise ValueError("immutable_corpus_drift")
    subject = decode_case_inputs(path)
    separate = yaml.safe_load(raw)
    first = [(row["case_id"], row["family"]) for row in subject["cases"]]
    second = [(item["case_id"], item["family"]) for item in separate["cases"]]
    if first != second or len({identity for identity, _ in first}) != len(first):
        raise ValueError("corpus_parser_or_unique_identity_mismatch")
    types = {kind.value for kind in AcquisitionType}
    ids = {f"{family}.{kind}" for family in
           ("happy", "form", "provisional", "deeper", "reentry", "ceiling") for kind in types}
    ids.update(f"rows.{kind}.{count}" for kind in
               ("grounding_relation", "estimand_binding", "legal_mandate")
               for count in (0, 1, 1000, 1000000))
    ids.update(f"capstone.{name}" for name in ("education", "first_vertical", "unseen"))
    if ids != {identity for identity, _ in first}:
        raise ValueError("research_case_denominator_mismatch")
    research = (ROOT / "docs/research/policy-operations/int-r2/operational-closure-and-fixtures.md").read_text()
    family_table = research.split("## 4. Public regression fixture denominator", 1)[1].split(
        "### 4.1", 1
    )[0]
    source_counts = [int(value) for value in re.findall(r"^\|[^|]+\| (\d+) \|", family_table, re.M)]
    stated_total = re.search(r"\*\*Total\*\* \| \*\*(\d+)\*\*", family_table)
    if source_counts != [8, 8, 12, 16, 8, 8, 3] or stated_total is None:
        raise ValueError("research_family_table_changed")
    if sum(source_counts) != int(stated_total.group(1)) or sum(source_counts) != len(second):
        raise ValueError("research_total_reconciliation_failed")
    families = Counter(family for _, family in first)
    if families != {"happy": 8, "form": 8, "rows": 12, "provisional": 8,
                    "deeper": 8, "reentry": 8, "ceiling": 8, "capstone": 3}:
        raise ValueError("research_family_denominator_mismatch")
    if len(first) != 63 or not all(row["authority_purpose"] == "contract_testing"
                                   for row in subject["cases"]):
        raise ValueError("research_corpus_boundary_mismatch")
    full_demands = {row["discriminator"]: row["required_facts"] for row in subject["cases"]
                    if row["family"] == "happy"}
    for row in subject["cases"]:
        if row["family"] == "form":
            expected = full_demands[row["discriminator"]]
            actual = row["candidate"]["facts"]
            if row["required_facts"] != expected or not set(actual) < set(expected):
                raise ValueError("form_adversary_property_not_distinguished")
    return subject


def evaluate_wire(wire: str, *, challenge: str | None = None) -> subprocess.CompletedProcess[str]:
    """Call the root-owned isolated oracle; share only serialized observations."""
    command = [sys.executable, "-I", "-S", str(ORACLE), "--expectations", str(EXPECTED),
               "--expected-sha256", EXPECTED_SHA256]
    if challenge:
        command.extend(("--challenge", challenge))
    return subprocess.run(command, input=wire, capture_output=True, text=True, check=False, timeout=30)


def _scratch_root() -> Path:
    root = ROOT / "docs/superpowers/journals/gy-lattice/as1/raw"
    root.mkdir(parents=True, exist_ok=True)
    return root


def run_check(
    *, mutant: str | None = None, challenge: str | None = None, corpus_path: Path = CORPUS
) -> int:
    """Execute and grade the complete corpus, retaining every oracle finding."""
    corpus = validate_corpus(corpus_path)
    with TemporaryDirectory(prefix="as1-", dir=_scratch_root()) as directory:
        if data_availability_positive_control(Path(directory) / "data-control") != (False, True):
            raise ValueError("ordinary_data_positive_control_failed")
        observations = run_corpus(corpus, Path(directory), mutant=mutant)
        result = evaluate_wire(observation_wire(observations), challenge=challenge)
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    return result.returncode


def mutation_battery(*, corpus_path: Path = CORPUS) -> int:
    """Prove every predeclared mutation red on its own semantic witness."""
    corpus = validate_corpus(corpus_path)
    for mutant, (identity, field, reason) in WITNESSES.items():
        with TemporaryDirectory(prefix="as1-mutant-", dir=_scratch_root()) as directory:
            actual = run_corpus(corpus, Path(directory), mutant=mutant)
            result = evaluate_wire(observation_wire(actual))
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
        prefix = f"{identity}\t{field}\t"
        if result.returncode != 1 or not any(line.startswith(prefix)
                                             for line in result.stdout.splitlines()):
            sys.stdout.write(f"MUTANT_NOT_KILLED\t{mutant}\t{reason}\n")
            return 1
        sys.stdout.write(f"MUTANT_KILLED\t{mutant}\t{reason}\n")
    return 0


def main() -> int:
    """Expose baseline, drift, mutation and actual independence-removal checks."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--mutant", choices=MUTANTS)
    parser.add_argument("--mutation-battery", action="store_true")
    parser.add_argument("--challenge", choices=("decoder", "loader", "comparator", "unconfined"))
    parser.add_argument("--corpus", type=Path, default=CORPUS)
    args = parser.parse_args()
    try:
        validate_corpus(args.corpus)
        if args.mutation_battery:
            return mutation_battery(corpus_path=args.corpus)
        return run_check(mutant=args.mutant, challenge=args.challenge, corpus_path=args.corpus)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"ASSURANCE_REFUSED\t{type(exc).__name__}\t{exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
