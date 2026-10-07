#!/usr/bin/env python3
"""Independent immutable original35 metadata delta review; no scientific rerun.

Retains the earlier full material audit as source-bound evidence, verifies every
current original row/owner/card/source/pointer and ten primary references, but
does not rewalk unchanged raw scientific outputs or recreate author tests.
"""
import argparse
import collections
import copy
import hashlib
import importlib.util
import json
import pathlib
import platform
import subprocess
import sys
import time

PREFIX = 'policy-engine/docs/research/e02-cloud-test-plan/'
PACK = PREFIX + 'implementation-handoffs/F/continuation-transfer-20261007/'
BASELINE = 'd8334672f44d24dd32113264f96ca3f7954dace4'
PRODUCT = '519e4822f608cbe4e7ac1ee7b01f6c29cb84bc82'
PRODUCT_TREE = '750d28da94f372848fe6b2db5f88db95b94cb57d'
G_SHA = '855cb26a7a2c9fea60356663cf81e7d01e20c738'
OLDER_VALIDATOR = pathlib.Path('/tmp/e02-F-continuation-20261007/cau/root-current35-review/validate_root_current35.py')
EXPECTED = pathlib.Path('/tmp/e02-F-continuation-20261007/cau/ledger-recovery-review/expected-original35-compact.json')
PATCH = pathlib.Path('/tmp/e02-F-continuation-20261007/root-recovery/current35-implementation-full.patch')
REQUIRED_NEW = {
    'Installed-b5-failed': 'c22786dfce8308bb7d48a177ccb1b109843262b5',
    'Catalog-resource': 'ffae9fa4b45c23c3d2dca5c1bbf78d18418a7634',
    'Installed-resource-forward': 'de197363d4ba8a86b0e8c2fa0ff31c2858643d1c',
    'Installed-recovered-fresh-child': 'c4ddc4bcbddc2a7526f541d51196b176e4311362',
}

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def bind(path):
    raw = pathlib.Path(path).read_bytes()
    return {'path': str(path), 'bytes': len(raw), 'sha256': sha(raw)}

