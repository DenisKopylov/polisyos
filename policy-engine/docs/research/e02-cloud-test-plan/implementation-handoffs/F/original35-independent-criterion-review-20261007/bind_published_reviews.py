"""Append immutable published reviewer bindings to the already-read F35 packet."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--repo', required=True)
parser.add_argument('--input', required=True)
parser.add_argument('--output', required=True)
args = parser.parse_args()
packet = json.loads(Path(args.input).read_bytes())
prefix = 'policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/'

def ref(sha, path):
    data = subprocess.check_output(['git', 'show', sha + ':' + path], cwd=args.repo)
    return {'git_ref': sha, 'path': path, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(), 'git_blob': subprocess.check_output(['git', 'rev-parse', sha + ':' + path], cwd=args.repo).decode().strip()}

api = '605dadeb76499c3f6eadd95e16a8df1bbb2cb89f'
eco = 'fa53da2812eaa8578f79ec914b3b2abe4c491f3d'
ap = prefix + 'api-installed-graph-reconciliation-20261007'
ep = prefix + 'economic-baseline-consumer-proof-20261007'
packet['prepublication_review_output'] = {'sha256': hashlib.sha256(Path(args.input).read_bytes()).hexdigest(), 'bytes': Path(args.input).stat().st_size, 'role': 'Earlier source-bound scratch analysis; current complete packet appends actual published owner review bindings without changing row recommendations.'}
packet['fresh_independent_review_refs'] = {
    'economics193': dict(ref(eco, ep + '/independent-cau/independent-review.json'), material_role='Complete independent frozen193 scientific/native consumer review'),
    'economics_c008_doc_delta': dict(ref(eco, ep + '/independent-cau/doc-delta-review.json'), material_role='Independent nine-line doc-only append review; runtime/test bytes193 unchanged'),
    'API6f39': dict(ref(api, ap + '/independent-cau/independent-review.json'), material_role='Complete independent final6f test-carrier review of installed8236 runtime; initial7f observer failure retained'),
}
packet['published_owner_materials'] = [
    {'receipt': ref(api, ap + '.json'), 'manifest_ref': ref(api, ap + '/full-output-manifest.json'), 'record_count': 120, 'reviewed_product_source': '8236d9c368336a5ea20c1586f29aea7321db6536', 'test_carrier': '6f39b0edc48ec59db3731fa917c615b9f97e4dc0', 'role': 'Full author and independent native/removal/history bytes; test-only carrier is not a new installed runtime source'},
    {'receipt': ref(eco, ep + '.json'), 'manifest_pointer': '/evidence_transfer/manifest', 'record_count': 108, 'science_source': '193b3582a72c640c1d06a131f93502654a77a36a', 'doc_candidate': 'c0084cd530c1dbe01eedfb9b5c24f055954a97be', 'role': 'Full source/native/oracle/census/removal/history bytes; unchanged baseline runtime equals reviewed8236 provider'},
]
for row in packet['rows']:
    fid = row['finding_id']
    if fid in ('LA-007', 'LA-019', 'LA-020', 'B219', 'B220'):
        row['current_20261007_supplemental_review_refs'] = [packet['published_owner_materials'][0]['receipt'], packet['fresh_independent_review_refs']['API6f39']]
    if fid in ('LA-035', 'LA-004'):
        row['current_20261007_supplemental_review_refs'] = [packet['published_owner_materials'][1]['receipt'], packet['fresh_independent_review_refs']['economics193'], packet['fresh_independent_review_refs']['economics_c008_doc_delta']]
packet['custody_claim_scope'] = 'ROOT072 historical custody dispositions are explicitly recorded source claims, not a new full3387-artifact independent custody audit. New API120/ECO108 full stored/decoded companion bindings and current criterion/card/owner/ref/tree inputs are separately verified by the portable verifier; historical175c4 and textual lint remain UNRUN/nondeciding.'
out = Path(args.output)
assert not out.exists(), 'append-only scratch publication output must be new'
out.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'check': 'PASS', 'output': str(out), 'bytes': out.stat().st_size, 'sha256': hashlib.sha256(out.read_bytes()).hexdigest(), 'row_recommendations_unchanged': True, 'published_owner_records': 228, 'formal_G_closure': False}))
