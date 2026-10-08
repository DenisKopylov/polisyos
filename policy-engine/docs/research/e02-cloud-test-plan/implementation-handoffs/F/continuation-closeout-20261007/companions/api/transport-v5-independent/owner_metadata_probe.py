"""Hash full owner selector metadata, without reading large selected payloads."""
from pathlib import Path
import collections,hashlib,json
OUT=Path(__file__).resolve().parent
INPUTS=[('/tmp/e02-F-continuation-20261007/graph/root519-G855-review/transfer-selection.json','664e03368ab39b6a28206906af574d557d69c125195e5f6d21df9807779cd1b2','files',42),('/tmp/e02-F-continuation-20261007/economics/recovery-review-20261007/transfer-selection-final.json','65409d69d6fdfd29a101b4b66aee5ca2ab3fdd34e837ac02689248ffa2dd2716','selection',73),('/tmp/e02-F-continuation-20261007/cau/ledger-recovery-review/final-review-transfer-selection.json','58885bdbb9bd1c366dedf1b1cce0695e4505ee3f07f6e53bbc9405a09d747ee7','items',563)]
results=[]
for path,expected,key,count in INPUTS:
 b=Path(path).read_bytes();sha=hashlib.sha256(b).hexdigest();assert sha==expected;obj=json.loads(b);keys=[k for k in ['files','items','selection'] if isinstance(obj.get(k),list)];assert keys==[key] and len(obj[key])==count
 results.append({'path':path,'bytes':len(b),'sha256':sha,'schema':key,'rows':count,'encodings':dict(collections.Counter(str(r.get('encoding','identity')) for r in obj[key]))})
result={'outcome':'PASS','complete_selector_metadata_only':True,'selected_large_payloads_read':False,'inputs':results};(OUT/'owner-metadata-results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
