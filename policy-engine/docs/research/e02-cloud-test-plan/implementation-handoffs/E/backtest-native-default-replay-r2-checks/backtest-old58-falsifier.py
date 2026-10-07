import importlib.util
import sys
import traceback
from pathlib import Path

from polisyos.scientist.methods.backtesting import orchestrator


def _write_stdout(*values: object, flush: bool = False) -> None:
    """Emit the existing CLI text and optionally flush without logging side effects."""
    sys.stdout.write(" ".join(str(value) for value in values) + "\n")
    if flush:
        sys.stdout.flush()


if not (
    str(Path(orchestrator.__file__)).startswith(
        "/workspace/e02-E-pr38-r2-receipts/backtest-old58-overlay/policy-engine/src/"
    )
):
    raise AssertionError
_write_stdout("SOURCE_COMMIT=58e2d97965c0826c44843a78dcb2f8698d9950a3", flush=True)
_write_stdout("ORCHESTRATOR_ORIGIN=" + orchestrator.__file__, flush=True)
native = orchestrator.run_experiment


def observe(*args: object, **kwargs: object) -> object:
    try:
        return native(*args, **kwargs)
    except Exception:
        traceback.print_exc()
        raise


orchestrator.run_experiment = observe
spec = importlib.util.spec_from_file_location(
    "native_fixture",
    (
        "/workspace/e02-E-backtest-20261006/policy-engine/tests/unit/"
        "scientist/methods/backtesting/test_native_replay.py"
    ),
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
store, plan = module._fixture(
    Path("/workspace/e02-E-pr38-r2-receipts/backtest-old58-complete-tests"), count=1
)
report = orchestrator.BacktestOrchestrator(cas=store).run([plan])
_write_stdout("effective_mode=" + report.prediction_mode_effective, flush=True)
_write_stdout("degraded_reasons=" + repr(report.degraded_reasons), flush=True)
if not (report.prediction_mode_effective == "scientist"):
    raise AssertionError(report.degraded_reasons)
