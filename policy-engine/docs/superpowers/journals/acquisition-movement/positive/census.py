"""Bounded read-only source census; reuses the existing full AST/token instrument."""

import importlib.util
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[6]
OUT = Path(__file__).parent / "raw"
SOURCE = ROOT / "policy-engine/docs/superpowers/journals/uninvoked/census.py"
spec = importlib.util.spec_from_file_location("existing_census", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.TARGETS = {
    "WorldBankWDIAcquisitionExecutionPort", "build_production_world_bank_wdi_execution_port",
    "AcquisitionOwnerExecutionResult", "admit_acquisition_with_production_semantic_epoch",
    "admit_acquisition_with_semantic_epoch", "build_admission_passport",
    "activate_semantic_epoch", "ActivatedSemanticEpochAdmissionReceipt",
    "AcquisitionOverlayReentryReceipt", "commit_acquisition_reentry", "reenter_after_acquisition",
    "persist_world_commit_and_reenter", "resume_world_committed_reentry",
    "SemanticEpochQualificationAdapter", "EpochChronologyPolicyOwner",
    "from_unallocated_policy_authority", "compose_production_semantic_epoch_admission",
}
module.MODULES = {"acquisition_epoch_admission", "acquisition_surface_execution", "acquisition_reentry"}
summary, complete = module.measure(ROOT, "HEAD")
summary["executing_party"] = "positive_research agent; recomputed relative to this holder"
summary["predeclared_counterexample"] = (
    "A non-test composition constructs world_committed or activated admission, or calls "
    "the same-case re-entry under another alias, bypassing the production quarantine."
)
summary["unresolved_by_construction"] = [
    "runtime_receiver_dispatch: static call records do not resolve receiver instances",
    "dynamic_import_reflection: computed symbol dispatch remains undecided",
    "unselected_authority_documents: source census does not establish institution appointment",
    "external_production_data: source census is not a current live data instance",
]
# Independent Git tree denominator already reconciled by owner; explicit insensitive lexical
# search reads every selected source member, retaining actual content identities in complete.
tokens = ("world_committed", "activatedsemanticepochadmissionreceipt", "acquisition_reentry",
          "admit_acquisition_with_production_semantic_epoch", "qualification")
lexical = {token: [] for token in tokens}
for path in sorted(complete["source_hashes"]):
    content = (ROOT / path).read_text(encoding="utf-8-sig")
    for line_number, line in enumerate(content.splitlines(), 1):
        for token in tokens:
            if token in line.casefold():
                lexical[token].append({"path": path, "line": line_number,
                    "case_sensitive_match": token in line, "text": line.strip()})
summary["case_insensitive_matches"] = lexical
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "census-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
(OUT / "census-complete.json").write_text(json.dumps(complete, separators=(",", ":")) + "\n")
print(json.dumps({key: value for key, value in summary.items()
                 if key not in {"targets", "module_imports", "case_insensitive_matches"}}, indent=2))
