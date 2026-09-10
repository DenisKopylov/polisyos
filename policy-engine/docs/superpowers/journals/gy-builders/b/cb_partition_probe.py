"""Independently enumerate literal training-stimulus reuse in the CB1 corpus."""

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
    reused = []
    for train in training:
        # Exact known presentation wrapper only; no semantic/fuzzy adjudication.
        core = train["content"].removeprefix("Practice demonstration: ")
        for test in sealed:
            if core and core in test["content"]:
                reused.append((train["item_id"], test["item_id"]))
    # Independently invert the complete pair enumeration using encoded bytes.
    inverse = {
        (train["item_id"], test["item_id"])
        for test in sealed
        for train in training
        if train["content"].encode().removeprefix(b"Practice demonstration: ")
        in test["content"].encode()
    }
    assert set(reused) == inverse
    assert len(items) == sum(1 for _ in items) == len(training) + len(sealed)
    admitted = seal_corpus(raw)
    print(json.dumps({
        "corpus_path": str(source),
        "corpus_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "item_denominator": len(items),
        "training_items": len(training),
        "sealed_items": len(sealed),
        "complete_pair_denominator": len(training) * len(sealed),
        "literal_reuse_pair_count": len(reused),
        "independent_reverse_pair_count": len(inverse),
        "training_items_reused": len({pair[0] for pair in reused}),
        "sealed_items_with_training_core": len({pair[1] for pair in reused}),
        "real_owner_admitted_corpus": admitted.corpus_id,
        "real_owner_seal": admitted.seal,
        "classification": "NEW class: partition semantics reduced to caller-supplied IDs and exact decorated bytes",
    }, indent=2))
