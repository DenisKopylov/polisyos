"""Enumerate all tracked K epoch references without reading the prohibited registers."""

from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess


root = Path.cwd()
excluded = {"docs/plans/active/DEBT-REGISTER.md", "docs/plans/active/LEDGER.md"}
suffixes = {".py", ".json", ".toml", ".md"}
all_paths = subprocess.check_output(["git", "ls-files", "-z"], text=True).split("\0")
selected = {path for path in all_paths if path and Path(path).suffix in suffixes and path not in excluded}
second = subprocess.check_output(["git", "ls-files", "-z", "--", "*.py", "*.json", "*.toml", "*.md"], text=True).split("\0")
independent = {path for path in second if path and path not in excluded}
assert selected == independent
keys = (
    "layer3_gy_openalex_accuracy_report.json", "layer3_gy_openalex_skg_ingest_records.json",
    "layer3_gy_openalex_accuracy_report_v2.json", "layer3_gy_openalex_skg_ingest_records_v2.json",
    "openalex_accuracy_report.v1", "openalex_skg_ingest_records.v1", "openalex_accuracy.v1",
    "openalex_accuracy_report.v2", "openalex_skg_ingest_records.v2",
    "evaluate_openalex_claim_extractor_accuracy", "ExtractorAccuracyReport",
    "build_real_agent_accuracy_payload", "_evaluate_gold_span_support_accuracy",
    "check_layer3_gy_openalex_artifacts",
)
matches = []
unreadable = []
for relative in sorted(selected):
    try:
        raw = (root / relative).read_bytes()
        value = raw.decode("utf-8")
    except (OSError, UnicodeError) as exc:
        unreadable.append({"path": relative, "error": str(exc)})
        continue
    locations = {key: [index for index, line in enumerate(value.splitlines(), 1) if key in line] for key in keys if key in value}
    if locations:
        matches.append({"path": relative, "sha256": hashlib.sha256(raw).hexdigest(), "locations": locations})
print(json.dumps({
    "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
    "complete_tracked_file_type_denominator": dict(sorted(Counter(Path(path).suffix for path in selected).items())),
    "independent_git_glob_denominator": dict(sorted(Counter(Path(path).suffix for path in independent).items())),
    "full_file_identity_sets_equal": selected == independent,
    "excluded_without_reading": sorted(excluded), "unreadable": unreadable, "complete_matches": matches,
}, indent=2), flush=True)
assert not unreadable, "unreadable members make epoch census incomplete"
