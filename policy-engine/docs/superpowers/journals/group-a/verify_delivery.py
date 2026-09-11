"""Verify this research delivery and its retained evidence, without product imports.

This is a documentation/receipt check, not a product gate or an adjudication.
Complete output is written beside this instrument; stdout is a compact receipt.
"""
from __future__ import annotations

import ast
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
SPEC = ROOT / "policy-engine/docs/superpowers/specs"
BASE = "63bdb9640e7b76b49356cba940bab6067f1be512"
PREFIX = "2026-09-11-group-a-"
REPORT_NAMES = [
    PREFIX + "01-correspondence-destinations.md",
    PREFIX + "02-done-when-clauses.md",
    PREFIX + "03-phase5-findings.md",
    PREFIX + "04-ceiling-vocabularies.md",
    PREFIX + "05-scope-adjudication.md",
    PREFIX + "06-worktree-registrations.md",
]
INDEX_NAME = PREFIX + "analysis-index.md"
OUTPUT = HERE / "delivery-verification.json"
errors: list[str] = []
checks: list[dict] = []


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def require(condition: bool, identity: str, evidence=None) -> None:
    checks.append({"check": identity, "satisfied": bool(condition), "evidence": evidence})
    if not condition:
        errors.append(identity)


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def read_json(name: str):
    return json.loads((HERE / name).read_text())


def allowed(path: str) -> bool:
    return path.startswith(relative(HERE) + "/") or path in {
        relative(SPEC / name) for name in REPORT_NAMES + [INDEX_NAME]
    }


branch = git("symbolic-ref", "--quiet", "--short", "HEAD").decode().strip()
head = git("rev-parse", "HEAD").decode().strip()
require(branch == "codex/group-a-analysis", "exact_branch_attachment", branch)
require(git("rev-parse", "--show-toplevel").decode().strip() == str(ROOT), "exact_worktree_root", str(ROOT))
changed = sorted(set(git("diff", "--name-only", "-z", BASE).decode().split("\0")) - {""})
untracked = sorted(set(git("ls-files", "--others", "--exclude-standard", "-z").decode().split("\0")) - {""})
require(all(allowed(p) for p in changed + untracked), "all_changes_inside_research_allowlist", {
    "changed_since_base": changed, "nonignored_untracked": untracked,
    "outside_allowlist": [p for p in changed + untracked if not allowed(p)],
})

