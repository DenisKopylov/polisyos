"""Recompute an E02 organization proposal from its complete pinned sources.

This checks assignment coverage and declared path conflicts, not product behavior.
Run from any checkout containing the pinned Git objects. The original DOCX is
required to independently reconcile its 48 analytical packages.
"""

from __future__ import annotations

import argparse
import copy
import csv
import fnmatch
import hashlib
import itertools
import json
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter, defaultdict
from pathlib import Path


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def git_text(root: Path, cut: str, path: str) -> str:
    return git_read(root, "show", f"{cut}:{path}")


def git_read(root: Path, *arguments: str) -> str:
    executable = shutil.which("git")
    require(executable is not None, "Git executable missing")
    # Internal read-only Git commands, argument vector, no shell evaluation.
    return subprocess.check_output(  # noqa: S603
        [executable, *arguments], cwd=root, text=True, shell=False
    )


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream, delimiter="\t"))


def assignment_for(bundles: list[dict], prefixes: dict[str, list[str]]) -> dict:
    assigned = {}
    for bundle in bundles:
        prefix = bundle["id"].split("-")[0]
        owners = [unit for unit, values in prefixes.items() if prefix in values]
        require(len(owners) == 1, f"ambiguous/unassigned bundle {bundle['id']}")
        assigned[bundle["id"]] = owners[0]
    return assigned


def writer_families(assignment: dict, graph: dict) -> dict:
    adjacency = {b: set() for b in assignment}
    for pair in graph["write_conflicts"]:
        a, b = pair["a"], pair["b"]
        if assignment[a] == assignment[b]:
            adjacency[a].add(b)
            adjacency[b].add(a)
    result = {}
    for unit in sorted(set(assignment.values())):
        count = 0
        for bundle in sorted(b for b, u in assignment.items() if u == unit):
            if bundle in result:
                continue
            count += 1
            pending = [bundle]
            result[bundle] = f"{unit}-W{count:02d}"
            while pending:
                item = pending.pop()
                for other in sorted(adjacency[item]):
                    if other not in result:
                        result[other] = f"{unit}-W{count:02d}"
                        pending.append(other)
    return result


def docx_packages(path: Path, expected_hash: str) -> dict[str, str]:
    require(hashlib.sha256(path.read_bytes()).hexdigest() == expected_hash, "DOCX hash drift")
    with zipfile.ZipFile(path) as archive:
        # Parse only the exact hash-pinned source document, never arbitrary XML.
        document = ET.fromstring(archive.read("word/document.xml"))  # noqa: S314
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    candidates = []
    for table in document.findall(".//w:body/w:tbl", ns):
        rows = [
            ["".join(cell.itertext()) for cell in row.findall("w:tc", ns)]
            for row in table.findall("w:tr", ns)
        ]
        if len(rows) > 1 and all(re.match(r"^P\d{2}\s", row[0]) for row in rows[1:]):
            candidates.append(rows)
    require(len(candidates) == 1, "unique complete P table not established")
    rows = candidates[0]
    require(len(rows) - 1 == 48, "DOCX P-package denominator drift")
    output = {}
    packages = set()
    for row in rows[1:]:
        package = row[0][:3]
        require(package not in packages, f"duplicate DOCX package {package}")
        packages.add(package)
        require("IDs:" in row[1], f"IDs missing in {package}")
        text = row[1].split("IDs:", 1)[1].split(";", 1)[0]
        tokens = re.findall(r"(B\d+|LA-\d+)(?:\s*[–—]\s*(B\d+|LA-\d+))?", text)
        require(bool(tokens), f"finding basis missing in {package}")
        for start, end in tokens:
            kind = "LA" if start.startswith("LA-") else "B"
            first = int(start.split("-")[-1] if kind == "LA" else start[1:])
            last = int(end.split("-")[-1] if kind == "LA" else end[1:]) if end else first
            require(not end or (end.startswith("LA-") == (kind == "LA")), "mixed ID range")
            require(last >= first, "descending ID range")
            for number in range(first, last + 1):
                finding = f"LA-{number:03d}" if kind == "LA" else f"B{number:02d}"
                require(finding not in output, f"duplicate DOCX finding {finding}")
                output[finding] = package
    return output


def expanded_paths(bundles: list[dict], tree: set[str]) -> tuple[dict, list[str]]:
    by_bundle = {}
    missing = set()
    for bundle in bundles:
        paths = set()
        for declared in bundle["write_paths"]:
            if any(char in declared for char in "*?["):
                matches = {p for p in tree if fnmatch.fnmatchcase(p, declared)}
            elif declared in tree:
                matches = {declared}
            else:
                matches = {p for p in tree if p.startswith(declared.rstrip("/") + "/")}
                if not matches:
                    missing.add(declared)
            paths.update(matches)
        by_bundle[bundle["id"]] = paths
    return by_bundle, sorted(missing)


