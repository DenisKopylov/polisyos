(
    "Independent runner safety/metadata check"  # Exact bound literal continuation.
    "s; never execute a numerical or CI wave."  # Exact bound literal continuation.
)

import asyncio
import configparser
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace


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


R = Path("/workspace/e02-E-continuation-20261006")
P = R / "policy-engine"
observed_o = Path(__file__).parent
REF = "4758d495abb81aa51fea8e28cd071ca9ff989155"
BASE = "c79de1a8779482cf485317039fe12e3570ae2273"
W = P / (
    "docs/research/e02-cloud-test-plan/implementation-handoffs/E/"
    "continuation-20261006/pr38-r2/wave-controls"
)
paths = [str(p.relative_to(R)) for p in W.glob("*.py")] + [str((W / "README.md").relative_to(R))]
before = {}
for path in paths:
    expected = subprocess.check_output(  # noqa: S603 - source-bound fixture
        [_resolve_executable("git"), "show", REF + ":" + path], cwd=R
    )
    if not ((R / path).read_bytes() == expected):
        raise AssertionError
    before[path] = hashlib.sha256(expected).hexdigest()
if not (
    set(
        subprocess.check_output(  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
            [_resolve_executable("git"), "diff", "--name-only", BASE, REF], cwd=R, text=True
        ).splitlines()
    )
    == set(paths)
):
    raise AssertionError


def load(name: str, path: object) -> object:
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


plan = load("independent_final_plan", W / "plan_wave.py")
check = load("independent_final_check", W / "run_check.py")
args = SimpleNamespace(
    repo=R,
    candidate=REF,
    output_root=observed_o / "not-executed-plan-output",
    comparison_base="198076863e143dea9f89f02734b13d50dae3eed5",
    no_owner_packets=False,
)
prepared = plan.prepare(args)
if not (prepared["execution_state"] == "NOT_RUN" and prepared["old_paths_retained"]):
    raise AssertionError
if not (
    prepared["native_test_path_count"] == 120
    and prepared["test_input_path_count_including_owner_packets"] == 122
):
    raise AssertionError
if not (
    not prepared["missing_required_paths"]
    and all(r["in_candidate_history"] for r in prepared["required_upstream"].values())
):
    raise AssertionError
numerical = [j for j in prepared["jobs"] if j["kind"] == "numerical"]
if not (len(numerical) == 7):
    raise AssertionError
for job in numerical:
    if not ("addopts=" not in job["argv"] and "no:cacheprovider" not in job["argv"]):
        raise AssertionError
    if "--basetemp" not in job["argv"]:
        raise AssertionError
    if not (any(x.startswith("cache_dir=") for x in job["argv"])):
        raise AssertionError
    if not (any(x.startswith("--benchmark-storage=file:") for x in job["argv"])):
        raise AssertionError
if not (len({j["argv"][j["argv"].index("--basetemp") + 1] for j in numerical}) == 7):
    raise AssertionError
configuration = configparser.ConfigParser()
configuration.read(P / "pytest.ini")
defaults = configuration["pytest"]["addopts"]
if not ("--import-mode=importlib" in defaults and "--strict-markers" in defaults):
    raise AssertionError
if not (prepared["environment"]["PLAYWRIGHT_BROWSERS_PATH"] == "/home/agent/.cache/ms-playwright"):
    raise AssertionError
if not (prepared["environment"]["UV_NO_SYNC"] == "1"):
    raise AssertionError
if not (prepared["environment"]["UV_PROJECT_ENVIRONMENT"] == str(P / ".venv")):
    raise AssertionError
if any(x in prepared["environment"] for x in plan.CAP_VARIABLES):
    raise AssertionError
gate_names = [j["name"] for j in prepared["jobs"] if j["kind"] == "gate"]
if not (
    gate_names
    == [
        "architecture",
        "runtime-api-contract",
        "static-invocation",
        "ruff",
        "ruff-format",
        "workspace-verify",
        "ci-parity",
    ]
):
    raise AssertionError
