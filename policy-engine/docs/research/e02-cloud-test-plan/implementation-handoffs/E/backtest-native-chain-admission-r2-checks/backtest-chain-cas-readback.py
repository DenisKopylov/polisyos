from pathlib import Path
import importlib.util, json
from polisyos.core.artifacts import ArtifactRef, FileSystemCAS
from polisyos.scientist.methods.backtesting.native_replay import load_native_forecast
spec = importlib.util.spec_from_file_location('native_fixture', '/workspace/e02-E-backtest-20261006/policy-engine/tests/unit/scientist/methods/backtesting/test_native_replay.py')
fixture = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixture)
evidence = json.loads(Path('/workspace/e02-E-pr38-r2-receipts/backtest-native-deciding-evidence.json').read_text())
records = []
for report in evidence['generic_native_reports']:
    store = FileSystemCAS(Path(report['cas_root']))
    for item in report['scenario_evidence']:
        forecast, request = load_native_forecast(store, ArtifactRef.model_validate(item['metadata']['native_forecast_ref']), ArtifactRef.model_validate(item['metadata']['native_request_ref']))
        assert forecast.values == {'income': [1.5, 1.0]}
        fixture._assert_real_cas_chain_controls(store, forecast, request)
    records.append({'report_artifact_id': report['report_artifact_id'], 'K': len(report['scenario_evidence']), 'genuine_readback': 'PASS', 'five_hash_valid_chain_model_fakes': 'REFUSED for every scenario'})
print(json.dumps({'candidate_sha': '0983d064df3c3e21f8b1accff4ee90484d78973b', 'original_native_execution_sha': '0e457bf0b2cef01fb423ba925048d6d9f7ce1095', 'new_reader_scope': records}, indent=2), flush=True)
