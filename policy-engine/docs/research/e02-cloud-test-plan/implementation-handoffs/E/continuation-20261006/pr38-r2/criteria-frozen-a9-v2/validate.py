#!/usr/bin/env python3
"""Recompute source, criteria, owner, JUnit and portable publication bindings.

This validator runs no product checks and mutates no checkout or prior receipt.
The --negative-controls option corrupts in-memory copies only.
"""

import argparse
import copy
import csv
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
from collections import Counter
from functools import cache
from pathlib import Path

from defusedxml.ElementTree import fromstring

HERE = Path(__file__).resolve().parent
SOURCE = "a9f78817c873be5b35a08155f2593b229d9fdbb6"
TREE = "c02e043c3e1c8222c28aa71187fa8db4e2fdeea7"
EVIDENCE = "ddcdfd9c220ba57e37c8abf52b976a7184c384f9"
E02 = "policy-engine/docs/research/e02-cloud-test-plan/"
CONT = E02 + "implementation-handoffs/E/continuation-20261006/"


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


_NO_PATH = object()


def admit_source(sha: object, path: object = _NO_PATH) -> None:
    """Refuse unbound or option-like Git objects before any child process."""
    require(
        isinstance(sha, str) and re.fullmatch(r"[0-9a-f]{40}", sha) is not None,
        "source requires an exact commit SHA",
    )
    if path is not _NO_PATH:
        require(isinstance(path, str) and bool(path), "source path requires a string")
        require(
            not any(character.isspace() or character == "\0" for character in path),
            "source path contains ambiguous characters",
        )
        relative = Path(path)
        require(
            not relative.is_absolute()
            and bool(relative.parts)
            and relative.as_posix() == path
            and ".." not in relative.parts,
            "source path must be repository relative",
        )
        require(not path.startswith("-") and ":" not in path, "source path is ambiguous")


def admit_index(index: dict[str, object], packet: dict[str, object]) -> None:
    """Admit the whole object-reference set before the first Git callback."""
    for record in index["inputs"]:
        admit_source(record["source_sha"], record["path"])
    for record in index["portable_inputs"]:
        admit_source(record["evidence_git_commit"], record["repository_path"])
        require(record["evidence_git_commit"] == EVIDENCE, "wrong evidence input checkpoint")
        admit_source(record["source_sha"])
        admit_source(record["source_tree"])
    for row in packet["rows"]:
        for fragment in row["original_source_criterion_refs"]:
            admit_source(SOURCE, fragment["path"])


@cache
def _admit_git_object_arguments(arguments: tuple[str, ...]) -> None:
    """Keep object reads from interpreting record refs as Git options.

    Named/abbreviated refs remain available to retired source-pinned replay
    scripts; live packet admissions separately require full immutable SHAs.
    """
    if not arguments or arguments[0] not in {"show", "rev-parse"}:
        return
    safe_information_flags = {"--show-toplevel", "--git-dir", "--git-common-dir"}
    for value in arguments[1:]:
        if not isinstance(value, str) or not value or "\0" in value:
            raise ValueError("Git object argument must be a nonempty string")
        if value.startswith("-"):
            if arguments[0] == "rev-parse" and value in safe_information_flags:
                continue
            raise ValueError("Git object reference must never be an option")
        if ":" in value:
            _, relative = value.split(":", 1)
            path = Path(relative)
            if (
                not path.parts
                or path.is_absolute()
                or ".." in path.parts
                or path.as_posix() != relative
                or "\0" in relative
            ):
                raise ValueError("Git object path must be repository relative")


def git(repo: str, *args: str) -> bytes:
    _admit_git_object_arguments(args)
    require(
        len(args) == 2 and args[0] in {"show", "rev-parse"},
        "only read-only object Git commands admitted",
    )
    object_name = args[1]
    if ":" in object_name:
        sha, path = object_name.split(":", 1)
        admit_source(sha, path)
    else:
        sha = object_name.removesuffix("^{tree}")
        admit_source(sha)
    git_executable = shutil.which("git")
    if git_executable is None:
        raise RuntimeError("Git executable unavailable")
    return subprocess.check_output([git_executable, "-C", str(repo), *args])  # noqa: S603 - admitted exact Git objects, argv without shell


@cache
def read(path: str) -> bytes:
    return Path(path).read_bytes()


