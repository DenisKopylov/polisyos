"""Read-only exact-source peer audit of the native DoWhy CI companion."""

import ast
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path('/workspace/e02-F-closeout-20261006')
SCRATCH = Path('/tmp/e02-F-continuation-20261006/foundry/dowhy-companion-review')
BASE = '4a038c2ebf0c4fd79dcc084c983ed7b76756a488'
COMMITS = ['47a2ff90186628afafa4c01ecf7158325b0026fc', '46932cd30935b08e1da795f505a9b443c9dc668a', '386b361865fb22d6da241716481d919b6ebd8249']
PATH = 'policy-engine/tests/unit/foundry/methods/catalog/causal/test_dowhy_worker.py'


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def ref(path):
    data = path.read_bytes()
    return {'path':str(path),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}


def reader_and_outer(source):
    module = ast.parse(source)
    reader = None
    for function in module.body:
        if isinstance(function, ast.FunctionDef) and function.name == 'test_real_worker_job_cas_fresh_python314_reader':
            for node in function.body:
                if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'reader' for t in node.targets):
                    assert isinstance(node.value, ast.Constant)
                    reader = ast.parse(node.value.value)
                    node.value.value = '<independently reviewed embedded fresh-reader delta>'
    assert reader is not None
    return reader, ast.dump(module, include_attributes=False)


def main():
    SCRATCH.mkdir(exist_ok=True)
    previous = BASE
    snapshots = []
    for sha in [BASE,*COMMITS]:
        data = git('show', sha+':'+PATH)
        snapshots.append({'git_sha':sha,'tree':git('rev-parse',sha+'^{tree}').decode().strip(),'path':PATH,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
        if sha != BASE:
            assert git('rev-parse',sha+'^').decode().strip() == previous
            assert git('diff','--name-only',previous,sha).decode().splitlines() == [PATH]
            previous = sha
    assert git('diff','--name-only',BASE,COMMITS[-1]).decode().splitlines() == [PATH]
    assert git('diff','--numstat',BASE,COMMITS[-1]).decode().strip() == '5\t1\t'+PATH
    before, outer_before = reader_and_outer(git('show',BASE+':'+PATH).decode())
    after, outer_after = reader_and_outer(git('show',COMMITS[-1]+':'+PATH).decode())
    assert outer_before == outer_after
    assert len(after.body) == len(before.body)+4
    gate_index = next(index for index,node in enumerate(before.body) if isinstance(node,ast.Assert)
                      and isinstance(node.test,ast.Attribute) and node.test.attr == 'gate_eligible')
    reviewed_before = before.body[gate_index]
    reviewed_after = after.body[gate_index:gate_index+5]
    del before.body[gate_index]
    del after.body[gate_index:gate_index+5]
    assert ast.dump(before,include_attributes=False) == ast.dump(after,include_attributes=False)
    assert isinstance(reviewed_before,ast.Assert)
    assert isinstance(reviewed_after[0],ast.Assign) and len([x for x in reviewed_after if isinstance(x,ast.Assert)]) == 4
    observations=[]
    names=['root-composed-boundaries','root-composed-worker-candidate','root-composed-worker-corrected','root-composed-worker-policy']
    expected=[(BASE,1,'1 failed, 91 passed'),(COMMITS[0],1,'1 failed'),(COMMITS[1],1,'1 failed'),(COMMITS[2],0,'1 passed')]
    reasons=['old positive identification gate assertion','nonexistent UncertaintyEnvelope.ci attribute','raw equality against declared12-decimal canonicalization','corrected canonical interval and non-gating candidate assertions']
    external=[]
    for name,(sha,exit_code,count),reason in zip(names,expected,reasons,strict=True):
        directory=Path('/tmp/e02-F-continuation-20261006')/name
        receipt=directory/'receipt.json'
        observation=json.loads(receipt.read_text())
        assert observation['source_sha']==sha and observation['ending_head']==sha
        assert observation['source_tree']==git('rev-parse',sha+'^{tree}').decode().strip()
        assert observation['exit_code']==exit_code
        out,err=directory/'stdout',directory/'stderr'
        assert count in out.read_text()
        assert 'warnings summary' not in out.read_text()
        for label,path in [('stdout',out),('stderr',err)]:
            actual=ref(path)
            assert actual['sha256']==observation['outputs'][label]['sha256'] and actual['bytes']==observation['outputs'][label]['bytes']
        observations.append({'name':name,'target_sha':sha,'target_tree':observation['source_tree'],
                             'command':' '.join(observation['command']),'environment':observation['environment_overrides'],
                             'input_closure':'Exact authored real selected worker/MethodJob/CAS/fresh Python3.14 report reader path; oldwave also includes all7 declared native consumer selections.',
                             'outcome':'PASS' if exit_code==0 else 'FAIL','exit_code':exit_code,
                             'wall_seconds':observation['wall_seconds'],'output':str(out),'output_refs':[ref(out),ref(err)],
                             'interpretation':reason,'role':'Existing author actual run independently read and reconciled; no reviewer worker rerun'})
        external.extend([ref(receipt),ref(out),ref(err)])
    result={'source_sha':COMMITS[-1],'source_tree':snapshots[-1]['tree'],'slice_base_sha':BASE,'implementation_commits':COMMITS,
            'changed_paths':[PATH],'source_refs':snapshots,'exact_footprint':'one test,5 insertions1 deletion across3 append-only commits',
            'unchanged_pipeline_and_other_test_ast':True,'unchanged_inner_reader_ast_outside_reviewed_candidate_projection_assertions':True,
            'product_provider_worker_lock_catalog_schema_changes':[],'observations':observations,'external_full_refs':external,
            'reviewer_worker_reexecution':False,'outcome':'PASS'}
    (SCRATCH/'source-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    main()
