from __future__ import annotations

from pathlib import Path

from tools.ops_runners.release.check_release_artifact_sizes import evaluate_artifacts


def test_release_artifact_policy_flags_oversized_bundle(tmp_path: Path) -> None:
    (tmp_path / "policy_engine-0.1.0-py3-none-any.whl").write_bytes(b"x" * 32)
    (tmp_path / "policy_engine-0.1.0.tar.gz").write_bytes(b"x" * 64)

    report = evaluate_artifacts(
        tmp_path,
        {
            "total_max_bytes": 1024,
            "artifact": [
                {
                    "name": "Python wheel",
                    "pattern": "policy_engine-*.whl",
                    "owner": "platform",
                    "max_bytes": 16,
                },
                {
                    "name": "Python source distribution",
                    "pattern": "policy_engine-*.tar.gz",
                    "owner": "platform",
                    "max_bytes": 128,
                },
            ],
        },
    )

    assert report["blockers"]
    assert any("Python wheel" in blocker for blocker in report["blockers"])


def test_release_artifact_policy_flags_missing_expected_asset(tmp_path: Path) -> None:
    (tmp_path / "SHA256SUMS").write_text("abc", encoding="utf-8")

    report = evaluate_artifacts(
        tmp_path,
        {
            "artifact": [
                {
                    "name": "Runtime dashboard bundle",
                    "pattern": "runtime-dashboard-dist-*.tar.gz",
                    "owner": "runtime-dashboard",
                    "max_bytes": 1024,
                }
            ]
        },
    )

    assert report["blockers"]
    assert "no artifact matched pattern" in report["blockers"][0]
