"""Run new native consumers against immutable previous production modules."""
import hashlib,importlib.abc,importlib.util,json,pathlib,subprocess,sys
ROOT=pathlib.Path('/workspace/e02-B-current-execution-state')
SHA='89e2faad985250b02853a94718a126bdabc07641'
MODULES={name:'policy-engine/src/'+name.replace('.','/')+'.py' for name in ['polisyos.scientist.orchestration.engine.checkpoint','polisyos.scientist.orchestration.engine.async_executor','polisyos.scientist.orchestration.engine.executor']}
SOURCES={name:subprocess.check_output(['git','show',SHA+':'+path],cwd=ROOT) for name,path in MODULES.items()}
class Loader(importlib.abc.Loader):
    def create_module(self,spec):return None
    def exec_module(self,module):
        filename=SHA+':'+MODULES[module.__name__]
        module.__file__=filename
        exec(compile(SOURCES[module.__name__],filename,'exec'),module.__dict__)
class Finder(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname in SOURCES:return importlib.util.spec_from_loader(fullname,Loader(),origin=SHA+':'+MODULES[fullname])
sys.meta_path.insert(0,Finder())
print(json.dumps({'production_source_sha':SHA,'loader_source_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),'module_overrides':[{'module':n,'source_path':MODULES[n],'sha256':hashlib.sha256(v).hexdigest()} for n,v in SOURCES.items()],'qualification':'All other tracked production modules equal source89; new exact test file is supplied as overlay; no whole candidate checkout claim'}),flush=True)
import pytest
raise SystemExit(pytest.main(sys.argv[1:]))
