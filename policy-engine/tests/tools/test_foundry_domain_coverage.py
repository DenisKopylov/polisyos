from __future__ import annotations

from pathlib import Path

from tools.ci import check_foundry_domain_coverage


def _coverage_file(covered_lines: int, num_statements: int) -> dict[str, object]:
    return {
        "summary": {
            "covered_lines": covered_lines,
            "num_statements": num_statements,
        }
    }


def _payload_with_all_domains(repo_root: Path) -> dict[str, object]:
    return {
        "files": {
            str(
                repo_root / "policy-engine/src/polisyos/foundry/_executor_graph.py"
            ): _coverage_file(95, 100),
            str(
                repo_root / "policy-engine/src/polisyos/foundry/mechanisms/fiscal.py"
            ): _coverage_file(90, 100),
            str(
                repo_root
                / "policy-engine/src/polisyos/foundry/methods/catalog/bayesian/regression.py"
            ): _coverage_file(82, 100),
            str(
                repo_root / "policy-engine/src/polisyos/foundry/methods/catalog/ml/regression.py"
            ): _coverage_file(75, 100),
            str(
                repo_root / "policy-engine/src/polisyos/foundry/methods/catalog/spatial/analysis.py"
            ): _coverage_file(76, 100),
            str(repo_root / "policy-engine/src/polisyos/foundry/trace.py"): _coverage_file(3, 10),
            str(repo_root / "policy-engine/src/polisyos/foundry/queue.py"): _coverage_file(4, 10),
            str(repo_root / "policy-engine/src/polisyos/foundry/specs.py"): _coverage_file(5, 10),
            str(repo_root / "policy-engine/src/polisyos/foundry/profiles.py"): _coverage_file(
                2, 10
            ),
        }
    }


def test_foundry_domain_coverage_ratchet_passes_when_all_targets_are_met(tmp_path: Path) -> None:
    payload = _payload_with_all_domains(tmp_path)

    summaries, findings = check_foundry_domain_coverage.evaluate_foundry_domain_coverage(
        payload,
        repo_root=tmp_path,
    )

    assert findings == []
    assert {summary.name for summary in summaries} >= {
        "executor_internals",
        "core_mechanisms",
        "bayesian_methods",
        "ml_methods",
        "spatial_methods",
    }


def test_foundry_domain_coverage_ratchet_reports_threshold_and_missing_domain_failures(
    tmp_path: Path,
) -> None:
    payload = _payload_with_all_domains(tmp_path)
    payload["files"][str(tmp_path / "policy-engine/src/polisyos/foundry/mechanisms/fiscal.py")] = (
        _coverage_file(40, 100)
    )
    payload["files"].pop(
        str(tmp_path / "policy-engine/src/polisyos/foundry/methods/catalog/spatial/analysis.py")
    )

    _summaries, findings = check_foundry_domain_coverage.evaluate_foundry_domain_coverage(
        payload,
        repo_root=tmp_path,
    )

    assert any("core_mechanisms" in finding and "40.0%" in finding for finding in findings)
    assert any(
        "spatial_methods" in finding and "no coverage files matched" in finding
        for finding in findings
    )


def test_summarize_domain_normalizes_absolute_paths_against_repo_root(tmp_path: Path) -> None:
    payload = {
        "files": {
            str(tmp_path / "policy-engine/src/polisyos/foundry/specs.py"): _coverage_file(7, 10),
        }
    }
    target = next(
        target
        for target in check_foundry_domain_coverage.FOUNDRY_DOMAIN_TARGETS
        if target.name == "specs_module"
    )

    summary = check_foundry_domain_coverage.summarize_domain(
        payload,
        target,
        repo_root=tmp_path,
    )

    assert summary.percent_covered == 70.0
    assert summary.matched_files == ("policy-engine/src/polisyos/foundry/specs.py",)
