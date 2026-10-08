"""Append full independent review custody; no Git mutation or scientific checks."""
import argparse,hashlib,json,sys,subprocess
from pathlib import Path
DESIGN=Path('/tmp/e02-F-continuation-20261007/fit-tmle/root-final-transport-design')
sys.path.insert(0,str(DESIGN))
from publish_transport_v5 import verify_original,write_exact
from transport_text_policy import transport_text_policy
PREFIX='policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/continuation-closeout-20261007'
SOURCE='cbfc2647b63b7b43e608532abb2159d3785bab42'
TREE='37e88297463ae4084c5812ba20fddfc65d373d3d'
def binding(p):
 b=p.read_bytes();return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--selection',type=Path,required=True);ap.add_argument('--repository',type=Path,required=True);args=ap.parse_args()
 assert subprocess.check_output(['git','-C',str(args.repository),'rev-parse','HEAD'],text=True).strip()==SOURCE
 assert subprocess.check_output(['git','-C',str(args.repository),'rev-parse','HEAD^{tree}'],text=True).strip()==TREE
 selected=json.loads(args.selection.read_text());items=next((selected[k] for k in ['items','files','selection'] if isinstance(selected.get(k),list)),None);assert items is not None
 paths=[];declared={}
 for row in items:
  p=Path(row.get('path',row.get('original_path','')));assert p.is_file() and not p.is_symlink();assert binding(p)=={'bytes':row['bytes'],'sha256':row['sha256']};paths.append(p);declared[str(p)]=row
 paths.append(args.selection)
 own=Path(__file__).resolve();paths.append(own)
 rootcap=own.parent
 paths += sorted(p for p in rootcap.iterdir() if p.is_file() and p!=own and p.suffix in ['.txt','.json'])
 seen=set();rows=[]
 for p in paths:
  if str(p) in seen:continue
  seen.add(str(p));rel=p.relative_to('/tmp/e02-F-continuation-20261007');raw=binding(p);profile=transport_text_policy(p);encoding='gzip' if profile['gzip_required'] else 'identity'
  prior=declared.get(str(p),{});compressed=prior.get('encoding') in ['gzip','gzip-lossless']
  if compressed:
   assert isinstance(prior.get('decoded_bytes'),int) and isinstance(prior.get('decoded_sha256'),str),'declared compressed input must bind decoded bytes'
   encoding='gzip'
  name=str(rel)+('.gz' if encoding=='gzip' and not compressed else '')
  row={'original_path':str(p),**raw,'disposition':'transport','encoding':encoding,'target_path':PREFIX+'/independent-materialized-review/companions/'+name,'role':'Complete independent materialized Git/35-card review or exact ROOT custody/command context; no new scientific or authority inference.'}
  if compressed:
   row.update(input_encoding='gzip',input_binding=raw,bytes=prior['decoded_bytes'],sha256=prior['decoded_sha256'])
  verify_original(row);rows.append(write_exact(row,args.repository))
 manifest={'schema':'policyos.e02.independent_materialized_review_transport.v1','source_sha':SOURCE,'source_tree':TREE,'main_receipt':'b300da2e134a67fbd6f585a21ab42286c356fe7e','files':rows,'counts':{'files':len(rows),'stored_bytes':sum(x['bytes'] for x in rows),'decoded_bytes':sum(x['decoded_bytes'] for x in rows)},'sanitation':'none; exact identity or lossless gzip using independently-reviewed V5 writer','science_tests_run':False,'future_receipt_SHA_not_asserted':True}
 target=args.repository/(PREFIX+'/independent-materialized-review/outputs.json');target.parent.mkdir(parents=True,exist_ok=True);assert not target.exists();target.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'manifest_path':str(target),**binding(target),'counts':manifest['counts']},indent=2))
if __name__=='__main__':main()
