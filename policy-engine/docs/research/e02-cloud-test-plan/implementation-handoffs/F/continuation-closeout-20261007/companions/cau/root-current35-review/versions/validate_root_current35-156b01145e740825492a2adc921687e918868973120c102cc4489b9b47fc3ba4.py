"""Read-only source/card/full-output validator for the ROOT F35 Git packet.

No scientific execution, mutation, checkout or formal authority. Explicit current
per-ID records are followed in full; an index caption is never the evidence body.
"""
from __future__ import annotations
import argparse
import collections
import copy
import csv
import gzip
import hashlib
import io
import json
import lzma
import pathlib
import platform
import subprocess
import sys
import time

BASE = '198076863e143dea9f89f02734b13d50dae3eed5'
P = 'policy-engine/docs/research/e02-cloud-test-plan/'
PACK = P + 'implementation-handoffs/F/continuation-transfer-20261007/'
REQUIRED_CURRENT = {
    ('605dadeb76499c3f6eadd95e16a8df1bbb2cb89f', P+'implementation-handoffs/F/api-installed-graph-reconciliation-20261007.json'),
    ('e04ddf884071b17ffb1d021c9a6b23f826d76774', P+'implementation-handoffs/F/tmle-persisted-consumers-20261007.json'),
    ('fa53da2812eaa8578f79ec914b3b2abe4c491f3d', P+'implementation-handoffs/F/economic-baseline-consumer-proof-20261007.json'),
    ('0552bd338dad23b2eabb0d22a1c7c4eb4bcd61d6', P+'implementation-handoffs/F/foundry-consumer-input-review-20261007.json'),
    ('370cac5c342bbc5b206331f93776505e0cffe3a6', P+'implementation-handoffs/F/graph-intake-current-content-20261007.json'),
    ('4d8eaec43d09d9c7df3a2ac8bd244e4d132d03f9', P+'implementation-handoffs/F/original35-independent-criterion-review-20261007.json'),
}

def sha(data): return hashlib.sha256(data).hexdigest()
def pointer(value, p):
    for k in p.strip('/').split('/') if p.strip('/') else []:
        k = k.replace('~1', '/').replace('~0', '~')
        value = value[int(k)] if isinstance(value, list) else value[k]
    return value
def decode(raw, encoding):
    if encoding in (None, 'identity', 'raw', 'verbatim', 'utf8'): return raw
    if encoding in ('gzip', 'gzip-lossless'): return gzip.decompress(raw)
    if encoding in ('xz', 'xz-lossless'): return lzma.decompress(raw)
    if encoding in ('json-escaped-utf8', 'utf8-json-string', 'json-string-utf8', 'json-escaped-utf8-lossless'):
        return json.loads(raw).encode('utf8')
    if encoding in ('json-wrapped-utf8', 'json-lossless-utf8'):
        return json.loads(raw)['raw_utf8'].encode('utf8')
    if encoding == 'lossless_utf8_json':
        wrapped = json.loads(raw)
        assert wrapped['encoding'] == 'lossless_utf8'
        value = wrapped['text'].encode('utf8')
        assert len(value) == wrapped['decoded_bytes'] and sha(value) == wrapped['decoded_sha256']
        return value
    raise AssertionError('unsupported explicit encoding: ' + str(encoding))

