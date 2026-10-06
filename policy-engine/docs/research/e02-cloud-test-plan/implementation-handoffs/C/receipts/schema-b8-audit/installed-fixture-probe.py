from __future__ import annotations

import datetime
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path


BASE = Path(
    "/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/"
    ".tmp/e02-C2/raw/installed/schema-b8"
)
FIXTURE = BASE / "fixture-run1"
PYTHON = BASE / "venv-base/bin/python"
WHEEL = BASE / "dist/policy_engine-0.1.0-py3-none-any.whl"
ARCHIVE = BASE / "candidate.tar"
COMMAND_DIR = BASE / "fixture-commands"
COMMAND_DIR.mkdir(parents=True, exist_ok=True)
if FIXTURE.exists():
    raise SystemExit(f"refusing to overwrite fixture root: {FIXTURE}")

FIXTURE_FILES = {
    "src/polisyos/data_forge/kernel/schemas/__init__.py": (
        "from .codegen import GeneratedSchemaModule\n"
        "from . import codegen as relative_codegen\n"
        "from polisyos.data_forge.kernel.schemas import codegen as absolute_codegen\n"
    ),
    "src/polisyos/data_forge/kernel/schemas/codegen.py": (
        "class GeneratedSchemaModule: ...\n"
    ),
    "src/polisyos/data_forge/kernel/schemas/subpackage/__init__.py": "",
    "src/polisyos/data_forge/kernel/schemas/subpackage/caller.py": (
        "from .. import codegen as parent_codegen\n"
        "from ..codegen import GeneratedSchemaModule as parent_symbol\n"
    ),
    "src/polisyos/foundry/domain/__init__.py": "from . import schema as schema_module\n",
    "src/polisyos/foundry/domain/schema.py": "class RegionProfile: ...\n",
}
KIND_SET = {
    "absolute_import",
    "relative_import",
    "absolute_import_child_candidate",
    "relative_import_child_candidate",
}
EXPECTED_IMPORTS = {
    (
        "polisyos.data_forge.kernel.schemas.codegen",
        "src/polisyos/data_forge/kernel/schemas/__init__.py",
        1,
        "relative_import",
        "polisyos.data_forge.kernel.schemas.codegen",
    ),
    (
        "polisyos.data_forge.kernel.schemas.codegen",
        "src/polisyos/data_forge/kernel/schemas/__init__.py",
        2,
        "relative_import_child_candidate",
        "polisyos.data_forge.kernel.schemas.codegen",
    ),
    (
        "polisyos.data_forge.kernel.schemas.codegen",
        "src/polisyos/data_forge/kernel/schemas/__init__.py",
        3,
        "absolute_import_child_candidate",
        "polisyos.data_forge.kernel.schemas.codegen",
    ),
    (
        "polisyos.data_forge.kernel.schemas.codegen",
        "src/polisyos/data_forge/kernel/schemas/subpackage/caller.py",
        1,
        "relative_import_child_candidate",
        "polisyos.data_forge.kernel.schemas.codegen",
    ),
    (
        "polisyos.data_forge.kernel.schemas.codegen",
        "src/polisyos/data_forge/kernel/schemas/subpackage/caller.py",
        2,
        "relative_import",
        "polisyos.data_forge.kernel.schemas.codegen",
    ),
    (
        "polisyos.foundry.domain.schema",
        "src/polisyos/foundry/domain/__init__.py",
        1,
        "relative_import_child_candidate",
        "polisyos.foundry.domain.schema",
    ),
}
COMMANDS: list[dict[str, object]] = []


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_file(path: Path) -> str:
    return digest_bytes(path.read_bytes())


def run(name: str, argv: list[str], cwd: Path, env: dict[str, str], timeout: int) -> subprocess.CompletedProcess[bytes]:
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    tick = time.monotonic()
    completed = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, timeout=timeout)
    finished = datetime.datetime.now(datetime.timezone.utc).isoformat()
    duration = time.monotonic() - tick
    stem = f"{len(COMMANDS) + 1:02d}-{name}"
    stdout_path = COMMAND_DIR / f"{stem}.stdout"
    stderr_path = COMMAND_DIR / f"{stem}.stderr"
    exit_path = COMMAND_DIR / f"{stem}.exit"
    stdout_path.write_bytes(completed.stdout)
    stderr_path.write_bytes(completed.stderr)
    exit_path.write_text(f"{completed.returncode}\n", encoding="ascii")
    COMMANDS.append(
        {
            "name": name,
            "argv": argv,
            "cwd": str(cwd.resolve()),
            "environment_delta": {"PYTHONPATH": "unset", "PYTHONHOME": "unset"},
            "timeout_seconds": timeout,
            "started_at_utc": started,
            "finished_at_utc": finished,
            "duration_seconds": duration,
            "exit_code": completed.returncode,
            "stdout": {"path": str(stdout_path), "bytes": len(completed.stdout), "sha256": digest_file(stdout_path)},
            "stderr": {"path": str(stderr_path), "bytes": len(completed.stderr), "sha256": digest_file(stderr_path)},
            "exit": {"path": str(exit_path), "sha256": digest_file(exit_path)},
        }
    )
    return completed


FIXTURE.mkdir(parents=True)
for relative, content in FIXTURE_FILES.items():
    path = FIXTURE / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
