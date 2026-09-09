"""Measure the current legal-correspondence bridge without changing source/data."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from polisyos.lex.knowledge.store import LegalKnowledgeStore
from polisyos.runtime.quality import intervention_substrate as owner

if TYPE_CHECKING:
    from polisyos.lex.knowledge.types import LegalThresholdEvaluation

ROOT = Path.cwd()


class CountingStore:
    def __init__(self, store: LegalKnowledgeStore) -> None:
        self.store = store
        self.evaluations = 0

    def __getattr__(self, name: str) -> object:
        return getattr(self.store, name)

    def evaluate_rule_threshold(self, **kwargs: object) -> LegalThresholdEvaluation:
        self.evaluations += 1
        return self.store.evaluate_rule_threshold(**kwargs)


def decide(
    bundle: owner.InterventionSubstrateBundle,
    law: str,
    knob: str,
    value: object,
    store: CountingStore,
) -> dict[str, Any]:
    before = store.evaluations
    try:
        result = owner.resolve_law_bound_lever(
            bundle, law_token=law, knob_id=knob,
            parameter_value=value, legal_store=store,
        )
    except Exception as exc:
        output = {"error_type": type(exc).__name__, "error": str(exc),
                  "code": getattr(exc, "code", None)}
    else:
        output = {
            "schema_version": result.schema_version,
            "status": result.status,
            "current_authority_status": result.current_authority_status,
            "mapping_predicate_provenance": result.mapping_predicate_provenance,
            "mapping_reason_code": result.mapping_reason_code,
            "mapping_evidence_ref": result.mapping_evidence_ref,
            "threshold_id": result.threshold_id,
            "legal_threshold_evaluation": result.legal_threshold_evaluation,
            "resolution_content_hash": result.content_hash,
        }
    return {"law_token": law, "knob_id": knob, "parameter_value": value,
            "numeric_evaluator_calls": store.evaluations - before, "result": output}


def _emit(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


def main() -> None:
    paths = owner.default_l6_bundle_paths(ROOT)
    bundle = owner.load_l6_intervention_substrate(ROOT)
    raw_map = json.loads(paths["lex_intervention_map"].read_text())
    raw_knobs = json.loads(paths["intervention_knob_dictionary"].read_text())
    raw_pairs = {
        (law, knob) for law, row in raw_map.items()
        for knob in (row if isinstance(row, list) else row["knob_ids"])
    }
    owner_pairs = {
        (str(row.get("law_token", row["metadata"]["law_token"])), knob)
        for row in bundle.lex_authority_manifest["intervention_map_entries"]
        for knob in row["knob_ids"]
    }
    if raw_pairs != owner_pairs:
        raise ValueError((raw_pairs - owner_pairs, owner_pairs - raw_pairs))
    if set(raw_knobs) != set(bundle.knob_dictionary):
        raise ValueError("raw_and_owner_knob_identity_sets_differ")
    identities = []
    for path in (
        ROOT / "src/polisyos/runtime/quality/intervention_substrate.py",
        ROOT / "src/polisyos/runtime/quality/credal_reference.py",
        ROOT / "src/polisyos/lex/intervention_artifacts.py",
        ROOT / "src/polisyos/lex/knowledge/types.py",
        ROOT / "src/polisyos/foundry/validation/constraints_engine.py",
        paths["owner_authority_bindings"],
    ):
        blob = subprocess.run(  # noqa: S603 - fixed local git command; paths are data, no shell.
            ["/usr/bin/git", "hash-object", str(path)], check=True,
            capture_output=True, text=True,
        ).stdout.strip()
        identities.append({"path": str(path.relative_to(ROOT)), "git_blob": blob})
    for key in ("intervention_knob_dictionary", "lex_intervention_map"):
        path = paths[key]
        identities.append({"path": str(path.relative_to(ROOT)),
                           "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    _emit({"source_identities": identities,
           "denominator": {"raw_json_law_knob_pairs": len(raw_pairs),
                           "independent_owner_registry_pairs": len(owner_pairs),
                           "pair_identity_symmetric_difference": [],
                           "raw_knobs": len(raw_knobs),
                           "owner_knob_identity_symmetric_difference": []}})
    db = ROOT / (
        "production_data/lex/lex-amendment-only-optimized-20260501-v3/"
        "finalize/lex_knowledge_graph.duckdb"
    )
    store = CountingStore(LegalKnowledgeStore(db, db.parent))
    for law, knob in sorted(raw_pairs):
        output = decide(bundle, law, knob,
                        owner._representative_knob_value(raw_knobs[knob], knob_id=knob), store)
        _emit({"case": "complete_real_baseline", **output})
    manifest = copy.deepcopy(bundle.lex_authority_manifest)
    entries = {row["law_token"]: row for row in manifest["intervention_map_entries"]}
    budget, tax = entries["budget_law"], entries["tax_relief_statute"]
    budget["provision_ref"], tax["provision_ref"] = tax["provision_ref"], budget["provision_ref"]
    transposed = owner.replace_intervention_substrate_bundle(
        bundle, update={"lex_authority_manifest": manifest})
    _emit({"case": "real_transposition", **decide(
        transposed, "tax_relief_statute", "tax_relief_rate", 0.24, store)})
    manifest = copy.deepcopy(bundle.lex_authority_manifest)
    for row in manifest["intervention_map_entries"]:
        if row["law_token"] == "budget_law":  # noqa: S105 - semantic law identity, not a secret.
            row["measurement_expectations"]["candidate_unit"] = "corr.invalid.unit"
    bad_units = owner.replace_intervention_substrate_bundle(
        bundle, update={"lex_authority_manifest": manifest})
    _emit({"case": "missing_subject_with_bad_units", **decide(
        bad_units, "budget_law", "budget_allocation_multiplier", 1.0, store)})


if __name__ == "__main__":
    main()
