from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.causal_discovery import DiscoveryPipelineReport
from polisyos.ir.analytics.causal_graph import GraphType
from polisyos.ir.artifacts import get_json_artifact

ROOT = Path('/dev/shm/e02-F-profile-consistency-report')
SOURCE = Path('/dev/shm/e02-F-report-export-852/policy-engine/src').resolve()

def main():
    source = json.loads((ROOT/'final-report-consumer.json').read_text())
    assert os.getpid() != source['producer_pid']
    cases=[]
    baseline_graph=None
    for item in source['cases']:
        store=FileSystemCAS(Path(item['cas_root']))
        artifact_id=item['result_ref']['artifact_id']
        raw=store.get_bytes(artifact_id)
        assert hashlib.sha256(raw).hexdigest()==item['result_sha256']==artifact_id.split(':',1)[1]
        payload=get_json_artifact(store,artifact_id)
        assert payload['report']==payload['discovery_pipeline_report']
        report=DiscoveryPipelineReport.model_validate(payload['discovery_pipeline_report'])
        assert report.unified_pag.graph_type is GraphType.PAG
        assert report.unified_pag.edges
        if item['case']=='no_request':
            baseline_graph=report.unified_pag
            assert 'reconciliation' not in report.metadata
            assert not any(w.startswith('reconciliation_') for w in report.warnings)
        else:
            limitation=report.metadata['reconciliation']
            assert limitation['requested'] is True and limitation['applied'] is False
            assert limitation['reason']=='unsupported_profile'
            assert 'reconciliation_not_applied:unsupported_profile' in report.warnings
            assert report.unified_pag==baseline_graph
        cases.append({'case':item['case'],'artifact_id':artifact_id,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'warnings':report.warnings,'reconciliation':report.metadata.get('reconciliation')})
    origins={}
    for name,module in list(sys.modules.items()):
        path=getattr(module,'__file__',None)
        if name.startswith('polisyos.') and path and path.endswith('.py'):
            resolved=Path(path).resolve()
            assert resolved.is_relative_to(SOURCE),(name,resolved)
            origins[name]=str(resolved)
    record={'source_sha':source['source_sha'],'source_tree':source['source_tree'],'producer_pid':source['producer_pid'],'reader_pid':os.getpid(),'distinct_process':True,'python':sys.version,'interpreter':sys.executable,'cases':cases,'polisyos_module_count':len(origins),'origin_errors':0,'reader_module_origin':origins['polisyos.ir.analytics.causal_discovery'],'loaded_via_actual_CAS_api':True,'authority_scope':'report limitation/readback only; no causal/identification authority'}
    (ROOT/'fresh-report-reader.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record,indent=2))

if __name__=='__main__':
    main()
