"""Complete tracked Python/JSON/TOML census for the governed D1 version delta."""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import subprocess


SUFFIXES = {".py", ".json", ".toml"}
PATTERN = re.compile(
    r"(?<![A-Za-z0-9_.])(?:"
    r"policyos\.policy_design_case\.layer3_gy\.n9_promotion\.v\d+"
    r"|polisyos\.policy_design_case\.layer3_gy\.n9_obligation_scope\.v\d+"
    r"|polisyos\.runtime\.quality\.promotion_sequence\.canonical_promotion_receipt_verification_projection\.v\d+"
    r"|policyos\.gy\.fabric_measurement_root\.v\d+)(?![A-Za-z0-9_.])"
)


def git(*args):
    return subprocess.check_output(["git", *args]).decode().split("\0")


def main():
    index = {p for p in git("ls-files", "-z", "--cached", "--others", "--exclude-standard")
             if Path(p).suffix in SUFFIXES and Path(p).is_file()}
    tree = {p for p in git("ls-tree", "-r", "--name-only", "-z", "HEAD") if Path(p).suffix in SUFFIXES}
    reconciled = set(tree)
    prefix = subprocess.check_output(["git", "rev-parse", "--show-prefix"]).decode().strip()
    status = git("status", "--porcelain=v1", "-z", "--untracked-files=all", "--", ".")
    cursor=0
    while cursor < len(status):
        row=status[cursor];cursor+=1
        if not row: continue
        code,path=row[:2],row[3:].removeprefix(prefix)
        if "R" in code or "C" in code:
            previous=status[cursor].removeprefix(prefix);cursor+=1
            if "R" in code: reconciled.discard(previous)
        if Path(path).suffix in SUFFIXES:
            if "D" in code: reconciled.discard(path)
            else: reconciled.add(path)
    assert index == reconciled, {"current_only": sorted(index-reconciled), "head_status_only": sorted(reconciled-index)}
    hashes={}
    by_line = set()
    by_whole_text = set()
    unreadable = []
    for path in sorted(index):
        try:
            raw = Path(path).read_bytes()
            hashes[path]=hashlib.sha256(raw).hexdigest()
            content = raw.decode("utf-8")
        except (OSError, UnicodeError) as error:
            unreadable.append({"path": path, "type": type(error).__name__})
            continue
        for line_no, line in enumerate(content.splitlines(), 1):
            for match in PATTERN.finditer(line):
                by_line.add((path, line_no, match.start(), match.group()))
        for match in PATTERN.finditer(content):
            line_no = content.count("\n", 0, match.start()) + 1
            column = match.start() - content.rfind("\n", 0, match.start()) - 1
            by_whole_text.add((path, line_no, column, match.group()))
    assert by_line == by_whole_text, {
        "line_only": sorted(by_line-by_whole_text),
        "whole_only": sorted(by_whole_text-by_line),
    }
    assert hashes == {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in index}, "source_changed_nonreceipt"
    print(json.dumps({
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip(),
        "denominator": {"index": dict(Counter(Path(p).suffix for p in index)),
                        "head_tree": dict(Counter(Path(p).suffix for p in tree)),
                        "independent_head_plus_status": dict(Counter(Path(p).suffix for p in reconciled))},
        "denominator_identity_sets_equal": index == reconciled,
        "path_denominator": "complete current product .py/.json/.toml, tracked plus nonignored new files",
        "source_hashes_stable": True,
        "match_identity_sets_equal": by_line == by_whole_text,
        "literal_counts": dict(sorted(Counter(item[3] for item in by_line).items())),
        "unreadable": unreadable,
    }, sort_keys=True))
    grouped = defaultdict(lambda: defaultdict(list))
    for path, line, column, value in sorted(by_line):
        grouped[path][value].append([line, column])
    for path, values in sorted(grouped.items()):
        print(json.dumps({"path": path, "literal_locations": values}, sort_keys=True))
    assert not unreadable, "ambiguous_unreadable_case"


if __name__ == "__main__":
    main()
