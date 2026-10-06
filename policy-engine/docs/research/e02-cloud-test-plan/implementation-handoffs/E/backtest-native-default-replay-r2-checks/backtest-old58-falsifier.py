from pathlib import Path
import importlib.util, traceback
from polisyos.scientist.methods.backtesting import orchestrator
assert str(Path(orchestrator.__file__)).startswith('/workspace/e02-E-pr38-r2-receipts/backtest-old58-overlay/policy-engine/src/')
print('SOURCE_COMMIT=58e2d97965c0826c44843a78dcb2f8698d9950a3', flush=True)
print('ORCHESTRATOR_ORIGIN=' + orchestrator.__file__, flush=True)
native = orchestrator.run_experiment
def observe(*args, **kwargs):
    try:
        return native(*args, **kwargs)
    except Exception:
        traceback.print_exc()
        raise
orchestrator.run_experiment = observe
spec = importlib.util.spec_from_file_location('native_fixture', '/workspace/e02-E-backtest-20261006/policy-engine/tests/unit/scientist/methods/backtesting/test_native_replay.py')
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
store, plan = module._fixture(Path('/workspace/e02-E-pr38-r2-receipts/backtest-old58-complete-tests'), count=1)
report = orchestrator.BacktestOrchestrator(cas=store).run([plan])
print('effective_mode=' + report.prediction_mode_effective, flush=True)
print('degraded_reasons=' + repr(report.degraded_reasons), flush=True)
assert report.prediction_mode_effective == 'scientist', report.degraded_reasons
