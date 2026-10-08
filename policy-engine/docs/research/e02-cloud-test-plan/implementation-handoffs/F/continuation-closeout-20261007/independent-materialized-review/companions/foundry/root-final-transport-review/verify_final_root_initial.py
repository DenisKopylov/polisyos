"""Read-only immutable Git transport/35-row verifier; never reruns science."""
import argparse,collections,copy,csv,gzip,hashlib,io,json,re,subprocess,sys
from pathlib import Path
class Invalid(ValueError): pass
def require(value,reason):
    if not value: raise Invalid(reason)
def load(raw):
    try:return json.loads(raw,parse_constant=lambda x:(_ for _ in ()).throw(Invalid('non-finite JSON constant '+x)))
    except (ValueError,UnicodeError) as error:raise Invalid('malformed JSON: '+str(error)) from error
class Reader:
    def __init__(self,repo,sha):
        self.repo=repo;self.sha=sha;self.commit_cache={};self.blob_cache={};self.hash_cache={};self.bindings=[]
        self.commit(sha)
    def git(self,*args):
        r=subprocess.run(['git','-C',self.repo,*args],capture_output=True)
        require(r.returncode==0,'Git missing/invalid object: '+' '.join(args)+' '+r.stderr.decode(errors='replace'))
        return r.stdout
    def commit(self,sha):
        require(isinstance(sha,str) and re.fullmatch('[0-9a-f]{40}',sha),'unpinned or malformed commit SHA '+repr(sha))
        if sha not in self.commit_cache:
            require(self.git('cat-file','-t',sha).strip()==b'commit','object is not commit '+sha)
            self.commit_cache[sha]=self.git('rev-parse',sha+'^{tree}').decode().strip()
        return self.commit_cache[sha]
    def blob(self,sha,path):
        self.commit(sha);require(isinstance(path,str) and not path.startswith('/') and '..' not in Path(path).parts,'noncanonical Git path '+repr(path))
        oid=self.git('rev-parse',sha+':'+path).decode().strip()
        require(self.git('cat-file','-t',oid).strip()==b'blob','not Git blob '+path)
        if oid not in self.blob_cache:self.blob_cache[oid]=self.git('cat-file','blob',oid)
        return oid,self.blob_cache[oid]
    def json(self,path,sha=None):return load(self.blob(sha or self.sha,path)[1])
    def ref(self,row,default=None):
        path=row.get('committed_path',row.get('path'))
        require(isinstance(path,str),'ref has no path')
        sha=row.get('git_ref',default or self.sha)
        oid,raw=self.blob(sha,path)
        size=row.get('stored_bytes',row.get('bytes'));digest=row.get('stored_sha256',row.get('sha256'))
        if size is not None:require(len(raw)==size,'stored size mismatch '+path)
        if digest is not None:require(hashlib.sha256(raw).hexdigest()==digest,'stored hash mismatch '+path)
        if row.get('git_blob'):require(oid==row['git_blob'],'Git blob mismatch '+path)
        if row.get('tree'):require(self.commit(sha)==row['tree'],'provider tree mismatch '+path)
        decoded_size=row.get('decoded_bytes');decoded_sha=row.get('decoded_sha256')
        if decoded_size is not None or decoded_sha is not None:
            key=(oid,row.get('encoding'),decoded_size,decoded_sha)
            if key not in self.hash_cache:
                if path.endswith('.gz') or row.get('encoding')=='gzip':stream=gzip.GzipFile(fileobj=io.BytesIO(raw))
                elif path.endswith('.txt.json') or row.get('encoding') in ['lossless_utf8_text','utf8_text_json']:
                    wrapper=load(raw);text=wrapper.get('text',wrapper.get('raw_text'));require(isinstance(text,str),'unknown text wrapper '+path);stream=io.BytesIO(text.encode('utf-8'))
                else:stream=io.BytesIO(raw)
                h=hashlib.sha256();count=0
                try:
                    while True:
                        chunk=stream.read(1024*1024)
                        if not chunk:break
                        count+=len(chunk);h.update(chunk)
                except (OSError,EOFError) as error:raise Invalid('malformed codec '+path+' '+str(error)) from error
                if decoded_size is not None:require(count==decoded_size,'decoded size mismatch '+path)
                if decoded_sha is not None:require(h.hexdigest()==decoded_sha,'decoded hash mismatch '+path)
                self.hash_cache[key]=(count,h.hexdigest())
        self.bindings.append({'git_ref':sha,'path':path,'git_blob':oid,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'decoded_bytes':decoded_size,'decoded_sha256':decoded_sha})
        return raw
    def references(self,value):
        if isinstance(value,list):
            for x in value:self.references(x)
        elif isinstance(value,dict):
            if 'committed_path' in value or ('path' in value and ('git_ref' in value or 'sha256' in value) and isinstance(value['path'],str) and not value['path'].startswith('/')):self.ref(value)
            for sha_key,tree_key in [('code_candidate_sha','code_candidate_tree'),('code_sha','code_tree'),('source_sha','source_tree'),('tested_source_sha','tested_source_tree_sha'),('candidate_sha','candidate_tree_sha')]:
                if value.get(sha_key) and re.fullmatch('[0-9a-f]{40}',str(value[sha_key])):
                    tree=self.commit(value[sha_key]);
                    if value.get(tree_key):require(tree==value[tree_key],'source/tree mismatch '+sha_key)
            if isinstance(value.get('sha'),str) and re.fullmatch('[0-9a-f]{40}',value['sha']) and isinstance(value.get('tree'),str):require(self.commit(value['sha'])==value['tree'],'source/tree mismatch')
            for x in value.values():
                if isinstance(x,(dict,list)):self.references(x)
