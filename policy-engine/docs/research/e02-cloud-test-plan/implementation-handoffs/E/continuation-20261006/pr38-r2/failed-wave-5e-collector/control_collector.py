"""Synthetic custody-protocol controls only; no product/numerical/gate execution."""
from __future__ import annotations
import copy, hashlib, json, runpy
from argparse import Namespace
from pathlib import Path

ROOT=Path('/workspace/e02-E-continuation-20261006')
OUT=Path('/workspace/e02-E-pr38-r2-receipts/common-wave-publication-prep')
CANDIDATE='d43f8d4693767637424da759ae960f7b51736449'
HARNESS=ROOT/'policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/E/continuation-20261006/pr38-r2/wave-controls'
COLLECTOR=runpy.run_path(str(OUT/'collect_wave.py'),run_name='collector_protocol_controls_only')
PLANNER=runpy.run_path(str(HARNESS/'plan_wave.py'),run_name='metadata_factory_only')
CONTROLS=OUT/'synthetic-controls';CONTROLS.mkdir()
GIT=COLLECTOR['git_bytes']
track_count=len(GIT(ROOT,'ls-tree','-r','--name-only',CANDIDATE).decode().splitlines())
inputs={}
for name in ('AGENTS.md','policy-engine/CONTRIBUTING.md','policy-engine/pyproject.toml','policy-engine/uv.lock'):
    data=GIT(ROOT,'show',CANDIDATE+':'+name)
    inputs[name]={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'git_blob':GIT(ROOT,'rev-parse',CANDIDATE+':'+name).decode().strip()}
frame={'tracked_paths':track_count,'bytes':0,'framed_sha256':'SYNTHETIC_HELPER_CONTROL_NOT_SOURCE_BYTES'}
private=b'collector-control-private-sentinel-not-real-config\0'
private_hash=hashlib.sha256(private).hexdigest()

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n')

