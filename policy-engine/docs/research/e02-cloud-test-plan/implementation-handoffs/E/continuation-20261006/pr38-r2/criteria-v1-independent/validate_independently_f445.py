#!/usr/bin/env python3
(
    "Read-only exact-input checks for the all"  # Exact bound literal continuation.
    "54 closeout packet.\n\nThis verifies prove"  # Exact bound literal continuation.
    "nance, denominator, old/current evidence"  # Exact bound literal continuation.
    " and negative controls.\nIt does not infe"  # Exact bound literal continuation.
    "r finding closure, source-law authority,"  # Exact bound literal continuation.
    " or a new numerical wave.\n"  # Exact bound literal continuation.
)

import argparse
import copy
import hashlib
import json
import pathlib
import re
import runpy
import shutil
import subprocess
import sys
from pathlib import Path


def _resolve_executable(name: str) -> str:
    (
        "Resolve an admitted executable and refus"  # Exact bound literal continuation.
        "e an unavailable program before invocati"  # Exact bound literal continuation.
        "on."  # Exact bound literal continuation.
    )
    resolved = shutil.which(name)
    if resolved is None:
        raise RuntimeError(f"required utility executable unavailable: {name}")
    return str(Path(resolved).resolve())


def _write_stdout(*values: object, flush: bool = False) -> None:
    (
        "Emit the existing CLI text and optionall"  # Exact bound literal continuation.
        "y flush without logging side effects."  # Exact bound literal continuation.
    )
    sys.stdout.write(" ".join(str(value) for value in values) + "\n")
    if flush:
        sys.stdout.flush()


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise ValueError(reason)


def digest(data: object) -> dict[str, object]:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def _admit_require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


_NO_PATH = object()


def admit_source(sha: object, path: object = _NO_PATH) -> None:
    """Refuse unbound or option-like Git objects before any child process."""
    _admit_require(
        isinstance(sha, str) and re.fullmatch(r"[0-9a-f]{40}", sha) is not None,
        "source requires an exact commit SHA",
    )
    if path is not _NO_PATH:
        _admit_require(isinstance(path, str) and bool(path), "source path requires a string")
        _admit_require(
            not any(character.isspace() or character == "\0" for character in path),
            "source path contains ambiguous characters",
        )
        relative = Path(path)
        _admit_require(
            not relative.is_absolute()
            and bool(relative.parts)
            and relative.as_posix() == path
            and ".." not in relative.parts,
            "source path must be repository relative",
        )
        _admit_require(not path.startswith("-") and ":" not in path, "source path is ambiguous")


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


def git(repo: object, *args: str) -> bytes:
    _admit_git_object_arguments(args)
    _admit_require(
        len(args) == 2 and args[0] in {"show", "rev-parse"},
        "only read-only object Git commands admitted",
    )
    if ":" in args[1]:
        sha, path = args[1].split(":", 1)
        admit_source(sha, path)
    else:
        admit_source(args[1].removesuffix("^{tree}"))
    return subprocess.check_output([_resolve_executable("git"), "-C", str(repo), *args])  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit


def load_git(repo: object, sha: str, path: object) -> object:
    return json.loads(git(repo, "show", sha + ":" + path))