def verify(config,mutator=None):
    r=Reader(config['repository'],config['candidate_sha'])
    require(r.commit(config['candidate_sha'])==config['candidate_tree'],'frozen candidate tree mismatch')
    primary=r.json(config['primary_path']);index=r.json(config['index_path']);audit=r.json(config['audit_path']);manifest=r.json(config['manifest_path'])
    if mutator:mutator(primary,index,audit,manifest)
    for key in ['schema','unit','slice','closure_ids','bundle_ids','slice_base_sha','implementation_commits','candidate_tree_sha','branch','pull_request','changed_paths','baseline_cells','checks','property','predicate_basis','capability_state_or_finding_state','limitations_and_next_owner']:require(key in primary,'primary mandatory field '+key)
    require(primary['unit']=='F','wrong primary unit');require(primary['closure_ids']==[],'unexpected formal closure marker')
    if primary.get('candidate_sha'):r.commit(primary['candidate_sha']);require(r.commit(primary['candidate_sha'])==primary['candidate_tree_sha'],'primary candidate/tree mismatch')
    require(not primary.get('formal_G_findings_closed',0),'unissued G closures');require(not primary.get('main_or_integration_published',False),'unexpected main/integration claim')
    for check in primary['checks']:
        for key in ['command','target_sha','environment','input_closure','outcome','output']:require(isinstance(check.get(key),str) and check[key],'primary check required '+key)
        require(check['outcome'] in ['PASS','FAIL','ERROR','SKIP','UNRUN'],'noncanonical check state');r.commit(check['target_sha'])
        output=check['output']
        if output.startswith('policy-engine/'):
            path,sep,sha=output.rpartition('@')
            r.blob(sha,path) if sep and re.fullmatch('[0-9a-f]{40}',sha) else r.blob(config['candidate_sha'],output)
    owners=list(csv.DictReader(io.StringIO(r.blob(config['candidate_sha'],config['finding_owners_path'])[1].decode()),delimiter='\t'))
    expected={x['finding_id'] for x in owners if x['unit']=='F'};require(len(expected)==35,'canonical TSV F denominator not35')
    rows=index['rows'];ids=[x['finding_id'] for x in rows];require(len(rows)==35 and len(set(ids))==35 and set(ids)==expected,'35-row duplicate/missing/unknown ID')
    refs=index['per_ID_complete_records'];refids=[x['finding_id'] for x in refs];require(len(refs)==35 and len(set(refids))==35 and set(refids)==expected,'35 per-ID duplicate/missing/unknown ID')
    require(index['denominator']['IDs']==35 and index['denominator']['bundles']==17 and index['denominator']['original_bindings']==36,'wrong original denominator')
    require(index.get('formal_G_acceptance') is False,'unissued formal G acceptance')
    binding_count=0
    for row in rows:
        require(row['F_finding_outcome'] in ['closed','limited','held','open'],'noncanonical F finding outcome')
        require(row['F_technical_recommendation'] in ['closed','limited','held','open'],'noncanonical technical recommendation')
        require(row['check_result'] in ['PASS','FAIL','ERROR','SKIP','UNRUN'],'noncanonical per-ID check')
        require(row['G_finding_acceptance'].get('formal_G_closed') is False,'unissued per-ID G closure')
        require(not(row['check_result'] in ['ERROR','SKIP'] and row['F_technical_recommendation']=='closed'),'skip/error treated as technical closed')
        rr=next(x for x in refs if x['finding_id']==row['finding_id']);body=load(r.ref(rr));require(body==row,'index/per-ID body mismatch '+row['finding_id'])
        for card in row['original_card_refs']:
            oid,raw=r.blob(card['source_sha'],card['source_path']);require(oid==card['document_git_blob'],'original card document Git blob mismatch')
            start,end=card['lines'];selected=b''.join(raw.splitlines(keepends=True)[start-1:end]);require(len(selected)==card['bytes'] and hashlib.sha256(selected).hexdigest()==card['sha256'],'original criterion bytes mismatch '+row['finding_id']);binding_count+=1
    require(binding_count==36,'original card bindings not36')
    require([x['finding_id'] for x in audit['rows']]==refids,'audit/per-ID membership mismatch')
    for doc in [primary,index,audit,manifest]:r.references(doc)
    if 'mandatory_companions' in primary:
        require(len(set(primary['mandatory_companions']))==len(primary['mandatory_companions']),'duplicate companion path')
        for path in primary['mandatory_companions']:r.blob(config['candidate_sha'],path)
    return {'outcome':'PASS','scope':'Structural immutable root transport, content custody and original35 bookkeeping only; no scientific rerun/re-adjudication.','candidate_sha':config['candidate_sha'],'candidate_tree':config['candidate_tree'],'IDs':35,'original_bindings':binding_count,'bundles':17,'F_finding_counts':dict(collections.Counter(x['F_finding_outcome'] for x in rows)),'check_counts':dict(collections.Counter(x['check_result'] for x in rows)),'checked_refs':r.bindings,'unique_stored_blobs_read':len(r.blob_cache),'unique_decoded_bindings_checked':len(r.hash_cache),'formal_G_closures':0}
