from __future__ import annotations

from pathlib import Path

import pytest

from tools.quality.testing import check_fabric_exception_baseline as checker


def test_fabric_exception_baseline_missing_source_is_unrun(
    tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        checker.sys, "argv", ["check-fabric-exception-baseline", "--repo-root", str(tmp_path)]
    )
    assert checker.main() == 2
    output = capsys.readouterr()
    assert "UNRUN" in output.out + output.err
    assert "no complete verdict" in output.out + output.err


def test_fabric_exception_baseline_names_unmeasured_handler_syntax(
    tmp_path: Path,
    capsys,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import hashlib

    source = tmp_path / "src/polisyos/fabric/candidate.py"
    source.parent.mkdir(parents=True)
    source.write_text("try:\n    run()\nexcept (ValueError, Exception):\n    raise\n")
    monkeypatch.setattr(checker, "EXPECTED_MATCH_COUNT", 0)
    monkeypatch.setattr(checker, "EXPECTED_OUTPUT_SHA256", hashlib.sha256(b"").hexdigest())
    monkeypatch.setattr(
        checker.sys, "argv", ["check-fabric-exception-baseline", "--repo-root", str(tmp_path)]
    )
    assert checker.main() == 0
    output = capsys.readouterr().out
    assert "literal-text fingerprint unchanged" in output
    assert "Unmeasured:" in output
    assert "tuple/bare/aliased handlers" in output
    assert "runtime exception safety" in output


def test_fabric_exception_baseline_unavailable_scanner_is_unrun(
    tmp_path: Path,
    capsys,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "src/polisyos/fabric"
    source.mkdir(parents=True)

    def unavailable(*args, **kwargs):
        raise FileNotFoundError("rg is unavailable")

    monkeypatch.setattr(checker.subprocess, "run", unavailable)
    monkeypatch.setattr(
        checker.sys, "argv", ["check-fabric-exception-baseline", "--repo-root", str(tmp_path)]
    )
    assert checker.main() == 2
    assert "UNRUN" in capsys.readouterr().err


def test_fabric_exception_baseline_refuses_an_added_literal_handler(
    tmp_path: Path,
    capsys,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An intentional refreshed fingerprint still refuses the next source drift."""
    import hashlib

    source = tmp_path / "src/polisyos/fabric/candidate.py"
    source.parent.mkdir(parents=True)
    source.write_text("try:\n    run()\nexcept Exception:\n    raise\n")
    expected = "src/polisyos/fabric/candidate.py:except Exception:"
    monkeypatch.setattr(checker, "EXPECTED_MATCH_COUNT", 1)
    monkeypatch.setattr(
        checker, "EXPECTED_OUTPUT_SHA256", hashlib.sha256(expected.encode()).hexdigest()
    )
    monkeypatch.setattr(
        checker.sys, "argv", ["check-fabric-exception-baseline", "--repo-root", str(tmp_path)]
    )
    assert checker.main() == 0
    capsys.readouterr()

    source.write_text(source.read_text() + "try:\n    other()\nexcept Exception:\n    raise\n")
    assert checker.main() == 1
    output = capsys.readouterr().err
    assert "FAILED: literal-text fingerprint changed" in output
    assert "expected count=1" in output
    assert "actual   count=2" in output
