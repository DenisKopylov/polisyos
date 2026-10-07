#!/usr/bin/env python3
"Read exact Git evidence and recompute final closeout joins; no product execution."

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

from defusedxml.ElementTree import fromstring as _safe_xml_fromstring


def _resolve_executable(name: str) -> str:
    "Resolve an admitted executable and refuse an unavailable program before invocation."
    resolved = shutil.which(name)
    if resolved is None:
        raise RuntimeError(f"required utility executable unavailable: {name}")
    return str(Path(resolved).resolve())


REPO = Path("/workspace/e02-E-continuation-20261006")
HERE = Path(__file__).resolve().parent
COMMIT = "9954f394b470961d9e144a557f3cefeb9e0a67b6"
SOURCE = "a9f78817c873be5b35a08155f2593b229d9fdbb6"
TREE = "c02e043c3e1c8222c28aa71187fa8db4e2fdeea7"
EVIDENCE = "ddcdfd9c220ba57e37c8abf52b976a7184c384f9"
E02 = "policy-engine/docs/research/e02-cloud-test-plan/"
PR38 = E02 + "implementation-handoffs/E/continuation-20261006/pr38-r2/"
PREFIX = PR38 + "criteria-frozen-a9-v2/"


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


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


def git(*argv: object) -> object:
    _admit_git_object_arguments(argv)
    return subprocess.check_output([_resolve_executable("git"), "-C", str(REPO), *argv])  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit


def blob(commit: str, path: object) -> object:
    return git("show", commit + ":" + path)


def parse(commit: str, path: object) -> object:
    return json.loads(blob(commit, path))


def identity(data: object) -> dict[str, object]:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def load(name: str) -> object:
    return json.loads((HERE / "exact-Git-inputs" / name).read_bytes())


def check_manifest(manifest: object) -> object:
    require(manifest["source_sha"] == SOURCE and manifest["source_tree"] == TREE, "manifest source")
    names = [r["path"] for r in manifest["files"]]
    require(len(names) == len(set(names)) == 17, "manifest full denominator")
    total = 0
    for record in manifest["files"]:
        name = record["path"]
        require(not Path(name).is_absolute() and ".." not in Path(name).parts, "manifest escape")
        data = blob(COMMIT, PREFIX + name)
        require(
            identity(data) == {k: record[k] for k in ["bytes", "sha256"]},
            "manifest committed bytes",
        )
        require(data == (HERE / "exact-Git-inputs" / name).read_bytes(), "snapshot byte removal")
        total += len(data)
    require(total == manifest["total_bytes"] == 3614273, "manifest size denominator")
    return total


