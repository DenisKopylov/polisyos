from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
from pathlib import Path

import numpy as np

from polisyos.core.artifacts import PutOptions, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import CanonSpec
from polisyos.foundry.methods.catalog.causal.discovery_pipeline import UnifiedCausalDiscovery
from polisyos.foundry.methods.catalog.causal.protocols import LLMStructuralHint, UnifiedDiscoveryData
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.analytics.causal_discovery import DiscoveryPipelineReport
from polisyos.ir.analytics.causal_graph import GraphType
from polisyos.ir.analytics.literature import LiteratureCausalPrior
from polisyos.scientist.compute.job_spec import JobSpec
from polisyos.scientist.compute.runner import run_job

ROOT = Path('/tmp/e02-F-profile-consistency-20261007/report-review')
SOURCE = Path(sys.argv[1]).resolve()

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
    baseline_graph = None
    for name, request in cases.items():
        state = UnifiedDiscoveryData(data=data, variable_names=['X','Y'], **request)
        store = FileSystemCAS(ROOT / 'final-cas' / name)
        input_ref = store.put_json(state.model_dump(mode='json'), PutOptions(kind='test.discovery.input', media_type='application/json', schema=SchemaInfo(name='test.UnifiedDiscoveryData', version='1.0')), canon_spec=CanonSpec(forbid_floats=False))
        job = run_job(JobSpec(job_kind='method', method_fqn=UnifiedCausalDiscovery.signature.fqn, input_refs={'discovery_data': input_ref}, method_params={'force_algorithms':['pc'],'n_bootstrap':0,'timeout_seconds':60,'enable_regime_shift_discovery':False,'ci_backend':'numpy'}, seed=710),cas_root=store.root,method_state=state)
        assert not job.issues, job.issues
        assert job.method_result_ref is not None
        assert job.final_state['report'] is job.final_state['discovery_pipeline_report']
        fresh = FileSystemCAS(store.root)
        raw = fresh.get_bytes(job.method_result_ref.artifact_id)
        payload = json.loads(raw)
        assert payload['report'] == payload['discovery_pipeline_report']
        report = DiscoveryPipelineReport.model_validate(payload['discovery_pipeline_report'])
        assert report.n_algorithms_run == 1
        assert report.unified_pag.graph_type is GraphType.PAG
        assert report.unified_pag.edges
        assert not any('algorithm_failed' in warning for item in report.individual_results for warning in item.warnings)
        if name == 'no_request':
            assert 'reconciliation' not in report.metadata
            assert not any(w.startswith('reconciliation_') for w in report.warnings)
            baseline_graph = report.unified_pag
        else:
            limitation = report.metadata['reconciliation']
            assert limitation['requested'] is True
            assert limitation['applied'] is False
            assert limitation['status'] == 'not_applied'
            assert limitation['reason'] == 'unsupported_profile'
            assert limitation['input_graph_type'] == limitation['output_graph_type'] == 'pag'
            assert 'Unsupported graph reconciliation profile' in limitation['detail']
            assert 'reconciliation_not_applied:unsupported_profile' in report.warnings
            assert report.unified_pag == baseline_graph
        evidence = json.loads(fresh.get_bytes(job.method_evidence_ref.artifact_id))
        assert evidence['authority_purpose'] == 'method_execution'
        assert 'governance_admissibility' in evidence['may_not_use_for']
        output_name = f'final-cas-{name}.json'
        (ROOT / output_name).write_bytes(raw)
        findings.append({'case': name, 'cas_root':str(store.root),'warnings':report.warnings,'reconciliation':report.metadata.get('reconciliation'),'actual_ci_backend':report.individual_results[0].metadata.get('ci_backend_runtime'),'result_ref':job.method_result_ref.model_dump(mode='json'),'output':output_name,'result_bytes':len(raw),'result_sha256':hashlib.sha256(raw).hexdigest()})
    origins = {}
    for name,module in list(sys.modules.items()):
        path = getattr(module,'__file__',None)
        if name.startswith('polisyos.') and path and path.endswith('.py'):
            resolved = Path(path).resolve()
            assert resolved.is_relative_to(SOURCE), (name, resolved)
            origins[name] = str(resolved)
    record = {'source_sha':'852cc3707bfc7dee132ec07a9ed5adcb5911fdf2','source_tree':'52fb13e9e12d80e4b1af5580f61d15310535e5e8','producer_pid':os.getpid(),'interpreter':sys.executable,'python':sys.version,'platform':platform.platform(),'source_root':str(SOURCE),'cases':findings,'polisyos_module_count':len(origins),'origin_errors':0,'selected_module_origins':{n:origins[n] for n in ['polisyos.foundry.methods.catalog.causal.discovery_pipeline','polisyos.foundry.methods.catalog.causal.graph_reconciliation','polisyos.foundry.methods.catalog.causal.constraint_discovery','polisyos.scientist.compute.runner','polisyos.ir.analytics.causal_discovery']},'authority_claim':'report execution/limitation only; no identification or institutional authority'}
    (ROOT / 'final-report-consumer.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record,indent=2))

if __name__ == '__main__':
    main()
