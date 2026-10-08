"""Portable Git-only readback of the narrow ECO source, evidence and caption basis."""
import hashlib
import json
import lzma
from pathlib import Path
import subprocess
import sys

REPO = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('/workspace/e02-F-closeout-20261006')
OUT = Path(__file__).resolve().parent
ECO = 'fa53da2812eaa8578f79ec914b3b2abe4c491f3d'
SOURCE = 'c0084cd530c1dbe01eedfb9b5c24f055954a97be'
ROOT = '7ba0ce11648aac20351e7e9f4bf3fa61c0a847de'
OLD = '5609d09cbf519f01bde1ea81c6b3ee4a36a484a8'
PREFIX = 'policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/economic-baseline-consumer-proof-20261007'

def read(ref, path):
    return subprocess.check_output(['git', 'show', ref + ':' + path], cwd=REPO)

def identity(body):
    return {'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}

primary = json.loads(read(ECO, PREFIX + '.json'))
deciding = {}
for row in primary['evidence_transfer']['manifest']:
    body = read(ECO, row['path'])
    assert identity(body) == {k:row[k] for k in ('bytes','sha256')}
    raw = lzma.decompress(body) if row['encoding'] == 'xz' else body
    assert identity(raw) == {'bytes':row['raw_bytes'],'sha256':row['raw_sha256']}
    deciding[row['path']] = raw
caption = json.loads(deciding[PREFIX + '/current-caption-role-classification.json'])
assert len(caption['rows']) == caption['denominator'] == 31
for row in caption['rows']:
    body = read(row['git_ref'],row['path'])
    assert identity(body) == {k:row[k] for k in ('bytes','sha256')}
    lines = body.decode().splitlines()
    for match in row['matches']:
        assert lines[match['line']-1] == match['text'], (row['path'],match['line'])
for row in primary['source_bindings']:
    assert read(ROOT,row['path']) == read(row['git_ref'],row['path'])
paths = ['policy-engine/docs/research/e02-cloud-test-plan/closure-decisions/' + x for x in ('F.md','method-decisions.md','runtime-profiles.md')]
observed_hashes = {
    paths[0]: {'bytes':26757,'sha256':'4538c75a0aaf11eb253e9d7831d884859acb4c3ff9c81fea62ee2e0df8fdf2c6'},
    paths[1]: {'bytes':106381,'sha256':'1dce4ad02656b5c9d873c2ed6066264a7b3ec3f02766001f437920a789e3f3ca'},
    paths[2]: {'bytes':35578,'sha256':'ad7b68c4f9a35086e7492bfe84fb4f6a854e1d4f27f6addef07d562c06bd42d1'},
}
docs = []
for path in paths:
    body = read(ROOT,path)
    old = read(OLD,path)
    assert identity(body) == observed_hashes[path], path
    docs.append({'git_ref':ROOT,'path':path,**identity(body),'matches_previously_read_working_delta':True,'old_ref':OLD,'old_identity':identity(old)})
fragment = json.loads(deciding[PREFIX+'/fragment.stdout.txt.xz'])
assert fragment['errors']==[] and len(fragment['findings'])==1
assert fragment['findings'][0]['severity']=='warning'
for name, marker in [('native.stdout.txt.xz','83 passed'),('removal-baseline-sign.stdout.txt.xz','13 failed, 8 passed'),('removal-baseline-guard.stdout.txt.xz','1 failed, 20 passed'),('removal-gini-domain.stdout.txt.xz','5 failed, 2 passed'),('independent-cau/native.stdout.xz','28 passed'),('independent-cau/siblings.stdout.xz','55 passed'),('independent-cau/gini-removal.stdout.xz','2 failed')]:
    assert marker in deciding[PREFIX+'/'+name].decode(), name
result={'schema':'policyos.e02.readonly_publication_binding.v1','outcome':'PASS','root_doc_ref':ROOT,'root_tree':subprocess.check_output(['git','rev-parse',ROOT+'^{tree}'],cwd=REPO).decode().strip(),'eco_primary':{'git_ref':ECO,'path':PREFIX+'.json',**identity(read(ECO,PREFIX+'.json'))},'complete_evidence_count':len(deciding),'complete_decoded_bytes':sum(len(b) for b in deciding.values()),'all31_caption_source_bytes_and_literal_locators':'PASS','four_owned_sources_match_root':'PASS','three_current_docs':docs,'fragment_warning_preserved':fragment['findings'],'numeric_suites_executed_here':False,'historical_caption_decision':'BLOCK at5609 for presenting absent new optimizer/intent as LA035 relocation prerequisite; corrected ROOT7ba0 economic captions GO_BOUNDED','scope':'Economic caption/source/evidence companion only. Full35 formal acceptance and unrelated statuses assigned to ROOT/CAU/G.'}
(OUT/'publication-readback.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False,indent=2))
