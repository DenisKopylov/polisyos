#!/usr/bin/env python3
"""Verify this source-grounded launch kit only; never imports or runs PolicyOS."""
from __future__ import annotations
import argparse
import collections
import graphlib
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote

EXPECTED_SOURCES = {'B_r19': '9c98584cbfa72996b058abf127f6c689f919a3421cdd563a82c84a7324ab39b5', 'LA_r09': '2e13d05d40ab162dba6f1ed495865037bc08fc359a987e7a42c4d445a9b8d727'}
BLOCK_RE = re.compile(r'<!-- SOURCE_BEGIN ([A-Z]+):([\w-]+) -->\n(.*?)<!-- SOURCE_END \1:\2 -->\n', re.S)

def load(root: Path, name: str):
    return json.loads((root / name).read_text(encoding='utf-8'))

def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)

def blocks(text: str):
    result = collections.defaultdict(list)
    for kind, key, body in BLOCK_RE.findall(text):
        result[(kind, key)].append(body)
    return result

def strip_source_blocks(text: str) -> str:
    return BLOCK_RE.sub('', text)

def verify(root: Path, check_hashes: bool = True) -> dict:
    root = root.resolve()
    m = load(root, 'bundle_manifest.json')
    bundles = m['bundles']
    ids = [b['id'] for b in bundles]
    require(len(ids) == 127 and len(set(ids)) == 127, 'Expected 127 unique active packets')
    require(m['current_head_verified'] is False and m['native_PolicyOS_tests_run'] is False and m['mac_load_test_run'] is False, 'Plan must not claim native/current verification')
    bm = {b['id']: b for b in bundles}
    B = [x for b in bundles for x in b['findings']]
    expected_B = {f'B{x:02d}' for x in range(1,226)}
    require(set(B) == expected_B and len(B) == 225, 'B coverage has missing or duplicate assignments')
    require(load(root,'finding_to_bundle.json') == {x:b['id'] for b in bundles for x in b['findings']}, 'B mapping drift')
    lm = load(root, 'legacy_to_bundles.json')
    require(set(lm) == {f'LA-{x:03d}' for x in range(1,58)}, 'LA coverage incomplete')
    require(collections.Counter(x['category'] for x in lm.values()) == {'D':8,'C':12,'R':10,'M':27}, 'Legacy category counts changed')
    for la, data in lm.items():
        participants = {b['id'] for b in bundles if la in b['legacy_cards']}
        require(participants == set(data['required_bundles']) and bool(participants), f'{la} phased mapping drift')
        require(data['closure_owner'] in participants, f'{la} lacks a closure owner')
        for bid in participants:
            require(bool(bm[bid]['legacy_scope'].get(la)), f'{la} phase scope absent in {bid}')
    controls = {f'LK{x:02d}' for x in range(1,37)}
    require({x for b in bundles for x in b['protected_controls']} == controls, 'Protected LK coverage incomplete')
    require({'LK34','LK35'} <= set(bm['DDM-02']['protected_controls']), 'DDM R2/schema protections missing')
    require('LK36' in bm['RUN-01']['protected_controls'], 'Async bridge protection missing')
    require('LA-057' in bm['RUN-01']['legacy_cards'] and 'LA-045' in bm['REQ-01']['legacy_cards'], 'Exact cleanup owners lost')
    require(len(m['evolution']) == 8 and {e['source_direction'] for e in m['evolution']} == {f'S{x:02d}' for x in range(1,9)}, 'S directions not preserved')
    r = m['local_execution']
    require(r['light_max_jobs'] == 2 and r['native_max_jobs'] == 1 and r['native_exclusive'] is True and r['checkpoint_exclusive'] is True and r['checkpoint_max_jobs'] == 1, 'Mac resource limits changed')
    require(r['routine_load_polling'] is False and r['parallel_installs'] is False, 'Monitoring/install anti-pattern introduced')
    require((r['implementers'],r['reviewers'],r['integrators'],r['default_luna']) == (9,3,2,14), 'Default team mismatch')
    require(r['modes'] == {'12':[8,2,2],'14':[9,3,2],'16':[10,4,2]}, 'Team ranges mismatch')
    graph = {b['id']: b['depends_on'] for b in bundles}
    require(all(x in bm for deps in graph.values() for x in deps), 'Unknown dependency')
    try:
        topo = list(graphlib.TopologicalSorter(graph).static_order())
    except graphlib.CycleError as exc:
        raise ValueError('Implementation dependency cycle') from exc
    require(set(topo) == set(ids), 'DAG nodes mismatch')
    dg = load(root, 'dependency_graph.json')
    edges = {(x,b['id']) for b in bundles for x in b['depends_on']}
    require(edges == {(e['from'],e['to']) for e in dg['edges']}, 'Dependency JSON drift')
    actual_conflicts = {}
    for i,a in enumerate(bundles):
        for b in bundles[i+1:]:
            paths=sorted(set(a['lease_paths'])&set(b['lease_paths']))
            extra=sorted(set(a['special_leases'])&set(b['special_leases']))
            if paths or extra:actual_conflicts[frozenset([a['id'],b['id']])] = (paths,extra)
    supplied = {frozenset([c['a'],c['b']]):(c['paths'],c['special_leases']) for c in dg['write_conflicts']}
    require(supplied == actual_conflicts, 'Write conflict map incomplete or stale')
    for bid,b in bm.items():
        peers={next(iter(pair-{bid})) for pair in supplied if bid in pair}
        require(peers == set(b['write_conflicts_with']), f'{bid} asymmetric conflicts')
        require(set(b['write_paths']) <= set(b['lease_paths']), f'{bid} write not leased')
        require(b['proposed_regression_file'] in b['lease_paths'], f'{bid} test write not leased')
        require(b['initial_status']=='planned' and b['checkpoint_status']=='not_run', f'{bid} premature completion')
        require(b['checkpoint'] in {f'CP{x}' for x in range(1,7)}, f'{bid} ambiguous checkpoint ID')
        require(b['check_class'] in {'L','N'}, f'{bid} invalid local test class')
    first=m['first_dispatch']
    require(len(first)==9 and len(set(first))==9, 'Initial writer count mismatch')
    require(all(not graph[x] for x in first), 'Initial dispatch waits for prerequisite')
    require(not any(pair<=set(first) for pair in supplied), 'Initial dispatch conflict')
    reloc=load(root,'relocation_map.json')['moves']
    require(len(reloc)==21, 'Relocation map count mismatch')
    for move in reloc:
        owner=bm[move['owner_bundle']]
        require(set(move['source_paths']+move['proposed_target_paths']) <= set(owner['lease_paths']), f'{move["id"]} does not lease both move ends')
        require(all(x in bm for x in move['followers']), 'Unknown relocation follower')
        require(move['initial_status']=='proposed_not_applied', 'Unperformed move marked applied')
    lanes=load(root,'migration_lanes.json')
    require(len(lanes)==12 and {x for l in lanes for x in l['bundles']}==set(ids), 'Migration lanes lose a bundle')
    require(set(m['T_scenarios'])=={f'T{x}' for x in range(1,22)}, 'T scenario coverage incomplete')
    require(all(x in bm for members in m['T_scenarios'].values() for x in members), 'Unknown T bundle')
    for a in m['activation_rules']:
        require(all(x in bm for x in a['bundles']), f'{a["id"]} unknown activation participant')
    # Preserve all exact input bytes and all fully quoted source slices.
    sourcetext={}
    sourcelines={}
    for s in m['sources']:
        data=(root/s['path']).read_bytes()
        require(digest(data)==s['sha256']==EXPECTED_SOURCES[s['id']], f'{s["id"]} source integrity mismatch')
        sourcetext[s['id']]=data.decode('utf-8')
        sourcelines[s['id']]=data.decode('utf-8').splitlines(keepends=True)
    for p in m['parents']:
        require(digest((root/p['path']).read_bytes())==p['sha256'], 'Parent E01 altered')
    bix=load(root,'source/card_index.json');lix=load(root,'source/legacy_card_index.json');cix=load(root,'source/legacy_control_index.json');am=load(root,'source/amendment_index.json')
    expected={}
    for key,data in bix.items():
        body=''.join(sourcelines['B_r19'][data['start_line']-1:data['end_line']])
        require(digest(body.encode())==data['sha256'], f'{key} source range mismatch')
        expected[('S' if key.startswith('S') else 'B',key)]=body
    for kind,index in [('LA',lix),('LK',cix)]:
        for key,data in index.items():
            body=''.join(sourcelines['LA_r09'][data['start_line']-1:data['end_line']])
            require(digest(body.encode())==data['sha256'], f'{key} legacy source range mismatch')
            expected[(kind,key.replace('K','LK') if kind=='LK' else key)]=body
    require(len(am)==4, 'Late amendments missing')
    for a in am:
        body=''.join(sourcelines['LA_r09'][a['start_line']-1:a['end_line']])
        require(digest(body.encode())==a['sha256'], 'Amendment source mismatch')
        expected[('AM',a['amendment_id'])]=body
    require(any(a['id']=='LA-045' and '_digest' in expected[('AM',a['amendment_id'])] for a in am), 'LA045 _digest amendment missing')
    require(any(a['id']=='LA-046' and 'без resolver' in expected[('AM',a['amendment_id'])] for a in am), 'LA046 actual handoff amendment missing')
    segments=load(root,'source/segments.json')
    for sid in sourcetext:
        parts=[s for s in segments if s['source']==sid]
        pos=1;out=[]
        for s in parts:
            require(s['start_line']==pos, f'{sid} partition gap/overlap')
            body=''.join(sourcelines[sid][s['start_line']-1:s['end_line']])
            require(digest(body.encode())==s['sha256'], 'Context range hash mismatch')
            if s['kind']=='CTX':expected[('CTX',s['id'])]=body
            out.append(body);pos=s['end_line']+1
        require(''.join(out)==sourcetext[sid], f'{sid} historical context not preserved')
    main=(root/m['main_document']).read_text(encoding='utf-8');mb=blocks(main)
    for key,body in expected.items():
        require(key in mb and all(x==body for x in mb[key]), f'Master omitted/changed source block {key}')
    require(set(mb)==set(expected), 'Master has unexpected source blocks')
    for b in bundles:
        path=root/b['artifact_path'];require(path.is_file(), f'{b["id"]} packet absent')
        text=path.read_text(encoding='utf-8');found=blocks(text)
        keys={('B',x) for x in b['findings']}|{('LA',x) for x in b['legacy_cards']}|{('LK',x) for x in b['protected_controls']}|{('AM',a['amendment_id']) for a in am if a['id'] in b['legacy_cards']}
        require(set(found)==keys, f'{b["id"]} source blocks/amendments incomplete')
        for key in keys:require(found[key]==[expected[key]], f'{b["id"]} changed/duplicate source block {key}')
        for key in ['work','tests','avoid']:require(b[key] in text, f'{b["id"]} manifest/prose {key} drift')
        require(b['checkpoint'] in text, f'{b["id"]} checkpoint prose mismatch')
    for e in m['evolution']:
        eb=blocks((root/e['artifact_path']).read_text(encoding='utf-8'))
        require(eb.get(('S',e['source_direction']))==[expected[('S',e['source_direction'])]], 'EVO source changed')
    # Relative links in new operational prose only. Original historical URLs/paths are unchanged evidence.
    checked_links=0
    for path in root.rglob('*.md'):
        if any(x in path.relative_to(root).parts for x in ['source','parent']):continue
        text=strip_source_blocks(path.read_text(encoding='utf-8'))
        text=re.sub(r'```.*?```','',text,flags=re.S)
        for raw in re.findall(r'\[[^\]\n]+\]\(([^\s)]+)\)',text):
            if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:',raw):continue
            rel,_,anchor=raw.partition('#');target=(path.parent/unquote(rel)).resolve() if rel else path.resolve()
            require(root==target or root in target.parents, f'Link escapes kit: {path.name}:{raw}')
            require(target.is_file(), f'Broken relative link: {path.name}:{raw}')
            if anchor:
                targettext=target.read_text(encoding='utf-8')
                require(f'id="{unquote(anchor)}"' in targettext, f'Unknown explicit anchor {path.name}:{raw}')
            checked_links+=1
    cross=load(root,'E01_TO_E02.json')
    require(len(cross['old_ids_retained'])==84 and set(cross['old_ids_retained']) <= set(ids), 'Old packet IDs lost')
    require(len(cross['new_ids'])==43 and set(cross['new_ids'])==set(ids)-set(cross['old_ids_retained']), 'New packet crosswalk mismatch')
    require(len(cross['B_reassignments'])==6, 'B split count mismatch')
    for x in cross['B_reassignments']:require(x['finding'] in bm[x['to']]['findings'], 'Split destination wrong')
    for field,value in [('implementation_edges',len(edges)),('write_conflict_pairs',len(supplied)),('relocation_maps',len(reloc)),('coordination_lanes',len(lanes))]:require(m['counts'][field]==value, f'Count drift {field}')
    checksum_count=0
    if check_hashes:
        sums=root/'SHA256SUMS';require(sums.is_file(), 'SHA256SUMS missing')
        listed=set()
        for line in sums.read_text(encoding='utf-8').splitlines():
            hashval,name=line.split('  ',1);require(name not in listed, 'Duplicate checksum path');listed.add(name)
            p=(root/name).resolve();require(root in p.parents and p.is_file(), 'Invalid checksum path')
            require(digest(p.read_bytes())==hashval, f'Checksum mismatch {name}');checksum_count+=1
        actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p.name!='SHA256SUMS' and '__pycache__' not in p.parts and not p.name.endswith('.pyc')}
        require(actual==listed, 'Checksum inventory has extra/missing files')
    return {'status':'PASS','scope':'launch-kit integrity and plan structure only; not PolicyOS code or hardware tests','bundles':len(ids),'B_unique':225,'LA_unique':57,'S_unique':8,'protected_controls':36,'late_amendments':4,'dependency_edges':len(edges),'write_conflict_pairs':len(supplied),'initial_dispatch_conflict_free':True,'source_partitions_complete':True,'source_blocks_unchanged':True,'relative_links_checked':checked_links,'checksums_checked':checksum_count,'native_PolicyOS_tests_run':False,'current_head_verified':False}

def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parent)
    parser.add_argument('--skip-hashes',action='store_true',help='Structural developer/mutation test only; normal delivery verification checks hashes.')
    args=parser.parse_args()
    try:
        report=verify(args.root,check_hashes=not args.skip_hashes)
    except (ValueError,KeyError,OSError,json.JSONDecodeError) as exc:
        print(json.dumps({'status':'FAIL','error':str(exc)},ensure_ascii=False,indent=2));return 1
    print(json.dumps(report,ensure_ascii=False,indent=2));return 0

if __name__=='__main__':
    sys.exit(main())
