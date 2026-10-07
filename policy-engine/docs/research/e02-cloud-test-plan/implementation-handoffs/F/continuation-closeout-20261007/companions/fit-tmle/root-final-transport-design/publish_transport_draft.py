"""Materialize an additive exact-byte transport without any Git mutation.

Default validates only. --materialize requires an explicit destination; source
raw files remain untouched. ROOT may supply its separately reviewed final primary.
This script neither decides finding closure nor runs scientific/source tests.
"""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess

BLOCK = 1 << 20
PREFIX = 'policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/continuation-closeout-20261007'
PRIMARY = 'policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/continuation-closeout-20261007.json'

def hash_stream(stream):
    size=0;sha=hashlib.sha256()
    while chunk:=stream.read(BLOCK):size+=len(chunk);sha.update(chunk)
    return size,sha.hexdigest()

def file_binding(path):
    with path.open('rb') as stream:size,sha=hash_stream(stream)
    return {'bytes':size,'sha256':sha}

def safe_target(destination, relative):
    rel=PurePosixPath(relative)
    if rel.is_absolute() or '..' in rel.parts or not str(rel).startswith(PREFIX+'/'):
        raise ValueError(f'unsafe or out-of-scope target: {relative}')
    return destination.joinpath(*rel.parts)

def verify_original(row):
    path=Path(row['original_path'])
    if not path.is_file() or path.is_symlink():raise ValueError(f'nonregular source: {path}')
    actual=file_binding(path)
    if actual != {'bytes':row['bytes'],'sha256':row['sha256']}:
        raise ValueError(f'selected original changed: {path}: {actual}')

