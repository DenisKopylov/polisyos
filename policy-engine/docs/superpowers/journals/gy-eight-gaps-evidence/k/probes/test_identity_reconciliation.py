"""Reconcile full native K test identities without substituting totals for findings."""
from __future__ import annotations

import ast
import argparse
import hashlib
import itertools
import json
import re
from pathlib import Path

ROOT = Path.cwd()
FILES = (
    "tests/unit/ir/test_literature_openalex_grounding.py",
    "tests/unit/data_forge/domains/academic/knowledge/test_openalex_skg_ingest.py",
    "tests/unit/scholar/search/test_openalex_provider.py",
    "tests/repo_quality/tools/test_layer3_gy_openalex_artifacts.py",
)
PENDING_CANONICAL = {
    FILES[-1] + "::test_layer3_gy_openalex_artifacts_recompute_from_recorded_real_sources",
    FILES[-1] + "::test_layer3_gy_openalex_artifacts_corrupt_accuracy_drift_fails",
}


def statuses(receipt):
    pairs = []
    for line in (receipt["stdout"] + receipt["stderr"]).splitlines():
        match = re.fullmatch(r"(PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS) (tests/.*)", line)
        if match:
            pairs.append((match[2], match[1]))
    assert len(dict(pairs)) == len(pairs)
    return dict(pairs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--final", action="store_true")
    args = parser.parse_args()
    expected = set()
    denominator = []
    for relative in FILES:
        raw = (ROOT / relative).read_bytes()
        tree = ast.parse(raw)
        definitions = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                       and node.name.startswith("test_")]
        independent = re.findall(r"^(?:async )?def (test_\w+)\(", raw.decode(), re.MULTILINE)
        assert {node.name for node in definitions} == set(independent)
        assert len(definitions) == len(independent)
        before = len(expected)
        for node in definitions:
            base = relative + "::" + node.name
            dimensions = []
            for decorator in node.decorator_list:
                if not (isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute)
                        and decorator.func.attr == "parametrize"):
                    continue
                names = ast.literal_eval(decorator.args[0])
                names = names.split(",") if isinstance(names, str) else list(names)
                values = ast.literal_eval(decorator.args[1])
                assert not any(keyword.arg == "ids" for keyword in decorator.keywords)
                ids = []
                for index, value in enumerate(values):
                    row = [value] if len(names) == 1 else value
                    assert len(row) == len(names)
                    ids.append("-".join(str(item) if item is None or isinstance(item, (str, int, float, bool))
                                        else name + str(index) for name, item in zip(names, row, strict=True)))
                dimensions.append(ids)
            expected.update(base + "[" + "-".join(items) + "]" for items in itertools.product(*dimensions)) if dimensions else expected.add(base)
        denominator.append({"path": relative, "sha256": hashlib.sha256(raw).hexdigest(),
                            "ast_functions": len(definitions), "independent_definitions": len(independent),
                            "expanded_cases": len(expected) - before})
    observed = {}
    receipt_refs = []
    names = ["owner-final-green.json", "source-context-green.json"]
    if args.final:
        names.append("corrupt-status-green.json")
    for name in names:
        path = ROOT / "_build/gy-gaps/k" / name
        report = json.loads(path.read_text())
        assert report["returncode"] == 0 and not report["timed_out"]
        current = statuses(report)
        assert current and all(status == "PASSED" for status in current.values())
        for identity, status in current.items():
            assert identity not in observed or observed[identity] == status
            observed[identity] = status
        receipt_refs.append({"path": str(path.relative_to(ROOT)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    pending = set() if args.final else PENDING_CANONICAL
    assert expected - pending == set(observed)
    initial = statuses(json.loads((ROOT / "_build/gy-gaps/k/owner-tests-first-green.json").read_text()))
    importer = "tests/integration/scholar_scientist/test_extraction_strength_vocabulary.py::test_claim_axes_round_trip_through_activated_writer_and_all_public_readers"
    assert initial[importer] == "FAILED"
    lost = set(initial) - set(observed)
    assert lost == {importer}
    removal_deltas = []
    for name in ("source-verifier", "stored-content", "default-extractor"):
        path = ROOT / f"_build/gy-gaps/k/removal-{name}.json"
        report = json.loads(path.read_text())
        assert report["returncode"] == 1 and not report["timed_out"]
        failed = statuses(report)
        assert len(failed) == 1 and set(failed.values()) == {"FAILED"}
        assert set(failed) <= set(observed)
        removal_deltas.append({"receipt": str(path.relative_to(ROOT)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                               "baseline_pass_to_removed_fail": sorted(failed), "lost_selected_case_identities": []})
    print(json.dumps({"complete_python_file_denominator": len(FILES), "files": denominator,
                      "complete_expanded_case_count": len(expected), "checked_case_union_count": len(observed),
                      "pending_parent_canonical": sorted(pending), "missing": [], "unexpected": [],
                      "receipt_refs": receipt_refs, "first_wave_added_cases": sorted(set(observed) - set(initial)),
                      "separately_retained_importer_failure": sorted(lost), "importer_attribution": "not_established",
                      "removal_identity_deltas": removal_deltas}, sort_keys=True))


if __name__ == "__main__":
    main()
