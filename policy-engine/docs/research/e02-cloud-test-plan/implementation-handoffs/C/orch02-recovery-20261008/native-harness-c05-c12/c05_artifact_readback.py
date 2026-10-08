"""Read actual repaired SQL/receipt/report outputs of the one full native run."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import duckdb


def main():
    basetemp = Path(__file__).resolve().parent / "raw/c05-full-native/basetemp"
    cases = sorted(basetemp.glob("test_material_input_change_rec[01]"))
    assert len(cases) == 2
    result = []
    for i, case in enumerate(cases):
        root = case / "snapshot/datasets"
        db = root / "graph/dataset_catalog.duckdb"
        checkpoint_path = root / "manifests/observation_ingest_checkpoint.json"
        stage_path = root / "manifests/stage_state.json"
        report_path = root / "benchmark_report.json"
        checkpoint = json.loads(checkpoint_path.read_text())
        stage = json.loads(stage_path.read_text())["core_sources_ingest"]["metadata"]
        report = json.loads(report_path.read_text())
        with duckdb.connect(str(db), read_only=True) as con:
            rows = con.execute("SELECT dataset_id, raw_variable, country_code, year, value FROM ds_observations WHERE dataset_id = 'wb-gdp'").fetchall()
            evidence = con.execute("SELECT evidence FROM ds_variable_alignments WHERE dataset_id = 'wb-gdp' AND raw_variable = 'NY.GDP.MKTP.CD'").fetchall()
        expected_value = 2.2 if i == 0 else 1.1
        expected_evidence = "seed_worldbank_wdi;source=worldbank" if i == 0 else "seed_worldbank_alt;source=worldbank"
        assert rows == [("wb-gdp", "NY.GDP.MKTP.CD", "UA", 2020, expected_value)]
        assert evidence == [(expected_evidence,)]
        assert checkpoint["core_output_receipt"] == stage["core_output_receipt"]
        assert report["evaluation_mode"] == "full-ready"
        assert report["diagnostic_context"]["core_output_receipt_current"] is True
        assert report["diagnostic_context"]["core_output_receipt_digest"] == checkpoint["core_output_receipt"]["basis_digest"]
        assert {x["status"] for x in checkpoint["completed"].values()} == {"complete_with_rows"}
        result.append({"fixture": str(case), "mutation": "profile_url" if i == 0 else "seed_evidence",
                       "actual_rows": rows, "actual_evidence": evidence,
                       "checkpoint_stage_receipt_equal": True,
                       "receipt_digest": checkpoint["core_output_receipt"]["basis_digest"],
                       "benchmark_mode": report["evaluation_mode"],
                       "benchmark_current": report["diagnostic_context"]["core_output_receipt_current"],
                       "artifact_origins": {str(p): {"bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                                            for p in [db, checkpoint_path, stage_path, report_path]}})
    out = Path(os.environ["ORCH02_OUTPUT_DIR"])
    payload = {"verdict": "PASS_PERSISTED_REPAIRED_OUTPUT_READBACK", "scope": "Independent read-only SQL and cross-artifact observations after the full owned test; no producer rerun or live fixture-profile reconstruction", "cases": result}
    (out / "semantic.json").write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
