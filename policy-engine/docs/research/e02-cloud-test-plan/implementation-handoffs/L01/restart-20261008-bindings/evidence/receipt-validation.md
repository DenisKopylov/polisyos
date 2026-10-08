# Receipt integrity recipe

Executed from the admitted L01 repository root with local system Python. This checks only Git/JSON receipt content and the exact original spans; it does not admit production inputs or run a consumer. Full stdout is in [receipt-validation-stdout.txt](receipt-validation-stdout.txt).

The executed local command was `python3 policy-engine/_build/e02-L01-restart-20261008/validate_final_facts.py`. Its complete one-off body is below; use the same body with `python3` after fetching the two cited commits and G. It does not read any confidential locator.

```python
import hashlib,json,pathlib,subprocess
candidate='621e9e7aec1af78da72b0c4b47a8cb8b79daa5fd'
base='5c3afde4833e8ee0314fe6e003070a29b649ad5b'
prefix='policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/L01/restart-20261008-bindings/'
def read(commit,path):
 return subprocess.check_output(['git','show',commit+':'+path])
source=json.loads(read(candidate,prefix+'source.json'))
for r in source['source_refs']:
 assert subprocess.check_output(['git','rev-parse',r['commit']+':'+r['path']],text=True).strip()==r['git_blob']
occurrences=0
for row in source['original_criteria']:
 for o in row['source_occurrences']:
  r=o['source_ref'];lines=read(r['commit'],r['path']).decode().splitlines(keepends=True);lo,hi=o['lines']
  assert hashlib.sha256(''.join(lines[lo-1:hi]).encode()).hexdigest()==o['sha256'];occurrences+=1
paths=subprocess.check_output(['git','diff','--name-only',base,candidate],text=True).splitlines()
assert paths and all(p.startswith(prefix) for p in paths)
for p in paths:
 raw=read(candidate,p);assert raw==pathlib.Path(p).read_bytes()
 if p.endswith('.json'):json.loads(raw)
print(json.dumps({'outcome':'PASS','scope':'factual receipt integrity; no runtime or input admission','candidate':candidate,'source_ref_denominator':{'pointer':prefix+'source.json#/source_refs','records':len(source['source_refs'])},'original_occurrence_denominator':{'pointer':prefix+'source.json#/original_criteria','occurrences':occurrences},'document_denominator':{'git_diff_base':base,'git_diff_candidate':candidate,'files':len(paths),'file_types':['md','json']},'byte_readback':True,'product_test_config_lock_generated_delta':[],'runtime_tests':'UNRUN'},indent=2))
```
