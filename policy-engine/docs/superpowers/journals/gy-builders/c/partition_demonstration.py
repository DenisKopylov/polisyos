"""Recompute complete source partitions and demonstrate their semantic residual."""
from __future__ import annotations

import hashlib
import json
import runpy
from pathlib import Path

root = Path(__file__).resolve().parents[5]
harness = runpy.run_path(root / "tests/unit/runtime/quality/test_operator_comprehension.py")
module = harness["owner"]()
raw = json.loads(harness["CORPUS"].read_text())
spec = module.seal_corpus(raw)
training = [item for item in spec.items if item.partition == "training"]
sealed = [item for item in spec.items if item.partition == "sealed"]
# Direct pair enumeration and independent inverted membership sets reconcile the full set.
pairs = [(a.item_id, b.item_id) for a in training for b in sealed
         if set(a.stimulus_family) & set(b.stimulus_family)]
index = {}
for item in spec.items:
    for member in item.stimulus_family:
        index.setdefault(member, {"training":set(), "sealed":set()})[item.partition].add(item.item_id)
inverted = {(a, b) for partitions in index.values()
            for a in partitions["training"] for b in partitions["sealed"]}
assert set(pairs) == inverted == set()

# A human-readable semantic twin with different bytes demonstrates the exact bound.
training_raw = next(item for item in raw["items"] if item["partition"] == "training")
sealed_raw = next(item for item in raw["items"]
                  if item["partition"] == "sealed" and item["construct"] == "unknown")
training_raw["stimulus_text"] = "The decisive observation is unavailable. Obtain it; do not infer zero."
training_raw["stimulus_family"] = [training_raw["stimulus_text"]]
residual_spec = module.seal_corpus(raw)
residual = module.score_trials(residual_spec, harness["events"](residual_spec), design=harness["design"]())
assert residual.result == "instrument_demonstrated"
assert residual.human_comprehension_established is False
assert residual.projection()["semantic_independence"] == "not_established"
print(json.dumps({
    "fixture": str(harness["CORPUS"].relative_to(root)),
    "fixture_sha256": hashlib.sha256(harness["CORPUS"].read_bytes()).hexdigest(),
    "schema": spec.schema_version,
    "all_item_denominator": len(spec.items),
    "training_denominator": len(training), "sealed_denominator": len(sealed),
    "pair_denominator": len(training) * len(sealed),
    "overlapping_family_member_pairs": len(pairs),
    "independent_inverted_pairs": len(inverted),
    "target_authority_levels": sorted({item.target_authority_level for item in spec.items}),
    "paraphrase_residual": {
        "sealed_source": sealed_raw["stimulus_text"],
        "training_source": training_raw["stimulus_text"],
        "structural_admission": "accepted", "candidate_result": residual.result,
        "human_comprehension_established": residual.human_comprehension_established,
        "semantic_independence": residual.projection()["semantic_independence"],
        "limitations": residual.projection()["limitations"],
        "smallest_missing_capability": "W5-R3-Q06 independent item/family adjudication",
        "owner_absence_evidence": "stage1 complete src owner census plus institutional row",
    },
}, indent=2))