def validate(
    config: dict,
    bundle_rows: list[dict],
    finding_rows: list[dict],
    manifest: dict,
    ledger: dict,
    graph: dict,
    path_sets: dict,
    p_by_id: dict,
) -> dict:
    prefixes = {u["id"]: u["bundle_prefixes"] for u in config["units"] if u["id"] != "G"}
    require(set(prefixes) == set("ABCDEF"), "six subject units required")
    require(
        Counter(u["id"] for u in config["units"]) == Counter("ABCDEFG"), "unit uniqueness drift"
    )
    require(sum(config["subject_unit_leaf_role_capacity"].values()) == 20, "leaf role sum drift")
    assignment = assignment_for(manifest["bundles"], prefixes)
    expected_ids = set(assignment)
    require(len(bundle_rows) == len(expected_ids), "bundle denominator mismatch")
    require({r["bundle_id"] for r in bundle_rows} == expected_ids, "bundle set mismatch")
    require(len({r["bundle_id"] for r in bundle_rows}) == len(bundle_rows), "duplicate bundle")
    families = writer_families(assignment, graph)
    for row in bundle_rows:
        require(
            row["unit"] == assignment[row["bundle_id"]], f"wrong bundle unit {row['bundle_id']}"
        )
        require(row["initial_writer_family"] == families[row["bundle_id"]], "writer family drift")

    residuals = {r["id"]: r for r in ledger["rows"]}
    require(len(residuals) == ledger["denominator"]["unique"], "source ledger duplicates")
    require(len(finding_rows) == ledger["denominator"]["total"], "finding denominator mismatch")
    require(len({r["finding_id"] for r in finding_rows}) == len(finding_rows), "duplicate finding")
    require({r["finding_id"] for r in finding_rows} == set(residuals), "finding set mismatch")
    require(set(p_by_id) == set(residuals), "DOCX/ledger complete set mismatch")
    require(
        dict(Counter(r["status"] for r in ledger["rows"])) == ledger["status_counts"],
        "source status count mismatch",
    )
    for row in finding_rows:
        source = residuals[row["finding_id"]]
        owner = source["closure_owner"]
        unit = assignment.get(
            owner, config["closure_owner_exceptions"].get(source["id"], {}).get("unit")
        )
        require(unit is not None and row["unit"] == unit, f"wrong finding unit {source['id']}")
        require(row["source_status"] == source["status"], f"status promotion {source['id']}")
        require(row["source_closure_owner"] == owner, "source closure owner drift")
        require(
            row["source_bundle_ids"] == ",".join(source["bundle_ids"]), "source bundle map drift"
        )
        require(row["docx_analytical_package"] == p_by_id[source["id"]], "DOCX package drift")

    path_owners = defaultdict(set)
    for bundle, paths in path_sets.items():
        for path in paths:
            path_owners[path].add(assignment[bundle])
    cross_paths = {path: units for path, units in path_owners.items() if len(units) > 1}
    publishers = config["cross_unit_single_publishers"]
    require(len({r["path"] for r in publishers}) == len(publishers), "multiple path publishers")
    require(
        {r["path"] for r in publishers} == set(cross_paths),
        "cross-unit publisher coverage mismatch",
    )
    for publisher in publishers:
        require(
            publisher["publisher"] in cross_paths[publisher["path"]],
            "publisher has no declared mechanism",
        )
        require(
            set(publisher["foreign_supplier_units"])
            == cross_paths[publisher["path"]] - {publisher["publisher"]},
            "supplier set drift",
        )
    return assignment


