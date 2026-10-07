"""Run exact frozen carriers from a neutral installed -I profile; retain literal observations."""
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
sys.dont_write_bytecode = True
import pytest
config = json.loads(Path(sys.argv[1]).read_text())
kind = sys.argv[2]
scratch = Path(config['scratch'])
site = Path(config['sites'][kind]).resolve()
carrier = scratch / (kind+'-consumer')
assert sys.flags.isolated == 1 and Path.cwd() == carrier
assert not (carrier/'src').exists()
assert not any(Path(entry).is_relative_to(Path(config['source_root'])) for entry in sys.path if entry)
manifest = json.loads(Path(config['carrier_manifest']).read_text())
for ref in manifest['files']:
    path = carrier / ref['path'].removeprefix('policy-engine/')
    raw = path.read_bytes()
    assert len(raw) == ref['bytes'] and hashlib.sha256(raw).hexdigest() == ref['sha256'], path
os.environ['POLISYOS_DOWHY_WORKER_PYTHON'] = config['worker_python']
os.environ['E02_PROFILE_EXPECTED_JSON'] = str(scratch/'profile-expected.json')
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
os.environ.pop('PYTHONPATH', None)
reader = scratch/'installed_tmle_reader.py'
reader_proofs = scratch/(kind+'-reader-origin-proofs')
reader_proofs.mkdir(exist_ok=False)
tmle = carrier/'tests/unit/scientist/governance/test_tmle_persisted_evidence_consumers.py'
actual_subprocess_run = subprocess.run
adapted = []
def installed_run(argv, *args, **kwargs):
    if isinstance(argv, (list,tuple)) and len(argv)==4 and argv[:3] == [sys.executable,str(tmle),'--reader']:
        selected = [sys.executable,'-I',str(reader),str(tmle),str(argv[3]),str(reader_proofs),str(site),config['source_sha']]
        adapted.append({'original_argv': list(argv), 'actual_argv': selected})
        return actual_subprocess_run(selected,*args,**kwargs)
    return actual_subprocess_run(argv,*args,**kwargs)
subprocess.run = installed_run
class Collection:
    def pytest_collection_finish(self,session):
        self.ids = [item.nodeid for item in session.items]
        assert len(self.ids)==config['expected_cases_per_profile'],len(self.ids)
collection = Collection()
argv = ['-q','-s','-ra','-o','addopts=','--import-mode=importlib','-p','no:cacheprovider',
        '--basetemp='+str(scratch/(kind+'-pytest-tmp')),
        '--junitxml='+str(scratch/(kind+'-junit.xml')),
        *[str(carrier/path) for path in config['selectors']]]
status = pytest.main(argv,plugins=[collection])
subprocess.run = actual_subprocess_run
origins = {name:str(Path(module.__file__).resolve()) for name,module in sys.modules.copy().items()
           if name.startswith(('polisyos','tools')) and getattr(module,'__file__',None)}
violations = {name:path for name,path in origins.items() if not Path(path).is_relative_to(site)}
proof = {'source_sha':config['source_sha'],'source_tree':config['source_tree'],'python':platform.python_version(),
    'executable':sys.executable,'isolated':sys.flags.isolated,'cwd':str(Path.cwd()),'sys_path':sys.path,
    'pytest_argv':argv,'pytest_exit':int(status),'collected_ids':getattr(collection,'ids',[]),
    'product_origins':origins,'origin_violations':violations,'adapted_tmle_readers':adapted,
    'reader_adapter_scope':'Only unchanged frozen --reader runpy entry receives -I and complete product origin observer. No producer/consumer/authority replacement.',
    'authority':'Known synthetic candidates; no operational/statistical/value positive admission or admitted B56 study budget witness.'}
(scratch/(kind+'-installed-proof.json')).write_text(json.dumps(proof,indent=2)+'\n')
assert not violations,violations
assert len(adapted)==53,len(adapted)
print(json.dumps({'source_sha':config['source_sha'],'kind':kind,'pytest_exit':int(status),
    'cases':len(getattr(collection,'ids',[])),'owned_origins':len(origins),'TMLE_fresh_isolated_readers':len(adapted),'origin_violations':len(violations)}))
raise SystemExit(status)
