from __future__ import annotations

import json
from pathlib import Path

from polisyos.ir.loading.norm_pack import NormPack, NormRule, RuleType
from polisyos.scientist.methods.doe.designs import SensitivityMethod, SensitivityResult
from tools.ops_runners.runtime_cli import main


def _norm_rule(norm_id: str, description: str) -> NormRule:
    return NormRule(
        norm_id=norm_id,
        rule_type=RuleType.OBLIGATION,
        description=description,
    )


def test_cli_lex_impact_json_output(tmp_path: Path, capsys) -> None:
    old_pack = NormPack(
        pack_id="normpack.old",
        jurisdiction="ua",
        norms=[_norm_rule("n.a", "A"), _norm_rule("n.b", "B")],
    )
    new_pack = NormPack(
        pack_id="normpack.new",
        jurisdiction="ua",
        norms=[_norm_rule("n.a", "A+"), _norm_rule("n.c", "C")],
    )

    old_path = tmp_path / "old.json"
    new_path = tmp_path / "new.json"
    old_path.write_text(old_pack.model_dump_json(indent=2), encoding="utf-8")
    new_path.write_text(new_pack.model_dump_json(indent=2), encoding="utf-8")

    code = main(
        [
            "lex",
            "impact",
            str(old_path),
            str(new_path),
            "--format",
            "json",
            "--cas-root",
            str(tmp_path / ".polisyos"),
        ]
    )
    out = capsys.readouterr().out

    assert code == 0
    payload = json.loads(out)
    assert payload["norms_added"] == 1
    assert payload["norms_removed"] == 1
    assert payload["norms_modified"] == 1


def test_cli_stress_test_json_output(tmp_path: Path, capsys) -> None:
    config = {
        "plan": {
            "parameter_specs": [
                {"name": "x", "lower_bound": -1.0, "upper_bound": 1.0},
                {"name": "y", "lower_bound": -1.0, "upper_bound": 1.0},
            ],
            "strategy": "grid_extreme",
            "max_iterations": 8,
            "vulnerability_threshold": 2.0,
            "stop_on_first_vulnerability": False,
        },
        "objective": {"type": "quadratic"},
    }
    config_path = tmp_path / "stress.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    code = main(
        [
            "scientist",
            "stress-test",
            "--config",
            str(config_path),
            "--format",
            "json",
            "--cas-root",
            str(tmp_path / ".polisyos"),
        ]
    )
    out = capsys.readouterr().out

    assert code == 0
    payload = json.loads(out)
    assert payload["report_id"]
    assert payload["total_scenarios_evaluated"] >= 4
    assert "cas_artifact_id" in payload


def test_cli_sensitivity_run_json_output(tmp_path: Path, capsys, monkeypatch) -> None:
    config = {
        "plan": {
            "method": "morris",
            "parameter_specs": [{"name": "x", "lower_bound": 0.0, "upper_bound": 1.0}],
            "n_trajectories": 2,
        },
        "samples": [[0.1], [0.9]],
        "outputs": [1.0, 2.0],
    }
    config_path = tmp_path / "sensitivity.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    import polisyos.scientist.methods.doe.analysis as doe_analysis

    def _fake_analyze(plan, samples, outputs):
        del plan, samples, outputs
        return SensitivityResult(
            method=SensitivityMethod.MORRIS,
            parameter_names=["x"],
            ranking=["x"],
            total_runs=2,
            successful_runs=2,
            failed_runs=0,
        )

    monkeypatch.setattr(doe_analysis, "analyze_sensitivity", _fake_analyze)

    code = main(
        [
            "scientist",
            "sensitivity",
            "run",
            "--config",
            str(config_path),
            "--format",
            "json",
            "--cas-root",
            str(tmp_path / ".polisyos"),
        ]
    )
    out = capsys.readouterr().out

    assert code == 0
    payload = json.loads(out)
    assert payload["method"] == "morris"
    assert payload["cas_artifact_id"]


def test_cli_backtest_json_output(tmp_path: Path, capsys) -> None:
    history = {"tax_revenue": [10.0, 11.0, 12.0, 12.5]}
    history_path = tmp_path / "history.json"
    history_path.write_text(json.dumps(history), encoding="utf-8")

    config = {
        "plans": [
            {
                "plan_id": "bt_cli_1",
                "plan_label": "CLI backtest",
                "historical_data_path": str(history_path),
                "intervention_step": 2,
                "ground_truth_outcomes": {"tax_revenue": [12.6, 12.8]},
                "target_metrics": ["tax_revenue"],
                "prediction_source": "provided",
                "predicted_outcomes": {"tax_revenue": [12.5, 12.7]},
            }
        ]
    }
    config_path = tmp_path / "backtest.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    code = main(
        [
            "scientist",
            "backtest",
            "--config",
            str(config_path),
            "--format",
            "json",
            "--cas-root",
            str(tmp_path / ".polisyos"),
        ]
    )
    out = capsys.readouterr().out

    assert code == 0
    payload = json.loads(out)
    assert payload["report_id"]
    assert payload["n_scenarios"] == 1
    assert payload["cas_artifact_id"]
