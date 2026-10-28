"""Run bounded Lex controls in isolated processes and retain deciding outputs.

This test utility does not grant authority, establish legal currency, or close
LA-017. Invoke with an admitted commit, tree and a new absolute output directory.
"""

from __future__ import annotations

import gzip
import hashlib
import importlib.metadata
import json
import os
import signal
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from contextlib import suppress
from pathlib import Path

PRODUCT = Path(__file__).resolve().parents[3]
ROOT = PRODUCT.parent
PYTHON = PRODUCT / ".venv/bin/python"
TEST = "tests/unit/remediation/test_e02_lex_impact_controls.py"
SELECTORS = (
    (
        "f17-01",
        "tests/unit/remediation/test_lex_impact_semantics.py::test_real_impact_report_reopens_its_diff_and_preserves_issue_and_topic_semantics",
    ),
    (
        "f17-02",
        "tests/unit/remediation/test_lex_impact_semantics.py::test_impact_cli_emits_real_backend_report_and_fresh_json_and_markdown",
    ),
    (
        "f17-03",
        "tests/unit/remediation/test_lex_impact_semantics.py::test_selected_diff_profile_is_reconciled_with_issued_report_manifest",
    ),
    (
        "f17-04",
        "tests/unit/remediation/test_lex_impact_semantics.py::test_historical_report_without_backend_metadata_stays_readable",
    ),
    (
        "f17-05",
        "tests/unit/remediation/test_lex_impact_semantics.py::test_versioned_reader_first_and_explicit_legacy_writer_rollback",
    ),
    (
        "f17-06",
        "tests/unit/lex/simulator/test_diff.py::test_diff_norm_packs_detects_all_change_types",
    ),
)
MODES = (
    "producer_topics",
    "report_bridge",
    "markdown_disclaimer",
    "manifest_edge",
    "report_reconciliation",
    "diff_reconstruction",
    "delta_replay",
    "issue_total_bound",
    "scope_guard",
)
OWNER_INPUTS = (
    "src/polisyos/lex/legal_evaluation/impact_diff.py",
    "src/polisyos/lex/normpack/diff.py",
    "src/polisyos/lex/simulator/cli.py",
    "tests/unit/remediation/test_lex_impact_semantics.py",
    "tests/unit/lex/simulator/test_diff.py",
    TEST,
    "tests/unit/remediation/e02_lex_triplet_runner.py",
    "pytest.ini",
    "pyproject.toml",
    "uv.lock",
)


def digest(data: bytes) -> str:
    """Return a content digest for a receipt."""
    return hashlib.sha256(data).hexdigest()


def git_blob(data: bytes) -> str:
    """Compute the SHA-1 Git blob identity without writing to Git's object store."""
    header = f"blob {len(data)}\0".encode()
    return hashlib.sha1(header + data, usedforsecurity=False).hexdigest()


def git(*args: str) -> str:
    """Read Git metadata from the selected working tree."""
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def head_tree(head: str) -> dict[str, str]:
    """Enumerate tracked blobs in the selected source commit once."""
    data = subprocess.check_output(
        ["git", "-C", str(ROOT), "ls-tree", "-r", "-z", head, "--", "policy-engine"]
    )
    found: dict[str, str] = {}
    for item in data.split(b"\0"):
        if not item:
            continue
        metadata, name = item.split(b"\t", 1)
        mode, kind, obj = metadata.decode().split()
        if kind == "blob" and mode in {"100644", "100755"}:
            found[name.decode().removeprefix("policy-engine/")] = obj
    return found


def read_sources() -> dict[str, str]:
    """Capture finite loaded repository Python paths, not an all-input census."""
    found: dict[str, str] = {}
    for module in list(sys.modules.values()):
        filename = getattr(module, "__file__", None)
        if not filename or not str(filename).endswith(".py"):
            continue
        try:
            path = Path(filename).resolve()
            rel = path.relative_to(PRODUCT).as_posix()
            if not rel.startswith(("src/polisyos/", "tests/", "tools/")):
                continue
            found[rel] = digest(path.read_bytes())
        except (OSError, ValueError):
            continue
    return found


def worker() -> None:
    """Use the native pytest configuration and add an observation-only plugin."""
    import pytest

    class ReadsetObserver:
        @pytest.hookimpl(trylast=True)
        def pytest_sessionfinish(self, session: object, exitstatus: object) -> None:
            plugins = []
            for name, plugin in session.config.pluginmanager.list_name_plugin():
                plugins.append(
                    {
                        "name": name,
                        "module": getattr(plugin, "__name__", type(plugin).__module__),
                        "path": getattr(plugin, "__file__", None),
                    }
                )
            record = {
                "pid": os.getpid(),
                "exitstatus": int(exitstatus),
                "readset": read_sources(),
                "plugins": plugins,
            }
            Path(os.environ["C95_WORKER_READSET"]).write_text(
                json.dumps(record, sort_keys=True) + "\n"
            )

    raise SystemExit(pytest.main(sys.argv[2:], plugins=[ReadsetObserver()]))


