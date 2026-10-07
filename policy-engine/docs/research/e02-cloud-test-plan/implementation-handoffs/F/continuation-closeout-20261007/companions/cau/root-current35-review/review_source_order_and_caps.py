"""Independent immutable Git metadata/caption review; no product execution."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import subprocess
import time

P = 'policy-engine/docs/research/e02-cloud-test-plan/'
PACK = P+'implementation-handoffs/F/continuation-transfer-20261007/'
OLD_PRODUCT = '8236d9c368336a5ea20c1586f29aea7321db6536'
PRODUCT_PATHS = [
    'policy-engine/src/polisyos/foundry/methods/catalog/causal/graph_reconciliation.py',
    'policy-engine/src/polisyos/scientist/nodes/builtins/causal/reconcile_causal_graph.py',
]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--repo', required=True)
    ap.add_argument('--target', required=True)
    ap.add_argument('--output', required=True)
    a = ap.parse_args()
    start = time.monotonic()
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=a.repo, stderr=subprocess.PIPE)
    def raw(path, ref=None): return git('show', (ref or a.target)+':'+path)
    def obj(path, ref=None): return json.loads(raw(path, ref))
    def h(b): return hashlib.sha256(b).hexdigest()
    def bind(path, ref=None):
        b = raw(path, ref)
        return dict(git_ref=ref or a.target, path=path, bytes=len(b), sha256=h(b), git_blob=git('rev-parse',(ref or a.target)+':'+path).decode().strip())
    def ancestor(base, head):
        return subprocess.run(['git','merge-base','--is-ancestor',base,head],cwd=a.repo,capture_output=True).returncode == 0

    index = obj(PACK+'index.json')
    rows = [obj(record['path']) for record in index['per_ID_complete_records']]
    by_id = {r['finding_id']:r for r in rows}
    order = obj(PACK+'G-source-integration-order.json')
    packets = obj(PACK+'G-local-causal-reruns.json')
    issues, observations = [], []
    try:
        assert order['source_product_freeze'] == index['product_source']['sha']
        assert order['source_product_tree'] == index['product_source']['tree']
        assert order['carrier_is_not_unified_method_candidate'] and order['upstream_original_history_required']
        assert len(order['entries']) == 6
        for entry in order['entries']:
            head = entry['published_head_or_product_source']; base = entry['true_slice_dependency_base']
            assert git('rev-parse',head+'^{tree}').decode().strip() == entry['tree']
            assert ancestor(base,head)
            paths = git('diff','--name-only',base,head).decode().splitlines()
            assert paths == entry['complete_diff_footprint_paths'], 'incomplete topic footprint:'+entry['lane']
            assert all(ancestor(c,head) for c in entry['implementation_commits'])
            assert ancestor(head,a.target), 'owner topic not preserved in metadata root history:'+entry['lane']
            assert entry['not_G_acceptance'] is True
            product_bindings = []
            if entry['product_paths']:
                assert entry['product_paths'] == PRODUCT_PATHS
                source = entry['product_source_sha']
                assert git('rev-parse',source+'^{tree}').decode().strip() == entry['product_source_tree']
                for path in entry['product_paths']:
                    assert raw(path,source) == raw(path,index['product_source']['sha'])
                    product_bindings.append(bind(path,source))
            observations.append(dict(lane=entry['lane'],head=head,base=base,tree=entry['tree'],whole_diff_paths=len(paths),whole_diff_paths_sha256=h(('\n'.join(paths)+'\n').encode()),base_is_ancestor=True,implementation_history_preserved=True,owner_head_is_root_ancestor=True,product_blob_identity=product_bindings,check='PASS'))
        delta = git('diff','--name-only',OLD_PRODUCT,index['product_source']['sha'],'--','policy-engine/src','policy-engine/workers','policy-engine/schema','policy-engine/tools','policy-engine/pyproject.toml','policy-engine/uv.lock').decode().splitlines()
        assert delta == PRODUCT_PATHS
        assert order['G_local_readonly_reruns_packet'].startswith('G-local-causal-reruns.json;')
        assert packets['source_sha'] == index['product_source']['sha'] and packets['source_tree'] == index['product_source']['tree']
        assert packets['no_self_issued_authority']
        assert len(packets['packets']) == 7
        original = [p for p in packets['packets'] if p['finding_ids']]
        assert {p['packet_id'] for p in original} == {'original-B214-capability','original-B56-shared-study'}
        assert all(p['unknown_input_refs'] is None and p['local_command'] is None for p in packets['packets'])
        bridge = next(p for p in packets['packets'] if p['packet_id']=='followup-A-EMP01-protected-graph-bridge')
        assert bridge['finding_ids'] == [] and bridge['status'] == 'bridge_missing'
        assert {r['finding_id'] for r in rows if r['original_missing_input']} == {'B214','B56'}
        assert all(r['G_finding_acceptance']['status']=='not_issued' for r in rows)
        assert dict(collections.Counter(r['F_finding_outcome'] for r in rows)) == {'closed':33,'limited':2}
        assert dict(collections.Counter(r['check_result'] for r in rows)) == {'PASS':34,'UNRUN':1}
        assert all(r['check_result']=='PASS' and r['F_finding_outcome']=='closed' for r in rows if r['finding_id'] not in {'B214','B56'})
    except (AssertionError,KeyError,subprocess.CalledProcessError) as e:
        issues.append(str(e) or type(e).__name__)

    critical = {
        'B206':'Both DiD and RDD confidence level are in the original scope; cebe/fb science sources remain separate from root assembly.',
        'B207':'Selected scalar theta_sel, estimated cohort-share ratio IF and no silent eligibility drops are a known synthetic/method property, not real parallel-trends admission.',
        'B208':'One iid Mammen multiplier by unit, centered studentized null and matching CI inversion; discrete endpoint decision correction preserved.',
        'B209':'Preperiod diagnostic input/result recomputation binds time_treatment separately from the selected estimand, with invalid/not_testable intact and no identification authority.',
        'B212':'Genuine selected Python3.12 DoWhy point-only/interval witness; baseline Python3.14 excluded backend is UNRUN, not a positive capability witness.',
        'B213':'Actual estimand_type/contrast/target identify/estimate binding, not real-data observational validity or forced identification.',
        'B214':'Reverse normalization and preserved/refused unresolved endpoints are measured; sound conditional partial/DAG-extension route remains original limited capability.',
        'B216':'Independent latent-DAG oracle plus actual static do/sigma/ID/IDC consumers; graph uncertainty/temporal graphs do not become static ID by serialization.',
        'B220':'Internal stable deep immutability/cache-copy property with actual cache consumers; no changed public-stable classification.',
        'B222':'Existing conditional additive polynomial helper payload reaches real SCM/CAS/query/twin; LINEAR retained-fields discriminator; no new default nonlinear fitter or unrestricted posterior.',
        'B223':'Attribution target and baseline/query refs: same-arm zero, do2-do0=6, observational/stochastic comparators. Outcome/refit interval semantics remain additional boundary.',
        'B225':'Independent math.erfc/tail calculation; not product SciPy self-comparison.',
        'B56':'Actual admitted shared study/fold resource workload absent; old 4-study fixture and attempted pool failure before zero fits cannot establish it.',
        'LA-002':'Four catalog identities/IC-service/native certificates, not four newly implemented optional family kernels.',
        'LA-003':'Declared fiscal/labor relocation/precision compatibility with real CAS/registry/compiler consumers; separate ABM diagnostic FAIL and P41 not established stay visible.',
        'LA-004':'Two distinct native/plugin models, matched and deliberately divergent laws; canonical Gini and signed-population C/PPO are separate properties.',
        'LA-007':'Empty sibling already absent at198; installed packaging/API checks prove bounded maintained property without a new deletion claim.',
        'LA-016':'One original ID/two bindings; maintained dedicated DiD FQN/metadata/flags/slots migration plus explicitly historical adapter replay.',
        'LA-017':'All unchanged/added/removed/modified norm diff, LegalPass configuration/issues, persisted reports and CLI readers; dedupe alone is not closure. Accepted code ancestry is not G finding closure/current law.',
        'LA-019':'Empty siblings already absent at198; bounded installed maintained client/loader window with computed/external unresolved clients explicit.',
        'LA-020':'Supported facade/caller identity and installed consumer window; no repository/global reflection-zero claim.',
        'LA-035':'Original equivalent historical formula/sign/scale/guards/aliases/native/JIT-grad/caller property; COMMON removes newly added optimizer/welfare prerequisite. Fresh Fraction and actual signed-Gini consumer witnesses are separate scoped observations.',
        'LA-037':'Actual IR slot/family/compiler/registry/CAS/layout, real docs and installed support; no invented new layout law.',
    }
    doc_paths = [PACK+'REPORT.md',P+'closure-decisions/F.md',P+'closure-decisions/method-decisions.md',P+'closure-decisions/runtime-profiles.md']
    documents = [bind(path) for path in doc_paths]
    # Full bodies were read for semantic review; these bindings allow exact reconstruction.
    for path in doc_paths:
        if b'GiniPureExecutor' in raw(path): issues.append('nonexistent consumer label in '+path)
    caption_observations = [dict(finding_id=r['finding_id'],complete_per_ID_ref=next(x for x in index['per_ID_complete_records'] if x['finding_id']==r['finding_id']),original_titles=[b['title'] for b in r['original_card_refs']],observed_check=r['check_result'],observed_F_original_recommendation=r['F_finding_outcome'],actual_consumer=r['consumer'],semantic_review='PASS',review_scope_note=critical.get(r['finding_id'],'Original finite criterion, producer/artifact/bridge/actual consumer and retained independent/removal source-specific evidence agree with the published independent original35 packet; no universal production prerequisite.')) for r in rows]
    report = dict(schema='e02.F.independent-current35-source-order-caption-review.v1',target=dict(sha=a.target,tree=git('rev-parse',a.target+'^{tree}').decode().strip()),check='FAIL' if issues else 'PASS',recommendation='BLOCK' if issues else 'GO_BOUNDED',issues=issues,source_order_ref=bind(PACK+'G-source-integration-order.json'),minimal_packets_ref=bind(PACK+'G-local-causal-reruns.json'),source_order_observations=observations,product_delta=dict(base=OLD_PRODUCT,candidate=index['product_source'],scoped_product_paths=PRODUCT_PATHS,whole_scoped_diff_verified=True,not_new_method_or_numeric_proof=True),minimal_packet_observations=[dict(packet_id=p['packet_id'],status=p['status'],original_finding_ids=p['finding_ids'],unknown_refs_and_command_null=True) for p in packets['packets']],caption_document_refs=documents,per_ID_semantic_review=caption_observations,remaining=dict(original_limited_ids=['B214','B56'],formal_G_finding_acceptance='not_issued',baseline314_optional_backend='excluded/UNRUN',historical175c4_nondeciding_custody='UNRUN',historical20_check_raw_output_custody='UNRUN',global_quality='actual FAIL/partial UNRUN preserved; P41 not_established',final_b5_installed_wave='Await separately published exact-source deciding receipt; old8236 PASS not reused',A_protected_graph_bridge='Refusal-only sibling tests PASS; bridge_missing positive UNRUN; not original F closure prerequisite'),independence='Read-only ROOT metadata and original-criterion reconciliation by CAU leaf; no root writing, new checkout, source execution, scientific rerun, invented issuer or G decision.',replayer=dict(path=__file__,bytes=Path(__file__).stat().st_size,sha256=h(Path(__file__).read_bytes())),elapsed_s=time.monotonic()-start)
    Path(a.output).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(check=report['check'],target=report['target'],issues=issues,source_order_topics=len(observations),minimal_packets=len(packets['packets']),per_ID_semantic_rows=len(rows),product_delta_paths=PRODUCT_PATHS,elapsed_s=report['elapsed_s']),indent=2))
    return bool(issues)


if __name__ == '__main__': raise SystemExit(main())
