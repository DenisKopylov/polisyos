"""Native provider and frozen-source provenance for bounded root consumer review."""
import ast,hashlib,importlib,json,pathlib,platform,subprocess,sys
from polisyos.scientist.nodes.builtins.simulate import run_causal_evaluation as owner
repo=pathlib.Path("/workspace/e02-F-closeout-20261006");sha=owner.__frozen_e02_source_sha__
mods=["numpy","scipy","statsmodels","pytest","pydantic","polisyos.core.artifacts.store","polisyos.core.artifacts.models","polisyos.foundry.methods.catalog.causal.did","polisyos.foundry.methods.registry","polisyos.foundry.methods.components.io","polisyos.scientist.compute.runner","polisyos.scientist.nodes.conftest"]
# Fixture module is a test provider under the repository tests namespace.
mods[-1]="tests.unit.scientist.nodes.conftest"
records=[]
for name in mods:
    m=importlib.import_module(name);file=pathlib.Path(m.__file__);record={"module":name,"file":str(file),"version":getattr(m,"__version__",None)}
    if file.is_relative_to(repo) and ".venv" not in file.parts:
        rel=str(file.relative_to(repo));actual=file.read_bytes();expected=subprocess.check_output(["git","-C",str(repo),"show",sha+":"+rel]);record.update({"path":rel,"actual_sha256":hashlib.sha256(actual).hexdigest(),"frozen_git_sha256":hashlib.sha256(expected).hexdigest(),"matches_frozen_git":actual==expected});assert actual==expected
    records.append(record)
path="policy-engine/src/polisyos/scientist/nodes/builtins/simulate/run_causal_evaluation.py";raw=subprocess.check_output(["git","-C",str(repo),"show",sha+":"+path]);tree=ast.parse(raw)
bare=[]
for node in ast.walk(tree):
    if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr in {"get_bytes","get_manifest","verify"} and isinstance(node.func.value,ast.Attribute) and node.func.value.attr=="store" and any(isinstance(arg,ast.Attribute) and arg.attr=="artifact_id" for arg in node.args):bare.append(node.lineno)
assert not bare
print(json.dumps({"source_sha":sha,"source_tree":subprocess.check_output(["git","-C",str(repo),"rev-parse",sha+"^{tree}"],text=True).strip(),"owner_sha256":hashlib.sha256(raw).hexdigest(),"python":platform.python_version(),"executable":sys.executable,"providers":records,"canonical_owner_bare_artifact_id_store_reads":bare,"working_tree_status_observed":subprocess.check_output(["git","-C",str(repo),"status","--short"],text=True),"profile":"Core CAS actual byte/selected-manifest identity; independent from PDC semantic identity and evaluation authority"},indent=2),flush=True)