if any(
    flag in prepared["jobs"][-1]["argv"]
    for flag in [
        "--skip-doctor",
        "--skip-browser",
        "--skip-docs",
        "--skip-runtime-http",
        "--backend-only",
    ]
):
    raise AssertionError
if not (prepared["jobs"][-2]["argv"][-1] == "--backend-only"):
    raise AssertionError
lint_job = next(j for j in prepared["jobs"] if j["name"] == "ruff")
if not (len(lint_job["argv"][4:]) == len(prepared["changed_python_lint_paths"])):
    raise AssertionError
properties = []
sentinel_root = observed_o / "preservation-controls"
sentinel_root.mkdir(exist_ok=False)
existing = sentinel_root / "existing-output"
existing.mkdir()
sentinel = existing / "unique-data.txt"
sentinel.write_text("preserve unique data\n")
broken = sentinel_root / "broken-output"
broken.symlink_to(sentinel_root / "absent-target")
old_prepare = plan.prepare
counter = [0]


def counted_prepare(*a: object, **kw: object) -> None:
    counter[0] += 1
    raise AssertionError("prepare must not be entered for a reused output")


plan.prepare = counted_prepare
old_argv = sys.argv
try:
    for path in [existing, broken]:
        sys.argv = [
            "plan_wave.py",
            "--repo",
            str(R),
            "--candidate",
            REF,
            "--output-root",
            str(path),
        ]
        try:
            plan.main()
        except RuntimeError as e:
            if "exists" not in str(e):
                raise AssertionError from None
        else:
            raise AssertionError("existing output/symlink admitted")
finally:
    plan.prepare = old_prepare
    sys.argv = old_argv
if not (
    counter[0] == 0 and sentinel.read_text() == "preserve unique data\n" and broken.is_symlink()
):
    raise AssertionError
properties.append(
    {
        "property": "raw existing output and dangling symlink refused before prepare/process",
        "cases": 2,
        "prepare_counter": 0,
        "sentinel_preserved": True,
        "outcome": "PASS",
    }
)
basetemp = sentinel_root / "existing-basetemp"
basetemp.mkdir()
data = basetemp / "unique-data.txt"
data.write_text("unchanged\n")
proc_counter = [0]


class FakeProcess:
    async def wait(self) -> int:
        return 42


async def fake_spawn(*a: object, **kw: object) -> object:
    proc_counter[0] += 1
    return FakeProcess()


old_spawn = plan.asyncio.create_subprocess_exec
plan.asyncio.create_subprocess_exec = fake_spawn


def fixture(output: object) -> dict[str, object]:
    return {
        "repo": str(R),
        "output_root": str(output),
        "tracked_dirty": "",
        "candidate_sha": REF,
        "observed_head": REF,
        "missing_required_paths": [],
        "required_upstream": {},
        "owner_packet_extra_inputs": [],
        "interpreter": sys.executable,
        "jobs": [
            {
                "kind": "importer",
                "name": "spy-importer",
                "argv": ["NEVER_EXECUTED"],
                "cwd": str(P),
                "output": str(output / "checks/importer"),
                "junit": None,
                "environment": {"TMPDIR": str(output / "tmp/importer")},
            },
            {
                "kind": "numerical",
                "name": "spy-numeric",
                "argv": ["NEVER_EXECUTED", "--basetemp", str(basetemp)],
                "cwd": str(P),
                "output": str(output / "checks/numeric"),
                "junit": None,
                "environment": {"TMPDIR": str(output / "tmp/numeric")},
            },
        ],
    }


