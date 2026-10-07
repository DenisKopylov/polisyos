"Read-only independent frozen-wave input audit; never invokes the wave."

from __future__ import annotations

import ast
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from audit_quantities import content_digest


def _resolve_executable(name: str) -> str:
    (
        "Resolve an admitted executable and refus"  # Exact bound literal continuation.
        "e an unavailable program before invocati"  # Exact bound literal continuation.
        "on."  # Exact bound literal continuation.
    )
    resolved = shutil.which(name)
    if resolved is None:
        raise RuntimeError(f"required utility executable unavailable: {name}")
    return str(Path(resolved).resolve())


def _write_stdout(*values: object, flush: bool = False) -> None:
    (
        "Emit the existing CLI text and optionall"  # Exact bound literal continuation.
        "y flush without logging side effects."  # Exact bound literal continuation.
    )
    sys.stdout.write(" ".join(str(value) for value in values) + "\n")
    if flush:
        sys.stdout.flush()


REPO = Path("/workspace/e02-E-continuation-20261006")
WAVE = Path("/workspace/e02-E-pr38-r2-receipts/common-wave-5e3e37276")
OUT = Path(__file__).resolve().parent
FREEZE = "5e3e3727685132f270a3a07b9f63dd962a88cd96"
TREE = "3b63e778d5b6d17b2e9edc3b4bf91af079b32eb0"
BASE = "198076863e143dea9f89f02734b13d50dae3eed5"
PREFIX = (
    "policy-engine/docs/research/e02-cloud-test-plan/implementati"
    "on-handoffs/E/continuation-20261006/pr38-r2/wave-controls/"
)


def _admit_git_object_arguments(arguments: tuple[str, ...]) -> None:
    """Keep object reads from interpreting record refs as Git options.

    Named/abbreviated refs remain available to retired source-pinned replay
    scripts; live packet admissions separately require full immutable SHAs.
    """
    if not arguments or arguments[0] not in {"show", "rev-parse"}:
        return
    safe_information_flags = {"--show-toplevel", "--git-dir", "--git-common-dir"}
    for value in arguments[1:]:
        if not isinstance(value, str) or not value or "\0" in value:
            raise ValueError("Git object argument must be a nonempty string")
        if value.startswith("-"):
            if arguments[0] == "rev-parse" and value in safe_information_flags:
                continue
            raise ValueError("Git object reference must never be an option")
        if ":" in value:
            _, relative = value.split(":", 1)
            path = Path(relative)
            if (
                not path.parts
                or path.is_absolute()
                or ".." in path.parts
                or path.as_posix() != relative
                or "\0" in relative
            ):
                raise ValueError("Git object path must be repository relative")


def git(*args: str) -> bytes:
    _admit_git_object_arguments(args)
    result = subprocess.run(  # noqa: S603 - source-bound fixture
        [_resolve_executable("git"), "-C", str(REPO), *args], capture_output=True, check=True
    )
    return result.stdout


def git_json(path: str) -> object:
    return json.loads(git("show", FREEZE + ":" + path))


def fingerprint() -> tuple[object, ...]:
    raw_paths = sorted(p for p in git("ls-files", "-z").split(b"\0") if p)
    records = {}
    for entry in git("ls-tree", "-rz", "--full-tree", FREEZE).split(b"\0"):
        if not entry:
            continue
        head, path = entry.split(b"\t", 1)
        mode, kind, oid = head.split()
        records[path] = (mode, kind, oid)
    if not (set(raw_paths) == set(records)):
        raise AssertionError
    digest = hashlib.sha256()
    total = 0
    exceptional = []
    for raw in raw_paths:
        path = REPO / os.fsdecode(raw)
        mode, kind, expected = records[raw]
        data = path.read_bytes() if path.is_file() else b"ABSENT"
        digest.update(raw + b"\0" + data + b"\0")
        total += len(data)
        if mode == b"120000":
            blob = os.fsencode(os.readlink(path))
            exceptional.append(
                {
                    "path": os.fsdecode(raw),
                    "kind": (
                        "tracked symlink; Git binds link target, "
                        "framing reads resolved file if present"
                    ),
                }
            )
        elif kind == b"blob":
            if not (path.is_file()):
                raise AssertionError(os.fsdecode(raw))
            blob = data
        else:
            exceptional.append(
                {"path": os.fsdecode(raw), "kind": kind.decode(), "mode": mode.decode()}
            )
            continue
        actual_oid = hashlib.sha1(
            b"blob " + str(len(blob)).encode() + b"\0" + blob, usedforsecurity=False
        ).hexdigest()
        if not (actual_oid == expected.decode()):
            raise AssertionError(os.fsdecode(raw))
    return {
        "tracked_paths": len(raw_paths),
        "bytes": total,
        "framed_sha256": digest.hexdigest(),
    }, exceptional