def check_wave(packet: object, cases: object) -> dict[str, object]:
    wave = packet["common_wave"]
    require(wave["source_sha"] == SOURCE and wave["source_tree"] == TREE, "wave source")
    actual = []
    actual_job_rows = []
    plan = parse(EVIDENCE, wave["plan_ref"]["repository_path"])
    require(
        [j["name"] for j in wave["jobs"]] == [j["name"] for j in plan["jobs"]],
        "wave full command plan",
    )
    for job, planned in zip(wave["jobs"], plan["jobs"], strict=True):
        receipt = parse(EVIDENCE, job["receipt_ref"]["repository_path"])
        require(
            job["command"] == planned["argv"] == receipt["command"], "wave command substitution"
        )
        require(job["outcome"] == receipt["outcome"], "job outcome changed")
        require(
            receipt["candidate_sha"] == SOURCE and receipt["candidate_tree_sha"] == TREE,
            "receipt source",
        )
        stdout = blob(EVIDENCE, job["stdout_ref"]["repository_path"])
        require(
            identity(stdout)
            == {"bytes": receipt["stdout_bytes"], "sha256": receipt["stdout_sha256"]},
            "stdout custody",
        )
        actual_job_rows.append(
            {
                "job": job["name"],
                "kind": job["kind"],
                "outcome": receipt["outcome"],
                "exit_code": receipt["exit_code"],
            }
        )
        if "JUnit_ref" in job:
            data = blob(EVIDENCE, job["JUnit_ref"]["repository_path"])
            for case in _safe_xml_fromstring(data).iter("testcase"):
                tags = {n.tag for n in case}
                outcome = (
                    "ERROR"
                    if "error" in tags
                    else "FAIL"
                    if "failure" in tags
                    else "SKIP"
                    if "skipped" in tags
                    else "PASS"
                )
                actual.append(
                    (job["name"], case.get("classname", ""), case.get("name", ""), outcome)
                )
    require(
        actual == [(r["job"], r["classname"], r["name"], r["outcome"]) for r in cases["cases"]],
        "XML actual denominator",
    )
    counts = Counter(x[3] for x in actual)
    require(
        dict(counts) == {"PASS": 1441, "FAIL": 4} and len(actual) == 1445, "actual numeric outcomes"
    )
    require(
        wave["numeric_counts"]
        == {"cases": 1445, "passed": 1441, "failed": 4, "errors": 0, "skipped": 0},
        "wave numeric declared denominator",
    )
    require(
        sum(j["kind"] != "numerical" and j["outcome"] == "FAIL" for j in actual_job_rows) == 7,
        "seven actual failed gates",
    )
    stages = {}
    for name in ["workspace-verify", "ci-parity"]:
        stage_data = parse(EVIDENCE, wave["umbrella_stages"][name]["ref"]["repository_path"])
        scopes = stage_data if isinstance(stage_data, list) else stage_data["scopes"]
        outcomes = Counter(s["outcome"] for scope in scopes for s in scope["steps"])
        require(dict(outcomes) == wave["umbrella_stages"][name]["counts"], "actual umbrella count")
        stages[name] = dict(outcomes)
    require(
        stages["workspace-verify"]["UNRUN"] == 13 and stages["ci-parity"]["UNRUN"] == 23,
        "actual fail-fast stages",
    )
    return {
        "cases": len(actual),
        "outcomes": dict(counts),
        "jobs": actual_job_rows,
        "umbrella": stages,
    }


def check_semantics(packet: object, recipes: object, empirical: object) -> dict[str, object]:
    rows = {r["id"]: r for r in packet["rows"]}
    require(
        {i for i, r in rows.items() if r["proposed_verdict"] == "held"}
        == {"B194", "B197", "B201", "B202"},
        "held authority decisions",
    )
    require(
        {i for i, r in rows.items() if r["proposed_verdict"] == "closed"} == {"B198"},
        "automatic finding closure",
    )
    require(
        rows["B198"]["ledger_status_preserved"] == "closed"
        and "only a new defining-property falsifier" in rows["B198"]["next_verifiable_result"],
        "B198 historical regression",
    )
    require(
        sum(
            r["historical_bounded_proposal"] and r["ledger_status_preserved"] == "partial"
            for r in rows.values()
        )
        == 32,
        "32 original partial proposals",
    )
    require(
        sum(r["historical_bucket"] == "partial_active_residual" for r in rows.values()) == 17,
        "17 historical active denominator",
    )
    for fid in ["B186", "B188", "B192"]:
        require(
            rows[fid]["criterion_evidence"]["state"] == "satisfied_declared_native_generic_scope",
            "generic criterion hidden behind external authority",
        )
        require(
            "productioncorpus"
            not in rows[fid]["criterion_evidence"]["original_criterion_input_state"]
            .lower()
            .replace("no additionalproductioncorpus", ""),
            "invented corpus prerequisite",
        )
    for fid in ["LA-054", "LA-055"]:
        require(
            rows[fid]["criterion_evidence"]["state"]
            == "native_property_measured_with_original_owner_boundary_remaining",
            "DDM institutional authority invented",
        )
        require(
            (
                "Actual" in rows[fid]["minimal_inputs"]
                and "owner" in rows[fid]["implementation_residual_or_external_boundary"].lower()
            )
            or "institutional authority"
            in rows[fid]["implementation_residual_or_external_boundary"],
            "DDM actual inputs absent",
        )
    ddm = next(r for r in recipes["recipes"] if r["family"] == "ddm")
    require(
        "schema_version=2 automatically" in ddm["actual_api_sequence"][0]
        and "build_model_registry_record(schema_version=" not in ddm["actual_api_sequence"][0],
        "unsupported DDM API",
    )
    for recipe in recipes["recipes"]:
        require(
            recipe["implementation_sha_for_this_recipe"] == SOURCE
            and recipe["implementation_tree"] == TREE,
            "local recipe old source",
        )
        require(
            recipe["minimal_inputs"] and recipe["next_owner"] and recipe["deciding_controls"],
            "recipe input/owner/negative absent",
        )
    receipt = empirical["artifacts"]["receipt_ref"]["content"]
    report = empirical["artifacts"]["propagation_report_ref"]["content"]
    sample = empirical["artifacts"]["sample_ref"]["content"]
    require(
        (
            receipt["requested_draw_count"],
            receipt["attempted_draw_count"],
            receipt["successful_draw_count"],
            receipt["failed_draw_count"],
            receipt["unattempted_draw_count"],
        )
        == (128, 128, 92, 36, 0),
        "hidden failed support denominator",
    )
    require(
        len(receipt["draw_records"]) == 128 and len(receipt["failure_records"]) == 36,
        "failed outcomes removed",
    )
    require(
        set(sample["welfare_draws"]) == {2.0} and len(sample["welfare_draws"]) == 92,
        "empirical successful result",
    )
    require(
        report["draw_summary"]["conditional_welfare_mean"] == 2.0
        and report["draw_summary"]["welfare_mean"] is None
        and report["support_complete"] is False
        and report["gate_eligible"] is False,
        "conditional support became unconditional",
    )
    return {
        "128draws": "92success+36failure",
        "estimate_scope": report["estimate_scope"],
        "finding_closure": "only historical B198",
        "DDM": "library evidence distinct from institutional/current-feed authority",
    }


