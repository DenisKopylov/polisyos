from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from polisyos.foundry.methods.catalog.causal.discovery_pipeline import UnifiedCausalDiscovery
from polisyos.foundry.methods.catalog.causal.protocols import LLMStructuralHint, UnifiedDiscoveryData
from polisyos.ir.analytics.literature import LiteratureCausalPrior

ROOT = Path('/tmp/e02-F-profile-consistency-20261007/report-review')

def main():
    rng = np.random.default_rng(710)
    x = rng.normal(size=160)
    data = np.column_stack([x,2*x+rng.normal(scale=0.1,size=160)])
    records=[]
    for name,request in [('no_request',{}),('literature_prior',{'literature_prior':LiteratureCausalPrior()}),('llm_hint',{'llm_hints':[LLMStructuralHint(src='X',dst='Y',confidence=0.8)]})]:
        state=UnifiedDiscoveryData(data=data,variable_names=['X','Y'],**request)
        result=UnifiedCausalDiscovery.pure_step(state,{'force_algorithms':['pc'],'n_bootstrap':0,'timeout_seconds':60,'enable_regime_shift_discovery':False,'ci_backend':'numpy'})
        report=result['report']
        assert report.n_algorithms_run==1
        assert not any('algorithm_failed' in w for r in report.individual_results for w in r.warnings)
        records.append({'case':name,'output_keys':list(result),'report':report.model_dump(mode='json')})
    (ROOT/'baseline-pure-report.json').write_text(json.dumps({'source_sha':'2c09571eb9e9efdb91c09b3b4871a49f4c013c1d','cases':records},indent=2)+'\n')
    print(json.dumps({'source_sha':'2c09571eb9e9efdb91c09b3b4871a49f4c013c1d','cases':[{'case':r['case'],'warnings':r['report']['warnings'],'metadata':r['report']['metadata'],'output_keys':r['output_keys'],'graph':r['report']['unified_pag']} for r in records]},indent=2))

if __name__=='__main__':
    main()