def partition_counts(assignment: dict, graph: dict, path_sets: dict) -> dict:
    actual_pairs = [
        (a, b)
        for a, b in itertools.combinations(sorted(path_sets), 2)
        if path_sets[a] & path_sets[b]
    ]
    return {
        "subject_units": len(set(assignment.values())),
        "cross_write_pairs": sum(assignment[a] != assignment[b] for a, b in actual_pairs),
        "cross_implementation_edges": sum(
            assignment[e["from"]] != assignment[e["to"]] for e in graph["edges"]
        ),
        "cross_read_contract_impacts": sum(
            assignment[e["producer"]] != assignment[e["consumer"]]
            for e in graph["read_contract_impacts"]
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docx", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    directory = Path(__file__).resolve().parent
    root = Path(git_read(directory, "rev-parse", "--show-toplevel").strip())
    config = json.loads((directory / "allocation.json").read_text())
    cut, package = config["source_cut"], config["source_package_root"]
    require(re.fullmatch(r"[0-9a-f]{40}", cut) is not None, "source must be a full commit SHA")
    manifest_path, graph_path = (
        f"{package}/bundle_manifest.json",
        f"{package}/dependency_graph.json",
    )
    manifest = json.loads(git_text(root, cut, manifest_path))
    graph = json.loads(git_text(root, cut, graph_path))
    ledger = json.loads(git_text(root, cut, config["residual_ledger_path"]))
    tree = set(git_read(root, "ls-tree", "-r", "--name-only", cut).splitlines())
    paths, missing = expanded_paths(manifest["bundles"], tree)
    bundles = read_rows(directory / "bundle-owners.tsv")
    findings = read_rows(directory / "finding-owners.tsv")
    p_by_id = docx_packages(
        args.docx or Path(config["source_document"]["path"]), config["source_document"]["sha256"]
    )
    assignment = validate(config, bundles, findings, manifest, ledger, graph, paths, p_by_id)
    require(len(bundles) == manifest["counts"]["bundles"], "manifest count mismatch")
    require(
        len(findings) == manifest["counts"]["source_records_B_plus_LA"],
        "manifest/ledger total mismatch",
    )
    present_pairs = {
        tuple(sorted((a, b))) for a, b in itertools.combinations(paths, 2) if paths[a] & paths[b]
    }
    declared_pairs = {tuple(sorted((e["a"], e["b"]))) for e in graph["write_conflicts"]}
    require(present_pairs == declared_pairs, "present-tree/declared pair mismatch")
    require(
        len(present_pairs) == manifest["counts"]["write_conflict_pairs"], "write count mismatch"
    )
    require(
        len(graph["edges"]) == manifest["counts"]["implementation_edges"],
        "implementation count mismatch",
    )
    require(
        len(graph["read_contract_impacts"]) == manifest["counts"]["read_contract_impact_edges"],
        "read-contract count mismatch",
    )

    corruptions = []
    cases = []
    cases.append(("missing_bundle", config, bundles[1:], findings))
    cases.append(("duplicate_finding", config, bundles, [*findings, findings[0]]))
    wrong = copy.deepcopy(findings)
    wrong[0]["unit"] = "B" if wrong[0]["unit"] != "B" else "A"
    cases.append(("wrong_finding_unit", config, bundles, wrong))
    wrong = copy.deepcopy(findings)
    wrong[0]["source_status"] = "closed"
    cases.append(("source_status_promotion", config, bundles, wrong))
    wrong = copy.deepcopy(config)
    wrong["cross_unit_single_publishers"].append(
        copy.deepcopy(wrong["cross_unit_single_publishers"][0])
    )
    cases.append(("duplicate_shared_publisher", wrong, bundles, findings))
    wrong = copy.deepcopy(config)
    wrong["cross_unit_single_publishers"].pop()
    cases.append(("uncovered_cross_unit_path", wrong, bundles, findings))
    wrong = copy.deepcopy(findings)
    wrong[0]["docx_analytical_package"] = "P99"
    cases.append(("wrong_docx_package", config, bundles, wrong))
    for name, cfg, b_rows, f_rows in cases:
        try:
            validate(cfg, b_rows, f_rows, manifest, ledger, graph, paths, p_by_id)
        except ValueError as error:
            corruptions.append({"case": name, "verdict": "REJECTED", "reason": str(error)})
        else:
            raise ValueError(f"corruption accepted: {name}")

    partitions = {"six": partition_counts(assignment, graph, paths)}
    for name, prefixes in config["comparison_subject_partitions"].items():
        partitions[name] = partition_counts(
            assignment_for(manifest["bundles"], prefixes), graph, paths
        )
    report = {
        "schema": "policyos.e02.execution_organization.verification.v1",
        "verdict": "PASS_ASSIGNMENT_CENSUS_ONLY",
        "source_cut": cut,
        "inputs": [
            f"{p}@{cut}" for p in [manifest_path, graph_path, config["residual_ledger_path"]]
        ],
        "denominator": {
            "bundle_json_objects": len(bundles),
            "ledger_json_rows": len(findings),
            "docx_P_table_packages": len(set(p_by_id.values())),
            "docx_P_table_unique_finding_ids": len(p_by_id),
            "tracked_git_paths_all_file_types": len(tree),
            "declared_write_path_entries": sum(len(b["write_paths"]) for b in manifest["bundles"]),
            "declared_unique_write_paths": len(
                {p for b in manifest["bundles"] for p in b["write_paths"]}
            ),
        },
        "source_status_counts_preserved": dict(Counter(r["source_status"] for r in findings)),
        "bundle_counts_by_unit": dict(sorted(Counter(assignment.values()).items())),
        "finding_counts_by_unit": dict(sorted(Counter(r["unit"] for r in findings).items())),
        "full_graph": {
            "implementation_edges": len(graph["edges"]),
            "write_conflict_pairs": len(present_pairs),
            "read_contract_impacts": len(graph["read_contract_impacts"]),
        },
        "partition_comparison": partitions,
        "missing_literal_write_paths": missing,
        "corrupt_assignment_probes": corruptions,
        "local_artifact_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [
                directory / "allocation.json",
                directory / "bundle-owners.tsv",
                directory / "finding-owners.tsv",
                Path(__file__).resolve(),
            ]
        },
        "claim_limits": [
            "No product tests, performance benchmarks or cloud execution performed.",
            "Coverage validates proposal bookkeeping and declared-path ownership only; "
            "it does not establish capability closure or optimal throughput.",
        ],
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered)
    sys.stdout.write(rendered)


if __name__ == "__main__":
    main()
