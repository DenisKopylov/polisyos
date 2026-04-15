from __future__ import annotations

from pathlib import Path

from tools.ci import check_scientist_phase2_ratchet


def _write_source(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "from typing import Any",
                "",
                "payload: dict[str, Any] = {}",
                "value = payload[\"key\"]",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_scientist_phase2_ratchet_passes_with_matching_baseline(tmp_path: Path) -> None:
    source = tmp_path / "tracked.py"
    baseline = tmp_path / "baseline.toml"
    _write_source(source)
    baseline.write_text(
        "\n".join(
            [
                "[explicit_any]",
                "\"tracked.py\" = 1",
                "",
                "[unsafe_cast]",
                "\"tracked.py\" = 0",
                "",
                "[raw_dict_index]",
                "\"tracked.py\" = 1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = check_scientist_phase2_ratchet.main(
        [
            "--repo-root",
            str(tmp_path),
            "--baseline",
            str(baseline.relative_to(tmp_path)),
            "--target",
            "tracked.py",
        ]
    )

    assert exit_code == 0


def test_scientist_phase2_ratchet_fails_on_new_debt_growth(tmp_path: Path) -> None:
    source = tmp_path / "tracked.py"
    baseline = tmp_path / "baseline.toml"
    _write_source(source)
    baseline.write_text(
        "\n".join(
            [
                "[explicit_any]",
                "\"tracked.py\" = 0",
                "",
                "[unsafe_cast]",
                "\"tracked.py\" = 0",
                "",
                "[raw_dict_index]",
                "\"tracked.py\" = 0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = check_scientist_phase2_ratchet.main(
        [
            "--repo-root",
            str(tmp_path),
            "--baseline",
            str(baseline.relative_to(tmp_path)),
            "--target",
            "tracked.py",
        ]
    )

    assert exit_code == 1
