from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from polisyos.core.artifacts import PutOptions, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import CanonSpec
from polisyos.foundry.methods.catalog.causal.discovery_pipeline import UnifiedCausalDiscovery
from polisyos.foundry.methods.catalog.causal.protocols import LLMStructuralHint, UnifiedDiscoveryData
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.analytics.causal_discovery import DiscoveryPipelineReport
from polisyos.ir.analytics.literature import LiteratureCausalPrior
from polisyos.scientist.compute.job_spec import JobSpec
from polisyos.scientist.compute.runner import run_job

ROOT = Path('/tmp/e02-F-profile-consistency-20261007/report-review')

def main():
    rng = np.random.default_rng(710)
    x = rng.normal(size=160)
    y = 2*x + rng.normal(scale=0.1, size=160)
    data = np.column_stack([x,y])
    cases = {
        'no_request': {},
        'literature_prior': {'literature_prior': LiteratureCausalPrior()},
        'llm_hint': {'llm_hints': [LLMStructuralHint(src='X', dst='Y', confidence=0.8)]},
    }
    MethodRegistry.get_instance().register(UnifiedCausalDiscovery, override=True)
    findings = []
    for name, request in cases.items():
        state = UnifiedDiscoveryData(data=data, variable_names=['X','Y'], **request)
        store = FileSystemCAS(ROOT / 'baseline-cas' / name)
        input_ref = store.put_json(state.model_dump(mode='json'), PutOptions(kind='test.discovery.input', media_type='application/json', schema=SchemaInfo(name='test.UnifiedDiscoveryData', version='1.0')), canon_spec=CanonSpec(forbid_floats=False))
        job = run_job(JobSpec(job_kind='method', method_fqn=UnifiedCausalDiscovery.signature.fqn, input_refs={'discovery_data': input_ref}, method_params={'force_algorithms':['pc'],'n_bootstrap':0,'timeout_seconds':60,'enable_regime_shift_discovery':False,'ci_backend':'numpy'}, seed=710),cas_root=store.root,method_state=state)
        assert not job.issues, job.issues
        assert job.method_result_ref is not None
        fresh = FileSystemCAS(store.root)
        raw = fresh.get_bytes(job.method_result_ref.artifact_id)
        payload = json.loads(raw)
        report = DiscoveryPipelineReport.model_validate(payload['report'])
        assert report.n_algorithms_run == 1
        assert not any('algorithm_failed' in warning for item in report.individual_results for warning in item.warnings)
        findings.append({'case': name, 'report':report.model_dump(mode='json'),'job_warnings':job.warnings,'result_ref':job.method_result_ref.model_dump(mode='json'),'result_bytes':len(raw),'result_sha256':hashlib.sha256(raw).hexdigest()})
    (ROOT / 'baseline-consumer.json').write_text(json.dumps({'source_sha':'2c09571eb9e9efdb91c09b3b4871a49f4c013c1d','source_tree':'c9dcc58e520cb2c161c85a74e8a2161c32a7276f','cases':findings},indent=2)+'\n')
    print(json.dumps({'source_sha':'2c09571eb9e9efdb91c09b3b4871a49f4c013c1d','cases':[{'case':item['case'],'report_warnings':item['report']['warnings'],'reconciliation':item['report']['metadata'].get('reconciliation'),'graph_type':item['report']['unified_pag']['graph_type'],'edge_count':len(item['report']['unified_pag']['edges'])} for item in findings]},indent=2))

if __name__ == '__main__':
    main()
