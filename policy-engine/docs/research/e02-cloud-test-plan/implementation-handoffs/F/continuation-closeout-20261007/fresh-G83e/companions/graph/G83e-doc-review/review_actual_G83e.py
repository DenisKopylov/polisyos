#!/usr/bin/env python3
"""Read-only, exact-Git review of the actual G83e documentation merge.
No product imports, fixtures, source edits, Git mutation or numerical tests.
"""
import argparse, csv, hashlib, io, json, pathlib, re, subprocess, sys, xml.etree.ElementTree as ET
REPO = pathlib.Path('/workspace/e02-F-closeout-20261006')
OWN = pathlib.Path('/workspace/e02-F-graph-20261006')
BASE = '855cb26a7a2c9fea60356663cf81e7d01e20c738'
G = '83e7c0e934d0b40644dec8a24264a0602ef013e7'
PARENT = '92e1eea364e9038fc7f6868335b2c98226d2dab2'
MERGE = 'ea9a606f06dad1f94c0f841ec1ec7a53fc694f5c'
TREE = '4d5fccfc3f89c7149af500b523e5ad44a3838df2'
GTREE = 'dc1a7697f506b23f2db0f1c80bf929fd2d6a2e0d'
OWNHEAD = 'ffae9fa4b45c23c3d2dca5c1bbf78d18418a7634'
PREFIX = 'policy-engine/docs/research/e02-cloud-test-plan/'
ROOT_CAPTURE = pathlib.Path('/tmp/e02-F-continuation-20261007/root-fresh-G-83e/ordinary-G83e-merge.json')
CHECKS = []
COMMANDS = []

def digest(data):
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}

def command(args, cwd=REPO, expected=0):
    p = subprocess.run(args, cwd=cwd, capture_output=True)
    COMMANDS.append({'argv': args, 'cwd': str(cwd), 'returncode': p.returncode,
                     'stdout': digest(p.stdout), 'stderr': digest(p.stderr)})
    if p.returncode != expected:
        raise RuntimeError(f'Unexpected command exit {p.returncode}: {args!r}; {p.stderr.decode(errors="replace")}')
    return p.stdout

def git(*args):
    return command(['git', *args])

def blob(ref, path):
    return git('show', ref + ':' + path)

def check(name, ok, detail):
    row = {'name': name, 'check': 'PASS' if ok else 'FAIL', 'detail': detail}
    CHECKS.append(row)
    if not ok:
        raise AssertionError(json.dumps(row, ensure_ascii=False))

def jdigest(value):
    return digest(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode())

def recursive_diff(a, b, path=()):
    if type(a) is not type(b):
        return [{'path': list(path), 'before': a, 'after': b}]
    if isinstance(a, dict):
        if set(a) != set(b):
            return [{'path': list(path), 'before_keys': sorted(a), 'after_keys': sorted(b)}]
        return sum((recursive_diff(a[k], b[k], path + (k,)) for k in a), [])
    if isinstance(a, list):
        if len(a) != len(b):
            return [{'path': list(path), 'before_length': len(a), 'after_length': len(b)}]
        return sum((recursive_diff(x, y, path + (i,)) for i, (x, y) in enumerate(zip(a, b))), [])
    return [] if a == b else [{'path': list(path), 'before': a, 'after': b}]

def f_section(data):
    hit = re.search(rb'^## F [^\n]*\n', data, re.M)
    if not hit:
        raise ValueError('Missing F section')
    return data[hit.start():]

def ce_section(data):
    start = re.search(rb'^## C [^\n]*\n', data, re.M)
    end = re.search(rb'^## F [^\n]*\n', data, re.M)
    if not start or not end:
        raise ValueError('Missing method C/F section')
    return data[start.start():end.start()]

def verify_root_capture():
    raw = ROOT_CAPTURE.read_bytes()
    d = json.loads(raw)
    refs = []
    for row in d['records']:
        for key, ref in row['outputs'].items():
            p = pathlib.Path(ref['path'])
            b = p.read_bytes()
            check('ROOT captured command full ' + row['label'] + '/' + key,
                  digest(b) == {'bytes': ref['bytes'], 'sha256': ref['sha256']},
                  {'path': str(p), 'declared': ref, 'actual': digest(b)})
            refs.append({'label': row['label'], 'stream': key, **ref})
    expected_identity = f'{MERGE} {TREE} {PARENT} {G}'
    check('ROOT ordinary merge record identity', d['actual_merge_identity'] == expected_identity,
          {'expected': expected_identity, 'actual': d['actual_merge_identity']})
    return {'path': str(ROOT_CAPTURE), **digest(raw), 'records': d['records'], 'full_output_refs': refs}

