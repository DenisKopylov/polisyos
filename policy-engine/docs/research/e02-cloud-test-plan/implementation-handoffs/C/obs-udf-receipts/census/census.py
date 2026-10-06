from __future__ import annotations

import collections
import json
import subprocess
from pathlib import Path

REPO = Path.cwd()
COMMIT = "5afffab19c30d88f6522ca397f622ef9a3135646"
OUT = Path("/Users/deniskopylov/polisyos/.tmp/e02-C2/raw/udf-inventory-owner")
TERMS = {
    "asset_prefix": ("-E", "UKRAINE_DEMOGRAPHY_(TARGETS|PRIORS|DONOR)"),
    "asset_key_strings": ("-E", "ukraine/demography/(targets|priors|donor_pool)"),
    "asset_schema_ids": ("-E", r"ukraine\.demography\.(targets|priors|donor_pool)"),
    "new_targets_path": ("-F", "demography/targets.json"),
    "new_priors_path": ("-F", "demography/transition_priors.json"),
    "new_donor_path": ("-F", "demography/donor_pool.json"),
    "legacy_targets_path": ("-F", "demography_targets.json"),
    "legacy_priors_path": ("-F", "demography_transition_priors.json"),
    "legacy_donor_path": ("-F", "demography_donor_pool.json"),
    "payload_target_totals": ("-F", "target_state_totals"),
    "payload_entrant_totals": ("-F", "entrant_state_totals"),
    "payload_transition_priors": ("-F", "transition_prior_matrix"),
    "payload_allowed_transition_mask": ("-F", "allowed_transition_mask"),
    "payload_donor_weights": ("-F", "donor_weights"),
    "payload_donor_state_index": ("-F", "donor_state_index"),
    "payload_donor_record_index": ("-F", "donor_record_index"),
    "artifact_model": ("-F", "UkraineDemographyArtifacts"),
    "reader_composite": ("-F", "load_demography_artifacts"),
    "reader_targets": ("-F", "load_reconciled_targets"),
    "reader_priors": ("-F", "load_transition_priors"),
    "reader_donor": ("-F", "load_donor_pool"),
}
SOURCE_SUFFIXES = {".py", ".pyi", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".kt", ".rb", ".php", ".sh", ".bash", ".ps1", ".sql"}
CONFIG_SUFFIXES = {".toml", ".ini", ".cfg", ".conf", ".yaml", ".yml", ".json", ".json5", ".jsonc", ".xml", ".env", ".properties", ".lock"}
DOC_SUFFIXES = {".md", ".rst", ".txt", ".adoc"}
DATA_SUFFIXES = {".csv", ".tsv", ".parquet", ".arrow", ".feather", ".xlsx", ".pdf"}


def git(args: list[str], *, input_bytes: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["git", *args], cwd=REPO, input=input_bytes, capture_output=True, check=False)


def file_category(path: str, mode: str, object_type: str) -> str:
    if object_type == "commit":
        return "gitlink"
    if mode == "120000":
        return "symlink"
    suffix = Path(path).suffix.lower()
    if suffix in SOURCE_SUFFIXES:
        return "source_code"
    if suffix in CONFIG_SUFFIXES:
        return "configuration"
    if suffix in DOC_SUFFIXES:
        return "documentation"
    if suffix in DATA_SUFFIXES:
        return "data_or_binary"
    return "other_tracked"


listing = git(["ls-tree", "-r", "-z", "--full-tree", COMMIT])
assert listing.returncode == 0, listing.stderr.decode("utf-8", "replace")
entries = []
for raw in listing.stdout.split(b"\0"):
    if not raw:
        continue
    meta, path_bytes = raw.split(b"\t", 1)
    mode, object_type, oid = meta.decode("ascii").split(" ")
    path = path_bytes.decode("utf-8", "surrogateescape")
    entries.append({"path": path, "mode": mode, "object_type": object_type, "oid": oid, "category": file_category(path, mode, object_type)})
counts = collections.Counter(item["category"] for item in entries)
(OUT / "tracked-tree.stdout.nul").write_bytes(listing.stdout)
(OUT / "tracked-tree.stderr.txt").write_bytes(listing.stderr)

