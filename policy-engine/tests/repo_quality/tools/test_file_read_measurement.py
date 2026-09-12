"""Unreadable filesystem observations must not be reported as measured absence."""

from pathlib import Path

import pytest

from tools.lib import fs


@pytest.mark.parametrize("probe_name", ["measured_is_file", "measured_is_dir"])
def test_parent_permission_denial_is_unreadable_not_absent(tmp_path: Path, probe_name: str) -> None:
    parent = tmp_path / "parent"
    parent.mkdir()
    target = parent / "target"
    target.mkdir()
    parent.chmod(0)
    try:
        with fs.measure_file_reads(tmp_path) as reads:
            with pytest.raises(PermissionError):
                getattr(fs, probe_name)(target)
            receipt = reads.snapshot(complete_verdict=False)
        assert receipt["inputs"][-1]["status"] == "unreadable"
        assert receipt["inputs"][-1]["error"] == "PermissionError"
        assert receipt["complete_verdict"] is False
    finally:
        parent.chmod(0o700)


def test_directory_probe_distinguishes_present_file_directory_and_missing(tmp_path: Path) -> None:
    regular = tmp_path / "regular"
    regular.write_text("bytes")
    with fs.measure_file_reads(tmp_path) as reads:
        assert fs.measured_is_dir(tmp_path)
        assert not fs.measured_is_dir(regular)
        assert not fs.measured_is_dir(tmp_path / "missing")
    assert [item["status"] for item in reads.snapshot()["inputs"]] == ["present", "present", "absent"]
