"""Read-only Git-frozen native module selection, inherited by actual fresh readers."""
import hashlib, importlib.abc, importlib.util, json, linecache, os, pathlib, subprocess, sys
SHA=os.environ.get("E02_REVIEW_FROZEN_SHA")
REPO=pathlib.Path("/workspace/e02-F-closeout-20261006")
OWNER="polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation"
FILES={OWNER:"policy-engine/src/polisyos/scientist/nodes/builtins/simulate/run_causal_evaluation.py"}
TEST_FILES={"test_did_diagnostic_consumer":"policy-engine/tests/unit/scientist/nodes/builtins/simulate/test_did_diagnostic_consumer.py", "test_causal_input_byte_binding":"policy-engine/tests/unit/scientist/nodes/builtins/simulate/test_causal_input_byte_binding.py"}
class ExactLoader(importlib.abc.Loader):
    def __init__(self, name, path):
        self.name=name;self.path=path
        self.raw=subprocess.check_output(["git","-C",str(REPO),"show",SHA+":"+path])
    def create_module(self, spec): return None
    def get_source(self, name): return self.raw.decode("utf-8")
    def exec_module(self, module):
        location=SHA+":"+self.path
        linecache.cache[location]=(len(self.raw),None,self.raw.decode("utf-8").splitlines(True),location)
        module.__file__=str(REPO/self.path)
        module.__frozen_e02_source_sha__=SHA
        module.__frozen_e02_source_sha256__=hashlib.sha256(self.raw).hexdigest()
        exec(compile(self.raw,location,"exec"),module.__dict__)
        if self.name == OWNER:
            print(json.dumps({"independent_frozen_owner":SHA,"source_sha256":module.__frozen_e02_source_sha256__,"pid":os.getpid(),"origin":location}),flush=True)
class ExactFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        source=FILES.get(fullname) or TEST_FILES.get(fullname.rsplit(".",1)[-1])
        if source:
            return importlib.util.spec_from_loader(fullname,ExactLoader(fullname,source),origin=str(REPO/source))
if SHA:
    sys.meta_path.insert(0,ExactFinder())
