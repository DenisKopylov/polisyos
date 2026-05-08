from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_run_foundry_ws9_frontier_demo_emits_json_payload() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / "tools" / "research" / "demos" / "run_foundry_ws9_frontier_demo.py"
    completed = subprocess.run(
        [sys.executable, str(script)],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(completed.stdout)
    assert sorted(payload) == [
        "foundation_model_policy_analysis",
        "ft_transformer",
        "proximal_bridge",
    ]
    assert payload["proximal_bridge"]["report"]["status"] == "success"
    assert payload["ft_transformer"]["result"]["metrics"]["r_squared"] > 0.25
    assert payload["foundation_model_policy_analysis"]["result"]["runtime_backend"] == "tfidf"
