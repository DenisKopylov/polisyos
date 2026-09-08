"""Read visible lane prose and reconcile local Markdown evidence links."""
# ruff: noqa: T201 - bounded read-only handback audit output
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

root = Path.cwd()
documents = [
    root / "docs/superpowers/journals/2026-09-08-gy-phase5-research.md",
    root / "docs/superpowers/plans/2026-09-08-gy-phase5-execution.md",
    root / "docs/superpowers/journals/2026-09-08-gy-phase5-completion.md",
]
out = root / "docs/superpowers/journals/gy-phase5-evidence/shared"
records = []
prose = []
for document in documents:
    visible = []
    fence = None
    for number, line in enumerate(document.read_text().splitlines(), 1):
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if marker:
            token, tail = marker.groups()
            if fence is None:
                fence = token
                continue
            if token[0] == fence[0] and len(token) >= len(fence) and not tail.strip():
                fence = None
                continue
        if fence is None:
            visible.append((number, line))
    links = []
    independently_found = []
    for number, line in visible:
        for match in re.finditer(r"\[([^\]]*)\]\((<[^>]+>|[^)]*)\)", line):
            links.append((number, match.group(1), match.group(2)))
        offset = 0
        while (middle := line.find("](", offset)) != -1:
            beginning = line.rfind("[", offset, middle)
            end = line.find(")", middle + 2)
            if beginning == -1 or end == -1:
                break
            independently_found.append((
                number, line[beginning + 1:middle], line[middle + 2:end]
            ))
            offset = end + 1
    resolved = []
    for number, label, raw_target in links:
        target = raw_target.strip()
        if target.startswith("<") and target.endswith(">"):
            target = target[1:-1]
        else:
            target = target.split(' "', 1)[0]
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc:
            continue
        path_text = unquote(parsed.path)
        path_text = re.sub(r":\d+$", "", path_text)
        path = (document.parent / path_text).resolve() if path_text else document
        resolved.append({
            "line": number, "label": label, "target": raw_target,
            "resolved": str(path), "fragment": parsed.fragment,
            "exists": path.exists(), "is_file": path.is_file(),
        })
    records.append({
        "document": str(document),
        "fence_closed": fence is None,
        "link_parser_identity_sets_equal": set(links) == set(independently_found),
        "regex_only": sorted(set(links) - set(independently_found)),
        "scanner_only": sorted(set(independently_found) - set(links)),
        "local_links": resolved,
    })
    prose.append("\n".join(
        [f"DOCUMENT {document}"] + [f"{number}: {line}" for number, line in visible]
    ))
(out / "handback-link-audit.json").write_text(json.dumps(records, indent=2) + "\n")
(out / "handback-link-audit-visible.txt").write_text("\n\n".join(prose) + "\n")
evidence_records = []
evidence_prose = []
evidence_paths = {
    Path(link["resolved"])
    for record in records for link in record["local_links"]
    if link["is_file"] and "gy-phase5-evidence" in Path(link["resolved"]).parts
}
recovered_links = []
for record in records:
    for link in record["local_links"]:
        if link["exists"]:
            continue
        relative = (
            "pr1/n8-owner-assignment.json"
            if link["target"] == "../pr1/n8-owner-assignment.json"
            else "pa1/" + Path(link["target"]).name
        )
        candidate = out.parent / relative
        recovered_links.append({
            "document": record["document"], "line": link["line"],
            "original_target": link["target"],
            "suggested_target": "gy-phase5-evidence/" + relative,
            "exists": candidate.is_file(), "path": str(candidate),
        })
        if candidate.is_file():
            evidence_paths.add(candidate)
(out / "handback-link-audit-recovered.json").write_text(
    json.dumps(recovered_links, indent=2) + "\n"
)
for path in sorted(evidence_paths):
    raw = path.read_bytes()
    decoded = raw.decode("utf-8")
    record = {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()}
    if path.suffix == ".json":
        try:
            data = json.loads(decoded)
            if isinstance(data, dict):
                record.update({
                    key: value for key, value in data.items()
                    if key in {
                        "returncode", "elapsed_seconds", "command", "cwd", "status",
                        "source_commit", "head_commit", "branch", "revision",
                    }
                })
                stdout = data.get("stdout", "")
                if isinstance(stdout, str):
                    record["stdout_terminal_lines"] = stdout.splitlines()[-14:]
                record["stderr"] = data.get("stderr")
            record["json_readable"] = True
        except json.JSONDecodeError as error:
            record["json_readable"] = False
            record["error"] = str(error)
    else:
        evidence_prose.append(f"DOCUMENT {path}\n" + "\n".join(
            f"{number}: {line}" for number, line in enumerate(decoded.splitlines(), 1)
        ))
    evidence_records.append(record)
(out / "handback-link-audit-evidence.json").write_text(
    json.dumps(evidence_records, indent=2) + "\n"
)
(out / "handback-link-audit-evidence-visible.txt").write_text(
    "\n\n".join(evidence_prose) + "\n"
)
print(json.dumps({
    "documents": [record["document"] for record in records],
    "all_fences_closed": all(record["fence_closed"] for record in records),
    "independent_link_identity_sets_equal": all(
        record["link_parser_identity_sets_equal"] for record in records
    ),
    "missing_or_nonfile_targets": [
        {"document": record["document"], **link}
        for record in records for link in record["local_links"]
        if not link["exists"] or not link["is_file"]
    ],
}, indent=2))
