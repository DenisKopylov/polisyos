"""Exact Git-object AST reconciliation; edge and symbol denominators stay distinct."""
import ast
import hashlib
import json
import subprocess
import tomllib
from pathlib import Path

ROOT=Path('/workspace/e02-E-continuation-20261006')
OUT=Path(__file__).parent
BASE='198076863e143dea9f89f02734b13d50dae3eed5'
FROZEN='58e2d97965c0826c44843a78dcb2f8698d9950a3'
CURRENT='5d4e01011a0b7e0a3954decdb622a9e9cf1fb787'
BKT='0983d064df3c3e21f8b1accff4ee90484d78973b'
FRC='8486baad6fdef8063cfaad80b15f6b6d8532460a'
SLICE='028829629a9c30454e44d25e7bea7be3ea05b561'
PRE_FAMILY='31059ec77f9add8651667967a4b1a51acfab6d24'
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()
def source(ref,path):
    result=subprocess.run(['git','show',ref+':'+path],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    return result.stdout.decode() if result.returncode==0 else None
def parsed_imports(ref,path):
    text=source(ref,path)
    if text is None:return []
    module=path.removeprefix('policy-engine/src/').removesuffix('.py').replace('/','.')
    if module.endswith('.__init__'):module=module.removesuffix('.__init__')
    root=module.split('.')[1]
    results=[]
    def visit(node,type_checking=False):
        if isinstance(node,ast.If) and isinstance(node.test,(ast.Name,ast.Attribute)) and (getattr(node.test,'id',None)=='TYPE_CHECKING' or getattr(node.test,'attr',None)=='TYPE_CHECKING'):
            for child in node.body:visit(child,True)
            for child in node.orelse:visit(child,type_checking)
            return
        if isinstance(node,ast.ImportFrom) and node.level==0 and node.module and node.module.startswith('polisyos.'):
            target=node.module
            if target.split('.')[1]!=root:
                results.append({'source_module':module,'source_path':path,'target_module':target,'symbols':[a.name for a in node.names],'aliases':{a.name:a.asname for a in node.names if a.asname},'type_checking':type_checking,'line':node.lineno})
        if isinstance(node,ast.Import):
            for alias in node.names:
                if alias.name.startswith('polisyos.') and alias.name.split('.')[1]!=root:results.append({'source_module':module,'source_path':path,'target_module':alias.name,'symbols':['<module>'],'aliases':{alias.name:alias.asname} if alias.asname else {},'type_checking':type_checking,'line':node.lineno})
        for child in ast.iter_child_nodes(node):visit(child,type_checking)
    visit(ast.parse(text));return results
contract=tomllib.loads(source(FROZEN,'policy-engine/architecture/public_surface/contract.toml'))
allowed={e for package in contract['package'] for e in package['supported_entrypoints']}
def unadmitted(row):
    target=row['target_module']
    return target not in allowed and len(target.split('.'))>2
paths=git('diff','--name-only',BASE,FROZEN,'--','policy-engine/src').splitlines()
new=[]
for path in paths:
    if not path.endswith('.py'):continue
    old_targets={r['target_module'] for r in parsed_imports(BASE,path)}
    for row in parsed_imports(FROZEN,path):
        if row['target_module'] not in old_targets and unadmitted(row):new.append(row)
expected=[('calibration.continuous','core.artifacts'),('calibration.continuous','core.canon'),('calibration.forecast_bridge','ir.analytics.forecasting_uncertainty'),('foundry.methods.catalog.econometrics.advanced','core.artifacts'),('foundry.uncertainty.sampling_admission','ir.analytics.uncertainty'),('scientist.methods.autotune.sensitivity_bridge','core.artifacts'),('scientist.methods.backtesting.forecast_owner','calibration.forecast_bridge'),('scientist.methods.doe._receipt','core.artifacts'),('scientist.methods.doe._receipt','core.canon'),('scientist.methods.search.sensitivity_adapter','core.artifacts'),('scientist.nodes.builtins.simulate.propagate_uncertainty','foundry.uncertainty.sampling_admission'),('scientist.nodes.builtins.simulate.propagate_welfare','foundry.uncertainty.sampling_admission')]
keys={(r['source_module'],r['target_module']) for r in new}
expected_keys={('polisyos.'+s,'polisyos.'+t) for s,t in expected}
audit_rows=[]
for s,t in expected:
    source_module,target_module='polisyos.'+s,'polisyos.'+t
    path='policy-engine/src/'+source_module.replace('.','/')+'.py'
    old=[r for r in parsed_imports(FROZEN,path) if r['target_module']==target_module]
    current=parsed_imports(CURRENT,path)
    remaining=[r for r in current if r['target_module']==target_module]
    replacements=[r for r in current if r['target_module'] in ['polisyos.calibration','polisyos.foundry.uncertainty','polisyos.ir.analytics']]
    audit_rows.append({'source_module':source_module,'old_target_module':target_module,'source_path':path,'frozen_imports':old,'current_same_target':remaining,'current_facade_replacements':replacements,'edge_present_in_exact_ast_delta':(source_module,target_module) in keys})
forthcoming={}
for label,ref in [('BKT',BKT),('FRC',FRC)]:
    changed=git('diff','--name-only',SLICE,ref,'--','policy-engine/src').splitlines();rows=[]
    for path in changed:
        if not path.endswith('.py'):continue
        if label=='BKT' and '/backtesting/' not in path:continue
        if label=='FRC' and path not in ['policy-engine/src/polisyos/calibration/forecast_bridge.py','policy-engine/src/polisyos/scientist/methods/backtesting/forecast_owner.py']:continue
        old_targets={r['target_module'] for r in parsed_imports(PRE_FAMILY,path)}
        for row in parsed_imports(ref,path):
            row['new_vs_current_module_edge']=row['target_module'] not in old_targets
            row['admitted_by_frozen_contract']=row['target_module'] in allowed or len(row['target_module'].split('.'))==2
            rows.append(row)
    forthcoming[label]={'comparison_sha':PRE_FAMILY,'source_sha':ref,'source_tree':git('rev-parse',ref+'^{tree}'),'rows':rows}
out={'base_sha':BASE,'frozen_sha':FROZEN,'current_sha':CURRENT,'current_tree':git('rev-parse',CURRENT+'^{tree}'),'audit_sha':'0346fc656a45ff2cd43d37126992d8ddbb739d10','denominators':{'changed_src_paths':len(paths),'new_unadmitted_cross_root_module_edges':len(keys),'audit_expected_edges':len(expected_keys),'E_changed_path_report_rows':35,'all_report_rows':163},'ast_equals_exact_audit_edges':keys==expected_keys,'extra_ast_edges':sorted(keys-expected_keys),'missing_ast_edges':sorted(expected_keys-keys),'all_new_ast_rows':new,'original12_reconciliation':audit_rows,'forthcoming_family_imports':forthcoming,'P41':'not_established; no global command replay or input denominator measured by this AST-only packet'}
OUT.mkdir(parents=True,exist_ok=True);(OUT/'edge-reconciliation.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:out[k] for k in ['denominators','ast_equals_exact_audit_edges','extra_ast_edges','missing_ast_edges']},indent=2))