def original_card_join(packet: object, repo: object) -> object:
    admit_source(packet["input_snapshot_sha"])
    for row in packet["rows"]:
        for ref in row["original_source_criterion_refs"]:
            admit_source(packet["input_snapshot_sha"], ref["path"])
        for card_ref in row["original_card_refs"]:
            card_path, source_sha = card_ref.rsplit("@", 1)
            admit_source(source_sha, card_path)
    matches = []
    for row in packet["rows"]:
        fid = row["id"]
        tag = ("LA:" if fid.startswith("LA-") else "B:") + fid
        ref = row["original_source_criterion_refs"][0]
        lines = (
            git(repo, "show", packet["input_snapshot_sha"] + ":" + ref["path"])
            .decode()
            .splitlines()
        )
        start, end = ref["lines"]
        original = "\n".join(lines[start - 1 : end]).strip()
        for card_ref in row["original_card_refs"]:
            card_path, source_sha = card_ref.rsplit("@", 1)
            card = git(repo, "show", source_sha + ":" + card_path).decode()
            match = re.search(
                r"<!-- SOURCE_BEGIN "
                + re.escape(tag)
                + r" -->\n(.*?)<!-- SOURCE_END "
                + re.escape(tag)
                + r" -->",
                card,
                re.S,
            )
            require(
                match is not None and match.group(1).strip() == original,
                "original card/source criterion mismatch:" + fid,
            )
            matches.append(
                {
                    "id": fid,
                    "card": card_path,
                    "source_sha": source_sha,
                    "inclusive_lines": ref["lines"],
                    "body_matches_original": True,
                }
            )
    require(len(matches) == 55, "original card/source denominator must be 55 links")
    return matches


def validate_indexed_blob(repo: object, sha: str, record: object) -> None:
    data = git(repo, "show", sha + ":" + record["git_path"])
    require(
        digest(data) == {"bytes": record["bytes"], "sha256": record["sha256"]},
        "publication index mismatch:" + record["git_path"],
    )


def evidence_correction(repo: object, sha: str) -> dict[str, object]:
    base = (
        "policy-engine/docs/research/e02-cloud-test-plan/implementati"
        "on-handoffs/E/continuation-20261006/"
    )
    correction = load_git(repo, sha, base + "pr38-r2/evidence-correction.json")
    summary_path = base + "common-wave/summary.json"
    summary_data = git(repo, "show", sha + ":" + summary_path)
    require(
        digest(summary_data) == correction["current_summary"],
        "corrective summary bytes/hash mismatch",
    )
    summary = json.loads(summary_data)
    require(
        summary["candidate_sha"] == correction["historical_source_sha"],
        "historical wave silently retagged to new source",
    )
    original = git(repo, "show", correction["historical_published_head"] + ":" + summary_path)
    require(
        digest(original) == correction["superseded_summary"],
        "superseded publication identity mismatch",
    )
    stdout_path = base + "common-wave/workspace-verify-after-browser.stdout.txt"
    stdout = git(repo, "show", sha + ":" + stdout_path)
    require(
        hashlib.sha256(stdout).hexdigest() == correction["raw_stdout_sha256"],
        "raw stdout changed during summary correction",
    )
    require(
        stdout == git(repo, "show", correction["historical_published_head"] + ":" + stdout_path),
        "historical original stdout bytes differ",
    )
    lint_rows = re.findall(rb"^- (src/[^:]+):[0-9]+ \[ARCH[0-9]+\]", stdout, re.M)
    require(
        len(lint_rows) == correction["corrected_workspace_rows"] == 21,
        "actual workspace lint row denominator mismatch",
    )
    require(
        len(set(lint_rows)) == correction["corrected_workspace_paths"] == 17,
        "actual workspace lint path denominator mismatch",
    )
    indices = []
    for suffix in [
        "common-wave/copy-index.json",
        "final-closeout-review/copy-index.json",
    ]:
        index = load_git(repo, sha, base + suffix)
        for record in index["files"]:
            validate_indexed_blob(repo, sha, record)
        indices.append(
            {
                "path": base + suffix,
                "indexed_files": len(index["files"]),
                "state": "PASS",
            }
        )
    final_review = load_git(repo, sha, base + "final-closeout-review/review-58e2d97965c0.json")
    require(
        final_review["full_output_integrity"]["receipt_and_stdout_hashes"]["summary.json"]
        == correction["current_summary"],
        "final review summary entry still stale",
    )
    return {
        "state": "PASS",
        "actual_lint_rows": len(lint_rows),
        "actual_lint_paths": len(set(lint_rows)),
        "current_summary": digest(summary_data),
        "historical_summary": digest(original),
        "raw_stdout_preserved": True,
        "indices": indices,
        "old_wave_source": summary["candidate_sha"],
        "new_candidate_wave_inferred": False,
    }


