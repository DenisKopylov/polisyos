"""Remove CR1's decisive content check in an isolated import and run its unchanged negative."""

import importlib.util
from pathlib import Path
import sys
import tempfile

import polisyos.runtime.http.services.control  # noqa: F401 - supported cold import order
import pytest

if __name__ == "__main__":
    module_name = "polisyos.runtime.quality.adaptation_transition"
    source_path = Path("src/polisyos/runtime/quality/adaptation_transition.py")
    source = source_path.read_text()
    decisive = "if row.topic != topic or row.event_key != key or row.payload != payload:"
    assert source.count(decisive) == 1
    raw = Path("docs/superpowers/journals/gy-builders/b/raw")
    raw.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=raw) as directory:
        mutated = Path(directory) / "adaptation_transition.py"
        mutated.write_text(source.replace(decisive, "if False:  # removed decisive content check"))
        spec = importlib.util.spec_from_file_location(module_name, mutated)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        raise SystemExit(pytest.main([
            "tests/unit/runtime/quality/test_adaptation_transition.py::"
            "test_conflicting_duplicate_cannot_replace_original_request",
            "-o", "addopts=", "-q",
        ]))