def group_for(path: object) -> None | str:
    p = "policy-engine/tests/unit/"
    if not path.startswith(p):
        return None
    r = path[len(p) :]
    if (
        r.startswith("calibration/")
        or r == "foundry/methods/catalog/econometrics/test_advanced_persistence.py"
    ):
        return "PCL_continuous_persistence"
    if r.startswith("ddm/"):
        return "DDM_runtime_and_facade"
    if r.startswith(
        (
            "scientist/methods/backtesting/",
            "scientist/governance/test_backtest",
            "remediation/test_frc",
        )
    ):
        return "BKT_FRC_S10_and_adjacent_report_consumers"
    if (
        r.startswith("foundry/calibration/")
        or r == "scientist/nodes/test_calibration_report_consumer.py"
        or (r.startswith("scientist/nodes/builtins/simulate/") and "welfare" in r)
    ):
        return "CAL_and_welfare_consumer"
    if r.startswith("foundry/uncertainty/") or (
        r.startswith("scientist/nodes/") and "propagate_uncertainty" in r
    ):
        return "MC_joint_law_support_and_Scientist_consumer"
    if r.startswith(("scientist/methods/doe/", "scientist/methods/autotune/test_sensitivity")):
        return "DOE_SALib_and_consumer_factory"
    return None