git_env = os.environ.copy()
git_env.pop("PYTHONPATH", None)
git_env.pop("PYTHONHOME", None)
git_env["GIT_CONFIG_NOSYSTEM"] = "1"
for name, argv in [
    ("fixture-git-init", ["git", "init", "--quiet"]),
    ("fixture-git-email", ["git", "config", "user.email", "schema-b8-fixture@example.invalid"]),
    ("fixture-git-name", ["git", "config", "user.name", "Schema b8 fixture"]),
    ("fixture-git-add", ["git", "add", "--all"]),
    ("fixture-git-commit", ["git", "commit", "--quiet", "-m", "schema census installed fixture"]),
]:
    result = run(name, argv, FIXTURE, git_env, 30)
    if result.returncode:
        raise SystemExit(f"{name} failed: {result.stderr.decode(errors='replace')}")

git_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=FIXTURE, capture_output=True, check=True, text=True).stdout.strip()
install_env = os.environ.copy()
install_env.pop("PYTHONPATH", None)
install_env.pop("PYTHONHOME", None)
tool_argv = [str(PYTHON), "-I", "-m", "tools.quality.validation.schema_fqn_census", "--repo-root", str(FIXTURE)]
positive = run("installed-fixture-positive", tool_argv, Path("/private/tmp"), install_env, 120)
if positive.returncode:
    raise SystemExit(f"positive installed invocation failed: {positive.stderr.decode(errors='replace')}")
positive_json = json.loads(positive.stdout)
if positive_json["result"] != "complete_for_selected_local_text_inputs":
    raise SystemExit(f"positive fixture census incomplete: {positive_json['result']}")
positive_hits = {
    (
        hit["target"],
        hit["path"],
        hit["line"],
        hit["evidence_kind"],
        hit["matched_value"],
    )
    for hit in positive_json["matches"]
    if hit["evidence_kind"] in KIND_SET
}
if positive_hits != EXPECTED_IMPORTS:
    raise SystemExit(f"positive import evidence mismatch: got {sorted(positive_hits)!r}")
child_hits = [hit for hit in positive_json["matches"] if hit["evidence_kind"].endswith("_child_candidate")]
if not child_hits or {hit.get("resolution") for hit in child_hits} != {"child_module_or_package_attribute"}:
    raise SystemExit("child candidate semantics were not explicit")

for relative, content in {
    "src/polisyos/data_forge/kernel/schemas/__init__.py": "from math import sqrt\n",
    "src/polisyos/data_forge/kernel/schemas/subpackage/caller.py": "from math import floor\n",
    "src/polisyos/foundry/domain/__init__.py": "from math import ceil\n",
}.items():
    (FIXTURE / relative).write_text(content, encoding="utf-8")
negative = run("installed-fixture-property-removed", tool_argv, Path("/private/tmp"), install_env, 120)
if negative.returncode:
    raise SystemExit(f"removal installed invocation failed: {negative.stderr.decode(errors='replace')}")
negative_json = json.loads(negative.stdout)
if negative_json["result"] != "complete_for_selected_local_text_inputs":
    raise SystemExit(f"removal fixture census incomplete: {negative_json['result']}")
negative_hits = [hit for hit in negative_json["matches"] if hit["evidence_kind"] in KIND_SET]
if negative_hits:
    raise SystemExit(f"removed ImportFrom property still generated hits: {negative_hits!r}")
remaining_targets = {
    relative: digest_file(FIXTURE / relative)
    for relative in (
        "src/polisyos/data_forge/kernel/schemas/codegen.py",
        "src/polisyos/foundry/domain/schema.py",
    )
}
if any(not (FIXTURE / path).is_file() for path in remaining_targets):
    raise SystemExit("target module marker files were removed unexpectedly")

report = {
    "candidate": {
        "commit": "b8d9115cdc6a55920c1e0a3cae2e5f9092010c27",
        "tree": "467cd6f01ec204767dc60bb939955578428bf102",
        "source_archive_sha256": digest_file(ARCHIVE),
        "wheel_sha256": digest_file(WHEEL),
    },
    "fixture": {
        "root": str(FIXTURE),
        "git_head": git_head,
        "input_files": {name: digest_bytes(content.encode()) for name, content in FIXTURE_FILES.items()},
        "retained_target_module_files_after_removal": remaining_targets,
    },
    "installed_behavior": {
        "module": "tools.quality.validation.schema_fqn_census",
        "invocation": "python -I -m tools.quality.validation.schema_fqn_census --repo-root <fixture>",
        "positive_result": positive_json["result"],
        "positive_selected_paths": positive_json["selection"]["selected_path_count"],
        "positive_exact_import_hits": len(positive_hits),
        "positive_child_candidate_hits": len(child_hits),
        "positive_hits": [list(hit) for hit in sorted(positive_hits)],
        "negative_result": negative_json["result"],
        "negative_import_hit_count": len(negative_hits),
        "removal_falsifier": "all relevant ImportFrom sites removed while both candidate target module files remained present; the installed census emitted no import evidence",
    },
    "commands": COMMANDS,
}
report_path = BASE / "installed-fixture-results.json"
report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({"result": "pass", "report_path": str(report_path), "report_sha256": digest_file(report_path), "positive_hits": len(positive_hits), "negative_hits": len(negative_hits), "git_head": git_head}, sort_keys=True))