def available_ram() -> int | None:
    """Measure available memory when the platform exposes Linux MemAvailable."""
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        pass
    return None


def tree_rss(pid: int) -> int | None:
    """Sample Linux process-tree RSS; return None on other platforms."""
    proc = Path("/proc")
    if not proc.is_dir():
        return None
    children: dict[int, set[int]] = {}
    for item in proc.iterdir():
        if not item.name.isdigit():
            continue
        try:
            stat = (item / "stat").read_text()
            after_name = stat[stat.rfind(")") + 2 :].split()
            children.setdefault(int(after_name[1]), set()).add(int(item.name))
        except (OSError, ValueError, IndexError):
            continue
    todo, seen = [pid], set()
    while todo:
        child = todo.pop()
        if child in seen:
            continue
        seen.add(child)
        todo.extend(children.get(child, ()))
    rss = 0
    for child in seen:
        try:
            for line in (proc / str(child) / "status").read_text().splitlines():
                if line.startswith("VmRSS:"):
                    rss += int(line.split()[1]) * 1024
                    break
        except (OSError, ValueError, IndexError):
            continue
    return rss


def free_bytes(path: Path) -> int:
    """Measure unprivileged free bytes on the output filesystem."""
    stat = os.statvfs(path)
    return stat.f_bavail * stat.f_frsize


def reconcile(readset: dict[str, str], tree: dict[str, str]) -> dict[str, object]:
    """Match observed Python source to current bytes and pinned commit blobs."""
    mismatches = []
    for rel, observed in sorted(readset.items()):
        path = PRODUCT / rel
        try:
            raw = path.read_bytes()
            current, blob = digest(raw), git_blob(raw)
        except OSError:
            current, blob = None, None
        if current != observed or tree.get(rel) != blob:
            mismatches.append(
                {
                    "path": rel,
                    "observed_sha256": observed,
                    "current_sha256": current,
                    "git_blob": tree.get(rel),
                    "current_git_blob": blob,
                }
            )
    return {"loaded_python_paths": len(readset), "mismatches": mismatches}


def applicable_inputs() -> list[str]:
    """Enumerate each selected test's applicable conftests and fixed owner inputs."""
    paths = set(OWNER_INPUTS)
    for _, selector in (*SELECTORS, ("triplet", TEST)):
        path = PRODUCT / selector.split("::", 1)[0]
        for parent in (path.parent, *path.parent.parents):
            try:
                rel = parent.relative_to(PRODUCT)
            except ValueError:
                break
            conftest = PRODUCT / rel / "conftest.py"
            if conftest.is_file():
                paths.add(conftest.relative_to(PRODUCT).as_posix())
            if parent == PRODUCT:
                break
    return sorted(paths)


def write_json(path: Path, data: object) -> None:
    """Write a compact retained machine receipt."""
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def compress(path: Path) -> dict[str, object]:
    """Store complete command output with lossless compression."""
    raw = path.read_bytes()
    dest = path.with_suffix(path.suffix + ".gz")
    with dest.open("wb") as target, gzip.GzipFile(fileobj=target, mode="wb", mtime=0) as stream:
        stream.write(raw)
    return {
        "file": str(dest),
        "sha256": digest(dest.read_bytes()),
        "uncompressed_sha256": digest(raw),
        "uncompressed_bytes": len(raw),
    }