def main() -> None:
    manifest = load("publication-index.json")
    packet = load("all-54-update.json")
    recipes = load("current-local-G-recipes.json")
    cases = load("current-case-index.json")
    index = load("input-index.json")
    require(
        git("rev-parse", COMMIT + "^{tree}").decode().strip()
        == "e923abf31637b4299ec36a467f4c6b06e26cae1c",
        "publication Git tree",
    )
    require(git("rev-parse", SOURCE + "^{tree}").decode().strip() == TREE, "actual source Git tree")
    total = check_manifest(manifest)
    coverage = parse(SOURCE, E02 + "closure-decisions/coverage.json")
    findings = {r["id"]: r for r in coverage["findings"] if r["unit"] == "E"}
    bundles = {r["id"]: r for r in coverage["bundles"] if r["unit"] == "E"}
    owners = {}
    for family in ["finding", "bundle"]:
        rows = csv.DictReader(
            io.StringIO(
                blob(SOURCE, E02 + "execution-organization/" + family + "-owners.tsv").decode()
            ),
            delimiter="\t",
        )
        owners[family] = {r[family + "_id"]: r for r in rows if r["unit"] == "E"}
    ledger = parse(
        SOURCE,
        ("policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/residual_ledger.json"),
    )
    ledger_rows = {r["id"]: r for r in ledger["rows"] if r["id"] in findings}
    require(
        set(findings)
        == set(owners["finding"])
        == set(ledger_rows)
        == {r["id"] for r in packet["rows"]},
        "actual 54 ID ownership/ledger coverage",
    )
    require(
        len(findings) == 54 and len(bundles) == len(owners["bundle"]) == 22,
        "actual 22/54 denominator",
    )
    require(
        Counter(r["status"] for r in ledger_rows.values())
        == {"partial": 49, "held": 4, "closed": 1},
        "current actual ledger",
    )
    all_joins = []
    for row in packet["rows"]:
        fid = row["id"]
        require(
            row["ledger_status_preserved"]
            == ledger_rows[fid]["status"]
            == owners["finding"][fid]["source_status"],
            "actual ledger drift",
        )
        require(
            row["source_closure_owner_literal"]
            == ledger_rows[fid]["closure_owner"]
            == owners["finding"][fid]["source_closure_owner"],
            "actual accountable owner drift",
        )
        require(
            set(row["bundle_ids"])
            == set(findings[fid]["companion_bundles"])
            == set(ledger_rows[fid]["bundle_ids"]),
            "actual bundle links",
        )
        require(
            row["formal_ledger_change"] is False
            and row["finding_owner_acceptance"] == "not decided; historical status unchanged",
            "owner adjudication invented",
        )
        require(
            all(row[k] for k in ["next_owner", "minimal_inputs", "next_verifiable_result"]),
            "owner/input/result absent",
        )
        require(
            row["gate_predicate_basis"]["current_per_ID_predicate"] == row["criterion"],
            "predicate replaced by family proxy",
        )
        for ref in row["original_source_criterion_refs"]:
            data = blob(SOURCE, ref["path"]).decode().splitlines()
            lo, hi = ref["lines"]
            fragment = "\n".join(data[lo - 1 : hi]) + "\n"
            require(
                identity(fragment.encode())["sha256"] == ref["sha256"],
                "original criterion fragment",
            )
            for bid in row["bundle_ids"]:
                card = bundles[bid]["criterion_card"]
                content = blob(SOURCE, card).decode()
                source_tag = "B:" if fid.startswith("B") else "LA:"
                blocks = re.findall(
                    r"<!-- SOURCE_BEGIN "
                    + re.escape(source_tag + fid)
                    + r" -->\s*(.*?)\s*<!-- SOURCE_END "
                    + re.escape(source_tag + fid)
                    + r" -->",
                    content,
                    re.S,
                )
                require(
                    len(blocks) == 1 and blocks[0].strip() == fragment.strip(),
                    "original card full body join",
                )
                require(
                    row["bundle_writers"][bid] == owners["bundle"][bid]["initial_writer_family"],
                    "canonical bundle writer",
                )
                all_joins.append(
                    {
                        "id": fid,
                        "bundle": bid,
                        "source": ref["path"],
                        "lines": ref["lines"],
                        "fragment_sha256": ref["sha256"],
                        "card_blob": git("rev-parse", SOURCE + ":" + card).decode().strip(),
                    }
                )
        chosen = [
            c
            for c in cases["cases"]
            if re.search(
                row["current_oracle_negative"]["current_selector_rule"],
                c["classname"] + "::" + c["name"],
            )
        ]
        require(chosen or fid in {"B201", "B202"}, "missing scoped runtime cases")
        require(
            len(chosen) == row["root_wave_outcome"]["selected_case_counts"]["cases"],
            "per-ID denominator",
        )
    require(len(all_joins) == 55, "55 original body joins")
    for record in index["inputs"]:
        data = blob(record["source_sha"], record["path"])
        require(
            identity(data) == {k: record[k] for k in ["bytes", "sha256"]}, "Git full input bytes"
        )
        require(
            git("rev-parse", record["source_sha"] + ":" + record["path"]).decode().strip()
            == record["git_blob"],
            "Git actual input blob",
        )
    for record in index["portable_inputs"]:
        require(record["evidence_git_commit"] == EVIDENCE, "portable evidence checkpoint")
        require(
            identity(blob(EVIDENCE, record["repository_path"]))
            == {k: record[k] for k in ["bytes", "sha256"]},
            "portable bytes unavailable",
        )
    publication = parse(COMMIT, PR38 + "corrected-wave-publication-validation.json")
    group_rows = []
    for group in publication["copy_groups"]:
        data = blob(EVIDENCE, group["path"])
        require(
            identity(data) == {k: group[k] for k in ["bytes", "sha256"]},
            "authoritative portable index",
        )
        carrier = json.loads(data)
        require(len(carrier["files"]) == group["records"], "portable group record denominator")
        for r in carrier["files"]:
            require(
                identity(blob(EVIDENCE, r["copied_path"]))
                == {k: r[k] for k in ["bytes", "sha256"]},
                "authoritative copied Git bytes",
            )
        group_rows.append(
            {"path": group["path"], "records": len(carrier["files"]), "sha256": group["sha256"]}
        )
    require(
        len(group_rows) == 13 and sum(r["records"] for r in group_rows) == 213,
        "authoritative 13/213 axis",
    )
    wave = check_wave(packet, cases)
    empirical = parse(SOURCE, PR38 + "independent-welfare/native-ge-deciding-artifacts.json")
    semantics = check_semantics(packet, recipes, empirical)
    ir = parse(SOURCE, PR38 + "ir-semantic-owner-decision.json")
    require(
        ir["canonical_owner"] is None
        and ir["decision_state"] == "unratified"
        and len(ir["four_decisions"]) == 4,
        "semantic appointment fabricated",
    )
    ddm_review = parse(SOURCE, PR38 + "independent-reviews/cal-ddm/review.json")
    require(
        ddm_review["reviewer"].startswith("root/doe_r2")
        and ddm_review["families"]["ddm"]["code_verdict"] == "GO_bounded_mechanism",
        "DDM independent acceptance basis",
    )
    ddm_reuse = []
    for path in [
        "policy-engine/src/polisyos/ddm",
        "policy-engine/tests/unit/ddm/test_registry_schema_compatibility.py",
    ]:
        old = git("rev-parse", "4c5afb1dc10b4e3f4dbc10b50ca6066de9b08ccb:" + path).decode().strip()
        current = git("rev-parse", SOURCE + ":" + path).decode().strip()
        require(old == current, "DDM independently reviewed source changed")
        ddm_reuse.append(
            {
                "path": path,
                "Git_object": current,
                "basis": "Independent DoE review; no author self-review",
            }
        )
    controls = []
    edits = [
        ("READY_hash_corrupt", "manifest", lambda x: x["files"][0].update(sha256="0" * 64)),
        ("READY_size_corrupt", "manifest", lambda x: x["files"][0].update(bytes=-1)),
        (
            "wave_source_historical58",
            "packet",
            lambda x: x["common_wave"].update(
                source_sha="58e2d97965c0826c44843a78dcb2f8698d9950a3"
            ),
        ),
        (
            "B202_auto_closed",
            "packet",
            lambda x: next(r for r in x["rows"] if r["id"] == "B202").update(
                proposed_verdict="closed"
            ),
        ),
        (
            "B198_new_partial_proposal",
            "packet",
            lambda x: next(r for r in x["rows"] if r["id"] == "B198").update(
                ledger_status_preserved="partial"
            ),
        ),
        (
            "32_proposals_become_acceptance",
            "packet",
            lambda x: next(r for r in x["rows"] if r["id"] == "B97").update(
                historical_bounded_proposal=False
            ),
        ),
        (
            "DDM_unsupported_keyword",
            "recipes",
            lambda x: next(r for r in x["recipes"] if r["family"] == "ddm")[
                "actual_api_sequence"
            ].__setitem__(0, "build_model_registry_record(schema_version=2)"),
        ),
        (
            "Welfare_failed_support_suppressed",
            "empirical",
            lambda x: x["artifacts"]["receipt_ref"]["content"].update(failed_draw_count=0),
        ),
        (
            "DDM_boolean_institutional_authority",
            "packet",
            lambda x: next(r for r in x["rows"] if r["id"] == "LA-055")[
                "criterion_evidence"
            ].update(state="satisfied_declared_native_generic_scope"),
        ),
        (
            "hash_valid_conditional_as_unconditional",
            "empirical",
            lambda x: x["artifacts"]["propagation_report_ref"]["content"]["draw_summary"].update(
                welfare_mean=2.0
            ),
        ),
    ]
    for name, target, edit in edits:
        changed = copy.deepcopy(
            {"manifest": manifest, "packet": packet, "recipes": recipes, "empirical": empirical}
        )
        edit(changed[target])
        try:
            if target == "manifest":
                check_manifest(changed["manifest"])
            elif name == "wave_source_historical58":
                check_wave(changed["packet"], cases)
            else:
                check_semantics(changed["packet"], changed["recipes"], changed["empirical"])
        except ValueError as error:
            controls.append({"name": name, "outcome": "REFUSED", "reason": str(error)})
        else:
            raise ValueError("metadata property-removal admitted: " + name)
    result = {
        "schema": "e02.E.final_all54_independent_recomputation.v1",
        "disposition": "GO_bounded_metadata_criteria_custody",
        "publication_commit": COMMIT,
        "source_sha": SOURCE,
        "source_tree": TREE,
        "manifest_bytes": total,
        "original_card_joins": all_joins,
        "current_ledger": dict(Counter(r["status"] for r in ledger_rows.values())),
        "Git_inputs": len(index["inputs"]),
        "portable_record_axis": len(index["portable_inputs"]),
        "authoritative_portable_groups": group_rows,
        "actual_wave": wave,
        "semantic_boundaries": semantics,
        "DDM_independent_source_reuse": ddm_reuse,
        "controls": controls,
        "product_tests_run": False,
        "automatic_finding_closures": False,
    }
    sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