searches = {}
source_code_pathspecs = [f"{COMMIT}", "--", "*.py", "*.pyi", "*.js", "*.mjs", "*.cjs", "*.ts", "*.tsx", "*.jsx", "*.go", "*.rs", "*.java", "*.kt", "*.rb", "*.php", "*.sh", "*.bash", "*.ps1", "*.sql"]
producer_expr = "UKRAINE_DEMOGRAPHY_(TARGETS|PRIORS|DONOR)|demography/(targets|transition_priors|donor_pool)\\.json|demography_(targets|transition_priors|donor_pool)\\.json|target_state_totals|transition_prior_matrix|donor_weights"
for name, (kind, term) in TERMS.items():
    args = ["grep", "-n", "-I", kind, "-e", term, COMMIT, "--"]
    result = git(args)
    searches[name] = {
        "argv": ["git", *args],
        "exit_code": result.returncode,
        "stdout": result.stdout.decode("utf-8", "replace"),
        "stderr": result.stderr.decode("utf-8", "replace"),
        "matching_paths": sorted({line.removeprefix(f"{COMMIT}:").split(":", 1)[0] for line in result.stdout.decode("utf-8", "replace").splitlines()}),
    }
    assert result.returncode in (0, 1), (name, result.stderr.decode("utf-8", "replace"))

source_result = git(["grep", "-n", "-I", "-E", "-e", producer_expr, *source_code_pathspecs])
assert source_result.returncode in (0, 1), source_result.stderr.decode("utf-8", "replace")
source_text = source_result.stdout.decode("utf-8", "replace")
source_lines = []
for line in source_text.splitlines():
    relative = line.removeprefix(f"{COMMIT}:")
    path, lineno, content = relative.split(":", 2)
    source_lines.append({"path": path, "line": int(lineno), "text": content})
source_paths = sorted({item["path"] for item in source_lines})

result = {
    "schema": "policyos.e02.ukraine_demography_tracked_census.v1",
    "target_commit": COMMIT,
    "target_tree": git(["rev-parse", f"{COMMIT}^{{tree}}"]).stdout.decode().strip(),
    "scope": "Every recursive tracked tree entry at the frozen candidate commit is enumerated from git ls-tree. git grep -I searches exact constants, new/legacy file paths, schema fields, public readers, and producer candidate expressions across the complete tracked tree; source-code output lines are separately searched across all tracked source-code suffixes.",
    "denominator": {
        "tracked_tree_entries": len(entries),
        "tracked_file_type_counts": dict(sorted(counts.items())),
        "tracked_source_files": counts["source_code"],
        "tracked_data_or_binary_paths": [item["path"] for item in entries if item["category"] == "data_or_binary"],
        "tracked_candidate_demography_paths": [item["path"] for item in entries if any(part in item["path"] for part in ("demography/targets.json", "demography/transition_priors.json", "demography/donor_pool.json", "demography_targets.json", "demography_transition_priors.json", "demography_donor_pool.json"))],
        "tracked_tree_enumeration_receipt": "tracked-tree.stdout.nul",
        "tracked_configuration_files": counts["configuration"],
        "tracked_documentation_files": counts["documentation"],
        "tracked_data_or_binary_files": counts["data_or_binary"],
        "tracked_gitlinks": counts["gitlink"],
        "gitlink_paths": [item["path"] for item in entries if item["category"] == "gitlink"],
        "symlink_paths": [item["path"] for item in entries if item["category"] == "symlink"],
    },
    "search_commands": searches,
    "producer_candidate_expression": producer_expr,
    "producer_candidate_source_command": ["git", "grep", "-n", "-I", "-E", "-e", producer_expr, *source_code_pathspecs],
    "producer_candidate_source_exit_code": source_result.returncode,
    "producer_candidate_source_output": source_text,
    "producer_candidate_source_paths": source_paths,
    "producer_candidate_source_match_lines": source_lines,
    "complete_tracked_set_enumerated": True,
    "producer_disposition": "Search output is discovery evidence only. Asset registration, tests/fixtures, reader code, and D3 calibrated Parquet artifacts are not treated as demographic target/prior producers unless a tracked runtime path actually emits and versions those target/prior/donor artifacts from identified inputs."
}
(OUT / "source-census.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
summary = {
    "result": "COMPLETE_TRACKED_TREE_CENSUS",
    "target_commit": COMMIT,
    "target_tree": result["target_tree"],
    "denominator": result["denominator"],
    "search_hit_path_counts": {name: len(item["matching_paths"]) for name, item in searches.items()},
    "producer_candidate_paths": source_paths,
    "raw_source_census": str(OUT / "source-census.json"),
}
(OUT / "source-census.stdout.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
(OUT / "source-census.stderr.txt").write_text("", encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