def run(outdir):
    begin = command(['git', 'status', '--porcelain=v1'], cwd=OWN)
    ownid = command(['git', 'show', '-s', '--format=%H %T', 'HEAD'], cwd=OWN).decode().strip()
    check('Own admitted branch clean/read-only before', begin == b'' and ownid.startswith(OWNHEAD + ' '),
          {'identity': ownid, 'porcelain': begin.decode()})
    ident = git('show', '-s', '--format=%H %T %P', MERGE).decode().strip()
    check('Actual immutable merge identity', ident == f'{MERGE} {TREE} {PARENT} {G}', {'identity': ident})
    gident = git('show', '-s', '--format=%H %T %P', G).decode().strip()
    check('Fresh G identity', gident == f'{G} {GTREE} {BASE}', {'identity': gident})
    root_capture = verify_root_capture()
    gd = git('diff', '--name-status', BASE, G)
    md = git('diff', '--name-status', PARENT, MERGE)
    (outdir / 'actual-merge-name-status.stdout').write_bytes(md)
    (outdir / 'actual-merge-name-status.stderr').write_bytes(b'')
    gchanges = [line.split('\t') for line in gd.decode().splitlines()]
    mchanges = [line.split('\t') for line in md.decode().splitlines()]
    check('Exact complete changed-path denominator', gchanges == mchanges and len(gchanges) == 42,
          {'G_paths': gchanges, 'actual_merge_paths': mchanges, 'count': len(gchanges)})
    check('No product/source/test/build/schema modification',
          all(len(r) == 2 and r[1].startswith(PREFIX) for r in gchanges),
          {'scope': PREFIX, 'all_42_paths_under_research_documentation': True,
           'research_captured_replayers_are_evidence_not_product_code': [r[1] for r in gchanges if r[1].endswith('.py')]})
    preserved = []
    mismatch = []
    for status, path in gchanges:
        gb = blob(G, path)
        mb = blob(MERGE, path)
        row = {'status': status, 'path': path, 'G_ref': G, 'merge_ref': MERGE,
               'G_blob': git('rev-parse', G + ':' + path).decode().strip(),
               'merge_blob': git('rev-parse', MERGE + ':' + path).decode().strip(),
               'G_content': digest(gb), 'merge_content': digest(mb), 'full_bytes_equal': gb == mb}
        if gb != mb:
            mismatch.append(path)
        # Full contents are consumed. JSON/XML syntax and references are reviewed without executing replayers.
        if path.endswith('.json'):
            json.loads(gb)
            json.loads(mb)
            row['full_syntax_read'] = 'JSON'
        elif path.endswith('.xml'):
            ET.fromstring(gb)
            ET.fromstring(mb)
            row['full_syntax_read'] = 'XML'
        else:
            gb.decode('utf-8')
            mb.decode('utf-8')
            row['full_syntax_read'] = 'UTF-8 full input'
        preserved.append(row)
    method = PREFIX + 'closure-decisions/method-decisions.md'
    check('41 G files preserved verbatim; sole shared method file retained by section', mismatch == [method],
          {'full_equal': 41, 'shared_file': mismatch})
    gm = blob(G, method); pm = blob(PARENT, method); mm = blob(MERGE, method)
    check('Full current G C–E method sections preserved', ce_section(gm) == ce_section(mm),
          {'G_C_E': digest(ce_section(gm)), 'merge_C_E': digest(ce_section(mm))})
    check('ROOT full F method section preserved', f_section(pm) == f_section(mm),
          {'parent_F': digest(f_section(pm)), 'merge_F': digest(f_section(mm)),
           'F_anchors': re.findall(r'^### (F-M\d+) ', f_section(mm).decode(), re.M)})
    pmhead = pm[:pm.index(b'## C ')]
    mmhead = mm[:mm.index(b'## C ')]
    check('Prior ROOT shared method introduction preserved', pmhead == mmhead,
          {'parent': digest(pmhead), 'merge': digest(mmhead),
           'qualification': 'Shared introduction remains ROOT source-bound; G update is only D-M4.'})
    check('D-M4 update remains bounded/no acceptance inference',
          b'Current B120 qualification:' in ce_section(mm) and b'code acceptance and integrated replay are pending.' in ce_section(mm),
          {'qualification': 'Exact G-observed candidate factory evidence; no new formal/source/integrated acceptance.'})
    coverage = PREFIX + 'closure-decisions/coverage.json'
    cd = {r: json.loads(blob(r, coverage)) for r in [BASE, G, PARENT, MERGE]}
    changes = recursive_diff(cd[BASE], cd[G])
    idx = next(i for i,x in enumerate(cd[BASE]['findings']) if x['id'] == 'B120')
    allowed = {'acceptance_command', 'capability_state_label', 'concrete_next_task',
               'independent_oracle_after_integration', 'next_owner', 'remaining_input'}
    check('Coverage exactly six B120 next-action scalar fields',
          len(changes) == 6 and {x['path'][-1] for x in changes} == allowed and
          all(x['path'][:3] == ['findings', idx, 'selected_plan_not_executed'] for x in changes),
          {'B120_index': idx, 'complete_recursive_changes': changes})
    for r in [BASE, G, PARENT, MERGE]:
        b120 = cd[r]['findings'][idx]
        check('B120 original criteria and formal status preserved ' + r[:8],
              b120['criterion_refs'] == cd[BASE]['findings'][idx]['criterion_refs'] and
              b120['closure_now'] == 'not_adjudicated',
              {'ref': r, 'criterion_refs': b120['criterion_refs'], 'closure_now': b120['closure_now']})
    owners_path = PREFIX + 'execution-organization/finding-owners.tsv'
    owners = list(csv.DictReader(io.StringIO(blob(MERGE, owners_path).decode()), delimiter='\t'))
    fid = sorted(x['finding_id'] for x in owners if x['unit'] == 'F')
    fs = {r: [x for x in cd[r]['findings'] if x['unit'] == 'F'] for r in cd}
    fbs = {r: [x for x in cd[r]['bundles'] if x['unit'] == 'F'] for r in cd}
    check('All F35 original rows /36 criterion occurrences /17 bundles unchanged',
          len(fid) == 35 and all(sorted(x['id'] for x in fs[r]) == fid for r in cd) and
          all(fs[r] == fs[BASE] and fbs[r] == fbs[BASE] for r in cd) and
          sum(len(x['criterion_refs']) for x in fs[MERGE]) == 36 and len(fbs[MERGE]) == 17,
          {'ids': fid, 'finding_count': 35, 'criterion_occurrences': 36, 'bundle_count': 17,
           'full_F_findings_canonical_JSON': {r: jdigest(fs[r]) for r in cd},
           'full_F_bundles_canonical_JSON': {r: jdigest(fbs[r]) for r in cd}})
    check('All coverage outside B120 row unchanged',
          [x for x in cd[BASE]['findings'] if x['id'] != 'B120'] == [x for x in cd[G]['findings'] if x['id'] != 'B120'],
          {'non_B120_findings': len(cd[BASE]['findings']) - 1})
    protected_paths = [PREFIX + 'closure-decisions/F.md', PREFIX + 'closure-decisions/runtime-profiles.md',
        owners_path, PREFIX + 'execution-organization/bundle-owners.tsv',
        PREFIX + 'implementation-handoffs/F/continuation-transfer-20261007/index.json',
        PREFIX + 'implementation-handoffs/F/continuation-transfer-20261007/G-source-integration-order.json',
        PREFIX + 'implementation-handoffs/F/continuation-closeout-20261007.json',
        PREFIX + 'implementation-handoffs/F/continuation-closeout-reviewed-20261007.json']
    protected_paths += [PREFIX + 'implementation-handoffs/F/continuation-transfer-20261007/per-ID/' + x + '.json' for x in fid]
    protected = []
    for path in protected_paths:
        pblob = git('rev-parse', PARENT + ':' + path).decode().strip()
        mblob = git('rev-parse', MERGE + ':' + path).decode().strip()
        protected.append({'path': path, 'parent_git_blob': pblob, 'merge_git_blob': mblob, 'unchanged': pblob == mblob})
    check('All43 selected current F ledger/primary/per-ID inputs unchanged',
          len(protected) == 43 and all(x['unchanged'] for x in protected),
          {'selected_inputs': protected, 'no_companion_body_redecode': True})
    fdoc = blob(MERGE, PREFIX + 'closure-decisions/F.md').decode()
    check('F33 closed bounded /2 limited original recommendations retained',
          '33' in fdoc and 'B214' in fdoc and 'B56' in fdoc,
          {'binding': digest(fdoc.encode()), 'qualification': 'Byte identity above is the deciding preservation check; no new adjudication.'})
    dpre = PREFIX + 'integration/checks/2026-10-07-eleventh-wave/D-budget/'
    receipt = json.loads(blob(G, dpre + 'receipt-attempt-02.json'))
    final_receipt = json.loads(blob(G, dpre + 'final-receipt.json'))
    xml_bytes = blob(G, dpre + 'owner-budget-factory.attempt-02.junit.xml')
    suites = ET.fromstring(xml_bytes).findall('testsuite')
    reported = {k: sum(int(s.attrib[k]) for s in suites) for k in ['tests','failures','errors','skipped']}
    check('Reported G exact-D680 ten-case run is internally consistent',
          reported == {'tests': 10, 'failures': 0, 'errors': 0, 'skipped': 0} and
          receipt['junit']['tests'] == 10 and receipt['test_outcome'] == 'PASS' and
          receipt['candidate_sha'] == final_receipt['candidate']['commit'] == '68070854bddba2593efaef59a107a3cbe3b08d4d' and
          digest(blob(G, dpre + 'pytest.attempt-02.stdout.txt')) == {k:receipt['stdout'][k] for k in ['bytes','sha256']} and
          digest(blob(G, dpre + 'pytest.attempt-02.stderr.txt')) == {k:receipt['stderr'][k] for k in ['bytes','sha256']},
          {'reported_observation_not_fresh_reviewer_execution': reported, 'actual_candidate_sha': receipt['candidate_sha'],
           'actual_candidate_tree': receipt['candidate_tree'], 'junit_content': digest(xml_bytes),
           'first_attempt_reported': final_receipt['attempt_01']['pytest_collection'],
           'fresh_scientific_execution_by_this_reviewer': 'UNRUN'})
    # This merge review must not silently claim custody of another owner's unfetched implementation.
    dprobe = subprocess.run(['git', 'cat-file', '-e', receipt['candidate_sha'] + '^{commit}'], cwd=REPO, capture_output=True)
    (outdir/'D680-local-source-probe.stdout').write_bytes(dprobe.stdout)
    (outdir/'D680-local-source-probe.stderr').write_bytes(dprobe.stderr)
    COMMANDS.append({'argv':['git','cat-file','-e',receipt['candidate_sha']+'^{commit}'],
                     'cwd':str(REPO),'returncode':dprobe.returncode,
                     'stdout':digest(dprobe.stdout),'stderr':digest(dprobe.stderr)})
    dsource = {'check':'UNRUN', 'candidate':final_receipt['candidate'],
               'source_binding_locally_available':False,'probe_exit':dprobe.returncode,
               'reason':'D680 original implementation is not present in this cloud Git object store; no fetch or source reconstruction in this metadata-only review.',
               'reported_G_JUnit_observation_separate':True,'probe_stderr':dprobe.stderr.decode()}
    if dprobe.returncode == 0:
        actual = digest(blob(receipt['candidate_sha'], final_receipt['candidate']['implementation_test_path']))
        dsource.update(check='PASS' if actual['sha256']==final_receipt['candidate']['test_sha256'] else 'FAIL',
                       source_binding_locally_available=True,actual_source_content=actual)
    elif dprobe.returncode != 128:
        raise RuntimeError('Unexpected D680 source probe status: '+str(dprobe.returncode))
    # Existing observed whitespace is retained as an actual independent diff-check FAIL.
    white = subprocess.run(['git', 'diff', '--check', PARENT, MERGE], cwd=REPO, capture_output=True)
    (outdir / 'actual-merge-diff-check.stdout').write_bytes(white.stdout)
    (outdir / 'actual-merge-diff-check.stderr').write_bytes(white.stderr)
    COMMANDS.append({'argv':['git','diff','--check',PARENT,MERGE], 'cwd':str(REPO), 'returncode':white.returncode,
                     'stdout':digest(white.stdout),'stderr':digest(white.stderr)})
    expected_whitespace_path = dpre + 'pytest.attempt-02.stdout.txt'
    check('Full observed diff-check failure retained without source attribution',
          white.returncode == 2 and white.stderr == b'' and white.stdout.decode().count('trailing whitespace.') == 2 and
          all(line.startswith(expected_whitespace_path + ':') for line in white.stdout.decode().splitlines() if 'trailing whitespace.' in line),
          {'diff_check': 'FAIL', 'exit_code': white.returncode, 'full_stdout': white.stdout.decode(),
           'output_path': str(outdir/'actual-merge-diff-check.stdout'), 'P41': 'not_established',
           'category': 'raw deciding G pytest stdout whitespace; bytes preserved; no runtime defect inferred'})
    full_patch = git('diff', '--binary', '--full-index', PARENT, MERGE)
    (outdir / 'actual-merge-full-binary.patch').write_bytes(full_patch)
    check('Complete actual merge patch retained',
          full_patch.count(b'diff --git ') == 42,
          {'path':str(outdir/'actual-merge-full-binary.patch'), **digest(full_patch), 'path_sections':42})
    end = command(['git', 'status', '--porcelain=v1'], cwd=OWN)
    ownend = command(['git','show','-s','--format=%H %T','HEAD'], cwd=OWN).decode().strip()
    check('Own admitted lane unchanged/read-only after', end == begin and ownend == ownid,
          {'before':ownid,'after':ownend,'porcelain':end.decode()})
    report = {
        'schema':'policyos.e02.independent-G-document-merge-review.v1', 'reviewer':'graph_scm',
        'check':'PASS', 'outcome':'GO_BOUNDED',
        'scope':'Read-only actual G855→83e document/checkpoint delta and ROOT92→ea9a merge preservation. No C/D/E algorithm, scientific acceptance, formal closure or full result-pack revalidation.',
        'actual_merge':{'sha':MERGE,'tree':TREE,'parents':[PARENT,G]},
        'G_source':{'sha':G,'tree':GTREE,'parent':BASE},
        'product_source_not_relabelled':'519e4822f608cbe4e7ac1ee7b01f6c29cb84bc82',
        'checks':CHECKS, 'changed_path_manifest':preserved, 'coverage_recursive_diff':changes,
        'protected_current_F_inputs':protected, 'root_merge_capture':root_capture,
        'other_owner_source_custody_observation':dsource,
        'preserved_first_observer_ERROR':{'path':str(outdir/'independent-review.stderr'), 'classification':'ERROR; undeclared local D680 source ref was unavailable; no deciding D-source PASS asserted'},
        'quality':{'actual_whole_merge_diff_check':'FAIL','P41':'not_established','new_product_delta':0,
                   'scientific_execution_by_reviewer':'UNRUN','C_D_E_formal_source_acceptance':'UNRUN'},
        'semantic_review':[
            'G B120 qualification restores original measured-owner budget criterion scope; universal deployment invoice truth is a separate claim. Criterion bytes/status remain unchanged.',
            'D68010PASS is a reported source-bound G execution with 833 declared candidate origins. First missing-TOML6FAIL is preserved as harness history. This review binds committed JUnit/outputs, not the uncommitted2926-source inventory or a new execution.',
            'C54/D45/B/E continuation recommendations retain explicit source/profile limitations, historical failures and G acceptance boundaries. No authority or all-backend inference is added by the document merge.',
            'Storage/nativeTrash documents are copied from G without performing cleanup or inferring physical disk recovery.',
            '41 whole G file bodies, full G C–E method sections, prior ROOT F method section and all35F/36card/17bundle coverage records are preserved.'
        ],
        'limitations':[
            'No new numerical/backend/production or installed run. Optional exclusions, scientific residuals and formal G acceptance remain those of their exact existing receipts.',
            'Original D680 source custody is UNRUN locally: its commit is unavailable in this cloud object store. First strict source probe ERROR remains preserved; current reported-G receipt consistency does not assert source custody.',
            'No re-decoding233MB of prior F custody artifacts and no7k-blob union replay: this incremental42-path delta does not touch those inputs.',
            'Actual diff-check exit2/two raw D stdout trailing whitespace records remain FAIL; no inherited-red/P41 attribution.',
            'Metadata/delta preservation GO does not independently approve D/C/E implementation claims or finding closures.'
        ],
        'commands':COMMANDS,
    }
    (outdir/'actual-ea9a-review.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    summary = {'check':'PASS','outcome':'GO_BOUNDED','actual_merge':MERGE,'G_delta_paths':42,
               'G_whole_blob_equal':41,'shared_method_C_E_equal':True,'ROOT_F_method_equal':True,
               'F_findings_unchanged':35,'criterion_occurrences_unchanged':36,'F_bundles_unchanged':17,
               'protected_F_inputs':43,'coverage_changed_fields':6,'new_product_delta':0,
               'actual_diff_check':'FAIL','P41':'not_established','fresh_science':'UNRUN',
               'report':str(outdir/'actual-ea9a-review.json')}
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__ == '__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--outdir',required=True);a=ap.parse_args()
    out=pathlib.Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
    run(out)
