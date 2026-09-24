"""Review exact source-family separation without adjudicating paraphrase semantics."""

import copy
import hashlib
import json
from pathlib import Path

import polisyos.runtime.http.services.control  # supported Runtime composition root
from polisyos.runtime.quality.operator_comprehension import seal_corpus


if __name__ == "__main__":
    source = Path("tests/fixtures/runtime_quality/operator_comprehension.json")
    raw = json.loads(source.read_text())
    items = raw["items"]
    training = [item for item in items if item["partition"] == "training"]
    sealed = [item for item in items if item["partition"] == "sealed"]
    matches = {
        (train["item_id"], test["item_id"])
        for train in training
        for test in sealed
        if train["stimulus_text"] == test["stimulus_text"]
    }
    inverse = {
        (train["item_id"], test["item_id"])
        for test in sealed
        for train in training
        if train["stimulus_text"].encode() == test["stimulus_text"].encode()
    }
    assert matches == inverse
    seal_corpus(raw)
    changed = copy.deepcopy(raw)
    train = next(item for item in changed["items"] if item["partition"] == "training")
    test = next(item for item in changed["items"] if item["partition"] == "sealed")
    train["stimulus_family"].append(test["stimulus_text"])
    assert train["stimulus_text"] != test["stimulus_text"]
    assert set(train["stimulus_family"]) != set(test["stimulus_family"])
    overlap = set(train["stimulus_family"]) & set(test["stimulus_family"])
    try:
        seal_corpus(changed)
    except ValueError as error:
        accepted = False
        disposition = str(error)
    else:
        accepted = True
        disposition = "admitted"
    print(json.dumps({
        "corpus_path": str(source),
        "corpus_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "item_denominator": len(items),
        "training_items": len(training),
        "sealed_items": len(sealed),
        "complete_pair_denominator": len(training) * len(sealed),
        "exact_source_reuse_pairs": len(matches),
        "independent_reverse_pair_count": len(inverse),
        "mutant_distinct_sources": True,
        "mutant_declared_family_overlap": len(overlap),
        "real_owner_accepts_overlapping_declared_family": accepted,
        "disposition": disposition,
    }, indent=2))