def audit() -> None:
    plan = json.loads((WAVE / "plan.json").read_text())
    start = json.loads((WAVE / "wave-started.json").read_text())
    source_freeze = json.loads((WAVE.parent / "source-freeze-5e3e37276.json").read_text())
    if not (git("rev-parse", "HEAD").decode().strip() == FREEZE):
        raise AssertionError
    if not (git("rev-parse", FREEZE + "^{tree}").decode().strip() == TREE):
        raise AssertionError
    if not (git("status", "--porcelain", "--untracked-files=no") == b""):
        raise AssertionError
    if not (
        plan["candidate_sha"]
        == plan["observed_head"]
        == start["candidate_sha"]
        == source_freeze["frozen_sha"]
        == FREEZE
    ):
        raise AssertionError
    if not (plan["candidate_tree_sha"] == source_freeze["tree"] == TREE):
        raise AssertionError
    remote = (
        git("ls-remote", "origin", "refs/heads/codex/e02-E-continuation-20261006").decode().split()
    )
    if not (remote == [FREEZE, "refs/heads/codex/e02-E-continuation-20261006"]):
        raise AssertionError
    if not (source_freeze["remote_ls_readback_sha"] == FREEZE):
        raise AssertionError
    identity, exceptional = fingerprint()
    original = git_json(PREFIX + "original-wave-groups.json")
    proposal = git_json(PREFIX + "proposal.json")
    groups = {k: list(v) for k, v in original["groups"].items()}
    for name, paths in proposal["required_additions"].items():
        groups.setdefault(name, [])
        for path in paths:
            if path not in groups[name]:
                groups[name].append(path)
    changed = (
        git(
            "diff",
            "--name-only",
            "--diff-filter=ACMR",
            proposal["delta_selection_base"],
            FREEZE,
            "--",
            "policy-engine/tests",
        )
        .decode()
        .splitlines()
    )
    unassigned = []
    for path in changed:
        family = group_for(path)
        if family:
            if path not in groups[family]:
                groups[family].append(path)
        elif path != "policy-engine/tests/unit/runtime/http/test_control_plane_store.py":
            unassigned.append(path)
    if not (plan["groups"] == groups):
        raise AssertionError
    if not (plan["changed_foreign_tests_outside_E_wave"] == unassigned):
        raise AssertionError
    all_paths = [p for paths in groups.values() for p in paths]
    if not (len(all_paths) == len(set(all_paths)) == plan["native_test_path_count"]):
        raise AssertionError
    tracked = set(git("ls-tree", "-r", "--name-only", FREEZE).decode().splitlines())
    if not (set(all_paths) <= tracked):
        raise AssertionError
    ast_counts = {}
    for name, paths in groups.items():
        count = 0
        for path in paths:
            data = git("show", FREEZE + ":" + path)
            if not (
                plan["source_test_assets"][path]
                == {
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "bytes": len(data),
                }
            ):
                raise AssertionError
            count += sum(
                isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                and n.name.startswith("test_")
                for n in ast.walk(ast.parse(data))
            )
        ast_counts[name] = count
    if not (ast_counts == plan["ast_test_function_counts_only"]):
        raise AssertionError
    lint = [
        p[len("policy-engine/") :]
        for p in git(
            "diff", "--name-only", "--diff-filter=ACMR", BASE, FREEZE, "--", "policy-engine"
        )
        .decode()
        .splitlines()
        if p.endswith(".py") and p in tracked
    ]
    if not (lint == plan["changed_python_lint_paths"]):
        raise AssertionError
    upstream = {}
    for name, row in plan["required_upstream"].items():
        if row["in_candidate_history"] is not True:
            raise AssertionError
        git("merge-base", "--is-ancestor", row["sha"], FREEZE)
        upstream[name] = row["sha"]
    packets = []
    for row in plan["owner_packet_extra_inputs"]:
        data = git("show", FREEZE + ":" + row["source"])
        observed = content_digest(Path(row["destination"]))
        if not (
            observed
            == {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            == {"bytes": row["bytes"], "sha256": row["sha256"]}
        ):
            raise AssertionError
        packets.append({"source": row["source"], "destination": row["destination"], **observed})
    if not (len(all_paths) + len(packets) == plan["test_input_path_count_including_owner_packets"]):
        raise AssertionError
    numerical = [j for j in plan["jobs"] if j["kind"] == "numerical"]
    if not (len(numerical) == 7):
        raise AssertionError
    scratch = []
    for job in numerical:
        argv = job["argv"]
        stop = argv.index("--basetemp") + 2
        expected = [p[len("policy-engine/") :] for p in groups[job["group"]]]
        if job["group"] == "BKT_FRC_S10_and_adjacent_report_consumers":
            expected += [p["destination"] for p in packets]
        if not (argv[stop:] == expected):
            raise AssertionError
        if not (argv[:4] == [plan["interpreter"], "-m", "pytest", "-q"]):
            raise AssertionError
        if not ("-n" not in argv and "--numprocesses" not in argv):
            raise AssertionError
        if not (argv[argv.index("--junitxml") + 1] == job["junit"]):
            raise AssertionError
        scratch.append(
            {
                "group": job["group"],
                "basetemp": argv[argv.index("--basetemp") + 1],
                "tmpdir": job["environment"]["TMPDIR"],
            }
        )
    if not (len({r["basetemp"] for r in scratch}) == len(scratch)):
        raise AssertionError
    if not (len({r["tmpdir"] for r in scratch}) == len(scratch)):
        raise AssertionError
    for name, prefix in [
        ("ruff", ["-m", "ruff", "check"]),
        ("ruff-format", ["-m", "ruff", "format", "--check"]),
    ]:
        job = next(j for j in plan["jobs"] if j["name"] == name)
        if not (job["argv"] == [plan["interpreter"], *prefix, *lint]):
            raise AssertionError
    review_assets = []
    for row in source_freeze["reviews"]:
        data = git("show", FREEZE + ":" + row["path"])
        if not (
            {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            == {
                "bytes": row["bytes"],
                "sha256": row["sha256"],
            }
        ):
            raise AssertionError
        review_assets.append(row)
    input_paths = (
        "AGENTS.md",
        "policy-engine/CONTRIBUTING.md",
        "policy-engine/pyproject.toml",
        "policy-engine/uv.lock",
    )
    input_files = {}
    for path in input_paths:
        data = git("show", FREEZE + ":" + path)
        input_files[path] = {
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "git_blob": git("rev-parse", FREEZE + ":" + path).decode().strip(),
        }
    result = {
        "schema": "e02.E.independent-wave-input-audit.v1",
        "candidate_sha": FREEZE,
        "candidate_tree_sha": TREE,
        "read_only": True,
        "checks_launched": False,
        "Git_mutations": False,
        "input_integrity": "GO",
        "source_framing": identity,
        "tracked_exceptions": exceptional,
        "remote_topic_sha": remote[0],
        "plan_digest": content_digest(WAVE / "plan.json"),
        "native_group_paths": {k: len(v) for k, v in groups.items()},
        "native_test_path_count": len(all_paths),
        "owner_packet_count": len(packets),
        "test_input_path_count_including_owner_packets": len(all_paths) + len(packets),
        "ast_test_function_counts_only": ast_counts,
        "changed_python_lint_path_count": len(lint),
        "changed_python_lint_paths": lint,
        "foreign_tests_outside_E_numerical_wave": unassigned,
        "source_test_assets_all_reconciled": True,
        "source_test_asset_count": len(all_paths),
        "owner_packet_assets": packets,
        "distinct_scratch": scratch,
        "required_upstream": upstream,
        "review_assets": review_assets,
        "input_files": input_files,
        "source_and_input_observed_while_wave_running": True,
        "numerical_outcome": "NOT_DECIDED; wait for actual complete outputs",
        "backend_observer_scope": "Post-command collector process; no pytest-child x64 proof",
        "finding_closure": False,
        "P41": "not_established without exact base/input replay",
    }
    target = OUT / "input-audit-5e3e37276.json"
    if target.exists():
        raise AssertionError
    target.write_text(json.dumps(result, indent=2) + "\n")
    _write_stdout(
        json.dumps(
            {
                k: result[k]
                for k in [
                    "candidate_sha",
                    "candidate_tree_sha",
                    "input_integrity",
                    "native_test_path_count",
                    "owner_packet_count",
                    "test_input_path_count_including_owner_packets",
                    "changed_python_lint_path_count",
                    "source_framing",
                    "numerical_outcome",
                ]
            }
        )
    )


if __name__ == "__main__":
    audit()