class Validator:
    def __init__(self, repo, target):
        self.repo, self.target = repo, target
        self.cache, self.artifacts, self.decoded, self.receipts = {}, {}, {}, set()
        self.check_refs, self.pointers, self.missing_nondeciding = set(), [], []
        self.document_inputs = []

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.repo, stderr=subprocess.PIPE)

    def raw(self, ref, path):
        key = (ref, path)
        if key not in self.cache: self.cache[key] = self.git('show', ref + ':' + path)
        return self.cache[key]

    def tree(self, ref): return self.git('rev-parse', ref + '^{tree}').decode().strip()

    def ref(self, record, default=None):
        ref = record.get('git_ref', record.get('artifact_git_ref', record.get('head', record.get('git_sha', default))))
        path = record.get('path', record.get('receipt_path'))
        assert ref and path, 'explicit artifact carrier/path absent'
        raw = self.raw(ref, path)
        n, h = record.get('bytes', record.get('receipt_bytes')), record.get('sha256', record.get('receipt_sha256'))
        assert n is not None and h is not None, 'explicit size/hash absent: ' + path
        assert len(raw) == n and sha(raw) == h, 'artifact bytes/hash: ' + path
        blob = record.get('git_blob', record.get('blob'))
        if blob: assert self.git('rev-parse', ref + ':' + path).decode().strip() == blob, 'artifact Git blob: ' + path
        if record.get('tree'): assert self.tree(ref) == record['tree'], 'artifact carrier tree: ' + path
        self.artifacts[(ref, path)] = {'git_ref': ref, 'path': path, 'bytes': len(raw), 'sha256': sha(raw)}
        decoded_n = record.get('decoded_bytes', record.get('raw_bytes'))
        decoded_h = record.get('decoded_sha256', record.get('raw_sha256'))
        if decoded_n is not None or decoded_h is not None:
            assert decoded_n is not None and decoded_h is not None
            value = decode(raw, record.get('encoding'))
            assert len(value) == decoded_n and sha(value) == decoded_h, 'decoded bytes/hash: ' + path
            self.decoded[(ref, path)] = {'git_ref': ref, 'path': path, 'decoded_bytes': len(value), 'decoded_sha256': sha(value), 'encoding': record.get('encoding')}
        return raw

    def obj(self, record, default=None):
        raw = self.ref(record, default)
        if raw.startswith(b'\x1f\x8b'): raw = gzip.decompress(raw)
        elif raw.startswith(b'\xfd7zXZ\x00'): raw = lzma.decompress(raw)
        return json.loads(raw)

    def verify_declared_artifact_walk(self, value, carrier):
        if isinstance(value, dict):
            path = value.get('path', value.get('receipt_path'))
            if path and isinstance(path, str) and path.startswith(P + 'implementation-handoffs/') and any(k in value for k in ('bytes', 'receipt_bytes')) and any(k in value for k in ('sha256', 'receipt_sha256')):
                self.ref(value, carrier)
            for item in value.values(): self.verify_declared_artifact_walk(item, carrier)
        elif isinstance(value, list):
            for item in value: self.verify_declared_artifact_walk(item, carrier)

    def owner_outputs(self, spec):
        obj = self.obj(spec)
        carrier = spec['git_ref']
        self.receipts.add((carrier, spec['path']))
        self.verify_declared_artifact_walk(obj, carrier)
        # Manifest paths are actual committed owner declarations, not summaries.
        candidates = set()
        if obj.get('full_output_manifest'): candidates.add(obj['full_output_manifest']['path'])
        for path in obj.get('mandatory_companions', []) + obj.get('changed_paths', []):
            if isinstance(path, str) and path.endswith(('/outputs.json', '/full-output-manifest.json')): candidates.add(path)
        for path in candidates:
            raw = self.raw(carrier, path)
            manifest = json.loads(raw)
            self.artifacts[(carrier, path)] = {'git_ref': carrier, 'path': path, 'bytes': len(raw), 'sha256': sha(raw), 'binding': 'complete immutable owner commit/declaration, with explicit external hash when declared'}
            self.verify_declared_artifact_walk(manifest, carrier)

    def expand_rows(self, index):
        if not index.get('per_ID_complete_records'): return index['rows']
        records = index['per_ID_complete_records']
        assert len(records) == 35 and len({r['finding_id'] for r in records}) == 35, 'per-ID denominator'
        rows = [self.obj(record, self.target) for record in records]
        summaries = {r['finding_id']: r for r in index['rows']}
        assert len(summaries) == 35
        for row in rows:
            summary = summaries[row['finding_id']]
            for k, value in summary.items():
                if k != 'full_record_ref': assert row.get(k) == value, 'index summary differs from complete per-ID: ' + row['finding_id'] + ':' + k
        return rows

    def verify_rows(self, index, rows):
        owners_raw = self.raw(BASE, P + 'execution-organization/finding-owners.tsv')
        bundles_raw = self.raw(BASE, P + 'execution-organization/bundle-owners.tsv')
        all_owners = list(csv.DictReader(io.StringIO(owners_raw.decode()), delimiter='\t'))
        all_bundles = list(csv.DictReader(io.StringIO(bundles_raw.decode()), delimiter='\t'))
        owners = {r['finding_id']: r for r in all_owners if r['unit'] == 'F'}
        bundles = {r['bundle_id']: r for r in all_bundles if r['unit'] == 'F'}
        assert len(all_owners) == 282 and len(all_bundles) == 127 and len(bundles) == 17
        ids = [r['finding_id'] for r in rows]
        assert len(ids) == len(set(ids)) == 35 and set(ids) == set(owners), 'original35 ID denominator'
        assert sum(len(r['original_card_refs']) for r in rows) == 36, 'original36 binding denominator'
        assert {r['primary_bundle'] for r in rows} == set(bundles), 'original17 bundle denominator'
        assert index['formal_G_acceptance'] is False
        for row in rows:
            fid = row['finding_id']
            assert row['primary_owner_from_full_TSV'] == owners[fid], 'TSV owner: ' + fid
            assert row['primary_bundle'] == owners[fid]['source_closure_owner']
            assert row['bundle_owner_from_full_TSV'] == bundles[row['primary_bundle']]
            assert len(row['original_card_refs']) == (2 if fid == 'LA-016' else 1)
            for binding in row['original_card_refs']:
                doc = self.raw(binding['source_sha'], binding['source_path'])
                lo, hi = binding['lines']; block = b''.join(doc.splitlines(keepends=True)[lo-1:hi])
                assert len(block) == binding['bytes'] and sha(block) == binding['sha256'], 'original card bytes: ' + fid
                assert row['original_text'] == block.decode(), 'complete original text: ' + fid
                assert block.decode().startswith(binding['title'] + '\n') and binding['title'].startswith('## ' + fid + '. ')
                assert binding['criterion_id'] == fid
                assert self.git('rev-parse', binding['source_sha'] + ':' + binding['source_path']).decode().strip() == binding['document_git_blob']
            sci = row['scientific_implementation']
            assert self.tree(sci['sha']) == sci['tree'], 'scientific source/tree: ' + fid
            assert row['code_sha'] == sci['sha'] and row['code_tree'] == sci['tree']
            assert row['root_assembled_source']['sha'] == index['product_source']['sha'] and row['root_assembled_source']['tree'] == index['product_source']['tree']
            assert row['root_assembled_source']['not_new_numerical_proof'] is True
            assert row['check_result'] in {'PASS','FAIL','ERROR','SKIP','UNRUN'} and row['F_finding_outcome'] in {'closed','limited','held','open'}
            assert row['F_finding_outcome'] != 'open'
            if row['F_finding_outcome'] == 'closed': assert row['check_result'] == 'PASS'
            assert row['G_finding_acceptance'] == {'status':'not_issued','formal_G_closed':False}
            for field in ['primary_acceptance_scope','F_rationale','consumer','oracle_and_negative','surface']: assert row[field], fid + ':missing ' + field
            assert set(row['source_chain']) == {'producer','artifact','bridge','consumer'}
            if fid in ('B214','B56'): assert row['original_missing_input'] and row['original_next_owner'] and row['F_finding_outcome'] == 'limited'
            else: assert row['original_missing_input'] is None and row['original_next_owner'] is None, fid + ':extra original prerequisite'
            for ref in row['deciding_receipt_refs']:
                value = self.obj(ref)
                self.receipts.add((ref['git_ref'],ref['path']))
                if ref.get('json_pointer'):
                    pointer(value, ref['json_pointer']);self.pointers.append({'finding_id':fid,'git_ref':ref['git_ref'],'path':ref['path'],'pointer':ref['json_pointer']})
            self.ref(row['deciding_per_ID_carrier_ref'])
            for text in row['complete_raw_receipt_checks_refs']:
                location, p = text.split('#',1); carrier, path = location.split(':',1)
                value = json.loads(self.raw(carrier,path));pointer(value,p);self.check_refs.add(text)
        assert dict(collections.Counter(r['F_finding_outcome'] for r in rows)) == index['summary']['F_original_finding_recommendation'] == {'closed':33,'limited':2}
        assert dict(collections.Counter(r['check_result'] for r in rows)) == index['summary']['check_results'] == {'PASS':34,'UNRUN':1}
        assert index['summary']['formal_G_closures'] == 0
        assert next(r for r in rows if r['finding_id']=='B56')['check_result'] == 'UNRUN'

    def validate(self, index, audit, overrides=None):
        rows = overrides if overrides is not None else self.expand_rows(index)
        self.verify_rows(index, rows)
        assert self.tree(index['product_source']['sha']) == index['product_source']['tree'], 'assembled product tree'
        assert self.tree(index['slice_base_sha']) == index['slice_base_tree'], 'slice-base tree'
        for k in ['product_source','G_checkpoint','denominator','summary','current_receipt_registry','prior_full_deciding_registry','independent_original35_review','formal_G_acceptance']:
            assert index[k] == audit[k], 'index/audit field: ' + k
        current = {(r['git_ref'],r['path']) for r in index['current_receipt_registry']}
        assert REQUIRED_CURRENT <= current, 'independently selected required current receipt omitted'
        assert len(current) == len(index['current_receipt_registry']), 'duplicate current receipt'
        if audit['rows'] and 'path' in audit['rows'][0]:
            assert audit['rows'] == index['per_ID_complete_records'], 'audit/index per-ID ref bijection'
            for ref in audit['rows']: self.ref(ref,self.target)
        else: assert audit['rows'] == rows
        for spec in index['current_receipt_registry']: self.owner_outputs(spec)
        prior = self.obj(index['prior_full_deciding_registry']['ref'])
        for p in index['prior_full_deciding_registry']['pointers']: pointer(prior,p)
        assert prior['historical_non_deciding_reference_check'] == 'UNRUN' and prior['all_reference_custody_check'] == 'UNRUN'
        # This denominator claim belongs to the old INDEX, not the AUDIT schema.
        independent = index['independent_original35_review']
        self.ref(independent['receipt']); compressed = self.ref(independent['packet']); raw = gzip.decompress(compressed)
        assert len(raw)==independent['decoded_bytes'] and sha(raw)==independent['decoded_sha256']
        original = json.loads(raw)
        prior_index = self.obj(original['source']['ROOT072_index'])
        assert prior_index['zero_finding_deciding_dependence_on_missing_historical175c_and_lint_raw'] is True
        checks = prior['complete_component_checks']
        if isinstance(audit['complete_old_component_checks'],dict):
            item = audit['complete_old_component_checks']; source = self.obj(item['ref'])
            assert pointer(source,item['json_pointer']) == checks and len(checks) == item['records']
        else: assert audit['complete_old_component_checks'] == checks
        for check in checks:
            spec = check['receipt_ref']; value = self.obj(spec)
            assert pointer(value,check['json_pointer']) == check['complete_actual_check'], 'full historical check differs from immutable owner: ' + spec['path'] + '#' + check['json_pointer']
            for ref in check['verified_complete_output_refs']: self.ref(ref)
            if not check['verified_complete_output_refs']:
                assert check['output_custody_check'] == 'UNRUN'
                self.missing_nondeciding.append({'receipt':spec,'pointer':check['json_pointer'],'check':check['output_custody_check'],'reason':check.get('output_custody_reason'),'role':'No full raw declared, never promoted to a new raw measurement witness'})
        assert original['original_recommendation_counts'] == index['summary']['F_original_finding_recommendation']
        for row in rows:
            earlier = next(r for r in original['rows'] if r['finding_id'] == row['finding_id'])
            assert row['original_card_refs'] == earlier['original_card_refs'] and row['original_text'] == earlier['original_text']
        return rows


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',required=True);parser.add_argument('--target',required=True);parser.add_argument('--output',required=True);parser.add_argument('--negative-controls',action='store_true')
    args=parser.parse_args(); start=time.monotonic();v=Validator(args.repo,args.target)
    index_raw=v.raw(args.target,PACK+'index.json'); audit_raw=v.raw(args.target,PACK+'full-audit.json')
    index,audit=json.loads(index_raw),json.loads(audit_raw);issues=[];negatives=[];rows=[]
    try: rows=v.validate(index,audit)
    except (AssertionError,KeyError,ValueError,TypeError,IndexError,subprocess.CalledProcessError) as error: issues.append(str(error) or type(error).__name__)
    if not issues and args.negative_controls:
        controls=[('remove-original-binding',lambda rs:rs[0]['original_card_refs'].clear()),('wrong-card-hash',lambda rs:rs[0]['original_card_refs'][0].update(sha256='0'*64)),('missing-ID',lambda rs:rs.pop()),('wrong-source-tree',lambda rs:rs[0]['scientific_implementation'].update(tree='0'*40)),('wrong-owner',lambda rs:rs[0]['primary_owner_from_full_TSV'].update(source_closure_owner='CAU-03'))]
        for name,mutate in controls:
            changed=copy.deepcopy(rows);mutate(changed)
            try:v.verify_rows(index,changed);negatives.append({'control':name,'validator_check':'PASS','harness_check':'FAIL'})
            except (AssertionError,KeyError,ValueError,TypeError,IndexError,subprocess.CalledProcessError) as error:negatives.append({'control':name,'validator_check':'FAIL','harness_check':'PASS','reason':str(error) or type(error).__name__})
        if index.get('per_ID_complete_records'):
            changed=copy.deepcopy(index);changed['per_ID_complete_records'][0]['sha256']='0'*64
            try:v.expand_rows(changed);negatives.append({'control':'stale-per-ID-hash','validator_check':'PASS','harness_check':'FAIL'})
            except (AssertionError,KeyError,ValueError,TypeError,IndexError,subprocess.CalledProcessError) as error:negatives.append({'control':'stale-per-ID-hash','validator_check':'FAIL','harness_check':'PASS','reason':str(error) or type(error).__name__})
    result={'schema':'F-root-current35-independent-metadata-review/v1','check':'FAIL' if issues or any(n['harness_check']=='FAIL' for n in negatives) else 'PASS','target':{'sha':args.target,'tree':v.tree(args.target)},'product_source':index['product_source'],'inputs':{'index':{'path':PACK+'index.json','bytes':len(index_raw),'sha256':sha(index_raw)},'audit':{'path':PACK+'full-audit.json','bytes':len(audit_raw),'sha256':sha(audit_raw)},'replayer':{'path':__file__,'bytes':pathlib.Path(__file__).stat().st_size,'sha256':sha(pathlib.Path(__file__).read_bytes())}},'environment':{'python':platform.python_version(),'executable':sys.executable,'purpose':'stdlib immutable Git metadata/full-output verifier; no product backend'},'denominator':{'IDs':35,'bundles':17,'original_bindings':36},'recommendations':index['summary'],'issues':issues,'negative_controls':negatives,'complete_deciding_check_pointer_count':len(v.check_refs),'full_deciding_pointers':v.pointers,'verified_artifacts':list(v.artifacts.values()),'verified_decoded_artifacts':list(v.decoded.values()),'missing_full_nondeciding_outputs_preserved':v.missing_nondeciding,'scope':'Independent ROOT ledger/card/caption/material reconciliation; no numerical rerun or G closure; old source-specific raw outcomes retained. Semantic caption review is separately recorded.','historical175c4_custody':'UNRUN/nondeciding','P41':'not_established','elapsed_s':time.monotonic()-start}
    pathlib.Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['check','target','denominator','issues','negative_controls','complete_deciding_check_pointer_count','elapsed_s']},ensure_ascii=False,indent=2));print(json.dumps({'verified_artifacts':len(v.artifacts),'decoded_artifacts':len(v.decoded),'historical_output_custody_UNRUN':len(v.missing_nondeciding),'output':args.output}))
    return int(result['check']!='PASS')
if __name__=='__main__':raise SystemExit(main())
