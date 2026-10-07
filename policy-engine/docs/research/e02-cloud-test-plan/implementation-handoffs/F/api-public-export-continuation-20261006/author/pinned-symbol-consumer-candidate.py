import ast,json,sys,subprocess,hashlib
from pathlib import Path
sys.path.insert(0,'/workspace/e02-F-api-20261006/policy-engine')
from tools.devx.architecture import guardrails
source_sha='737ecba79eb505ba3ec0af1fc7ef7e8308abcba7'
source_path='policy-engine/tools/devx/architecture/guardrails.py'
raw=subprocess.check_output(['git','show',source_sha+':'+source_path],cwd='/workspace/e02-F-api-20261006')
exec(compile(raw,guardrails.__file__,'exec'),guardrails.__dict__)
_extract_exports=guardrails._extract_exports
cases={
 'unknown_call_receives_mapping':"M={'x':1}\ndef mutate(value):value['y']=2\nmutate(M)\n__all__=sorted(M)\n",
 'mapping_alias_mutation':"M={'x':1}\nA=M\nA['y']=2\n__all__=sorted(M)\n",
 'unknown_call_receives_all':"__all__=['x']\ndef mutate(value):value.append('y')\nmutate(__all__)\n",
 'builtin_shadow':"sorted=lambda value:['wrong']\nM={'x':1}\n__all__=sorted(M)\n",
 'supported_literal':"M={'x':1}\n__all__=sorted(M)\n",
}
out={}
for name,code in cases.items():
 try: out[name]={'result':list(_extract_exports(ast.parse(code))),'state':'RESOLVED'}
 except ValueError as exc: out[name]={'state':'UNRESOLVED','reason':str(exc)}
 namespace={};exec(code,namespace);out[name]['actual_controlled_fixture_all']=namespace['__all__']
record={'source_sha':source_sha,'source_tree':'a0fce600f7235cd2826e5db0a8379960701ed4ae','source_path':source_path,'source_sha256':hashlib.sha256(raw).hexdigest(),'cases':out,'scope':'Finite wholly authored fixture execution only; pinned product static reader via exact Git source. No external input/module execution by reader.'}
Path('/tmp/e02-F-continuation-20261006/root-api-symbol-consumer-probe.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
