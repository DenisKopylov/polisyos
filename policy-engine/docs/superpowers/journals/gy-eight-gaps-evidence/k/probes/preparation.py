"""Read-only K census and red witnesses; never write governed source or output."""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path.cwd()
CONFIG = "architecture/policy_design_case/layer3_gy_openalex_provider_config.json"
GOLD = "architecture/policy_design_case/layer3_gy_openalex_claim_span_gold.json"
ACCURACY = "architecture/policy_design_case/layer3_gy_openalex_accuracy_report.json"
GATE = "tools/quality/validation/check_layer3_gy_openalex_artifacts.py"


def emit(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False), flush=True)


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def population() -> None:
    config = json.loads((ROOT / CONFIG).read_text())
    gold = json.loads((ROOT / GOLD).read_text())
    paths = config["provenance"]["recorded_response_fixtures"]
    fixtures = {path: json.loads((ROOT / path).read_text()) for path in paths}
    results = {
        path: [row["id"] for row in payload["results"]]
        for path, payload in fixtures.items()
    }
    selected = sorted({(row["source_fixture"], row["openalex_id"]) for row in gold["records"]})
    full = sorted((path, identity) for path, identities in results.items() for identity in identities)
    cross = json.loads(subprocess.check_output([
        "node", "-e",
        "const fs=require('fs');const c=JSON.parse(fs.readFileSync(process.argv[1]));"
        "const g=JSON.parse(fs.readFileSync(process.argv[2]));"
        "const out={fixtures:{},selected:[],gold_ids:g.records.map(r=>r.label_id)};"
        "for(const p of c.provenance.recorded_response_fixtures){"
        "const d=JSON.parse(fs.readFileSync(p));out.fixtures[p]=d.results.map(r=>r.id);}"
        "out.selected=[...new Set(g.records.map(r=>JSON.stringify([r.source_fixture,r.openalex_id])))]"
        ".map(JSON.parse).sort();process.stdout.write(JSON.stringify(out));",
        CONFIG, GOLD,
    ], text=True))
    assert results == cross["fixtures"]
    assert [list(row) for row in selected] == cross["selected"]
    assert [row["label_id"] for row in gold["records"]] == cross["gold_ids"]
    assert len(full) == sum(len(payload["results"]) for payload in fixtures.values())
    assert len(set(full)) == len(full), "duplicate work identity within configured source"
    assert set(selected) <= set(full), "gold source identity missing from configured population"
    tree = ast.parse((ROOT / GATE).read_text())
    held_out = next(
        ast.literal_eval(node.value) for node in tree.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name) and node.target.id == "HELD_OUT_ACCURACY_CASES"
    )
    report = json.loads((ROOT / ACCURACY).read_text())
    declared_case_ids = {row["label_id"] for row in gold["records"]} | {
        row["label_id"] for row in held_out
    }
    actual_case_ids = {row["label_id"] for row in report["case_judgments"]}
    assert declared_case_ids == actual_case_ids
    paths_read = [CONFIG, GOLD, ACCURACY, GATE, *paths]
    emit({
        "scope": "complete configured recorded response population; no accuracy claim",
        "source_refs": {
            path: {"git_blob": subprocess.check_output(["git", "hash-object", path], text=True).strip()}
            for path in paths_read
        },
        "independent_json_parsers_identity_sets_equal": True,
        "configured_fixture_json_denominator": len(paths),
        "result_rows_by_fixture": {path: len(rows) for path, rows in results.items()},
        "complete_configured_work_identities": full,
        "complete_configured_work_denominator": len(full),
        "current_gold_selected_work_identities": selected,
        "configured_works_omitted_by_current_gold_selection": sorted(set(full) - set(selected)),
        "gold_record_denominator": len(gold["records"]),
        "declared_held_out_case_denominator": len(held_out),
        "complete_accuracy_case_identity_set_reconciled": sorted(actual_case_ids),
        "recorded_stratum_dates": {
            path: payload["_recording"]["captured_at"] for path, payload in fixtures.items()
        },
        "positive_accuracy": "withheld; correspondence-acceptance-standing-rule appointment absent",
    })


