"""Reconcile E02 planning coverage with pinned Git sources, not product behavior."""

from __future__ import annotations

import argparse
import collections
import copy
import csv
import hashlib
import io
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

GIT = shutil.which("git")
if GIT is None:
    raise RuntimeError("git executable is unavailable")


def git_bytes(root: Path, spec: str) -> bytes:
    """Read one immutable Git object without using the working source tree."""
    require(bool(re.fullmatch(r"[0-9a-f]{40}:[^\x00\n]+", spec)), "invalid immutable source")
    return subprocess.check_output([GIT, "show", spec], cwd=root)  # noqa: S603


def require(condition: bool, message: str) -> None:
    """Reject an accounting mismatch with a readable diagnostic."""
    if not condition:
        raise ValueError(message)


def validate(data: dict[str, Any], directory: Path, root: Path) -> dict[str, Any]:
    """Check exact sets, ownership, source blocks and document task anchors."""
    sha = data["runtime_source"]
    org = "policy-engine/docs/research/e02-cloud-test-plan/execution-organization/"
    package = "policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/"

    def rows(path: str) -> list[dict[str, str]]:
        return list(
            csv.DictReader(io.StringIO(git_bytes(root, sha + ":" + path).decode()), delimiter="\t")
        )

    owners = {r["finding_id"]: r for r in rows(org + "finding-owners.tsv")}
    writers = {r["bundle_id"]: r for r in rows(org + "bundle-owners.tsv")}
    manifest = json.loads(git_bytes(root, sha + ":" + package + "bundle_manifest.json"))
    bundles = {r["id"]: r for r in manifest["bundles"]}
    ledger = json.loads(
        git_bytes(
            root,
            sha
            + ":policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/residual_ledger.json",
        )
    )
    statuses = {r["id"]: r for r in ledger["rows"]}
    indexes = {
        "B_r19": json.loads(git_bytes(root, sha + ":" + package + "source/card_index.json")),
        "LA_r09": json.loads(
            git_bytes(root, sha + ":" + package + "source/legacy_card_index.json")
        ),
    }
    actual_ids = [r["id"] for r in data["findings"]]
    actual_bundles = [r["id"] for r in data["bundles"]]
    require(
        len(actual_ids) == len(set(actual_ids)) and set(actual_ids) == set(owners) == set(statuses),
        "finding ID set or uniqueness differs from complete owners/ledger",
    )
    require(
        len(actual_bundles) == len(set(actual_bundles))
        and set(actual_bundles) == set(writers) == set(bundles),
        "bundle ID set or uniqueness differs from complete manifest/owners",
    )
    docs: dict[str, str] = {}

    def check_refs(refs: list[str]) -> None:
        require(bool(refs), "missing task references")
        for ref in refs:
            name, separator, anchor = ref.partition("#")
            require(name in {unit + ".md" for unit in "ABCDEF"}, "unexpected task file: " + name)
            if name not in docs:
                docs[name] = (directory / name).read_text()
            if separator:
                require(
                    docs[name].count('<a id="' + anchor + '"></a>') == 1,
                    "task anchor missing or ambiguous: " + ref,
                )

    for row in data["bundles"]:
        writer = writers[row["id"]]
        require(
            row["unit"] == writer["unit"] and row["writer"] == writer["initial_writer_family"],
            "bundle writer changed: " + row["id"],
        )
        expected_members = set(bundles[row["id"]]["findings"]) | set(
            bundles[row["id"]].get("legacy_cards", [])
        )
        require(
            set(row["finding_ids"]) == expected_members,
            "bundle finding membership differs: " + row["id"],
        )
        check_refs(row["task_refs"])
    source_lines: dict[str, list[str]] = {}
    for key, source in data["criterion_documents"].items():
        spec = sha + ":" + source["path"]
        blob = subprocess.check_output([GIT, "rev-parse", spec], cwd=root).decode().strip()  # noqa: S603
        require(blob == source["blob"], "criterion source blob differs: " + key)
        source_lines[key] = git_bytes(root, spec).decode().splitlines(keepends=True)
    source_occurrences = 0
    incidence = 0
    for row in data["findings"]:
        fid = row["id"]
        owner = owners[fid]
        expected_cards = set(re.split(r"[;, ]+", owner["source_bundle_ids"])) - {""}
        literal_owner = owner["source_closure_owner"]
        require(
            row["unit"] == owner["unit"] and row["source_closure_owner_literal"] == literal_owner,
            "finding owner differs: " + fid,
        )
        expected_primary = (
            literal_owner
            if literal_owner in bundles
            else next(iter(expected_cards))
            if len(expected_cards) == 1
            else None
        )
        require(row["primary_bundle"] == expected_primary, "primary routing differs: " + fid)
        require(
            set(row["companion_bundles"]) == expected_cards, "finding companions differ: " + fid
        )
        require(
            row["ledger_status_historical"] == statuses[fid]["status"],
            "historical ledger status differs: " + fid,
        )
        require(
            row["appendix_c_status_separate"] == statuses[fid]["appendix_c_status"],
            "Appendix C status differs: " + fid,
        )
        require(row["closure_now"] == "not_adjudicated", "planning index changed closure: " + fid)
        check_refs(row["task_refs"])
        refs = row["criterion_refs"]
        require(
            len(refs) == len(expected_cards) and {r["card"] for r in refs} == expected_cards,
            "criterion/card occurrence set differs: " + fid,
        )
        incidence += len(expected_cards)
        for ref in refs:
            require(ref["criterion_id"] == fid, "criterion identity differs: " + fid)
            index = indexes[ref["document"]][fid]
            require(
                ref["lines"] == [index["start_line"], index["end_line"]]
                and ref["sha256"] == index["sha256"],
                "criterion locator differs from canonical index: " + fid,
            )
            start, end = ref["lines"]
            actual = hashlib.sha256(
                "".join(source_lines[ref["document"]][start - 1 : end]).encode()
            ).hexdigest()
            require(actual == ref["sha256"], "criterion bytes differ: " + fid)
            source_occurrences += 1
        if row["unit"] == "C":
            plan = row["selected_plan_not_executed"]
            require(
                all(
                    plan.get(key)
                    for key in ("paths", "dependency", "positive", "oracle", "negative", "command")
                ),
                "C selected plan incomplete: " + fid,
            )
            require(
                plan["command"] in data["C_shared_commands_not_executed"],
                "C command group missing: " + fid,
            )
    expected_denominator = {
        "bundles": len(bundles),
        "findings": len(owners),
        "canonical_source_block_occurrences": incidence,
    }
    require(
        data["denominator"] == expected_denominator and source_occurrences == incidence,
        "denominator differs",
    )
    require(
        data["historical_ledger_counts"]
        == dict(collections.Counter(r["status"] for r in statuses.values())),
        "status count differs",
    )
    graph = json.loads(git_bytes(root, sha + ":" + package + "dependency_graph.json"))

    def unit_of(bundle: str) -> str:
        return writers[bundle]["unit"]

    implementation = [edge for edge in graph["edges"] if edge["kind"] == "implementation"]
    cross = sum(unit_of(e["from"]) != unit_of(e["to"]) for e in implementation)
    mutex_cross = sum(unit_of(e["a"]) != unit_of(e["b"]) for e in graph["write_conflicts"])
    read_cross = sum(
        unit_of(e["producer"]) != unit_of(e["consumer"]) for e in graph["read_contract_impacts"]
    )
    expected_dependencies = {
        "implementation": len(implementation),
        "cross_unit_implementation": cross,
        "same_unit_implementation": len(implementation) - cross,
        "mutex": len(graph["write_conflicts"]),
        "cross_unit_mutex": mutex_cross,
        "read_impacts": len(graph["read_contract_impacts"]),
        "cross_unit_read_impacts": read_cross,
    }
    require(data["dependency_counts"] == expected_dependencies, "dependency count differs")
    identity = json.loads((directory / "input-identity.json").read_text())
    require(identity["runtime_source"] == sha, "identity/runtime pin differs")
    for source in identity["sources"]:
        content = git_bytes(root, source["commit_sha"] + ":" + source["path"])
        require(
            hashlib.sha256(content).hexdigest() == source["sha256"],
            "input source digest differs: " + source["path"],
        )
    return {
        "scope": "planning bookkeeping only; not semantic proof",
        **expected_denominator,
        "task_files": len(docs),
        "dependencies": expected_dependencies,
    }


