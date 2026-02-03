from __future__ import annotations

from pathlib import Path


def test_no_io_in_kernel_modules() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "polisyos" / "foundry"
    for subdir in ("compile", "execute"):
        for path in (root / subdir).rglob("*.py"):
            text = path.read_text("utf-8")
            assert "open(" not in text
            assert "subprocess.run" not in text
            assert "requests." not in text
