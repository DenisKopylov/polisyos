#!/usr/bin/env python3
"""Recompute all54 denominator/owners/source bindings; no mutable source edits."""

import argparse
import collections
import copy
import csv
import hashlib
import io
import json
import pathlib
import subprocess

HERE = pathlib.Path(__file__).resolve().parent
E02 = "policy-engine/docs/research/e02-cloud-test-plan/"
E = E02 + "implementation-handoffs/E/"
CONT = E + "continuation-20261006/"


def require(ok, why):
    if not ok:
        raise ValueError(why)


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args])


def load(repo, sha, path):
    return json.loads(git(repo, "show", f"{sha}:{path}"))


def check(packet, index, repo):
    snapshot = packet["input_snapshot_sha"]
    source = packet["assembled_source_sha"]
    require(
        git(repo, "rev-parse", snapshot + "^{tree}").decode().strip()
        == packet["input_snapshot_tree"],
        "snapshot tree mismatch",
    )
    require(
        git(repo, "rev-parse", source + "^{tree}").decode().strip()
        == packet["assembled_source_tree"],
        "source tree mismatch",
    )
    require(index["input_snapshot_sha"] == snapshot, "input index snapshot mismatch")
    indexed = {(r["source_sha"], r["path"]): r for r in index["inputs"]}
    require(len(indexed) == len(index["inputs"]), "duplicate exact source input")
    for record in index["inputs"]:
        key = f"{record['source_sha']}:{record['path']}"
        data = git(repo, "show", key)
        require(
            len(data) == record["bytes"]
            and hashlib.sha256(data).hexdigest() == record["sha256"],
            "source input size/hash mismatch:" + key,
        )
        require(
            git(repo, "rev-parse", key).decode().strip() == record["git_blob"],
            "source Git blob mismatch:" + key,
        )
    coverage = load(repo, snapshot, E02 + "closure-decisions/coverage.json")
    expected = {r["id"]: r for r in coverage["findings"] if r["unit"] == "E"}
    bundles = {r["id"]: r for r in coverage["bundles"] if r["unit"] == "E"}
    prior = load(repo, snapshot, CONT + "closure-frozen/all-54-closeout.json")
    prior_rows = {r["finding_id"]: r for r in prior["rows"]}
    find_owner = list(
        csv.DictReader(
            io.StringIO(
                git(
                    repo,
                    "show",
                    snapshot + ":" + E02 + "execution-organization/finding-owners.tsv",
                ).decode()
            ),
            delimiter="\t",
        )
    )
    find_owner = {r["finding_id"]: r for r in find_owner if r["unit"] == "E"}
    bundle_owner = list(
        csv.DictReader(
            io.StringIO(
                git(
                    repo,
                    "show",
                    snapshot + ":" + E02 + "execution-organization/bundle-owners.tsv",
                ).decode()
            ),
            delimiter="\t",
        )
    )
    bundle_owner = {r["bundle_id"]: r for r in bundle_owner if r["unit"] == "E"}
    rows = packet["rows"]
    require(
        len(rows) == 54 and len({r["id"] for r in rows}) == 54,
        "54unique finding denominator",
    )
    require(
        {r["id"] for r in rows} == set(expected) == set(find_owner),
        "exact E finding set",
    )
    require(len(bundles) == 22 and len(bundle_owner) == 22, "22bundle denominator")
    require({b["id"] for b in packet["bundles"]} == set(bundles), "exact E bundle set")
    for b in packet["bundles"]:
        require(
            b["writer"] == bundle_owner[b["id"]]["initial_writer_family"],
            "bundle writer mismatch:" + b["id"],
        )
        require(
            b["finding_ids"] == bundles[b["id"]]["finding_ids"],
            "bundle members mismatch:" + b["id"],
        )
    require(sum(len(r["bundle_ids"]) for r in rows) == 55, "55 ID-to-bundle links")
    require(
        packet["denominator"]
        == {"bundles": 22, "findings": 54, "ID_to_bundle_links": 55},
        "declared denominator mismatch",
    )
    for row in rows:
        fid = row["id"]
        previous = prior_rows[fid]
        owner = find_owner[fid]
        require(
            set(row["bundle_ids"]) == set(expected[fid]["companion_bundles"]),
            "finding bundle set:" + fid,
        )
        require(
            row["source_closure_owner_literal"] == owner["source_closure_owner"],
            "original closure owner mismatch:" + fid,
        )
        require(
            row["ledger_status_preserved"]
            == previous["ledger_status_preserved"]
            == owner["source_status"],
            "historical ledger mutation:" + fid,
        )
        require(row["formal_ledger_change"] is False, "formal ledger mutation:" + fid)
        require(row["criterion"] == previous["criterion"], "criterion drift:" + fid)
        require(
            row["original_source_criterion_refs"] == previous["criterion_refs"],
            "original criterion refs drift:" + fid,
        )
        require(
            all(
                row[k]
                for k in [
                    "next_owner",
                    "minimal_inputs",
                    "next_verifiable_result",
                    "implementation_residual_or_external_boundary",
                ]
            ),
            "missing concrete owner/input/result:" + fid,
        )
        require(
            row["family_evidence"] in packet["family_evidence"],
            "missing family evidence:" + fid,
        )
        require(
            row["gate_predicate_basis"]
            == packet["family_evidence"][row["family_evidence"]]["P37"],
            "P37 basis drift:" + fid,
        )
        for bid in row["bundle_ids"]:
            require(
                row["bundle_writers"][bid]
                == bundle_owner[bid]["initial_writer_family"],
                "writer mutation:" + fid,
            )
            card = bundles[bid]["criterion_card"]
            require(
                f"{card}@{snapshot}" in row["original_card_refs"],
                "missing original card:" + fid,
            )
            require((snapshot, card) in indexed, "unbound original card:" + fid)
        for criterion in row["original_source_criterion_refs"]:
            require(
                (snapshot, criterion["path"]) in indexed,
                "unbound original source criterion:" + fid,
            )
            original = (
                git(repo, "show", snapshot + ":" + criterion["path"])
                .decode()
                .splitlines()
            )
            start, end = criterion["lines"]
            block = ("\n".join(original[start - 1 : end]) + "\n").encode()
            require(
                hashlib.sha256(block).hexdigest() == criterion["sha256"],
                "original source criterion line-block hash mismatch:" + fid,
            )
    require(
        dict(collections.Counter(r["ledger_status_preserved"] for r in rows))
        == {"partial": 49, "held": 4, "closed": 1},
        "ledger counts",
    )
    require(
        packet["ledger_status_counts_preserved"]
        == {"partial": 49, "held": 4, "closed": 1},
        "declared ledger counts",
    )
    held = {r["id"] for r in rows if r["ledger_status_preserved"] == "held"}
    require(held == {"B194", "B197", "B201", "B202"}, "four exact held IDs")
    require(
        all(r["proposed_verdict"] == "held" for r in rows if r["id"] in held),
        "held semantics/source mutation",
    )
    require(
        [r["id"] for r in rows if r["proposed_verdict"] == "closed"] == ["B198"],
        "automatic closure mutation",
    )
    require(
        sum(
            r["historical_bounded_proposal"]
            and r["ledger_status_preserved"] == "partial"
            for r in rows
        )
        == 32,
        "32partial historical proposals",
    )
    require(
        {r["id"] for r in rows if r["historical_bounded_proposal"]}
        == set(prior["bounded_property_complete_candidate_ids"]),
        "historical bounded proposals drift",
    )
    require(
        sum(r["historical_bucket"] == "partial_active_residual" for r in rows) == 17,
        "17partial historical residuals",
    )
    for fid in ["B166", "B169", "B170"]:
        row = next(r for r in rows if r["id"] == fid)
        require(
            "0983" in row["current_property_status"]
            and "GO" in row["current_property_status"],
            "BKT corrective source review omitted:" + fid,
        )
    row = next(r for r in rows if r["id"] == "B198")
    require(
        "only a new defining-property falsifier" in row["next_verifiable_result"]
        and "Retain closed" in row["next_verifiable_result"],
        "closed B198 mistaken as new closure proposal",
    )
    row = next(r for r in rows if r["id"] == "B197")
    require(
        "bypass" in row["implementation_residual_or_external_boundary"]
        and "1e942" in row["implementation_residual_or_external_boundary"],
        "B197 implementable reader defect hidden as externalhold",
    )
    for fid in ("B188", "B192", "B194"):
        row = next(r for r in rows if r["id"] == fid)
        require(
            "welfare sibling law defect"
            in row["implementation_residual_or_external_boundary"]
            and "Normal" in row["implementation_residual_or_external_boundary"],
            "welfare code classfix hidden by externalhold:" + fid,
        )
    require(
        all("UNRUN" in row["root_wave_outcome"] for row in rows),
        "component PASS misreported as root wave",
    )
    semantic = load(repo, snapshot, CONT + "pr38-r2/ir-semantic-owner-decision.json")
    require(
        semantic["canonical_owner"] is None
        and semantic["decision_state"] == "unratified",
        "unexpected semantic authority requires refreshed packet",
    )
    assembly = load(repo, snapshot, CONT + "pr38-r2/reviewed-five-slice-assembly.json")
    for c in assembly["components"]:
        meta = packet["family_evidence"][c["family"].upper()]
        require(
            meta["implementation_sha"] == c["implementation_sha"],
            "component implementation drift:" + c["family"],
        )
        require(
            meta["assembled_source_sha"] == source,
            "component false root source binding",
        )
        require(
            meta["implementation_tree"]
            == git(repo, "rev-parse", c["implementation_sha"] + "^{tree}")
            .decode()
            .strip(),
            "component tree mismatch",
        )
    require(
        packet["family_evidence"]["BKT"]["assembled_state"].startswith("source-present")
        and packet["family_evidence"]["BKT"]["implementation_sha"]
        == "0983d064df3c3e21f8b1accff4ee90484d78973b",
        "corrective BKT source admission mismatch",
    )
    require(
        packet["family_evidence"]["FRC"]["assembled_state"].startswith(
            "source-present"
        ),
        "FRC merged source omitted",
    )
    require(
        packet["family_evidence"]["UQS"]["assembled_state"]
        == "existing v1.1 source, v2 unimplemented",
        "v2 falsely implemented",
    )
    local = json.loads((HERE / "current-local-G-recipes.json").read_text())
    require(
        local["implementation_sha"] == source
        and local["implementation_tree"] == packet["assembled_source_tree"],
        "current local recipe source mismatch",
    )
    require(len(local["recipes"]) == 6, "current six factual recipe slices")
    for recipe in local["recipes"]:
        require(
            recipe["implementation_sha_for_this_recipe"] == source
            and recipe["implementation_tree"] == packet["assembled_source_tree"],
            "stale implementation in current recipe",
        )
        if recipe["family"] == "backtest":
            require(
                "generic native binding now exists" in recipe["minimal_inputs"][1]
                and "presently missing" not in "\n".join(recipe["minimal_inputs"]),
                "obsolete missing native bridge recipe",
            )
            require(
                "prepare_native_replay" in recipe["actual_api_sequence"][0]
                and "execute_native_forecast" in recipe["actual_api_sequence"][1]
                and "load_native_forecast" in recipe["actual_api_sequence"][2],
                "current native APIs not bound",
            )
    return {
        "state": "PASS",
        "findings": 54,
        "bundles": 22,
        "links": 55,
        "source_inputs_recomputed": len(indexed),
        "ledger": "49partial/4held/1closed",
        "historical_partial_proposals": 32,
        "historical_active_partial": 17,
        "code_vs_closure": "separate",
        "root_numeric_wave": "UNRUN",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=pathlib.Path, required=True)
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    packet = json.loads((HERE / "all-54-update.json").read_text())
    index = json.loads((HERE / "input-index.json").read_text())
    result = check(packet, index, args.repo)
    negatives = []
    if args.negative:

        def mutate_owner(p, i):
            p["rows"][0]["source_closure_owner_literal"] = "present-but-fake-owner"

        def mutate_ledger(p, i):
            next(r for r in p["rows"] if r["id"] == "B197")[
                "ledger_status_preserved"
            ] = "closed"

        def mutate_bundle(p, i):
            p["rows"][0]["bundle_ids"].append(p["rows"][0]["bundle_ids"][0])

        def mutate_hash(p, i):
            i["inputs"][0]["sha256"] = "0" * 64

        def hide_code(p, i):
            next(r for r in p["rows"] if r["id"] == "B197")[
                "implementation_residual_or_external_boundary"
            ] = "Only external source authority hold; no code work"

        def mutate_source(p, i):
            p["assembled_source_tree"] = "0" * 40

        def mutate_closed_regression(p, i):
            next(r for r in p["rows"] if r["id"] == "B198")[
                "next_verifiable_result"
            ] = "Owner accepts or rejects a new closure proposal"

        for name, mutator in [
            ("owner", mutate_owner),
            ("held_ledger", mutate_ledger),
            ("duplicate_bundle_denominator", mutate_bundle),
            ("git_input_hash", mutate_hash),
            ("hide_B197_code_defect", hide_code),
            ("assembled_tree", mutate_source),
            ("B198_closed_regression", mutate_closed_regression),
        ]:
            altered = copy.deepcopy(packet)
            altered_index = copy.deepcopy(index)
            mutator(altered, altered_index)
            try:
                check(altered, altered_index, args.repo)
            except ValueError as exc:
                negatives.append(
                    {"control": name, "state": "REJECTED", "reason": str(exc)}
                )
            else:
                raise AssertionError("negative accepted:" + name)
    output = {
        "validation": result,
        "negative_controls": negatives,
        "mutations": "in-memory only; source and deciding inputs unchanged",
    }
    (HERE / "validation.json").write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps(output))


if __name__ == "__main__":
    main()