def ident(data: bytes) -> dict[str, object]:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def tally(cases: list[dict[str, object]]) -> dict[str, int]:
    result = Counter(c["outcome"] for c in cases)
    return {
        "cases": len(cases),
        "passed": result["PASS"],
        "failed": result["FAIL"],
        "errors": result["ERROR"],
        "skipped": result["SKIP"],
    }


def portable_bytes(record: dict[str, object], repo: Path) -> bytes:
    return git(str(repo), "show", record["evidence_git_commit"] + ":" + record["repository_path"])


def exact_portable(index: dict[str, object], repo: Path) -> dict[str, object]:
    repository = {}
    for record in index["portable_inputs"]:
        path = record["repository_path"]
        require(path.startswith(CONT + "pr38-r2/"), "portable repository path scope")
        require(
            not Path(path).is_absolute() and ".." not in Path(path).parts, "portable path escape"
        )
        require(record["evidence_git_commit"] == EVIDENCE, "wrong evidence input checkpoint")
        require(
            record["source_sha"] == SOURCE and record["source_tree"] == TREE,
            "portable source identity",
        )
        require(
            ident(portable_bytes(record, repo)) == {k: record[k] for k in ["bytes", "sha256"]},
            "portable byte/hash custody",
        )
        if path in repository:
            require(
                repository[path]["sha256"] == record["sha256"]
                and repository[path]["bytes"] == record["bytes"],
                "different portable bytes at same intended repository path",
            )
        repository[path] = record
    return repository


