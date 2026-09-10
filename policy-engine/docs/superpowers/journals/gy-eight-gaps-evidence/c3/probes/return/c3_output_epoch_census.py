"""Read-only complete tracked text census for the causal output epoch companion."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tomllib
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCOPES = ("src", "tests", "tools", "architecture", "docs/reference")
PREFIX = "scientist.node_run_causal_evaluation@"
VERSION_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._+-")
PATTERN = re.compile(re.escape(PREFIX) + r"[A-Za-z0-9._+-]+")


def tracked() -> set[str]:
    raw = subprocess.check_output(["git", "ls-files", "-z", "--", *SCOPES], cwd=ROOT)
    return {os.fsdecode(path) for path in raw.split(b"\0") if path}


def digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def main() -> int:
    families = tomllib.loads((ROOT / "architecture/generated_artifacts.toml").read_text())["family"]

    def owner_context(name: str, actual_hash: str) -> dict:
        if not name.startswith("architecture/"):
            return {"owner": "current_companion"}
        claims = [family for family in families if name in family.get("outputs", [])]
        if len(claims) != 1:
            return {"owner": "registration_unresolved", "claiming_families": [x.get("id") for x in claims]}
        family = claims[0]
        historical = family.get("lifecycle") == "source_committed"
        pin = family.get("source_integrity_sha256", {}).get(name)
        return {
            "owner": "registered_source_committed_record" if historical else "registered_current_generated_artifact",
            "family_id": family["id"], "lifecycle": family.get("lifecycle"),
            "registered_integrity": pin,
            "registered_integrity_matches": pin == actual_hash if pin is not None else None,
            "interpretation": "Registration is custody; inspect the pin's role before treating a historical observation as a current consumer.",
        }

    names = tracked()
    physical = {
        str((Path(directory) / name).relative_to(ROOT))
        for scope in SCOPES
        for directory, _children, files in os.walk(ROOT / scope)
        for name in files
    }
    missing = sorted(names - physical)
    read_failures: list[dict[str, str]] = []
    first_text: set[str] = set()
    second_text: set[str] = set()
    nontext: list[dict[str, str]] = []
    hashes: dict[str, str] = {}
    first: set[tuple[str, int, int, str]] = set()
    second: set[tuple[str, int, int, str]] = set()
    for name in sorted(names & physical):
        path = ROOT / name
        try:
            raw = path.read_bytes()
            hashes[name] = digest(raw)
            try:
                source = raw.decode("utf-8")
            except UnicodeDecodeError:
                nontext.append({"path": name, "classification": "non_utf8"})
                source = None
            if source is not None and "\0" in source:
                nontext.append({"path": name, "classification": "nul_binary"})
                source = None
            if source is not None:
                first_text.add(name)
                for line_number, line in enumerate(source.splitlines(), 1):
                    for match in PATTERN.finditer(line):
                        first.add((name, line_number, match.start() + 1, match.group()))
            # Independent streaming decode/prefix scan, not the regex result.
            streamed: list[tuple[str, int, int, str]] = []
            is_text = True
            try:
                with path.open("r", encoding="utf-8", newline="") as handle:
                    for line_number, line in enumerate(handle, 1):
                        if "\0" in line:
                            is_text = False
                        position = 0
                        while (start := line.find(PREFIX, position)) >= 0:
                            end = start + len(PREFIX)
                            while end < len(line) and line[end] in VERSION_CHARS:
                                end += 1
                            if end > start + len(PREFIX):
                                streamed.append((name, line_number, start + 1, line[start:end]))
                            position = max(end, start + 1)
            except UnicodeDecodeError:
                is_text = False
            if is_text:
                second_text.add(name)
                second.update(streamed)
        except OSError as exc:
            read_failures.append({"path": name, "classification": "ambiguous", "reason": repr(exc)})
    changed = sorted(name for name, expected in hashes.items() if digest((ROOT / name).read_bytes()) != expected)
    final_names = tracked()
    print(json.dumps({
        "scope": list(SCOPES),
        "denominator": {
            "all_tracked_files": len(names),
            "physical_tracked_files": len(names & physical),
            "utf8_text_byte_decode": len(first_text),
            "utf8_text_stream_decode": len(second_text),
            "file_types": dict(sorted(Counter(Path(name).suffix or "<none>" for name in names).items())),
            "nontext": nontext,
        },
        "all_input_content_hash": digest(json.dumps(hashes, sort_keys=True, separators=(",", ":")).encode()),
        "missing_tracked": missing,
        "unreadable": read_failures,
        "text_identity_difference": sorted(first_text ^ second_text),
        "pin_identity_difference": sorted(first ^ second),
        "pin_count_regex": len(first),
        "pin_count_prefix_scan": len(second),
        "pins": [
            {"path": name, "line": line, "column": column, "pin": pin, "source_ref": name + "@" + hashes[name],
             **owner_context(name, hashes[name])}
            for name, line, column, pin in sorted(first)
        ],
        "changed_during_read": changed,
        "tracking_identity_difference": sorted(names ^ final_names),
    }, indent=2))
    return int(bool(missing or read_failures or first_text != second_text or first != second or changed or names != final_names))


if __name__ == "__main__":
    raise SystemExit(main())
