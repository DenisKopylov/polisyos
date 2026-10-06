from __future__ import annotations

import datetime
import hashlib
import json
import os
import subprocess
import sys
import tarfile
import time
from collections import Counter
from pathlib import Path

import tools.quality.validation.schema_fqn_census as census
from tools.lib.fs import measure_file_reads, measured_read_bytes


BASE = Path(
    "/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/"
    ".tmp/e02-C2/raw/installed/schema-b8"
)
ARCHIVE = BASE / "candidate.tar"
WHEEL = BASE / "dist/policy_engine-0.1.0-py3-none-any.whl"
CORPUS = BASE / "outside-corpus"
COMMAND_DIR = BASE / "outside-commands"
PYTHON = BASE / "venv-base/bin/python"
COMMAND_DIR.mkdir(parents=True, exist_ok=True)
if CORPUS.exists():
    raise SystemExit(f"refusing to overwrite corpus: {CORPUS}")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_file(path: Path) -> str:
    return digest(path.read_bytes())


def save_command(name: str, argv: list[str], cwd: Path, env: dict[str, str], timeout: int):
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    tick = time.monotonic()
    proc = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, timeout=timeout)
    finished = datetime.datetime.now(datetime.timezone.utc).isoformat()
    duration = time.monotonic() - tick
    stem = f"{len(commands) + 1:02d}-{name}"
    stdout_path = COMMAND_DIR / f"{stem}.stdout"
    stderr_path = COMMAND_DIR / f"{stem}.stderr"
    exit_path = COMMAND_DIR / f"{stem}.exit"
    stdout_path.write_bytes(proc.stdout)
    stderr_path.write_bytes(proc.stderr)
    exit_path.write_text(f"{proc.returncode}\n", encoding="ascii")
    commands.append(
        {
            "name": name,
            "argv": argv,
            "cwd": str(cwd.resolve()),
            "environment_delta": {"PYTHONPATH": "unset", "PYTHONHOME": "unset"},
            "timeout_seconds": timeout,
            "started_at_utc": started,
            "finished_at_utc": finished,
            "duration_seconds": duration,
            "exit_code": proc.returncode,
            "stdout": {"path": str(stdout_path), "bytes": len(proc.stdout), "sha256": digest_file(stdout_path)},
            "stderr": {"path": str(stderr_path), "bytes": len(proc.stderr), "sha256": digest_file(stderr_path)},
            "exit": {"path": str(exit_path), "sha256": digest_file(exit_path)},
        }
    )
    return proc


commands: list[dict[str, object]] = []
CORPUS.mkdir(parents=True)
source_files: dict[str, bytes] = {}
with tarfile.open(ARCHIVE, "r:") as archive:
    for member in archive.getmembers():
        if member.isfile() and not member.name.startswith("policy-engine/"):
            stream = archive.extractfile(member)
            if stream is None:
                raise SystemExit(f"cannot read source member {member.name}")
            source_files[member.name] = stream.read()
if len(source_files) != 28:
    raise SystemExit(f"outside-product source denominator changed: {len(source_files)}")
suffixes = Counter(Path(path).suffix.lower() or "<no-extension>" for path in source_files)
expected_suffixes = {
    "<no-extension>": 4,
    ".md": 2,
    ".yml": 17,
    ".json": 1,
    ".py": 2,
    ".sh": 1,
    ".toml": 1,
}
if dict(suffixes) != expected_suffixes:
    raise SystemExit(f"outside-product file-type denominator changed: {dict(suffixes)}")
for relative, data in source_files.items():
    path = CORPUS / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)

git_env = os.environ.copy()
git_env.pop("PYTHONPATH", None)
git_env.pop("PYTHONHOME", None)
git_env["GIT_CONFIG_NOSYSTEM"] = "1"
for name, argv in [
    ("git-init", ["git", "init", "--quiet"]),
    ("git-user-email", ["git", "config", "user.email", "schema-b8-outside@example.invalid"]),
    ("git-user-name", ["git", "config", "user.name", "Schema b8 outside corpus"]),
    ("git-add", ["git", "add", "--all"]),
    ("git-commit", ["git", "commit", "--quiet", "-m", "exact outside-product archive inputs"]),
]:
    proc = save_command(name, argv, CORPUS, git_env, 30)
    if proc.returncode:
        raise SystemExit(f"{name} failed: {proc.stderr.decode(errors='replace')}")
head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=CORPUS, capture_output=True, check=True, text=True).stdout.strip()
index = subprocess.run(["git", "ls-files", "--cached", "-z", "--", "."], cwd=CORPUS, capture_output=True, check=True).stdout
indexed_paths = sorted(os.fsdecode(item) for item in index.split(b"\0") if item)
if indexed_paths != sorted(source_files):
    raise SystemExit("outside-corpus indexed paths do not equal the exact archive denominator")

