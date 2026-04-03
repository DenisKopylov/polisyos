from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _env() -> dict[str, str]:
    env = os.environ.copy()
    pythonpath = f"{REPO_ROOT / 'src'}:{REPO_ROOT}"
    if env.get("PYTHONPATH"):
        pythonpath = f"{pythonpath}:{env['PYTHONPATH']}"
    env["PYTHONPATH"] = pythonpath
    env["BENCH_TEST_FAST"] = "1"
    return env


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=REPO_ROOT,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )


def test_proof_closure_prod_smoke_emits_extended_fields(tmp_path: Path) -> None:
    out = tmp_path / "proof_closure_prod.json"
    result = _run(
        [
            "python3",
            "benchmarks/proof_closure/proof_closure_prod.py",
            "--mode",
            "smoke",
            "--quiet",
            "--json",
            str(out),
        ]
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["suite_id"] == "proof_closure_prod"
    assert payload["validation_contour"] == "production"
    assert payload["visibility"] == "public"
    assert payload["release_gate_results"]["passes_all"] is True


def test_hidden_release_suite_requires_manifest_in_acceptance(tmp_path: Path) -> None:
    out = tmp_path / "proof_closure_hidden.json"
    result = _run(
        [
            "python3",
            "benchmarks/proof_closure/proof_closure_hidden_release.py",
            "--mode",
            "acceptance",
            "--quiet",
            "--json",
            str(out),
        ]
    )
    assert result.returncode == 2
    assert "hidden release manifest required" in (result.stdout + result.stderr)


def test_strategic_hidden_release_requires_manifest_in_acceptance(tmp_path: Path) -> None:
    out = tmp_path / "strategic_hidden.json"
    result = _run(
        [
            "python3",
            "benchmarks/strategic/strategic_solver_hidden_release.py",
            "--mode",
            "acceptance",
            "--quiet",
            "--json",
            str(out),
        ]
    )
    assert result.returncode == 2
    assert "hidden release manifest required" in (result.stdout + result.stderr)


def test_release_summary_merges_new_contours(tmp_path: Path) -> None:
    proof_out = tmp_path / "proof.json"
    academic_out = tmp_path / "academic.json"
    for script, out in (
        ("benchmarks/proof_closure/proof_closure_prod.py", proof_out),
        ("benchmarks/distributional/distributional_public.py", academic_out),
    ):
        result = _run(["python3", script, "--mode", "smoke", "--quiet", "--json", str(out)])
        assert result.returncode == 0, result.stdout + result.stderr

    summary_path = tmp_path / "release_summary.json"
    result = _run(
        [
            "python3",
            "benchmarks/build_release_summary.py",
            "--json-dir",
            str(tmp_path),
            "--out",
            str(summary_path),
        ]
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert payload["production_contour"]["n_suites"] == 1
    assert payload["academic_contour"]["n_suites"] == 1
    assert "leaderboard_tables" in payload
    assert "production" in payload["leaderboard_tables"]
    assert "replay_determinism" in payload["leaderboard_tables"]["production"]
    assert "release_gate_results" in payload
    assert "proof_closure" in payload["release_gate_results"]["production"]
