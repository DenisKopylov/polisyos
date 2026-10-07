#!/usr/bin/env python3
"""Preserve moderate, independently recomputed fresh native CAS readback."""

import hashlib
import json
from pathlib import Path

import numpy as np

from polisyos.core.artifacts import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.scientist.nodes.builtins.simulate import propagate_welfare as module

OUT = Path(__file__).parent
CASE = OUT / "native-basetemp/test_native_ge_preserves_empir0"


def main():
    store = FileSystemCAS(CASE)
    selected = {}
    refs = []
    for path in sorted(CASE.rglob("*.manifest.json")):
        if ".view." in path.name:
            continue
        manifest = json.loads(path.read_text())
        kind = manifest["kind"]
        if kind not in {
            "foundry.welfare_draw_outcomes",
            "ir.uncertainty_envelope",
            "ir.welfare_bundle",
            "ir.welfare_sample_bundle",
            "foundry.welfare_propagation_report",
        }:
            continue
        payload = store.get_bytes(manifest["artifact_id"])
        assert store.verify(manifest["artifact_id"]).ok
        selected[kind] = from_canonical_bytes(payload)
        refs.append(
            {
                "artifact_id": manifest["artifact_id"],
                "kind": kind,
                "schema": manifest["schema"],
                "inputs": manifest["inputs"],
                "payload_bytes": len(payload),
                "payload_sha256": hashlib.sha256(payload).hexdigest(),
                "manifest_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "CAS_integrity": "PASS",
            }
        )
    draw_ref = next(r for r in refs if r["kind"] == "foundry.welfare_draw_outcomes")
    outcome = module._load_welfare_draw_outcomes(
        store,
        module.ArtifactRef.model_validate(
            {
                "artifact_id": draw_ref["artifact_id"],
                "kind": draw_ref["kind"],
                "media_type": "application/json",
            }
        ),
    )
    source = selected["ir.uncertainty_envelope"]["distribution_payload"]
    expected_row = (
        (np.random.default_rng(31415).random(128) >= 0.75).astype(int).tolist()
    )
    actual_row = [row["row_index"] for row in outcome["empirical_rows"]]
    assert actual_row == expected_row
    assert source["samples"] == [0.0, 1.0]
    assert source["weights"] == [3.0, 1.0]
    failed = [
        row["draw_index"] for row in outcome["draw_records"] if row["failed_outputs"]
    ]
    succeeded = [
        row["draw_index"]
        for row in outcome["draw_records"]
        if row["successful_outputs"]
    ]
    assert failed == [i for i, row in enumerate(expected_row) if row == 1]
    assert len(succeeded) == 92 and len(failed) == 36
    assert sorted(failed + succeeded) == list(range(128))
    samples = selected["ir.welfare_sample_bundle"]
    assert samples["welfare_draws"] == [2.0] * 92
    bundle = selected["ir.welfare_bundle"]
    assert bundle["credible_interval"] is None and bundle["robust_interval"] is None
    assert outcome["support_complete"] is False and outcome["gate_eligible"] is False
    result = {
        "schema": "policyos.e02.independent-facade-fresh-CAS-summary.v1",
        "base_sha": "5e3e3727685132f270a3a07b9f63dd962a88cd96",
        "patch_sha256": "ed474d8a61cc5edeff3f195044cd9d095282b72d51b56e1eb0fb74e48ef572b7",
        "case_store": str(CASE),
        "fresh_store_and_actual_reader": True,
        "oracle": {
            "source_atoms": [0, 1],
            "masses": [3, 1],
            "seed": 31415,
            "N": 128,
            "row_rule": "U<.75 ->0, otherwise1",
            "native_welfare": "2/(1-A); A=1 singular",
            "row_indices": expected_row,
        },
        "recomputed_counts": {
            "requested": 128,
            "attempted": len(failed) + len(succeeded),
            "successful": len(succeeded),
            "failed": len(failed),
            "unattempted": 0,
        },
        "failed_ids": failed,
        "all_terminal_ids_preserved": True,
        "conditional_mean": 2.0,
        "unconditional_result": "undefined absent completion rule",
        "credible_interval": bundle["credible_interval"],
        "robust_interval": bundle["robust_interval"],
        "support_complete": outcome["support_complete"],
        "gate_eligible": outcome["gate_eligible"],
        "source_artifact_refs": refs,
        "evidence_scope": "Fresh readback of our actual9PASS native frame; synthetic mathematical input, no production/source-law authority or finding closure",
    }
    (OUT / "native-CAS-deciding.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(result["recomputed_counts"], indent=2))


if __name__ == "__main__":
    main()