def run_one(
    label: str,
    selector: str,
    output: Path,
    tree: dict[str, str],
    head: str,
    source_tree: str,
    pins: dict[str, dict[str, str]],
    rss_cap: int,
) -> dict[str, object]:
    """Execute one selector in one process and retain all deciding bytes."""
    slot = output / label
    slot.mkdir()
    tmp = slot / "tmp"
    tmp.mkdir()
    cache = slot / "pycache"
    cache.mkdir()
    env = os.environ.copy()
    for key in (
        "PYTEST_ADDOPTS",
        "PYTEST_PLUGINS",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD",
        "PYTHONPATH",
        "PYTHONOPTIMIZE",
        "PYTHONHOME",
        "VIRTUAL_ENV",
    ):
        env.pop(key, None)
    for key in list(env):
        if key.startswith("POLISYOS_LEX_CONTROL"):
            env.pop(key)
    env.update(
        dict.fromkeys(
            (
                "OMP_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
                "MKL_NUM_THREADS",
                "NUMBA_NUM_THREADS",
                "NUMEXPR_NUM_THREADS",
                "VECLIB_MAXIMUM_THREADS",
            ),
            "1",
        )
    )
    env.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPYCACHEPREFIX": str(cache),
            "TMPDIR": str(tmp),
            "XDG_CACHE_HOME": str(tmp / "xdg"),
            "HYPOTHESIS_STORAGE_DIRECTORY": str(tmp / "hypothesis"),
            "C95_SOURCE_COMMIT": head,
            "C95_SOURCE_TREE": source_tree,
            "C95_WORKER_READSET": str(slot / "readset.json"),
        }
    )
    argv = [
        str(PYTHON),
        "-B",
        str(Path(__file__).resolve()),
        "--worker",
        "-q",
        "-s",
        selector,
        "--tb=short",
        "--color=no",
        "--maxfail=0",
        "--basetemp",
        str(slot / "basetemp"),
        "-o",
        "cache_dir=" + str(slot / "pytest-cache"),
        "--benchmark-storage=file://" + str(slot / "benchmark"),
        "--junitxml",
        str(slot / "junit.xml"),
    ]
    started = time.monotonic()
    initial_disk = free_bytes(output)
    available = available_ram()
    low_disk, peak = initial_disk, None
    timed_out = False
    abort_reason = None
    with (slot / "stdout.txt").open("wb") as stdout, (slot / "stderr.txt").open("wb") as stderr:
        process = subprocess.Popen(
            argv, cwd=PRODUCT, env=env, stdout=stdout, stderr=stderr, start_new_session=True
        )
        while process.poll() is None:
            rss = tree_rss(process.pid)
            if rss is not None:
                peak = max(peak or 0, rss)
            low_disk = min(low_disk, free_bytes(output))
            if time.monotonic() - started > 600:
                timed_out = True
                abort_reason = "wall_cap"
            elif rss is not None and rss > rss_cap:
                abort_reason = "process_tree_rss_cap"
            elif low_disk < 2 * 1024**3:
                abort_reason = "disk_floor"
            if abort_reason:
                with suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    with suppress(ProcessLookupError):
                        os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                break
            time.sleep(1)
        code = process.wait()
    stdout_bytes = (slot / "stdout.txt").read_bytes()
    phase_records = []
    phase_parse_error = None
    for line in stdout_bytes.decode("utf-8", "replace").splitlines():
        if line.startswith("C95_ACTUAL_PHASES="):
            try:
                phase_records.append(json.loads(line.removeprefix("C95_ACTUAL_PHASES=")))
            except json.JSONDecodeError as exc:
                phase_parse_error = str(exc)
    readset_path = slot / "readset.json"
    try:
        observed = json.loads(readset_path.read_text()) if readset_path.exists() else None
    except (OSError, json.JSONDecodeError):
        observed = None
    source_check = reconcile(observed["readset"], tree) if observed is not None else None
    xml_path = slot / "junit.xml"
    try:
        cases = list(ET.parse(xml_path).iter("testcase")) if xml_path.exists() else []  # noqa: S314 - own pytest output
    except (OSError, ET.ParseError):
        cases = []
    counts = {
        "tests": len(cases),
        "failures": sum(c.find("failure") is not None for c in cases),
        "errors": sum(c.find("error") is not None for c in cases),
        "skipped": sum(c.find("skipped") is not None for c in cases),
    }
    phase_ok = not label.startswith("triplet-") or (
        phase_parse_error is None
        and len(phase_records) == 1
        and phase_records[0]["mode"] == label.removeprefix("triplet-")
        and phase_records[0]["pid_set"] == [process.pid]
        and [p["phase"] for p in phase_records[0]["phases"]]
        == ["positive_before", "removal_negative", "positive_restored"]
    )
    changed_pins = [
        rel
        for rel, pin in pins.items()
        if not (PRODUCT / rel).is_file() or digest((PRODUCT / rel).read_bytes()) != pin["sha256"]
    ]
    sources_ok = (
        not changed_pins
        and observed is not None
        and observed["pid"] == process.pid
        and source_check is not None
        and not source_check["mismatches"]
        and git("rev-parse", "HEAD") == head
        and git("rev-parse", "HEAD^{tree}") == source_tree
    )
    if abort_reason or not sources_ok or not phase_ok or not cases:
        status = "ERROR"
    elif code == 0 and counts == {"tests": 1, "failures": 0, "errors": 0, "skipped": 0}:
        status = "PASS"
    elif counts["skipped"]:
        status = "SKIP"
    elif counts["failures"]:
        status = "FAIL"
    else:
        status = "ERROR"
    record = {
        "label": label,
        "selector": selector,
        "argv": argv,
        "cwd": str(PRODUCT),
        "pid": process.pid,
        "returncode": code,
        "status": status,
        "timed_out": timed_out,
        "abort_reason": abort_reason,
        "deadline_seconds": 600,
        "rss_cap_bytes": rss_cap,
        "changed_input_pins": changed_pins,
        "status_interpretation": "pytest observation only; product vs setup cause requires review",
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "peak_process_tree_rss_bytes": peak,
        "available_ram_initial_bytes": available,
        "free_disk_initial_bytes": initial_disk,
        "free_disk_low_bytes": low_disk,
        "junit": counts,
        "phase_evidence_present": phase_ok,
        "phase_parse_error": phase_parse_error,
        "source_readback": source_check,
        "stdout": compress(slot / "stdout.txt"),
        "stderr": compress(slot / "stderr.txt"),
        "junit_sha256": digest(xml_path.read_bytes()) if xml_path.exists() else None,
        "readset_sha256": digest(readset_path.read_bytes()) if readset_path.exists() else None,
    }
    write_json(slot / "record.json", record)
    return record


