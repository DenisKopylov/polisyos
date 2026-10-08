"""Refresh explicitly named final ROOT transport inputs without source/Git writes.
V4 accepts actual owner row-list schemas and declared precompressed output identities.

Changed prior bytes remain in the immutable staged draft or immutable Git; their
old proof scope is historical. No aliases/old Git references survive a byte change
by inference. Explicit extra paths and actual published refs are the only inputs.
"""
from __future__ import annotations
import argparse,gzip,hashlib,json,re,subprocess
from pathlib import Path
from transport_text_policy import transport_text_policy
BLOCK=1<<20
PREFIX='policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/continuation-closeout-20261007'
HEX=re.compile(r'[0-9a-f]{40}')

def stream_hash(stream):
    n=0;s=hashlib.sha256()
    while chunk:=stream.read(BLOCK):n+=len(chunk);s.update(chunk)
    return {'bytes':n,'sha256':s.hexdigest()}
def binding(path):
    with path.open('rb') as f:return stream_hash(f)
def git(repository,*argv):return subprocess.check_output(['git','-C',str(repository),*argv],text=True).strip()
def git_binding(repository,ref,path):
    if not HEX.fullmatch(ref):raise ValueError('Git references must be exact40hex')
    proc=subprocess.Popen(['git','-C',str(repository),'show',f'{ref}:{path}'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    result=stream_hash(proc.stdout);err=proc.stderr.read();code=proc.wait()
    if code:raise ValueError(f'Git readback failed {ref}:{path}: {err!r}')
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed-selection',type=Path,required=True)
    parser.add_argument('--prior-manifest',type=Path,required=True)
    parser.add_argument('--prior-staging-root',type=Path,required=True)
    parser.add_argument('--repository',type=Path,required=True)
    parser.add_argument('--final-source-sha',required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--refresh-directory',type=Path,action='append',default=[])
    parser.add_argument('--include-directory',action='append',default=[],metavar='ID=PATH')
    parser.add_argument('--include-selection',action='append',default=[],metavar='ID=PATH')
    parser.add_argument('--include-file',type=Path,action='append',default=[])
    parser.add_argument('--existing-git-spec',type=Path,action='append',default=[])
    parser.add_argument('--resolve-pending',action='append',default=[])
    parser.add_argument('--publisher',type=Path,default=Path(__file__).with_name('publish_transport_v3.py'))
    args=parser.parse_args()
    if not HEX.fullmatch(args.final_source_sha):raise ValueError('actual final source SHA required')
    final_tree=git(args.repository,'rev-parse',args.final_source_sha+'^{tree}')
    seed=json.loads(args.seed_selection.read_bytes());prior=json.loads(args.prior_manifest.read_bytes())
    # Exact prior bytes/hash are checked against the manifest before use.
    snapshots={r['original_path']:r for r in prior['files']}
    by_stored={r['path']:r for r in prior['files']}
    for row in prior['aliases']:snapshots[row['original_path']]=by_stored[row['stored_path']]
    old_git={r['original_path']:r for r in prior['existing_git_files']}
    candidates={};changes=[];kept_prior=[];known_git={};extension_inputs={};inputs=[]
    def add_file(p,role='Complete explicit final input; original outcome/scope retained.'):
        p=p.resolve()
        if not p.is_file() or p.is_symlink():raise ValueError(f'explicit nonregular input: {p}')
        if p==args.output.resolve():raise ValueError('recursive selection input')
        candidates.setdefault(str(p),{'original_path':str(p),**binding(p),'role':role})
    def retain_old(row):
        original=row['original_path']
        if original in old_git:
            body=old_git[original];actual=git_binding(args.repository,body['git_ref'],body['path'])
            if actual!={'bytes':row['bytes'],'sha256':row['sha256']}:raise ValueError('prior Git locator changed')
            kept_prior.append({'original_path':original,'scope':'Historical changed draft input, not final source proof.',**body});return
        stored=snapshots[original];p=args.prior_staging_root/stored['path'];actual=binding(p)
        if actual!={'bytes':stored['bytes'],'sha256':stored['sha256']}:raise ValueError('prior staged byte binding failed')
        if stored['encoding']=='gzip':
            with gzip.open(p,'rb') as f:decoded=stream_hash(f)
        else:decoded=actual
        if decoded!={'bytes':row['bytes'],'sha256':row['sha256']}:raise ValueError('prior decoded binding failed')
        logical={'original_path':str(p.resolve()),'bytes':row['bytes'],'sha256':row['sha256'],'role':f'Historical immutable prior draft-input custody from {original}; no current final GO/quality claim.'}
        if stored['encoding']=='gzip':logical.update(input_encoding='gzip',input_binding=actual)
        candidates.setdefault(logical['original_path'],logical)
        kept_prior.append({'original_path':original,'retained_snapshot_path':str(p.resolve()),'prior_bytes':row['bytes'],'prior_sha256':row['sha256'],'prior_encoding':stored['encoding'],'scope':'Historical only'})
    # Every previous declared file is rehashed; even an alias is independently
    # compared so metadata overwrite cannot keep an old existing-ref/alias flag.
    for row in seed['logical_files']:
        p=Path(row['original_path']);actual=binding(p) if p.is_file() else None
        if actual!={'bytes':row['bytes'],'sha256':row['sha256']}:
            changes.append({'original_path':str(p),'prior':{'bytes':row['bytes'],'sha256':row['sha256']},'current':actual});retain_old(row)
        if actual is not None:add_file(p,row.get('role','Complete original observation'))
        if row['disposition']=='existing_git':
            body=row['existing_git'];expected=git_binding(args.repository,body['git_ref'],body['path'])
            if actual==expected:known_git[str(p.resolve())]=body
    # Explicit refresh folder captures additive ROOT files as well as mutations.
    for folder in args.refresh_directory:
        if not folder.is_dir():raise ValueError('refresh directory absent')
        for p in sorted(folder.rglob('*')):
            if p.is_file():add_file(p,'Actual refreshed ROOT integration metadata/custody; historical streams remain scoped.')
    def explicit(value):
        if '=' not in value:raise ValueError('extension needs explicitID=path')
        ident,path=value.split('=',1);return ident,Path(path)
    for value in args.include_directory:
        ident,folder=explicit(value)
        if not folder.is_dir():raise ValueError('explicit extension directory absent')
        if args.output.resolve().is_relative_to(folder.resolve()):raise ValueError('recursive output directory')
        files=sorted(p for p in folder.rglob('*') if p.is_file())
        if not files:raise ValueError('empty extension directory')
        for p in files:add_file(p)
        extension_inputs[ident]={'kind':'explicit_complete_directory','path':str(folder.resolve()),'file_count':len(files)}
    for value in args.include_selection:
        ident,path=explicit(value);obj=json.loads(path.read_bytes())
        row_lists=[obj[key] for key in ('files','items','selection') if isinstance(obj.get(key),list)]
        if len(row_lists)!=1:raise ValueError('extension selection needs one unambiguous complete file-row list')
        rows=row_lists[0]
        for row in rows:
            p=Path(row['path']);p=p if p.is_absolute() else path.parent/p
            if not p.is_file() or p.is_symlink():raise ValueError('extension selected input must be a regular file')
            actual=binding(p)
            if actual!={'bytes':row['bytes'],'sha256':row['sha256']}:raise ValueError('extension selected bytes differ')
            if row.get('encoding')=='gzip':
                if 'decoded_bytes' not in row or 'decoded_sha256' not in row:raise ValueError('declared gzip input needs complete decoded identity')
                with gzip.open(p,'rb') as stream:decoded=stream_hash(stream)
                if decoded!={'bytes':row['decoded_bytes'],'sha256':row['decoded_sha256']}:raise ValueError('extension gzip decoded bytes differ')
                original=str(p.resolve())
                logical={'original_path':original,**decoded,'input_encoding':'gzip','input_binding':actual,'role':row.get('role','Complete declared precompressed owner output; same compressed bytes reused, no double gzip.')}
                if original in candidates and candidates[original]!=logical:raise ValueError('one source declared with incompatible raw/decoded input modes')
                candidates[original]=logical
            elif row.get('encoding','identity')=='identity':add_file(p)
            else:raise ValueError('unknown selected input encoding')
        add_file(path,'Exact explicit complete final reviewer selection input')
        inputs.append({'original_path':str(path.resolve()),**binding(path)})
        extension_inputs[ident]={'kind':'explicit_hashchecked_selection','path':str(path.resolve()),'file_count':len(rows)}
    published=[]
    for specpath in args.existing_git_spec:
        spec=json.loads(specpath.read_bytes())
        if isinstance(spec,dict):spec=spec['files']
        for row in spec:
            expected=git_binding(args.repository,row['git_ref'],row['path'])
            if expected!={'bytes':row['bytes'],'sha256':row['sha256']}:raise ValueError('new published Git bytes differ')
            # A real observed origin ref is mandatory; no future SHA/publication
            # claim inferred from a local object. ROOT must have fetched/read it.
            remote=row['remote_ref']
            if not remote.startswith('refs/remotes/'):raise ValueError('observed remote-tracking ref required')
            tip=git(args.repository,'rev-parse',remote)
            if row.get('remote_head') and tip!=row['remote_head']:raise ValueError('observed origin head changed; refresh explicit record')
            result=subprocess.run(['git','-C',str(args.repository),'merge-base','--is-ancestor',row['git_ref'],tip],capture_output=True)
            if result.returncode:raise ValueError('published Git ref not reachable from actual observed origin ref')
            published.append({**row,'observed_remote_head':tip,'role':row.get('role','Exact new published owner receipt, referenced without copied bytes.')})
            ident=row.get('extension_id')
            if ident:extension_inputs.setdefault(ident,{'kind':'published_git','files':[]})['files'].append({'git_ref':row['git_ref'],'path':row['path'],**expected})
        inputs.append({'original_path':str(specpath.resolve()),**binding(specpath)});add_file(specpath,'Exact published-ref extension spec/readback basis')
    for p in args.include_file:add_file(p)
    # Frozen script bytes are transport inputs. The selection itself is added by
    # publisher to its OUTPUT manifest; no self-hash or recursive staging scan.
    add_file(Path(__file__),'Exact final selection refresher source')
    add_file(args.publisher,'Exact final additive streaming publisher source')
    add_file(Path(__file__).with_name('transport_text_policy.py'),'Exact complete transport-format classifier source')
    inputs.append({'original_path':str(args.seed_selection.resolve()),**binding(args.seed_selection)})
    pending=[]
    for row in seed['pending_extensions']:
        if row['id'] in args.resolve_pending:
            if row['id'] not in extension_inputs:raise ValueError('pending extension cannot resolve without explicit actual input')
        else:pending.append(row)
    unknown=set(args.resolve_pending)-{r['id'] for r in seed['pending_extensions']}
    if unknown:raise ValueError('unknown pending IDs cannot be silently introduced')
    published_by_bytes={(r['bytes'],r['sha256']):r for r in published}
    logical=[];unique={};existing=[];aliases=[];target_paths=set()
    for n,row in enumerate(candidates.values()):
        p=Path(row['original_path']);body=known_git.get(str(p)) or published_by_bytes.get((row['bytes'],row['sha256']))
        if body:
            row.update(disposition='existing_git',existing_git=body);existing.append(row);logical.append(row);continue
        key=(row['bytes'],row['sha256'])
        if key in unique:
            row.update(disposition='alias',canonical_original_path=unique[key]['original_path']);aliases.append(row);logical.append(row);continue
        # Only source paths relative to declared scratch root are accepted.
        scratch_root=Path('/tmp/e02-F-continuation-20261007')
        if not p.is_relative_to(scratch_root):raise ValueError('explicit input outside authorized continuation scratch')
        relative=p.relative_to(scratch_root).as_posix()
        # Prior stored paths would create a huge repeated prefix; use a finite
        # separately scoped prior directory while preserving complete original.
        if p.is_relative_to(args.prior_staging_root.resolve()):relative='prior-draft/'+p.relative_to(args.prior_staging_root.resolve()).as_posix()
        format_check=({'gzip_required':True,'reasons':['already_lossless_gzip_prior_snapshot']} if row.get('input_encoding')=='gzip' else transport_text_policy(p))
        row['transport_format_check']=format_check
        encoding='gzip' if format_check['gzip_required'] or p.suffix in {'.patch','.diff'} or row['bytes']>=1_000_000 else 'identity'
        target=PREFIX+'/companions/'+relative
        if encoding=='gzip' and not target.endswith('.gz'):target+='.gz'
        if target in target_paths:raise ValueError('scoped target collision')
        target_paths.add(target);row.update(disposition='transport',encoding=encoding,target_path=target);unique[key]=row;logical.append(row)
    output={**seed,'draft':bool(pending),'transport_input_selection':True,'selection_inputs':inputs,'logical_files':logical,'pending_extensions':pending,'source_window':{'actual_final_source_sha':args.final_source_sha,'actual_final_source_tree':final_tree,'historical_seed_source_window':seed['source_window'],'meaning':'Actual explicit final source window; historical b5 quality and d833 original35 GO retain their old source scopes, not current final scientific PASS.'},'refresh':{'changed_prior_inputs':changes,'retained_prior_custody':kept_prior,'explicit_extension_inputs':extension_inputs,'new_published_git_files':published,'old_aliases_recomputed_from_actual_complete_bytes':True,'old_existing_refs_kept_only_exact_bytes':True,'old_quality_raw_outputs_not_modified':True,'ROOT_decides_final_semantic_adoption':True},'existing_declared_git_references':seed['existing_declared_git_references']+published+[r for r in kept_prior if 'git_ref' in r],'counts':{'logical_files':len(logical),'unique_transport_files':len(unique),'aliases':len(aliases),'existing_git_files':len(existing),'changed_prior_inputs':len(changes),'unique_raw_transport_bytes':sum(r['bytes'] for r in unique.values())}}
    # Additive-only output; a new actual final freeze requires a new output name.
    data=(json.dumps(output,indent=2)+'\n').encode();args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('xb') as f:f.write(data)
    print(json.dumps({'output':{'path':str(args.output),**binding(args.output)},'counts':output['counts'],'pending_extensions':pending,'root_source_writes':False,'Git_writes':False,'tests_run':False},indent=2))

if __name__=='__main__':main()
