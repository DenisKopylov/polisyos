#!/usr/bin/env python3
import argparse,gzip,hashlib,json,pathlib
ap=argparse.ArgumentParser();ap.add_argument('selection');a=ap.parse_args()
s=json.loads(pathlib.Path(a.selection).read_text());results=[]
for x in s['items']:
 b=pathlib.Path(x['path']).read_bytes()
 assert len(b)==x['bytes'] and hashlib.sha256(b).hexdigest()==x['sha256'],x['path']
 if x.get('encoding')=='gzip':
  v=gzip.decompress(b)
  assert len(v)==x['decoded_bytes'] and hashlib.sha256(v).hexdigest()==x['decoded_sha256'],x['path']
 results.append({'path':x['path'],'stored_check':'PASS','decoded_check':'PASS' if x.get('encoding') else 'not_encoded'})
print(json.dumps({'check':'PASS','selected_files':len(results),'stored_bytes':sum(x['bytes'] for x in s['items']),'decoded_bytes_encoded_only':sum(x.get('decoded_bytes',0) for x in s['items']),'actual_merge_sha':s['actual_merge_sha'],'scientific_execution':'UNRUN','results':results},indent=2))
