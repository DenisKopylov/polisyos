import argparse,json,pathlib,shutil
p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--out',required=True);a=p.parse_args();src=pathlib.Path(a.source);out=pathlib.Path(a.out);out.mkdir(parents=True,exist_ok=False)
for q in src.iterdir():
 if q.name!='policy-engine':(out/q.name).symlink_to(q,target_is_directory=q.is_dir())
product=out/'policy-engine';product.mkdir()
for q in (src/'policy-engine').iterdir():
 if q.name in ['src','tests']:shutil.copytree(q,product/q.name,symlinks=True)
 else:(product/q.name).symlink_to(q,target_is_directory=q.is_dir())
print(json.dumps({'source':str(src),'removal_clone':str(out),'copied_mutable_source_roots':['policy-engine/src','policy-engine/tests'],'unchanged_other_inputs':'symlinked original committed export bytes'}))
