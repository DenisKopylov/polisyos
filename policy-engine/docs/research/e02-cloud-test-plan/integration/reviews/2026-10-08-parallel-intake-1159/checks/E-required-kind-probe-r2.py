import hashlib
import json
import runpy
import subprocess
import sys
import tempfile
from pathlib import Path

root, checkout, source, out = sys.argv[1:]
root, checkout, out = Path(root), Path(checkout), Path(out)
sys.path.insert(0, str(checkout / "policy-engine/src"))
from polisyos.core.artifacts import FileSystemCAS
from polisyos.ir.analytics.backtest import load_backtest_report
from polisyos.scientist.governance.backtest_matrix import BacktestKind, BacktestMatrixRunner
from polisyos.scientist.governance.calibration_leaderboard import CalibrationLeaderboard

fixture = runpy.run_path(str(checkout / "policy-engine/tests/unit/scientist/governance/test_calibration_leaderboard.py"))
promotion = runpy.run_path(str(checkout / "policy-engine/tests/unit/scientist/governance/test_interval_basis_promotion.py"))
tmp = Path(tempfile.mkdtemp(prefix="required-kind-", dir=out))  # Retained; no automatic deletion.
tmp = Path(tmp)
store = FileSystemCAS(tmp / "cas")
missing_kind = list(BacktestKind)[-1]
runner = BacktestMatrixRunner(store)
complete = runner.run({kind: promotion["_bundle"](tmp, kind, None) for kind in BacktestKind})
missing = runner.run({kind: promotion["_bundle"](tmp, kind, None) for kind in BacktestKind if kind != missing_kind})
report = load_backtest_report(store, missing.backtest_report_ref)
assert missing_kind.value not in {scenario.metadata.get("backtest_kind") for scenario in report.scenarios}
def entry(matrix, name):
    return CalibrationLeaderboard(store).build_entry(
        run_id=name, candidate_ref=None,
        governance_report=fixture["_governance_report"](),
        calibration_fit_score=0.9, backtest_matrix=matrix,
        stress_scenarios=fixture["_stress_result"](),
    )
positive = entry(complete, "full-real-kind-fixture")
ordinary = entry(missing, "natural-missing-kind-fixture")
forged = missing.model_copy(deep=True)
forged.gap_flags = []
for item in forged.kind_results:
    if item.kind == missing_kind:
        assert item.n_scenarios == 0 and item.scenario_ids == []
        item.status = "ok"
        item.gap_flag = None
scores = [item.score for item in forged.kind_results if item.score is not None]
forged.composite_score = sum(scores) / len(scores)
damaged = entry(forged, "retained-required-kind-markers")
observation = {
    "source": source, "missing_kind": missing_kind.value,
    "actual_report_scenarios": len(report.scenarios),
    "actual_report_kind_set": sorted({s.metadata.get("backtest_kind") for s in report.scenarios}),
    "report_metadata": report.metadata,
    "complete_fixture_eligible": positive.metrics.eligible_for_promotion,
    "natural_missing_fixture_eligible": ordinary.metrics.eligible_for_promotion,
    "forged_missing_fixture_eligible": damaged.metrics.eligible_for_promotion,
    "forged_gap_flags": damaged.metrics.gap_flags,
    "property": "A required kind absent from actual persisted report cannot become complete promotion evidence through an empty ok matrix row.",
    "qualification": "Actual matrix/CAS/report/leaderboard; approval/point profiles are synthetic fixtures, no institutional or production authority claim.",
}
(out / "observation.json").write_text(json.dumps(observation, indent=2) + "\n")
print(json.dumps(observation))
tree = subprocess.check_output(["git", "ls-tree", "-r", source, "policy-engine/src"], cwd=root).splitlines()
blobs = {}
for line in tree:
    meta, name = line.split(b"\t", 1)
    blobs[name.decode()] = meta.split()[2].decode()
origins, bad = [], []
for name, module in sorted(sys.modules.items()):
    if (name != "polisyos" and not name.startswith("polisyos.")) or not getattr(module, "__file__", None):
        continue
    path = Path(module.__file__).resolve()
    try:
        rel = path.relative_to(checkout).as_posix()
    except ValueError:
        bad.append({"module": name, "reason": "foreign_source", "path": str(path)})
        continue
    data = path.read_bytes()
    blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
    origins.append({"module": name, "path": rel, "blob": blob, "candidate_blob": blobs.get(rel)})
    if blob != blobs.get(rel):
        bad.append(origins[-1])
summary = {"file_backed_polisyos_modules": len(origins), "mismatches": len(bad)}
(out / "origins.json").write_text(json.dumps({"summary": summary, "origins": origins, "bad": bad}, indent=2) + "\n")
print(json.dumps(summary))
assert not bad, "exact source origins"
assert positive.metrics.eligible_for_promotion, "matching complete positive"
assert not ordinary.metrics.eligible_for_promotion, "unaltered missing-kind negative"
assert not damaged.metrics.eligible_for_promotion, "missing required kind accepted after empty-kind declaration forged"
