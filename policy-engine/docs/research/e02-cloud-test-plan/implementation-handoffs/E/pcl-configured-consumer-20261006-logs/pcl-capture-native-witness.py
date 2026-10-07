"""Capture refs and an independent fresh-pair oracle from existing native tests."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

from polisyos.calibration import load_continuous_evaluation
from polisyos.core.artifacts import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes


test_path = Path(sys.argv[1])
output_path = Path(sys.argv[2])
fixture_root = Path(sys.argv[3])
spec = importlib.util.spec_from_file_location("pcl_native_tests", test_path)
assert spec is not None and spec.loader is not None
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)
original_oracle = native._assert_fresh_source_and_pairs
records = []


def capture(store: FileSystemCAS, ref: ArtifactRef) -> None:
    original_oracle(store, ref)
    fresh = FileSystemCAS(store.root)
    report = load_continuous_evaluation(fresh, ref)
    artifact = from_canonical_bytes(fresh.get_bytes(ref))
    pairs_ref = ArtifactRef.model_validate(artifact["pairs_ref"])
    source_ref = ArtifactRef.model_validate(artifact["source_binding"]["source_data_ref"])
    pairs = from_canonical_bytes(fresh.get_bytes(pairs_ref))
    source = from_canonical_bytes(fresh.get_bytes(source_ref))
    rows = artifact["source_binding"]["evaluated_rows"]
    hits = sum(
        lo <= source["dependent"][row["source_row_index"]] <= hi
        for row, (lo, hi) in zip(rows, pairs["intervals"][0], strict=True)
    )
    records.append(
        {
            "cas_root": str(store.root),
            "diagnostics_ref": ref.model_dump(mode="json"),
            "pairs_ref": pairs_ref.model_dump(mode="json"),
            "source_data_ref": source_ref.model_dump(mode="json"),
            "oracle": "fresh source dependent[source_row_index] vs persisted interval endpoints",
            "manual_hits": hits,
            "requested": report.metadata["interval_coverage"]["requested"],
            "eligible": report.metadata["interval_coverage"]["eligible"],
            "observed": report.metadata["interval_coverage"]["observed"],
            "observed_pairs": report.metadata["interval_coverage"]["observed_pairs"],
            "manual_coverage": hits / len(rows),
            "reopened_coverage": report.curves["interval_coverage"][0].mean_observed,
            "reopened_ece": report.metrics.ece,
            "source_binding": {
                key: value
                for key, value in artifact["source_binding"].items()
                if key not in {"source_data_ref", "evaluated_rows"}
            },
            "first_row": rows[0],
            "last_row": rows[-1],
            "row_binding_sha256": hashlib.sha256(
                json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
            "gate_eligible": artifact["gate_eligible"],
            "source_authority_basis": "not_established",
        }
    )


def reset() -> None:
    native.MethodRegistry.reset_instance()
    native.MethodDispatcher.reset_instance()
    native.CircuitBreakerRegistry.reset_instance()


native._assert_fresh_source_and_pairs = capture
for label, fn in (
    ("real_dispatch", native.test_real_dispatch_reopens_all_three_summary_call_sites),
    ("native_graph", native.test_native_graph_returns_refs_from_its_configured_cas),
):
    reset()
    path = fixture_root / label
    path.mkdir(parents=True, exist_ok=False)
    fn(path)
reset()
native.test_method_without_store_remains_descriptive_and_has_no_persisted_refs()
reset()
output_path.write_text(
    json.dumps(
        {
            "schema": "policyos.e02.pcl.native_witness.v1",
            "fixture": {
                "test_path": str(test_path),
                "test_sha256": hashlib.sha256(test_path.read_bytes()).hexdigest(),
                "distribution": "NumPy default_rng(20261006).normal(scale=0.25, size=140)",
                "rows": 140,
                "entities": 2,
                "time_steps_per_entity": 70,
                "holdout_steps_per_entity": 50,
                "target_id": "synthetic-return",
                "unit": "return",
                "production_history": False,
            },
            "native_checks": 3,
            "source_row_checks": "all 100 ordered rows per artifact checked by tracked native oracle",
            "artifacts": records,
            "missing_store": {"persistence_status": "store_missing", "gate_eligible": False},
        },
        indent=2,
    )
    + "\n"
)
print(json.dumps({"checks": 3, "artifacts": len(records), "output": str(output_path)}))
