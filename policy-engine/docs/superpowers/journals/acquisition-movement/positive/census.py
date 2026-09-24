"""Read-only census with one complete disclosure envelope for success and failure.

Run from the repository or product root. Detailed AST records are raw data;
stdout and the receipt file carry the same verdict and complete input disclosure.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[6]
OUT = Path(__file__).parent / "raw"
SOURCE = ROOT / "policy-engine/docs/superpowers/journals/uninvoked/census.py"
sys.path.insert(0, str(ROOT / "policy-engine"))
from tools.lib.fs import measure_file_reads, measured_read_bytes  # noqa: E402

TARGETS = {
    "WorldBankWDIAcquisitionExecutionPort",
    "build_production_world_bank_wdi_execution_port",
    "AcquisitionOwnerExecutionResult",
    "admit_acquisition_with_production_semantic_epoch",
    "admit_acquisition_with_semantic_epoch",
    "build_admission_passport",
    "activate_semantic_epoch",
    "ActivatedSemanticEpochAdmissionReceipt",
    "AcquisitionOverlayReentryReceipt",
    "commit_acquisition_reentry",
    "reenter_after_acquisition",
    "persist_world_commit_and_reenter",
    "resume_world_committed_reentry",
    "SemanticEpochQualificationAdapter",
    "EpochChronologyPolicyOwner",
    "from_unallocated_policy_authority",
    "compose_production_semantic_epoch_admission",
}
MODULES = {"acquisition_epoch_admission", "acquisition_surface_execution", "acquisition_reentry"}
TOKENS = (
    "world_committed",
    "activatedsemanticepochadmissionreceipt",
    "acquisition_reentry",
    "admit_acquisition_with_production_semantic_epoch",
    "qualification",
)


def main() -> int:
    """Run the existing measuring procedure and disclose all partial/error boundaries."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-prefix", default="census-disclosure")
    args = parser.parse_args()
    if Path(args.output_prefix).name != args.output_prefix:
        parser.error("output-prefix must be a filename component")
    git_reads = []
    selected = []
    tree_selected = []
    excluded = []
    records = []
    findings = None
    failure = None
    module = types.ModuleType("existing_census")
    module.__file__ = str(SOURCE)

    def git(*arguments: str) -> bytes:
        nonlocal selected, tree_selected, excluded
        result = subprocess.run(  # noqa: S603 - Fixed read-only Git operations from the owner.
            ["git", *arguments],  # noqa: S607 - Preserve the existing owner Git entry point.
            cwd=ROOT,
            capture_output=True,
            check=False,
        )
        git_reads.append(
            {
                "command": ["git", *arguments],
                "cwd": str(ROOT),
                "exit_code": result.returncode,
                "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(),
                "stderr": result.stderr.decode("utf-8", errors="replace"),
            }
        )
        if result.returncode:
            raise RuntimeError("git_input_unavailable")
        if arguments[0] in {"ls-files", "ls-tree"}:
            paths = sorted({value.decode() for value in result.stdout.split(b"\0") if value})
            admitted = [
                path
                for path in paths
                if path.startswith("policy-engine/src/") and path.endswith(".py")
            ]
            if arguments[0] == "ls-files":
                selected = admitted
                admitted_set = set(admitted)
                excluded = [path for path in paths if path not in admitted_set]
            else:
                tree_selected = admitted
        return result.stdout

    class MeasuredPath(Path):
        def read_bytes(self) -> bytes:
            return measured_read_bytes(Path(str(self)))

    with measure_file_reads(ROOT) as reads:
        try:
            # Read/execute the exact existing owner, without changing its measure predicates.
            owner_bytes = measured_read_bytes(SOURCE)
            exec(compile(owner_bytes, str(SOURCE), "exec"), module.__dict__)  # noqa: S102 - Fixed measured owner.
            module.TARGETS = TARGETS
            module.MODULES = MODULES
            module.git = git
            findings, complete = module.measure(MeasuredPath(ROOT), "HEAD")
            records = complete["records"]
            lexical = {token: [] for token in TOKENS}
            for path in sorted(complete["source_hashes"]):
                body = measured_read_bytes(ROOT / path)
                if hashlib.sha256(body).hexdigest() != complete["source_hashes"][path]:
                    raise ValueError("source_changed_between_ast_and_lexical_reads")
                for line_number, line in enumerate(body.decode("utf-8-sig").splitlines(), 1):
                    for token in TOKENS:
                        if token in line.casefold():
                            lexical[token].append(
                                {
                                    "path": path,
                                    "line": line_number,
                                    "case_sensitive_match": token in line,
                                    "text": line.strip(),
                                }
                            )
            findings["case_insensitive_matches"] = lexical
            if findings["crosscheck_differences"]:
                raise ValueError("ast_token_interpretation_disagreement")
        except Exception as error:
            failure = {"error_type": type(error).__name__, "message": str(error)}
            # The owner retains already-observed AST events in its frame on a failed read.
            # Preserve these as partial findings, never reconstruct a successful full result.
            traceback = error.__traceback__
            while traceback is not None:
                frame = traceback.tb_frame
                if frame.f_globals is module.__dict__ and frame.f_code.co_name == "measure":
                    records = list(frame.f_locals.get("records", []))
                    findings = {
                        "partial_counts": dict(frame.f_locals.get("count", {})),
                        "interpretation_boundary": "owner did not complete selected input set",
                    }
                traceback = traceback.tb_next
        disclosure = reads.snapshot(complete_verdict=failure is None)
    unresolved = [
        {
            "class": "outside_source_selector",
            "property": "excluded paths may contain other mechanisms; no claim about them",
            "excluded_paths": excluded,
        },
        {
            "class": "runtime_receiver_dispatch",
            "property": "static syntax does not resolve receiver instances",
        },
        {"class": "dynamic_import_reflection", "property": "computed dispatch remains undecided"},
        {
            "class": "unselected_authority_documents",
            "property": "institutional appointment is not measured",
        },
        {
            "class": "external_production_data",
            "property": "this is not a current live production instance",
        },
        {
            "class": "bootstrap_imports_and_git_internals",
            "property": (
                "explicit file/Git outputs are observed; "
                "interpreter imports and Git internal reads are not"
            ),
        },
    ]
    if failure is not None:
        unresolved.append(
            {
                "class": "selected_input_or_interpretation_incomplete",
                "property": "no complete absence verdict",
                "failure": failure,
            }
        )
    OUT.mkdir(parents=True, exist_ok=True)
    detail = OUT / (args.output_prefix + "-records.jsonl")
    with detail.open("w", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, separators=(",", ":")) + "\n")
    receipt = {
        "schema_version": "research.census.disclosure.v1",
        "status": "UNRUN" if failure else "COMPLETE",
        "complete_verdict": failure is None,
        "finding_coverage": "partial_coverage" if failure else "complete_selected_inputs",
        "executing_party": "positive_research agent; recomputed relative to this holder",
        "predeclared_counterexample": (
            "A non-test composition bypasses quarantine/qualification under another alias; "
            "insensitive variant included."
        ),
        "selectors": {
            "path": "complete tracked policy-engine/src/**/*.py",
            "file_type": ".py",
            "exclusions": "outside-selector tracked paths; untracked files; external state",
        },
        "denominator": {
            "selected_paths": selected,
            "selected_count": len(selected),
            "independent_tree_paths": tree_selected,
            "index_tree_equal": selected == tree_selected,
        },
        "file_reads": disclosure,
        "git_reads": git_reads,
        "unresolved_by_construction": unresolved,
        "failure": failure,
        "findings": findings,
        "raw_records": {
            "path": str(detail.relative_to(ROOT)),
            "sha256": hashlib.sha256(detail.read_bytes()).hexdigest(),
            "meaning": "raw AST events; all verdicts require this disclosure envelope",
        },
    }
    rendered = json.dumps(receipt, indent=2) + "\n"
    (OUT / (args.output_prefix + ".json")).write_text(rendered)
    sys.stdout.write(rendered)
    return 1 if failure else 0


if __name__ == "__main__":
    raise SystemExit(main())