def main() -> None:
    """Admit exact source and run independent bounded selectors sequentially."""
    expected_head = os.environ.get("C95_EXPECTED_COMMIT")
    expected_tree = os.environ.get("C95_EXPECTED_TREE")
    output_var = os.environ.get("C95_OUTPUT_DIR")
    if not expected_head or not expected_tree or not output_var:
        raise SystemExit(
            "C95_EXPECTED_COMMIT, C95_EXPECTED_TREE and absolute C95_OUTPUT_DIR required"
        )
    output = Path(output_var)
    if not output.is_absolute() or output.exists():
        raise SystemExit("output directory must be absolute and absent")
    if not PYTHON.is_file():
        raise SystemExit("supported product Python environment is missing")
    head, source_tree = git("rev-parse", "HEAD"), git("rev-parse", "HEAD^{tree}")
    if (head, source_tree) != (expected_head, expected_tree):
        raise SystemExit(f"source identity mismatch: actual {head}/{source_tree}")
    tree = head_tree(head)
    pins = {}
    for rel in applicable_inputs():
        path = PRODUCT / rel
        data = path.read_bytes()
        blob = git_blob(data)
        if tree.get(rel) != blob:
            raise SystemExit(f"source input mismatch or untracked input: {rel}")
        pins[rel] = {"sha256": digest(data), "git_blob": blob}
    versions = {}
    for package in ("pytest", "pydantic", "duckdb"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    output.mkdir(parents=True)
    vfs = os.statvfs(output)
    ram = available_ram()
    override = os.environ.get("C95_RSS_CAP_BYTES")
    if ram is None and override is None:
        raise SystemExit("available RAM unavailable; measure it and set C95_RSS_CAP_BYTES")
    rss_cap = int(override) if override is not None else min(2 * 1024**3, ram // 2)
    if rss_cap <= 0 or free_bytes(output) < 4 * 1024**3:
        raise SystemExit(
            "resource admission failed: RSS cap must be positive and free disk at least 4 GiB"
        )
    write_json(
        output / "admission.json",
        {
            "head": head,
            "tree": source_tree,
            "branch_or_detached": git("branch", "--show-current"),
            "input_pins": pins,
            "python": sys.version,
            "platform": sys.platform,
            "versions": versions,
            "cpu_count": os.cpu_count(),
            "disk_total_bytes": vfs.f_blocks * vfs.f_frsize,
            "disk_free_bytes": free_bytes(output),
            "ram_available_bytes": ram,
            "rss_cap_bytes": rss_cap,
            "disk_floor_bytes": 2 * 1024**3,
            "numeric_threads": 1,
            "readset_boundary": "finite imported project .py paths; excludes compiled, external, parser-read and dynamically executed source",
            "closure_ids": [],
        },
    )
    nodes = list(SELECTORS) + [
        ("triplet-" + mode, TEST + "::test_exact_same_process_removal_triplet[" + mode + "]")
        for mode in MODES
    ]
    records = []
    stopped = False
    for label, selector in nodes:
        if stopped:
            records.append(
                {
                    "label": label,
                    "selector": selector,
                    "status": "UNRUN",
                    "reason": "prior resource abort",
                }
            )
            continue
        record = run_one(label, selector, output, tree, head, source_tree, pins, rss_cap)
        records.append(record)
        stopped = bool(record.get("abort_reason"))
    write_json(
        output / "batch.json",
        {
            "head": head,
            "tree": source_tree,
            "records": records,
            "closure_ids": [],
            "G_acceptance": "not claimed",
        },
    )
    print(
        json.dumps(
            {
                "output": str(output),
                "statuses": {
                    status: sum(r["status"] == status for r in records)
                    for status in ("PASS", "FAIL", "ERROR", "SKIP", "UNRUN")
                },
            }
        )
    )
    raise SystemExit(0 if all(record["status"] == "PASS" for record in records) else 1)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        worker()
    else:
        main()