try:
    output = sentinel_root / "not-started-wave"
    try:
        asyncio.run(plan.execute(fixture(output)))
    except RuntimeError as e:
        if "basetemp" not in str(e):
            raise AssertionError from None
    else:
        raise AssertionError("existing numeric basetemp admitted")
    if not (
        proc_counter[0] == 0
        and not (output / "wave-started.json").exists()
        and data.read_text() == "unchanged\n"
    ):
        raise AssertionError
    properties.append(
        {
            "property": "numeric basetemp refused before marker/importer process",
            "process_counter": 0,
            "marker_written": False,
            "sentinel_preserved": True,
            "outcome": "PASS",
        }
    )
    # Retain admission function names/identities, remove the actual property.
    original = plan.require_absent.__code__

    def noop(path: object, *, purpose: str) -> None:
        return None

    plan.require_absent.__code__ = noop.__code__
    try:
        removed = sentinel_root / "removed-admission-wave"
        result = asyncio.run(plan.execute(fixture(removed)))
    finally:
        plan.require_absent.__code__ = original
    if not (
        result == 1
        and proc_counter[0] == 1
        and (removed / "wave-started.json").exists()
        and data.read_text() == "unchanged\n"
    ):
        raise AssertionError
    properties.append(
        {
            "property_removed": "scratch admission only; function identity/names retained",
            "process_spy_counter": 1,
            "real_children_launched": 0,
            "marker_written": True,
            "sentinel_preserved": True,
            "outcome": "EXPECTED_DISCRIMINATING_ESCAPE",
        }
    )
finally:
    plan.asyncio.create_subprocess_exec = old_spawn
junit = sentinel_root / "four-outcomes.xml"
junit.write_text(
    "<testsuite><testcase/><testcase><skipped/></testcase><testca"
    "se><failure/></testcase><testcase><error/></testcase></tests"
    "uite>"
)
counts = check.junit_counts(junit)
if not (counts == {"cases": 4, "passed": 1, "failed": 1, "errors": 1, "skipped": 1}):
    raise AssertionError
dtd = sentinel_root / "dtd.xml"
dtd.write_text(
    '<!DOCTYPE x [<!ENTITY x "expanded">]><te'  # Exact bound literal continuation.
    'stsuite><testcase name="&x;"/></testsuit'  # Exact bound literal continuation.
    "e>"  # Exact bound literal continuation.
)
try:
    check.junit_counts(dtd)
except Exception as e:
    if not (type(e).__name__ == "DTDForbidden"):
        raise AssertionError from None
else:
    raise AssertionError("DTD accepted")
properties.append(
    {
        "property": "actual JUnit parser recomputes mixed outcomes and refusesDTD",
        "counts": counts,
        "DTD": "REFUSED",
        "outcome": "PASS",
    }
)
for path, h in before.items():
    if not (hashlib.sha256((R / path).read_bytes()).hexdigest() == h):
        raise AssertionError
moderate = {
    "source_sha": REF,
    "source_tree": "c10843f74311d6973ccefea609cd7bf34bc828fe",
    "base_sha": BASE,
    "footprint": paths,
    "property_paths": before,
    "before_after_equal": True,
    "native_wave_state": "UNRUN; no nativeCI/numeric command launched",
    "native_paths": 120,
    "owner_packet_inputs": 2,
    "planned_numeric_jobs": 7,
    "group_counts": prepared["group_path_counts"],
    "runtime_case_counts": "UNRUN until real JUnit",
    "planned_Ruff_denominator": len(prepared["changed_python_lint_paths"]),
    "planned_Ruff_docs_artifact_paths": sum(
        "/docs/" in x for x in prepared["changed_python_lint_paths"]
    ),
    "configured_pytest_addopts": defaults,
    "required_gate_sequence": gate_names,
    "runtime_environment": prepared["environment"],
    "controls": properties,
    "code_verdict": "GO-bounded-owned-harness-readiness-and-preservation",
    "browser_capability_receipt": "browser-capability-receipt.json",
    "authority": (
        "Browser launch and runner readiness do not equal doctor/full"
        "CI/numeric PASS or findingclosure."
    ),
}
(observed_o / "harness-independent-review.json").write_text(json.dumps(moderate, indent=2) + "\n")
_write_stdout(json.dumps(moderate, indent=2))