def verify_git(repository, row):
    body=row['existing_git'];ref=body['git_ref'];path=body['path']
    if not re.fullmatch('[0-9a-f]{40}',ref):raise ValueError('unpinned existing Git ref')
    process=subprocess.Popen(['git','-C',str(repository),'show',f'{ref}:{path}'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    size,sha=hash_stream(process.stdout);stderr=process.stderr.read();code=process.wait()
    if code or size!=body['bytes'] or sha!=body['sha256']:
        raise ValueError(f'existing Git byte binding failed: {ref}:{path}; {code}; {stderr!r}')

def write_exact(row, destination):
    target=safe_target(destination,row['target_path']);target.parent.mkdir(parents=True,exist_ok=True)
    # Resume verifies a fully written existing carrier; it never replaces a
    # partial or different file. Interrupted bytes are preserved for diagnosis.
    if not target.exists():
        with Path(row['original_path']).open('rb') as source,target.open('xb') as raw:
            if row['encoding']=='gzip':
                with gzip.GzipFile(filename='',fileobj=raw,mode='wb',compresslevel=6,mtime=0) as stored:
                    while chunk:=source.read(BLOCK):stored.write(chunk)
            elif row['encoding']=='identity':
                while chunk:=source.read(BLOCK):raw.write(chunk)
            else:raise ValueError('unknown encoding')
    stored=file_binding(target)
    if row['encoding']=='gzip':
        with gzip.open(target,'rb') as decoded:size,sha=hash_stream(decoded)
        restored={'bytes':size,'sha256':sha}
    else:restored=stored
    expected={'bytes':row['bytes'],'sha256':row['sha256']}
    if restored!=expected:raise ValueError(f'full decoded readback failed: {target}')
    return {'path':row['target_path'],'encoding':row['encoding'],**stored,'decoded_bytes':row['bytes'],'decoded_sha256':row['sha256'],'original_path':row['original_path'],'role':row['role']}

def write_json_additive(path, value):
    data=(json.dumps(value,indent=2,ensure_ascii=False)+'\n').encode()
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        if path.read_bytes()!=data:raise ValueError(f'additive carrier already exists with other bytes: {path}')
    else:
        with path.open('xb') as stream:stream.write(data)
    return file_binding(path)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selection',type=Path,required=True)
    parser.add_argument('--repository',type=Path,required=True)
    parser.add_argument('--materialize',action='store_true')
    parser.add_argument('--destination',type=Path)
    parser.add_argument('--primary-template',type=Path)
    args=parser.parse_args()
    selected=json.loads(args.selection.read_bytes())
    if args.materialize and args.destination is None:parser.error('--materialize requires explicit --destination')
    if args.primary_template and not args.materialize:parser.error('--primary-template requires materialize')
    rows=selected['logical_files'];paths=set();by_original={}
    for row in rows:
        verify_original(row)
        if row['original_path'] in by_original:raise ValueError('recursive/duplicate original path')
        by_original[row['original_path']]=row
        if row['disposition']=='existing_git':verify_git(args.repository,row)
        elif row['disposition']=='transport':
            if row['target_path'] in paths:raise ValueError('target path collision')
            paths.add(row['target_path'])
    for row in rows:
        if row['disposition']=='alias':
            original=by_original[row['canonical_original_path']]
            if original['disposition']!='transport' or row['bytes']!=original['bytes'] or row['sha256']!=original['sha256']:
                raise ValueError('alias does not bind complete canonical bytes')
    if not args.materialize:
        print(json.dumps({'mode':'validation_only','validated_logical_files':len(rows),'checks':'PASS','science_tests_run':False,'git_writes':False,'pending_extensions':selected['pending_extensions']},indent=2));return
    destination=args.destination.resolve();destination.mkdir(parents=True,exist_ok=True)
    output={};actual=[];existing=[];aliases=[]
    for row in rows:
        if row['disposition']=='transport':
            stored=write_exact(row,destination);output[row['original_path']]=stored;actual.append(stored)
        elif row['disposition']=='existing_git':
            existing.append({'original_path':row['original_path'],**row['existing_git']})
    for row in rows:
        if row['disposition']=='alias':
            stored=output[row['canonical_original_path']]
            aliases.append({'original_path':row['original_path'],'source_bytes':row['bytes'],'source_sha256':row['sha256'],'canonical_original_path':row['canonical_original_path'],'stored_path':stored['path'],'encoding':stored['encoding'],'stored_bytes':stored['bytes'],'stored_sha256':stored['sha256'],'decoded_bytes':stored['decoded_bytes'],'decoded_sha256':stored['decoded_sha256']})
    manifest={'schema':'policyos.e02.artifact_transports.v1','draft':selected['draft'],'files':actual,'aliases':aliases,'existing_git_files':existing,'existing_declared_git_references':selected['existing_declared_git_references'],'selection_inputs':selected['selection_inputs'],'pending_extensions':selected['pending_extensions'],'source_window':selected['source_window'],'policy':selected['policy'],'sanitation':'none; byte-exact identity or lossless gzip; originals preserved','counts':{'logical_files':len(rows),'transported_files':len(actual),'aliases':len(aliases),'existing_git_files':len(existing),'stored_bytes':sum(row['bytes'] for row in actual),'decoded_unique_bytes':sum(row['decoded_bytes'] for row in actual)}}
    manifest_target=safe_target(destination,PREFIX+'/artifact-transports.json')
    manifest_binding=write_json_additive(manifest_target,manifest)
    primary_written=False
    if args.primary_template:
        primary=json.loads(args.primary_template.read_bytes())
        if primary.get('draft') or not re.fullmatch('[0-9a-f]{40}',str(primary.get('candidate_sha',''))) or not re.fullmatch('[0-9a-f]{40}',str(primary.get('candidate_tree_sha',''))):
            raise ValueError('ROOT final primary must provide reviewed actual immutable candidate SHA/tree, not a draft/future identity')
        tree=subprocess.check_output(['git','-C',str(args.repository),'rev-parse',primary['candidate_sha']+'^{tree}'],text=True).strip()
        if tree!=primary['candidate_tree_sha']:raise ValueError('candidate tree differs from immutable Git')
        for check in primary.get('checks',[]):
            if not isinstance(check.get('output'),str) or not isinstance(check.get('outcome'),str):raise ValueError('canonical checks output/outcome must be strings')
        if selected['pending_extensions']:raise ValueError('final primary blocked until exact pending extension refs are resolved by ROOT')
        primary['artifact_transports']={'path':PREFIX+'/artifact-transports.json',**manifest_binding}
        primary_path=destination.joinpath(*PurePosixPath(PRIMARY).parts)
        write_json_additive(primary_path,primary);primary_written=True
    print(json.dumps({'mode':'materialized_exact_bytes','destination':str(destination),'artifact_transports':{'path':str(manifest_target),**manifest_binding},'counts':manifest['counts'],'primary_written':primary_written,'git_writes':False,'science_tests_run':False},indent=2))

if __name__=='__main__':main()