def current_recipe_gate(packet: object, recipes: object) -> None:
    require(
        recipes["implementation_sha"] == packet["assembled_source_sha"],
        "current local recipes still bind historical source",
    )
    require(
        recipes["implementation_tree"] == packet["assembled_source_tree"],
        "current local recipes tree does not bind current source",
    )
    for recipe in recipes["recipes"]:
        require(
            recipe["implementation_sha_for_this_recipe"] == packet["assembled_source_sha"],
            "recipe implementation source stale:" + recipe["family"],
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=pathlib.Path, required=True)
    parser.add_argument("--packet-dir", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    args = parser.parse_args()
    packet_path = args.packet_dir / "all-54-update.json"
    index_path = args.packet_dir / "input-index.json"
    validator_path = args.packet_dir / "validate.py"
    recipe_path = args.packet_dir / "current-local-G-recipes.json"
    manifest_path = args.packet_dir / "publication-index.json"
    protected_paths = [
        packet_path,
        index_path,
        validator_path,
        recipe_path,
        manifest_path,
    ]
    manifest = json.loads(manifest_path.read_text())
    for record in manifest["files"]:
        require(
            digest((args.packet_dir / record["path"]).read_bytes())
            == {"bytes": record["bytes"], "sha256": record["sha256"]},
            "immutable packet manifest mismatch:" + record["path"],
        )
    before = {str(path): digest(path.read_bytes()) for path in protected_paths}
    packet = json.loads(packet_path.read_text())
    index = json.loads(index_path.read_text())
    helper = runpy.run_path(str(validator_path))
    metadata = helper["check"](packet, index, args.repo)
    card_matches = original_card_join(packet, args.repo)
    correction = evidence_correction(args.repo, packet["input_snapshot_sha"])
    ddm_review_path = (
        "policy-engine/docs/research/e02-cloud-test-plan/implementati"
        "on-handoffs/E/continuation-20261006/pr38-r2/independent-revi"
        "ews/cal-ddm/review.json"
    )
    ddm_review_data = git(args.repo, "show", packet["input_snapshot_sha"] + ":" + ddm_review_path)
    ddm_review = json.loads(ddm_review_data)
    require(
        "doe_r2" in ddm_review["reviewer"],
        "DDM independent reviewer must be another author",
    )
    require(
        ddm_review["families"]["ddm"]["implementation_sha"]
        == packet["family_evidence"]["DDM"]["implementation_sha"],
        "DDM independent review wrong source",
    )
    require(
        ddm_review["families"]["ddm"]["code_verdict"] == "GO_bounded_mechanism",
        "DDM own author receipt substituted for independent GO",
    )
    controls = []

    def owner(p: object, i: int) -> None:
        next(row for row in p["rows"] if row["id"] == "LA-053")["source_closure_owner_literal"] = (
            "single-author-invented-alias-authority"
        )

    def held(p: object, i: int) -> None:
        next(row for row in p["rows"] if row["id"] == "B201")["proposed_verdict"] = "closed"

    def criterion(p: object, i: int) -> None:
        next(row for row in p["rows"] if row["id"] == "B190")["criterion"] = (
            "Every missing sensitivity is zero and production-certified"
        )

    def input_hash(p: object, i: int) -> None:
        i["inputs"][0]["sha256"] = "0" * 64

    def no_owner(p: object, i: int) -> None:
        next(row for row in p["rows"] if row["id"] == "B194")["next_owner"] = ""

    def source_tree(p: object, i: int) -> None:
        p["assembled_source_tree"] = "0" * 40

    for name, mutator in [
        ("LA053_wrong_actual_closure_owner", owner),
        ("B201_unratified_closed", held),
        ("B190_fake_criterion", criterion),
        ("indexed_input_digest", input_hash),
        ("B194_missing_next_owner", no_owner),
        ("assembled_tree", source_tree),
    ]:
        p, i = copy.deepcopy(packet), copy.deepcopy(index)
        mutator(p, i)
        try:
            helper["check"](p, i, args.repo)
        except ValueError as exc:
            controls.append(
                {
                    "control": name,
                    "state": "REJECTED",
                    "reason": str(exc),
                    "mutation_scope": "in-memory packet only",
                }
            )
        else:
            raise AssertionError("negative accepted:" + name)
    copy_index = load_git(
        args.repo,
        packet["input_snapshot_sha"],
        (
            "policy-engine/docs/research/e02-cloud-test-plan/implementati"
            "on-handoffs/E/continuation-20261006/common-wave/copy-index.j"
            "son"
        ),
    )
    summary_record = next(
        row for row in copy_index["files"] if row["git_path"].endswith("/summary.json")
    )
    for field, value in [("bytes", summary_record["bytes"] + 1), ("sha256", "0" * 64)]:
        record = copy.deepcopy(summary_record)
        record[field] = value
        try:
            validate_indexed_blob(args.repo, packet["input_snapshot_sha"], record)
        except ValueError as exc:
            controls.append(
                {
                    "control": "current_summary_" + field,
                    "state": "REJECTED",
                    "reason": str(exc),
                    "mutation_scope": "in-memory index only",
                }
            )
        else:
            raise AssertionError("negative accepted:summary_" + field)
    ref = packet["local_G_recipe_ref"]
    require(ref == "current-local-G-recipes.json", "unexpected current recipe identity")
    recipes = json.loads(recipe_path.read_text())
    try:
        current_recipe_gate(packet, recipes)
    except ValueError as exc:
        recipe_state = {
            "state": "HOLD_for_current_publication",
            "reason": str(exc),
            "recipe_candidate": recipes["implementation_sha"],
            "packet_candidate": packet["assembled_source_sha"],
            "historical_recipe_preserved": True,
        }
    else:
        recipe_state = {"state": "PASS_current_recipe_source"}
    after = {str(path): digest(path.read_bytes()) for path in protected_paths}
    require(
        before == after,
        "helper packet changed during read-only checks; rerun against frozen bytes",
    )
    output = {
        "schema": "policyos.e02.independent-closeout-check.v1",
        "reviewer": "root/ddm_r2",
        "role": (
            "Independent closeout evidence/criteria review. DDM source au"
            "thor; DDM code review quoted from independent doe_r2, never "
            "self-reviewed."
        ),
        "invocation": sys.argv,
        "input_bytes_before_after_equal": True,
        "inputs": before,
        "packet_source": packet["assembled_source_sha"],
        "packet_tree": packet["assembled_source_tree"],
        "metadata_recomputation": metadata,
        "original_card_source_criterion_matches": card_matches,
        "evidence_correction": correction,
        "independent_DDM_code_review": {
            "path": ddm_review_path,
            "source_sha": packet["input_snapshot_sha"],
            **digest(ddm_review_data),
            "reviewer": ddm_review["reviewer"],
            "implementation_sha": ddm_review["families"]["ddm"]["implementation_sha"],
            "bounded_verdict": ddm_review["families"]["ddm"]["code_verdict"],
            "institutional_authority": "not_established",
        },
        "negative_controls": controls,
        "current_recipe_admission": recipe_state,
        "numerical_wave": "UNRUN; no new mechanism test or global numerical/guard wave performed",
        "formal_ledger_change": False,
        "semantic_ratification": "unratified; no code review ratification",
    }
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    _write_stdout(
        json.dumps(
            {
                "metadata": metadata,
                "source_card_matches": len(card_matches),
                "evidence_correction": correction,
                "negative_control_count": len(controls),
                "current_recipe": recipe_state,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