found = sorted(p.name for p in SPEC.glob(PREFIX + "*.md"))
require(found == sorted(REPORT_NAMES + [INDEX_NAME]), "exact_six_reports_plus_index", found)
report_receipts = []
citations = set()
local_paths = set()
links = []
raw_citations = {}
for name in REPORT_NAMES + [INDEX_NAME]:
    path = SPEC / name
    if not path.exists():
        errors.append("missing report: " + name)
        continue
    source = path.read_text()
    sections = re.findall(r"^## ([1-5])\. (.+)$", source, re.M)
    if name in REPORT_NAMES:
        require([n for n, _ in sections] == list("12345"), "ordered_five_sections:" + name, sections)
        prefix = source.split("## 1.", 1)[0].strip()
        require(prefix == source.splitlines()[0], "discrepancy_before_other_prose:" + name)
    require(not re.search(r"^#+\s+recommendations?\b", source, re.I | re.M), "no_recommendations_section:" + name)
    report_receipts.append({"path": relative(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    for token in re.findall(r"`([^`\n]+)`", source):
        match = re.fullmatch(r"(policy-engine/[^@]+)@([0-9a-f]{7,40}\^?)", token)
        if match:
            citations.add(match.groups())
        raw_match = re.fullmatch(r"(policy-engine/[^@]+)@sha256:([0-9a-f]{64})", token)
        if raw_match:
            raw_citations[raw_match[1]] = raw_match[2]
        if token.startswith("policy-engine/") and "@" not in token and not any(x in token for x in ("*", " ")):
            local_paths.add(token)
    for target in re.findall(r"\[[^\]\n]+\]\(([^)\n]+)\)", source):
        if "://" not in target and not target.startswith("#"):
            destination = (path.parent / target.split("#", 1)[0]).resolve()
            # The output is created by this invocation; all other links must exist now.
            exists = destination.exists() or destination == OUTPUT
            links.append({"from": relative(path), "target": target, "exists": exists})
            require(exists, "local_link:" + name + ":" + target)

citation_receipts = []
for path, ref in sorted(citations):
    proc = subprocess.run(["git", "cat-file", "-e", f"{ref}:{path}"], cwd=ROOT, capture_output=True, text=True)
    require(proc.returncode == 0, "pinned_citation:" + path + "@" + ref, proc.stderr or None)
    citation_receipts.append({"path": path, "ref": ref, "exit_code": proc.returncode})
for path in sorted(local_paths):
    require((ROOT / path).exists(), "named_local_path:" + path)

# All instruments and compact JSON receipts, not an arbitrary selection.
python_paths = sorted(p for p in HERE.rglob("*.py") if "raw" not in p.parts)
json_paths = sorted(p for p in HERE.rglob("*.json") if "raw" not in p.parts and p != OUTPUT)
for path in python_paths:
    try:
        ast.parse(path.read_text(), filename=str(path))
    except (SyntaxError, UnicodeError, OSError) as exc:
        errors.append(f"instrument parse: {relative(path)}: {exc}")
for path in json_paths:
    try:
        json.loads(path.read_text())
    except (ValueError, UnicodeError, OSError) as exc:
        errors.append(f"receipt parse: {relative(path)}: {exc}")

hash_receipts = []
hashes = dict(raw_citations)
for name, key in [
    ("01-correspondence/document-census.json", "raw"),
    ("03-phase5/measurement.json", "raw"),
    ("04-vocabularies/summary.json", "raw_receipt"),
    ("06-worktrees/summary.json", "raw_receipt"),
    ("06-worktrees/final/summary.json", "raw_receipt"),
]:
    item = read_json(name)[key]
    hashes[item["path"]] = item["sha256"]
scope = read_json("05-scope/census-receipt.json")
hashes[relative(HERE / "05-scope" / scope["trace_receipt"]["path"])] = scope["trace_receipt"]["sha256"]
hashes.update(read_json("02-clauses/evaluation.json")["raw_receipts"])
hashes.update(read_json("04-vocabularies/distribution.json")["inputs"])
for path, expected in sorted(hashes.items()):
    actual = hashlib.sha256((ROOT / path).read_bytes()).hexdigest() if (ROOT / path).is_file() else None
    require(actual == expected, "retained_receipt_hash:" + path)
    hash_receipts.append({"path": path, "expected": expected, "measured": actual})

all_raw = sorted(relative(p) for p in HERE.rglob("*") if p.is_file() and "raw" in p.relative_to(HERE).parts)
ignored = subprocess.run(["git", "check-ignore", "--stdin", "-z"], cwd=ROOT, input=("\0".join(all_raw) + "\0").encode(), capture_output=True)
ignored_paths = set(ignored.stdout.decode().split("\0")) - {""}
require(ignored_paths == set(all_raw), "every_raw_file_gitignored", {"raw_paths": all_raw, "not_ignored": sorted(set(all_raw) - ignored_paths)})
tracked = set(git("ls-files", "-z").decode().split("\0")) - {""}
require(not set(all_raw) & tracked, "no_raw_file_tracked", sorted(set(all_raw) & tracked))

# Reconcile reported arithmetic against every member of its retained owner set.
routes = read_json("01-correspondence/document-census.json")
require(routes["w5_rows"] == routes["w5_unique"] == 106 and routes["independent_route_enumerations_equal"], "all_w5_rows_reconciled")
require(len(routes["institutional_routes"]) == 18 and len({r["route"] for r in routes["institutional_routes"]}) == 18, "all_eighteen_institutional_routes")
require(routes["phase5_table_rows"] == len(routes["phase5_rows"]) == 14 and routes["independent_phase5_enumerations_equal"], "all_fourteen_journal_findings")
require(routes["tracked_markdown_denominator"] == 1830 and routes["markdown_enumerations_equal"], "markdown_membership_reconciled")
clause = read_json("02-clauses/measurement.json")
require(clause["evidence_json_denominator"] == clause["evidence_walk_json_denominator"] == 452 and not clause["evidence_parse_errors"], "all_historical_json_receipts_readable")
require(clause["selected_receipt_denominator"] == len(read_json("02-clauses/selected-receipts.json")) == 12 and not clause["selected_missing"], "all_twelve_selected_receipts")
evaluation = read_json("02-clauses/evaluation.json")
require(len(evaluation["canonical_requests"]) == 3 and evaluation["independent_request_and_artifact_denominators_equal"] and evaluation["recomputed_rate"] == {"numerator": 0, "denominator": 1, "value": 0.0} and not evaluation["fixture_job_intersection_with_production"], "j_complete_production_population")
ledger = evaluation["ledger_parser_probe"]
require(sum(ledger["status_census"].values()) == ledger["complete_table_rows"] == 77 and ledger["work_output_identical"] and ledger["status_census_identical"], "ledger_section_removal_probe")
require(evaluation["f1_denominator_with_worker"] == len(evaluation["f1_surface_tuple"]) + 1 == 7, "f1_complete_surface_classes")
density = read_json("04-vocabularies/summary.json")
exact = read_json("04-vocabularies/exact-case-density.json")
distribution = read_json("04-vocabularies/distribution.json")
packages = distribution["complete_source_package_distribution"]
require(len(packages) == 26 and sum(r["python_files"] for r in packages) == 2653, "all_source_package_denominators")
for term, expected in zip(distribution["four_terms"], [169, 132, 0, 0], strict=True):
    require(sum(r[term]["exact_case_files"] for r in packages) == exact["terms"][term]["exact_case_files"] == len(exact["terms"][term]["rows"]) == expected, "exact_density:" + term)
    require(sum(r[term]["ast_identifier_files"] for r in packages) == density["density"][term]["identifier_nodes"]["files"], "ast_density_files:" + term)
    require(sum(r[term]["ast_identifier_nodes"] for r in packages) == sum(density["density"][term]["identifier_nodes"]["by_package_nodes"].values()), "ast_density_nodes:" + term)
require(sum(bool(r["normative"]["exact_case_files"]) for r in packages) == 12, "complete_normative_nonzero_package_count")
dup = read_json("03-phase5/duplicates-crosscheck.json")
require(dup["python_file_denominator"] == density["python_files"] == 6178 and dup["all_input_bytes_match_base"] and dup["first_census_counts_agree"] and dup["first_census_duplicates_agree"] and not dup["errors"], "independent_duplicate_algorithms_and_source_binding")
counts = dup["counts"]
require(counts["dict_literals"] == 64845 and counts["key_slots"] == counts["literal"] + counts["nonliteral"] + counts["unpacks"] == 199171 and not dup["duplicate_pairs"], "complete_literal_key_denominator")
trace = read_json("03-phase5/measurement.json")
require(trace["readable_text_denominator"] + trace["unreadable_text_denominator"] == trace["tracked_path_denominator"] == distribution["whole_tree_index_denominator"] == 12900 and distribution["whole_tree_list_equals_index_excluding_analysis"], "complete_text_and_tree_denominators")
for path, values in scope["denominators"].items():
    require(values["ls_tree_count"] == values["archive_count"], "scope_tree_archive_agreement:" + path, values)

worktree = read_json("06-worktrees/final/summary.json")
rows = worktree["registrations"]
selected = [r for r in rows if r["dry_run_selected"]]
existing = [r for r in rows if r["directory_exists"]]
require(len(rows) + 1 == worktree["porcelain_total"] == worktree["admin_plus_main_total"] == 77 and worktree["path_set_equal"], "all_current_registrations_reconciled")
require(len(selected) == worktree["missing_directory_count"] == worktree["dry_run_selected_count"] == 53 and len(existing) + 1 == 24 and not set(r["registration"] for r in selected) & set(r["registration"] for r in existing), "exact_prune_and_existing_directory_sets")
require(dict(Counter(r["branch_disposition"] for r in selected)) == worktree["selected_branch_distribution"] == {"merged_into_pinned_main": 43, "detached_commit_in_main": 10}, "every_selected_branch_or_detached_head_classified")
require(all(worktree[k] for k in ["metadata_stable_through_prune_dry_run", "metadata_stable_through_off_path_scan", "main_stable"]), "temporal_snapshot_stable")
raw_worktree = json.loads((ROOT / worktree["raw_receipt"]["path"]).read_text())
prune_commands = [c for c in raw_worktree["commands"] if c["argv"][1:3] == ["worktree", "prune"]]
require(len(prune_commands) == 1 and "--dry-run" in prune_commands[0]["argv"] and prune_commands[0]["returncode"] == 0, "only_retained_prune_command_is_dry_run")

result = {
    "measured_utc": datetime.now(timezone.utc).isoformat(), "base": BASE,
    "branch_observed": branch, "head_before_delivery_commit": head,
    "scope": "research delivery verification; no product behavior or adjudication verdict",
    "report_denominator": report_receipts, "citation_denominator": citation_receipts,
    "local_link_denominator": links,
    "instrument_denominator": [relative(p) for p in python_paths],
    "compact_json_denominator_excluding_this_output": [relative(p) for p in json_paths],
    "retained_hash_denominator": hash_receipts, "checks": checks, "errors": errors,
    "exit_code": 0 if not errors else 1,
}
OUTPUT.write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps({"receipt": relative(OUTPUT), "report_files": len(report_receipts), "pinned_citations": len(citation_receipts), "instruments": len(python_paths), "compact_json": len(json_paths), "retained_hashes": len(hash_receipts), "checks": len(checks), "errors": errors, "exit_code": result["exit_code"]}, indent=2))
raise SystemExit(result["exit_code"])
