"""Recompute the SIM source/test caller denominator and baseline path join."""

from __future__ import annotations

import ast
import csv
import hashlib
import subprocess
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[7]
BASE = "198076863e143dea9f89f02734b13d50dae3eed5"
TEST_PATHS = {
    "policy-engine/tests/unit/runtime/quality/test_joint_simulation_horizon.py",
    "policy-engine/tests/unit/remediation/test_sim_01.py",
    "policy-engine/tests/unit/remediation/test_sim_02.py",
    "policy-engine/tests/unit/remediation/test_sim_03.py",
}
TOKENS = (
    "JointSimulationHorizonController",
    "higher_order_residuals",
    "_conditional_simulation_value_observation",
    "_DefaultSimulationBoundFoundryValuePort",
)
B25 = (
    "test_summary_distance_requires_one_declared_metric_set",
    "test_smm_missing_required_moment_cannot_win_calibration",
    "test_smm_all_incomparable_candidates_are_explicitly_blocked",
)


def tracked_paths() -> list[str]:
    raw = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, check=True, stdout=subprocess.PIPE
    ).stdout.decode().split("\0")
    return [
        path
        for path in raw
        if path.endswith(".py")
        and (path.startswith("policy-engine/src/") or path.startswith("policy-engine/tests/"))
    ]


def function_hashes(source: str) -> dict[str, str]:
    tree = ast.parse(source)
    return {
        node.name: hashlib.sha256(ast.get_source_segment(source, node).encode()).hexdigest()
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in B25
    }


def main() -> None:
    paths = tracked_paths()
    source = [path for path in paths if path.startswith("policy-engine/src/")]
    tests = [path for path in paths if path.startswith("policy-engine/tests/")]
    print(f"tracked_product_python_files total={len(paths)} src={len(source)} tests={len(tests)}")
    for token in TOKENS:
        hits = [path for path in paths if token.encode() in (ROOT / path).read_bytes()]
        print(f"token={token!r} files={len(hits)}")
        for path in hits:
            print(f"  {path}")

    cells_path = ROOT / "policy-engine/docs/research/e02-cloud-test-plan/results/cells.tsv"
    routes_path = ROOT / "policy-engine/docs/research/e02-cloud-test-plan/results/routes.tsv"
    with cells_path.open(newline="") as stream:
        cells = list(csv.DictReader(stream, delimiter="\t"))
    with routes_path.open(newline="") as stream:
        routes = list(csv.DictReader(stream, delimiter="\t"))
    by_cell: dict[str, list[str]] = defaultdict(list)
    for route in routes:
        if route["unit"] == "A":
            by_cell[route["cell_id"]].append(route["finding_id"])
    rows = [row for row in cells if row["path"] in TEST_PATHS]
    print(f"baseline_existing_test_paths={len(TEST_PATHS)} source_cells={len(rows)}")
    for row in rows:
        print(
            "  "
            + "\t".join(
                (
                    row["id"],
                    row["source_sha"],
                    row["state"],
                    row["path"],
                    ",".join(sorted(by_cell[row["id"]])),
                )
            )
        )
    base_source = subprocess.run(
        ["git", "show", f"{BASE}:policy-engine/tests/unit/remediation/test_sim_03.py"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    ).stdout.decode()
    head_source = (ROOT / "policy-engine/tests/unit/remediation/test_sim_03.py").read_text()
    old, new = function_hashes(base_source), function_hashes(head_source)
    print("B25_preserved_function_body_sha256:")
    for name in B25:
        print(f"  {name} {old[name]} {new[name]} same={old[name] == new[name]}")


if __name__ == "__main__":
    main()