def check(
    packet: dict[str, object],
    recipes: dict[str, object],
    index: dict[str, object],
    case_index: dict[str, object],
    lint: dict[str, object],
    repo: Path,
) -> dict[str, object]:
    admit_index(index, packet)
    require(
        packet["assembled_source_sha"] == SOURCE and packet["final_frozen_source_sha"] == SOURCE,
        "wrong final source SHA",
    )
    require(
        packet["assembled_source_tree"] == TREE and packet["final_frozen_source_tree"] == TREE,
        "wrong final source tree",
    )
    require(
        git(str(repo), "rev-parse", SOURCE + "^{tree}").decode().strip() == TREE,
        "actual Git source tree mismatch",
    )
    require(index["input_snapshot_sha"] == SOURCE, "input index wrong source")
    require(
        packet["evidence_publication"]["evidence_git_checkpoint"] is None,
        "fake publication checkpoint",
    )
    bound = {}
    for record in index["inputs"]:
        key = (record["source_sha"], record["path"])
        require(key not in bound, "duplicate Git source input")
        data = git(str(repo), "show", key[0] + ":" + key[1])
        require(
            ident(data) == {k: record[k] for k in ["bytes", "sha256"]},
            "source whole-file hash/size mismatch",
        )
        require(
            git(str(repo), "rev-parse", key[0] + ":" + key[1]).decode().strip()
            == record["git_blob"],
            "source Git blob mismatch",
        )
        bound[key] = record
    portable = exact_portable(index, repo)
    coverage = json.loads(
        git(str(repo), "show", SOURCE + ":" + E02 + "closure-decisions/coverage.json")
    )
    findings = {r["id"]: r for r in coverage["findings"] if r["unit"] == "E"}
    bundles = {r["id"]: r for r in coverage["bundles"] if r["unit"] == "E"}
    owner_tables = {}
    for label in ["finding", "bundle"]:
        data = git(
            str(repo),
            "show",
            SOURCE + ":" + E02 + "execution-organization/" + label + "-owners.tsv",
        ).decode()
        owner_tables[label] = {
            r[label + "_id"]: r
            for r in csv.DictReader(io.StringIO(data), delimiter="\t")
            if r["unit"] == "E"
        }
    prior = json.loads(
        git(str(repo), "show", SOURCE + ":" + CONT + "closure-frozen/all-54-closeout.json")
    )
    history = {r["finding_id"]: r for r in prior["rows"]}
    rows = packet["rows"]
    require(len(rows) == len({r["id"] for r in rows}) == 54, "54 unique IDs")
    require(
        {r["id"] for r in rows} == set(findings) == set(owner_tables["finding"]),
        "complete exact finding denominator",
    )
    require(len(bundles) == len(owner_tables["bundle"]) == 22, "22 exact bundles")
    require({r["id"] for r in packet["bundles"]} == set(bundles), "bundle omissions")
    require(sum(len(r["bundle_ids"]) for r in rows) == 55, "55 ID-bundle links")
    require(
        packet["denominator"] == {"bundles": 22, "findings": 54, "ID_to_bundle_links": 55},
        "declared denominator",
    )
    for bundle in packet["bundles"]:
        require(
            bundle["writer"] == owner_tables["bundle"][bundle["id"]]["initial_writer_family"],
            "bundle writer drift",
        )
        require(
            bundle["finding_ids"] == bundles[bundle["id"]]["finding_ids"], "bundle membership drift"
        )
    for row in rows:
        fid = row["id"]
        owner = owner_tables["finding"][fid]
        previous = history[fid]
        require(
            row["source_closure_owner_literal"] == owner["source_closure_owner"],
            "original owner drift:" + fid,
        )
        require(
            set(row["bundle_ids"]) == set(findings[fid]["companion_bundles"]),
            "original bundle links drift:" + fid,
        )
        require(row["criterion"] == previous["criterion"], "criterion drift:" + fid)
        require(
            row["original_source_criterion_refs"] == previous["criterion_refs"],
            "original criterion fragment drift:" + fid,
        )
        require(
            row["ledger_status_preserved"]
            == previous["ledger_status_preserved"]
            == owner["source_status"],
            "historical ledger mutation:" + fid,
        )
        require(row["formal_ledger_change"] is False, "formal ledger mutation:" + fid)
        require(
            row["gate_predicate_basis"]["current_per_ID_predicate"] == row["criterion"],
            "family proxy replaced original predicate:" + fid,
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
            "missing owner/input/concrete next result:" + fid,
        )
        family = packet["family_evidence"][row["family_evidence"]]
        require(
            row["producer_artifact_bridge_consumer_surface"]
            == {k: family[k] for k in ["producer", "artifact", "bridge", "consumer", "surface"]},
            "producer/artifact/consumer mapping drift:" + fid,
        )
        for bid in row["bundle_ids"]:
            require(
                row["bundle_writers"][bid] == owner_tables["bundle"][bid]["initial_writer_family"],
                "writer drift:" + fid,
            )
            card = bundles[bid]["criterion_card"]
            require(
                card + "@" + SOURCE in row["original_card_refs"] and (SOURCE, card) in bound,
                "unbound original card:" + fid,
            )
        fragments = row["original_source_criterion_refs"]
        basis = row["original_source_criterion_hash_basis"]
        require(
            "not full source file" in basis["sha256_semantics"],
            "fragment hash mislabeled as full-file hash",
        )
        require(basis["selected_fragments"] == fragments, "fragment basis drift")
        for fragment in fragments:
            require((SOURCE, fragment["path"]) in bound, "unbound original source")
            original = git(str(repo), "show", SOURCE + ":" + fragment["path"]).decode().splitlines()
            start, end = fragment["lines"]
            data = ("\n".join(original[start - 1 : end]) + "\n").encode()
            require(ident(data)["sha256"] == fragment["sha256"], "fragment digest mismatch")
            require(
                bound[(SOURCE, fragment["path"])] in basis["full_source_files"],
                "full source file identity missing",
            )
        chosen = [
            c
            for c in case_index["cases"]
            if re.search(
                row["current_oracle_negative"]["current_selector_rule"],
                c["classname"] + "::" + c["name"],
            )
        ]
        expected = [
            {
                k: c[k]
                for k in [
                    "job",
                    "classname",
                    "name",
                    "outcome",
                    "xml_repository_path",
                    "xml_sha256",
                ]
            }
            for c in chosen
        ]
        require(
            row["current_oracle_negative"]["current_exact_wave_cases"] == expected,
            "current selected case evidence drift:" + fid,
        )
        require(
            row["root_wave_outcome"]["selected_case_counts"] == tally(chosen),
            "selected case denominator drift:" + fid,
        )
        require(chosen or fid in ["B201", "B202"], "missing native scoped selector:" + fid)
    require(
        dict(Counter(r["ledger_status_preserved"] for r in rows))
        == packet["ledger_status_counts_preserved"]
        == {"partial": 49, "held": 4, "closed": 1},
        "ledger count mutation",
    )
    require(
        {r["id"] for r in rows if r["proposed_verdict"] == "held"}
        == {"B194", "B197", "B201", "B202"},
        "four exact held decisions",
    )
    require(
        [r["id"] for r in rows if r["proposed_verdict"] == "closed"] == ["B198"],
        "automatic closure",
    )
    require(
        sum(
            r["historical_bounded_proposal"] and r["ledger_status_preserved"] == "partial"
            for r in rows
        )
        == 32,
        "32 bounded historical owner proposals",
    )
    require(
        sum(r["historical_bucket"] == "partial_active_residual" for r in rows) == 17,
        "17 historical active residuals",
    )
    require(
        {r["id"] for r in rows if r["historical_bounded_proposal"]}
        == set(prior["bounded_property_complete_candidate_ids"]),
        "historical proposal set",
    )
    b198 = next(r for r in rows if r["id"] == "B198")
    require(
        "Retain closed" in b198["next_verifiable_result"]
        and "only a new defining-property falsifier" in b198["next_verifiable_result"],
        "B198 incorrectly treated as new closure proposal",
    )
    b186 = next(r for r in rows if r["id"] == "B186")
    require(
        b186["criterion_evidence"]["state"] == "satisfied_declared_native_generic_scope"
        and "No productioncorpusrequired"
        in b186["criterion_evidence"]["supplementary_family_authority_boundary"],
        "invented production prerequisite for generic kwargs criterion",
    )
    require(
        b186["root_wave_outcome"]["selected_case_counts"]["cases"] == 3,
        "fixed kwargs 3-case exact denominator",
    )
    require(
        "6limiteddeterministic"
        in packet["family_evidence"]["MC"]["P37"]["G127_unknown_joint_law_qualification"]
        and "0stochasticattempts"
        in packet["family_evidence"]["MC"]["P37"]["G127_unknown_joint_law_qualification"],
        "unknown-law diagnostic vs stochastic callback conflation",
    )
    actual_cases = []
    wave = packet["common_wave"]
    plan = json.loads(portable_bytes(portable[wave["plan_ref"]["repository_path"]], repo))
    require(
        [j["name"] for j in wave["jobs"]] == [j["name"] for j in plan["jobs"]],
        "complete job plan denominator",
    )
    for job, declared in zip(wave["jobs"], plan["jobs"], strict=True):
        receipt = json.loads(portable_bytes(portable[job["receipt_ref"]["repository_path"]], repo))
        stdout = portable_bytes(portable[job["stdout_ref"]["repository_path"]], repo)
        require(
            job["command"] == declared["argv"] == receipt["command"],
            "actual full job command substitution",
        )
        require(
            job["outcome"] == receipt["outcome"] and job["exit_code"] == receipt["exit_code"],
            "actual job outcome substitution",
        )
        require(
            receipt["stdout_sha256"] == ident(stdout)["sha256"]
            and receipt["stdout_bytes"] == len(stdout),
            "actual stdout receipt drift",
        )
        require(
            receipt["candidate_sha"] == SOURCE and receipt["candidate_tree_sha"] == TREE,
            "actual job source drift",
        )
    for job in wave["jobs"]:
        if "JUnit_ref" not in job:
            continue
        ref = portable[job["JUnit_ref"]["repository_path"]]
        parsed = fromstring(portable_bytes(ref, repo))
        for node in parsed.iter("testcase"):
            tags = {child.tag for child in node}
            outcome = (
                "ERROR"
                if "error" in tags
                else "FAIL"
                if "failure" in tags
                else "SKIP"
                if "skipped" in tags
                else "PASS"
            )
            actual_cases.append(
                {
                    "job": job["name"],
                    "classname": node.get("classname", ""),
                    "name": node.get("name", ""),
                    "outcome": outcome,
                }
            )
    keys = ["job", "classname", "name", "outcome"]
    require(
        [{k: c[k] for k in keys} for c in case_index["cases"]] == actual_cases,
        "actual XML case index mismatch",
    )
    require(
        wave["numeric_counts"]
        == tally(actual_cases)
        == {"cases": 1445, "passed": 1441, "failed": 4, "errors": 0, "skipped": 0},
        "actual numerical denominator mismatch",
    )
    require(
        sum(j["outcome"] == "FAIL" for j in wave["jobs"] if j["kind"] != "numerical") == 7,
        "seven current global gate FAIL count",
    )
    require(
        wave["umbrella_stages"]["workspace-verify"]["counts"]["UNRUN"] == 13
        and wave["umbrella_stages"]["ci-parity"]["counts"]["UNRUN"] == 23,
        "umbrella UNRUN denominator",
    )
    require(
        wave["static_proxy"]["regressions"] == 10
        and wave["static_proxy"]["new_unresolved_by_construction"] == 89
        and wave["static_proxy"]["unresolved"] == 9238
        and wave["static_proxy"]["unresolved_receiver_calls"] == 140152,
        "current static proxy denominator",
    )
    require(
        wave["runtime_API"]["projection_numbers_in_actual_stdout"] == [1489, 1493],
        "actual API projection boundary",
    )
    require(
        lint["input_paths"] == plan["changed_python_lint_paths"],
        "full plan lint denominator substitution",
    )
    ruff_job = next(j for j in wave["jobs"] if j["name"] == "ruff")
    diagnostic_lines = (
        portable_bytes(portable[ruff_job["stdout_ref"]["repository_path"]], repo)
        .decode()
        .splitlines()
    )
    actual_diagnostics = []
    active_code = None
    for line in diagnostic_lines:
        header = re.match(r"^([A-Z]+[0-9]+) ", line)
        if header:
            active_code = header[1]
        location = re.match(r"^\s*--> (.+):(\d+):(\d+)\s*$", line)
        if location:
            require(active_code is not None, "unattributed Ruff diagnostic")
            actual_diagnostics.append((active_code, location[1]))
            active_code = None
    require(len(actual_diagnostics) == 7951, "actual full Ruff diagnostic parse")
    actual_codes = dict(sorted(Counter(c for c, _ in actual_diagnostics).items()))
    require(lint["ruff"]["codes"] == actual_codes, "Ruff diagnostic class substitution")
    actual_paths = Counter(path for _, path in actual_diagnostics)
    require(
        set(actual_paths) == {r["path"] for r in lint["path_rows"]}, "actual Ruff path substitution"
    )
    for row in lint["path_rows"]:
        require(
            row["diagnostics"] == actual_paths[row["path"]]
            and row["codes"]
            == dict(
                sorted(Counter(c for c, path in actual_diagnostics if path == row["path"]).items())
            ),
            "actual per-path lint diagnostic/class mismatch",
        )
    format_job = next(j for j in wave["jobs"] if j["name"] == "ruff-format")
    format_stdout = portable_bytes(
        portable[format_job["stdout_ref"]["repository_path"]], repo
    ).decode()
    require(
        lint["format"]["paths"] == re.findall(r"^Would reformat: (.+)$", format_stdout, re.M),
        "actual formatter path substitution",
    )
    require(lint["input_count"] == len(set(lint["input_paths"])) == 317, "317 full lint inputs")
    require(
        lint["ruff"]["diagnostics"] == 7951
        and lint["ruff"]["paths"] == 172
        and lint["ruff"]["rule_code_count"] == 49
        and sum(lint["ruff"]["codes"].values()) == 7951,
        "current Ruff denominator",
    )
    require(
        len(lint["path_rows"]) == len({p["path"] for p in lint["path_rows"]}) == 172,
        "current lint affected paths",
    )
    require(
        lint["format"]["would_reformat"] == len(lint["format"]["paths"]) == 156
        and lint["format"]["already_formatted"] == 161,
        "current format full denominator",
    )
    require(
        all(p["path"] in lint["input_paths"] for p in lint["path_rows"]),
        "affected lint path outside actual full input",
    )
    require(
        all(
            p["source_identity"] == bound[(SOURCE, "policy-engine/" + p["path"])]
            for p in lint["path_rows"]
        ),
        "source-bound lint path identity",
    )
    require(
        len(recipes["recipes"]) == 6
        and recipes["implementation_sha"] == SOURCE
        and recipes["implementation_tree"] == TREE,
        "six source-pinned local recipes",
    )
    for recipe in recipes["recipes"]:
        require(
            recipe["implementation_sha_for_this_recipe"] == SOURCE
            and recipe["implementation_tree"] == TREE,
            "recipe source drift",
        )
        require(
            all("/workspace/" not in command for command in recipe["bounded_mechanism_commands"]),
            "nonportable local recipe command",
        )
    ddm = next(r for r in recipes["recipes"] if r["family"] == "ddm")
    require(
        "schema_version=2 automatically" in ddm["actual_api_sequence"][0]
        and "build_model_registry_record(schema_version=" not in ddm["actual_api_sequence"][0],
        "unsupported DDM builder keyword",
    )
    return {
        "status": "PASS_metadata_source_and_actual_output_recomputation",
        "source_sha": SOURCE,
        "source_tree": TREE,
        "bundles": 22,
        "findings": 54,
        "links": 55,
        "ledger": {"partial": 49, "held": 4, "closed": 1},
        "partial_owner_proposals": 32,
        "historical_active_partials": 17,
        "Git_inputs": len(index["inputs"]),
        "portable_records": len(index["portable_inputs"]),
        "actual_numeric": tally(actual_cases),
        "global_gates": "7FAIL",
        "metadata_validation_is_product_or_finding_acceptance": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--negative-controls", action="store_true")
    args = parser.parse_args()
    names = [
        "all-54-update.json",
        "current-local-G-recipes.json",
        "input-index.json",
        "current-case-index.json",
        "current-lint-publication-debt.json",
    ]
    values = [json.loads(read(str(HERE / name))) for name in names]
    result = check(*values, args.repo)
    if args.negative_controls:
        edits = {
            "ledger_autoaccept": lambda v: v[0]["rows"][0].update(ledger_status_preserved="closed"),
            "owner_substitution": lambda v: v[0]["rows"][0].update(
                source_closure_owner_literal="E"
            ),
            "bundle_omission": lambda v: v[0]["bundles"].pop(),
            "source_hash_forgery": lambda v: v[2]["inputs"][0].update(sha256="0" * 64),
            "job_command_substitution": lambda v: v[0]["common_wave"]["jobs"][0].update(
                command=["dummy-positive"]
            ),
            "lint_class_substitution": lambda v: v[4]["ruff"]["codes"].update(B006=1),
            "criterion_fragment_as_full_file": lambda v: v[0]["rows"][0][
                "original_source_criterion_hash_basis"
            ].update(sha256_semantics="full file hash"),
            "source_tree_forgery": lambda v: v[0].update(assembled_source_tree="0" * 40),
            "fake_wave_counts": lambda v: v[0]["common_wave"]["numeric_counts"].update(failed=0),
            "missing_scoped_cases": lambda v: v[0]["rows"][0]["current_oracle_negative"][
                "current_exact_wave_cases"
            ].pop(),
            "false_stochastic_callback_zero": lambda v: v[0]["family_evidence"]["MC"]["P37"].update(
                G127_unknown_joint_law_qualification="0totalcallbacks"
            ),
            "fake_publication_checkpoint": lambda v: v[0]["evidence_publication"].update(
                evidence_git_checkpoint=SOURCE
            ),
            "portable_path_escape": lambda v: v[2]["portable_inputs"][0].update(
                repository_path="../private-config"
            ),
            "wrong_input_checkpoint": lambda v: v[2]["portable_inputs"][0].update(
                evidence_git_commit=SOURCE
            ),
            "portable_hash_forgery": lambda v: v[2]["portable_inputs"][0].update(sha256="0" * 64),
            "lint_denominator_narrowing": lambda v: v[4]["input_paths"].pop(),
            "lint_path_omission": lambda v: v[4]["path_rows"].pop(),
            "format_denominator_narrowing": lambda v: v[4]["format"].update(already_formatted=160),
            "unsupported_DDM_keyword": lambda v: next(
                r for r in v[1]["recipes"] if r["family"] == "ddm"
            )["actual_api_sequence"].__setitem__(
                0, "build_model_registry_record(schema_version=2)"
            ),
            "newly_closed_B201": lambda v: next(
                r for r in v[0]["rows"] if r["id"] == "B201"
            ).update(proposed_verdict="closed"),
            "invented_B186_production_prerequisite": lambda v: next(
                r for r in v[0]["rows"] if r["id"] == "B186"
            )["criterion_evidence"].update(state="requiresproductioncorpus"),
            "B198_generic_acceptance_plan": lambda v: next(
                r for r in v[0]["rows"] if r["id"] == "B198"
            ).update(next_verifiable_result="owneracceptsnewclosureproposal"),
        }
        controls = []
        for name, edit in edits.items():
            changed = copy.deepcopy(values)
            edit(changed)
            try:
                check(*changed, args.repo)
            except ValueError as error:
                controls.append({"name": name, "outcome": "REFUSED", "reason": str(error)})
            else:
                raise ValueError("present-but-fake metadata admitted:" + name)
        result["corrupt_field_controls"] = controls
    sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
