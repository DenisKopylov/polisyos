"""Read-only identity, receipt and change-scope audit of the survey artifacts."""
from __future__ import annotations

import collections
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[5]
BASE = "fc823071a7b6f2c9a573172aec3499ad6d138c0f"
JOURNAL = ROOT / "docs/superpowers/journals/debt-survey"
SPECS = ROOT / "docs/superpowers/specs"
STEM = "2026-09-11-debt-nature-survey"


def run(*args: str) -> str:
    return subprocess.check_output(args, cwd=ROOT, text=True)


def assessment(stream: str) -> list[dict]:
    source = (SPECS / f"{STEM}-{stream}.md").read_text()
    blocks = re.findall(r"```json\n(.*?)\n```", source, re.S)
    candidates = [json.loads(block) for block in blocks]
    return next(x for x in candidates if isinstance(x, list) and x and "id" in x[0])


def main() -> None:
    manifest = json.loads((JOURNAL / "denominator/reconciliation.json").read_text())
    expected = {r["id"]: r for r in manifest["nonterminal"] if r["status"] in {"open", "blocked"}}
    found = {}
    streams = {}
    blocked = []
    for stream in ("blocked-ac", "blocked-b", "open"):
        source = (SPECS / f"{STEM}-{stream}.md").read_text()
        # Independent heading grammars: a regex and line token processing.
        ids = re.findall(r"^(?:## B-[A-Z0-9]+ — |### (?:\d+\. )?|## )`([^`]+)`(?: \([A-Z]\))?\s*$", source, re.M)
        other = []
        for line in source.splitlines():
            if line.startswith("## ") or line.startswith("### "):
                body = line.split(" ", 1)[1]
                if body.startswith("B-") and " — " in body:
                    body = body.split(" — ", 1)[1]
                if re.match(r"^\d+\. ", body):
                    body = body.split(" ", 1)[1]
                if body.endswith((" (A)", " (B)", " (C)")):
                    body = body[:-4]
                if body.startswith("`") and body.endswith("`") and body.count("`") == 2:
                    other.append(body[1:-1])
        assert ids == other, (stream, ids, other)
        assert len(ids) == len(set(ids)), stream
        wanted = {k for k, r in expected.items() if
                  (stream == "open" and r["status"] == "open") or
                  (stream == "blocked-ac" and r["status"] == "blocked" and r["section"] in {"A", "C"}) or
                  (stream == "blocked-b" and r["status"] == "blocked" and r["section"] == "B")}
        assert set(ids) == wanted, (stream, sorted(set(ids) ^ wanted))
        assert not set(ids).intersection(found), stream
        found.update({k: stream for k in ids})
        streams[stream] = {"count": len(ids), "ids": sorted(ids)}
        if stream != "open":
            rows = assessment(stream)
            assert {r["id"] for r in rows} == wanted and len(rows) == len(wanted)
            blocked.extend(rows)
    assert set(found) == set(expected)
    master = (SPECS / f"{STEM}.md").read_text()
    unknowns = master.split("## 8. What could not be established", 1)[1]
    unknown_ids = re.findall(r"^\| `([^`]+)` \| (?:blocked-ac|blocked-b|open) \|", unknowns, re.M)
    assert set(unknown_ids) == set(expected) and len(unknown_ids) == 62
    assert re.findall(r"^## ([1-8])\.", master, re.M) == list("12345678")
    assert "Pending the indexed" not in master
    pinned_paths = set(run("git", "ls-tree", "-r", "--name-only", BASE, "--", ".").splitlines())
    citations = []
    citation_errors = []
    for file in sorted(SPECS.glob(f"{STEM}*.md")):
        for path, sha in re.findall(r"`([a-zA-Z0-9_/.-]+\.[a-zA-Z0-9]+)@([a-f0-9]{7,40})(?=[:`])", file.read_text()):
            # Source citations at base; other hashes can cite this survey's immutable commits.
            if BASE.startswith(sha):
                if path not in pinned_paths:
                    citation_errors.append((file.name, path, sha))
            else:
                run("git", "cat-file", "-e", f"{sha}:policy-engine/{path}")
            citations.append({"document": file.name, "path": path, "sha": sha})
    assert not citation_errors, citation_errors
    collection = (JOURNAL / "final/raw/cg2-case-denominator.txt").read_text()
    cases = [line for line in collection.splitlines() if line.startswith("tests/") and "::" in line]
    test_paths = sorted({case.split("::")[0] for case in cases})
    walked, visited = set(), set()
    for path in test_paths:
        tree = ast.parse((ROOT / path).read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
                walked.add(path + "::" + node.name)

        class Definitions(ast.NodeVisitor):
            def visit_FunctionDef(self, node):
                if node.name.startswith("test_"):
                    visited.add(path + "::" + node.name)
                self.generic_visit(node)

            visit_AsyncFunctionDef = visit_FunctionDef

        Definitions().visit(tree)
    collected_definitions = {case.split("[", 1)[0] for case in cases}
    assert walked == visited == collected_definitions
    assert len(cases) == len(set(cases)) == 31
    distributions = {}
    for field in ("premise_false", "appointment_effect", "engineering", "allocation", "confidence"):
        groups = {}
        for row in blocked:
            groups.setdefault(row[field], []).append(row["id"])
        counter = collections.Counter(row[field] for row in blocked)
        assert counter == {key: len(values) for key, values in groups.items()}
        assert sum(counter.values()) == 35
        distributions[field] = {key: {"count": len(values), "ids": sorted(values)} for key, values in sorted(groups.items())}
    receipts = []
    for index in sorted(JOURNAL.glob("*/receipts.json")):
        for label, record in json.loads(index.read_text()).items():
            path = ROOT / record["complete_output"]
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            assert actual == record["sha256"], (index, label)
            assert run("git", "check-ignore", str(path)).strip(), path
            receipts.append({"stream": index.parent.name, "label": label,
                             "exit_code": record["exit_code"], "sha256": actual})
    changed = run("git", "diff", BASE, "--name-only").splitlines()
    allowed_specs = {f"policy-engine/docs/superpowers/specs/{STEM}{suffix}.md" for suffix in ("", "-open", "-blocked-ac", "-blocked-b")}
    prohibited = [p for p in changed if p not in allowed_specs and
                  not p.startswith("policy-engine/docs/superpowers/journals/debt-survey/")]
    assert not prohibited, prohibited
    assert not any("/raw/" in p for p in run("git", "ls-files", ":(top)policy-engine/docs/superpowers/journals/debt-survey").splitlines())
    print(json.dumps({"base": BASE, "identity_agreement": True, "live_denominator": 62,
                      "streams": streams, "ambiguous_retained": manifest["unclassifiable_ids"],
                      "blocked_denominator": 35, "blocked_assessment_distributions": distributions,
                      "unknown_identity_agreement": True, "source_citations_verified": citations,
                      "cg2_denominator": {"cases": cases, "source_paths": test_paths,
                                          "ast_definition_ids": sorted(walked), "identity_equal": True},
                      "receipts_verified": receipts, "changed_paths": changed,
                      "prohibited_changes": prohibited}, indent=2))


if __name__ == "__main__":
    main()