def main():
    parser=argparse.ArgumentParser();parser.add_argument('config');parser.add_argument('--controls',action='store_true');args=parser.parse_args();config=load(Path(args.config).read_bytes());result=verify(config)
    if args.controls:
        def future(p,i,a,m):p['checks'][0]['target_sha']='0'*40
        def missing(p,i,a,m):p['checks'][0]['output']='policy-engine/__independent_missing_deciding_output__.json'
        def duplicate(p,i,a,m):i['rows'][1]['finding_id']=i['rows'][0]['finding_id']
        controls=[]
        for name,mut in [('future_SHA',future),('missing_output',missing),('duplicate_ID',duplicate)]:
            try:verify(config,mut)
            except Invalid as error:controls.append({'control':name,'expected_refusal':'PASS','actual_outcome':'FAIL','reason':str(error)})
            else:raise Invalid('negative falsely accepted '+name)
        try:load(b'{"schema":')
        except Invalid as error:controls.append({'control':'malformed_JSON','expected_refusal':'PASS','actual_outcome':'FAIL','reason':str(error)})
        else:raise Invalid('malformed JSON falsely accepted')
        result['negative_controls']=controls
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':
    try:main()
    except (Invalid,KeyError,TypeError) as error:print(json.dumps({'outcome':'FAIL','reason':str(error)}));sys.exit(1)
