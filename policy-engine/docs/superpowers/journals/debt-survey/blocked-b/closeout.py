"""Check the B survey record against its complete declared evidence denominators."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path.cwd()
BASE = "fc823071a7b6f2c9a573172aec3499ad6d138c0f"
JOURNAL = Path("docs/superpowers/journals/debt-survey")
DOCUMENT = Path("docs/superpowers/specs/2026-09-11-debt-nature-survey-blocked-b.md")


def git(*args):
    return subprocess.check_output(["git", *args], text=True).strip()


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


assert git("branch", "--show-current") == "codex/debt-nature-survey"
assert not git("diff", BASE, "--name-only", "--", "src", "tests", "tools", "architecture")
manifest = json.loads((JOURNAL / "denominator/reconciliation.json").read_text())
expected = sorted(r["id"] for r in manifest["nonterminal"] if r["section"] == "B" and r["status"] == "blocked")
live = {r["id"] for r in manifest["nonterminal"] if r["status"] in ("blocked", "open")}
text = DOCUMENT.read_text()
block = re.findall(r"```json\n(\[.*?\])\n```", text, re.S)
assert len(block) == 1
rows = json.loads(block[0])
ids = [r["id"] for r in rows]
assert len(ids) == len(set(ids)) and sorted(ids) == expected
headers = re.findall(r"^### `([^`]+)`$|^## B-W5 — `([^`]+)`$", text, re.M)
account_ids = [a or b for a, b in headers]
assert len(account_ids) == len(set(account_ids)) and sorted(account_ids) == expected
required = {"id", "premise_false", "q1", "q2", "appointment_effect", "engineering", "allocation", "reduction_peers", "property", "class", "evidence", "confidence", "unknowns"}
allowed = {
    "premise_false": {"yes", "no", "unestablished"},
    "appointment_effect": {"none_on_blocked_capability", "changes_reachable_slot", "unestablished", "not_institutional"},
    "engineering": {"complete", "incomplete", "unestablished"},
    "allocation": {"yes", "no", "unestablished"},
    "confidence": {"measured", "inferred", "unestablished"},
}
for row in rows:
    assert set(row) == required, row["id"]
    assert set(row["class"]) == {"mechanism", "missing_work", "holder"}
    assert row["q1"] and row["q2"] and row["property"] and row["unknowns"]
    assert set(row["reduction_peers"]) <= live
    for key, values in allowed.items():
        assert row[key] in values, (row["id"], key)

w5_rows = [line.split("|")[1].strip() for line in text.splitlines() if line.startswith("| W5-")]
assert len(w5_rows) == len(set(w5_rows))
assert sorted(w5_rows) == sorted(manifest["w5_ground_truth"]["unique_routes"])
routing = Path("docs/research/policy-operations/consolidation/wave5/wave5-routing-map.md").read_text()
route_map = [line.split("|")[1].strip() for line in routing.splitlines() if line.startswith("| W5-")]
assert all(route_map.count(route) == 1 for route in w5_rows)

citations = sorted(set(re.findall(r"`([^`\n]+)@([0-9a-f]{9,40})(?::\d+)?`", text)))
tree_paths = set(git("ls-tree", "-r", "--name-only", "--full-tree", BASE).splitlines())
for path, sha in citations:
    assert BASE.startswith(sha), (path, sha)
    assert "policy-engine/" + path in tree_paths, path

evidence_keys = sorted({key for row in rows for key in row["evidence"]} | {"public-existing-tests", "ds15-existing-tests", "epoch-existing-tests"})
receipts = {}
for key in evidence_keys:
    lane, label = key.split(":", 1) if ":" in key else ("blocked-b", key)
    entry = json.loads((JOURNAL / lane / "receipts.json").read_text())[label]
    output = Path(entry["complete_output"])
    assert digest(output) == entry["sha256"], key
    receipts[key] = {"exit_code": entry["exit_code"], "complete_output": str(output), "sha256": entry["sha256"]}

lex_receipt = json.loads((JOURNAL / "blocked-b/raw/lex-current-rows-v2.txt").read_text().split("\n", 1)[1])
for key in ("complete_selected_rows", "complete_unresolved_id_sequence"):
    entry = lex_receipt[key]
    assert digest(Path(entry["path"])) == entry["sha256"]
    assert len(json.loads(Path(entry["path"]).read_text())) == entry["records"]

print(json.dumps({
    "record_only_not_product_completion": True,
    "base": BASE,
    "branch": git("branch", "--show-current"),
    "document": str(DOCUMENT),
    "document_sha256": digest(DOCUMENT),
    "complete_B_blocked_ids": expected,
    "assessment_and_independent_heading_identity_equal": True,
    "rows": len(rows),
    "complete_W5_routes": sorted(w5_rows),
    "W5_master_and_independent_routing_map_equal": True,
    "W5_count": len(w5_rows),
    "assessment_distributions": {key: dict(sorted(Counter(r[key] for r in rows).items())) for key in allowed},
    "source_citations": [path + "@" + sha for path, sha in citations],
    "all_citations_resolve_at_source_base": True,
    "source_test_tool_architecture_diff_from_base_empty": True,
    "complete_deciding_outputs_verified": receipts,
    "complete_current_Lex_denominator_arrays_verified": True,
    "broader_product_gates": "UNRUN in B; root owns shared gate receipts",
}, indent=2))