def report_content() -> None:
    from tools.quality.validation import check_layer3_gy_openalex_artifacts as gate

    payload = json.loads((ROOT / ACCURACY).read_text())
    baseline: list[dict[str, str]] = []
    gate.validate_accuracy_report_payload(payload, expected=payload, issues=baseline)
    corrupted = copy.deepcopy(payload)
    changed = []
    for row in corrupted["case_judgments"]:
        changed.append(row["label_id"])
        row["claim_text"] = "A wholly fabricated claim with no source content."
        row["span_text"] = "This span does not exist in the declared source."
        row["agent_judgment"] = {"model_id": payload["accuracy_provenance"]["model_id"]}
    issues: list[dict[str, str]] = []
    gate.validate_accuracy_report_payload(corrupted, expected=payload, issues=issues)
    emit({
        "property": "actual current checker refuses fabricated substantive claim/span/judgment",
        "source_ref": ACCURACY,
        "complete_mutated_case_identity_set": sorted(changed),
        "numerical_accuracy": "not recomputed or claimed; prior recorded fields unchanged",
        "baseline_issues": baseline,
        "mutant_issues": issues,
    })
    assert baseline == [], baseline
    assert issues, "fabricated substantive content accepted while all accuracy/provenance markers remain"


def extractor_removal() -> None:
    from polisyos.ir.analytics import literature
    from tools.quality.validation import check_layer3_gy_openalex_artifacts as gate

    gold = literature.ClaimSpanGoldSet.model_validate_json((ROOT / GOLD).read_text())
    client = gate.DeterministicSpanSupportClient()
    original = literature.extract_span_grounded_claims_from_openalex_work
    baseline_calls: list[tuple[str, str]] = []
    removed_calls: list[tuple[str, str]] = []

    def tracked(work, *, query, **kwargs):
        baseline_calls.append((work.openalex_id, query))
        return original(work, query=query, **kwargs)

    def removed(work, *, query, **kwargs):
        removed_calls.append((work.openalex_id, query))
        return []

    try:
        literature.extract_span_grounded_claims_from_openalex_work = tracked
        baseline = literature.evaluate_openalex_claim_extractor_accuracy(gold, span_support_client=client)
        literature.extract_span_grounded_claims_from_openalex_work = removed
        mutant = literature.evaluate_openalex_claim_extractor_accuracy(gold, span_support_client=client)
    finally:
        literature.extract_span_grounded_claims_from_openalex_work = original
    emit({
        "property": "default instrument consults actual extractor; removal changes its evidence",
        "source_ref": GOLD,
        "baseline_extractor_calls": baseline_calls,
        "removed_extractor_calls": removed_calls,
        "complete_report_same": baseline == mutant,
        "report_delta_hashes": [digest(baseline.model_dump(mode="json")), digest(mutant.model_dump(mode="json"))],
        "rate_authority": "none: controlled offline client is an engineering witness; no positive rate reported",
    })
    assert baseline_calls and removed_calls and baseline != mutant, "default instrument bypasses extractor"


def ingestion() -> None:
    from tools.quality.validation import check_layer3_gy_openalex_artifacts as gate

    payload = gate.build_live_payloads(ROOT)[gate.INGEST_PATH]
    rows = payload["ingest"]["witness_records"]
    gold = json.loads((ROOT / GOLD).read_text())["records"]
    declared_by_work = {}
    for row in gold:
        declared_by_work.setdefault((row["query"], row["source_fixture"], row["openalex_id"]), row["label_id"])
    assert {row["label_id"] for row in rows} == set(declared_by_work.values())
    assert len(rows) == len(declared_by_work)
    expected = {(row["query"], row["source_fixture"]) for row in gold}
    actual = {(row["query"], row["fixture"]) for row in rows}
    assert actual == expected, (actual, expected)
    fixture_path = "tests/fixtures/scholar/openalex/credit_guarantee_firm_survival.json"
    query = json.loads((ROOT / fixture_path).read_text())["_recording"]["query"]
    selected = [row for row in rows if row["query"] == query and row["fixture"] == fixture_path]
    independent_selected = [key for key in declared_by_work if key[:2] == (query, fixture_path)]
    assert len(selected) == len(independent_selected)
    emit({
        "property": "actual canonical credit-guarantee query inserts source-bound candidate claims",
        "complete_live_witnesses": rows,
        "complete_query_fixture_identities": sorted(actual),
        "independent_gold_query_fixture_identities": sorted(expected),
        "selected_canonical_query": query,
        "selected_witness_denominator": len(selected),
        "independent_selected_work_identities": independent_selected,
        "positive_accuracy": "withheld; no accuracy value computed or reported by this probe",
    })
    assert selected and any(row["ingested_claim_count"] > 0 for row in selected), "canonical credit-guarantee query ingests no claims"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["population", "report-content", "extractor-removal", "ingestion"])
    mode = parser.parse_args().mode
    {"population": population, "report-content": report_content, "extractor-removal": extractor_removal, "ingestion": ingestion}[mode]()


if __name__ == "__main__":
    main()