def load_prior_validator():
    spec = importlib.util.spec_from_file_location('prior_current35_validator', OLDER_VALIDATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def pointer(obj, path):
    for token in path.removeprefix('/').split('/'):
        token = token.replace('~1', '/').replace('~0', '~')
        obj = obj[int(token)] if isinstance(obj, list) else obj[token]
    return obj

def compare_json(before, after, path=''):
    """Complete changed JSON leaves; no ranking/selection or length truncation."""
    if isinstance(before, dict) and isinstance(after, dict):
        out = []
        for key in sorted(set(before) | set(after)):
            where = path + '/' + key.replace('~', '~0').replace('/', '~1')
            if key not in before:
                out.append({'pointer': where, 'operation': 'added', 'after': after[key]})
            elif key not in after:
                out.append({'pointer': where, 'operation': 'removed', 'before': before[key]})
            else:
                out += compare_json(before[key], after[key], where)
        return out
    if before != after:
        return [{'pointer': path, 'operation': 'changed', 'before': before, 'after': after}]
    return []

class Review:
    def __init__(self, repo, target):
        self.module = load_prior_validator()
        self.v = self.module.Validator(repo, target)
        self.repo, self.target = repo, target
        self.footprints, self.registry_observations, self.row_observations = [], [], []

    def git(self, *args):
        return self.v.git(*args)

    def raw(self, path, ref=None):
        return self.v.raw(ref or self.target, path)

    def obj(self, path, ref=None):
        return json.loads(self.raw(path, ref))

    def rows(self, index):
        return self.v.expand_rows(index)

    def verify_rows(self, index, rows):
        self.v.verify_rows(index, rows)
        expected = json.loads(EXPECTED.read_bytes())
        oracle = {r['finding_id']: r for r in expected['rows']}
        assert len(oracle) == 35
        for row in rows:
            fid = row['finding_id']
            wanted = oracle[fid]
            assert row['check_result'] == wanted['expected_original_check'], fid + ':original check differs from independent criterion'
            assert row['F_finding_outcome'] == wanted['proposed_F_original_recommendation'], fid + ':F recommendation differs from criterion'
            assert row['F_technical_recommendation'] == wanted['proposed_original_technical_lens'], fid + ':technical-original lens differs from criterion'
            old = self.v.obj(wanted['original_norm_text_ref'])
            for key in ['original_card_refs', 'original_text', 'primary_owner_from_full_TSV', 'bundle_owner_from_full_TSV', 'scientific_implementation', 'complete_raw_receipt_checks_refs', 'deciding_receipt_refs']:
                assert row[key] == old[key], fid + ':changed original/deciding scientific binding:' + key
            assert row['original_missing_input'] == old['original_missing_input'], fid + ':changed original prerequisite'
            self.row_observations.append({
                'finding_id': fid,
                'check': row['check_result'], 'F_original': row['F_finding_outcome'],
                'technical_original': row['F_technical_recommendation'],
                'G_formal': row['G_finding_acceptance'],
                'code_acceptance': row['G_code_acceptance'],
                'source': row['scientific_implementation'],
                'original_card_bindings': len(row['original_card_refs']),
                'oracle_rationale': wanted['expected_rationale'],
                'current_rationale': row['F_rationale'],
                'missing_original': row['original_missing_input'],
                'predicate_basis': 'independently_reconciled to immutable original card/TSV and prior complete receipt pointers; no new estimator run',
            })
        technical = dict(collections.Counter(r['F_technical_recommendation'] for r in rows))
        assert technical == {'closed': 33, 'limited': 2} == index['summary']['F_bounded_technical_recommendation'], 'technical lens denominator'
        assert index['summary']['historical_ROOT072'] == {
            'finding': {'closed':25,'limited':9,'held':1},
            'technical': {'closed':30,'limited':4,'held':1},
            'checks': {'PASS':33,'UNRUN':2},
        }, 'historical072 restamped'

    def verify_metadata(self, index, audit, rows):
        self.verify_rows(index, rows)
        for key in set(index) & set(audit) - {'role', 'rows'}:
            assert index[key] == audit[key], 'index/audit projection:' + key
        assert audit['rows'] == index['per_ID_complete_records'], 'full audit/per-ID bijection'
        assert index['denominator'] == {'IDs':35,'bundles':17,'original_bindings':36,'unique_original_blocks':35,'LA016':'Two same-card byte bindings, one ID'}
        assert index['product_source']['sha'] == PRODUCT and index['product_source']['tree'] == PRODUCT_TREE
        assert self.v.tree(PRODUCT) == PRODUCT_TREE
        assert index['assembled_consumer_ready'] is True and index['formal_G_acceptance'] is False
        assert index['G_checkpoint']['G'] == G_SHA and index['G_checkpoint']['G_tree'] == self.v.tree(G_SHA)
        assert index['reconciled_F_G_document_carrier']['not_new_method_candidate'] is True
        merge = index['G_checkpoint']['actual_F_ordinary_merge']
        assert self.git('rev-list','--parents','-n','1',merge['head']).decode().split()[1:] == merge['parents']
        assert G_SHA in merge['parents'] and self.v.tree(merge['head']) == merge['tree']
        assert index['P41']['status'] == 'not_established'
        quality = index['global_quality']
        assert quality['source519_scanner']['returncodes'] == [-9,-9]
        assert quality['source519_scanner']['first'] == quality['source519_scanner']['retry'] == 'ERROR/incomplete'
        assert quality['source519_scanner']['complete_output_absent'] is True
        assert quality['Ruff'] == 'FAIL103' and quality['public_surface'] == 'FAIL38'
        limits = ' '.join(index['runtime_limits'])
        assert all(t in limits for t in ['Python3.14','DoWhy/EconML','UNRUN','175c','non-deciding','38static UNKNOWN'])
        older = self.obj(PACK+'index.json',BASELINE)
        for key in ['prior_full_deciding_registry','independent_original35_review']:
            assert index[key] == older[key], 'old full evidence locator changed:' + key
        # Primary bytes and complete JSON selectors are checked. Raw scientific
        # output bodies remain exactly the old verified bindings, not rerun.
        registry = index['current_receipt_registry']
        assert len(registry) == len({(r['git_ref'],r['path']) for r in registry}) == 10
        lanes = {r['lane']:r for r in registry}
        assert set(lanes) == {'API','FIT','ECO','Runtime-input-review','Graph','Original35',*REQUIRED_NEW}
        for lane, head in REQUIRED_NEW.items():
            assert lanes[lane]['git_ref'] == head, 'missing required new immutable component:'+lane
        old_registry = {(r['git_ref'],r['path']):r for r in older['current_receipt_registry']}
        primaries = {}
        for entry in registry:
            obj = self.v.obj(entry)
            primaries[entry['lane']] = obj
            if entry.get('code_candidate_sha'):
                assert self.v.tree(entry['code_candidate_sha']) == entry['code_candidate_tree']
            old = old_registry.get((entry['git_ref'],entry['path']))
            if old:
                for key in ['bytes','sha256','git_blob','tree','code_candidate_sha','code_candidate_tree']:
                    assert old.get(key) == entry.get(key), 'unchanged prior primary binding:'+entry['lane']+':'+key
            manifests = [obj.get('complete_outputs_manifest')]
            transfer = obj.get('evidence_transfer',{})
            if isinstance(transfer,dict):
                manifest = transfer.get('full_output_manifest')
                if isinstance(manifest,dict):
                    raw = self.v.ref(manifest,entry['git_ref'])
                    manifests += [manifest['path']]
            for path in [p for p in manifests if p]:
                raw = self.v.raw(entry['git_ref'],path)
                doc = json.loads(raw)
                records = doc.get('records',doc.get('files',doc.get('items',doc.get('artifacts',[]))))
                assert isinstance(records,list)
                self.registry_observations.append({'lane':entry['lane'],'git_ref':entry['git_ref'],'manifest':path,'bytes':len(raw),'sha256':sha(raw),'complete_record_count':len(records),'raw_bodies_rewalked':False})
        failed = primaries['Installed-b5-failed']
        positive = primaries['Installed-resource-forward']
        recovered = primaries['Installed-recovered-fresh-child']
        assert failed['tested_source_sha'] == index['product_source']['first_installed_freeze']['sha']
        assert failed['tested_source_tree_sha'] == index['product_source']['first_installed_freeze']['tree']
        for name in ['wheel','sdist']:
            assert {k:failed['native_profile_outcomes'][name][k] for k in ['PASS','FAIL','ERROR','SKIP']} == {'PASS':130,'FAIL':32,'ERROR':0,'SKIP':0}
            assert {k:positive['native_profile_outcomes'][name][k] for k in ['PASS','FAIL','ERROR','SKIP']} == {'PASS':91,'FAIL':0,'ERROR':0,'SKIP':0}
        assert positive['tested_source_sha'] == recovered['tested_source_sha'] == PRODUCT
        assert positive['tested_source_tree_sha'] == recovered['tested_source_tree_sha'] == PRODUCT_TREE
        assert sum(c['outcome']=='FAIL' for c in positive['checks']) == 6
        assert positive['checks'][5]['outcome'] == 'ERROR', 'initial binder harness lost'
        assert positive['native_science_scope'].find('same process') >= 0
        counts = recovered['current_native_run_counts']
        assert counts['new_registered_method_jobs'] == counts['new_Node_executions'] == counts['new_fresh_I_children'] == 1
        assert counts['wheel_only'] is True and counts['origin_escapes'] == 0
        assert recovered['unknown_pre_outage_attempt']['outcome'] == 'UNRUN'
        assert recovered['checks'][7]['outcome'] == 'UNRUN' and recovered['closure_ids'] == []
        assert index['recovered_graph_fresh_child'] == lanes['Installed-recovered-fresh-child']
        # Original full check evidence survives through immutable complete refs;
        # earlier custody limitations remain UNRUN, not fresh raw verification.
        assert audit['complete_old_component_checks'] == self.obj(PACK+'full-audit.json',BASELINE)['complete_old_component_checks']

    def verify_source_order(self, index):
        order = self.obj(PACK+'G-source-integration-order.json')
        assert order['source_product_freeze'] == PRODUCT and order['source_product_tree'] == PRODUCT_TREE
        assert len(order['entries']) == 6 and len({q['topic'] for q in order['entries']}) == 6
        for entry in order['entries']:
            head, base = entry['published_head_or_product_source'], entry['true_slice_dependency_base']
            assert self.v.tree(head) == entry['tree']
            assert entry['not_G_acceptance'] is True
            actual = self.git('diff','--name-only',base,head).decode().splitlines()
            assert actual == entry['complete_diff_footprint_paths'], 'full source-order footprint:'+entry['lane']
            for commit in entry['implementation_commits']:
                self.git('merge-base','--is-ancestor',commit,head)
            self.footprints.append({'lane':entry['lane'],'topic':entry['topic'],'base':base,'head':head,'tree':entry['tree'],'paths':actual})
        assembly = order['assembled_installed_final']
        assert assembly['source'] == PRODUCT and assembly['tree'] == PRODUCT_TREE
        assert assembly['receipt_ref'] == REQUIRED_NEW['Installed-resource-forward']
        for name in ['wheel','rebuilt_sdist']:
            assert assembly[name] == {'PASS':91,'FAIL':0,'ERROR':0,'SKIP':0}
        assert assembly['retained_marker_controls'] == {'expected_raw_FAIL':6}
        assert order['historical_first_b5_source']['installed_each'] == {'PASS':130,'FAIL':32,'ERROR':0,'SKIP':0}
        assert order['G_local_readonly_reruns_packet'].startswith('G-local-causal-reruns.json;')
        packets = self.obj(PACK+'G-local-causal-reruns.json')
        assert packets['source_sha'] == PRODUCT and packets['source_tree'] == PRODUCT_TREE and packets['no_self_issued_authority'] is True
        assert len(packets['packets']) == 7
        original = {fid for q in packets['packets'] for fid in q['finding_ids']}
        assert original == {'B214','B56'}, 'extra original authority/optimizer prerequisite'
        for item in packets['packets']:
            assert item['unknown_input_refs'] is None and item['local_command'] is None
        product_paths = self.git('diff','--name-only','8236d9c368336a5ea20c1586f29aea7321db6536',PRODUCT,'--','policy-engine/src','policy-engine/hatch.toml').decode().splitlines()
        assert product_paths == index['product_source']['new_product_paths'], 'full actual product delta mismatch'
        return order,packets

    def verify_authored_patch(self):
        parent = self.git('rev-parse',self.target+'^').decode().strip()
        paths = self.git('diff','--name-only',parent,self.target).decode().splitlines()
        assert len(paths) == 44 and all(p.startswith('policy-engine/docs/') for p in paths), '44 doc-only authored paths'
        raw = self.git('diff','--no-ext-diff',parent,self.target)
        assert raw == PATCH.read_bytes(), 'author full patch differs from exact Git implementation diff'
        complete_json_deltas = {}
        for path in paths:
            if path.endswith('.json'):
                complete_json_deltas[path] = compare_json(json.loads(self.raw(path,parent)),json.loads(self.raw(path)))
        return {'parent':parent,'paths':paths,'patch_bytes':len(raw),'patch_sha256':sha(raw),'existing_full_patch_locator':str(PATCH),'complete_changed_JSON_leaves':complete_json_deltas}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',required=True);p.add_argument('--target',required=True);p.add_argument('--output',required=True)
    p.add_argument('--control',choices=['remove-original-binding','wrong-card-hash','missing-ID','wrong-source-tree','wrong-owner','stale-per-ID-hash'])
    a=p.parse_args();started=time.monotonic();review=Review(a.repo,a.target);issues=[];rows=[];patch=None;order=None;packets=None
    index=review.obj(PACK+'index.json');audit=review.obj(PACK+'full-audit.json')
    try:
        if a.control=='stale-per-ID-hash':
            index=copy.deepcopy(index);index['per_ID_complete_records'][0]['sha256']='0'*64
        rows=review.rows(index)
        if a.control:
            rows=copy.deepcopy(rows)
            if a.control=='remove-original-binding': rows[0]['original_card_refs'].clear()
            elif a.control=='wrong-card-hash': rows[0]['original_card_refs'][0]['sha256']='0'*64
            elif a.control=='missing-ID': rows.pop()
            elif a.control=='wrong-source-tree': rows[0]['scientific_implementation']['tree']='0'*40
            elif a.control=='wrong-owner': rows[0]['primary_owner_from_full_TSV']['source_closure_owner']='CAU-03'
        review.verify_metadata(index,audit,rows)
        order,packets=review.verify_source_order(index)
        patch=review.verify_authored_patch()
    except (AssertionError,KeyError,TypeError,ValueError,IndexError,subprocess.CalledProcessError) as e:
        issues.append({'exception':type(e).__name__,'message':str(e) or type(e).__name__})
    result={
        'schema':'F-independent-final-ledger-delta-review/v1',
        'check':'FAIL' if issues else 'PASS','control':a.control,
        'negative_harness_outcome': ('PASS' if issues else 'FAIL') if a.control else None,
        'target':{'sha':a.target,'tree':review.v.tree(a.target)},
        'product_source':index['product_source'],
        'previous_complete_audit':{'sha':BASELINE,'scope':'Complete previous1659stored/480decoded scientific custody audit preserved at its source; not rewalked by this metadata delta review'},
        'oracle_inputs':[bind(EXPECTED),bind(OLDER_VALIDATOR)],
        'replayer':bind(__file__),
        'environment':{'python':platform.python_version(),'executable':sys.executable,'purpose':'stdlib immutable Git metadata verifier; no product/backend execution'},
        'denominator':{'IDs':35,'bundles':17,'original_bindings':36},
        'recommendations':index['summary'],
        'issues':issues,
        'complete_independent_row_reconciliation':review.row_observations,
        'primary_and_card_metadata_artifacts_verified':list(review.v.artifacts.values()),
        'complete_deciding_check_pointer_count':len(review.v.check_refs),
        'actual_primary_json_selectors':review.v.pointers,
        'complete_current_manifest_metadata':review.registry_observations,
        'source_order_complete_actual_footprints':review.footprints,
        'authored_implementation_diff':patch,
        'criteria_scopes':{'original': '33closed/2limited;34PASS/1UNRUN', 'technical_original':'33closed/2limited','G_formal_closed':0,'assembled_readiness':'source519 affected91/profile plus6rawFAIL and separate ONEwheel child; no global/institutional/scientific approval'},
        'no_numerical_reruns':True,
        'no_unchanged_raw_output_rewalk':True,
        'limitations':['Historical175c four non-deciding references remain UNRUN; previous full-custody partiality retained','Python3.14 in-process DoWhy/EconML exclusions are UNRUN; genuine selected3.12 receipts separate','Original B214 supported partial/conditional route limited, B56 admitted common workload UNRUN','Missing exact Runtime/PDCsemantic/identification/value/currentlaw/Abridge positives remain distinct followups','Current source5957 scanner first+retry ERROR -9 incomplete;Ruff103FAIL/publicsurface38FAIL;P41not_established','Metadata delta review is not new numerical evidence, institutionally accepted code, or formal G finding closure'],
        'elapsed_s':time.monotonic()-started,
    }
    pathlib.Path(a.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['check','control','negative_harness_outcome','target','denominator','issues','complete_deciding_check_pointer_count','elapsed_s']},ensure_ascii=False,indent=2))
    print(json.dumps({'metadata_artifacts':len(review.v.artifacts),'primary_manifest_metadata':len(review.registry_observations),'source_order_topics':len(review.footprints),'output':a.output}))
    return int(bool(issues))

if __name__=='__main__':
    raise SystemExit(main())
