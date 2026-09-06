"""Schema findings must depend on current models and artifacts across stations."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
DRIVER = """
import sys
from pathlib import Path
from polisyos.schemas.abi_models import ABIModelEntry, CompatMode, Lifecycle, Priority
from tools.quality.diagnostics import gen_schema as g
from tools.quality.diagnostics import generate_ir_reference_catalog as docs

root = Path(sys.argv[1])
sys.path.insert(0, str(root / 'src'))
g.REPO_ROOT = root
g.SRC_ROOT = root / 'src'
docs.REPO_ROOT = root
docs.IR_REFERENCE_PATH = root / 'docs/ir/schema-catalog.md'
docs.SCHEMA_REFERENCE_PATH = root / 'docs/schemas.md'
# Supply a bounded catalog while retaining the real reference renderer and checks.
docs.get_ir_schema_catalog = lambda: docs.IRSchemaCatalog(types=(), exports=())
entry = ABIModelEntry(
    abi_key='envelope', fqn='envelope.Envelope', module='ir',
    schema_file='envelope.schema.json', priority=Priority.P1,
    compat_mode=CompatMode.STRICT, lifecycle=Lifecycle.ACTIVE,
)
g.select_abi_entries = lambda *args, **kwargs: (entry,)
raise SystemExit(g.main(['--output-dir', str(root / 'schemas/snapshots'), *sys.argv[2:]]))
"""


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", "-c", DRIVER, str(root), *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )


def _findings(result: subprocess.CompletedProcess[str], root: Path) -> set[str]:
    assert result.returncode in (0, 1), result.stdout + result.stderr
    return {
        line.split(": ", 1)[1].removeprefix(f"{root}/")
        for line in result.stdout.splitlines()
        if line.startswith("- ")
    }


@pytest.fixture
def station(tmp_path: Path) -> Path:
    source = tmp_path / "src"
    source.mkdir()
    (source / "dependency.py").write_text(
        "from pydantic import BaseModel\nclass Child(BaseModel):\n    amount: int\n"
    )
    (source / "envelope.py").write_text(
        "from pydantic import BaseModel\nfrom dependency import Child\n"
        "class Envelope(BaseModel):\n    child: Child\n"
    )
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    first = _run(tmp_path)
    assert first.returncode == 0, first.stdout + first.stderr
    subprocess.run(["git", "-C", str(tmp_path), "add", "src", "schemas", "docs"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "-c",
            "user.name=Schema test",
            "-c",
            "user.email=schema@example.invalid",
            "commit",
            "-qm",
            "baseline",
        ],
        check=True,
    )
    baseline = _run(tmp_path, "--check", "--skip-if-unchanged")
    assert baseline.returncode == 0, baseline.stdout + baseline.stderr
    return tmp_path


def _change_dependency(root: Path) -> None:
    dependency = root / "src/dependency.py"
    dependency.write_text(dependency.read_text().replace("amount: int", "amount: str"))


@pytest.mark.parametrize("hint", [(), ("--changed-only",), ("--skip-if-unchanged",)])
def test_dependency_drift_has_the_same_complete_set_with_warm_and_cold_caches(
    station: Path, hint: tuple[str, ...]
) -> None:
    parent_before = (station / "src/envelope.py").read_bytes()
    _change_dependency(station)
    warm = _run(station, "--check", *hint)
    cold = _run(station, "--check", "--cache-dir", str(station / "cold-cache"))
    expected = {"schemas/snapshots/ir/envelope.schema.json", "schemas/snapshots/ir/_manifest.json"}
    assert _findings(warm, station) == _findings(cold, station) == expected
    assert (station / "src/envelope.py").read_bytes() == parent_before


def test_regeneration_elsewhere_does_not_make_a_warm_station_falsely_red(station: Path) -> None:
    _change_dependency(station)
    generated = _run(station, "--cache-dir", str(station / "independent-cache"))
    assert generated.returncode == 0, generated.stdout + generated.stderr
    warm = _run(station, "--check")
    cold = _run(station, "--check", "--cache-dir", str(station / "cold-cache"))
    assert _findings(warm, station) == _findings(cold, station) == set()
    assert warm.returncode == cold.returncode == 0


@pytest.mark.parametrize("hint", [(), ("--changed-only",), ("--skip-if-unchanged",)])
def test_regeneration_consumes_changed_dependencies(station: Path, hint: tuple[str, ...]) -> None:
    _change_dependency(station)
    generated = _run(station, *hint)
    assert generated.returncode == 0, generated.stdout + generated.stderr
    schema = json.loads((station / "schemas/snapshots/ir/envelope.schema.json").read_text())
    assert schema["$defs"]["Child"]["properties"]["amount"]["type"] == "string"


@pytest.mark.parametrize(
    "artifact",
    [
        "schemas/snapshots/ir/envelope.schema.json",
        "schemas/snapshots/ir/_manifest.json",
        "docs/ir/schema-catalog.md",
        "docs/schemas.md",
    ],
)
@pytest.mark.parametrize("hint", [("--changed-only",), ("--skip-if-unchanged",)])
def test_successful_baseline_cannot_hide_artifact_corruption(
    station: Path, artifact: str, hint: tuple[str, ...]
) -> None:
    path = station / artifact
    path.write_text(path.read_text() + "\n")
    if path.name == "_manifest.json":
        manifest = json.loads(path.read_text())
        manifest["content_hash"] = "wrong"
        path.write_text(json.dumps(manifest))
    warm = _run(station, "--check", *hint)
    assert _findings(warm, station) == {artifact}
