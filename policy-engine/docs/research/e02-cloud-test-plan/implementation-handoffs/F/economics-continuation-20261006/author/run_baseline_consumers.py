from pathlib import Path
import hashlib,json,sys,subprocess
import pytest
root=Path('/tmp/e02-F-continuation-20261006/economics/base-source-archive/policy-engine')
source='fb51511fef60c5123875e99ab2f19a9a0bd5d16f'
class Provenance:
    def pytest_sessionfinish(self,session,exitstatus):
        rows=[]
        for name,module in sorted(sys.modules.items()):
            path=getattr(module,'__file__',None)
            if not name.startswith('polisyos.') or not path:continue
            p=Path(path).resolve()
            if p.suffix!='.py':continue
            assert p.is_relative_to(root/'src'),str(p)
            data=p.read_bytes();rel='policy-engine/'+str(p.relative_to(root))
            blob=subprocess.check_output(['git','-C','/workspace/e02-F-economics-20261006','show',source+':'+rel])
            assert blob==data,rel
            rows.append(dict(module=name,path=rel,bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),source_sha=source))
        result=dict(source_sha=source,exit_code=int(exitstatus),imported_modules=rows,count=len(rows),all_source_bytes_match_git=True)
        Path('/tmp/e02-F-continuation-20261006/economics/base-consumer-import-provenance.json').write_text(json.dumps(result,indent=2)+'\n')
        print('BASE_IMPORTED_SOURCE_IDENTITY',json.dumps(dict(count=len(rows),all_source_bytes_match_git=True,source_sha=source)),flush=True)
args=['tests/unit/foundry/mechanisms/test_fiscal.py','tests/unit/foundry/mechanisms/test_labor.py','tests/unit/foundry/mechanisms/test_gradients.py','tests/unit/foundry/methods/catalog/mechanism/test_runtime.py','tests/unit/foundry/agent_sim/test_agent_simulation_step4.py','tests/unit/foundry/agent_sim/test_agent_simulation_step5.py','tests/unit/foundry/agent_sim/test_agent_simulation_step6.py','tests/unit/foundry/agent_sim/test_monitoring.py','tests/unit/foundry/methods/catalog/simulation','-q','-ra','--tb=short','--junitxml=/tmp/e02-F-continuation-20261006/economics/economics-exact-base-consumer.xml']
raise SystemExit(pytest.main(args,plugins=[Provenance()]))