def main() -> None:
    """Validate the planning pack, optionally testing count-preserving corruption."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coverage", type=Path, default=Path(__file__).with_name("coverage.json"))
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    directory = Path(__file__).resolve().parent
    root = Path(
        subprocess.check_output([GIT, "rev-parse", "--show-toplevel"], cwd=directory)  # noqa: S603
        .decode()
        .strip()
    )
    data = json.loads(args.coverage.read_text())
    report = validate(data, directory, root)
    if args.self_check:
        for mutation in ("foreign_id", "duplicate_id", "wrong_criterion_hash", "wrong_task_anchor"):
            altered = copy.deepcopy(data)
            if mutation == "foreign_id":
                altered["findings"][0]["id"] = "FOREIGN-999"
            elif mutation == "duplicate_id":
                altered["findings"][0]["id"] = altered["findings"][1]["id"]
            elif mutation == "wrong_criterion_hash":
                altered["findings"][0]["criterion_refs"][0]["sha256"] = "0" * 64
            else:
                altered["findings"][0]["task_refs"] = ["A.md#absent-task"]
            try:
                validate(altered, directory, root)
            except (ValueError, KeyError):
                continue
            raise ValueError("mutation accepted: " + mutation)
        report["count_preserving_controls_rejected"] = 4
    print(json.dumps(report, ensure_ascii=False, indent=2))  # noqa: T201


if __name__ == "__main__":
    main()