def fixture(name,mutation=None):
    wave=CONTROLS/name/'wave';pub=CONTROLS/name/'publication';wave.mkdir(parents=True)
    args=Namespace(repo=ROOT,candidate=CANDIDATE,comparison_base='198076863e143dea9f89f02734b13d50dae3eed5',output_root=wave,no_owner_packets=False)
    plan=PLANNER['prepare'](args);plan['collector_control_only']=True
    write(wave/'plan.json',plan);write(wave/'wave-started.json',{'candidate_sha':CANDIDATE,'started_unix':1,'collector_control_only':True})
    for packet in plan['owner_packet_extra_inputs']:
        path=Path(packet['destination']);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(GIT(ROOT,'show',CANDIDATE+':'+packet['source']))
    codes=[];gate_codes=[]
    for job in plan['jobs']:
        output=Path(job['output']);output.mkdir(parents=True)
        stdout=output/(job['name']+'.stdout.txt');stdout.write_text('SYNTHETIC COLLECTOR CONTROL ONLY; no product check was executed.\n')
        priv=wave/'raw'/(job['name']+'.git-config-private.nul');priv.parent.mkdir(parents=True,exist_ok=True);priv.write_bytes(private)
        cases=[];counts=None;exit_code=0;outcome='PASS'
        if job['kind']=='numerical':
            cases=[{'name':'test_collector_native_fixture','classname':job['name'],'outcome':'passed'}]
            if job['group']=='BKT_FRC_S10_and_adjacent_report_consumers':
                for packet in plan['owner_packet_extra_inputs']:
                    names=[node.name for node in COLLECTOR['ast'].walk(COLLECTOR['ast'].parse(GIT(ROOT,'show',CANDIDATE+':'+packet['source']))) if isinstance(node,(COLLECTOR['ast'].FunctionDef,COLLECTOR['ast'].AsyncFunctionDef)) and node.name.startswith('test_')]
                    for i,testname in enumerate(names):
                        status='failed' if 'status_reason' in Path(packet['destination']).stem and i==0 else 'passed'
                        cases.append({'name':testname,'classname':Path(packet['destination']).stem,'outcome':status})
            xml=Path(job['junit']);xml.parent.mkdir(parents=True,exist_ok=True)
            xml.write_text('<testsuites><testsuite>'+''.join('<testcase name="'+case['name']+'" classname="'+case['classname']+'">'+('<failure>synthetic helper control</failure>' if case['outcome']=='failed' else '')+'</testcase>' for case in cases)+'</testsuite></testsuites>')
            counts=COLLECTOR['summarize_cases'](cases)
            if counts['failed']:exit_code=1;outcome='FAIL'
            codes.append(exit_code)
        elif job['kind']=='gate':gate_codes.append(0)
        receipt={'schema':'policyos.e02.frozen_check.v2','candidate_sha':CANDIDATE,'candidate_tree_sha':plan['candidate_tree_sha'],'head_at_end':CANDIDATE,'command':job['argv'],'cwd':job['cwd'],'exit_code':exit_code,'outcome':outcome,'wall_seconds':0,'max_rss_kib':0,'user_cpu_seconds':0,'system_cpu_seconds':0,'rss_scope':'synthetic control, not resource measurement','source_identity_before':frame,'source_identity_after':frame,'source_immutable':True,'input_files':inputs,'started_unix':2,'environment':{'selected_variables':{},'packages':{},'scope':'synthetic control'},'actual_numeric_backend':{'scope':'synthetic; no backend initialized'},'git_input_config':{'sha256':private_hash,'after_sha256':private_hash,'bytes':len(private),'stable':True,'private_complete_path':str(priv)},'stdout_path':str(stdout),'stdout_bytes':stdout.stat().st_size,'stdout_sha256':hashlib.sha256(stdout.read_bytes()).hexdigest(),'counts':counts,'collector_control_only':True}
        if mutation=='counts' and job['kind']=='numerical' and not fixture.mutated:
            receipt['counts']=dict(counts,cases=999);fixture.mutated=True
        if mutation=='source' and job['kind']=='numerical' and not fixture.mutated:
            receipt['candidate_sha']='0'*40;fixture.mutated=True
        if mutation=='stdout' and job['kind']=='numerical' and not fixture.mutated:
            receipt['stdout_sha256']='0'*64;fixture.mutated=True
        if mutation=='missing' and job['kind']=='numerical' and not fixture.mutated:
            fixture.mutated=True
        else:write(output/(job['name']+'.json'),receipt)
        if job['name'] in ('workspace-verify','ci-parity'):
            scopes=[]
            for reference in COLLECTOR['expected_umbrella_scopes'](ROOT,CANDIDATE,job['name']):
                scopes.append({'gate':reference['gate'],'argv':reference['argv'],'steps':[{'label':label,'outcome':'PASS','command':['SYNTHETIC_ONLY']} for label in reference['step_labels']]})
            if mutation=='stage' and job['name']=='ci-parity':scopes[0]['steps']=scopes[0]['steps'][:-1]
            write(output/'internal-stages.json',{'schema':'policyos.e02.umbrella_stages.v1','scopes':scopes,'collector_control_only':True})
        if job['name']=='static-invocation':
            raw=Path(job['argv'][job['argv'].index('--receipt')+1]);write(raw,{'mechanisms':{},'base':args.comparison_base,'denominator':{'paths':'SYNTHETIC controls only','current_files':0,'base_files':0,'source_files':0,'current_sha256':'0'*64,'base_sha256':'0'*64},'scope':'SYNTHETIC_ONLY'})
            # Canonical producer appends base/denominator last; this control keeps that layout.
            write(raw,{'mechanisms':{},'base':args.comparison_base,'denominator':{'paths':'SYNTHETIC controls only','current_files':0,'base_files':0,'source_files':0,'current_sha256':'0'*64,'base_sha256':'0'*64}})
    completion={'candidate_sha':CANDIDATE,'numerical_codes':codes,'gate_codes':gate_codes,'finished_unix':3,'collector_control_only':True}
    if mutation=='completion':completion['numerical_codes']=[0]*len(codes)
    write(wave/'execution-complete.json',completion)
    result=COLLECTOR['collect'](Namespace(repo=ROOT,candidate=CANDIDATE,wave_root=wave,publication_root=pub,max_moderate_bytes=8*1024*1024,capture_incomplete=False))
    assert not any(path.name.endswith('git-config-private.nul') or path.name.endswith('production-invocation.raw.json') for path in pub.rglob('*'))
    assert all(private not in path.read_bytes() for path in pub.rglob('*') if path.is_file())
    return {'case':name,'state':result['collection_state'],'issues':result['issues'],'numeric_counts':result['numeric_counts'],'native_counts':result['native_numeric_counts_excluding_A_packets'],'owner_A_counts':[row['counts'] for row in result['foreign_owner_A_packet_cases']],'all15_receipts':result['job_receipt_count'],'private_and_large_raw_excluded':True,'finding_closure':result['finding_closure']}

rows=[]
for name,mutation in [('positive',None),('corrupt-counts','counts'),('corrupt-source','source'),('corrupt-stdout','stdout'),('missing-receipt','missing'),('missing-required-stage','stage'),('corrupt-completion','completion')]:
    fixture.mutated=False
    row=fixture(name,mutation)
    if mutation is None:assert row['state']=='CONTROL_COMPLETE_BOUND' and not row['issues']
    else:assert row['state']=='CONTROL_LIMITED_INCOMPLETE_OR_INCONSISTENT' and row['issues']
    rows.append(row)
write(OUT/'collector-control-results.json',{'scope':'Synthetic collector protocol controls only; no product test/numeric/backend/doctor/gate executed','source_reference':CANDIDATE,'controls':rows,'all_required_controls_passed':True,'all_original_fixture_bytes_preserved':True})
print(json.dumps({'controls':len(rows),'all_passed':True,'product_or_numeric_wave_executed':False,'result':str(OUT/'collector-control-results.json')}))