env = os.environ.copy()
env.pop("PYTHONPATH", None)
env.pop("PYTHONHOME", None)
argv = [str(PYTHON), "-I", "-m", "tools.quality.validation.schema_fqn_census", "--repo-root", str(CORPUS)]
proc = save_command("installed-outside-product-corpus", argv, Path("/private/tmp"), env, 120)
if proc.returncode:
    raise SystemExit(f"installed outside corpus census failed: {proc.stderr.decode(errors='replace')}")
receipt = json.loads(proc.stdout)
if receipt["result"] != "complete_for_selected_local_text_inputs":
    raise SystemExit(f"outside corpus census incomplete: {receipt['result']}")
if receipt["git_enumeration"]["tracked_path_count"] != 28:
    raise SystemExit("installed corpus did not report the exact 28-file tracked denominator")
if receipt["selection"]["selected_path_count"] != 27 or receipt["selection"]["excluded_path_count"] != 1:
    raise SystemExit("installed selector did not report 27 selected files plus one exclusion")
excluded = receipt["selection"]["excluded_paths"]
if excluded != [{"path": ".github/CODEOWNERS", "reason": "unsupported_filename_or_suffix"}]:
    raise SystemExit(f"unexpected external path exclusion: {excluded!r}")

# The instrument's own selector omits this one text file. Bind its exact archive
# bytes, then run the installed instrument's FQN/resource pattern tables directly.
codeowners_path = CORPUS / ".github/CODEOWNERS"
with measure_file_reads(CORPUS) as measurement:
    raw = measured_read_bytes(codeowners_path)
    text = raw.decode("utf-8")
    codeowners_receipt = measurement.snapshot(complete_verdict=True)
fqn_hits = []
for target, pattern in census._FQN_PATTERNS.items():
    fqn_hits.extend({"target": target, "matched_value": match.group(0)} for match in pattern.finditer(text))
resource_hits = []
for target, patterns in census._RESOURCE_PATTERNS.items():
    for pattern in patterns:
        resource_hits.extend(
            {"target": target, "matched_value": match.group(0)}
            for match in pattern.finditer(text)
        )
if fqn_hits or resource_hits:
    raise SystemExit(f"outside selector-excluded CODEOWNERS contains target references: {fqn_hits!r} {resource_hits!r}")

report = {
    "candidate": {
        "commit": "b8d9115cdc6a55920c1e0a3cae2e5f9092010c27",
        "tree": "467cd6f01ec204767dc60bb939955578428bf102",
        "source_archive_sha256": digest_file(ARCHIVE),
        "wheel_sha256": digest_file(WHEEL),
    },
    "outside_product_denominator": {
        "archive_paths": 28,
        "file_type_counts": dict(sorted(suffixes.items())),
        "git_index_paths": len(indexed_paths),
        "exact_archive_path_set": True,
        "all_28_files_byte_equal_archive": all(digest_file(CORPUS / path) == digest(data) for path, data in source_files.items()),
        "fixture_git_head": head,
    },
    "installed_instrument": {
        "module": "tools.quality.validation.schema_fqn_census",
        "result": receipt["result"],
        "tracked_paths": receipt["git_enumeration"]["tracked_path_count"],
        "selected_paths": receipt["selection"]["selected_path_count"],
        "decoded_utf8_inputs": receipt["scanned_denominator"]["decoded_utf8_inputs"],
        "excluded_paths": excluded,
        "dynamic_loader_count": len(receipt["dynamic_loader_sites"]),
        "unresolved_nonliteral_loader_count": sum(
            site["status"] == "unresolved_nonliteral_target" for site in receipt["dynamic_loader_sites"]
        ),
        "target_match_counts": {target["fqn"]: len(target["matches"]) for target in receipt["targets"]},
        "complete_only_for_selected_local_text_inputs": True,
    },
    "selector_exclusion_supplement": {
        "path": ".github/CODEOWNERS",
        "sha256": digest(raw),
        "bytes": len(raw),
        "read_receipt": codeowners_receipt,
        "installed_instrument_fqn_matches": fqn_hits,
        "installed_instrument_resource_matches": resource_hits,
        "target_references_found": False,
        "python_ast_loader_scan_applicable": False,
    },
    "commands": commands,
    "installed_census_stdout_sha256": digest(proc.stdout),
    "installed_census_stdout_bytes": len(proc.stdout),
}
report_path = BASE / "outside-repo-results.json"
report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(
    json.dumps(
        {
            "report_path": str(report_path),
            "report_sha256": digest_file(report_path),
            "tracked": report["installed_instrument"]["tracked_paths"],
            "selected": report["installed_instrument"]["selected_paths"],
            "excluded": excluded,
            "dynamic_loaders": report["installed_instrument"]["dynamic_loader_count"],
            "fqn_matches": report["installed_instrument"]["target_match_counts"],
        },
        sort_keys=True,
    )
)
