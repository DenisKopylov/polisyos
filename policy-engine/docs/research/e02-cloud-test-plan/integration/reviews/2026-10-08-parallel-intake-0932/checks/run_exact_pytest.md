# Exact verification harness transcript

This is the recorded Python reproduction recipe, not a new product module. Save the fenced body to an isolated scratch script before using the receipt argv; input source/tree and qualifications are in verdict.json.

```python
import sys,json,hashlib,subprocess,os
from pathlib import Path
root=Path(sys.argv[1]); checkout=Path(sys.argv[2]);sha=sys.argv[3];out=Path(sys.argv[4]);sys.path.insert(0,str(checkout/'policy-engine/src'))
import pytest
args=['-q','-o','addopts=','-p','no:cacheprovider','tests/unit/scientist/methods/backtesting/test_evaluator_interval_admission.py','tests/unit/scientist/methods/backtesting/test_backtesting.py','tests/unit/remediation/test_bkt_02.py','tests/unit/remediation/test_bkt_03.py','--basetemp='+str(out/'C09-pytest-temp'),'--junitxml='+str(out/'C09-affected.junit.xml')]
result=pytest.main(args)
origins=[];bad=[]
for name,module in sorted(sys.modules.items()):
 if name!='polisyos' and not name.startswith('polisyos.'):continue
 file=getattr(module,'__file__',None)
 if not file:continue
 p=Path(file).resolve()
 try:relative=p.relative_to(checkout).as_posix()
 except ValueError:bad.append({'module':name,'file':str(p),'reason':'outside_exact_source'});continue
 actual=subprocess.check_output(['git','hash-object',str(p)],cwd=root,text=True).strip();expected=subprocess.run(['git','rev-parse',sha+':'+relative],cwd=root,capture_output=True,text=True)
 origins.append({'module':name,'path':relative,'actual_blob':actual,'candidate_blob':expected.stdout.strip()})
 if expected.returncode!=0 or actual!=expected.stdout.strip():bad.append(origins[-1])
(out/'C09-loaded-origins.json').write_text(json.dumps({'source':sha,'origins':origins,'mismatches':bad},indent=2)+'\n')
print(json.dumps({'pytest_returncode':int(result),'source_sha':sha,'loaded_file_backed_polisyos_module_denominator':len(origins),'source_mismatch_count':len(bad)}))
raise SystemExit(int(result) if not bad else 9)
```
