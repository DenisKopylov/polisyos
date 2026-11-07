"""Exercise the N5 provider observation against the recorded product imports."""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
import types
from contextlib import suppress
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools import authority_bootstrap as host
from tools.loaded_execution_capture import CaptureError, ExpectedSource, SourceExecutionCapture


def _exercise_recorded_ncm_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """Record the real NCM initializer and its selected determinism provider."""
    product = Path.cwd().resolve()
    rows, export_rows, _, _, _, _ = host._selected_snapshot()
    sources = {
        name: ExpectedSource(*row)
        for name, row in rows.items()
        if name == "polisyos" or name.startswith("polisyos.")
    }
    exports = {name: set(value) for name, value in export_rows.items() if name in sources}
    engine_name = "polisyos.foundry.methods.catalog.causal.ncm_engine"
    exports.setdefault(engine_name, set()).add("NCMEngineMethod")
    site = product / ".venv/lib/python3.14/site-packages"
    selector = host._LockedWheelSourceSelector(product, site, (product / "uv.lock").read_bytes())
    wheels = Path(os.environ["POLISYOS_N5_PROVIDER_WHEEL_DIR"]).resolve(strict=True)

    def fetch(url: str, size: int) -> bytes:
        name = url.rsplit("/", 1)[-1]
        content = (wheels / name).read_bytes()
        if len(content) != size:
            raise ValueError("test_provider_wheel_size_mismatch")
        return content

    selector._archive_bytes = fetch

    def select(name: str, origin: str) -> tuple[str, str] | None:
        if name.partition(".")[0] in {"sklearn", "importlib_metadata", "six"}:
            return selector.select(name, origin)
        return None

    recorder = SourceExecutionCapture(
        product,
        sources,
        exports=exports,
        external_source_selector=select,
        external_source_root=site,
    )
    recorder.install()
    # Defer the real ledger's import-time self-observation until its module is
    # complete. This test supplies only the later handoff/anchor, not authority.
    monkeypatch.setitem(
        sys.__dict__,
        "_polisyos_loaded_host_v1",
        {"phase": "collecting", "capture": recorder},
    )
    try:
        engine = importlib.import_module(engine_name)
        ledger = importlib.import_module("polisyos.runtime.quality.confidence_ledger")
        method = engine.NCMEngineMethod
        entry = method.pure_step
        frames: list[tuple[types.CodeType, dict[str, object]]] = []

        def observe(frame: types.FrameType, event: str, arg: object) -> None:
            del arg
            if event == "call" and frame.f_code is entry.__code__:
                frames.append((frame.f_code, frame.f_globals))

        from polisyos.foundry.methods.catalog.causal.protocols import NCMQueryData
        from polisyos.ir.analytics.ncm import ExogenousSpec, NCMSpec, StructuralEquation

        numerical_model = NCMSpec(
            endogenous_vars=["X", "Y"],
            exogenous_specs=[
                ExogenousSpec(variable="U_X", associated_endogenous="X"),
                ExogenousSpec(variable="U_Y", associated_endogenous="Y"),
            ],
            structural_equations=[
                StructuralEquation(
                    variable="X",
                    parents=[],
                    exogenous="U_X",
                    equation_type="linear",
                    equation_params={"intercept": 0.0, "coefficients": {}},
                ),
                StructuralEquation(
                    variable="Y",
                    parents=["X"],
                    exogenous="U_Y",
                    equation_type="linear",
                    equation_params={"intercept": 0.5, "coefficients": {"X": 2.0}},
                ),
            ],
            scm_spec=None,
            is_acyclic=True,
        )
        numerical_query = NCMQueryData(
            ncm_spec=numerical_model,
            interventions=[{"X": 0.0}, {"X": 1.0}],
            query_vars=["Y"],
            n_samples=32,
        )
        previous = sys.getprofile()
        sys.setprofile(observe)
        try:
            numerical_result = entry(
                {"ncm_query_data": numerical_query}, {"n_samples": 32, "__seed__": 7}
            )
        finally:
            sys.setprofile(previous)
        numerical_summary = numerical_result["counterfactual_result"]
        assert numerical_summary["n_worlds"] == 2
        assert numerical_summary["n_samples"] == 32
        world_means = [world["Y"]["mean"] for world in numerical_summary["world_summaries"]]
        assert world_means[1] - world_means[0] == pytest.approx(2.0, abs=1e-12)
        assert len(frames) == 1

        recorder_module = types.ModuleType("recorded_test_host")
        seal = SimpleNamespace(
            state="retained",
            capture=recorder,
            recorder_module=recorder_module,
            owner_module=ledger,
            owner_execution=recorder.completed(ledger.__name__),
        )
        monkeypatch.setitem(
            sys.__dict__,
            "_polisyos_loaded_host_v1",
            {"capture": recorder, "recorder": recorder_module},
        )
        monkeypatch.setattr(ledger, "_LOADED_EXECUTION_OBSERVATION_SEAL", seal)
        # Exercise this bounded provider relation with a test-only host anchor.
        # The actual launcher owns host appointment and its separate checks.
        monkeypatch.setattr(ledger, "_host_recorder_anchor_matches", lambda *_: True)

        before = ledger._observe_n5_early_python_provider(method, entry, tuple(frames))
        assert before is not None
        assert before["predicate_provenance"] == "independently_reconciled", (
            before,
            recorder.diagnostic(),
        )
        assert before["selected_member"] == "STATISTICAL"
        assert before["protected_through_use"] == "not_established"
        unobserved = ledger._observe_n5_early_python_provider(method, entry, ())
        assert unobserved is not None
        assert unobserved["predicate_provenance"] == "not_established"

        original_tier = engine.DeterminismTier
        with monkeypatch.context() as mutation:
            mutation.setattr(engine, "DeterminismTier", type("DeterminismTier", (), {}))
            after = ledger._observe_n5_early_python_provider(method, entry, tuple(frames))
            assert after is not None
            assert after["predicate_provenance"] == "not_established"
        assert engine.DeterminismTier is original_tier
        # Endpoint equality after restoration does not establish through-use protection.
    finally:
        with suppress(CaptureError):
            recorder.close()


def test_recorded_provider_and_consumer_replacement() -> None:
    """Start the real recorder before importing the selected source graph."""
    if not os.environ.get("POLISYOS_N5_PROVIDER_WHEEL_DIR"):
        pytest.skip("set POLISYOS_N5_PROVIDER_WHEEL_DIR to the selected locked wheel directory")
    product = Path(__file__).resolve().parents[4]
    venv = (product / ".venv").resolve(strict=True)
    if Path(sys.prefix).resolve(strict=True) != venv:
        pytest.skip("the selected project virtual environment is required")
    site = product / ".venv/lib/python3.14/site-packages"
    code = (
        "import sys\n"
        "sys.path[:0] = [sys.argv[1], sys.argv[2], sys.argv[3]]\n"
        "import pytest\n"
        "from tests.unit.runtime.quality.test_n5_early_provider_observation "
        "import _exercise_recorded_ncm_provider\n"
        "with pytest.MonkeyPatch.context() as patch:\n"
        "    _exercise_recorded_ncm_provider(patch)\n"
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            "-B",
            "-c",
            code,
            str(product),
            str(product / "src"),
            str(site),
        ],
        cwd=product,
        capture_output=True,
        text=True,
        check=False,
        timeout=150,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
