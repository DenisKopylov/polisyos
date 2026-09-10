"""Complete current/history outcome reference census; no product imports or writes."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import subprocess

from _build.gy_gaps.c3_scm_reference_census import occurrence_roles

ROOTS = ("src", "tests", "tools", "architecture", "docs/reference")
NEEDLES = ("layer3_gy_outcome_run.json", "layer3_gy_outcome_run_v2.json")
FORBIDDEN = {"DEBT-REGISTER.md", "LEDGER.md"}


def inventory():
    primary = {Path(path) for path in subprocess.check_output([
        "git", "ls-files", "--cached", "--others", "--exclude-standard", "-z", "--", *ROOTS,
    ]).decode().split("\0") if path}
    deleted = {Path(path) for path in subprocess.check_output([
        "git", "ls-files", "--deleted", "-z", "--", *ROOTS,
    ]).decode().split("\0") if path}
    primary -= deleted
    filesystem = set()
    for root in ROOTS:
        for directory, _, files in os.walk(root, onerror=lambda error: (_ for _ in ()).throw(error)):
            filesystem.update(Path(directory) / name for name in files)
    ignored = subprocess.run(["git", "check-ignore", "--stdin", "-z"],
                             input="\0".join(map(str, sorted(filesystem))) + "\0", text=True, capture_output=True)
    assert ignored.returncode in {0, 1}, ignored.stderr
    secondary = filesystem - {Path(path) for path in ignored.stdout.split("\0") if path}
    assert primary == secondary, {"file_identity_delta": sorted(map(str, primary ^ secondary))}
    return primary, secondary


def suffix(path):
    return path.suffix.lower() or "<no_suffix>"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", required=True)
    phase = parser.parse_args().phase
    primary, secondary = inventory()
    excluded = {path for path in primary if path.name in FORBIDDEN}
    paths = sorted(primary - excluded)
    classified = Counter()
    snapshots, texts, ambiguous = {}, {}, []
    for path in paths:
        try:
            raw = path.read_bytes()
        except OSError as exc:
            ambiguous.append({"path": str(path), "reason": "unreadable", "error": type(exc).__name__})
            continue
        snapshots[path] = hashlib.sha256(raw).hexdigest()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            if b"\0" not in raw:
                ambiguous.append({"path": str(path), "reason": "non_UTF8_without_binary_NUL_discriminator"})
                continue
            classified[(suffix(path), "binary_non_UTF8")] += 1
            continue
        if "\0" in text:
            classified[(suffix(path), "binary_NUL")] += 1
        else:
            classified[(suffix(path), "UTF8_text")] += 1
            texts[path] = (text, raw)
    # Every file is accounted for, including prohibited names and unreadable cases.
    assert sum(classified.values()) + len(ambiguous) + len(excluded) == len(primary)
    types_primary = Counter(suffix(path) for path in primary)
    types_secondary = Counter(("." + path.name.rsplit(".", 1)[1]).lower() if "." in path.name and not path.name.startswith(".") else suffix(path) for path in secondary)
    assert types_primary == types_secondary
    references = []
    for needle in NEEDLES:
        found = {path for path, (text, _) in texts.items() if needle in text}
        independently_found = set()
        text_paths = sorted(texts)
        for offset in range(0, len(text_paths), 200):
            checked = subprocess.run(["rg", "--files-with-matches", "--fixed-strings", "--text", "--", needle,
                                      *map(str, text_paths[offset:offset + 200])], text=True, capture_output=True)
            assert checked.returncode in {0, 1}, checked.stderr
            independently_found.update(map(Path, checked.stdout.splitlines()))
        assert found == independently_found, {"reference_identity_delta": sorted(map(str, found ^ independently_found))}
        members = []
        for path in sorted(found):
            text, raw = texts[path]
            locations = {"syntax": "text", "line_numbers": [index for index, line in enumerate(text.splitlines(), 1) if needle in line]}
            if path.suffix in {".py", ".json", ".toml"}:
                try:
                    locations = occurrence_roles(path, raw, needle)
                except (ValueError, SyntaxError) as exc:
                    locations["parsed_location_unavailable"] = type(exc).__name__
            members.append({"path": str(path), "file_type": suffix(path), "sha256": snapshots[path], "locations": locations})
        references.append({"needle": needle, "matching_file_count": len(found),
                           "independent_rg_matching_file_count": len(independently_found), "members": members})
    after_primary, after_secondary = inventory()
    assert after_primary == primary and after_secondary == secondary, "file_population_changed"
    assert all(hashlib.sha256(path.read_bytes()).hexdigest() == digest for path, digest in snapshots.items()), "source_changed"
    output = {
        "phase": phase, "scope": {"roots": ROOTS, "file_types": "all; individually classified below", "forbidden_names_not_read": sorted(map(str, excluded))},
        "current_file_denominator": len(primary), "independent_filesystem_denominator": len(secondary),
        "file_types": dict(sorted(types_primary.items())), "independent_file_types": dict(sorted(types_secondary.items())),
        "classification": [{"file_type": kind, "classification": classification, "count": count} for (kind, classification), count in sorted(classified.items())],
        "text_denominator": len(texts), "ambiguous_cases": ambiguous, "references": references,
        "identity_deltas": [], "source_and_population_unchanged": True,
        "role_limit": "Locations are evidence for owner inspection, not authority. Current consumers, historical observations and retired literals must be classified from actual owner flow; no automatic replacement.",
    }
    print(json.dumps(output, indent=2))
    if ambiguous:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
