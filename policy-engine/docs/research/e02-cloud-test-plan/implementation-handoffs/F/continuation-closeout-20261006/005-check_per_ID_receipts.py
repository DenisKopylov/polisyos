"""Check full original cards and current decisions in immutable per-ID carriers."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--packet-sha', required=True)
args = parser.parse_args()
task_root = Path(__file__).resolve().parent
run_root = task_root / args.packet_sha
index = json.loads((run_root / 'immutable-index.json').read_bytes())
rows = {row['finding_id']: row for row in index['finding_rows']}
observations = []
blocks = []


def project(value, shape):
    if isinstance(shape, dict):
        return {key: project(value[key], sub) for key, sub in shape.items()}
    if isinstance(shape, list):
        if len(value) != len(shape):
            raise ValueError('Card/decision list length mismatch.')
        return [project(v, s) for v, s in zip(value, shape)]
    return value


for record in index['current_per_ID_receipts']:
    raw = subprocess.check_output(['git', '-C', '/workspace/e02-F-closeout-20261006', 'show', args.packet_sha + ':' + record['path']])
    value = json.loads(raw)
    row = value['complete_original_bound_row']
    identifier = row['finding_id']
    common = set(rows[identifier]) & set(row)
    mismatches = [name for name in common if project(row[name], rows[identifier][name]) != rows[identifier][name]]
    for block in row['original_source_criterion_refs']:
        body = block['complete_original_block'].encode('utf8')
        blocks.append({'finding_id': identifier, 'source_sha': block['source_sha'],
                       'source_path': block['source_path'], 'lines': block['lines'],
                       'declared_bytes': block['bytes'], 'declared_sha256': block['sha256'],
                       'actual_bytes': len(body), 'actual_sha256': hashlib.sha256(body).hexdigest(),
                       'check': 'PASS' if len(body) == block['bytes'] and hashlib.sha256(body).hexdigest() == block['sha256'] else 'FAIL'})
    observations.append({'finding_id': identifier, 'ref': record,
                         'bytes_hash_match': len(raw) == record['bytes'] and hashlib.sha256(raw).hexdigest() == record['sha256'],
                         'source_sha': value['source_sha'], 'source_tree': value['source_tree'],
                         'shared_row_fields': len(common), 'mismatches': mismatches,
                         'formal_G_acceptance': value['formal_G_acceptance'],
                         'independent_packet_review_resolution': value['independent_packet_review_resolution']})
valid = (len(observations) == 35 and len({r['finding_id'] for r in observations}) == 35
         and len(blocks) == 36 and all(b['check'] == 'PASS' for b in blocks)
         and all(r['bytes_hash_match'] and not r['mismatches']
                 and r['source_sha'] == index['current_root_source_sha']
                 and r['source_tree'] == index['current_root_source_tree_sha']
                 and r['formal_G_acceptance'] == 'not_issued' for r in observations))
output = {'check': 'PASS' if valid else 'FAIL', 'packet_sha': args.packet_sha,
          'actual_full_Git_per_ID_receipts': observations, 'full_original_card_blocks': blocks,
          'scope': 'Index shared-field projection plus additional complete per-ID original text; no ignored decision difference.',
          'prior_unprojected_comparison': 'FAIL preserved: all35 differences were additional complete_original_block fields, not changed original refs or current decisions.'}
target = run_root / 'per-ID-projection-check.json'
target.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'check': output['check'], 'receipts': len(observations), 'full_original_blocks': len(blocks),
                  'total_shared_field_comparisons': sum(r['shared_row_fields'] for r in observations)}))
raise SystemExit(0 if valid else 1)
